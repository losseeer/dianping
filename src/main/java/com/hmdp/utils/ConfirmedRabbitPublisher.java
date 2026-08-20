package com.hmdp.utils;

import org.springframework.amqp.core.MessagePostProcessor;
import org.springframework.amqp.rabbit.connection.CorrelationData;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Component;

import javax.annotation.Resource;
import java.util.concurrent.TimeUnit;

/**
 * 带发布确认的RabbitMQ发送器 —— 【八股:消息丢失第一环:生产者怎么知道broker收到了?】
 *
 * 【八股:publisher-confirm 与 returns 回调的区别】
 * - Confirm(确认):broker是否"收到了这条消息"(落盘/入队前),nack说明broker出问题
 * - Return(退回):消息被broker接收但"路由不到任何队列"(routingKey错/队列不存在)
 * 两者都正常才算发送成功,缺一不可
 *
 * 【八股:为什么这里同步等待5秒?】
 * CorrelationData.getFuture().get(5s)把异步ack变成同步语义:
 * 发送方立刻知道结果,失败直接抛异常 → 上层Outbox把事件标回待重试
 * 超时时间要在"及时发现失败"和"误判慢网络"之间取折衷
 * 注意:必须在yaml开启 publisher-confirm-type: correlated 和 publisher-returns: true
 */
@Component
public class ConfirmedRabbitPublisher {

    private static final long CONFIRM_TIMEOUT_SECONDS = 5L;

    @Resource
    private RabbitTemplate rabbitTemplate;

    public void send(String exchange, String routingKey, Object payload, String correlationId) {
        send(exchange, routingKey, payload, null, correlationId);
    }

    public void send(String exchange, String routingKey, Object payload,
                     MessagePostProcessor postProcessor, String correlationId) {
        CorrelationData correlationData = new CorrelationData(correlationId);
        if (postProcessor == null) {
            rabbitTemplate.convertAndSend(exchange, routingKey, payload, correlationData);
        } else {
            rabbitTemplate.convertAndSend(
                    exchange, routingKey, payload, postProcessor, correlationData);
        }

        try {
            CorrelationData.Confirm confirm = correlationData.getFuture()
                    .get(CONFIRM_TIMEOUT_SECONDS, TimeUnit.SECONDS);
            if (!confirm.isAck()) {
                throw new IllegalStateException("RabbitMQ拒绝消息: " + confirm.getReason());
            }
            if (correlationData.getReturnedMessage() != null) {
                throw new IllegalStateException("RabbitMQ消息未路由到队列: " + correlationId);
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("等待RabbitMQ确认时线程被中断", e);
        } catch (java.util.concurrent.ExecutionException
                 | java.util.concurrent.TimeoutException e) {
            throw new IllegalStateException("等待RabbitMQ发布确认失败", e);
        }
    }
}
