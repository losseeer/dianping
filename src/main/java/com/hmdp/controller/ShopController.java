package com.hmdp.controller;


import cn.hutool.core.util.StrUtil;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.hmdp.annotation.CircuitBreaker;
import com.hmdp.dto.Result;
import com.hmdp.entity.Shop;
import com.hmdp.service.IShopService;
import com.hmdp.utils.SystemConstants;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;

/**
 * <p>
 * 前端控制器 —— 商铺查询
 * </p>
 *
 * 【八股：商铺查询为什么需要熔断？】
 * 商铺查询依赖Redis缓存：
 * 1. Redis宕机 → 大量请求超时 → 线程池耗尽 → 服务不可用
 * 2. 网络抖动 → Redis连接超时 → 请求堆积 → 雪崩
 * 3. 慢查询 → Redis响应慢 → 请求超时 → 用户等待
 *
 * 熔断的作用：
 * - 当Redis连续失败时，停止调用Redis，直接查MySQL
 * - 保护应用不被拖垮
 * - Redis恢复后自动切换回缓存模式
 *
 * 【八股：熔断后为什么查MySQL而不是直接返回错误？】
 * 这叫"降级"而非"拒绝"：
 * - 拒绝：用户看到"服务不可用"，体验差
 * - 降级：跳过缓存直查数据库，用户正常拿到数据（只是慢一点）
 * - 降级的前提：数据库能承受降级后的流量（通常加一层限流保护）
 *
 * @author 虎哥
 * @since 2021-12-22
 */
@RestController
@RequestMapping("/shop")
public class ShopController {

    @Resource
    public IShopService shopService;

    /**
     * 根据id查询商铺信息
     *
     * 熔断策略：
     * - 失败阈值：10次（60秒内失败10次就熔断）
     * - 恢复时间：30秒（熔断后30秒尝试探测）
     * - 降级方法：queryShopByIdFallback（直接查数据库）
     *
     * 【八股：为什么fallback参数和原方法一致？】
     * AOP切面通过反射调用降级方法，参数必须完全匹配
     * 否则反射找不到方法会抛NoSuchMethodException
     *
     * @param id 商铺id
     * @return 商铺详情数据
     */
    @GetMapping("/{id}")
    @CircuitBreaker(failureThreshold = 10, recoveryTimeout = 30000, fallback = "queryShopByIdFallback")
    public Result queryShopById(@PathVariable("id") Long id) throws InterruptedException {
        return shopService.queryById(id);
    }

    /**
     * 商铺查询的降级方法 —— 直查数据库，跳过Redis缓存
     *
     * 【八股：降级方法为什么用private？】
     * 1. 降级方法是内部逻辑，不需要暴露给外部调用
     * 2. AOP切面通过反射调用，setAccessible(true)可以调用private方法
     * 3. private更安全，不会被Spring MVC误注册为接口
     *
     * 【八股：降级方法为什么不加@CircuitBreaker？】
     * 降级方法本身不应该再被熔断保护
     * 否则：Redis挂了 → 触发熔断 → 调降级方法查DB → DB也慢 → 又触发熔断 → 死循环
     * 降级方法应该尽量简单可靠，直查数据库不经过任何中间件
     */
    private Result queryShopByIdFallback(Long id) {
        // 降级：直接查数据库，跳过缓存
        Shop shop = shopService.getById(id);
        if (shop == null) {
            return Result.fail("店铺不存在！");
        }
        return Result.ok(shop);
    }

    /**
     * 新增商铺信息
     * @param shop 商铺数据
     * @return 商铺id
     */
    @PostMapping
    public Result saveShop(@RequestBody Shop shop) {
        // 写入数据库
        shopService.save(shop);
        // 返回店铺id
        return Result.ok(shop.getId());
    }

    /**
     * 更新商铺信息
     * @param shop 商铺数据
     * @return 无
     */
    @PutMapping
    public Result updateShop(@RequestBody Shop shop) {
        // 写入数据库

        return shopService.update(shop);
    }

    /**
     * 根据商铺类型分页查询商铺信息
     * @param typeId 商铺类型
     * @param current 页码
     * @return 商铺列表
     */
    @GetMapping("/of/type")
    public Result queryShopByType(
            @RequestParam("typeId") Integer typeId,
            @RequestParam(value = "current", defaultValue = "1") Integer current,
            @RequestParam(value = "x",required = false) Double x,
            @RequestParam(value = "y",required = false) Double y
    ) {
        return shopService.queryShopByType(typeId,current,x,y);
    }

    /**
     * 根据商铺名称关键字分页查询商铺信息
     * @param name 商铺名称关键字
     * @param current 页码
     * @return 商铺列表
     */
    @GetMapping("/of/name")
    public Result queryShopByName(
            @RequestParam(value = "name", required = false) String name,
            @RequestParam(value = "current", defaultValue = "1") Integer current
    ) {
        // 根据类型分页查询
        Page<Shop> page = shopService.query()
                .like(StrUtil.isNotBlank(name), "name", name)
                .page(new Page<>(current, SystemConstants.MAX_PAGE_SIZE));
        // 返回数据
        return Result.ok(page.getRecords());
    }
}
