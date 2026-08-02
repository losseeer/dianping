package com.hmdp.service;

import com.hmdp.dto.PaymentDTO;
import com.hmdp.dto.Result;

/**
 * 支付服务接口 —— 交易闭环核心模块
 *
 * 【八股：支付系统的核心职责】
 * 1. 发起支付：创建支付流水，调用第三方支付SDK
 * 2. 处理回调：接收第三方支付平台的异步通知，更新订单状态
 * 3. 申请退款：发起退款流程，更新订单为退款中
 * 4. 处理退款回调：接收退款结果，恢复库存
 *
 * 【八股：为什么支付服务要独立出来？】
 * 1. 单一职责：订单服务管订单，支付服务管支付，职责清晰
 * 2. 可扩展：未来支持多种支付方式（微信、支付宝、银行卡），互不影响
 * 3. 可测试：Mock支付服务比Mock整个订单服务简单
 * 4. 对账独立：支付流水和订单是两条数据线，方便对账
 */
public interface IPaymentService {

    /**
     * 发起支付（模拟微信/支付宝沙箱）
     * 【八股：支付流程】
     * 用户下单 → 选支付方式 → 调用支付SDK → 返回支付链接/二维码
     * → 用户扫码/跳转支付 → 第三方平台回调 → 更新订单状态
     *
     * @param dto 支付请求（订单ID + 支付方式）
     * @return 支付链接/二维码URL
     */
    Result payOrder(PaymentDTO dto);

    /**
     * 处理支付回调（第三方支付平台异步通知）
     * 【八股：为什么要处理回调？】
     * 支付是异步的，用户在前端扫码支付后，支付平台会异步回调我们的接口
     * 我们在回调中确认支付结果，更新订单状态
     * 这是分布式事务最终一致性的体现——不保证实时一致，但保证最终一致
     *
     * @param tradeNo 第三方支付流水号
     * @param orderId 业务订单号
     * @return 处理结果
     */
    Result handlePayNotify(String tradeNo, Long orderId);

    /**
     * 申请退款
     * 【八股：退款流程】
     * 用户发起退款 → 订单状态改为退款中 → 调用第三方退款API
     * → 第三方平台处理退款 → 回调通知退款结果 → 恢复库存
     *
     * @param orderId 订单ID
     * @return 退款申请结果
     */
    Result refundOrder(Long orderId);

    /**
     * 处理退款回调
     * 【八股：退款回调要做什么？】
     * 1. 更新订单状态为已退款
     * 2. 恢复秒杀库存（DB stock+1 + Redis INCR）
     * 3. 删除Redis中一人一单记录（SREM）
     * 4. 通知用户退款已到账
     *
     * @param tradeNo 第三方退款流水号
     * @param orderId 业务订单号
     * @return 处理结果
     */
    Result handleRefund(String tradeNo, Long orderId);
}
