package com.hmdp.service.impl;

import cn.hutool.json.JSONUtil;
import com.hmdp.dto.PaymentDTO;
import com.hmdp.dto.Result;
import com.hmdp.entity.PayLog;
import com.hmdp.entity.VoucherOrder;
import com.hmdp.entity.TransactionOutbox;
import com.hmdp.enums.OrderStatus;
import com.hmdp.enums.PayType;
import com.hmdp.service.IPaymentService;
import com.hmdp.service.ISeckillVoucherService;
import com.hmdp.mapper.TransactionOutboxMapper;
import com.hmdp.listener.TransactionOutboxPublisher;
import com.hmdp.utils.UserHolder;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import javax.annotation.Resource;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * 支付服务实现类 —— 交易闭环核心模块
 *
 * 【八股：支付系统的整体架构】
 *
 *   用户下单(UNPAID)
 *       │
 *       ▼
 *   发起支付 ──→ 创建PayLog(待支付)
 *       │            │
 *       ▼            │
 *   调用第三方SDK     │
 *       │            │
 *       ▼            │
 *   第三方回调 ──→ 更新PayLog(成功) + 更新订单(已支付)
 *       │
 *       ▼
 *   发送支付通知MQ
 *
 *   退款流程：
 *   PAID → refundOrder() → REFUNDING → 发送退款MQ
 *                                          │
 *                                          ▼
 *                                    handleRefund() → REFUNDED + 恢复库存
 *
 * 【八股：为什么金额用Long类型（分）而不是BigDecimal？】
 * 1. 性能：Long是基本类型，运算快；BigDecimal是对象，运算慢
 * 2. 精度：浮点数(float/double)有精度丢失问题（0.1+0.2≠0.3）
 *    用分作为单位，整数运算，没有精度问题
 * 3. 存储：Long占8字节，BigDecimal占更多空间
 * 4. 对接：微信支付/支付宝的API金额单位都是分
 * 5. 展示：前端展示时除以100转为元即可
 *
 * 【八股：依赖注入说明】
 * - VoucherOrderServiceImpl：查询/更新订单
 * - PayLogServiceImpl：管理支付流水
 * - StringRedisTemplate：恢复Redis库存、删除一人一单记录
 * - RabbitTemplate：发送支付通知和退款消息到MQ
 * - ISeckillVoucherService：退款时恢复DB库存
 */
@Slf4j
@Service
public class PaymentServiceImpl implements IPaymentService {

    @Resource
    private VoucherOrderServiceImpl voucherOrderService;

    @Resource
    private PayLogServiceImpl payLogService;

    /**
     * 秒杀券服务 —— 退款时恢复DB库存
     */
    @Resource
    private ISeckillVoucherService seckillVoucherService;

    @Resource
    @org.springframework.context.annotation.Lazy
    private IPaymentService selfProxy;

    @Resource
    private TransactionOutboxMapper outboxMapper;


