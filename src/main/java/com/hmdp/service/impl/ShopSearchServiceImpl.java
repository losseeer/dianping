package com.hmdp.service.impl;

import cn.hutool.core.bean.BeanUtil;
import cn.hutool.core.util.StrUtil;
import com.hmdp.document.ShopDoc;
import com.hmdp.dto.Result;
import com.hmdp.dto.ShopSearchResult;
import com.hmdp.entity.Shop;
import com.hmdp.repository.ShopDocRepository;
import com.hmdp.service.IShopService;
import com.hmdp.annotation.CircuitBreaker;
import com.hmdp.config.ElasticsearchConfiguration;
import com.hmdp.service.IShopSearchService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import lombok.extern.slf4j.Slf4j;
import org.elasticsearch.index.query.BoolQueryBuilder;
import org.elasticsearch.index.query.QueryBuilders;
import org.elasticsearch.search.fetch.subphase.highlight.HighlightBuilder;
import org.elasticsearch.search.sort.SortBuilders;
import org.elasticsearch.search.sort.SortOrder;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.elasticsearch.core.SearchHit;
import org.springframework.data.elasticsearch.core.SearchHits;
import org.springframework.data.elasticsearch.core.ElasticsearchRestTemplate;
import org.springframework.data.elasticsearch.core.query.NativeSearchQuery;
import org.springframework.data.elasticsearch.core.query.NativeSearchQueryBuilder;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * 商铺ES全文搜索服务实现类
 *
 * 【八股：倒排索引（Inverted Index）原理】
 * 倒排索引是ES全文搜索的核心数据结构，与传统的正向索引相反。
 *
 * 正向索引（MySQL B+树）：
 *   文档ID → 文档内容
 *   查询时需要扫描所有文档，逐个匹配关键词，效率低
 *
 * 倒排索引（ES）：
 *   关键词 → 文档ID列表
 *   分两步构建：
 *   1. 分词：将文档内容拆分成一个个词（Term），如"好吃的牛排" → ["好吃","的","牛排"]
 *   2. 构建：记录每个词出现在哪些文档中
 *
 *   词项表（Term Dictionary）          倒排表（Posting List）
 *   ┌──────────┐  ──────────────────►  ┌────────────────────────┐
 *   │ "好吃"   │                        │ [文档1, 文档3, 文档5]  │
 *   │ "牛排"   │  ──────────────────►  │ [文档1, 文档2]         │
 *   │ "餐厅"   │  ──────────────────►  │ [文档2, 文档3]         │
 *   └──────────┘                        └────────────────────────┘
 *
 * 搜索"好吃牛排"时：
 *   1. 分词：["好吃", "牛排"]
 *   2. 查倒排表："好吃" → [文档1,3,5]  "牛排" → [文档1,2]
 *   3. 取交集/并集：文档1同时包含两个词，相关度最高
 *   4. 按相关度排序返回
 *
 * 为什么ES搜索比MySQL LIKE快？
 *   - MySQL LIKE '%keyword%' 全表扫描，O(n)
 *   - ES通过倒排表直接定位文档，接近O(1)
 *
 * 【八股：FST（Finite State Transducer）优化】
 * 当词项数量巨大时，Term Dictionary内存占用大
 * ES用FST（有限状态转换器）压缩存储词项：
 *   - 类似字典树（Trie），但共享前缀和后缀
 *   - 前缀压缩：共享相同前缀的词
 *   - 后缀压缩：共享相同后缀的词
 *   FST将词项表加载到内存，Posting List存在磁盘
 *   搜索时先在内存FST中查到词项位置，再去磁盘读Posting List
 */
@Slf4j
@Service
public class ShopSearchServiceImpl implements IShopSearchService {

    /**
     * ES操作模板 —— 用于执行复杂的NativeSearchQuery查询
     */
    @Resource
    private ElasticsearchRestTemplate elasticsearchRestTemplate;

    /**
     * ES Repository —— 用于简单的CRUD操作（saveAll、findById等）
     */
    @Resource
    private ShopDocRepository shopDocRepository;

    /**
     * MySQL商铺服务 —— 用于从数据库查询商铺数据
     */
    @Resource
    private IShopService shopService;

