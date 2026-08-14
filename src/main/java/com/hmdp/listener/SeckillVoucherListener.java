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
import org.springframework.data.redis.connection.stream.Consumer;
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
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.nio.charset.StandardCharsets;
import java.util.stream.Collectors;

@Slf4j
@Component
public class SeckillVoucherListener {

    private static final int PENDING_BATCH_SIZE = 20;
    private static final int MAX_PENDING_SCAN = 200;

    private final ExecutorService executor = Executors.newSingleThreadExecutor(r -> {
        Thread thread = new Thread(r, "seckill-order-consumer");
        thread.setDaemon(true);
        return thread;
    });
    private final String consumerName = "order-" + java.lang.management.ManagementFactory
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
        int scanned = 0;
        while (scanned < MAX_PENDING_SCAN) {
            final Range<String> range = abandonedPendingCursor == null
                    ? Range.unbounded()
                    : Range.rightUnbounded(Range.Bound.exclusive(abandonedPendingCursor));
            PendingBatch batch = stringRedisTemplate.execute(
                    (RedisCallback<PendingBatch>) connection -> {
                    PendingMessages pending = connection.xPending(
                            RedisConstants.SECKILL_ORDER_STREAM_KEY.getBytes(StandardCharsets.UTF_8),
                            RedisConstants.SECKILL_ORDER_STREAM_GROUP, range,
                            (long) PENDING_BATCH_SIZE);
                    if (pending.isEmpty()) {
                        return PendingBatch.empty();
                    }
                    List<String> ids = pending.stream()
                            .filter(message -> message.getElapsedTimeSinceLastDelivery().compareTo(
                                    Duration.ofSeconds(30)) >= 0)
                            .map(message -> message.getIdAsString())
                            .collect(Collectors.toList());
                    if (ids.isEmpty()) {
                        return new PendingBatch(java.util.Collections.emptyList(),
                                pending.get(pending.size() - 1).getIdAsString(), pending.size());
                    }
                    List<ByteRecord> records = connection.xClaim(
                            RedisConstants.SECKILL_ORDER_STREAM_KEY.getBytes(StandardCharsets.UTF_8),
                            RedisConstants.SECKILL_ORDER_STREAM_GROUP,
                            consumerName,
                            org.springframework.data.redis.connection.RedisStreamCommands.XClaimOptions
                                    .minIdle(Duration.ofSeconds(30))
                                    .ids(ids.toArray(new String[0])));
                    List<MapRecord<String, Object, Object>> claimed = new java.util.ArrayList<>();
                    for (ByteRecord record : records) {
                        MapRecord<String, String, String> deserialized = record.deserialize(
                                stringRedisTemplate.getStringSerializer(),
                                stringRedisTemplate.getStringSerializer(),
                                stringRedisTemplate.getStringSerializer());
                        @SuppressWarnings({"unchecked", "rawtypes"})
                        MapRecord<String, Object, Object> converted = (MapRecord) deserialized;
                        claimed.add(converted);
                    }
                    return new PendingBatch(claimed,
                            pending.get(pending.size() - 1).getIdAsString(), pending.size());
                });
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

    private void processRecords(List<MapRecord<String, Object, Object>> records) {
        if (records == null || records.isEmpty()) {
            return;
        }
        for (MapRecord<String, Object, Object> record : records) {
            try {
                VoucherOrder order = toOrder(record.getValue());
                OrderCreationResult result = voucherOrderService.handleVoucherOrder(order);
                if (result == OrderCreationResult.ACTIVE_ORDER_EXISTS) {
                    voucherOrderService.releaseRejectedReservation(order, true, false);
                } else if (result == OrderCreationResult.OUT_OF_STOCK) {
                    // Redis was ahead of MySQL. Keep the pre-decrement so cached stock converges to DB.
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
            return new PendingBatch(java.util.Collections.emptyList(), null, 0);
        }
    }
}