    /**
     * 发起支付（模拟微信/支付宝沙箱）
     *
     * 【八股：支付流程详解】
     * 1. 查订单：确认订单存在且状态为待支付
     * 2. 查金额：从优惠券获取payValue（支付金额，单位分）
     * 3. 创建PayLog：记录支付流水（状态=待支付）
     * 4. 生成流水号：模拟第三方支付平台的交易号
     * 5. 调用SDK：模拟生成支付链接/二维码URL
     * 6. 更新payType：记录用户选择的支付方式
     *
     * 【八股：为什么PayLog要在支付前创建？】
     * 1. 记录支付意图：即使支付未完成，也能追溯用户发起过支付
     * 2. 防重复支付：一个PayLog对应一次支付尝试，避免重复扣款
     * 3. 对账依据：PayLog的tradeNo和第三方流水号一一对应
     * 4. 超时取消：可以根据PayLog的createTime判断支付是否超时
     *
     * 【八股：UUID作为第三方流水号的模拟】
     * 真实场景中，tradeNo由第三方支付平台生成并返回
     * 这里用UUID模拟，格式：550e8400-e29b-41d4-a716-446655440000
     * UUID的冲突概率极低（2^122种可能），适合做唯一标识
     */
    @Override
    @Transactional
    public Result payOrder(PaymentDTO dto) {
        Long orderId = dto.getOrderId();
        Integer payType = dto.getPayType();
        if (orderId == null || payType == null) {
            return Result.fail("支付参数不能为空");
        }
        final PayType payTypeEnum;
        try {
            payTypeEnum = PayType.of(payType);
        } catch (IllegalArgumentException e) {
            return Result.fail("不支持的支付方式");
        }

        // 1. 查订单是否存在、是否是待支付状态（先DB、再Redis pending，防止异步落库窗口"订单不存在"）
        VoucherOrder order = voucherOrderService.getOrderWithPending(orderId);
        if (order == null) {
            return Result.fail("订单不存在");
        }
        if (!UserHolder.getUser().getId().equals(order.getUserId())) {
            return Result.fail("无权支付他人订单");
        }
        // 状态机校验：只有UNPAID状态才能发起支付
        OrderStatus currentStatus = OrderStatus.of(order.getStatus());
        if (currentStatus != OrderStatus.UNPAID) {
            return Result.fail("订单状态不允许支付: " + currentStatus.getDesc());
        }

        // 1.5 如果订单还没真正落库（仍处于 pending 状态），主动立即落库一次（幂等），
        //     否则下面的 updateById(order)、以及后续支付回调里的 getById 都找不到 DB 记录。
        VoucherOrder dbOrder = voucherOrderService.getById(orderId);
        if (dbOrder == null) {
            log.info("支付时订单尚未落库，主动同步执行落库，orderId={}", orderId);
            try {
                voucherOrderService.handleVoucherOrder(order);
            } catch (Exception e) {
                log.error("主动同步落库失败，orderId={}", orderId, e);
                return Result.fail("订单创建中，请稍后再试");
            }
            dbOrder = voucherOrderService.getById(orderId);
            if (dbOrder == null) {
                return Result.fail("订单创建中，请稍后再试");
            }
            order = dbOrder;
        }
        VoucherOrder lockedOrder = voucherOrderService.getBaseMapper().selectByIdForUpdate(orderId);
        if (lockedOrder == null) {
            return Result.fail("订单不存在");
        }
        order = lockedOrder;
        if (!Integer.valueOf(OrderStatus.UNPAID.getCode()).equals(order.getStatus())) {
            return Result.fail("订单状态不允许支付: " + OrderStatus.of(order.getStatus()).getDesc());
        }

        // 2. 使用下单时快照金额，避免优惠券改价影响历史订单。
        Long amount = order.getAmount();
        if (amount == null || amount <= 0) {
            return Result.fail("支付金额异常");
        }

        PayLog existingPayLog = payLogService.query()
                .eq("order_id", orderId)
                .eq("status", 1)
                .orderByDesc("create_time")
                .last("LIMIT 1")
                .one();
        if (existingPayLog != null && payType.equals(existingPayLog.getPayType())) {
            return Result.ok(buildPayResult(existingPayLog));
        }
        if (existingPayLog != null) {
            return Result.fail("订单已有待支付流水，请完成或取消原支付");
        }

        // 3. 创建PayLog记录（status=1待支付）
        PayLog payLog = new PayLog();
        payLog.setOrderId(orderId);
        payLog.setUserId(order.getUserId());
        payLog.setPayType(payType);
        payLog.setAmount(amount);
        payLog.setStatus(1); // 1=待支付
        payLog.setPendingFlag(1);
        payLog.setCreateTime(LocalDateTime.now());

        // 4. 模拟生成第三方支付流水号 —— UUID
        String tradeNo = UUID.randomUUID().toString().replace("-", "");
        payLog.setTradeNo(tradeNo);

        // 保存支付流水
        payLogService.save(payLog);
        log.info("创建支付流水: orderId={}, tradeNo={}, amount={}分, payType={}",
                orderId, tradeNo, amount, PayType.of(payType).getDesc());

        // 5. 模拟调用支付SDK（这里直接返回支付链接/二维码URL）
        // 【八股：真实支付SDK的调用流程】
        // 微信支付：调用统一下单API → 返回prepay_id → 生成二维码
        // 支付宝：调用alipay.trade.precreate → 返回二维码链接
        // 这里模拟返回一个支付URL，前端展示为二维码
        String payUrl = simulatePaySdk(tradeNo, amount, payType);

        // 6. 只更新仍处于待支付状态的订单，不能用旧实体覆盖并发取消结果
        boolean payTypeSaved = voucherOrderService.lambdaUpdate()
                .set(VoucherOrder::getPayType, payType)
                .set(VoucherOrder::getUpdateTime, LocalDateTime.now())
                .eq(VoucherOrder::getId, orderId)
                .eq(VoucherOrder::getStatus, OrderStatus.UNPAID.getCode())
                .update();
        if (!payTypeSaved) {
            throw new IllegalStateException("订单状态已变化，无法发起支付");
        }

        // 7. 对 payType=BALANCE（余额支付，本项目前端默认点击"立即支付"就是余额）直接同步完成回调。
        //    【为什么需要这一步？】
        //    原流程：payOrder 只创建 PayLog(status=1) + 返回 payUrl，需要真实扫码→第三方回调→handlePayNotify
        //    才会把订单状态 UNPAID→PAID。但本地 demo 环境没有第三方扫码渠道，
        //    用户点击"立即支付"按钮后前端看到仍然是"待支付/立即支付"按钮，体验矛盾
        //    （也是用户认为"支付失败/订单异常"的第二大触发点）。
        //    所以余额支付直接 mock 回调：既保留真实沙箱的 PayLog/tradeNo/payUrl 字段，
        //    又保证订单状态与前端体验一致。其他 payType（微信/支付宝）仍走二维码+回调。
        if (payTypeEnum == PayType.BALANCE) {
            Result notifyResult = selfProxy.handlePayNotify(tradeNo, orderId, amount);
            if (notifyResult != null && Boolean.FALSE.equals(notifyResult.getSuccess())) {
                throw new IllegalStateException("余额支付失败: " + notifyResult.getErrorMsg());
            } else {
                log.info("余额支付自动完成回调：orderId={}, tradeNo={}", orderId, tradeNo);
            }
        }

        // 返回支付信息（包含支付链接和流水号）
        return Result.ok(buildPayResult(payLog));
    }

