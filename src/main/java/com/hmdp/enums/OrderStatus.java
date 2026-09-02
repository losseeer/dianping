package com.hmdp.enums;

/**
 * 订单状态枚举 —— 【八股：订单状态机设计】
 *
 * 【八股：什么是订单状态机？】
 * 状态机是一种数学模型，描述对象在不同状态之间的转换关系
 * 订单状态机的核心：每个状态只能合法地转换到特定状态，非法转换要被拒绝
 *
 * 本项目的订单状态流转：
 *
 *   ┌──────────┐    支付成功    ┌──────────┐    核销      ┌──────────┐
 *   │  待支付   │ ──────────→  │  已支付   │ ─────────→  │  已核销   │
 *   │  UNPAID  │              │   PAID    │             │  VERIFIED │
 *   └────┬─────┘              └─────┬────┘             └──────────┘
 *        │                          │
 *   超时取消                     申请退款
 *        │                          │
 *        ▼                          ▼
 *   ┌──────────┐              ┌──────────┐    退款成功   ┌──────────┐
 *   │  已取消   │              │  退款中   │ ─────────→ │  已退款   │
 *   │ CANCELLED│              │ REFUNDING│             │  REFUNDED│
 *   └──────────┘              └──────────┘             └──────────┘
 *
 * 【八股：为什么用枚举而不是常量？】
 * 1. 类型安全：编译器能检查类型，防止传入非法值
 * 2. 可读性好：OrderStatus.UNPAID 比 1 更易理解
 * 3. 可扩展：可以给枚举添加属性和方法（如canTransitionTo）
 * 4. 单例：枚举值是全局唯一的，不会重复创建
 */
public enum OrderStatus {
    UNPAID(1, "待支付"),
    PAID(2, "已支付"),
    VERIFIED(3, "已核销"),
    CANCELLED(4, "已取消"),
    REFUNDING(5, "退款中"),
    REFUNDED(6, "已退款");

    private final int code;
    private final String desc;

    OrderStatus(int code, String desc) {
        this.code = code;
        this.desc = desc;
    }

    public int getCode() {
        return code;
    }

    public String getDesc() {
        return desc;
    }

    /**
     * 根据code获取枚举（严格版：未知状态码直接抛异常，用于状态机校验路径）
     */
    public static OrderStatus of(int code) {
        for (OrderStatus status : values()) {
            if (status.code == code) {
                return status;
            }
        }
        throw new IllegalArgumentException("非法订单状态码: " + code);
    }

    /**
     * 根据code取描述文案（宽松版：未知状态码不抛异常，仅用于组装用户提示语，
     * 避免脏数据让"错误提示"路径自己变成 500）
     */
    public static String descOf(int code) {
        for (OrderStatus status : values()) {
            if (status.code == code) {
                return status.desc;
            }
        }
        return "未知状态(" + code + ")";
    }

    /**
     * 状态转换合法性校验 —— 【八股：状态机的核心约束】
     * 防止非法状态跳转，比如从"已取消"跳到"已支付"
     */
    public boolean canTransitionTo(OrderStatus target) {
        switch (this) {
            case UNPAID:
                return target == PAID || target == CANCELLED;
            case PAID:
                return target == VERIFIED || target == REFUNDING;
            case REFUNDING:
                return target == REFUNDED;
            case VERIFIED:
                // 已核销的订单不能退款（已消费）
                return false;
            default:
                // 已取消、已退款是终态，不能转换
                return false;
        }
    }
}
