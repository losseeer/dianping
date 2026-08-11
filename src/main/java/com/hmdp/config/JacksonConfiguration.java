package com.hmdp.config;

import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.databind.ser.std.ToStringSerializer;
import org.springframework.boot.autoconfigure.jackson.Jackson2ObjectMapperBuilderCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.converter.json.Jackson2ObjectMapperBuilder;

import java.math.BigInteger;

/**
 * Jackson 全局定制 —— 把 Long / BigInteger 序列化为 JSON 字符串。
 *
 * 【背景：为什么必须做这件事 —— 秒杀/订单「订单不存在」的隐性根因】
 * 本项目的订单、用户、秒杀券主键全部基于 RedisIdWorker 生成的 64-bit Long（~19 位十进制）：
 *   例如 624910564677648387。
 * 但 JavaScript 的 Number 只支持 2^53-1 以内的安全整数（~16 位十进制），
 * 浏览器端 JSON.parse 会把 Long 静默截断到最近的安全整数，上面例子实际变成：
 *   624910564677648384（delta=-3）或 624910564677648400。
 * 前端再用这个错位 id 调 GET /order/{id} / POST /pay / POST /order/cancel/{id}，
 * 后端查不到 → 统一返回「订单不存在」，即使订单已真实写入 DB。
 *
 * 【修复原则】
 * - 只在"输出到浏览器"时把 Long 转 String；Java 内部、DB 仍然用 Long，不影响 MP 查询与 SQL。
 * - Result.total 也会自动按 Long→String 转，前端 <el-pagination> 赋值依然可用（Vue 会自动 toNumber）。
 * - 输入侧保持兼容：前端即使 String id 传到 @PathVariable Long，Spring 也能 parse。
 */
@Configuration
public class JacksonConfiguration {

    @Bean
    public Jackson2ObjectMapperBuilderCustomizer longAsStringCustomizer() {
        return new Jackson2ObjectMapperBuilderCustomizer() {
            @Override
            public void customize(Jackson2ObjectMapperBuilder builder) {
                builder
                        .serializerByType(Long.class, ToStringSerializer.instance)
                        .serializerByType(Long.TYPE, ToStringSerializer.instance)
                        .serializerByType(BigInteger.class, ToStringSerializer.instance)
                        // 写日期时间用 timestamp(ms) 的场景保持关闭，避免前后端冲突
                        .featuresToDisable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
            }
        };
    }
}
