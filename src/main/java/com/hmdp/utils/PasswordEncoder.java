package com.hmdp.utils;


import cn.hutool.core.util.RandomUtil;
import org.springframework.util.DigestUtils;

import java.nio.charset.StandardCharsets;

/**
 * 密码编码器(盐 + MD5) —— 【八股:密码为什么不能明文存?哈希怎么选?】
 *
 * 【八股:加盐能解决什么?】
 * - 防彩虹表:同一密码+不同盐,哈希结果完全不同,预 computed 表全废
 * - 每个用户独立随机盐,相同密码的用户存出的密文也不同
 *
 * 【已知缺陷,面试主动讲:为什么MD5+盐仍然不够?】
 * MD5/SHA系列是"快哈希",设计目标是快速计算——这正是密码存储的反面:
 * 攻击者拿到库后可用GPU每秒跑数十亿次猜测,盐只是让每次猜测更贵一点点
 * 生产应使用"慢哈希":BCrypt/Argon2/PBKDF2,内置盐、可调计算成本(如BCrypt的cost),
 * 每次校验故意耗时几十~几百毫秒,暴力破解成本提高几个数量级
 * (本类是学习项目沿用黑马点评的实现,改造点:换 spring-security-crypto 的 BCrypt)
 *
 * 【八股:时序安全】matches里用equals比较,严格来说应像支付验签那样用常量时间比较,
 * 不过密码场景有时序攻击的前提是攻击者能精确测量,风险远低于回调验签场景
 */
public class PasswordEncoder {

    public static String encode(String password) {
        // 生成盐
        String salt = RandomUtil.randomString(20);
        // 加密
        return encode(password,salt);
    }
    private static String encode(String password, String salt) {
        // 加密
        return salt + "@" + DigestUtils.md5DigestAsHex((password + salt).getBytes(StandardCharsets.UTF_8));
    }
    public static Boolean matches(String encodedPassword, String rawPassword) {
        if (encodedPassword == null || rawPassword == null) {
            return false;
        }
        if(!encodedPassword.contains("@")){
            throw new RuntimeException("密码格式不正确！");
        }
        String[] arr = encodedPassword.split("@");
        // 获取盐
        String salt = arr[0];
        // 比较
        return encodedPassword.equals(encode(rawPassword, salt));
    }
}
