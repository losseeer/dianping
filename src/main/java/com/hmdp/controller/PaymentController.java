package com.hmdp.controller;

import com.hmdp.annotation.RateLimit;
import com.hmdp.dto.PaymentDTO;
import com.hmdp.dto.Result;
import com.hmdp.service.IPaymentService;
import com.hmdp.service.IVoucherOrderService;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;

/**
 * 支付控制器 —— 交易闭环入口
 *
 * 【八股：RESTful API设计规范】
 * POST /pay          → 发起支付（创建资源）
 * POST /pay/notify    → 支付回调（第三方调用）
 * POST /pay/refund/{id} → 申请退款
 * POST /pay/refund/callback → 退款回调（第三方调用）
 *
 * 【八股：回调接口的安全设计】
 * 第三方回调接口需要验证签名，防止伪造请求
 * 微信回调：验证签名 + 验证金额 + 验证订单号
 * 支付宝回调：验证签名 + 验证app_id
 * 这里是模拟环境，省略签名验证
 *
 * 【八股：回调接口需要排除登录拦截器】
 * 第三方支付平台调用回调时不会携带用户的登录Token
 * 所以回调接口(/pay/notify, /pay/refund/callback)必须排除登录拦截器
 * 已在MvcConfig中配置排除路径
 */
@RestController
@RequestMapping("/pay")
public class PaymentController {

    @Resource
    private IVoucherOrderService voucherOrderService;

    @Resource
    private IPaymentService paymentService;

    /**
     * 发起支付
     *
     * 【八股：支付接口为什么需要限流？】
     * 1. 防止恶意刷单：攻击者批量发起支付，占库存但不支付
     * 2. 第三方支付API有频率限制：超出会被拒绝
     * 3. QPS=20：支付是低频操作，正常用户不会1秒支付20次
     *
     * 【八股：为什么用POST而不是GET？】
     * 1. POST的参数在body中，更安全（不会出现在URL中）
     * 2. POST语义是"创建资源"——发起支付就是创建支付流水
     * 3. GET可以被浏览器缓存、收藏，支付操作不应该被缓存
     *
     * @param dto 支付请求（orderId + payType）
     * @return 支付链接/二维码URL
     */
    @PostMapping
    @RateLimit(qps = 20, message = "支付操作过于频繁，请稍后再试")
    public Result pay(@RequestBody PaymentDTO dto) {
        return voucherOrderService.payOrder(dto.getOrderId(), dto.getPayType());
    }

    /**
     * 支付回调（模拟第三方回调）
     * 【八股：第三方支付回调的流程】
     * 1. 用户扫码支付完成
     * 2. 第三方支付平台异步调用此接口
     * 3. 接口验证签名、确认金额
     * 4. 更新订单状态为已支付
     * 5. 返回SUCCESS给第三方（表示已收到回调）
     *
     * 【八股：回调返回值约定】
     * 微信支付：返回XML <return_code>SUCCESS</return_code>
     * 支付宝：返回字符串 "success"
     * 如果返回其他值，第三方会重试回调（最多8次）
     *
     * @param tradeNo 第三方支付流水号
     * @param orderId 业务订单号
     */
    @PostMapping("/notify")
    public Result payNotify(@RequestParam String tradeNo,
                            @RequestParam Long orderId) {
        return paymentService.handlePayNotify(tradeNo, orderId);
    }

    /**
     * 申请退款
     * 【八股：退款的触发场景】
     * 1. 用户主动申请退款（不满意、买错了）
     * 2. 商家主动退款（缺货、服务问题）
     * 3. 系统自动退款（超时未核销、异常订单）
     *
     * @param orderId 订单ID
     */
    @PostMapping("/refund/{orderId}")
    public Result refund(@PathVariable Long orderId) {
        return voucherOrderService.refundOrder(orderId);
    }

    /**
     * 退款回调（模拟第三方退款回调）
     * 【八股：退款回调与支付回调的区别】
     * 支付回调：用户付钱给商家，更新订单为已支付
     * 退款回调：商家退钱给用户，更新订单为已退款 + 恢复库存
     *
     * @param tradeNo 第三方退款流水号
     * @param orderId 业务订单号
     */
    @PostMapping("/refund/callback")
    public Result refundCallback(@RequestParam String tradeNo,
                                 @RequestParam Long orderId) {
        return paymentService.handleRefund(tradeNo, orderId);
    }
}
