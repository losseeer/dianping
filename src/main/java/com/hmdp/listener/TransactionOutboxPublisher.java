package com.hmdp.listener;

import cn.hutool.json.JSONUtil;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.UpdateWrapper;
import com.hmdp.config.QueueConfig;
import com.hmdp.entity.TransactionOutbox;
import com.hmdp.entity.VoucherOrder;
import com.hmdp.mapper.TransactionOutboxMapper;
import com.hmdp.service.IVoucherOrderService;
import com.hmdp.utils.ConfirmedRabbitPublisher;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import javax.annotation.Resource;
import java.time.LocalDateTime;
import java.util.List;

/**
 * 本地事件表(Outbox)发布器 —— 【八股:Outbox模式解决什么问题?】
 *
 * 【八股:"DB事务成功"和"MQ发送成功"为什么无法原子?】
 * 方案A:事务里直接发MQ → 发送成功后事务回滚 = 幽灵消息(消费者处理了一个不存在的业务变更)
 * 方案B:事务提交后再发MQ → 提交后、发送前进程崩溃 = 消息永远丢失
 * 根因:数据库和MQ是两个系统,没有共享事务
 *
 * Outbox解法:业务事务里同库insert一条事件记录(与业务同事务,天然原子),
 * 后台任务扫表把事件真正发出去,发送成功才标记完成——最坏"重复发送",
 * 由消费端幂等兜底(至少一次语义)
 *
 * 【八股:为什么不用RocketMQ事务消息?】
 * 事务消息需要实现回查接口,broker与生产者强交互;Outbox只依赖本地DB+定时扫描,
 * 对MQ选型无侵入,还可顺便落审计。代价是扫描有延迟(本配置1秒)和事件表膨胀(需归档)
 */
@Slf4j
@Component
public class TransactionOutboxPublisher {

    public static final String PAY_NOTIFY = "PAY_NOTIFY";
    public static final String REFUND = "REFUND";
    public static final String REDIS_COMPENSATION = "REDIS_COMPENSATION";

    @Resource
    private TransactionOutboxMapper outboxMapper;
    @Resource
    private ConfirmedRabbitPublisher confirmedRabbitPublisher;
    @Resource
    private IVoucherOrderService voucherOrderService;

    @Scheduled(fixedDelayString = "${transaction.outbox.publish-interval-ms:1000}")
    public void publishPendingEvents() {
        // 0. 自愈:卡在"发送中(status=2)"超过1分钟的事件重置回待发送
        //    (发送中途崩溃的实例永远不会回来标记它,必须有超时回收,类似分布式锁的TTL兜底)
        outboxMapper.update(null, new UpdateWrapper<TransactionOutbox>()
                .set("status", 0)
                .set("next_retry_time", LocalDateTime.now())
                .set("update_time", LocalDateTime.now())
                .eq("status", 2)
                .lt("update_time", LocalDateTime.now().minusMinutes(1)));
        List<TransactionOutbox> events = outboxMapper.selectList(new QueryWrapper<TransactionOutbox>()
                .eq("status", 0)
                .le("next_retry_time", LocalDateTime.now())
                .orderByAsc("id")
                .last("LIMIT 50"));
        for (TransactionOutbox event : events) {
            // 【八股:CAS抢占防多实例重复发】update ... set status=2 where id=? and status=0
            // 只有一个实例能更新成功(affected=1),其余实例抢不到直接跳过
            // 这与秒杀"条件更新订单状态"是同一个数据库CAS思想,无需引入分布式锁
            boolean claimed = outboxMapper.update(null, new UpdateWrapper<TransactionOutbox>()
                    .set("status", 2)
                    .set("update_time", LocalDateTime.now())
                    .eq("id", event.getId())
                    .eq("status", 0)) == 1;
            if (claimed) {
                event.setStatus(2);
                publish(event);
            }
        }
    }

    private void publish(TransactionOutbox event) {
        try {
            if (REDIS_COMPENSATION.equals(event.getEventType())) {
                VoucherOrder order = JSONUtil.toBean(event.getPayload(), VoucherOrder.class);
                if (order.getId() == null || order.getUserId() == null
                        || order.getVoucherId() == null) {
                    throw new IllegalArgumentException("Redis补偿事件字段不完整");
                }
                voucherOrderService.releaseRejectedReservation(order, true, true);
                markSent(event);
                return;
            }
            String exchange;
            String routingKey;
            if (PAY_NOTIFY.equals(event.getEventType())) {
                exchange = QueueConfig.PAY_NOTIFY_EXCHANGE;
                routingKey = QueueConfig.PAY_NOTIFY_ROUTING_KEY;
            } else if (REFUND.equals(event.getEventType())) {
                exchange = QueueConfig.REFUND_EXCHANGE;
                routingKey = QueueConfig.REFUND_ROUTING_KEY;
            } else {
                markFailed(event, "未知事件类型");
                return;
            }
            confirmedRabbitPublisher.send(exchange, routingKey, event.getPayload(),
                    "outbox:" + event.getId() + ":" + event.getRetryCount());
            markSent(event);
        } catch (Exception e) {
            markFailed(event, e.getMessage());
        }
    }

    private void markSent(TransactionOutbox event) {
        outboxMapper.update(null, new UpdateWrapper<TransactionOutbox>()
                .set("status", 1)
                .set("update_time", LocalDateTime.now())
                .eq("id", event.getId())
                .eq("status", 2));
    }

    private void markFailed(TransactionOutbox event, String reason) {
        // 【八股:指数退避重试】delay = min(2^retry, 300s):
        // 每失败一次等待翻倍,避免下游故障时被固定频率重试打死;封顶防止无限增长
        // (与Agent侧LLM重试、Redisson锁重试是同一思想)
        int retry = event.getRetryCount() == null ? 1 : event.getRetryCount() + 1;
        long delaySeconds = Math.min(300, 1L << Math.min(retry, 8));
        outboxMapper.update(null, new UpdateWrapper<TransactionOutbox>()
                .set("retry_count", retry)
                .set("status", 0)
                .set("next_retry_time", LocalDateTime.now().plusSeconds(delaySeconds))
                .set("update_time", LocalDateTime.now())
                .eq("id", event.getId())
                .eq("status", 2));
        log.warn("Outbox事件发布失败, id={}, type={}, retry={}, reason={}",
                event.getId(), event.getEventType(), retry, reason);
    }
}
