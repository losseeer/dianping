package com.hmdp.config;

import cn.hutool.core.io.IoUtil;
import cn.hutool.core.io.resource.ClassPathResource;
import cn.hutool.core.util.StrUtil;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.hmdp.document.ShopDoc;
import com.hmdp.dto.Result;
import com.hmdp.dto.ShopSearchResult;
import com.hmdp.entity.Shop;
import com.hmdp.repository.ShopDocRepository;
import com.hmdp.service.IShopSearchService;
import com.hmdp.service.IShopService;
import lombok.extern.slf4j.Slf4j;
import org.elasticsearch.action.admin.indices.alias.IndicesAliasesRequest;
import org.elasticsearch.action.admin.indices.create.CreateIndexRequest;
import org.elasticsearch.action.admin.indices.delete.DeleteIndexRequest;
import org.elasticsearch.action.support.master.AcknowledgedResponse;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.RequestOptions;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.RestHighLevelClient;
import org.elasticsearch.client.indices.GetIndexRequest;
import org.elasticsearch.common.settings.Settings;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.elasticsearch.core.ElasticsearchRestTemplate;

import javax.annotation.Resource;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.stream.Collectors;

/**
 * Elasticsearch 索引初始化配置
 *
 * 做三件事：
 *  1. 读取 classpath:synonyms.txt，构造 synonym_graph filter（14 组同义词，search_analyzer 侧扩展）
 *  2. 启动时按 elasticsearch.init.rebuild-on-startup 开关决定是否 DROP + 重建 shop 索引 settings/mappings
 *  3. 重建后从 MySQL tb_shop 全量导入数据（单节点，数据量≈百~千级，可接受）
 *
 *  为什么必须手动建 settings/mappings？
 *    Spring Data Elasticsearch 4.0.x（Spring Boot 2.3.x 对应版本）的 @Document + @Field(analyzer="X")
 *    只负责"告诉框架 mapping 是什么"，但不会把 X 这个 analyzer 的定义（filter/tokenizer）写进 index settings。
 *    也就是说——如果只写 @Field(analyzer="shop_index_ik") 而没有手动写 settings，
 *    在 ES 里第一次 saveAll() 时 Spring Data 会自动建索引，但 analyzer 找不到 → 要么报错，
 *    要么 fallback 到 standard（同义词根本不生效）。所以这里必须手动创建 settings 包含完整
 *    shop_synonyms（synonym_graph） + shop_index_ik（ik_max_word） + shop_search_synonym（ik_smart+同义词）
 *    这三个分析链定义，然后 putMapping。
 */
@Slf4j
@Configuration
public class ElasticsearchConfiguration implements ApplicationRunner {

    /**
     * Spring Boot 2.3.x starter 自动装配的 ES HTTP 客户端
     * — 底层基于 elasticsearch.rest.uris（application.yaml 已配 http://127.0.0.1:9200）
     */
    @Resource
    private RestHighLevelClient client;

    @Resource
    private ElasticsearchRestTemplate elasticsearchRestTemplate;

    @Resource
    private IShopService shopService;

    @Resource
    private ShopDocRepository shopDocRepository;

    @Resource
    private IShopSearchService shopSearchService;

    /**
     * 是否在启动时强制重建索引（DROP + CREATE + PUT MAPPING + 重新 MySQL 导入）。
     * 默认 false，只在索引不存在时创建；修改同义词后改为 true 触发一次即可，或调管理接口。
     */
    @Value("${elasticsearch.init.rebuild-on-startup:false}")
    private boolean rebuildOnStartup;

    /**
     * number_of_shards / replicas — 单节点默认 1 分片 0 副本（集群 RED 时也能跑）
     */
    @Value("${elasticsearch.init.shards:1}")
    private int shards;

    @Value("${elasticsearch.init.replicas:0}")
    private int replicas;

