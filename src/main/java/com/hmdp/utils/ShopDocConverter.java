package com.hmdp.utils;

import cn.hutool.core.bean.BeanUtil;
import cn.hutool.core.util.StrUtil;
import com.hmdp.document.ShopDoc;
import com.hmdp.entity.Shop;

/**
 * Shop(MySQL) → ShopDoc(ES) 统一转换器。
 *
 * 全项目只允许这一条转换路径：全量重建（ElasticsearchConfiguration.importAllShops）
 * 与增量写入（ShopSearchServiceImpl.syncShopToEs / importShop）必须产出一致的数据，
 * 否则重建索引和增量更新后同名商铺的 score 等字段会出现两套值，搜索排序漂移。
 *
 * 注意 score 直接透传：tb_shop.score 本身就是"评分×10"的整数（见 001_core.sql 建表注释），
 * 这里不要再乘 10，前端与 agent2 均按 /10 还原展示。
 */
public final class ShopDocConverter {

    private ShopDocConverter() {
    }

    public static ShopDoc fromShop(Shop shop) {
        ShopDoc shopDoc = new ShopDoc();
        BeanUtil.copyProperties(shop, shopDoc);
        // MySQL tb_shop 实体没有 tags 字段，用 area 兜底作为 ES tags，
        // 让同义词扩展（如日料→寿司/居酒屋）能在 tags 侧也命中
        if (StrUtil.isNotBlank(shop.getArea())) {
            shopDoc.setTags(shop.getArea());
        }
        return shopDoc;
    }
}
