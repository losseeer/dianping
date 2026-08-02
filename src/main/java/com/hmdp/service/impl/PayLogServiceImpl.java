package com.hmdp.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.hmdp.entity.PayLog;
import com.hmdp.mapper.PayLogMapper;
import com.hmdp.service.IPayLogService;
import org.springframework.stereotype.Service;

/**
 * 支付流水服务实现类
 *
 * 【八股：ServiceImpl<M, T>的作用？】
 * M = PayLogMapper：指定Mapper接口
 * T = PayLog：指定实体类
 * ServiceImpl帮我们实现了IService中定义的所有CRUD方法
 * 底层就是调用Mapper的方法，不需要我们手写SQL
 *
 * 【八股：MyBatis-Plus的架构】
 * Controller → IService → ServiceImpl → BaseMapper → 数据库
 * - IService定义接口规范
 * - ServiceImpl实现通用CRUD
 * - BaseMapper定义Mapper通用方法
 * - 具体的Mapper接口继承BaseMapper，可以扩展自定义SQL
 */
@Service
public class PayLogServiceImpl extends ServiceImpl<PayLogMapper, PayLog> implements IPayLogService {
}
