package com.hmdp.utils;

import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import javax.annotation.Resource;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;

/**
 * Redis全局唯一ID生成器 —— 【八股：分布式ID为什么要单独设计？】
 *
 * 为什么不用数据库自增ID？
 * 1. 分库分表后各表自增会互相重复
 * 2. 自增ID暴露业务量：下单id=1024 → 竞品能推算日订单量
 *
 * 本实现的位布局（64bit）：符号位(1) + 时间戳(31) + 序列号(32)
 * - 时间戳：相对2022-01-01的秒数差，约可用68年
 * - 序列号：Redis INCR自增，同一个秒内可生成2^32个ID
 * - INCR的key按天分片（icr:{prefix}:yyyy:MM:dd）：
 *   ① 避免单个key无限增长 ② key带日期方便统计当天订单量
 *
 * 【八股：对比雪花算法Snowflake】
 * - 雪花：1+41时间戳+10机器ID+12序列号，纯本地生成零网络开销，
 *   但依赖机器时钟，时钟回拨会出重复ID（需要等待/扩展位方案）
 * - Redis版：时钟只影响高位趋势、不产生重复（序列号来自Redis单调递增），
 *   代价是每次生成多一次Redis网络往返
 */
@Component
public class RedisIdWorker {
    //开始时间戳
    private static final long BEGIN_TIMESTAMP=1640995200L;

    //序列号位数
    private static final int COUNT_BITS=32;

    @Resource
    private StringRedisTemplate stringRedisTemplate;
    public Long nextId(String keyPrefix){
        //1.生成时间戳
        LocalDateTime now = LocalDateTime.now();
        long nowSecond = now.toEpochSecond(ZoneOffset.UTC);
        long timestamp = nowSecond - BEGIN_TIMESTAMP;
        //2.生成序列号
        //2.1.获取当前日期，精确到天
        String date = now.format(DateTimeFormatter.ofPattern("yyyy:MM:dd"));
        Long count = stringRedisTemplate.opsForValue().increment("icr:" + keyPrefix + ":" + date);


        //3.拼接并返回
        return timestamp<<COUNT_BITS | count;
    }

}