    /**
     * Redis操作 —— 用于业务缓存
     */
    @Resource
    private StringRedisTemplate stringRedisTemplate;

    /**
     * ES 索引初始化配置 —— 用于 rebuildIndex 管理接口复用 DROP+CREATE+MAPPING+IMPORT 主流程
     */
    @Resource
    private ElasticsearchConfiguration elasticsearchConfiguration;

    @Override
    public Result rebuildIndex() {
        try {
            long start = System.currentTimeMillis();
            java.util.Map<String, Object> summary = elasticsearchConfiguration.rebuildIndexInternal(true);
            long took = System.currentTimeMillis() - start;
            summary.put("tookMs", took);
            log.info("[ES] rebuildIndex 管理接口执行完成: {}", summary);
            return Result.ok(summary);
        } catch (Exception e) {
            log.error("[ES] rebuildIndex 失败: {}", e.getMessage(), e);
            return Result.fail("重建ES索引失败: " + e.getMessage());
        }
    }

    /**
     * 全文搜索商铺
     *
     * 【八股：bool query的must vs filter区别】
     *
     * bool query是ES中组合多个查询条件的查询类型，包含4种子句：
     *
     * 1. must：必须匹配，参与相关度评分（_score）
     *    - 搜索"牛排"时，name中包含"牛排"的文档分数更高
     *    - 如果有多个must条件，分数会累加
     *    - 场景：用户输入的搜索关键词，需要按相关度排序
     *
     * 2. filter：必须匹配，但不参与评分
     *    - filter条件不影响文档的_score
     *    - ES会缓存filter结果（query cache），性能更高
     *    - 场景：精确过滤条件，如typeId=1、价格范围、商圈
     *
     * 3. should：应该匹配（可选），参与评分
     *    - 不必须满足，但满足会增加分数
     *    - 如果没有must/filter，至少要满足一个should
     *
     * 4. must_not：必须不匹配，不参与评分
     *    - 排除某些条件
     *
     * 为什么typeId用filter而不用must？
     *    - typeId是精确匹配，不需要相关度评分
     *    - filter不计算score，性能更高
     *    - filter结果会被ES缓存
     *
     * 【八股：multi_match多字段查询】
     *
     * multi_match允许一个关键词同时在多个字段中搜索：
     *   multi_match {
     *     query: "牛排"
     *     fields: ["name", "area", "address", "tags"]
     *   }
     *
     * ES会将查询词分词，然后在每个字段中匹配，取最高分。
     * 可以通过^符号加权：["name^3", "area^1"]，name的匹配权重是area的3倍
     *
     * multi_match的几种类型（type参数）：
     *   - best_fields（默认）：取所有字段中得分最高的，适合"短词在多字段中搜"
     *   - most_fields：所有字段得分相加，适合"多字段都包含该词更好"
     *   - cross_fields：把多个字段当一个大字段搜索，适合"人名拆分搜"
     *   - phrase：短语匹配，每个字段分别做phrase匹配
     *   - phrase_prefix：短语前缀匹配
     *
     * 【八股：高亮（Highlight）原理】
     *
     * 高亮就是在搜索结果中把匹配的关键词用特殊标签包裹，方便前端加粗显示。
     *
     * 工作原理：
     *   1. ES执行查询，找到匹配的文档
     *   2. 对指定字段，重新分析文本，找到匹配词的位置
     *   3. 在匹配词前后插入preTags和postTags
     *   4. 返回highlight字段，与原始source分开
     *
     * 示例：
     *   原始name: "好吃的牛排餐厅"
     *   搜索词: "牛排"
     *   高亮后: "好吃的<em>牛排</em>餐厅"
     *
     * 注意：高亮会增加ES的CPU开销，因为需要重新分析每个字段。
     * 如果不需要高亮，不要配置highlight_builder。
     *
     * 【八股：ES分页的深分页问题】
     *
     * ES分页有两种方式：
     *
     * 1. from + size（浅分页）
     *    - from = (current - 1) * size，表示跳过前多少条
     *    - size = 每页条数
     *    - 问题：from + size 不能超过 10000（index.max_result_window默认值）
     *    - 原因：ES是分布式存储，数据分布在多个分片（shard）
     *      假设要查第1000页（from=9990, size=10）：
     *      - 每个分片要取前10000条数据（9990+10）返回给协调节点
     *      - 如果有5个分片，协调节点要处理50000条数据
     *      - 排序后只取10条，其余49990条全浪费了
     *      - 分片数越多、页数越深，浪费越严重
     *
     * 2. scroll（游标分页/深分页）
     *    - 第一次查询时ES生成一个游标（scroll_id）
     *    - 后续查询带着scroll_id，ES从上次位置继续取
     *    - 适合大数据量导出，不适合实时搜索（数据不是最新的）
     *
     * 3. search_after（推荐）
     *    - 类似MySQL的游标分页，用上一页最后一条的排序值作为游标
     *    - 无状态，高性能，适合实时深分页
     *    - 要求排序字段唯一（通常加_id排序保证唯一性）
     *
     * 本项目使用from + size分页，适用于浅分页场景（前几页）。
     */
    @Override
    @CircuitBreaker(failureThreshold = 5, recoveryTimeout = 30000, slidingWindow = 60000,
            fallback = "searchFallback")
    public Result search(String keyword, Long typeId, String area, Integer current, Integer size) {
        // 1.参数校验与默认值处理
        if (current == null || current < 1) {
            current = 1;
        }
        if (size == null || size < 1) {
            size = 10;
        }

        // 【八股：深分页保护】
        // from + size 不能超过 10000，否则ES会报错
        int from = (current - 1) * size;
        if (from + size > 10000) {
            return Result.fail("分页深度超过限制，from + size 不能超过10000，请使用search_after方式");
        }

        // 2.构建bool查询
        BoolQueryBuilder boolQuery = QueryBuilders.boolQuery();

        // 2.1 must：多字段全文搜索（参与评分，按相关度排序）
        if (StrUtil.isNotBlank(keyword)) {
            // multi_match：在name、area、address、tags四个字段中搜索关键词
            // 字段加权：name权重最高（用户搜"海底捞"应优先返回店名匹配），tags/area次之
            // 【重要】四字段 mapping.search_analyzer 已统一配置为 shop_search_synonym（ik_smart + 同义词扩展）
            //   例：用户搜"日料"会自动扩展为 "日料 OR 日本料理 OR 日式 OR 寿司 OR 刺身 OR 居酒屋"
            //   因此这里无需在 multiMatchQuery 中再显式指定 analyzer
            boolQuery.must(QueryBuilders.multiMatchQuery(keyword,
                    "name^3", "tags^2", "area^1.5", "address")
                    .type("most_fields"));
        } else {
            // 关键词为空时匹配所有文档
            boolQuery.must(QueryBuilders.matchAllQuery());
        }

        // 2.2 filter：类型过滤（不参与评分，但会过滤结果，性能更好且会被缓存）
        if (typeId != null) {
            // typeId是keyword类型，用termQuery精确匹配
            boolQuery.filter(QueryBuilders.termQuery("typeId", typeId));
        }

        // 2.3 filter：商圈过滤
        if (StrUtil.isNotBlank(area)) {
            // area是text类型，用matchQuery分词后匹配
            boolQuery.filter(QueryBuilders.matchQuery("area", area));
        }

        // 3.构建高亮：匹配的关键词用<em>标签包裹
        HighlightBuilder highlightBuilder = new HighlightBuilder();
        highlightBuilder.field("name");
        highlightBuilder.field("tags");
        highlightBuilder.preTags("<em>");
        highlightBuilder.postTags("</em>");
        // 不需要将字段与原始内容分开的标记
        highlightBuilder.requireFieldMatch(false);

        // 4.构建NativeSearchQuery
        NativeSearchQuery query = new NativeSearchQueryBuilder()
                .withQuery(boolQuery)
                .withPageable(PageRequest.of(current - 1, size))
                // 排序：先按评分降序，再按销量降序
                .withSort(SortBuilders.fieldSort("score").order(SortOrder.DESC))
                .withSort(SortBuilders.fieldSort("sold").order(SortOrder.DESC))
                .withHighlightBuilder(highlightBuilder)
                .build();

        // 5.执行查询，记录耗时
        long startTime = System.currentTimeMillis();
        SearchHits<ShopDoc> searchHits = elasticsearchRestTemplate.search(query, ShopDoc.class);
        long took = System.currentTimeMillis() - startTime;

        // 6.解析搜索结果
        List<ShopDoc> shopDocList = new ArrayList<>();
        for (SearchHit<ShopDoc> hit : searchHits.getSearchHits()) {
            ShopDoc shopDoc = hit.getContent();
            // 应用高亮：将高亮后的文本替换原始字段值
            Map<String, List<String>> highlightFields = hit.getHighlightFields();
            if (highlightFields != null) {
                // 如果name字段有高亮，替换为高亮后的文本
                List<String> nameHighlights = highlightFields.get("name");
                if (nameHighlights != null && !nameHighlights.isEmpty()) {
                    shopDoc.setName(nameHighlights.get(0));
                }
                // 如果tags字段有高亮，替换为高亮后的文本
                List<String> tagsHighlights = highlightFields.get("tags");
                if (tagsHighlights != null && !tagsHighlights.isEmpty()) {
                    shopDoc.setTags(tagsHighlights.get(0));
                }
            }
            shopDocList.add(shopDoc);
        }

        // 7.封装返回结果
        ShopSearchResult result = new ShopSearchResult();
        result.setList(shopDocList);
        result.setTotal(searchHits.getTotalHits());
        result.setTook(took);
        result.setCurrent(current);
        result.setSize(size);

        return Result.ok(result);
    }

