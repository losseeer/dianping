package com.hmdp.aspect;

import com.hmdp.annotation.CircuitBreaker;
import com.hmdp.dto.Result;
import com.hmdp.enums.BreakerState;
import com.hmdp.model.BreakerInfo;
import lombok.extern.slf4j.Slf4j;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.springframework.stereotype.Component;

import java.util.concurrent.ConcurrentHashMap;

/**
 * 熔断降级切面 —— 自定义断路器实现
 *
 * 【八股：断路器的完整工作流程】
 *
 *   请求进来
 *      │
 *      ▼
 *  ┌─检查熔断状态──┐
 *  │               │
 *  ├─CLOSED──→ 放行请求，统计成功/失败
 *  │               │
 *  ├─OPEN──→ 检查是否超过恢复时间？
 *  │           ├─没超过 → 直接返回降级响应
 *  │           └─超过了 → 转为HALF_OPEN，放行1个探测请求
 *  │               │
 *  └─HALF_OPEN──→ 检查是否已有探测请求在进行
 *                  ├─有 → 返回降级响应（只允许1个探测）
 *                  └─没有 → 放行探测请求
 *                               ├─探测成功 → 转为CLOSED
 *                               └─探测失败 → 转为OPEN，重置计时
 *
 * 【八股：滑动窗口统计的原理】
 * 传统方案：每隔slidingWindow时间清零计数器（有边界效应，窗口边界处可能漏判）
 * 滑动窗口：只统计最近slidingWindow时间内的请求，更精确
 * 简化实现：在每次请求时检查"上次重置时间"，如果超过窗口就重置
 * （本项目用简化版，精确版可用环形数组或Redis ZSet实现）
 *
 * 【八股：@Around的通知顺序】
 * @Around是环绕通知，包裹了整个方法执行：
 *   try {
 *       // @Before 逻辑
 *       result = joinPoint.proceed();  // 执行原方法
 *       // @AfterReturning 逻辑
 *   } catch (Throwable e) {
 *       // @AfterThrowing 逻辑
 *   } finally {
 *       // @After 逻辑
 *   }
 * 一个@Around可以替代@Before + @After + @AfterReturning + @AfterThrowing
 */
@Slf4j
@Aspect
@Component
public class CircuitBreakerAspect {

    /**
     * 每个被保护方法的熔断器信息
     * key = "类名.方法名"
     */
    private final ConcurrentHashMap<String, BreakerInfo> breakers = new ConcurrentHashMap<>();

