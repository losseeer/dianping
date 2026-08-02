package com.hmdp.enums;

/**
 * 熔断器状态枚举
 *
 * 【八股：断路器状态机的转换规则】
 *
 *   ┌──────────────────────────────────────────────────────┐
 *   │                                                      │
 *   │   CLOSED ──失败率超阈值──→ OPEN                      │
 *   │     ↑                      │                         │
 *   │     │                  等待recoveryTimeout           │
 *   │  探测成功                   │                         │
 *   │     │                      ↓                         │
 *   │   HALF_OPEN ←──────────────┘                         │
 *   │     │                                                │
 *   │  探测失败                                              │
 *   │     │                                                │
 *   │     ↓                                                │
 *   │   OPEN (重新计时)                                      │
 *   │                                                      │
 *   └──────────────────────────────────────────────────────┘
 *
 * 【八股：为什么需要HALF_OPEN状态？】
 * 直接从OPEN→CLOSED有风险：如果依赖服务还没恢复，大量请求涌入会再次失败
 * HALF_OPEN只放行1个探测请求，成功才恢复，失败继续熔断
 * 这是一种"试探性恢复"策略
 */
public enum BreakerState {
    /**
     * 关闭状态：正常放行请求，统计失败率
     */
    CLOSED("正常"),

    /**
     * 打开状态：熔断中，直接返回降级响应
     */
    OPEN("熔断中"),

    /**
     * 半开状态：放行少量探测请求，试探是否恢复
     */
    HALF_OPEN("半开探测");

    private final String desc;

    BreakerState(String desc) {
        this.desc = desc;
    }

    public String getDesc() {
        return desc;
    }
}