    /**
     * ES 搜索熔断降级方法 —— MySQL LIKE 查询
     *
     * 【八股：熔断降级的 fallback 设计原则】
     * 1. 降级方法必须与原方法签名完全一致（参数列表、返回类型）
     * 2. 降级逻辑应尽量轻量，避免再次触发熔断
     * 3. 降级返回的数据可以是"次优"的，但不能是"错误"的
     * 4. 降级方法中不应该再调用可能失败的外部服务
     *
     * 【八股：MySQL LIKE vs ES 全文搜索的性能差异】
     * - MySQL LIKE '%keyword%'：全表扫描，O(n)，无法利用索引
     * - ES 倒排索引：直接定位文档，接近 O(1)
     * - 数据量小时（<1万条）MySQL LIKE 也能接受
     * - 数据量大时（>10万条）必须用 ES，否则响应时间秒级
     *
     * 降级场景：ES 不可用时（OOM、节点宕机、网络超时），
     * 用 MySQL LIKE 兜底保证搜索功能可用，虽然慢但有结果。
     */
    private Result searchFallback(String keyword, Long typeId, String area,
                                   Integer current, Integer size) {
        // 1. 参数校验
        if (current == null || current < 1) current = 1;
        if (size == null || size < 1) size = 10;

        log.warn("ES 搜索熔断降级，使用 MySQL LIKE 查询: keyword={}, typeId={}, area={}",
                keyword, typeId, area);

        long startTime = System.currentTimeMillis();

        // 2. 构建 MySQL 查询条件（MyBatis-Plus LambdaQueryWrapper）
        LambdaQueryWrapper<Shop> wrapper = new LambdaQueryWrapper<>();

        // 关键词搜索：在 name、area、address 中 LIKE 匹配（等价于 ES 的 multi_match）
        if (StrUtil.isNotBlank(keyword)) {
            wrapper.and(w -> w.like(Shop::getName, keyword)
                    .or().like(Shop::getArea, keyword)
                    .or().like(Shop::getAddress, keyword));
        }

        // 类型过滤（等价于 ES 的 filter termQuery）
        if (typeId != null) {
            wrapper.eq(Shop::getTypeId, typeId);
        }

        // 商圈过滤
        if (StrUtil.isNotBlank(area)) {
            wrapper.like(Shop::getArea, area);
        }

        // 排序：先按评分降序，再按销量降序（等价于 ES 的 fieldSort）
        wrapper.orderByDesc(Shop::getScore);
        wrapper.orderByDesc(Shop::getSold);

        // 3. 分页查询 MySQL
        Page<Shop> page = new Page<>(current, size);
        Page<Shop> shopPage = shopService.page(page, wrapper);

        // 4. 转换为 ShopDoc（复用已有的转换方法）
        List<ShopDoc> shopDocList = new ArrayList<>();
        for (Shop shop : shopPage.getRecords()) {
            shopDocList.add(convertToShopDoc(shop));
        }

        long took = System.currentTimeMillis() - startTime;

        // 5. 封装返回结果
        ShopSearchResult result = new ShopSearchResult();
        result.setList(shopDocList);
        result.setTotal(shopPage.getTotal());
        result.setTook(took);
        result.setCurrent(current);
        result.setSize(size);

        log.info("MySQL 降级查询完成: total={}, took={}ms", shopPage.getTotal(), took);
        return Result.ok(result);
    }

