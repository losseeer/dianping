package com.hmdp.utils;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/**
 * 支付回调验签器 —— 【八股:HMAC 签名原理】
 *
 * 【八股:HMAC 是加密吗?和 HTTPS 什么关系?】
 * - HMAC(哈希消息认证码)= 密钥 + 哈希(SHA256),用于"验证消息来源和完整性",不是加密
 * - 对称:签名方和验签方持有同一个secret(微信支付V3用的就是类似机制)
 * - HTTPS的TLS解决"传输链路被窃听篡改";HMAC解决"这条消息确实是持有secret的一方发的"
 *   两者是不同层面的保障,支付回调通常两个都要
 *
 * 【八股:为什么不能只比对金额/订单号?】
 * 回调接口暴露在公网,任何人都能POST伪造"支付成功"
 * 只有持有secret的支付平台才能算出正确签名——身份认证靠密码学,不靠参数可信
 *
 * 【八股:fail-safe设计】
 * secret默认空串时verify直接返回false——即"未配置密钥=拒绝所有公网回调"
 * 安全默认值应该是"关",配置错了最坏是不可用,而不是被伪造支付
 */
@Component
public class PaymentCallbackVerifier {

    private static final String HMAC_SHA_256 = "HmacSHA256";

    private final byte[] secret;

    public PaymentCallbackVerifier(@Value("${payment.callback-secret:}") String secret) {
        this.secret = secret == null ? new byte[0] : secret.getBytes(StandardCharsets.UTF_8);
    }

    public boolean verifyPay(String signature, String tradeNo, Long orderId, Long amount) {
        return verify(signature, payload("PAY", tradeNo, orderId, amount));
    }

    public boolean verifyRefund(String signature, String tradeNo, Long orderId, Long amount) {
        return verify(signature, payload("REFUND", tradeNo, orderId, amount));
    }

    private String payload(String event, String tradeNo, Long orderId, Long amount) {
        return event + "\n" + tradeNo + "\n" + orderId + "\n" + (amount == null ? "" : amount);
    }

    private boolean verify(String signature, String payload) {
        if (secret.length == 0 || signature == null || signature.length() != 64) {
            // HMAC-SHA256输出固定32字节=64个hex字符,长度不对直接拒绝(省一次MAC计算)
            return false;
        }
        try {
            Mac mac = Mac.getInstance(HMAC_SHA_256);
            mac.init(new SecretKeySpec(secret, HMAC_SHA_256));
            byte[] expected = mac.doFinal(payload.getBytes(StandardCharsets.UTF_8));
            byte[] actual = decodeHex(signature);
            // 【八股:为什么用 MessageDigest.isEqual 而不是 Arrays.equals?】
            // 常量时间比较:逐字节异或全部比对完才返回,耗时与"前几个字节是否匹配"无关
            // 普通equals碰到第一个不同字节就返回,攻击者可据此逐字节爆破签名(时序侧信道攻击)
            return actual != null && MessageDigest.isEqual(expected, actual);
        } catch (Exception e) {
            return false;
        }
    }

    private byte[] decodeHex(String value) {
        byte[] result = new byte[value.length() / 2];
        for (int i = 0; i < value.length(); i += 2) {
            int high = Character.digit(value.charAt(i), 16);
            int low = Character.digit(value.charAt(i + 1), 16);
            if (high < 0 || low < 0) {
                return null;
            }
            result[i / 2] = (byte) ((high << 4) + low);
        }
        return result;
    }
}
