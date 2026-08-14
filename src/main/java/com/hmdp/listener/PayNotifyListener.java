package com.hmdp.listener;

import cn.hutool.json.JSONUtil;
import com.hmdp.config.QueueConfig;
import com.hmdp.service.IPaymentService;
import com.hmdp.dto.Result;
import com.rabbitmq.client.Channel;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;

import javax.annotation.Resource;
import java.util.Map;

/**
 * 支付通知监听器 —— 监听支付通知队列和退款队列
 *
 * 【八股：为什么支付通知要单独用MQ？】
 * 支付回调(handlePayNotify)需要快速返回给第三方支付平台
 * 但通知用户（发短信、APP推送）耗时较长，不能在回调中同步做
 * 所以把通知消息发到MQ，由本监听器异步处理
 *
 * 优点：
 * 1. 支付回调快速返回，不被通知逻辑拖慢
 * 2. 通知失败可以重试（MQ的自动重试机制）
 * 3. 解耦：支付逻辑和通知逻辑分离
 *
 * 【八股：消息队列的异步解耦模式】
 * 这是一种典型的"生产者-消费者"异步模式：
 * - handlePayNotify是生产者，只负责发消息
 * - PayNotifyListener是消费者，负责处理通知
 * - 两者通过MQ解耦，互不阻塞
 *
 * 生产环境增强：
 * 1. 消费失败时记录到数据库，人工补偿
 * 2. 设置最大重试次数，超过后转人工
 * 3. 不同通知渠道（短信、推送、邮件）可以用不同队列
 */
@Slf4j
@Component
public class PayNotifyListener {

    @Resource
    private IPaymentService paymentService;

    /**
     * 监听支付通知队列
     * 收到支付成功消息后，记录日志并模拟发送推送通知给用户
     *
     * 【八股：推送通知的实现方式】
     * 1. APP推送：极光推送/友盟推送/FCM
     * 2. 短信通知：阿里云短信/腾讯云短信
     * 3. 站内信：写入数据库的消息表
     * 4. 微信模板消息：公众号/小程序模板消息
     * 这里用log模拟，实际项目对接具体推送SDK
     */
    @RabbitListener(queues = QueueConfig.PAY_NOTIFY_QUEUE)
    public void handlePayNotify(Message message, Channel channel) throws Exception {
        String msg = new String(message.getBody());
        log.info("收到支付通知消息: {}", msg);

        try {
            // 解析消息内容
            Map<String, Object> map = JSONUtil.toBean(msg, Map.class);
            Long orderId = Long.valueOf(map.get("orderId").toString());
            Long userId = Long.valueOf(map.get("userId").toString());
            Object amountObj = map.get("amount");
            Long amount = amountObj != null ? Long.valueOf(amountObj.toString()) : null;

            // 模拟发送推送通知给用户
            log.info("【模拟推送】用户{}您好，您的订单{}支付成功，支付金额{}分", userId, orderId, amount);

            // 模拟发送短信
            log.info("【模拟短信】您的订单{}已支付成功，感谢您的购买！", orderId);

            // 实际项目中这里会调用：
            // pushService.send(userId, "支付成功", "订单" + orderId + "支付成功");
            // smsService.send(userPhone, "您的订单已支付成功");

        } catch (Exception e) {
            log.error("处理支付通知消息异常: msg={}", msg, e);
            throw e;
        }
    }

    /**
     * 监听退款队列
     * 收到退款消息后，模拟调用第三方退款API，然后调用handleRefund完成退款
     *
     * 【八股：退款的异步处理流程】
     * 1. refundOrder()：更新订单为退款中，发送消息到REFUND_QUEUE
     * 2. 本监听器收到消息：模拟调用第三方退款API
     * 3. 退款API返回成功后：调用handleRefund恢复库存
     *
     * 【八股：退款失败的重试策略】
     * 如果第三方退款API调用失败：
     * 1. 抛异常 → 消息会重新入队（手动ACK模式下）
     * 2. 设置重试次数限制（3次）
     * 3. 超过重试次数 → 转入死信队列 → 人工处理
     * 4. 或者记录到退款失败表，定时任务补偿
     */
    @RabbitListener(queues = QueueConfig.REFUND_QUEUE)
    public void handleRefundMessage(Message message, Channel channel) throws Exception {
        String msg = new String(message.getBody());
        log.info("收到退款处理消息: {}", msg);

        try {
            // 解析消息内容
            Map<String, Object> map = JSONUtil.toBean(msg, Map.class);
            Long orderId = Long.valueOf(map.get("orderId").toString());
            String tradeNo = map.get("tradeNo") != null ? map.get("tradeNo").toString() : "";
            Long amount = map.get("amount") == null ? null
                    : Long.valueOf(map.get("amount").toString());

            // 模拟调用第三方退款API
            log.info("【模拟退款API】调用第三方退款API，tradeNo={}, orderId={}", tradeNo, orderId);

            // 模拟退款API返回成功
            boolean refundSuccess = simulateRefundApi(tradeNo, orderId);
            if (!refundSuccess) {
                log.error("第三方退款API返回失败，tradeNo={}, orderId={}", tradeNo, orderId);
                throw new RuntimeException("退款API调用失败");
            }

            // 退款成功，调用handleRefund完成退款（更新订单状态、恢复库存）
            Result result = paymentService.handleRefund(tradeNo, orderId, amount);
            if (result == null || Boolean.FALSE.equals(result.getSuccess())) {
                throw new IllegalStateException(result == null
                        ? "退款回调无结果" : result.getErrorMsg());
            }

            log.info("退款处理完成: orderId={}, tradeNo={}", orderId, tradeNo);

        } catch (Exception e) {
            log.error("处理退款消息异常: msg={}", msg, e);
            throw e;
        }
    }

    /**
     * 模拟第三方退款API调用
     * 【八股：真实退款API的调用】
     * 微信退款：POST https://api.mch.weixin.qq.com/secapi/pay/refund
     * 支付宝退款：alipay.trade.refund
     * 这里直接返回true模拟成功
     */
    private boolean simulateRefundApi(String tradeNo, Long orderId) {
        // 模拟退款API处理耗时
        try {
            Thread.sleep(100);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        return true;
    }
}
