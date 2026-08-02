package com.hmdp.service.impl;

import cn.hutool.core.bean.BeanUtil;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.hmdp.dto.Result;
import com.hmdp.dto.UserDTO;
import com.hmdp.entity.Follow;
import com.hmdp.entity.User;
import com.hmdp.mapper.FollowMapper;
import com.hmdp.service.IFollowService;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.hmdp.utils.UserHolder;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.time.LocalDateTime;
import java.util.Collections;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * <p>
 *  关注服务实现类 —— 【八股：Redis Set 数据结构】
 *
 *  Set数据结构特点：
 *  - 无序、唯一（元素不重复）
 *  - 时间复杂度：添加SADD O(1)、删除SREM O(1)、判断存在SISMEMBER O(1)
 *  - 支持集合运算：交集(inter)、并集(union)、差集(diff)
 *
 *  本项目中Set的应用场景：
 *  - 关注列表：每个用户的关注者ID存在一个Set里
 *  - 共同关注：两个用户关注列表求交集
 *  - 一人一单判断：秒杀订单用Set存用户ID，判断是否重复下单
 *
 *  【八股：为什么用Set存关注列表，而不是List？】
 *  - Set自动去重：同一个用户不能关注两次（虽然业务上也会校验，但Set天然保证）
 *  - 判断是否关注更高效：SISMEMBER O(1) vs List遍历 O(n)
 *  - 支持集合运算：求共同关注直接用SINTER，不需要自己写循环
 * </p>
 *
 * @author 虎哥
 * @since 2021-12-22
 */
@Service
public class FollowServiceImpl extends ServiceImpl<FollowMapper, Follow> implements IFollowService {

    @Resource
    private StringRedisTemplate stringRedisTemplate;

    @Resource
    private UserServiceImpl userService;

    @Override
    public Result follow(Long followUserId, Boolean isFollow) {
        //获取登录用户
        Long userId = UserHolder.getUser().getId();
        String key = "follows:" + userId;
        //1.判断关注还是取关
        if(isFollow) {
            //2.关注
            Follow follow = new Follow();
            follow.setFollowUserId(followUserId);
            follow.setUserId(userId);
            boolean isSuccess = save(follow);
            if(isSuccess){
                //把关注用户的id，放入redis的set集合 sadd userId followUserId
                // 【八股：为什么数据库和Redis都要存？】
                // - 数据库：持久化存储，数据的最终来源
                // - Redis：缓存，提高查询性能
                // - 典型的Cache Aside模式：写操作先写数据库，再更新缓存
                stringRedisTemplate.opsForSet().add(key,followUserId.toString());
            }
        }else {
            //3.取关
            boolean isSuccess = remove(new QueryWrapper<Follow>()
                    .eq("user_id", userId)
                    .eq("follow_user_id", followUserId));
            //移除
            if(isSuccess){
                stringRedisTemplate.opsForSet().remove(key,followUserId.toString());
            }
        }
        return Result.ok();
    }

    @Override
    public Result isFollow(Long followUserId) {
        Long userId = UserHolder.getUser().getId();
        //1.查询是否关注select* from tb_follow where user_id=？ and follow_id=?
        // 【八股：这里可以优化！】
        // 现在是查数据库，其实可以直接查Redis的Set
        // SISMEMBER key member  时间复杂度O(1)，比查数据库快得多
        // 这是一个可以优化的点，面试时可以主动提出来
        Integer count = query().eq("user_id", userId).eq("follow_user_id", followUserId).count();
            return Result.ok(count>0);

    }

    /**
     * 共同关注 —— 【八股：Set交集运算的经典应用】
     *
     * 如果不用Redis，怎么实现共同关注？
     * - 查A的关注列表，查B的关注列表，然后代码里循环找交集
     * - 时间复杂度O(n*m)，数据量大的话很慢
     * - 而且要把两个列表都查出来，网络IO也大
     *
     * 用Redis Set的SINTER命令：
     * - 直接在Redis里计算交集，返回结果
     * - 时间复杂度O(min(n,m))，Redis内部用高效算法实现
     * - 网络传输小，只传交集结果
     *
     * 【八股：Set的其他集合运算命令】
     * - SINTER key1 key2：交集（两个集合都有的元素）
     * - SUNION key1 key2：并集（两个集合所有元素，去重）
     * - SDIFF key1 key2：差集（key1有但key2没有的元素）
     * - 这些命令都可以一次操作多个key
     *
     * @param id 目标用户ID
     * @return
     */
    @Override
    public Result followCommons(Long id) {
        //获取当前用户
        Long userId = UserHolder.getUser().getId();
        String key = "follows:" + userId;
        //求交集
        String key2 = "follows:" + id;
        // 【八股：SINTER命令的时间复杂度】
        // O(N*M)，其中N是最小集合的大小，M是集合的数量
        // 比代码里循环比较快，因为Redis是C语言实现的，而且数据在内存里
        Set<String> intersect = stringRedisTemplate.opsForSet().intersect(key, key2);
        if(intersect==null||intersect.isEmpty()){
            return Result.ok(Collections.emptyList());
        }
        //解析出id
        List<Long> ids = intersect.stream().map(Long::valueOf).collect(Collectors.toList());

        //查询用户
        List<UserDTO> userDTOS = userService
                .listByIds(ids).stream()
                .map(user -> BeanUtil.copyProperties(user, UserDTO.class))
                .collect(Collectors.toList());

        return Result.ok(userDTOS);

    }
}
