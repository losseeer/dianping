package com.hmdp.controller;

import com.hmdp.annotation.RateLimit;
import com.hmdp.dto.Result;
import com.hmdp.entity.Shop;
import com.hmdp.service.IShopSearchService;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;

/**
 * 商铺搜索控制器 —— ES全文搜索接口
 *
 * 【八股：RESTful API设计规范】
 * - GET    /shop/search          —— 搜索商铺（查询操作用GET，参数在URL）
 * - POST   /shop/search/sync     —— 全量同步到ES（有副作用的操作用POST）
 * - POST   /shop/search/import   —— 单条导入ES（有副作用的操作用POST）
 *
 * 【八股：GET vs POST的选择】
 * - 搜索是查询操作（幂等、无副作用），适合用GET
 * - 同步/导入是写操作（有副作用），适合用POST
 * - GET的URL长度有限（浏览器约2KB），超长查询条件才考虑POST
 */
@RestController
@RequestMapping("/shop/search")
public class ShopSearchController {

    @Resource
    private IShopSearchService shopSearchService;

    /**
     * 全文搜索商铺
     *
     * 【八股：搜索接口为什么需要限流？】
     * 1. ES是CPU密集型服务：分词、打分、排序都消耗CPU
     * 2. 深分页性能差：from + size 越大越慢
     * 3. 恶意搜索：构造复杂查询条件拖垮ES
     * 4. QPS=100：每秒100次搜索，对单节点ES足够
     * 5. 如果ES扛不住，还应该加一层熔断保护
     *
     * 【八股：搜索接口的限流和秒杀限流有什么不同？】
     * - 秒杀：QPS=50，拒绝策略是"请稍后再试"
     * - 搜索：QPS=100，拒绝策略也是"请稍后再试"
     * - 搜索不需要像秒杀那么严格，因为搜索不是"抢"
     * - 但ES的资源消耗比Redis大，所以也要限流
     *
     * @param keyword 搜索关键词（必填）
     * @param typeId  商铺类型ID（可选）
     * @param area    商圈（可选）
     * @param current 当前页码，默认1
     * @param size    每页条数，默认10
     * @return 搜索结果
     */
    @GetMapping
    @RateLimit(qps = 100, message = "搜索请求过于频繁，请稍后再试")
    public Result search(
            @RequestParam("keyword") String keyword,
            @RequestParam(value = "typeId", required = false) Long typeId,
            @RequestParam(value = "area", required = false) String area,
            @RequestParam(value = "current", defaultValue = "1") Integer current,
            @RequestParam(value = "size", defaultValue = "10") Integer size
    ) {
        return shopSearchService.search(keyword, typeId, area, current, size);
    }

    /**
     * 全量同步MySQL商铺数据到ES
     *
     * 【八股：什么时候需要全量同步？】
     * - 系统首次上线，ES索引为空
     * - 数据出现不一致，需要修复
     * - ES索引结构变更（mapping修改后需要重建）
     *
     * @return 同步结果
     */
    @PostMapping("/sync")
    public Result syncShopToEs() {
        return shopSearchService.syncShopToEs();
    }

    /**
     * 导入单个商铺到ES
     *
     * 【八股：单条导入的应用场景】
     * - 新增商铺时实时同步到ES
     * - 商铺信息修改后更新ES
     * - 通常在商铺的save/update接口中自动调用
     *
     * @param shop 商铺数据
     * @return 导入结果
     */
    @PostMapping("/import")
    public Result importShop(@RequestBody Shop shop) {
        return shopSearchService.importShop(shop);
    }

    /**
     * 重建 ES shop 索引（DROP + CREATE + PUT MAPPING + MySQL 全量导入）。
     *
     * 【典型使用时机】
     * 1. 修改 classpath:synonyms.txt（同义词表）后，需要让 synonym_graph filter 立即生效
     * 2. 调整 analyzer / mapping 后需要重建
     * 3. ES 索引损坏或 mapping 未写入时的一键修复
     *
     * 与重启 rebuild-on-startup=true 的区别：本接口可在服务运行期间随时调用，无需重启。
     * 【八股：为什么要 DROP 再重建？】
     *   · ES 的 index settings（analysis.filter/analyzer 部分）是「不可变」的——索引创建后，
     *     不能直接 PUT _settings 修改 analysis，必须 close → update → open；更稳妥且简单的方式
     *     （尤其项目数据量 <1000）就是 DROP + 重建 + MySQL 重导，一次解决所有 setting/mapping/sync 问题。
     *
     * @return 重建摘要（indexExistedBefore / dropped / created / mappingApplied / importedShops / tookMs 等）
     */
    @PostMapping("/rebuild-index")
    public Result rebuildIndex() {
        return shopSearchService.rebuildIndex();
    }
}
