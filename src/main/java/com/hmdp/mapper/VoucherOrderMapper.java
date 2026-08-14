package com.hmdp.mapper;

import com.hmdp.entity.VoucherOrder;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

/**
 * <p>
 *  Mapper 接口
 * </p>
 *
 * @author 虎哥
 * @since 2021-12-22
 */
public interface VoucherOrderMapper extends BaseMapper<VoucherOrder> {

    @Insert("INSERT IGNORE INTO tb_voucher_order " +
            "(id, user_id, voucher_id, status, active_flag, amount, create_time) " +
            "VALUES (#{order.id}, #{order.userId}, #{order.voucherId}, #{cancelledStatus}, " +
            "NULL, #{order.amount}, #{order.createTime})")
    int insertCancelledIfAbsent(@Param("order") VoucherOrder order,
                                @Param("cancelledStatus") int cancelledStatus);

    @Select("SELECT * FROM tb_voucher_order WHERE id = #{orderId} FOR UPDATE")
    VoucherOrder selectByIdForUpdate(@Param("orderId") Long orderId);
}
