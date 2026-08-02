package com.hmdp.listener;

import com.hmdp.config.QueueConfig;
import com.hmdp.service.IVoucherOrderService;
import com.rabbitmq.client.Channel;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;

import javax.annotation.Resource;

/**
 * 订单延迟队列监听器 —— 监听死信队列，处理超时未支付订单
 *
 * 【八股：延迟队列的原理】
 * 1. 消息发送到ORDER_DELAY_QUEUE（普通队列），设置TTL=30分钟
 * 2. 消息在队列中等待30分钟，期间用户可以支付
 * 3. 30分钟后消息过期，成为"死信"(Dead Letter)
 * 4. 死信被转发到ORDER_DEAD_EXCHANGE（死信交换机）
 * 5. 死信交换机根据routing key路由到ORDER_CANCEL_QUEUE（死信队列）
 * 6. 本监听器从ORDER_CANCEL_QUEUE消费消息，执行超时取消
 *
 * 消息流转路径：
 *   生产者 → ORDER_DELAY_EXCHANGE → ORDER_DELAY_QUEUE(30min TTL)
 *   → [过期成为死信] → ORDER_DEAD_EXCHANGE → ORDER_CANCEL_QUEUE
 *   → OrderDelayListener消费
 *
 * 【八股：死信(Dead Letter)的三种来源】
 * 1. 消息被拒绝(basic.reject/basic.nack)且requeue=false
 * 2. 消息TTL过期
 * 3. 队列达到最大长度
 * 本项目用的是第2种：消息TTL过期
 *
 * 【八股：为什么用死信队列而不是定时任务？】
 * 1. 精确性：每条消息的TTL独立计时，30分钟后精确过期
 *    定时任务有扫描间隔（比如每分钟扫一次），不够精确
 * 2. 解耦：消息队列负责计时和投递，业务代码只管消费
 * 3. 可扩展：多个消费者可以同时消费死信队列，提高处理速度
 * 4. 可靠性：消息持久化，即使应用重启也不会丢失
 *
 * 【八股：per-message TTL的队头阻塞问题】
 * 队列级TTL(x-message-ttl)有队头阻塞问题：
 * 如果队头消息TTL=30min，后面消息TTL=10s
 * 后面的消息即使先过期，也要等队头消息过期后才会被检查
 * 解决方案：用rabbitmq_delayed_message_exchange插件
 * 本项目所有消息TTL相同(30min)，不存在队头阻塞问题
 */
@Slf4j
@Component
public class OrderDelayListener {

    @Resource
    private IVoucherOrderService voucherOrderService;

    /**
     * 监听订单取消死信队列
     * 收到消息后调用voucherOrderService.handleOrderTimeout(orderId)
     *
     * 【八股：消息消费的可靠性】
     * 消息从延迟队列到死信队列的过程中，RabbitMQ会保证不丢失：
     * 1. 消息持久化：Queue和Message都是durable的
     * 2. 手动ACK：消费者处理成功后才确认（这里用自动ACK）
     * 3. 死信转发：RabbitMQ内部保证死信转发可靠性
     *
     * 【八股：消费失败怎么办？】
     * 如果handleOrderTimeout抛异常，消息会：
     * - 自动ACK模式下：消息丢失（已被消费但处理失败）
     * - 手动ACK模式下：消息会重新入队，无限重试
     * 生产环境建议：
     * 1. 用手动ACK + 重试次数限制
     * 2. 超过重试次数后转发到失败队列人工处理
     * 3. 或者用RabbitMQ的死信队列做重试（重试队列→死信队列→重试队列循环）
     */
    @RabbitListener(queues = QueueConfig.ORDER_CANCEL_QUEUE)
    public void handleOrderCancel(Message message, Channel channel) throws Exception {
        String msg = new String(message.getBody());
        log.info("收到订单超时取消消息: {}", msg);

        try {
            Long orderId = Long.parseLong(msg.trim());
            // 调用订单服务处理超时
            // handleOrderTimeout内部会检查订单状态：
            // - 如果还是UNPAID → 取消订单 + 恢复库存
            // - 如果已经PAID → 忽略（用户已支付）
            voucherOrderService.handleOrderTimeout(orderId);
        } catch (NumberFormatException e) {
            log.error("订单超时取消消息格式错误: {}", msg, e);
        } catch (Exception e) {
            log.error("处理订单超时取消异常: msg={}", msg, e);
            throw e;
        }
    }
}
