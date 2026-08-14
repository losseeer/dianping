package com.hmdp.enums;

/** Result of consuming a seckill reservation event. */
public enum OrderCreationResult {
    CREATED,
    ALREADY_PROCESSED,
    ACTIVE_ORDER_EXISTS,
    OUT_OF_STOCK
}
