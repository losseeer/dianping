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
        // 【八股：真实的跨平台坑】这里加载的是 "unlock.lua"（小写l），
        // 但资源文件实际叫 "unLock.lua"（大写L）——Windows文件系统大小写不敏感能正常跑，
        // 一旦部署到Linux（大小写敏感）会抛ClassPathResource找不到的异常
        // 教训：资源文件命名全小写，加载路径与文件名严格一致，容器化部署前在Linux环境验证
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

    // 【八股：这个简易锁还有什么局限？→ 为什么生产要用Redisson】
    // 1. 不可重入：同一线程二次tryLock会失败（Redisson用Hash结构存重入计数解决）
    // 2. 不可重试：失败直接返回，不能阻塞等待（Redisson的tryLock带waitTime自旋订阅解锁消息）
    // 3. 无续期：业务超时锁被误释放（Redisson看门狗每10s续期到30s）
    // 4. 主从切换丢锁：master写入锁后未同步到slave就宕机，新master上锁消失（RedissonmultiLock/红锁方案，存在争议）
    // 旧版"判断+删除"分离的非原子释放实现已删除，演进过程见类头注释
}