    /**
     * 全量同步MySQL商铺数据到ES
     *
     * 【八股：MySQL到ES的数据同步方案】
     *
     * 1. 全量同步（本方法采用）
     *    - 从MySQL查出所有数据，批量写入ES
     *    - 优点：实现简单，数据完整
     *    - 缺点：同步慢，不适合频繁执行，同步期间ES数据不完整
     *    - 适用：初始化建索引、数据修复
     *
     * 2. 增量同步（推荐生产使用）
     *    - 只同步变化的数据
     *    - 实现方式1：双写 —— 修改MySQL时同时修改ES（代码侵入大）
     *    - 实现方式2：Binlog监听 —— 用Canal监听MySQL Binlog，解析后写入ES（解耦，推荐）
     *    - 实现方式3：消息队列 —— MySQL修改后发MQ消息，消费者写ES（异步解耦）
     *    - 实现方式4：定时任务 —— 定时扫描update_time变化的记录同步（有延迟）
     *
     * 3. 本方法：全量同步，简单直接
     *    - shopService.list() 查出所有商铺
     *    - 转换为ShopDoc
     *    - shopDocRepository.saveAll() 批量写入ES
     */
    @Override
    public Result syncShopToEs() {
        // 1.从MySQL查询所有商铺数据
        List<Shop> shops = shopService.list();
        if (shops == null || shops.isEmpty()) {
            return Result.fail("MySQL中没有商铺数据");
        }

        // 2.将Shop实体转换为ShopDoc文档
        List<ShopDoc> shopDocs = new ArrayList<>(shops.size());
        for (Shop shop : shops) {
            ShopDoc shopDoc = convertToShopDoc(shop);
            shopDocs.add(shopDoc);
        }

        // 3.批量保存到ES
        // saveAll底层会使用ES的bulk API批量写入，比逐条save性能高很多
        shopDocRepository.saveAll(shopDocs);

        return Result.ok("成功同步 " + shopDocs.size() + " 条商铺数据到ES");
    }

