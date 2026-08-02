package com.hmdp.service.impl;

import cn.hutool.core.util.StrUtil;
import com.hmdp.dto.Result;
import com.hmdp.entity.Shop;
import com.hmdp.service.IBlogService;
import com.hmdp.service.IRecommendService;
import com.hmdp.service.IShopService;
import com.hmdp.utils.RedisConstants;
import com.hmdp.utils.UserHolder;
import org.springframework.data.geo.Distance;
import org.springframework.data.geo.GeoResult;
import org.springframework.data.geo.GeoResults;
import org.springframework.data.redis.connection.RedisGeoCommands;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.domain.geo.GeoReference;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.util.*;
import java.util.stream.Collectors;

import static com.hmdp.utils.RedisConstants.*;

/**
 * 推荐服务实现类 —— 协同过滤推荐 + 附近热门 + 全站热门
 *
 * 【八股：协同过滤（Collaborative Filtering）原理】
 *
 * 协同过滤是推荐系统最经典的算法，核心思想是"物以类聚，人以群分"：
 * - 和你兴趣相似的人喜欢的东西，你可能也喜欢
 *
 * 两大流派：
 *
 * 1. User-based CF（基于用户的协同过滤）—— 本项目采用
 *    步骤：
 *    a) 找到和目标用户兴趣相似的用户群体
 *    b) 把相似用户喜欢但目标用户还没看过的物品推荐给目标用户
 *    示例：用户A喜欢[牛排,寿司]，用户B喜欢[牛排,寿司,火锅]
 *         A和B兴趣相似 → 把"火锅"推荐给A
 *
 * 2. Item-based CF（基于物品的协同过滤）
 *    步骤：
 *    a) 计算物品之间的相似度（被相同用户喜欢的物品相似度高）
 *    b) 用户喜欢某物品 → 推荐与之相似的其他物品
 *    示例：喜欢"牛排"的人大多也喜欢"红酒" → 牛排和红酒相似
 *         用户喜欢牛排 → 推荐红酒
 *
 * User-based vs Item-based：
 *    - User-based：用户多时计算量大（用户相似度矩阵 N×N），适合用户数少的场景
 *    - Item-based：物品相对稳定，可离线计算物品相似度，适合物品数少的场景
 *    - Amazon最早用Item-based，因为商品数远少于用户数
 *
 * 【八股：相似度计算方法】
 *
 * 1. 余弦相似度（Cosine Similarity）
 *    把用户的行为看作向量，计算两个向量的夹角余弦值
 *    cos(A,B) = (A·B) / (|A| × |B|)
 *    值域[-1,1]，越接近1越相似
 *    优点：考虑了评分大小，适合显式评分（1-5分）
 *
 * 2. Jaccard相似度（杰卡德相似度）—— 本项目隐式使用
 *    J(A,B) = |A∩B| / |A∪B|
 *    只考虑是否喜欢（0/1），不考虑评分大小
 *    适合隐式反馈（点赞、点击、浏览）
 *
 * 3. 皮尔逊相关系数（Pearson Correlation）
 *    在余弦相似度基础上减去用户平均分，消除评分尺度差异
 *    适合评分尺度不一的场景
 *
 * 本项目简化实现：用Redis Set存储用户-商铺的点赞关系
 * 用"共同点赞的商铺数"作为相似度度量（Jaccard的简化版）
 *
 * 【八股：推荐系统的冷启动问题】
 *
 * 冷启动 = 新用户/新物品没有历史数据，无法做个性化推荐
 *
 * 三种冷启动：
 * 1. 用户冷启动：新用户没有点赞/浏览记录
 *    解决：用热门排行兜底、注册时让用户选兴趣标签
 * 2. 物品冷启动：新商铺没有人点赞
 *    解决：基于内容推荐（用商铺的标签、类型做推荐）
 * 3. 系统冷启动：新系统没有数据
 *    解决：先用规则推荐（热门、最新），积累数据后切换算法
 *
 * 本项目处理：如果用户没有点赞记录，退化为全站热门推荐（按sold排序）
 */
