package com.hmdp.enums;

/**
 * 支付方式枚举
 *
 * 【八股：为什么需要记录支付方式？】
 * 1. 退款时需要原路返回（微信支付的走微信退款，支付宝的走支付宝退款）
 * 2. 对账时需要按支付渠道统计
 * 3. 不同支付渠道的费率不同，财务核算需要
 */
public enum PayType {
    BALANCE(1, "余额支付"),
    ALIPAY(2, "支付宝"),
    WECHAT(3, "微信支付");

    private final int code;
    private final String desc;

    PayType(int code, String desc) {
        this.code = code;
        this.desc = desc;
    }

    public int getCode() {
        return code;
    }

    public String getDesc() {
        return desc;
    }

    public static PayType of(int code) {
        for (PayType type : values()) {
            if (type.code == code) {
                return type;
            }
        }
        throw new IllegalArgumentException("非法支付方式: " + code);
    }
}
