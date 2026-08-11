package com.hmdp.service.impl;

import cn.hutool.json.JSONUtil;
import com.hmdp.config.QueueConfig;
import com.hmdp.dto.PaymentDTO;
import com.hmdp.dto.Result;
import com.hmdp.entity.PayLog;
import com.hmdp.entity.Voucher;
import com.hmdp.entity.VoucherOrder;
import com.hmdp.enums.OrderStatus;
import com.hmdp.enums.PayType;
import com.hmdp.service.IPaymentService;
import com.hmdp.service.ISeckillVoucherService;
import com.hmdp.service.IVoucherService;
import com.hmdp.utils.RedisConstants;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

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
 * - IVoucherService：查询优惠券获取支付金额
 * - ISeckillVoucherService：退款时恢复DB库存
 */
@Slf4j
@Service
public class PaymentServiceImpl implements IPaymentService {

    @Resource
    private VoucherOrderServiceImpl voucherOrderService;

    @Resource
    private PayLogServiceImpl payLogService;

    @Resource
    private StringRedisTemplate stringRedisTemplate;

    @Resource
    private RabbitTemplate rabbitTemplate;

    /**
     * 优惠券服务 —— 查询优惠券的支付金额(payValue)
     */
    @Resource
    private IVoucherService voucherService;

