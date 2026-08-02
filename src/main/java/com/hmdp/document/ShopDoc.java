package com.hmdp.document;

import lombok.Data;
import org.springframework.data.annotation.Id;
import org.springframework.data.elasticsearch.annotations.Document;
import org.springframework.data.elasticsearch.annotations.Field;
import org.springframework.data.elasticsearch.annotations.FieldType;

import java.io.Serializable;

/**
 * 商铺ES文档 —— 【八股：ES中的Document映射】
 *
 * 【八股：ES中为什么叫"文档"（Document）？】
 * ES是面向文档的搜索引擎，每条数据就是一个JSON文档
 * 类比关系型数据库：
 *   - ES Index ≈ MySQL Database/Table
 *   - ES Document ≈ MySQL Row（行）
 *   - ES Field ≈ MySQL Column（列）
 *
 * 【八股：ik分词器的两种模式】
 * ik_smart：粗粒度分词，"好吃的牛排" → ["好吃", "的", "牛排"]
 * ik_max_word：细粒度分词，"好吃的牛排" → ["好吃", "的", "牛排", "好吃", "牛"]
 * 搜索时用ik_smart（分词少，匹配快）
 * 索引时用ik_max_word（分词多，匹配多）
 *
 * 【八股：keyword vs text类型】
 * keyword：不分词，整体匹配。用于精确匹配（如typeId、标签）
 * text：分词后匹配。用于全文搜索（如name、address）
 * 一个字段如果既要精确匹配又要全文搜索，可以用multi-field：
 *   "name": { "type": "text", "fields": { "keyword": { "type": "keyword" } } }
 */
@Data
@Document(indexName = "shop", type = "_doc")
public class ShopDoc implements Serializable {

    private static final long serialVersionUID = 1L;

    @Id
    private Long id;

    /**
     * 商铺名称 —— text类型，支持分词搜索
     * analyzer = ik_max_word：索引时分词
     * searchAnalyzer = ik_smart：搜索时分词
     */
    @Field(type = FieldType.Text, analyzer = "ik_max_word", searchAnalyzer = "ik_smart")
    private String name;

    /**
     * 商铺类型id —— keyword类型，精确匹配
     */
    @Field(type = FieldType.Keyword)
    private Long typeId;

    /**
     * 商铺图片
     */
    @Field(type = FieldType.Keyword, index = false)
    private String images;

    /**
     * 商圈 —— text类型，支持搜索"陆家嘴"
     */
    @Field(type = FieldType.Text, analyzer = "ik_max_word", searchAnalyzer = "ik_smart")
    private String area;

    /**
     * 地址 —— text类型，支持搜索"杭州西湖"
     */
    @Field(type = FieldType.Text, analyzer = "ik_max_word", searchAnalyzer = "ik_smart")
    private String address;

    /**
     * 经度
     */
    @Field(type = FieldType.Double)
    private Double x;

    /**
     * 纬度
     */
    @Field(type = FieldType.Double)
    private Double y;

    /**
     * 均价
     */
    @Field(type = FieldType.Long)
    private Long avgPrice;

    /**
     * 销量 —— 用于排序
     */
    @Field(type = FieldType.Integer)
    private Integer sold;

    /**
     * 评论数量
     */
    @Field(type = FieldType.Integer)
    private Integer comments;

    /**
     * 评分（1-50，乘10保存）
     */
    @Field(type = FieldType.Integer)
    private Integer score;

    /**
     * 营业时间
     */
    @Field(type = FieldType.Keyword, index = false)
    private String openHours;

    /**
     * 标签 —— 用于搜索"好吃""牛排"
     * 【八股：为什么tags用text？】
     * 因为用户搜索"好吃"时，要匹配到标签中包含"好吃"的商铺
     * 如果用keyword，只能精确匹配整个标签
     */
    @Field(type = FieldType.Text, analyzer = "ik_max_word", searchAnalyzer = "ik_smart")
    private String tags;
}
