package com.hmdp.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("tb_transaction_outbox")
public class TransactionOutbox {
    @TableId(type = IdType.AUTO)
    private Long id;
    private String eventKey;
    private String eventType;
    private Long aggregateId;
    private String payload;
    private Integer status;
    private Integer retryCount;
    private LocalDateTime nextRetryTime;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
