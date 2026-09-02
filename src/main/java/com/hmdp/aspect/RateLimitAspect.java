package com.hmdp.aspect;

import com.google.common.util.concurrent.RateLimiter;
import com.hmdp.annotation.RateLimit;
import com.hmdp.dto.Result;
import lombok.extern.slf4j.Slf4j;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.springframework.stereotype.Component;

import java.util.concurrent.ConcurrentHashMap;

/**
 * 限流切面 —— 基于Guava RateLimiter令牌桶算法
 *
 * 【八股：AOP切面的执行流程】
 * 1. Spring在启动时扫描所有@Aspect注解的类，注册为切面
 * 2. 当请求到达Controller方法时，如果方法上有@RateLimit注解
 * 3. Spring的AOP代理拦截请求，在方法执行前调用@Around逻辑
 * 4. 切面从令牌桶中获取令牌，获取到则放行原方法，获取不到则返回降级响应
 *
 * 【八股：为什么每个方法需要一个独立的RateLimiter？】
 * 不同接口的限流阈值不同（秒杀50 QPS，搜索100 QPS）
 * 如果共享一个RateLimiter，所有接口共享同一个限流阈值
 * 一个接口把令牌用完，其他接口就被影响了
 * 所以每个方法维护自己的RateLimiter实例
 *
 * 【八股：ConcurrentHashMap为什么是线程安全的？】
 * 1. JDK 1.8之前：分段锁（Segment），每个段独立加锁，并发度=段数
 * 2. JDK 1.8之后：CAS + synchronized，锁粒度细化到桶（Node）
 * 3. computeIfAbsent是原子操作：如果key不存在就计算并放入，整个过程线程安全
 *
 * 【八股：RateLimiter.create(qps)的原理】
 * Guava的RateLimiter基于令牌桶算法：
 * - 每秒生成qps个令牌
 * - tryAcquire()尝试获取1个令牌，不阻塞
 * - acquire()阻塞等待直到拿到令牌
 * - 内部用"预消费"机制：可以一次性消耗多个令牌（突发流量）
 */
@Slf4j
@Aspect
@Component
public class RateLimitAspect {

    /**
     * 每个方法的限流器缓存
     * key = "类名.方法名"，value = RateLimiter实例
     *
     * 【八股：为什么用ConcurrentHashMap而不是HashMap？】
     * Web应用是多线程的，多个请求可能同时到达不同接口
     * HashMap在并发put时可能导致链表成环（JDK1.7）或数据丢失（JDK1.8）
     * ConcurrentHashMap保证并发安全
     */
    private final ConcurrentHashMap<String, RateLimiter> limiters = new ConcurrentHashMap<>();

    @Around("@annotation(rateLimit)")
    public Object around(ProceedingJoinPoint joinPoint, RateLimit rateLimit) throws Throwable {
        String methodName = getMethodName(joinPoint);

        // 获取或创建限流器 —— 【八股：computeIfAbsent的原子性】
        // computeIfAbsent保证：如果key不存在，执行lambda创建value并放入map
        // 整个过程是原子的，不会重复创建RateLimiter
        RateLimiter limiter = limiters.computeIfAbsent(methodName, k -> {
            log.info("初始化限流器: {} | QPS: {}", methodName, rateLimit.qps());
            return RateLimiter.create(rateLimit.qps());
        });

        // 尝试获取令牌 —— 【八股：tryAcquire vs acquire】
        // tryAcquire()：非阻塞，立即返回true/false
        // acquire()：阻塞等待，直到拿到令牌（不适合秒杀场景，用户不想等）
        // 秒杀场景用tryAcquire：抢不到直接返回"请稍后再试"
        if (!limiter.tryAcquire()) {
            // 被限流了
            log.warn("接口被限流: {} | 当前QPS限制: {}", methodName, rateLimit.qps());

            // 尝试调用降级方法
            if (!rateLimit.fallback().isEmpty()) {
                return invokeFallback(joinPoint, rateLimit.fallback());
            }

            // 没有降级方法，返回默认提示
            return Result.fail(rateLimit.message());
        }

        // 获取到令牌，放行执行原方法
        return joinPoint.proceed();
    }

    private String getMethodName(ProceedingJoinPoint joinPoint) {
        return AspectFallbackSupport.getMethodName(joinPoint);
    }

    private Object invokeFallback(ProceedingJoinPoint joinPoint, String fallbackName) throws Throwable {
        return AspectFallbackSupport.invokeFallback(
                joinPoint, fallbackName, Result.fail("系统繁忙，请稍后再试"));
    }
}
