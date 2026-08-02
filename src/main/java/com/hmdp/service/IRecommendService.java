package com.hmdp.service;

import com.hmdp.dto.Result;

/**
 * 推荐服务接口 —— 【八股：推荐系统的三大核心场景】
 *
 * 【八股：推荐系统分类】
 * 1. 个性化推荐（recommendShops）：根据用户历史行为推荐，解决"千人千面"
 * 2. 附近推荐（nearbyHotShops）：基于地理位置的LBS推荐，解决"附近有什么"
 * 3. 热门排行（hotShops）：全站热门内容，解决"大家都在看什么"（冷启动兜底）
 *
 * 这三种推荐方式互补：
 * - 新用户没有历史行为 → 用热门排行兜底（冷启动）
 * - 老用户有历史行为 → 用协同过滤做个性化推荐
 * - 用户有位置信息 → 用GEO推荐附近热门
 */
public interface IRecommendService {

    /**
     * 基于当前用户的协同过滤推荐
     *
     * 【八股：协同过滤（Collaborative Filtering）】
     * 核心思想：找到和你兴趣相似的人，推荐他们喜欢但你还没看过的东西
     *
     * @return 推荐商铺列表
     */
    Result recommendShops();

    /**
     * 附近热门商铺排行
     *
     * 基于Redis GEO搜索附近商铺，按评分和销量排序
     *
     * @param x      经度
     * @param y      纬度
     * @param typeId 商铺类型（可选）
     * @return 附近热门商铺列表
     */
    Result nearbyHotShops(Double x, Double y, Long typeId);

    /**
     * 全站热门商铺排行
     *
     * 按销量降序排列，可结合Redis ZSet缓存
     *
     * @return 热门商铺列表
     */
    Result hotShops();
}
