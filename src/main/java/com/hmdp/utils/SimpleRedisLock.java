package com.hmdp.utils;

import cn.hutool.core.lang.UUID;
import org.springframework.core.io.ClassPathResource;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.data.redis.support.collections.DefaultRedisList;

import java.util.Collections;
import java.util.concurrent.TimeUnit;

/**
 * 简易Redis分布式锁实现 —— 【八股：分布式锁的演进过程】
 *
 * 分布式锁演进路线：
 * 第一版：setnx key value —— 有死锁问题（服务宕机锁永远不释放）
 * 第二版：setnx + expire —— 不是原子操作，setnx后expire前宕机还是死锁
 * 第三版：set key value nx ex seconds —— 原子操作，解决死锁
 * 第四版：value存唯一标识 + 释放时判断 —— 解决误删别人锁的问题
 * 第五版：Lua脚本释放锁 —— 解决"判断+删除"的原子性问题
 * 第六版：Redisson —— 可重入、看门狗续期、主从一致等完善功能
 *
 * 本类就是第四/五版的实现（改进版的简易Redis锁）
 * 实际生产环境用Redisson更靠谱
 */
public class SimpleRedisLock implements ILock{
    //锁名称
    private String name;
    private StringRedisTemplate stringRedisTemplate;

    private static final String KEY_PREFIX="lock";
    // 【八股：为什么锁的value要存UUID+线程ID？】
    // 为了标识这把锁是谁加的
    // 释放锁的时候，先判断是不是自己加的锁，是自己的才释放
    // 防止误删别人的锁（详见下面delLock方法的注释）
    private static final String ID_PREFIX= UUID.randomUUID().toString(true)+"-";

    /**
     * 脚本初始化
     * 【八股：为什么释放锁也要用Lua脚本？】
     * 因为释放锁有两步：1.判断是不是自己的锁  2.如果是就删除
     * 这两步如果分开执行，中间可能被其他线程插入
     * 极端场景：
     * 1. 线程A判断是自己的锁，准备删除
     * 2. 此时锁过期了（刚好到时间）
     * 3. 线程B获取到了这把锁
     * 4. 线程A执行删除操作，把线程B的锁删了！
     *
     * 用Lua脚本把"判断+删除"打包成原子操作，就不会有这个问题了
     */
    private static final DefaultRedisScript<Long> UNLOCK_SCRIPT;
    static {
        UNLOCK_SCRIPT=new DefaultRedisScript<>();
        UNLOCK_SCRIPT.setLocation(new ClassPathResource("unlock.lua"));
        UNLOCK_SCRIPT.setResultType(Long.class);
    }

    public SimpleRedisLock(String name, StringRedisTemplate stringRedisTemplate) {
        this.name = name;
        this.stringRedisTemplate = stringRedisTemplate;
    }

    @Override
    public boolean  tryLock(long timeoutSec) {
        //获取线程标识
        String threadId = ID_PREFIX+Thread.currentThread().getId();
        //获取锁
        // 【八股：setIfAbsent就是SETNX】
        // SET if Not eXists：key不存在时才能设置成功
        // 利用这个特性实现互斥：谁先set成功，谁就拿到了锁
        // 同时设置过期时间，防止服务宕机导致死锁
        // 这一步是原子操作（Redis 2.6.12之后支持）
       Boolean success= stringRedisTemplate.opsForValue()
                .setIfAbsent(KEY_PREFIX+name,threadId,timeoutSec, TimeUnit.SECONDS);
        return Boolean.TRUE.equals(success);
    }

    @Override
    public void delLock() {
        //调节lua脚本
        // 【八股：Lua脚本释放锁的原子性】
        // 把"判断锁是否属于自己 + 删除锁"放在一个Lua脚本中
        // Redis执行Lua脚本是原子的，保证了判断和删除之间不会被插入其他操作
        stringRedisTemplate.execute(
                UNLOCK_SCRIPT,
                Collections.singletonList(KEY_PREFIX+name),
                ID_PREFIX+Thread.currentThread().getId()
        );
    }

//    @Override
//    public void delLock() {
//        //获取线程标识
//        String threadId = ID_PREFIX + Thread.currentThread().getId();
//        //获取锁中标识
//        String id = stringRedisTemplate.opsForValue().get(KEY_PREFIX + name);
//        if (threadId.equals(id)) {
//            //释放锁
//            stringRedisTemplate.delete(KEY_PREFIX + name);
//        }
//    }
}
