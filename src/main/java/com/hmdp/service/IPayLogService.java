package com.hmdp.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.hmdp.entity.PayLog;

/**
 * 支付流水服务接口
 *
 * 【八股：为什么Service继承IService<T>？】
 * IService是MyBatis-Plus提供的通用服务接口，内置了：
 * - save/saveBatch：插入
 * - update/updateById：更新
 * - remove/removeById：删除
 * - getById/getOne/query：查询
 * - page：分页查询
 * 继承后无需自己写这些CRUD方法，直接调用即可
 *
 * 【八股：为什么要分Service和ServiceImpl？】
 * 1. 面向接口编程：Controller依赖Service接口，不依赖实现类，解耦
 * 2. 可替换性：换实现类只需改Spring注入，不改Controller代码
 * 3. 可测试性：Mock接口比Mock类更容易
 * 4. AOP代理：Spring对接口做JDK动态代理，对类做CGLIB代理
 */
public interface IPayLogService extends IService<PayLog> {
}
