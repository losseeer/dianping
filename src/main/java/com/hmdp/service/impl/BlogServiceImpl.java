package com.hmdp.service.impl;

import cn.hutool.core.bean.BeanUtil;
import cn.hutool.core.util.BooleanUtil;
import cn.hutool.core.util.StrUtil;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.hmdp.dto.Result;
import com.hmdp.dto.ScrollResult;
import com.hmdp.dto.UserDTO;
import com.hmdp.entity.Blog;
import com.hmdp.entity.Follow;
import com.hmdp.entity.User;
import com.hmdp.mapper.BlogMapper;
import com.hmdp.service.IBlogService;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.hmdp.service.IFollowService;
import com.hmdp.service.IUserService;
import com.hmdp.utils.RedisConstants;
import com.hmdp.utils.SystemConstants;
import com.hmdp.utils.UserHolder;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ZSetOperations;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;
import java.util.stream.LongStream;

import static com.hmdp.utils.RedisConstants.BLOG_LIKED_KEY;
import static com.hmdp.utils.RedisConstants.FEED_KEY;
import static com.hmdp.utils.RedisConstants.USER_LIKED_SHOPS_KEY;
import static com.hmdp.utils.RedisConstants.SHOP_LIKED_USERS_KEY;

/**
 * <p>
 *  博客(探店笔记)服务实现类 —— 【八股：Redis ZSet 数据结构】
 *
 *  ZSet（Sorted Set，有序集合）特点：
 *  - 元素唯一不重复（和Set一样）
 *  - 每个元素有一个score（分数），按score排序
 *  - 底层实现：跳表(skiplist) + 哈希表
 *  - 时间复杂度：添加/删除/查找都是 O(log n)
 *
 *  本项目中ZSet的应用场景：
 *  - 点赞排行榜：用户ID是member，时间戳是score，按点赞时间排序
 *  - Feed流（关注推送）：博客ID是member，时间戳是score，按时间倒序展示
 *
 *  【八股：ZSet底层为什么用跳表而不是红黑树？】
 *  - 跳表实现更简单，代码容易维护
 *  - 范围查询效率更高（红黑树范围查询需要中序遍历，跳表直接走链表）
 *  - 插入删除的平均时间复杂度都是O(log n)，和红黑树差不多
 *  - Redis作者认为跳表在并发场景下更容易实现（锁的粒度更细）
 * </p>
 *
 * @author 虎哥
 * @since 2021-12-22
 */
@Service
public class BlogServiceImpl extends ServiceImpl<BlogMapper, Blog> implements IBlogService {

    @Resource
    private IUserService userService;

    @Resource
    private IFollowService followService;

    @Resource
    private StringRedisTemplate stringRedisTemplate;

    @Override
    public Result queryHotBlog(Integer current) {
        // 根据用户查询
        Page<Blog> page = query()
                .orderByDesc("liked")
                .page(new Page<>(current, SystemConstants.MAX_PAGE_SIZE));
        // 获取当前页数据
        List<Blog> records = page.getRecords();
        // 查询用户
        records.forEach(blog -> {
            this.isBlogLiked(blog);
            this.queryBlogUser(blog);
        });
        return Result.ok(records);
    }

