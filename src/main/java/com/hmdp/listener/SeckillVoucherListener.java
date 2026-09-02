package com.hmdp.listener;

import cn.hutool.core.bean.BeanUtil;
import com.hmdp.config.QueueConfig;
import com.hmdp.entity.VoucherOrder;
import com.hmdp.enums.OrderCreationResult;
import com.hmdp.enums.OrderStatus;
import com.hmdp.service.IVoucherOrderService;
import com.hmdp.utils.ConfirmedRabbitPublisher;
import com.hmdp.utils.RedisConstants;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.core.MessagePostProcessor;
import org.springframework.data.redis.connection.RedisConnection;
import org.springframework.data.redis.connection.RedisStreamCommands;
import org.springframework.data.redis.connection.stream.Consumer;
import org.springframework.data.redis.connection.stream.PendingMessage;
import org.springframework.data.redis.connection.stream.ByteRecord;
import org.springframework.data.redis.connection.stream.PendingMessages;
import org.springframework.data.redis.connection.stream.MapRecord;
import org.springframework.data.redis.connection.stream.ReadOffset;
import org.springframework.data.redis.connection.stream.StreamOffset;
import org.springframework.data.redis.connection.stream.StreamReadOptions;
import org.springframework.data.domain.Range;
import org.springframework.data.redis.core.RedisCallback;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import javax.annotation.PostConstruct;
import javax.annotation.PreDestroy;
import javax.annotation.Resource;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.lang.management.ManagementFactory;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.nio.charset.StandardCharsets;
import java.util.stream.Collectors;

/**
 * 秒杀订单Stream消费者 —— 【八股:Redis Stream 消费者组与消息可靠性】
 *
 * 【八股:为什么削峰选Redis Stream而不是RabbitMQ?】
 * - 秒杀预扣本来就在Redis里完成,Lua脚本内直接XADD,一次网络往返零跨系统窗口
 * - Stream自带消费者组语义:XREADGROUP/XACK/PENDING/XCLAIM,轻量且故障转移能力强
 * - RabbitMQ留给延迟取消场景(需要成熟TTL+死信),各取所长
 *
 * 【八股:消息不丢的三层可靠性(本类的核心设计)】
 * 1. 正常路径:处理成功才XACK+XDEL,处理异常保留在PENDING列表
 * 2. 自愈路径:每轮循环重读自己的PENDING(processOwnPending)——覆盖"处理中崩溃"的消息
 * 3. 故障转移:XCLAIM认领其他崩溃实例遗留的消息(claimAbandonedPending,
 *    minIdle=30s保证不抢正在处理的消息)——这是Stream相对普通队列的关键优势
 *
 * 【八股:为什么单线程消费?】
 * newSingleThreadExecutor:①同一券的库存扣减天然串行,避免并发落库冲突
 * ②消费顺序可控;吞吐不够时按voucherId分片到多个组/实例水平扩展(daemon线程不阻塞JVM退出)
 */
@Slf4j
@Component
public class SeckillVoucherListener {

    private static final int PENDING_BATCH_SIZE = 20;
    private static final int MAX_PENDING_SCAN = 200;
    /** 只认领空闲超过该时长的消息：避免抢走其他实例正在处理中的消息（处理慢≠崩溃） */
    private static final Duration IDLE_CLAIM_THRESHOLD = Duration.ofSeconds(30);

    private final ExecutorService executor = Executors.newSingleThreadExecutor(r -> {
        Thread thread = new Thread(r, "seckill-order-consumer");
        thread.setDaemon(true);
        return thread;
    });
    private final String consumerName = "order-" + ManagementFactory
            .getRuntimeMXBean().getName().replace('@', '-');
    private volatile boolean running = true;
    private String ownPendingCursor = "0";
    private String abandonedPendingCursor;

    @Resource
    private IVoucherOrderService voucherOrderService;
    @Resource
    private StringRedisTemplate stringRedisTemplate;
    @Resource
    private ConfirmedRabbitPublisher confirmedRabbitPublisher;

    @PostConstruct
    public void start() {
        createConsumerGroup();
        executor.submit(this::consumeLoop);
    }

    @PreDestroy
    public void stop() {
        running = false;
        executor.shutdownNow();
    }

    private void createConsumerGroup() {
        try {
            stringRedisTemplate.execute((RedisCallback<Object>) connection -> connection.execute(
                    "XGROUP",
                    "CREATE".getBytes(),
                    RedisConstants.SECKILL_ORDER_STREAM_KEY.getBytes(),
                    RedisConstants.SECKILL_ORDER_STREAM_GROUP.getBytes(),
                    "0".getBytes(),
                    "MKSTREAM".getBytes()
            ));
        } catch (Exception e) {
            if (e.getMessage() == null || !e.getMessage().contains("BUSYGROUP")) {
                throw e;
            }
        }
    }

