package com.hmdp.service;

import com.hmdp.dto.Result;
import com.hmdp.entity.VoucherOrder;
import com.baomidou.mybatisplus.extension.service.IService;
import com.hmdp.enums.OrderCreationResult;

/**
 * <p>
 *  服务类
 * </p>
 *
 * @author 虎哥
 * @since 2021-12-22
 */
public interface IVoucherOrderService extends IService<VoucherOrder> {

    Result seckillVoucher(Long voucherId);

    OrderCreationResult createVoucherOrder(VoucherOrder voucherOrder);

    OrderCreationResult handleVoucherOrder(VoucherOrder voucherOrder);

    void releaseRejectedReservation(VoucherOrder voucherOrder,
                                    boolean restoreRedisStock,
                                    boolean releaseQualification);

    /**
     * 查询订单（先查 DB，查不到再查 Redis pending 预订单），
     * 供支付/取消/详情查询的统一入口使用，避免异步落库窗口期出现"订单不存在"。
     *
     * @param orderId 订单ID
     * @return VoucherOrder 或 null
     */
    VoucherOrder getOrderWithPending(Long orderId);

    /**
     * 落库成功后清理 Redis pending 预订单缓存，保证一致性。
     *
     * @param orderId  订单ID
     * @param userId   用户ID（用于清理用户维度索引，可为空）
     */
    void evictPendingOrder(Long orderId, Long userId);

    /**
     * 查询订单详情（包含优惠券信息）
     * 【八股：为什么查询要联表？】
     * 订单表只存了voucherId，用户还需要知道优惠券标题、金额等信息
     * 需要联表查询Voucher表获取详情
     *
     * @param orderId 订单ID
     * @return 订单详情（订单+优惠券信息）
     */
    Result queryOrderById(Long orderId);

    /**
     * 查询我的订单（可按状态筛选）
     * 【八股：分页查询的必要性】
     * 1. 数据量大时一次查全部会OOM
     * 2. 前端只需要展示一页，没必要查全部
     * 3. 数据库LIMIT分页比查全部快得多
     *
     * @param status 订单状态（null表示查全部状态）
     * @return 分页订单列表
     */
    Result queryMyOrders(Integer status);

    /**
     * 手动取消订单
     * 【八股：取消订单要做什么？】
     * 1. 校验订单状态（只有未支付才能取消）
     * 2. 更新订单状态为已取消
     * 3. 恢复Redis库存（INCR）
     * 4. 恢复DB库存（stock+1）
     * 5. 删除一人一单记录（SREM）—— 让用户可以重新下单
     *
     * @param orderId 订单ID
     * @return 取消结果
     */
    Result cancelOrder(Long orderId);

    /**
     * 处理超时订单（MQ延迟队列回调）
     * 【八股：为什么要检查状态？】
     * 延迟消息发出去后，用户可能在30分钟内已经支付了
     * 消费延迟消息时必须先检查订单状态：
     * - 如果还是UNPAID → 执行取消
     * - 如果已经PAID → 忽略（用户已支付，不能取消）
     * 这是并发场景下的幂等性保护
     *
     * @param orderId 订单ID
     */
    void handleOrderTimeout(Long orderId);
}
