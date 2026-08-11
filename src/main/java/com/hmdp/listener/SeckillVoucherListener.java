package com.hmdp.listener;

import cn.hutool.json.JSONUtil;
import com.hmdp.config.QueueConfig;
import com.hmdp.entity.VoucherOrder;
import com.hmdp.service.IVoucherOrderService;
import com.rabbitmq.client.Channel;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.core.MessagePostProcessor;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Component;

import javax.annotation.Resource;
import java.io.IOException;

/**
 * 秒杀券订单监听器 —— 消费MQ消息，异步创建订单
 *
 * 【设计原则】
 * - 消费端必须走 IVoucherOrderService#handleVoucherOrder → #createVoucherOrder 链路，
 *   不允许直接 baseMapper.save() 裸写：
 *   1. 保证 Redisson 分布式锁兜底（防止 MQ 重复投递 / QA+QD 双消费者同时命中同一用户导致重复下单）
 *   2. 保证 createVoucherOrder 上的 @Transactional 生效
 *   3. 保证"一人一单 DB 二次校验 + 乐观锁扣 seckill_stock + save 订单 + 清理 pending 缓存"的原子一致性
 * - 使用手动 ACK（Channel#basicAck/#basicNack）：显式确认处理成功/失败，防止异常被吃掉后
 *   RabbitMQ 仍认为消费成功、消息丢失但订单实际未入 DB。
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class SeckillVoucherListener {

    @Resource
    private IVoucherOrderService voucherOrderService;

    @Resource
    private RabbitTemplate rabbitTemplate;

    /**
     * QA 正常消费者
     */
    @RabbitListener(queues = "QA")
    public void receivedA(Message message, Channel channel) throws Exception {
        long tag = message.getMessageProperties().getDeliveryTag();
        try {
            String msg = new String(message.getBody());
            log.info("[QA] 收到秒杀落库消息: msg={}", msg);
            VoucherOrder voucherOrder = JSONUtil.toBean(msg, VoucherOrder.class);
            if (voucherOrder == null || voucherOrder.getId() == null
                    || voucherOrder.getUserId() == null || voucherOrder.getVoucherId() == null) {
                log.warn("[QA] 消息非法，直接丢弃：msg={}", msg);
                channel.basicAck(tag, false);
                return;
            }
            voucherOrderService.handleVoucherOrder(voucherOrder);

            // 保存/落库成功后发送延迟取消消息（计时起点 = 落库成功时刻）
            sendOrderDelayMessage(voucherOrder.getId());
            channel.basicAck(tag, false);
        } catch (Exception e) {
            log.error("[QA] 消费秒杀落库失败，tag={}, body={}", tag,
                    message.getBody() == null ? null : new String(message.getBody()), e);
            try {
                // 异常 requeue=false，进入死信队列 QD 做兜底；避免无限重试阻塞 QA 队列
                channel.basicNack(tag, false, false);
            } catch (IOException ioe) {
                log.error("[QA] basicNack 失败", ioe);
            }
        }
    }

    /**
     * QD 死信消费者（兜底）
     */
    @RabbitListener(queues = "QD")
    public void receivedD(Message message, Channel channel) throws Exception {
        long tag = message.getMessageProperties().getDeliveryTag();
        try {
            String msg = new String(message.getBody());
            log.info("[QD] 死信队列收到秒杀落库消息: msg={}", msg);
            VoucherOrder voucherOrder = JSONUtil.toBean(msg, VoucherOrder.class);
            if (voucherOrder == null || voucherOrder.getId() == null
                    || voucherOrder.getUserId() == null || voucherOrder.getVoucherId() == null) {
                log.warn("[QD] 消息非法，丢弃：msg={}", msg);
                channel.basicAck(tag, false);
                return;
            }
            voucherOrderService.handleVoucherOrder(voucherOrder);

            sendOrderDelayMessage(voucherOrder.getId());
            channel.basicAck(tag, false);
        } catch (Exception e) {
            log.error("[QD] 死信消费秒杀落库失败，tag={}, body={}", tag,
                    message.getBody() == null ? null : new String(message.getBody()), e);
            try {
                // 死信消费失败不再 requeue，避免循环；依赖 pending 缓存 TTL + 支付时主动落库兜底
                channel.basicNack(tag, false, false);
            } catch (IOException ioe) {
                log.error("[QD] basicNack 失败", ioe);
            }
        }
    }

    /**
     * 发送订单延迟取消消息（TTL = QueueConfig.ORDER_DELAY_TTL，30 分钟）
     */
    private void sendOrderDelayMessage(Long orderId) {
        if (orderId == null) {
            log.warn("orderId为空，跳过发送延迟取消消息");
            return;
        }
        try {
            MessagePostProcessor messagePostProcessor = message -> {
                message.getMessageProperties().setExpiration(String.valueOf(QueueConfig.ORDER_DELAY_TTL));
                return message;
            };
            rabbitTemplate.convertAndSend(
                    QueueConfig.ORDER_DELAY_EXCHANGE,
                    QueueConfig.ORDER_DELAY_ROUTING_KEY,
                    orderId.toString(),
                    messagePostProcessor
            );
            log.info("已发送订单延迟取消消息: orderId={}, TTL={}ms", orderId, QueueConfig.ORDER_DELAY_TTL);
        } catch (Exception e) {
            log.error("发送订单延迟取消消息失败: orderId={}", orderId, e);
        }
    }
}