    @Around("@annotation(circuitBreaker)")
    public Object around(ProceedingJoinPoint joinPoint, CircuitBreaker circuitBreaker) throws Throwable {
        String methodName = getMethodName(joinPoint);
        BreakerInfo breaker = breakers.computeIfAbsent(methodName, k -> {
            log.info("初始化熔断器: {} | 失败阈值: {} | 恢复时间: {}ms",
                    methodName, circuitBreaker.failureThreshold(), circuitBreaker.recoveryTimeout());
            return new BreakerInfo();
        });

        // 获取当前状态
        BreakerState state = breaker.getState().get();

        // ========== 状态判断 ==========

        if (state == BreakerState.OPEN) {
            // 熔断打开状态，检查是否到了恢复时间
            long now = System.currentTimeMillis();
            if (now - breaker.getOpenTime() >= circuitBreaker.recoveryTimeout()) {
                // 超过恢复时间，尝试从OPEN转为HALF_OPEN —— 【八股：CAS保证状态转换原子性】
                // compareAndSet: 如果当前状态是OPEN，才转为HALF_OPEN
                // 如果多个线程同时到达，只有一个能成功转换
                if (breaker.getState().compareAndSet(BreakerState.OPEN, BreakerState.HALF_OPEN)) {
                    breaker.resetCounters();
                    log.info("熔断器 [{}] OPEN → HALF_OPEN，开始探测", methodName);
                }
            } else {
                // 还没到恢复时间，直接降级
                log.warn("熔断器 [{}] 处于OPEN状态，直接降级", methodName);
                return doFallback(joinPoint, circuitBreaker);
            }
            // 重新读取状态（可能已被其他线程改成HALF_OPEN）
            state = breaker.getState().get();
        }

        if (state == BreakerState.HALF_OPEN) {
            // 半开状态，只允许1个探测请求
            // 【八股：为什么HALF_OPEN只放行1个请求？】
            // 如果放行多个，万一服务还没恢复，大量请求又会失败
            // 只放1个探测请求，成功才完全恢复
            if (!breaker.getProbeSent().compareAndSet(false, true)) {
                // 已经有探测请求在进行中，其他请求直接降级
                return doFallback(joinPoint, circuitBreaker);
            }
            log.info("熔断器 [{}] HALF_OPEN，放行探测请求", methodName);
        }

        // ========== 执行原方法 ==========

        // 检查滑动窗口是否需要重置
        checkAndResetSlidingWindow(breaker, circuitBreaker);

        try {
            // 执行原方法
            Object result = joinPoint.proceed();

            // ========== 执行成功 ==========

            BreakerState current = breaker.getState().get();
            if (current == BreakerState.HALF_OPEN) {
                // 探测成功，恢复为CLOSED —— 【八股：探测成功恢复流程】
                breaker.getState().set(BreakerState.CLOSED);
                breaker.resetCounters();
                log.info("熔断器 [{}] HALF_OPEN → CLOSED，探测成功，恢复正常", methodName);
            }

            return result;

        } catch (Throwable e) {
            // ========== 执行失败 ==========

            int failures = breaker.getFailureCount().incrementAndGet();
            breaker.setLastFailureTime(System.currentTimeMillis());

            log.warn("熔断器 [{}] 方法执行失败，当前失败次数: {}", methodName, failures);

            BreakerState current = breaker.getState().get();
            if (current == BreakerState.HALF_OPEN) {
                // 探测失败，重新进入OPEN状态
                breaker.getState().set(BreakerState.OPEN);
                breaker.setOpenTime(System.currentTimeMillis());
                breaker.resetCounters();
                log.error("熔断器 [{}] HALF_OPEN → OPEN，探测失败，重新熔断", methodName);
            } else if (current == BreakerState.CLOSED) {
                // CLOSED状态下检查是否需要熔断
                // 条件：失败次数 >= 阈值
                if (failures >= circuitBreaker.failureThreshold()) {
                    if (breaker.getState().compareAndSet(BreakerState.CLOSED, BreakerState.OPEN)) {
                        breaker.setOpenTime(System.currentTimeMillis());
                        log.error("熔断器 [{}] CLOSED → OPEN，失败次数 {} 达到阈值 {}",
                                methodName, failures, circuitBreaker.failureThreshold());
                    }
                }
            }

            // 返回降级响应
            return doFallback(joinPoint, circuitBreaker);
        }
    }

    /**
     * 检查滑动窗口是否过期，过期则重置计数器
     *
     * 【八股：滑动窗口的实现方式】
     * 精确版：用环形数组记录每个请求的时间戳，查询时过滤窗口外的
     * 简化版（本项目）：记录上次重置时间，如果距上次重置超过窗口大小就重置
     * 简化版的缺点：在窗口边界处会有短暂的不精确（最多多算一个窗口的数据）
     */
    private void checkAndResetSlidingWindow(BreakerInfo breaker, CircuitBreaker cb) {
        long now = System.currentTimeMillis();
        if (breaker.getLastFailureTime() > 0 &&
                now - breaker.getLastFailureTime() > cb.slidingWindow()) {
            // 窗口已过期，重置计数
            breaker.resetCounters();
        }
    }

    /**
     * 执行降级逻辑
     */
    private Object doFallback(ProceedingJoinPoint joinPoint, CircuitBreaker cb) throws Throwable {
        if (!cb.fallback().isEmpty()) {
            return invokeFallback(joinPoint, cb.fallback());
        }
        return Result.fail(cb.message());
    }

    private String getMethodName(ProceedingJoinPoint joinPoint) {
        return AspectFallbackSupport.getMethodName(joinPoint);
    }

    private Object invokeFallback(ProceedingJoinPoint joinPoint, String fallbackName) throws Throwable {
        return AspectFallbackSupport.invokeFallback(
                joinPoint, fallbackName, Result.fail("服务暂时不可用，请稍后再试"));
    }
}
