package com.hmdp.service.impl;

import cn.hutool.core.bean.BeanUtil;
import cn.hutool.core.bean.copier.CopyOptions;
import cn.hutool.core.lang.UUID;
import cn.hutool.core.util.RandomUtil;
import com.baomidou.mybatisplus.extension.conditions.query.LambdaQueryChainWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.hmdp.dto.LoginFormDTO;
import com.hmdp.dto.Result;
import com.hmdp.dto.UserDTO;
import com.hmdp.entity.User;
import com.hmdp.mapper.UserMapper;
import com.hmdp.service.IUserService;
import com.hmdp.utils.*;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.connection.BitFieldSubCommands;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import javax.servlet.http.HttpSession;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.TimeUnit;

import static com.hmdp.utils.RedisConstants.USER_SIGN_KEY;

/**
 * <p>
 *  用户服务实现类 —— 【八股：分布式登录 & BitMap签到】
 *
 *  面试关联知识点：
 *  - Session共享问题 & Redis替代方案
 *  - Token认证 vs Session认证 vs JWT
 *  - 双层拦截器设计思想
 *  - BitMap位图数据结构原理
 *  - 位运算技巧（与运算、无符号右移）
 * </p>
 *
 * @author 虎哥
 * @since 2021-12-22
 */
@Service
@Slf4j
public class UserServiceImpl extends ServiceImpl<UserMapper, User> implements IUserService {

    @Resource
    private StringRedisTemplate stringRedisTemplate;
    /**
     * 发送验证码
     * @param phone
     * @param session
     * @return
     */
    @Override
    public Result sendCode(String phone, HttpSession session) {
        //1.校验手机号
        if(RegexUtils.isPhoneInvalid(phone)) {
            //2.不符合，返回错误
            return Result.fail("手机号格式错误");
        }

        //3.符合，生成验证码
        String code = RandomUtil.randomNumbers(6);
        //4.保存验证码到redis
        // 【八股：为什么验证码存在Redis而不是Session？】
        // 1. 集群环境下Session不共享，Redis天然分布式
        // 2. 设置过期时间方便（Redis自带TTL）
        // 3. 验证码是临时数据，放Redis比放数据库快得多
        // 4. Session是针对每个用户的，验证码只需要手机号作为key就行
       stringRedisTemplate.opsForValue().set(RedisConstants.LOGIN_CODE_KEY +phone,code,2, TimeUnit.MINUTES);
        //5.发送验证码
        log.info("短信验证码发送成功：{}",code);

        return Result.ok();

    }


