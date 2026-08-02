package com.hmdp.annotation;

import java.lang.annotation.*;

/**
 * 接口限流注解 —— 基于令牌桶算法
 *
 * 【八股：令牌桶算法原理】
 * 1. 系统以固定速率往桶里放令牌（token）
 * 2. 请求来时从桶里取一个令牌，取到则放行，取不到则拒绝
 * 3. 桶满了就丢弃多余的令牌（防止令牌堆积）
 * 4. 允许一定程度的突发流量（桶里攒的令牌可以瞬间消耗完）
 *
 * 【八股：令牌桶 vs 漏桶的区别】
 * 令牌桶（Guava RateLimiter）：
 *   - 允许突发流量（桶里有令牌就可以瞬间放行多个请求）
 *   - 适合"平时低流量，偶尔高并发"的场景（如秒杀）
 *
 * 漏桶（Leaky Bucket）：
 *   - 请求匀速流出，不管来多少请求，出去的速率恒定
 *   - 适合需要严格匀速的场景（如消息队列消费）
 *
 * 【八股：常见限流算法对比】
 * | 算法     | 突发流量 | 匀速  | 复杂度 | 适用场景          |
 * |---------|---------|-------|--------|-----------------|
 * | 计数器   | 不允许   | 否    | 低     | 固定QPS限制       |
 * | 滑动窗口  | 部分允许 | 否    | 中     | 精确控制时间窗口    |
 * | 漏桶     | 不允许   | 是    | 中     | 整流（让流量均匀）  |
 * | 令牌桶   | 允许     | 否    | 中     | 允许突发的一般限流  |
 *
 * 使用示例：
 *   @RateLimit(qps = 50, fallback = "seckillFallback")
 *   public Result seckillVoucher(Long voucherId) { ... }
 *
 *   private Result seckillFallback(Long voucherId) {
 *       return Result.fail("当前排队人数较多，请稍后再试");
 *   }
 */
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
@Documented
public @interface RateLimit {

    /**
     * 每秒允许的请求数（QPS）
     * 默认100，秒杀接口建议设50，普通接口设200
     */
    double qps() default 100;

    /**
     * 降级方法名
     * 被限流时调用此方法，方法签名需与原方法一致
     * 如果不指定，默认返回"请求过于频繁，请稍后再试"
     */
    String fallback() default "";

    /**
     * 限流提示消息（fallback为空时使用）
     */
    String message() default "请求过于频繁，请稍后再试";
}