    /**
     * 点赞/取消点赞 —— 【八股：为什么用ZSet存点赞用户，而不是Set？】
     *
     * Set也能存点赞用户ID，也能判断是否点赞
     * 但ZSet多了一个score字段，可以用来排序
     *
     * 业务需求：点赞排行榜（前5个点赞的用户）
     * - 用Set：存进去是无序的，没法知道谁先谁后
     * - 用ZSet：时间戳作为score，天然按点赞时间排序，取前5个就是最早点赞的
     *
     * 所以选择ZSet的核心原因是：需要排序功能
     * 如果只需要判断是否点赞，用Set就够了，更省内存
     *
     * @param id 博客ID
     * @return
     */
    @Override
    public Result updateLike(Long id){
        //1.获取当前用户
        Long userId = UserHolder.getUser().getId();

        //1.1 查询blog获取shopId —— 用于维护协同过滤的"用户-商铺"点赞关系
        // 【八股：为什么需要查blog获取shopId？】
        // 点赞操作的对象是blog，但协同过滤推荐需要"用户-商铺"的关系
        // blog表有shopId字段，通过blogId查到shopId，才能维护user:liked:shops和shop:liked:users
        Blog blog = getById(id);
        if(blog==null){
            return Result.fail("博客不存在");
        }
        Long shopId = blog.getShopId();

        //2.判断当前用户有没有点赞
        String key=BLOG_LIKED_KEY+id;
        // 【八股：ZSet的score方法是干什么的？】
        // ZSCORE key member
        // 获取指定member的score值
        // 如果member不存在，返回null
        // 这里用score是否为null来判断用户是否点过赞
        // 时间复杂度O(1)，非常高效
        Double score = stringRedisTemplate.opsForZSet().score(key, userId.toString());
        if(score==null) {
            //3.如果未点赞，可以点赞
            //3.1.数据库点赞数+1
            boolean isSuccess = update().setSql("liked=liked+1").eq("id", id).update();
            //3.2.保存用户到redis的ZSet集合  zadd key value score
            // 【八股：为什么用时间戳作为score？】
            // 业务上需要"点赞排行榜"，展示最早点赞的用户
            // 时间戳越大表示点赞越晚，时间戳越小表示点赞越早
            // 用时间戳当score，天然按点赞时间排序
            // 取前N个就是最早点赞的N个用户
            if(isSuccess){
                stringRedisTemplate.opsForZSet().add(key,userId.toString(),System.currentTimeMillis());

                //3.3 维护协同过滤所需的"用户-商铺"点赞关系（Redis Set）
                // 【八股：为什么额外维护Set？ZSet不是已经存了点赞用户吗？】
                // ZSet存的是 blog:liked:{blogId} → userId，是"用户-blog"关系
                // 协同过滤需要"用户-商铺"关系：
                //   user:liked:shops:{userId} → shopId（用户点赞过哪些商铺）
                //   shop:liked:users:{shopId} → userId（商铺被哪些用户点赞）
                // ZSet只存blog维度，Set补存shop维度，两者互补
                // Set的SADD/SREM/SINTER都是O(1)或O(n)操作，性能好
                if(shopId!=null){
                    // SADD user:liked:shops:{userId} shopId
                    stringRedisTemplate.opsForSet().add(USER_LIKED_SHOPS_KEY+userId, shopId.toString());
                    // SADD shop:liked:users:{shopId} userId
                    stringRedisTemplate.opsForSet().add(SHOP_LIKED_USERS_KEY+shopId, userId.toString());
                }
            }
        }else {
            //4.如果已经点赞，取消点赞
            //4.1.数据库点赞数-1
            boolean isSuccess = update().setSql("liked=liked-1").eq("id", id).update();
            if(isSuccess) {
                //4.2.将用户从ZSet集合中移除
                stringRedisTemplate.opsForZSet().remove(key,userId.toString());

                //4.3 同步移除协同过滤的"用户-商铺"点赞关系（Redis Set）
                // 保持ZSet和Set数据一致，取消点赞时必须同时清理
                if(shopId!=null){
                    // SREM user:liked:shops:{userId} shopId
                    stringRedisTemplate.opsForSet().remove(USER_LIKED_SHOPS_KEY+userId, shopId.toString());
                    // SREM shop:liked:users:{shopId} userId
                    stringRedisTemplate.opsForSet().remove(SHOP_LIKED_USERS_KEY+shopId, userId.toString());
                }
            }
        }
        return Result.ok();
    }

