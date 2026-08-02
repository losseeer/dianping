package com.hmdp.dto;

import lombok.Data;

import java.util.List;

/**
 * 商铺搜索结果DTO
 *
 * 【八股：为什么搜索结果要单独封装？】
 * 搜索结果除了数据本身，还需要：
 * - 总数：前端显示"共找到XX条结果"
 * - 耗时：用于性能监控
 * - 高亮字段：ES返回的高亮文本
 * - 分页信息
 */
@Data
public class ShopSearchResult {
    /**
     * 搜索结果列表
     */
    private List<?> list;

    /**
     * 总匹配数
     */
    private Long total;

    /**
     * 搜索耗时（毫秒）
     */
    private Long took;

    /**
     * 当前页码
     */
    private Integer current;

    /**
     * 每页大小
     */
    private Integer size;
}