@Service
public class RecommendServiceImpl implements IRecommendService {

    @Resource
    private StringRedisTemplate stringRedisTemplate;

    @Resource
    private IShopService shopService;

    /**
     * Blog服务 —— 用于查询博客相关数据
     * 在协同过滤中，可通过Blog获取用户与商铺的互动关系
     */
    @Resource
    private IBlogService blogService;

    /**
     * 推荐列表默认返回数量
     */
    private static final int RECOMMEND_LIMIT = 10;

    /**
     * 附近搜索半径（米）
     */
    private static final double NEARBY_RADIUS = 5000;

    /**
     * 热门商铺返回数量
     */
    private static final int HOT_LIMIT = 20;

    /**
     * 基于当前用户的协同过滤推荐（简化版User-based CF）
     *
     * 实现思路：
     * 1. 获取当前用户点赞过的所有商铺（Redis Set: user:liked:shops:{userId}）
     * 2. 对每个点过赞的商铺，找也点赞过该商铺的其他用户（Redis Set: shop:liked:users:{shopId}）
     * 3. 收集所有相似用户（与当前用户有共同点赞商铺的用户）
     * 4. 获取相似用户点赞过的商铺，排除当前用户已点赞的
     * 5. 按商铺被多少个相似用户点赞（出现次数）排序，取TopN推荐
     * 6. 冷启动处理：如果没有推荐结果，退化为全站热门推荐
     *
     * 【八股：为什么用Redis Set实现协同过滤？】
     * - Set的SINTER命令可以高效求交集（找共同点赞的用户）
     * - Set的SMEMBERS命令可以获取所有成员
     * - SADD/SREM是O(1)操作，维护成本低
     * - 缺点：大规模数据下Set会占用大量内存
     * - 生产环境通常用离线计算相似度矩阵 + 在线查询
     */
    @Override
    public Result recommendShops() {
        // 1.获取当前登录用户（冷启动处理：未登录用户看热门）
        if (UserHolder.getUser() == null) {
            return hotShops();
        }
        Long userId = UserHolder.getUser().getId();
        String userLikedShopsKey = USER_LIKED_SHOPS_KEY + userId;

        // 2.获取当前用户点赞过的所有商铺ID
        Set<String> likedShopIds = stringRedisTemplate.opsForSet().members(userLikedShopsKey);
        if (likedShopIds == null || likedShopIds.isEmpty()) {
            // 冷启动：用户没有点赞记录，退化为热门推荐
            return hotShops();
        }

        // 3.收集所有相似用户（点赞过相同商铺的其他用户）
        // 相似度度量：共同点赞的商铺越多，用户越相似（Jaccard相似度的简化版）
        Set<String> similarUserIds = new HashSet<>();
        for (String shopId : likedShopIds) {
            String shopLikedUsersKey = SHOP_LIKED_USERS_KEY + shopId;
            // 获取点赞过该商铺的所有用户
            Set<String> users = stringRedisTemplate.opsForSet().members(shopLikedUsersKey);
            if (users != null) {
                // 排除自己，加入相似用户集合
                for (String uid : users) {
                    if (!uid.equals(userId.toString())) {
                        similarUserIds.add(uid);
                    }
                }
            }
        }

        if (similarUserIds.isEmpty()) {
            // 没有相似用户，退化为热门推荐
            return hotShops();
        }

        // 4.统计相似用户点赞的商铺出现次数（排除当前用户已点赞的）
        // key=shopId, value=被多少个相似用户点赞（推荐权重）
        Map<String, Integer> shopCountMap = new HashMap<>();
        for (String similarUserId : similarUserIds) {
            String similarUserLikedKey = USER_LIKED_SHOPS_KEY + similarUserId;
            Set<String> similarLikedShops = stringRedisTemplate.opsForSet().members(similarUserLikedKey);
            if (similarLikedShops != null) {
                for (String shopId : similarLikedShops) {
                    // 排除当前用户已经点赞过的商铺（不重复推荐）
                    if (!likedShopIds.contains(shopId)) {
                        shopCountMap.merge(shopId, 1, Integer::sum);
                    }
                }
            }
        }

        if (shopCountMap.isEmpty()) {
            // 相似用户没有新商铺可推荐，退化为热门推荐
            return hotShops();
        }

        // 5.按出现次数（推荐权重）降序排序，取TopN
        List<String> recommendedShopIds = shopCountMap.entrySet().stream()
                .sorted((a, b) -> b.getValue().compareTo(a.getValue()))
                .limit(RECOMMEND_LIMIT)
                .map(Map.Entry::getKey)
                .collect(Collectors.toList());

        if (recommendedShopIds.isEmpty()) {
            return hotShops();
        }

        // 6.根据推荐排序的shopId列表查询商铺详情
        // 使用ORDER BY FIELD保持推荐顺序（出现次数高的排前面）
        List<Long> ids = recommendedShopIds.stream().map(Long::valueOf).collect(Collectors.toList());
        String idStr = StrUtil.join(",", ids);
        List<Shop> shops = shopService.query()
                .in("id", ids)
                .last("order by field(id," + idStr + ")")
                .list();

        return Result.ok(shops);
    }

