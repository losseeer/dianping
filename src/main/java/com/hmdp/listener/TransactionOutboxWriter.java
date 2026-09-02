package com.hmdp.listener;

import cn.hutool.json.JSONUtil;
import com.hmdp.entity.TransactionOutbox;
import com.hmdp.mapper.TransactionOutboxMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Component;

import javax.annotation.Resource;
import java.time.LocalDateTime;
import java.util.Map;

/**
 * 本地事件表(Outbox)统一写入入口。
 *
 * 业务事务内调用 {@link #save}（必须在事务中，保证与业务变更同库同事务原子提交），
 * 真正的投递由 {@link TransactionOutboxPublisher} 定时扫表完成。
 * 之前 VoucherOrderServiceImpl / PaymentServiceImpl 各自内联了一份相同的构造+插入逻辑，收敛到这里。
 */
@Slf4j
@Component
public class TransactionOutboxWriter {

    @Resource
    private TransactionOutboxMapper outboxMapper;

    /**
     * @param eventKey 幂等键（唯一索引），重复写入静默忽略
     */
    public void save(String eventKey, String eventType, Long aggregateId, Map<String, Object> payload) {
        TransactionOutbox event = new TransactionOutbox();
        event.setEventKey(eventKey);
        event.setEventType(eventType);
        event.setAggregateId(aggregateId);
        event.setPayload(JSONUtil.toJsonStr(payload));
        event.setStatus(0);
        event.setRetryCount(0);
        event.setNextRetryTime(LocalDateTime.now());
        event.setCreateTime(LocalDateTime.now());
        event.setUpdateTime(LocalDateTime.now());
        try {
            outboxMapper.insert(event);
        } catch (DuplicateKeyException duplicate) {
            log.debug("Outbox事件已存在，忽略重复写入: eventKey={}", eventKey);
        }
    }
}