    private Map<String, Object> buildPayResult(PayLog payLog) {
        Map<String, Object> result = new HashMap<>();
        result.put("payUrl", simulatePaySdk(
                payLog.getTradeNo(), payLog.getAmount(), payLog.getPayType()));
        result.put("tradeNo", payLog.getTradeNo());
        result.put("orderId", payLog.getOrderId());
        result.put("amount", payLog.getAmount());
        return result;
    }

    /**
     * 模拟支付SDK调用
     * 【八股：真实场景下这里会调用微信/支付宝的SDK】
     * 微信支付SDK: WXPay.unifiedOrder()
     * 支付宝SDK: AlipayClient.execute(new AlipayTradePrecreateRequest())
     * 这里用模拟URL代替
     */
    private String simulatePaySdk(String tradeNo, Long amount, Integer payType) {
        String channel = PayType.of(payType).getDesc();
        // 模拟生成支付链接
        return "https://pay.mock/" + channel + "/qrcode?tradeNo=" + tradeNo + "&amount=" + amount;
    }

    /**
     * 处理支付回调（模拟第三方回调）
     *
     * 【八股：支付回调的幂等性处理】
     * 第三方支付平台可能会重复发送回调通知（网络超时重试）
     * 必须保证多次处理同一条回调，结果一致：
     * 1. 查PayLog：如果已经是成功状态，说明已处理过，直接返回成功
     * 2. 更新操作使用乐观锁：UPDATE ... WHERE status = 1（待支付）
     *
     * 【八股：回调为什么要快速返回？】
     * 第三方支付平台对回调有超时限制（通常5-10秒）
     * 如果回调处理太慢，第三方会认为失败，然后重试
     * 所以耗时的操作（发通知、推送）应该异步化，放到MQ
     */
    @Override
    @Transactional
    public Result handlePayNotify(String tradeNo, Long orderId, Long amount) {
        if (tradeNo == null || orderId == null || amount == null || amount <= 0) {
            return Result.fail("支付回调参数无效");
        }
        // 1. 先锁定订单，再读取流水，保证并发回调能看到前一个事务提交后的状态。
        VoucherOrder order = voucherOrderService.getBaseMapper().selectByIdForUpdate(orderId);
        if (order == null) {
            return Result.fail("订单不存在");
        }
        // 必须精确匹配订单和第三方流水，不能取订单的“最新一笔”流水
        PayLog payLog = payLogService.query()
                .eq("order_id", orderId)
                .eq("trade_no", tradeNo)
                .one();
        if (payLog == null) {
            return Result.fail("支付流水不存在");
        }
        if (!amount.equals(payLog.getAmount())) {
            return Result.fail("支付金额校验失败");
        }

        // 幂等性检查：如果PayLog已经是成功状态，直接返回
        if (payLog.getStatus() != null && payLog.getStatus() == 2) {
            log.info("支付回调重复处理，PayLog已是成功状态: orderId={}", orderId);
            return Result.ok("已处理");
        }
        if (payLog.getStatus() == null || payLog.getStatus() != 1) {
            return Result.fail("支付流水状态不允许成功回调");
        }

        // 2. 先以条件更新抢占订单支付状态，取消/支付只能有一方成功
        if (Integer.valueOf(OrderStatus.CANCELLED.getCode()).equals(order.getStatus())) {
            boolean paidLate = payLogService.update()
                    .set("status", 2)
                    .set("pending_flag", null)
                    .set("pay_time", LocalDateTime.now())
                    .eq("id", payLog.getId())
                    .eq("status", 1)
                    .update();
            if (!paidLate) {
                return Result.fail("支付流水状态异常");
            }
            sendRefundMessage(order, payLog);
            return Result.ok("订单已取消，支付款项将原路退回");
        }
        if (!Integer.valueOf(OrderStatus.UNPAID.getCode()).equals(order.getStatus())) {
            return Result.fail("订单状态不允许支付");
        }
        boolean orderChanged = voucherOrderService.lambdaUpdate()
                .set(VoucherOrder::getStatus, OrderStatus.PAID.getCode())
                .set(VoucherOrder::getPayTime, LocalDateTime.now())
                .set(VoucherOrder::getUpdateTime, LocalDateTime.now())
                .eq(VoucherOrder::getId, orderId)
                .eq(VoucherOrder::getStatus, OrderStatus.UNPAID.getCode())
                .update();
        if (!orderChanged) {
            log.warn("支付回调时订单状态已变化: orderId={}", orderId);
            return Result.fail("订单状态不允许支付");
        }

        boolean payLogChanged = payLogService.update()
                .set("status", 2)
                .set("pending_flag", null)
                .set("pay_time", LocalDateTime.now())
                .eq("id", payLog.getId())
                .eq("status", 1)
                .update();
        if (!payLogChanged) {
            throw new IllegalStateException("支付流水状态更新失败");
        }
        order.setStatus(OrderStatus.PAID.getCode());

        log.info("支付成功: orderId={}, tradeNo={}, amount={}分", orderId, tradeNo, payLog.getAmount());

        // 4. 发送支付成功通知到PAY_NOTIFY_QUEUE
        Map<String, Object> notifyMsg = new HashMap<>();
        notifyMsg.put("orderId", orderId);
        notifyMsg.put("userId", order.getUserId());
        notifyMsg.put("amount", payLog.getAmount());
        notifyMsg.put("tradeNo", tradeNo);
        saveOutboxEvent("pay-notify:" + tradeNo,
                TransactionOutboxPublisher.PAY_NOTIFY, orderId, notifyMsg);

        return Result.ok("支付成功");
    }