    /**
     * 秒杀券服务 —— 退款时恢复DB库存
     */
    @Resource
    private ISeckillVoucherService seckillVoucherService;


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
    public Result payOrder(PaymentDTO dto) {
        Long orderId = dto.getOrderId();
        Integer payType = dto.getPayType();

        // 1. 查订单是否存在、是否是待支付状态（先DB、再Redis pending，防止异步落库窗口"订单不存在"）
        VoucherOrder order = voucherOrderService.getOrderWithPending(orderId);
        if (order == null) {
            return Result.fail("订单不存在");
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

        // 2. 查优惠券获取支付金额
        Voucher voucher = voucherService.getById(order.getVoucherId());
        if (voucher == null) {
            return Result.fail("优惠券不存在");
        }
        Long amount = voucher.getPayValue();
        if (amount == null || amount <= 0) {
            return Result.fail("支付金额异常");
        }

        // 3. 创建PayLog记录（status=1待支付）
        PayLog payLog = new PayLog();
        payLog.setOrderId(orderId);
        payLog.setUserId(order.getUserId());
        payLog.setPayType(payType);
        payLog.setAmount(amount);
        payLog.setStatus(1); // 1=待支付
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

        // 6. 更新订单payType
        order.setPayType(payType);
        order.setUpdateTime(LocalDateTime.now());
        voucherOrderService.updateById(order);

        // 7. 对 payType=BALANCE（余额支付，本项目前端默认点击"立即支付"就是余额）直接同步完成回调。
        //    【为什么需要这一步？】
        //    原流程：payOrder 只创建 PayLog(status=1) + 返回 payUrl，需要真实扫码→第三方回调→handlePayNotify
        //    才会把订单状态 UNPAID→PAID。但本地 demo 环境没有第三方扫码渠道，
        //    用户点击"立即支付"按钮后前端看到仍然是"待支付/立即支付"按钮，体验矛盾
        //    （也是用户认为"支付失败/订单异常"的第二大触发点）。
        //    所以余额支付直接 mock 回调：既保留真实沙箱的 PayLog/tradeNo/payUrl 字段，
        //    又保证订单状态与前端体验一致。其他 payType（微信/支付宝）仍走二维码+回调。
        PayType payTypeEnum = PayType.of(payType);
        if (payTypeEnum == PayType.BALANCE) {
            Result notifyResult = handlePayNotify(tradeNo, orderId);
            if (notifyResult != null && Boolean.FALSE.equals(notifyResult.getSuccess())) {
                log.warn("余额支付自动回调失败：orderId={}, msg={}", orderId, notifyResult.getErrorMsg());
            } else {
                log.info("余额支付自动完成回调：orderId={}, tradeNo={}", orderId, tradeNo);
            }
        }

        // 返回支付信息（包含支付链接和流水号）
        Map<String, Object> result = new HashMap<>();
        result.put("payUrl", payUrl);
        result.put("tradeNo", tradeNo);
        result.put("orderId", orderId);
        result.put("amount", amount);
        return Result.ok(result);
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
    public Result handlePayNotify(String tradeNo, Long orderId) {
        // 1. 查PayLog确认存在
        PayLog payLog = payLogService.query()
                .eq("order_id", orderId)
                .orderByDesc("create_time")
                .last("LIMIT 1")
                .one();
        if (payLog == null) {
            return Result.fail("支付流水不存在");
        }

        // 幂等性检查：如果PayLog已经是成功状态，直接返回
        if (payLog.getStatus() != null && payLog.getStatus() == 2) {
            log.info("支付回调重复处理，PayLog已是成功状态: orderId={}", orderId);
            return Result.ok("已处理");
        }

        // 2. 更新PayLog status=2成功，记录payTime
        payLog.setStatus(2); // 2=成功
        payLog.setPayTime(LocalDateTime.now());
        payLogService.updateById(payLog);

        // 3. 更新订单status=2已支付，记录payTime
        VoucherOrder order = voucherOrderService.getById(orderId);
        if (order == null) {
            return Result.fail("订单不存在");
        }
        // 状态机校验：UNPAID → PAID
        OrderStatus currentStatus = OrderStatus.of(order.getStatus());
        if (!currentStatus.canTransitionTo(OrderStatus.PAID)) {
            log.warn("支付回调时订单状态异常: orderId={}, status={}", orderId, currentStatus.getDesc());
            return Result.fail("订单状态不允许支付");
        }
        order.setStatus(OrderStatus.PAID.getCode());
        order.setPayTime(LocalDateTime.now());
        order.setUpdateTime(LocalDateTime.now());
        voucherOrderService.updateById(order);

        log.info("支付成功: orderId={}, tradeNo={}, amount={}分", orderId, tradeNo, payLog.getAmount());

        // 4. 发送支付成功通知到PAY_NOTIFY_QUEUE
        Map<String, Object> notifyMsg = new HashMap<>();
        notifyMsg.put("orderId", orderId);
        notifyMsg.put("userId", order.getUserId());
        notifyMsg.put("amount", payLog.getAmount());
        notifyMsg.put("tradeNo", tradeNo);
        rabbitTemplate.convertAndSend(
                QueueConfig.PAY_NOTIFY_EXCHANGE,
                QueueConfig.PAY_NOTIFY_ROUTING_KEY,
                JSONUtil.toJsonStr(notifyMsg)
        );

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
        VoucherOrder order = voucherOrderService.getById(orderId);
        if (order == null) {
            return Result.fail("订单不存在");
        }

        // 2. 校验订单状态(必须是已支付PAID)
        OrderStatus currentStatus = OrderStatus.of(order.getStatus());
        if (!currentStatus.canTransitionTo(OrderStatus.REFUNDING)) {
            return Result.fail("当前订单状态不允许退款: " + currentStatus.getDesc());
        }

        // 3. 更新订单status=5退款中
        order.setStatus(OrderStatus.REFUNDING.getCode());
        order.setUpdateTime(LocalDateTime.now());
        voucherOrderService.updateById(order);

        // 4. 更新PayLog status=4已退款
        PayLog payLog = payLogService.query()
                .eq("order_id", orderId)
                .orderByDesc("create_time")
                .last("LIMIT 1")
                .one();
        if (payLog != null) {
            payLog.setStatus(4); // 4=已退款
            payLog.setRefundTime(LocalDateTime.now());
            payLogService.updateById(payLog);
        }

        // 5. 发送退款消息到REFUND_QUEUE
        Map<String, Object> refundMsg = new HashMap<>();
        refundMsg.put("orderId", orderId);
        refundMsg.put("tradeNo", payLog != null ? payLog.getTradeNo() : null);
        refundMsg.put("userId", order.getUserId());
        rabbitTemplate.convertAndSend(
                QueueConfig.REFUND_EXCHANGE,
                QueueConfig.REFUND_ROUTING_KEY,
                JSONUtil.toJsonStr(refundMsg)
        );

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
    public Result handleRefund(String tradeNo, Long orderId) {
        // 1. 查询订单
        VoucherOrder order = voucherOrderService.getById(orderId);
        if (order == null) {
            return Result.fail("订单不存在");
        }

        // 2. 更新订单status=6已退款，记录refundTime
        OrderStatus currentStatus = OrderStatus.of(order.getStatus());
        if (!currentStatus.canTransitionTo(OrderStatus.REFUNDED)) {
            return Result.fail("当前订单状态不允许退款完成: " + currentStatus.getDesc());
        }
        order.setStatus(OrderStatus.REFUNDED.getCode());
        order.setRefundTime(LocalDateTime.now());
        order.setUpdateTime(LocalDateTime.now());
        voucherOrderService.updateById(order);

        // 3. 恢复秒杀库存(stock+1)
        Long voucherId = order.getVoucherId();
        Long userId = order.getUserId();

        // 3.1 恢复Redis库存 —— INCR是原子操作
        stringRedisTemplate.opsForValue().increment(RedisConstants.SECKILL_STOCK_KEY + voucherId);
        // 3.2 恢复DB库存 —— stock = stock + 1
        seckillVoucherService.update()
                .setSql("stock = stock + 1")
                .eq("voucher_id", voucherId)
                .update();

        // 4. 删除Redis中一人一单记录(SREM seckill:order:voucherId userId)
        // 【八股：为什么要删除一人一单记录？】
        // 退款后用户应该可以重新下单
        // 如果不删除SREM记录，Lua脚本会判定"重复下单"拒绝购买
        stringRedisTemplate.opsForSet().remove(RedisConstants.SECKILL_ORDER_KEY + voucherId, userId.toString());

        log.info("退款完成: orderId={}, userId={}, voucherId={}, 已恢复库存",
                orderId, userId, voucherId);
        return Result.ok("退款已到账");
    }
}
