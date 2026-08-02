package com.hmdp.controller;


import com.hmdp.annotation.RateLimit;
import com.hmdp.dto.Result;
import com.hmdp.service.IVoucherOrderService;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.annotation.Resource;

/**
 * <p>
 *  前端控制器 —— 秒杀订单入口
 * </p>
 *
 * 【八股：秒杀接口为什么需要限流？】
 * 秒杀场景的特点：
 * 1. 瞬时高并发：几千甚至几万用户在同一秒抢购
 * 2. 库存有限：可能只有100个名额
 * 3. 资源消耗大：每个请求都要查Redis、执行Lua脚本、发MQ
 *
 * 不限流的后果：
 * - 后端服务被打崩（CPU/内存耗尽）
 * - Redis被打爆（连接池耗尽）
 * - 正常用户也用不了（服务不可用）
 *
 * 限流策略：
 * - QPS=50：每秒只允许50个请求进入秒杀逻辑
 * - 多余的请求直接返回"排队中"
 * - 虽然用户被拒绝了，但比服务全崩了好
 * - 类似线下排队：门店容量有限，满了就在门口等着
 *
 * @author 虎哥
 * @since 2021-12-22
 */
@RestController
@RequestMapping("/voucher-order")
public class VoucherOrderController {
    @Resource
    private IVoucherOrderService voucherOrderService;

    /**
     * 秒杀下单
     *
     * 【八股：秒杀限流为什么不放在Service层？】
     * 放在Controller层有两个好处：
     * 1. 最早拦截：请求还没进入业务逻辑就被拒绝了，节省所有后续资源
     * 2. 语义清晰：限流是接口级别的控制，属于入口层职责
     * 如果放在Service层，请求已经经过了拦截器、参数解析等流程，浪费了资源
     *
     * 【八股：QPS设为50够吗？】
     * 这取决于服务器配置和业务复杂度：
     * - 单机8C16G：可以设100-200
     * - 单机2C4G：设50比较安全
     * - 面试时可以说：这个值需要通过压测来确定，50是一个保守估计
     */
    @PostMapping("seckill/{id}")
    @RateLimit(qps = 50, message = "当前抢购人数过多，请稍后再试")
    public Result seckillVoucher(@PathVariable("id") Long voucherId) {
        return voucherOrderService.seckillVoucher(voucherId);
    }
}
