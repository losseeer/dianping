package com.hmdp.listener;

import cn.hutool.json.JSONUtil;
import com.hmdp.config.QueueConfig;
import com.hmdp.entity.VoucherOrder;
import com.hmdp.service.impl.SeckillVoucherServiceImpl;
import com.hmdp.service.impl.VoucherOrderServiceImpl;
import com.rabbitmq.client.Channel;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.core.MessagePostProcessor;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Component;

import javax.annotation.Resource;

/**
 * 秒杀券订单监听器 —— 消费MQ消息，异步创建订单
 *
 * 【八股：消息队列异步下单的完整流程】
 * 1. 用户点击秒杀 → Lua脚本预检（Redis库存判断+一人一单判断+扣库存）
 * 2. 预检通过 → 发送订单消息到MQ（QA队列，TTL 10s）
 * 3. 本监听器消费消息 → 保存订单到数据库 + 扣减DB库存
 * 4. 保存订单后 → 发送延迟消息到ORDER_DELAY_QUEUE（TTL 30分钟）
 * 5. 30分钟后 → 延迟消息过期进入死信队列ORDER_CANCEL_QUEUE
 * 6. OrderDelayListener消费死信队列 → 检查订单是否已支付，未支付则取消
 *
 * 完整链路：秒杀 → 异步落库 → 延迟取消 → 支付/超时取消
 *
 * 【八股：为什么要发延迟消息？】
 * 秒杀下单后订单状态是"未支付"
 * 如果用户一直不支付，库存就被占用了（Redis库存-1，DB库存-1）
 * 发送延迟消息，30分钟后检查：
 * - 如果用户已支付 → 正常流程，不处理
 * - 如果用户未支付 → 自动取消订单，恢复库存
 * 这样保证了库存不会被无限期占用
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class SeckillVoucherListener {

    @Resource
    SeckillVoucherServiceImpl seckillVoucherService;
    @Resource
    VoucherOrderServiceImpl voucherOrderService;

    /**
     * RabbitTemplate —— 用于发送延迟消息到订单延迟队列
     * 【八股：为什么要在这里注入RabbitTemplate？】
     * 保存订单后需要发送延迟取消消息，这个操作在消费者中完成
     * 而不是在生产者(seckillVoucher)中完成，因为：
     * 1. 延迟消息的计时起点应该是"订单落库成功"而非"秒杀成功"
     * 2. 如果订单落库失败，不应该发送延迟取消消息
     * 3. 消费者保存成功后再发延迟消息，保证时序正确
     */
    @Resource
    private RabbitTemplate rabbitTemplate;

    /**
     * sheng  消费者1
     * @param message
     * @param channel
     * @throws Exception
     */
    @RabbitListener(queues = "QA")
    public void receivedA(Message message, Channel channel)throws Exception{
        String msg=new String(message.getBody());
        log.info("正常队列:");
        VoucherOrder voucherOrder = JSONUtil.toBean(msg, VoucherOrder.class);
        log.info(voucherOrder.toString());
        voucherOrderService.save(voucherOrder);//保存到数据库
        //数据库秒杀库存减一
        Long voucherId=voucherOrder.getVoucherId();
        seckillVoucherService.update()
                .setSql("stock = stock - 1") // set stock = stock - 1
                .eq("voucher_id", voucherId).gt("stock", 0) // where id = ? and stock > 0
                .update();

        // 【八股：保存订单后发送延迟取消消息】
        // 订单落库成功后，发送延迟消息到ORDER_DELAY_QUEUE
        // 30分钟后如果用户未支付，消息过期进入死信队列，触发自动取消
        sendOrderDelayMessage(voucherOrder.getId());

    }

    /**
     * sheng  消费者2
     * @param message
     * @throws Exception
     */
    @RabbitListener(queues = "QD")
    public void receivedD(Message message)throws Exception{
        log.info("死信队列:");
        String msg=new String(message.getBody());
        VoucherOrder voucherOrder = JSONUtil.toBean(msg, VoucherOrder.class);
        log.info(voucherOrder.toString());
        voucherOrderService.save(voucherOrder);

        Long voucherId=voucherOrder.getVoucherId();
        seckillVoucherService.update()
                .setSql("stock = stock - 1") // set stock = stock - 1
                .eq("voucher_id", voucherId).gt("stock", 0) // where id = ? and stock > 0
                .update();

        // 死信队列消费者也发送延迟取消消息（兜底）
        sendOrderDelayMessage(voucherOrder.getId());

    }

    /**
     * 发送订单延迟取消消息
     *
     * 【八股：per-message TTL设置】
     * 通过MessagePostProcessor为每条消息单独设置过期时间
     * 消息体内容为orderId（字符串），30分钟后过期进入死信队列
     *
     * 【八股：为什么用per-message TTL而不是队列级TTL？】
     * 1. 灵活性：不同订单可以设置不同的超时时间（比如VIP用户40分钟）
     * 2. 安全性：即使队列没有配置x-message-ttl，消息也能按时过期
     * 3. 但有队头阻塞问题：后面的消息即使先过期也要等前面的
     *    本项目所有消息TTL相同(30min)，不存在此问题
     *
     * 【八股：convertAndSend参数说明】
     * 参数1: exchange - 交换机名称（ORDER_DELAY_EXCHANGE）
     * 参数2: routingKey - 路由键（order.delay）
     * 参数3: message - 消息内容（orderId字符串）
     * 参数4: messagePostProcessor - 消息后处理器（设置TTL）
     *
     * MessagePostProcessor是函数式接口，用lambda实现：
     * message.getMessageProperties().setExpiration("1800000")
     * 设置过期时间为30分钟（毫秒）
     */
    private void sendOrderDelayMessage(Long orderId) {
        if (orderId == null) {
            log.warn("orderId为空，跳过发送延迟取消消息");
            return;
        }
        try {
            // 构建消息后处理器，设置per-message TTL
            MessagePostProcessor messagePostProcessor = message -> {
                // 设置消息过期时间（毫秒）—— 30分钟
                message.getMessageProperties().setExpiration(String.valueOf(QueueConfig.ORDER_DELAY_TTL));
                return message;
            };
            // 发送延迟消息：orderId作为消息体
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
