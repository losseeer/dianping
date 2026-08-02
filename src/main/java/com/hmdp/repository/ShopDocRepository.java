package com.hmdp.repository;

import com.hmdp.document.ShopDoc;
import org.springframework.data.elasticsearch.repository.ElasticsearchRepository;

/**
 * 商铺ES Repository —— 【八股：Spring Data Elasticsearch的Repository模式】
 *
 * 【八股：什么是Repository模式？】
 * Spring Data提供了一套统一的Repository抽象，类似于MyBatis-Plus的BaseMapper
 * 继承ElasticsearchRepository后，自动获得CRUD方法：
 * - save()：保存文档
 * - findById()：按ID查询
 * - findAll()：查询所有
 * - deleteById()：按ID删除
 *
 * 还支持方法名派生查询，比如：
 * - findByName(String name)：按name查询
 * - findByTypeIdAndArea(Long typeId, String area)：多条件查询
 *
 * 复杂查询用ElasticsearchRestTemplate + NativeSearchQuery
 */
public interface ShopDocRepository extends ElasticsearchRepository<ShopDoc, Long> {
}
