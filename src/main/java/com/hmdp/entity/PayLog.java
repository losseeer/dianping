package com.hmdp.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.experimental.Accessors;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 支付流水实体 —— 记录每一笔支付的详细信息
 *
 * 【八股：为什么需要独立的支付流水表？】
 * 1. 一个订单可能多次支付尝试（第一次失败，第二次成功）
 * 2. 支付和订单是两个独立的领域，职责分离
 * 3. 对账需要：支付平台返回的流水号和本地流水要对得上
 * 4. 退款也需要记录退款流水
 */
@Data
@EqualsAndHashCode(callSuper = false)
@Accessors(chain = true)
@TableName("tb_pay_log")
public class PayLog implements Serializable {

    private static final long serialVersionUID = 1L;

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    /**
     * 交易订单号（业务订单号）
     */
    private Long orderId;

    /**
     * 用户id
     */
    private Long userId;

    /**
     * 支付方式 1余额 2支付宝 3微信
     */
    private Integer payType;

    /**
     * 第三方支付流水号（支付宝/微信返回的）
     */
    private String tradeNo;

    /**
     * 支付金额（分）
     */
    private Long amount;

    /**
     * 支付状态 1待支付 2成功 3失败 4已退款
     */
    private Integer status;

    /** 1 means this is the pending payment attempt for the order; terminal rows use null. */
    private Integer pendingFlag;

    /**
     * 创建时间
     */
    private LocalDateTime createTime;

    /**
     * 支付完成时间
     */
    private LocalDateTime payTime;

    /**
     * 退款时间
     */
    private LocalDateTime refundTime;
}