    /**
     * 单个商铺导入ES
     *
     * 用于商铺新增或修改时，实时同步单条数据到ES。
     * save底层调用ES的index API（PUT /shop/_doc/{id}）
     */
    @Override
    public Result importShop(Shop shop) {
        if (shop == null || shop.getId() == null) {
            return Result.fail("商铺数据或ID不能为空");
        }
        // 转换并保存
        ShopDoc shopDoc = convertToShopDoc(shop);
        shopDocRepository.save(shopDoc);
        return Result.ok("商铺[" + shop.getName() + "]已导入ES");
    }

    /**
     * Shop实体转ShopDoc文档
     *
     * 【八股：为什么要做对象转换？】
     * Shop是MySQL表映射实体，ShopDoc是ES文档映射。
     * 两者字段大部分相同，但ShopDoc多了tags字段（用于搜索）。
     * 不能直接用Shop存ES，因为：
     * 1. Shop有createTime/updateTime等MySQL专有字段，ES不需要
     * 2. ShopDoc的tags字段在Shop中不存在，需要额外填充
     * 3. 分离实体让数据源职责清晰
     */
    private ShopDoc convertToShopDoc(Shop shop) {
        ShopDoc shopDoc = new ShopDoc();
        // 使用hutool的BeanUtil复制同名字段
        BeanUtil.copyProperties(shop, shopDoc);
        // tags字段Shop中没有，用area填充作为搜索标签
        // 实际项目中tags可来自商铺自选标签、分类名称等
        if (StrUtil.isNotBlank(shop.getArea())) {
            shopDoc.setTags(shop.getArea());
        }
        return shopDoc;
    }
}
