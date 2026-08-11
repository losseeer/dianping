package com.hmdp.service;

import com.hmdp.dto.Result;
import com.hmdp.entity.Shop;

/**
 * 商铺ES全文搜索服务 —— 【八股：为什么需要搜索引擎服务层？】
 *
 * 【八股：ES搜索为什么单独抽服务层？】
 * 1. 职责分离：ES搜索逻辑与MySQL CRUD逻辑分离，符合单一职责原则
 * 2. 可替换性：如果将来换成Solr或其他搜索引擎，只需替换实现类
 * 3. 可测试性：接口定义清晰，方便Mock测试
 *
 * 【八股：ES与MySQL的职责分工】
 * - MySQL：负责事务性写入、精确查询（按ID查、按外键查）
 * - ES：负责全文搜索、复杂条件查询、相关度排序
 * - 两者通过数据同步保持一致（本项目采用全量同步 + 单条导入方式）
 */
public interface IShopSearchService {

    /**
     * 全文搜索商铺
     *
     * @param keyword 搜索关键词（匹配商铺名称、商圈、地址、标签）
     * @param typeId  商铺类型ID（可选过滤条件）
     * @param area    商圈名称（可选过滤条件）
     * @param current 当前页码（从1开始）
     * @param size    每页条数
     * @return 搜索结果，包含高亮后的商铺列表、总数、耗时等
     */
    Result search(String keyword, Long typeId, String area, Integer current, Integer size);

    /**
     * 全量同步MySQL商铺数据到ES
     *
     * 【八股：全量同步 vs 增量同步】
     * - 全量同步：把MySQL所有数据重新导入ES，适用于初始化或数据修复
     * - 增量同步：只同步变化的数据，通过MySQL Binlog或消息队列实现
     * - 本方法采用全量同步，简单直接，适合数据量不大的场景
     *
     * @return 导入的商铺数量
     */
    Result syncShopToEs();

    /**
     * 单个商铺导入ES
     *
     * @param shop 商铺实体
     * @return 导入结果
     */
    Result importShop(Shop shop);

    /**
     * 重建 ES shop 索引（DROP + CREATE + PUT MAPPING + 重新 MySQL 全量导入）。
     *
     * 【应用场景】
     * 1. 修改 synonyms.txt（同义词表）后需要让 synonym_graph filter 立即生效
     * 2. 调整 analyzer / filter / mapping 后需要重建索引
     * 3. ES 索引数据损坏或 mapping 写入失败，需要一键修复
     *
     * 与 elasticsearch.init.rebuild-on-startup=true 的区别：
     *   · rebuild-on-startup=true 在 Spring Boot 启动时执行一次
     *   · 本方法可以在服务运行期间随时调用（无需重启），方便运维与同义词热更新
     *
     * @return 重建结果（包含导入的商铺数量、是否成功等）
     */
    Result rebuildIndex();
}