    /**
     * 查询点赞排行榜（Top5）
     *
     * 【八股：ZSet的range命令】
     * ZRANGE key start stop —— 按score从小到大取指定范围的元素
     * start=0, stop=4 就是取前5个（索引从0开始）
     * 因为时间戳小的排前面，所以前5个就是最早点赞的5个用户
     *
     * 【八股：ZSet时间复杂度总结】
     * - ZADD：O(log n)
     * - ZREM：O(log n)
     * - ZSCORE：O(1)
     * - ZRANGE：O(log n + m)，m是返回的元素数量
     * - ZRANK：O(log n)
     */
    @Override
    public Result queryBlogLikes(Long id) {
        //1.查询top5的点赞用户
        String key=BLOG_LIKED_KEY+id;
        Set<String> top5 = stringRedisTemplate.opsForZSet().range(key, 0, 4);
        if(top5==null||top5.isEmpty()){
            return Result.ok(Collections.emptyList());
        }
        //2.解析出其中的id
        List<Long> ids = top5.stream().map(Long::valueOf).collect(Collectors.toList());
        String idStr = StrUtil.join(",",ids);
        //3.根据用户id查询用户
        //SELECT *from tb_user where id IN(5,1) ORDER BY FIELD(id,5,1)
        // 【八股：为什么要用ORDER BY FIELD？】
        // MySQL的IN查询不会按IN里的顺序返回结果
        // 但我们需要按点赞时间顺序展示（最早点赞的在前）
        // 所以用FIELD函数手动指定排序顺序
        // FIELD(id, 5, 1) 表示id=5排第一，id=1排第二
        List<UserDTO> userDTOS = userService.query()
                .in("id",ids).last("order by field(id,"+idStr+")").list()
                .stream()
                .map(user -> BeanUtil.copyProperties(user, UserDTO.class))
                .collect(Collectors.toList());

        //4.返回
        return Result.ok(userDTOS);

    }

    /**
     * 发布探店笔记 —— 【八股：Feed流（关注推送）的实现思路】
     *
     * Feed流的两种实现模式：
     *
     * 1. 拉模式（Pull）：用户主动拉取
     *    - 发微博：只写入发件人的表
     *    - 刷首页：去查所有关注的人的微博，合并排序
     *    - 优点：写操作简单，不浪费存储
     *    - 缺点：读操作慢，关注的人多了查询很慢
     *    - 适用：关注人数不多的场景，或者微博这种大V场景（大V粉丝太多，推不动）
     *
     * 2. 推模式（Push）：主动推送给粉丝
     *    - 发微博：写入发件人表的同时，给每个粉丝的收件箱写一份
     *    - 刷首页：直接查自己的收件箱，快
     *    - 优点：读操作快，体验好
     *    - 缺点：写操作慢，粉丝多的话写扩散严重，浪费存储
     *    - 适用：普通用户场景，粉丝数不多
     *
     * 3. 推拉结合：
     *    - 普通用户用推模式
     *    - 大V用拉模式（粉丝太多，推不动）
     *    - 刷首页时，合并自己的收件箱 + 关注的大V的最新微博
     *
     * 本项目采用的是推模式（写扩散），把博客ID推送到每个粉丝的Feed流ZSet中
     *
     * 【八股：为什么用ZSet存Feed流？】
     * - 需要按时间排序：ZSet的score就是时间戳，天然有序
     * - 需要滚动分页：ZSet支持按score范围查询，适合实现"上拉加载更多"
     * - 元素唯一：同一篇博客不会在Feed流里出现两次
     */
    @Override
    public Result saveBlog(Blog blog) {
        // 获取登录用户
        UserDTO user = UserHolder.getUser();
        blog.setUserId(user.getId());
        // 保存探店博文
        boolean isSuccess = save(blog);
        if(!isSuccess){
           return Result.fail("新增笔记失败");
        }
        //查询笔记作者的所有粉丝 select* from tb_follow where follow_user_id=?
        List<Follow> follows = followService.query().eq("follow_user_id", user.getId()).list();
        //推送笔记id给所有粉丝
        for (Follow follow : follows) {
            //获取粉丝id
            Long userId = follow.getUserId();
            //推送
            String key=FEED_KEY+userId;
            // 【八股：Feed流的滚动分页怎么实现？】
            // 用ZSet的ZREVRANGEBYSCORE命令
            // 客户端传：min（上次最小时间戳）、offset（偏移量）
            // 服务端按score倒序查，从min开始，跳过offset条
            // 这样就实现了类似微博的"上拉加载更多"
            stringRedisTemplate.opsForZSet().add(key,blog.getId().toString(),System.currentTimeMillis());
        }
        // 返回id
        return Result.ok(blog.getId());
    }