    /**
     * 附近热门商铺排行
     *
     * 【八股：Redis GEO的数据结构】
     *
     * Redis GEO基于ZSet实现，用于存储和查询地理位置信息。
     *
     * 存储原理：
     *   - 使用GeoHash算法将经纬度编码为一个分数（score）
     *   - GeoHash将二维平面划分网格，相近的位置有相同的前缀
     *   - 底层就是一个ZSet，member=位置名称，score=GeoHash值
     *
     * 核心命令：
     *   GEOADD key longitude latitude member —— 添加地理位置
     *   GEODIST key member1 member2 —— 计算两点距离
     *   GEOSEARCH key FROMLONLAT x y BYRADIUS radius unit —— 搜索半径内的位置
     *
     * 本项目中GEO的应用：
     *   - key = shop:geo:{typeId}，按商铺类型分别存储
     *   - member = shopId（商铺ID）
     *   - 经纬度 = 商铺的x, y坐标
     *   - 查询：用户定位 → 搜索半径5000米内的商铺
     *
     * 【八股：GeoHash编码原理】
     * GeoHash将二维经纬度编码为一维字符串，核心思想：
     *   1. 将经度和纬度分别二进制编码（不断二分区间）
     *   2. 交叉组合经纬度二进制位（偶数位放经度，奇数位放纬度）
     *   3. 每5位一组，用Base32编码成字符
     *   示例：经度116.40, 纬度39.90 → GeoHash "wx4g0"
     *   特点：前缀相同的位置越近，可以用前缀快速过滤
     */
    @Override
    public Result nearbyHotShops(Double x, Double y, Long typeId) {
        if (x == null || y == null) {
            // 没有坐标，退化为全站热门
            return hotShops();
        }

        // 1.如果没有指定类型，直接从MySQL查热门
        if (typeId == null) {
            List<Shop> shops = shopService.query()
                    .orderByDesc("score")
                    .orderByDesc("sold")
                    .last("limit " + HOT_LIMIT)
                    .list();
            return Result.ok(shops);
        }

        // 2.用Redis GEO搜索附近商铺
        String key = SHOP_GEO_KEY + typeId;
        // GEOSEARCH：以(x,y)为中心，搜索5000米内的商铺，限制返回HOT_LIMIT条
        GeoResults<RedisGeoCommands.GeoLocation<String>> results = stringRedisTemplate.opsForGeo()
                .search(
                        key,
                        GeoReference.fromCoordinate(x, y),
                        new Distance(NEARBY_RADIUS),
                        RedisGeoCommands.GeoSearchCommandArgs.newGeoSearchArgs()
                                .includeDistance()
                                .limit(HOT_LIMIT)
                );

        if (results == null || results.getContent().isEmpty()) {
            return Result.ok(Collections.emptyList());
        }

        // 3.解析出商铺ID
        List<GeoResult<RedisGeoCommands.GeoLocation<String>>> list = results.getContent();
        List<Long> ids = new ArrayList<>(list.size());
        Map<String, Double> distanceMap = new HashMap<>(list.size());
        for (GeoResult<RedisGeoCommands.GeoLocation<String>> result : list) {
            String shopIdStr = result.getContent().getName();
            ids.add(Long.valueOf(shopIdStr));
            distanceMap.put(shopIdStr, result.getDistance().getValue());
        }

        if (ids.isEmpty()) {
            return Result.ok(Collections.emptyList());
        }

        // 4.根据ID查询商铺详情
        List<Shop> shops = shopService.listByIds(ids);

        // 5.按评分和销量排序（GEO结果按距离排序，这里按热门度重排）
        shops.sort((a, b) -> {
            // 先按评分降序
            int scoreCompare = Integer.compare(
                    b.getScore() == null ? 0 : b.getScore(),
                    a.getScore() == null ? 0 : a.getScore()
            );
            if (scoreCompare != 0) {
                return scoreCompare;
            }
            // 再按销量降序
            return Integer.compare(
                    b.getSold() == null ? 0 : b.getSold(),
                    a.getSold() == null ? 0 : a.getSold()
            );
        });

        // 6.填充距离信息
        for (Shop shop : shops) {
            Double distance = distanceMap.get(shop.getId().toString());
            if (distance != null) {
                shop.setDistance(distance);
            }
        }

        return Result.ok(shops);
    }