    /**
     * 索引 settings：
     * - filter.shop_synonyms  = synonym_graph，同义词从 classpath:synonyms.txt 读
     * - analyzer.shop_index_ik     = ik_max_word + lowercase（索引侧：细粒度分词，最大化召回）
     * - analyzer.shop_search_synonym = ik_smart + lowercase + shop_synonyms（搜索侧：粗分词 + 同义词展开）
     *
     * 同义词放「搜索侧」而不是「索引侧」的好处：
     *   修改 synonyms.txt 后，不需要 reindex 全部文档（不需要改倒排表），
     *   只需要重建 index settings（PUT _settings，close index → update settings → open index 即可），
     *   同义词立即生效。如果放在索引侧（analyzer 侧），就得 full reindex，成本高得多。
     */
    private Settings buildIndexSettings() throws IOException {
        List<String> synLines = loadSynonyms();
        Settings.Builder builder = Settings.builder()
                .put("number_of_shards", shards)
                .put("number_of_replicas", replicas)
                // --- filter.shop_synonyms = synonym_graph (同义词 graph filter，搜索侧扩展)
                .put("analysis.filter.shop_synonyms.type", "synonym_graph")
                .put("analysis.filter.shop_synonyms.expand", true)
                .put("analysis.filter.shop_synonyms.lenient", true)
                .putList("analysis.filter.shop_synonyms.synonyms", synLines)
                // --- analyzer.shop_index_ik = ik_max_word + lowercase（索引侧，细粒度分词 + 大小写归一）
                .put("analysis.analyzer.shop_index_ik.type", "custom")
                .put("analysis.analyzer.shop_index_ik.tokenizer", "ik_max_word")
                .putList("analysis.analyzer.shop_index_ik.filter", "lowercase")
                // --- analyzer.shop_search_synonym = ik_smart + lowercase + shop_synonyms（搜索侧：粗分词 + 同义词图扩展）
                .put("analysis.analyzer.shop_search_synonym.type", "custom")
                .put("analysis.analyzer.shop_search_synonym.tokenizer", "ik_smart")
                .putList("analysis.analyzer.shop_search_synonym.filter", "lowercase", "shop_synonyms");
        return builder.build();
    }

    /**
     * 读取 classpath:synonyms.txt，跳过空行和 # 注释行
     */
    private List<String> loadSynonyms() throws IOException {
        ClassPathResource r = new ClassPathResource("synonyms.txt");
        try (InputStream in = r.getStream()) {
            String content = IoUtil.read(in, StandardCharsets.UTF_8);
            return Arrays.stream(content.split("\\r?\\n"))
                    .map(String::trim)
                    .filter(StrUtil::isNotBlank)
                    .filter(line -> !line.startsWith("#"))
                    .collect(Collectors.toList());
        }
    }

    /**
     * Mapping：严格对应 ShopDoc 字段。
     * name / tags / area / address — Text + analyzer=shop_index_ik + search_analyzer=shop_search_synonym
     * 其他字段与 ShopDoc 注解一致（@Keyword / Long / Integer / Double）
     */
    private String buildMappingJson() throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        java.util.Map<String, Object> props = new java.util.LinkedHashMap<>();

        props.put("id", typed("long"));
        props.put("name", textWithSynonym());
        props.put("typeId", typed("keyword"));
        props.put("images", indexed("keyword", false));
        props.put("area", textWithSynonym());
        props.put("address", textWithSynonym());
        props.put("x", typed("double"));
        props.put("y", typed("double"));
        props.put("avgPrice", typed("long"));
        props.put("sold", typed("integer"));
        props.put("comments", typed("integer"));
        props.put("score", typed("integer"));
        props.put("openHours", indexed("keyword", false));
        props.put("tags", textWithSynonym());

