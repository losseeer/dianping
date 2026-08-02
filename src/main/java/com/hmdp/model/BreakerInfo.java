package com.hmdp.model;

import com.hmdp.enums.BreakerState;
import lombok.Data;

import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

/**
 * 熔断器运行时信息 —— 每个被保护方法一个实例
 *
 * 【八股：为什么用Atomic类而不是synchronized？】
 * 1. 性能更好：AtomicInteger基于CAS（Compare-And-Swap），无锁竞争
 * 2. 不会阻塞线程：CAS失败直接重试，不需要上下文切换
 * 3. 适合"高并发读+写"场景：失败计数是高频写操作
 * 4. synchronized是重量级锁，会阻塞其他线程
 *
 * 【八股：CAS的ABA问题】
 * CAS有三个操作数：内存值V、预期值A、新值B
 * 当V==A时，把V更新为B
 * ABA问题：线程1读到A，线程2把A改成B又改回A，线程1的CAS仍然成功
 * 解决方案：加版本号（AtomicStampedReference）
 * 在本场景中，ABA问题不影响正确性（计数器不需要知道中间过程）
 */
@Data
public class BreakerInfo {

    /**
     * 当前熔断状态 —— 用AtomicReference保证状态切换的可见性和原子性
     */
    private final AtomicReference<BreakerState> state = new AtomicReference<>(BreakerState.CLOSED);

    /**
     * 当前滑动窗口内的失败次数
     */
    private final AtomicInteger failureCount = new AtomicInteger(0);

    /**
     * 当前滑动窗口内的总请求次数（用于算失败率）
     */
    private final AtomicInteger totalCount = new AtomicInteger(0);

    /**
     * 最近一次失败发生的时间戳
     */
    private volatile long lastFailureTime = 0L;

    /**
     * 熔断器打开（进入OPEN状态）的时间戳
     * 用于判断是否到了恢复超时
     */
    private volatile long openTime = 0L;

    /**
     * 半开探测是否已发出（每次OPEN→HALF_OPEN只放行一个探测请求）
     */
    private final AtomicBoolean probeSent = new AtomicBoolean(false);

    /**
     * 重置统计计数
     * 在每次状态转换时调用，清空旧数据
     */
    public void resetCounters() {
        failureCount.set(0);
        totalCount.set(0);
        probeSent.set(false);
    }
}