    /**
     * 全站热门商铺排行
     *
     * 【八股：热门排行的缓存策略】
     *
     * 热门排行是高频访问接口，直接查MySQL压力大。
     * 缓存方案：
     *   1. Redis ZSet缓存：key=shop:hot:，member=shopId，score=sold
     *      ZSet天然按score排序，ZREVRANGE取TopN，性能极高
     *   2. 缓存更新：商铺销量变化时更新ZSet，或定时全量刷新
     *   3. 缓存过期：设置TTL，避免缓存与数据库长期不一致
     *
     * 本方法实现：
     *   - 先查Redis ZSet缓存，命中则直接返回
     *   - 未命中则查MySQL（按sold和score排序），并更新缓存
     */
    @Override
    public Result hotShops() {
        // 1.尝试从Redis ZSet缓存获取热门商铺ID列表
        String hotKey = SHOP_HOT_KEY;
        Set<String> cachedShopIds = stringRedisTemplate.opsForZSet().reverseRange(hotKey, 0, HOT_LIMIT - 1);

        if (cachedShopIds != null && !cachedShopIds.isEmpty()) {
            // 缓存命中：根据ID查询商铺详情
            List<Long> ids = cachedShopIds.stream().map(Long::valueOf).collect(Collectors.toList());
            List<Shop> shops = shopService.listByIds(ids);
            // 按缓存中的顺序排序（ZSet已按sold降序）
            Map<Long, Shop> shopMap = new HashMap<>();
            for (Shop shop : shops) {
                shopMap.put(shop.getId(), shop);
            }
            List<Shop> orderedShops = new ArrayList<>();
            for (Long id : ids) {
                Shop shop = shopMap.get(id);
                if (shop != null) {
                    orderedShops.add(shop);
                }
            }
            return Result.ok(orderedShops);
        }

        // 2.缓存未命中：从MySQL查询，按sold降序 + score降序
        List<Shop> shops = shopService.query()
                .orderByDesc("sold")
                .orderByDesc("score")
                .last("limit " + HOT_LIMIT)
                .list();

        // 3.更新Redis ZSet缓存（score=sold，用于下次快速查询）
        for (Shop shop : shops) {
            if (shop.getId() != null && shop.getSold() != null) {
                stringRedisTemplate.opsForZSet().add(
                        hotKey,
                        shop.getId().toString(),
                        shop.getSold()
                );
            }
        }

        return Result.ok(shops);
    }
}
