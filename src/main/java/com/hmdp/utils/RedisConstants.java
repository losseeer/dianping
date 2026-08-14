package com.hmdp.utils;

public class RedisConstants {
    public static final String LOGIN_CODE_KEY = "login:code:";
    public static final Long LOGIN_CODE_TTL = 2L;
    public static final String LOGIN_USER_KEY = "login:token:";
    public static final Long LOGIN_USER_TTL = 36000L;

    public static final Long CACHE_NULL_TTL = 2L;

    public static final Long CACHE_SHOP_TTL = 30L;
    public static final String CACHE_SHOP_KEY = "cache:shop:";

    public static final String LOCK_SHOP_KEY = "lock:shop:";
    public static final Long LOCK_SHOP_TTL = 10L;

    public static final String SECKILL_STOCK_KEY = "seckill:stock:";
    /**
     * 秒杀订单一人一单记录key前缀 —— Set结构，存储已下单的userId
     * 完整key: seckill:order:{voucherId}
     */
    public static final String SECKILL_ORDER_KEY = "seckill:order:";
    public static final String SECKILL_ORDER_STREAM_KEY = "stream.orders";
    public static final String SECKILL_ORDER_STREAM_GROUP = "g1";

    /**
     * 秒杀预订单（未完成落库的订单）缓存前缀 —— String，value=VoucherOrder JSON
     * 作用：秒杀返回后MQ异步写DB的窗口期，支付/取消/查详情/订单列表都能从此处捞到订单，
     *      避免前端立刻点"立即支付/取消订单"时出现"订单不存在"。
     * 完整key: seckill:order:pending:{orderId}
     */
    public static final String SECKILL_PENDING_ORDER_KEY = "seckill:order:pending:";
    public static final Long SECKILL_PENDING_ORDER_TTL = 10L;

    /**
     * 用户维度的未完成预订单索引 —— ZSet，value=orderId，score=createTime秒级时间戳
     * 作用："我的订单"列表先查DB，再补此索引里的 pending 订单，避免秒杀后立刻跳订单页看不到。
     * 完整key: seckill:order:pending:user:{userId}
     */
    public static final String SECKILL_PENDING_USER_KEY = "seckill:order:pending:user:";
    public static final Long SECKILL_PENDING_USER_TTL = 10L;
    public static final String BLOG_LIKED_KEY = "blog:liked:";
    public static final String FEED_KEY = "feed:";
    public static final String SHOP_GEO_KEY = "shop:geo:";
    public static final String USER_SIGN_KEY = "sign:";

    public static final String SHOP_TYPE_KEY = "shop_type:";
    public static final Long SHOP_TYPE_LONG=10L;

    // ========== 搜索与推荐模块新增常量 ==========

    /**
     * 用户点赞的商铺集合
     * 结构：Set，value=shopId
     * 用于协同过滤：快速获取某用户点过赞的所有商铺
     */
    public static final String USER_LIKED_SHOPS_KEY = "user:liked:shops:";

    /**
     * 商铺的点赞用户集合
     * 结构：Set，value=userId
     * 用于协同过滤：快速找到点赞过同一商铺的其他用户
     */
    public static final String SHOP_LIKED_USERS_KEY = "shop:liked:users:";

    /**
     * 热门商铺排行
     * 结构：ZSet，value=shopId，score=sold(销量)
     * 用于全站热门推荐
     */
    public static final String SHOP_HOT_KEY = "shop:hot:";
}