    /**
     * 登录方法 —— 【八股：基于Redis的分布式登录方案】
     *
     * 【八股：为什么用Redis替代Session？】
     * 传统Session的问题：
     * - 单Tomcat没问题，集群环境下Session不共享
     * - 用户请求打到不同的Tomcat，就找不到Session了
     * - Session复制（Session Replication）方案：数据同步有延迟，占用带宽
     * - Session粘连（Sticky Session）方案：负载均衡不均，一台挂了用户全丢
     *
     * Redis方案的优势：
     * - 所有Tomcat共享同一个Redis，天然解决共享问题
     * - Redis性能高，支持高并发
     * - 可以设置过期时间，自动清理
     * - 水平扩展方便，Redis可以集群
     *
     * 【八股：为什么不用JWT？】
     * JWT的缺点：
     * - 无法主动过期：JWT签发后，在过期前无法作废（除非加黑名单机制）
     * -  payload大：每次请求都要带，增加网络开销
     * - 无法存放敏感信息：payload是base64编码，不是加密
     * - 续签麻烦：快过期了怎么续期？
     *
     * Redis+Token方案的优点：
     * - 可以主动删除token，让用户立即下线
     * - token只是一个随机字符串，体积小
     * - 刷新过期时间方便（每次请求刷一下TTL）
     * - 用户信息存在Redis服务端，相对安全
     *
     * 【八股：Token为什么用UUID而不是自增ID？】
     * - 自增ID太容易被猜到，不安全
     * - UUID是全局唯一的随机字符串，无法被枚举
     * - 安全性更高，防止token被暴力破解
     *
     * @param loginForm
     * @param session
     * @return
     */
    @Override
    public Result login(LoginFormDTO loginForm, HttpSession session) {
        String code = loginForm.getCode();
        String phone = loginForm.getPhone();
        //1.校验手机号
        if(RegexUtils.isPhoneInvalid(phone)) {
            //2.不符合，返回错误
            return Result.fail("手机号格式错误");
        }
        //3.校验验证码
        String cacheCode = stringRedisTemplate.opsForValue().get(RedisConstants.LOGIN_CODE_KEY+phone);
        if(cacheCode==null||!cacheCode.equals(code)){
           return Result.fail("验证码不一致，请重新输入");
       }

        //4.一致，根据手机号查询用户
        User user = query().eq("phone",phone).one();

        //5.判断用户是否存在

        //6.不存在，创建新用户，保存到数据库
        if(user==null){
           user=createUserWithPhone(phone);
        }
        //7.存在 保存到redis
        //7.1 生成个token作为登陆令牌
        // 【八股：UUID.randomUUID().toString(true) 是什么意思？】
        // UUID.randomUUID() 生成标准UUID：如 550e8400-e29b-41d4-a716-446655440000
        // toString(true) 表示去掉横杠(-)，生成32位紧凑字符串
        // 去掉横杠后更短，放在请求头里更节省空间
        String token = UUID.randomUUID().toString(true);

        //7.2 将user对象转为Hash存储
        // 【八股：为什么用Hash结构存用户信息，而不是String(JSON)？】
        // Hash的优势：
        // - 可以单独修改某个字段，不需要整体读写（比如只改昵称）
        // - 更节省内存：Hash结构内部编码优化，小数据量用ziplist存储
        // String(JSON)的优势：
        // - 序列化反序列化方便，直接用JSON工具
        // - 可以设置过期时间（Hash也可以对整个key设置TTL）
        // 本项目用Hash是演示Redis数据结构，实际工作中String+JSON更常用
        UserDTO userDTO = BeanUtil.copyProperties(user, UserDTO.class);
        Map<String, Object> map = BeanUtil.beanToMap(userDTO, new HashMap<>(),
                CopyOptions.create().setIgnoreNullValue(true)
                        .setFieldValueEditor((fieldName, fieldValue) -> fieldValue.toString()));
        //7.3 存储
        String tokenKey=RedisConstants.LOGIN_USER_KEY+token;
        stringRedisTemplate.opsForHash().putAll(tokenKey,map);
        stringRedisTemplate.expire(tokenKey,30,TimeUnit.MINUTES);
        //8.返回token
        return Result.ok(token);
    }

    /**
     * 用户签到 —— 【八股：BitMap（位图）数据结构】
     *
     * 什么是BitMap？
     * - 用一个bit位来标记某个元素对应的状态（0或1）
     * - Redis的String类型底层是字节数组，每个字节8个bit
     * - 一个512MB大小的String可以存储 2^32 个bit位，非常节省空间
     *
     * 为什么用BitMap存签到数据？
     * - 签到是二值状态（签了/没签），用1个bit足够
     * - 一个用户一个月的签到数据，只需要31个bit ≈ 4个字节！
     * - 如果用数据库存，一条记录至少几十字节，差了一个数量级
     * - 100万用户 * 12个月 = 100万 * 12 * 4字节 ≈ 48MB，小意思
     *
     * 【八股：setbit命令的时间复杂度？】
     * O(1)，因为Redis是数组寻址，直接定位到对应的bit位
     *
     * 【八股：BitMap的应用场景】
     * - 用户签到/打卡
     * - 在线状态统计（用户是否在线）
     * - 布隆过滤器（底层就是BitMap + 哈希函数）
     * - 用户画像标签（有无某个标签）
     */
    @Override
    public Result sign() {
        //1.获取当前登录用户
        Long userId = UserHolder.getUser().getId();
        //2.获取日期
        LocalDateTime now = LocalDateTime.now();
        //3.拼接key
        // 【八股：Key的设计思路】
        // sign:userId:yyyyMM  按用户+月份分key
        // 为什么按月分？
        // - 一个月的数据量小，操作快
        // - 方便按月统计（连续签到、月签到天数）
        // - 过期清理方便（上个月的直接整个key过期）
        String keySuffix = now.format(DateTimeFormatter.ofPattern(":yyyyMM"));
        String key = USER_SIGN_KEY + userId + keySuffix;
        //4.获取今天是这个月的第几天
        int dayOfMonth = now.getDayOfMonth();
        //5.写入redis setbit key offset 1
        // 【八股：为什么offset是dayOfMonth - 1？】
        // 因为bit位的偏移量从0开始计数
        // 第1天对应offset 0，第2天对应offset 1，以此类推
        // 这是编程的常见习惯：数组/位都是从0开始
        stringRedisTemplate.opsForValue().setBit(key,dayOfMonth-1,true);
        return Result.ok();
    }