        java.util.Map<String, Object> mapping = new java.util.LinkedHashMap<>();
        mapping.put("properties", props);
        return mapper.writeValueAsString(mapping);
    }

    private java.util.Map<String, Object> typed(String t) {
        java.util.Map<String, Object> m = new java.util.LinkedHashMap<>();
        m.put("type", t);
        return m;
    }

    private java.util.Map<String, Object> indexed(String t, boolean idx) {
        java.util.Map<String, Object> m = typed(t);
        m.put("index", idx);
        return m;
    }

    private java.util.Map<String, Object> textWithSynonym() {
        java.util.Map<String, Object> m = new java.util.LinkedHashMap<>();
        m.put("type", "text");
        m.put("analyzer", "shop_index_ik");
        m.put("search_analyzer", "shop_search_synonym");
        return m;
    }

    /**
     * 重建索引主流程（可由 ApplicationRunner.run() 启动时调用，或通过 rebuildIndex 管理接口在运行期调用）。
     * 步骤：DROP（若存在）→ CREATE(settings 含 synonym_graph + IK 双 analyzer) → PUT MAPPING → MySQL 全量导入。
     *
     * @param force 若 false 且索引已存在 → 跳过；若 true → 不管索引存不存在都 DROP 重建。
     *              rebuild-on-startup=false → force=false（只在索引不存在时创建）
     *              rebuild-on-startup=true  或 手动调用 rebuildIndex 接口 → force=true
     * @return 本次重建的摘要信息（是否实际执行、导入条数等），供 Result 包装返回。
     */
    public java.util.Map<String, Object> rebuildIndexInternal(boolean force) throws Exception {
        java.util.Map<String, Object> summary = new java.util.LinkedHashMap<>();
        boolean exists = client.indices().exists(new GetIndexRequest("shop"), RequestOptions.DEFAULT);
        summary.put("indexExistedBefore", exists);

        if (exists && !force && hasShopMapping()) {
            summary.put("skipped", true);
            summary.put("reason", "索引已存在且 force=false，跳过重建。如需强制重建，请调用 POST /shop/search/rebuild-index 或将 elasticsearch.init.rebuild-on-startup=true 后重启。");
            warmUpCircuitBreaker();
            return summary;
        }

        if (exists && !force) {
            log.warn("[ES] shop 索引已存在但 mapping 为空，补写 typeless mapping 并重新导入数据。");
        }

        if (exists && force) {
            log.warn("[ES] rebuildIndexInternal(force=true) → 删除现有 shop 索引（包含所有已有文档）…");
            AcknowledgedResponse del = client.indices().delete(new DeleteIndexRequest("shop"), RequestOptions.DEFAULT);
            if (!del.isAcknowledged()) {
                throw new IllegalStateException("删除 shop 索引失败（未 ACK）");
            }
            log.info("[ES] 删除完成。");
            summary.put("dropped", true);
            exists = false;
        }

        Settings settings = buildIndexSettings();
        String mapping = buildMappingJson();

        if (!exists) {
            CreateIndexRequest createReq = new CreateIndexRequest("shop");
            createReq.settings(settings);
            AcknowledgedResponse cr = client.indices().create(createReq, RequestOptions.DEFAULT);
            if (!cr.isAcknowledged()) throw new IllegalStateException("创建 shop 索引失败（未 ACK）");
            log.info("[ES] 创建 shop 索引成功，开始写入 mapping（含同义词 graph + IK 双 analyzer）…");
            summary.put("created", true);
        }

        // The Boot 2.3 bundled high-level client validates the removed mapping
        // type locally. Send the typeless ES 7 request through its low-level API.
        Request mappingRequest = new Request("PUT", "/shop/_mapping");
        mappingRequest.setJsonEntity(mapping);
        Response mappingResponse = client.getLowLevelClient().performRequest(mappingRequest);
        int mappingStatus = mappingResponse.getStatusLine().getStatusCode();
        if (mappingStatus < 200 || mappingStatus >= 300) {
            throw new IllegalStateException("写入 mapping 失败，HTTP status=" + mappingStatus);
        }
        log.info("[ES] mapping 写入成功。开始从 MySQL 导入 tb_shop 全量数据…");
        summary.put("mappingApplied", true);

        int imported = importAllShops();
        summary.put("importedShops", imported);
        warmUpCircuitBreaker();
        summary.put("circuitBreakerWarmed", true);
        return summary;
    }

    /**
     * 判断已有索引是否已经写入字段 mapping。旧版本客户端可能在 put mapping
     * 本地校验阶段失败，留下 settings 已创建但 mappings 为空的索引。
     */
    private boolean hasShopMapping() throws IOException {
        Response response = client.getLowLevelClient().performRequest(new Request("GET", "/shop/_mapping"));
        try (InputStream in = response.getEntity().getContent()) {
            com.fasterxml.jackson.databind.JsonNode root = new ObjectMapper().readTree(in);
            com.fasterxml.jackson.databind.JsonNode properties = root.path("shop")
                    .path("mappings").path("properties");
            return properties.isObject() && properties.size() > 0;
        }
    }

    /**
     * Spring Boot 启动完成后执行一次。
     * 执行策略：
     *   · 若 shop 索引不存在 → create settings + put mapping + import
     *   · 若索引已存在 且 rebuildOnStartup=true → DROP → create + put mapping + import
     *   · 若索引已存在 且 rebuildOnStartup=false → 仅打印日志，跳过（避免误删数据）
     */
    @Override
    public void run(ApplicationArguments args) {
        try {
            java.util.Map<String, Object> s = rebuildIndexInternal(rebuildOnStartup);
            if (Boolean.TRUE.equals(s.get("skipped"))) {
                log.info("[ES] shop 索引已存在，rebuild-on-startup=false，跳过初始化。如需重建同义词，改 application.yaml: elasticsearch.init.rebuild-on-startup=true 后重启一次，或调 POST /shop/search/rebuild-index 管理接口。");
                return;
            }
            log.info("[ES] 初始化完成：importedShops={}, mappingApplied={}", s.get("importedShops"), s.get("mappingApplied"));
        } catch (Exception e) {
            // 初始化失败但不阻断启动（会通过 @CircuitBreaker fallback 到 MySQL LIKE，对用户透明）
            log.error("[ES] 初始化失败。本次启动将通过 searchFallback（MySQL LIKE 多字段）降级提供搜索。详情：{}", e.getMessage(), e);
        }
    }

    /**
     * 全量导入 tb_shop → shop 索引。
     * 使用 IShopService.list() 一次拿全（本项目数据量 < 1000，可接受；
     * 若未来扩到万级，可改成分页，一次 pageSize=1000）。
     *
     * @return 实际写入 ES 的商铺数量（MySQL 为空返回 0）
     */
    private int importAllShops() {
        List<Shop> all = shopService.list();
        if (all == null || all.isEmpty()) {
            log.warn("[ES] MySQL tb_shop 为空，跳过导入。");
            return 0;
        }
        List<ShopDoc> docs = new ArrayList<>(all.size());
        for (Shop s : all) {
            ShopDoc d = new ShopDoc();
            d.setId(s.getId());
            d.setName(s.getName());
            d.setTypeId(s.getTypeId());
            d.setImages(s.getImages());
            d.setArea(s.getArea());
            d.setAddress(s.getAddress());
            d.setX(s.getX());
            d.setY(s.getY());
            d.setAvgPrice(s.getAvgPrice());
            d.setSold(s.getSold());
            d.setComments(s.getComments());
            d.setScore(s.getScore() != null ? Math.round(s.getScore() * 10) : null); // 乘10存
            d.setOpenHours(s.getOpenHours());
            // 【注意】MySQL tb_shop 实体没有 tags 字段。与 ShopSearchServiceImpl.convertToShopDoc 保持一致：
            // 用 area 兜底作为 ES tags，让同义词扩展（如日料→寿司/居酒屋）能在 tags 侧也命中。
            d.setTags(s.getArea());
            docs.add(d);
        }
        shopDocRepository.saveAll(docs);
        log.info("[ES] MySQL → ES 导入完成：{} 条商铺。", docs.size());
        return docs.size();
    }

    /**
     * 热一下 @CircuitBreaker 熔断器状态：
     * 手动调一次带空 keyword 的搜索（内部会走 ES 分支），让熔断器滑动窗口记录一次 success，
     * 避免首次真实请求遇到熔断器初始化相关的问题。
     */
    private void warmUpCircuitBreaker() {
        try {
            Result r = shopSearchService.search("杭州", null, null, 1, 1);
            Object data = r.getData();
            long total = data instanceof ShopSearchResult
                    ? ((ShopSearchResult) data).getTotal() : 0L;
            log.info("[ES] 熔断器预热：搜索 keyword=杭州 命中 {} 条（OK）。", total);
        } catch (Exception e) {
            // fallback 到 MySQL，也 OK —— 这里只是为了初始化 CircuitBreaker 内部状态机
            log.info("[ES] 熔断器预热：已通过 search 触发 CircuitBreaker 一次（即使 fallback 也正常）。");
        }
    }
}
