package com.hmdp.utils;

import org.springframework.amqp.core.MessagePostProcessor;
import org.springframework.amqp.rabbit.connection.CorrelationData;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Component;

import javax.annotation.Resource;
import java.util.concurrent.TimeUnit;

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