    /**
     * 统计连续签到天数 —— 【八股：位运算技巧】
     *
     * 【八股：BITFIELD命令是干什么的？】
     * BITFIELD可以一次性对多个位域进行操作
     * 这里用 GET u14 0 表示：从偏移量0开始，获取14位无符号整数
     * 比如今天是14号，就获取前14位（第1天到第14天的签到状态）
     * 返回的是一个十进制数字，每一位代表一天是否签到
     *
     * 【八股：位运算求连续1的个数】
     * 思路：从最低位（今天）开始，依次和1做与运算
     * - num & 1：获取最低位，如果是1说明今天签到了
     * - num >>>= 1：无符号右移一位，抛弃最低位，看第二天
     * - 遇到0就停止，统计的就是从今天往前的连续签到天数
     *
     * 【八股：>>> 和 >> 的区别】
     * - >> ：有符号右移，正数补0，负数补1（保持符号不变）
     * - >>>：无符号右移，不管正负都补0
     * 这里用>>>是因为我们把数字当纯bit位来看，不关心它的数值正负
     *
     * @return
     */
    @Override
    public Result signCount() {
        //1.获取当前登录用户
        Long userId = UserHolder.getUser().getId();
        //2.获取日期
        LocalDateTime now = LocalDateTime.now();
        //3.拼接key
        String keySuffix = now.format(DateTimeFormatter.ofPattern(":yyyyMM"));
        String key = USER_SIGN_KEY + userId + keySuffix;
        //4.获取今天是这个月的第几天
        int dayOfMonth = now.getDayOfMonth();
        //5.获取本月截止今天为止所有的签到记录，返回的是一个十进制的数字
        // BITFIELD sign:5:202203 GET u14 0
        // 【八股：为什么用BitField而不是bitcount？】
        // bitcount是统计所有1的个数（总签到天数）
        // 但我们要的是"连续签到天数"，需要从今天往前数连续的1
        // 所以需要把bit位取出来，自己遍历统计
        List<Long> result = stringRedisTemplate.opsForValue()
                .bitField(key, BitFieldSubCommands.create()
                        .get(BitFieldSubCommands.BitFieldType.unsigned(dayOfMonth))
                        .valueAt(0));
        if(result==null||result.isEmpty()){
            //没有任何签到结果
            return Result.ok(0);
        }
        Long num = result.get(0);
        if(num==0||num==null){
            return Result.ok(0);
        }
        //6.循坏遍历
        int count=0;
        while (true) {
            //让这个数字与1做与运算，得到数字的最后一个bit位，判断这个bit是否为0
            // 【八股：与运算(&)的技巧】
            // 任何数 & 1 = 这个数的最低位
            // 因为1的二进制是 ...0001，其他位都是0，与运算后都变0
            // 只有最低位取决于原数的最低位
            if((num&1)==0) {
                //如果为0，未签到
                break;
            }else {
                //如果不为0，已签到，计算器+1
                count++;
                //把数字右移一位，抛弃最后一个bit位，继续下一个bit位
                // 【八股：为什么用无符号右移 >>> ？】
                // 如果用有符号右移 >> ，负数会在左边补1
                // 我们把数字纯当bit序列看，不需要符号位
                // 所以用>>>，左边永远补0
                num>>>=1;
            }
        }
        return Result.ok(count);

    }

    private User createUserWithPhone(String phone) {
        User user = new User();
        user.setPhone(phone);
        user.setNickName(SystemConstants.USER_NICK_NAME_PREFIX +RandomUtil.randomString(10));
        //保存
        save(user);
        return user;

    }
}