    private void consumeLoop() {
        // 【八股:XREADGROUP语义】COUNT 10每轮最多拉10条;BLOCK 2000没有新消息时阻塞2秒
        // (阻塞读优于忙轮询:空转不烧CPU);ReadOffset.lastConsumed()从组内未消费处继续
        while (running && !Thread.currentThread().isInterrupted()) {
            try {
                List<MapRecord<String, Object, Object>> records = stringRedisTemplate.opsForStream().read(
                        Consumer.from(RedisConstants.SECKILL_ORDER_STREAM_GROUP, consumerName),
                        StreamReadOptions.empty().count(10).block(Duration.ofSeconds(2)),
                        StreamOffset.create(RedisConstants.SECKILL_ORDER_STREAM_KEY, ReadOffset.lastConsumed())
                );
                processRecords(records);
                processOwnPending();
                claimAbandonedPending();
            } catch (Exception e) {
                if (running) {
                    log.error("消费秒杀订单Stream失败, consumer={}", consumerName, e);
                    try {
                        Thread.sleep(200);
                    } catch (InterruptedException interrupted) {
                        Thread.currentThread().interrupt();
                    }
                }
            }
        }
    }

    private void processOwnPending() {
        int scanned = 0;
        while (scanned < MAX_PENDING_SCAN) {
            List<MapRecord<String, Object, Object>> pending = stringRedisTemplate.opsForStream().read(
                    Consumer.from(RedisConstants.SECKILL_ORDER_STREAM_GROUP, consumerName),
                    StreamReadOptions.empty().count(PENDING_BATCH_SIZE),
                    StreamOffset.create(
                            RedisConstants.SECKILL_ORDER_STREAM_KEY,
                            ReadOffset.from(ownPendingCursor))
            );
            if (pending == null || pending.isEmpty()) {
                ownPendingCursor = "0";
                return;
            }
            processRecords(pending);
            scanned += pending.size();
            ownPendingCursor = pending.get(pending.size() - 1).getId().getValue();
            if (pending.size() < PENDING_BATCH_SIZE) {
                ownPendingCursor = "0";
                return;
            }
        }
    }

    private void claimAbandonedPending() {
        // 【八股:XCLAIM故障转移】XPENDING列出"已投递未ACK"的消息及其归属消费者和空闲时长
        // 某消费者崩溃后其PENDING消息永远不会被ACK——另一个实例用XCLAIM把所有权
        // 抢过来重新处理。minIdleTime=30s是安全阀:只认领"明显被遗弃"的消息,
        // 不会抢走仍在正常处理中的消息(处理慢≠崩溃)
        int scanned = 0;
        while (scanned < MAX_PENDING_SCAN) {
            PendingBatch batch = readAbandonedBatch();
            if (batch == null || batch.scanned == 0) {
                abandonedPendingCursor = null;
                return;
            }
            processRecords(batch.records);
            scanned += batch.scanned;
            abandonedPendingCursor = batch.lastId;
            if (batch.scanned < PENDING_BATCH_SIZE) {
                abandonedPendingCursor = null;
                return;
            }
        }
    }

    /**
     * 扫一轮"其他实例遗留"的PENDING消息：XPENDING列出 → 过滤空闲超30s的 → XCLAIM认领并反序列化。
     */
    private PendingBatch readAbandonedBatch() {
        final Range<String> range = abandonedPendingCursor == null
                ? Range.unbounded()
                : Range.rightUnbounded(Range.Bound.exclusive(abandonedPendingCursor));
        return stringRedisTemplate.execute((RedisCallback<PendingBatch>) connection -> {
            PendingMessages pending = connection.xPending(
                    RedisConstants.SECKILL_ORDER_STREAM_KEY.getBytes(StandardCharsets.UTF_8),
                    RedisConstants.SECKILL_ORDER_STREAM_GROUP, range,
                    (long) PENDING_BATCH_SIZE);
            if (pending.isEmpty()) {
                return PendingBatch.empty();
            }
            List<String> idleIds = pending.stream()
                    .filter(message -> message.getElapsedTimeSinceLastDelivery().compareTo(
                            IDLE_CLAIM_THRESHOLD) >= 0)
                    .map(PendingMessage::getIdAsString)
                    .collect(Collectors.toList());
            String lastId = pending.get(pending.size() - 1).getIdAsString();
            if (idleIds.isEmpty()) {
                return new PendingBatch(Collections.emptyList(), lastId, pending.size());
            }
            return new PendingBatch(claimRecords(connection, idleIds), lastId, pending.size());
        });
    }

    /**
     * XCLAIM认领消息并反序列化为 MapRecord（ByteRecord → StringSerializer 解码）
     */
    private List<MapRecord<String, Object, Object>> claimRecords(
            RedisConnection connection, List<String> ids) {
        List<ByteRecord> records = connection.xClaim(
                RedisConstants.SECKILL_ORDER_STREAM_KEY.getBytes(StandardCharsets.UTF_8),
                RedisConstants.SECKILL_ORDER_STREAM_GROUP,
                consumerName,
                RedisStreamCommands.XClaimOptions.minIdle(IDLE_CLAIM_THRESHOLD).ids(ids.toArray(new String[0])));
        List<MapRecord<String, Object, Object>> claimed = new ArrayList<>();
        for (ByteRecord record : records) {
            MapRecord<String, String, String> deserialized = record.deserialize(
                    stringRedisTemplate.getStringSerializer(),
                    stringRedisTemplate.getStringSerializer(),
                    stringRedisTemplate.getStringSerializer());
            @SuppressWarnings({"unchecked", "rawtypes"})
            MapRecord<String, Object, Object> converted = (MapRecord) deserialized;
            claimed.add(converted);
        }
        return claimed;
    }