    /**
     * 申请退款
     *
     * 【八股：退款流程的状态流转】
     * PAID → REFUNDING → REFUNDED
     *
     * 1. 校验订单状态(必须是已支付PAID)
     *    - canTransitionTo(REFUNDING) 检查是否可以退款
     *    - 已核销(VERIFIED)的不能退款（已消费）
     * 2. 更新订单status=5退款中
     *    - 退款中是中间状态，表示退款正在处理
     * 3. 更新PayLog status=4已退款
     *    - 从支付角度，这笔支付被反转了
     * 4. 发送退款消息到REFUND_QUEUE
     *    - 异步处理退款（模拟第三方退款API调用）
     *    - 处理完成后回调handleRefund恢复库存
     *
     * 【八股：为什么退款是异步的？】
     * 1. 第三方退款API调用耗时长（可能几秒到几分钟）
     * 2. 退款需要恢复库存、删除一人一单记录等操作
     * 3. 异步处理可以重试失败的操作
     * 4. 用户不需要等待退款完成，只需知道"退款已发起"
     */
    @Override
    @Transactional
    public Result refundOrder(Long orderId) {
        // 1. 查询订单
        VoucherOrder order = voucherOrderService.getBaseMapper().selectByIdForUpdate(orderId);
        if (order == null) {
            return Result.fail("订单不存在");
        }

        if (!UserHolder.getUser().getId().equals(order.getUserId())) {
            return Result.fail("无权退款他人订单");
        }
        // 2. 校验订单状态(必须是已支付PAID)
        OrderStatus currentStatus = OrderStatus.of(order.getStatus());
        if (!currentStatus.canTransitionTo(OrderStatus.REFUNDING)) {
            return Result.fail("当前订单状态不允许退款: " + currentStatus.getDesc());
        }
        PayLog payLog = payLogService.query()
                .eq("order_id", orderId)
                .eq("status", 2)
                .orderByDesc("create_time")
                .last("LIMIT 1")
                .one();
        if (payLog == null) {
            return Result.fail("支付流水不存在或尚未支付成功");
        }
        boolean changed = voucherOrderService.lambdaUpdate()
                .set(VoucherOrder::getStatus, OrderStatus.REFUNDING.getCode())
                .set(VoucherOrder::getUpdateTime, LocalDateTime.now())
                .eq(VoucherOrder::getId, orderId)
                .eq(VoucherOrder::getStatus, OrderStatus.PAID.getCode())
                .update();
        if (!changed) {
            return Result.fail("退款请求已处理或订单状态已变化");
        }

        // 5. 发送退款消息到REFUND_QUEUE
        sendRefundMessage(order, payLog);

        log.info("退款申请已发起: orderId={}, status=退款中", orderId);
        return Result.ok("退款申请已发起，请等待退款到账");
    }

