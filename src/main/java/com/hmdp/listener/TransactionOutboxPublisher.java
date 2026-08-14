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