    /**
     * 查询关注的人的博客（Feed流滚动分页）
     *
     * 【八股：滚动分页 vs 普通分页】
     *
     * 普通分页（PageHelper）：
     * - 用 limit offset, size
     * - 问题1：数据实时变化，翻页可能重复或漏掉
     * - 问题2：offset很大时性能差（MySQL要扫描很多行）
     *
     * 滚动分页（Scroll）：
     * - 用"上次最后一条的位置"作为游标
     * - 数据稳定，不会重复不会漏
     * - 性能好，直接从游标位置开始查
     * - 缺点：不能跳页（只能一页一页往下翻）
     *
     * Feed流场景用滚动分页更合适，因为用户都是一页一页往下刷的
     *
     * 【八股：ZSet滚动分页的实现细节】
     * 用 ZREVRANGEBYSCORE key max min LIMIT offset count
     * - max：上一次查询的最小时间戳（第一次查询用当前时间）
     * - min：0（或一个很早的时间）
     * - offset：偏移量，因为可能有多个元素score相同
     *
     * 返回结果包含：
     * - 数据列表
     * - 本次查询的最小时间戳（作为下次查询的max）
     * - 本次最小时间戳的重复个数（作为下次的offset）
     */
    @Override
    public Result quertBlogOfFollow(Long max, Integer offset) {
        //1.获取当前用户
        Long userId = UserHolder.getUser().getId();
        //2.查询收件箱  zrevrangebyscore key  min max limit offset count
        String key=FEED_KEY+userId;
        Set<ZSetOperations.TypedTuple<String>> typedTuples = stringRedisTemplate.opsForZSet()
                .reverseRangeByScoreWithScores(key, 0, max, offset, 2);
        if(typedTuples==null||typedTuples.isEmpty()){
            return Result.ok();
        }
        //3.解析数据：blogId,minTime时间戳),offset
        List<Long> ids=new ArrayList<>(typedTuples.size());
        long minTime=0;
        int os=1;
        for (ZSetOperations.TypedTuple<String> typedTuple : typedTuples) {
            //3.1.获取id
            ids.add(Long.valueOf( typedTuple.getValue()));
            //3.2.获取分数（时间戳）
            long time=typedTuple.getScore().longValue();
            if(time==minTime){
                os++;
            }else {
                minTime = time;
                os = 1;
            }

        }
        //4.根据id查询blog
        String idStr = StrUtil.join(",", ids);
        List<Blog> blogs = query()
                .in("id", ids).last("order by field(id," + idStr + ")").list();

        for (Blog blog : blogs) {
           //4.1.查询blog有关的用户
            queryBlogUser(blog);
            //4.2查询blog是否点赞
            isBlogLiked(blog);
        }
        //5.封装并返回
        ScrollResult scrollResult = new ScrollResult();
        scrollResult.setList(blogs);
        scrollResult.setOffset(os);
        scrollResult.setMinTime(minTime);
        return Result.ok(scrollResult);

    }

    @Override
    public Result  queryBlogById(Long id) {
        //1.查询blog
        Blog blog = getById(id);
        //2.查询blog关联的对象
        if(blog==null){
            return Result.fail("博客不存在");
        }
        queryBlogUser(blog);
        //3.查询blog是否点赞
        isBlogLiked(blog);
        return Result.ok(blog);
    }

    private void isBlogLiked(Blog blog) {
        //1.获取当前用户
        UserDTO user = UserHolder.getUser();
        if(user==null){
            //用户未登录，无需查询是否点赞
            return;
        }
        Long userId = user.getId();

        //2.判断当前用户有没有点赞
        String key=BLOG_LIKED_KEY+blog.getId();
        Double score = stringRedisTemplate.opsForZSet().score(key, userId.toString());
        blog.setIsLike(score!=null);
    }

    private void queryBlogUser(Blog blog) {
        Long userId = blog.getUserId();
        User user = userService.getById(userId);
        blog.setName(user.getNickName());
        blog.setIcon(user.getIcon());
    }

}