    /**
     * 处理退款回调
     *
     * 【八股：退款回调要做三件事】
     * 1. 更新订单状态：REFUNDING → REFUNDED，记录退款时间
     * 2. 恢复秒杀库存：
     *    - DB: stock = stock + 1（更新tb_seckill_voucher表）
     *    - Redis: INCR seckill:stock:{voucherId}（恢复Redis库存）
     * 3. 删除一人一单记录：SREM seckill:order:{voucherId} userId
     *    让用户可以重新下单
     *
     * 【八股：退款恢复库存 vs 取消恢复库存的区别】
     * 取消订单：订单从未支付过，库存恢复是因为用户放弃了购买
     * 退款：订单已支付，库存恢复是因为用户退款了
     * 两者恢复库存的操作完全相同，但业务语义不同
     *
     * 【八股：先恢复Redis还是先恢复DB？】
     * 先恢复Redis，再恢复DB：
     * - Redis是第一道防线（Lua脚本先查Redis库存）
     * - 即使DB恢复失败，Redis已恢复，其他用户可以下单
     * - DB恢复失败可以通过对账补偿
     * 这是一种"优先保证可用性"的设计思路
     */
    @Override
    @Transactional
    public Result handleRefund(String tradeNo, Long orderId, Long amount) {
        if (tradeNo == null || orderId == null || amount == null || amount <= 0) {
            return Result.fail("退款回调参数无效");
        }
        // 1. 查询订单
        VoucherOrder order = voucherOrderService.getBaseMapper().selectByIdForUpdate(orderId);
        if (order == null) {
            return Result.fail("订单不存在");
        }

        PayLog payLog = payLogService.query()
                .eq("order_id", orderId)
                .eq("trade_no", tradeNo)
                .one();
        if (payLog == null) {
            return Result.fail("支付流水不存在");
        }
        if (!amount.equals(payLog.getAmount())) {
            return Result.fail("退款金额校验失败");
        }
        if (order.getStatus() == OrderStatus.CANCELLED.getCode()) {
            if (payLog.getStatus() == 4) {
                scheduleRedisCompensation(order);
                return Result.ok("退款已处理");
            }
            boolean lateRefunded = payLogService.update()
                    .set("status", 4)
                    .set("pending_flag", null)
                    .set("refund_time", LocalDateTime.now())
                    .eq("id", payLog.getId())
                    .eq("status", 2)
                    .update();
            if (!lateRefunded) {
                return Result.fail("退款流水状态异常");
            }
            scheduleRedisCompensation(order);
            return Result.ok("取消订单的支付款项已退回");
        }
        if (order.getStatus() == OrderStatus.REFUNDED.getCode()
                && payLog.getStatus() == 4) {
            scheduleRedisCompensation(order);
            return Result.ok("退款已处理");
        }
        boolean changed = voucherOrderService.lambdaUpdate()
                .set(VoucherOrder::getStatus, OrderStatus.REFUNDED.getCode())
                .set(VoucherOrder::getActiveFlag, null)
                .set(VoucherOrder::getRefundTime, LocalDateTime.now())
                .set(VoucherOrder::getUpdateTime, LocalDateTime.now())
                .eq(VoucherOrder::getId, orderId)
                .eq(VoucherOrder::getStatus, OrderStatus.REFUNDING.getCode())
                .update();
        if (!changed) {
            return Result.fail("当前订单状态不允许退款完成");
        }
        boolean payLogChanged = payLogService.update()
                .set("status", 4)
                .set("pending_flag", null)
                .set("refund_time", LocalDateTime.now())
                .eq("id", payLog.getId())
                .eq("status", 2)
                .update();
        if (!payLogChanged) {
            throw new IllegalStateException("退款流水状态更新失败");
        }

        boolean stockChanged = seckillVoucherService.update()
                .setSql("stock = stock + 1")
                .eq("voucher_id", order.getVoucherId())
                .update();
        if (!stockChanged) {
            throw new IllegalStateException("退款恢复数据库库存失败");
        }

        scheduleRedisCompensation(order);

        log.info("退款完成: orderId={}, userId={}, voucherId={}, 已恢复数据库库存并登记Redis补偿",
                orderId, order.getUserId(), order.getVoucherId());
        return Result.ok("退款已到账");
    }

