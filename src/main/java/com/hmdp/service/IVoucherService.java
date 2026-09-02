package com.hmdp.service;

import com.hmdp.dto.Result;
import com.hmdp.entity.Voucher;
import com.baomidou.mybatisplus.extension.service.IService;

/**
 * <p>
 *  服务类
 * </p>
 *
 * @author 虎哥
 * @since 2021-12-22
 */
public interface IVoucherService extends IService<Voucher> {

    Result queryVoucherOfShop(Long shopId);

    /**
     * 查询全部秒杀券（秒杀专场页面使用）
     */
    Result queryAllSeckillVoucher();

    void addSeckillVoucher(Voucher voucher);

    /**
     * 新增普通券（只落 tb_voucher，不写秒杀表和 Redis 库存）
     */
    void addVoucher(Voucher voucher);
}
