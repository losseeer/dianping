package com.hmdp.controller;

import com.hmdp.dto.Result;
import com.hmdp.service.IRecommendService;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;

/**
 * 推荐控制器 —— 个性化推荐 + 附近热门 + 全站热门
 *
 * 【八股：推荐系统的三种典型场景与对应API】
 *
 * 1. 个性化推荐（GET /recommend/shops）
 *    - 不需要传参数，从Token中获取当前用户ID
 *    - 返回"千人千面"的推荐列表
 *    - 适合首页"猜你喜欢"模块
 *
 * 2. 附近热门（GET /recommend/nearby）
 *    - 需要传经纬度（x, y）
 *    - 可选传typeId过滤类型
 *    - 返回附近的商铺，按热门度排序
 *    - 适合"附近"Tab页
 *
 * 3. 全站热门（GET /recommend/hot）
 *    - 不需要参数
 *    - 返回全站最火的商铺
 *    - 适合"热榜"模块或冷启动兜底
 */
@RestController
@RequestMapping("/recommend")
public class RecommendController {

    @Resource
    private IRecommendService recommendService;

    /**
     * 个性化推荐商铺
     *
     * 基于当前用户的历史点赞行为，通过协同过滤算法推荐商铺。
     * 用户未登录或无历史行为时，退化为全站热门推荐。
     *
     * @return 推荐商铺列表
     */
    @GetMapping("/shops")
    public Result recommendShops() {
        return recommendService.recommendShops();
    }

    /**
     * 附近热门商铺
     *
     * 基于Redis GEO搜索用户附近的商铺，按评分和销量排序。
     *
     * @param x      经度
     * @param y      纬度
     * @param typeId 商铺类型ID（可选，不传则返回所有类型的热门）
     * @return 附近热门商铺列表
     */
    @GetMapping("/nearby")
    public Result nearbyHotShops(
            @RequestParam("x") Double x,
            @RequestParam("y") Double y,
            @RequestParam(value = "typeId", required = false) Long typeId
    ) {
        return recommendService.nearbyHotShops(x, y, typeId);
    }

    /**
     * 全站热门商铺排行
     *
     * 按销量降序、评分降序排列，返回全站最热门的商铺。
     * 使用Redis ZSet缓存，提升查询性能。
     *
     * @return 热门商铺列表
     */
    @GetMapping("/hot")
    public Result hotShops() {
        return recommendService.hotShops();
    }
}
