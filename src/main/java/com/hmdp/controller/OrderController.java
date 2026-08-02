package com.hmdp.controller;

import com.hmdp.dto.Result;
import com.hmdp.service.IVoucherOrderService;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;

/**
 * 订单控制器 —— 交易闭环订单管理
 *
 * 【八股：RESTful API设计规范】
 * GET    /order/{id}     → 查询订单详情（查询用GET，参数在URL中）
 * GET    /order/list     → 查询我的订单列表（查询用GET，参数在URL中）
 * POST   /order/cancel/{id} → 取消订单（状态变更用POST）
 *
 * 【八股：GET vs POST的使用场景】
 * GET：查询操作，幂等（多次调用结果一样），参数在URL中
 * POST：创建/修改操作，不幂等，参数在body中
 * 本控制器：
 * - 查询订单用GET（幂等，查多少次都一样）
 * - 取消订单用POST（不幂等，取消一次就变了状态）
 *
 * 【八股：为什么订单取消用POST而不是DELETE？】
 * DELETE语义是"删除资源"，但取消订单不是删除订单记录
 * 订单数据仍然保留在数据库中（状态改为已取消）
 * 用POST更合适，因为它是"修改资源状态"
 */
@RestController
@RequestMapping("/order")
public class OrderController {

    @Resource
    private IVoucherOrderService voucherOrderService;

    /**
     * 查询订单详情
     * 返回订单信息 + 优惠券信息
     *
     * @param id 订单ID
     */
    @GetMapping("/{id}")
    public Result queryOrderById(@PathVariable Long id) {
        return voucherOrderService.queryOrderById(id);
    }

    /**
     * 查询我的订单（可按状态筛选）
     *
     * 【八股：@RequestParam vs @PathVariable】
     * @PathVariable：从URL路径中取参数 /order/{id} → id
     * @RequestParam：从URL查询参数中取 /order/list?status=1 → status
     * 区别：
     * - PathVariable用于标识资源（订单ID）
     * - RequestParam用于过滤/排序（状态筛选）
     * - PathVariable是必填的，RequestParam可以设置required=false
     *
     * @param status 订单状态（可选，null表示查全部）
     */
    @GetMapping("/list")
    public Result queryMyOrders(@RequestParam(required = false) Integer status) {
        return voucherOrderService.queryMyOrders(status);
    }

    /**
     * 手动取消订单
     * 只有未支付(UNPAID)的订单才能手动取消
     * 已支付的需要走退款流程
     *
     * @param id 订单ID
     */
    @PostMapping("/cancel/{id}")
    public Result cancelOrder(@PathVariable Long id) {
        return voucherOrderService.cancelOrder(id);
    }
}