    private void processRecords(List<MapRecord<String, Object, Object>> records) {
        // 【八股:消费端必须幂等】Stream重投/claim/重启都会造成同一条消息被处理多次
        // 兜底在handleVoucherOrder内:Redisson锁(用户+券粒度) + 订单主键存在性检查,
        // "处理过"直接返回ALREADY_PROCESSED,重复处理是无害的
        if (records == null || records.isEmpty()) {
            return;
        }
        for (MapRecord<String, Object, Object> record : records) {
            try {
                VoucherOrder order = toOrder(record.getValue());
                OrderCreationResult result = voucherOrderService.handleVoucherOrder(order);
                if (result == OrderCreationResult.ACTIVE_ORDER_EXISTS) {
                    // 【八股:失败补偿】重复单:回滚Redis库存,但保留一人一单资格(防止反复穿透)
                    voucherOrderService.releaseRejectedReservation(order, true, false);
                } else if (result == OrderCreationResult.OUT_OF_STOCK) {
                    // Redis was ahead of MySQL. Keep the pre-decrement so cached stock converges to DB.
                    // 【八股:不回滚的智慧】DB库存不足说明Redis领先——保留Redis预扣,
                    // 让缓存库存向DB收敛,回滚反而会造成Redis超卖
                    voucherOrderService.releaseRejectedReservation(order, false, true);
                } else {
                    sendOrderDelayMessage(order);
                }
                acknowledgeAndDelete(record);
            } catch (IllegalArgumentException e) {
                log.error("丢弃非法秒杀订单消息: id={}", record.getId(), e);
                acknowledgeAndDelete(record);
            } catch (RuntimeException e) {
                log.error("秒杀订单消息处理失败，保留pending等待重试: id={}", record.getId(), e);
            }
        }
    }

    private void acknowledgeAndDelete(MapRecord<String, Object, Object> record) {
        stringRedisTemplate.opsForStream().acknowledge(
                RedisConstants.SECKILL_ORDER_STREAM_KEY,
                RedisConstants.SECKILL_ORDER_STREAM_GROUP,
                record.getId());
        try {
            stringRedisTemplate.opsForStream().delete(
                    RedisConstants.SECKILL_ORDER_STREAM_KEY, record.getId());
        } catch (RuntimeException e) {
            log.warn("删除已完成秒杀Stream记录失败: id={}", record.getId(), e);
        }
    }

    private VoucherOrder toOrder(Map<Object, Object> values) {
        VoucherOrder order = BeanUtil.fillBeanWithMap(values, new VoucherOrder(), true);
        if (order.getCreateTime() == null) {
            Object epoch = values.get("createEpoch");
            long epochSecond = epoch == null ? Instant.now().getEpochSecond()
                    : Long.parseLong(epoch.toString());
            order.setCreateTime(LocalDateTime.ofInstant(
                    Instant.ofEpochSecond(epochSecond), ZoneId.systemDefault()));
        }
        order.setStatus(OrderStatus.UNPAID.getCode());
        if (order.getId() == null || order.getUserId() == null || order.getVoucherId() == null) {
            throw new IllegalArgumentException("秒杀订单消息字段不完整");
        }
        return order;
    }

    private void sendOrderDelayMessage(VoucherOrder order) {
        // 【八股:消息级TTL动态扣减】异步落库有延迟,若固定发30分钟TTL,
        // 实际超时窗口会变成"落库时刻起30分钟"(比用户预期长)
        // 按下单时间算剩余:remaining = 30min - 已流逝时间,保证"下单起30分钟"精确取消
        // 注意:消息级expiration与队列级x-message-ttl并存时取较小者生效
        long elapsedMillis = order.getCreateTime() == null ? 0L
                : Math.max(0L, Duration.between(
                        order.getCreateTime(), LocalDateTime.now()).toMillis());
        long remainingMillis = Math.max(1L, QueueConfig.ORDER_DELAY_TTL - elapsedMillis);
        MessagePostProcessor expiration = message -> {
            message.getMessageProperties().setExpiration(String.valueOf(remainingMillis));
            return message;
        };
        confirmedRabbitPublisher.send(
                QueueConfig.ORDER_DELAY_EXCHANGE,
                QueueConfig.ORDER_DELAY_ROUTING_KEY,
                order.getId().toString(), expiration, "order-delay:" + order.getId());
    }

    private static final class PendingBatch {
        private final List<MapRecord<String, Object, Object>> records;
        private final String lastId;
        private final int scanned;

        private PendingBatch(List<MapRecord<String, Object, Object>> records,
                             String lastId, int scanned) {
            this.records = records;
            this.lastId = lastId;
            this.scanned = scanned;
        }

        private static PendingBatch empty() {
            return new PendingBatch(Collections.emptyList(), null, 0);
        }
    }
}
