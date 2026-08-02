package com.hmdp.dto;

import lombok.Data;

/**
 * 支付请求DTO
 *
 * 【八股：为什么用DTO而不是直接用实体？】
 * 1. 安全性：不暴露实体的所有字段（如createTime由服务端设置）
 * 2. 灵活性：DTO可以组合多个实体的字段，也可以只包含需要的字段
 * 3. 解耦：前端传参和后端实体解耦，实体改动不影响接口
 * 4. 校验：可以在DTO上加@NotNull等校验注解
 */
@Data
public class PaymentDTO {
    /**
     * 订单id
     */
    private Long orderId;

    /**
     * 支付方式 2支付宝 3微信
     */
    private Integer payType;
}
