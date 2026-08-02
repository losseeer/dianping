package com.hmdp.annotation;

import java.lang.annotation.*;

/**
 * 熔断降级注解 —— 基于断路器模式
 *
 * 【八股：熔断器（Circuit Breaker）的三个状态】
 *
 *   ┌──────────┐  失败率超过阈值  ┌──────────┐
 *   │  CLOSED  │ ──────────────→ │   OPEN   │
 *   │ (正常放行) │                 │ (直接拒绝) │
 *   └──────────┘                 └────┬─────┘
 *        ↑                            │
 *     探测成功                    等待recoveryTime
 *        │                            │
 *   ┌────┴──────┐  探测成功    ┌───────┴────┐
 *   │ HALF_OPEN │ ←────────── │  超时后    │
 *   │ (半开探测)  │             │  自动降级  │
 *   └───────────┘             └────────────┘
 *
 * 1. CLOSED（关闭）：正常状态，请求正常通过，统计失败次数
 * 2. OPEN（打开）：失败率超过阈值，直接返回降级响应，不再调用真实方法
 * 3. HALF_OPEN（半开）：超时后进入探测状态，放行少量请求试探
 *    - 探测成功 → 回到 CLOSED
 *    - 探测失败 → 回到 OPEN
 *
 * 【八股：熔断 vs 降级的区别】
 * 熔断：是一种自我保护机制，当依赖服务不可用时，快速失败不再调用
 * 降级：是熔断后的补救措施，提供备用方案（返回默认值、缓存数据等）
 * 熔断是"不调用了"，降级是"用别的方式回应"
 * 通常熔断和降级配合使用：熔断后执行降级逻辑
 *
 * 【八股：为什么不用Hystrix/Resilience4j？】
 * 1. Hystrix已停止维护（Netflix不再更新）
 * 2. Resilience4j需要额外引入依赖，本项目自定义实现更轻量
 * 3. 自定义实现能展示对熔断原理的深入理解（面试加分）
 * 4. 如果是微服务架构，推荐用Sentinel（集限流+熔断+降级于一体）
 *
 * 使用示例：
 *   @CircuitBreaker(failureThreshold = 10, recoveryTimeout = 30000,
 *                   fallback = "queryShopFallback")
 *   public Result queryById(Long id) { ... }
 *
 *   private Result queryShopFallback(Long id) {
 *       // 降级：直接查数据库，跳过缓存
 *       Shop shop = this.getById(id);
 *       return Result.ok(shop);
 *   }
 */
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
@Documented
public @interface CircuitBreaker {

    /**
     * 失败次数阈值（滑动窗口内达到此值则熔断）
     * 默认10次
     */
    int failureThreshold() default 10;

    /**
     * 熔断恢复超时时间（毫秒）
 * 超过此时间后进入半开状态，允许探测请求
 * 默认30秒
     */
    long recoveryTimeout() default 30000;

    /**
     * 滑动窗口大小（毫秒）
 * 只统计此时间窗口内的失败次数
 * 默认60秒
     */
    long slidingWindow() default 60000;

    /**
     * 降级方法名
 * 熔断时调用此方法，方法签名需与原方法一致
     */
    String fallback() default "";

    /**
     * 降级提示消息（fallback为空时使用）
     */
    String message() default "服务暂时不可用，请稍后再试";
}
