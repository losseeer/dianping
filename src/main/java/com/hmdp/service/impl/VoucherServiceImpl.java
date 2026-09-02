package com.hmdp.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.hmdp.dto.Result;
import com.hmdp.entity.Voucher;
import com.hmdp.mapper.VoucherMapper;
import com.hmdp.entity.SeckillVoucher;
import com.hmdp.service.ISeckillVoucherService;
import com.hmdp.service.IVoucherService;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import javax.annotation.Resource;
import java.util.List;

import static com.hmdp.utils.RedisConstants.SECKILL_STOCK_KEY;

/**
 * <p>
 *  服务实现类
 * </p>
 *
 * @author 虎哥
 * @since 2021-12-22
 */
@Service
public class VoucherServiceImpl extends ServiceImpl<VoucherMapper, Voucher> implements IVoucherService {

    @Resource
    private ISeckillVoucherService seckillVoucherService;
    @Resource
    private StringRedisTemplate stringRedisTemplate;

    @Override
    public Result queryVoucherOfShop(Long shopId) {
        // 查询优惠券信息
        List<Voucher> vouchers = getBaseMapper().queryVoucherOfShop(shopId);
        // 返回结果
        return Result.ok(vouchers);
    }

    @Override
    public Result queryAllSeckillVoucher() {
        List<Voucher> vouchers = getBaseMapper().queryAllSeckillVoucher();
        return Result.ok(vouchers);
    }

    @Override
    public void addVoucher(Voucher voucher) {
        // 普通券只落 tb_voucher；不写 tb_seckill_voucher、不预热 Redis 库存
        save(voucher);
    }

    @Override
    @Transactional
    public void addSeckillVoucher(Voucher voucher) {
        // 保存优惠券
        save(voucher);
        // 保存秒杀信息
        SeckillVoucher seckillVoucher = new SeckillVoucher();
        seckillVoucher.setVoucherId(voucher.getId());
        seckillVoucher.setStock(voucher.getStock());
        seckillVoucher.setBeginTime(voucher.getBeginTime());
        seckillVoucher.setEndTime(voucher.getEndTime());
        seckillVoucherService.save(seckillVoucher);
        //保存秒杀得库存到redis
        // 【八股：为什么用 setIfAbsent 而不是 set？】与 VoucherOrderServiceImpl#ensureRedisStock 同理：
        // Redis 里的库存是"已扣减后的余量"，无条件 set 会用 DB 全量覆盖、把已扣减的加回来（超卖）；
        // NX 保证只在 key 不存在（首次创建/冷启动）时初始化。已存在时不刷新（需人工对账）。
        stringRedisTemplate.opsForValue().setIfAbsent(SECKILL_STOCK_KEY + voucher.getId(), voucher.getStock().toString());

    }
}