    private void scheduleRedisCompensation(VoucherOrder order) {
        Map<String, Object> compensation = new HashMap<>();
        compensation.put("id", order.getId());
        compensation.put("userId", order.getUserId());
        compensation.put("voucherId", order.getVoucherId());
        saveOutboxEvent("redis-compensation:" + order.getId(),
                TransactionOutboxPublisher.REDIS_COMPENSATION, order.getId(), compensation);

        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCommit() {
                try {
                    voucherOrderService.releaseRejectedReservation(order, true, true);
                } catch (RuntimeException e) {
                    log.warn("退款Redis补偿暂时失败，等待Outbox重试: orderId={}", order.getId(), e);
                }
            }
        });
    }

    private void sendRefundMessage(VoucherOrder order, PayLog payLog) {
        Map<String, Object> refundMsg = new HashMap<>();
        refundMsg.put("orderId", order.getId());
        refundMsg.put("tradeNo", payLog.getTradeNo());
        refundMsg.put("userId", order.getUserId());
        refundMsg.put("amount", payLog.getAmount());
        saveOutboxEvent("refund:" + payLog.getTradeNo(),
                TransactionOutboxPublisher.REFUND, order.getId(), refundMsg);
    }

    private void saveOutboxEvent(String eventKey, String eventType,
                                 Long aggregateId, Map<String, Object> payload) {
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
        } catch (org.springframework.dao.DuplicateKeyException duplicate) {
            log.info("Outbox事件已存在，忽略重复写入: eventKey={}", eventKey);
        }
    }
}
