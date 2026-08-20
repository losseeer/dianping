package com.hmdp.service.impl;

import cn.hutool.core.bean.BeanUtil;
import cn.hutool.json.JSONUtil;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.hmdp.config.QueueConfig;
import com.hmdp.dto.PaymentDTO;
import com.hmdp.dto.Result;
import com.hmdp.entity.Voucher;
import com.hmdp.entity.VoucherOrder;
import com.hmdp.entity.SeckillVoucher;
import com.hmdp.entity.TransactionOutbox;
import com.hmdp.enums.OrderCreationResult;
import com.hmdp.enums.OrderStatus;
import com.hmdp.enums.PayType;
import com.hmdp.mapper.VoucherOrderMapper;
import com.hmdp.mapper.TransactionOutboxMapper;
import com.hmdp.listener.TransactionOutboxPublisher;
import com.hmdp.service.IPaymentService;
import com.hmdp.service.ISeckillVoucherService;
import com.hmdp.service.IVoucherOrderService;
import com.hmdp.service.IVoucherService;
import com.hmdp.utils.RedisConstants;
import com.hmdp.utils.RedisIdWorker;
import com.hmdp.utils.UserHolder;
import com.rabbitmq.client.Channel;
import lombok.extern.slf4j.Slf4j;
import org.apache.ibatis.javassist.bytecode.stackmap.BasicBlock;
import org.redisson.api.RLock;
import org.redisson.api.RedissonClient;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.aop.framework.AopContext;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Lazy;
import org.springframework.core.io.ClassPathResource;
import org.springframework.data.redis.connection.stream.*;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.transaction.interceptor.TransactionAspectSupport;
import org.springframework.dao.DuplicateKeyException;

import javax.annotation.PostConstruct;
import javax.annotation.Resource;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.*;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.stream.Collectors;

/**
 * <p>
 *  服务实现类 —— 【秒杀核心模块】
 *  面试八股关联：
 *  - 高并发秒杀方案演进：同步下单 → Redis预检+异步下单
 *  - 分布式锁：Redisson可重入锁 vs 自研setnx锁
 *  - 乐观锁vs悲观锁：超卖问题解决方案
 *  - Lua脚本原子性：Redis单线程模型保障
 *  - 消息队列削峰填谷：RabbitMQ异步解耦
 *  - Spring AOP代理：事务失效问题与解决方案
 * </p>
 *
 * @author 虎哥
 * @since 2021-12-22
 */
@Slf4j
@Service
public class VoucherOrderServiceImpl extends ServiceImpl<VoucherOrderMapper, VoucherOrder> implements IVoucherOrderService {

    /**
     * 自引用代理（@Lazy 打破循环依赖）。
     * 替代 AopContext.currentProxy() 方案：避免 Listener 消费线程/非 HTTP 请求线程
     * 未暴露 AopContext 而导致 proxy 为 null，造成 @Transactional 失效/重复扣库存。
     */
    @Resource
    @Lazy
    private IVoucherOrderService selfProxy;

    @PostConstruct
    public void initProxy() {
        this.proxy = selfProxy;
    }

    @Resource
    private ISeckillVoucherService seckillVoucherService;

    @Resource
    private RabbitTemplate rabbitTemplate;
    @Resource
    private RedisIdWorker redisIdWorker;

    @Resource
    private StringRedisTemplate stringRedisTemplate;

    @Resource
    private RedissonClient redissonClient;

    @Resource
    private TransactionOutboxMapper outboxMapper;

    private final TransactionTemplate transactionTemplate;

    public VoucherOrderServiceImpl(PlatformTransactionManager transactionManager) {
        this.transactionTemplate = new TransactionTemplate(transactionManager);
    }

    /**
     * 支付服务 —— 【八股：循环依赖问题】
     * VoucherOrderServiceImpl依赖IPaymentService，PaymentServiceImpl又依赖VoucherOrderServiceImpl
     * 这形成了循环依赖。Spring Boot 2.3默认允许循环依赖（spring.main.allow-circular-references=true）
     * 但为了安全和明确，加上@Lazy注解：
     * - @Lazy让Spring在首次使用时才创建代理对象，而不是启动时就注入
     * - 这样打破了"鸡生蛋蛋生鸡"的初始化循环
     *
     * 【八股：@Lazy的原理】
     * @Lazy注入的不是真实对象，而是一个CGLIB代理
     * 调用代理的方法时，代理才从容器中获取真实Bean并委托调用
     * 这就延迟了真正的依赖解析，打破了循环
     */
    @Resource
    @Lazy
    private IPaymentService paymentService;

    /**
     * 优惠券服务 —— 用于查询订单详情时获取优惠券信息
     */
    @Resource
    private IVoucherService voucherService;

    /**
     * 脚本初始化 —— 【八股：为什么用static final？】
     * 1. Lua脚本只需要加载一次，避免每次请求都重新读取文件
     * 2. DefaultRedisScript是不可变对象，线程安全，适合作为类常量
     * 3. 静态代码块在类加载时执行一次，符合单例模式思想
     *
     * 【八股：为什么用Lua脚本？】
     * - Redis执行单条命令是原子的（单线程模型），但多条命令就不是了
     * - Lua脚本将多条命令打包成一个整体，Redis会一次性执行完整个脚本
     * - 减少网络开销：一次网络调用完成多个操作
     * - 替代方案：用分布式锁也能实现，但性能不如Lua，Lua是天然互斥
     */
    private static final DefaultRedisScript<Long> SECKILL_SCRIPT;
    private static final DefaultRedisScript<Long> RESTORE_SECKILL_SCRIPT;
    static {
        SECKILL_SCRIPT=new DefaultRedisScript<>();
        SECKILL_SCRIPT.setLocation(new ClassPathResource("seckill.lua"));
        SECKILL_SCRIPT.setResultType(Long.class);
        RESTORE_SECKILL_SCRIPT = new DefaultRedisScript<>();
        RESTORE_SECKILL_SCRIPT.setLocation(new ClassPathResource("restore-seckill.lua"));
        RESTORE_SECKILL_SCRIPT.setResultType(Long.class);
    }

    // 旧的内嵌 VoucherOrderHandler（JVM BlockingQueue 版 + Redis Stream 轮询版）
    // 已整体迁移到 listener/SeckillVoucherListener.java，废弃死代码已删除

    /**
     * 处理秒杀订单（异步消费时调用）—— 【八股：为什么这里还要加分布式锁？】
     *
     * 按理说Lua脚本已经做了一人一单的判断，为什么消费端还要加锁？
     * 答：因为消息队列可能存在消息重复消费的情况（比如网络抖动导致ack失败，消息重新投递）
     * 分布式锁在这里是兜底保护，防止重复消费导致的重复下单
     *
     * 【八股：Redisson分布式锁原理】
     * 1. 可重入：用Hash结构存储，key是锁名，field是"线程ID:重入次数"
     *    - 同一线程多次加锁，重入计数+1
     *    - 释放锁时计数-1，减到0才真正删除key
     * 2. 看门狗(WatchDog)：默认30秒过期，每隔10秒检查一次，如果业务还在执行就续期到30秒
     *    - 解决了"锁过期了但业务还没执行完"的问题
     *    - 注意：如果手动指定了leaseTime，看门狗就不生效了
     * 3. 可重试：tryLock()会自旋等待一段时间，不是获取不到就直接失败
     * 4. 主从一致性问题：Redisson提供了multiLock（红锁），需要在多个独立节点都获取成功才算加锁成功
     *
     * 【八股：分布式锁的实现方案对比】
     * - 数据库：性能差，不适合高并发
     * - Redis setnx：简单但功能弱，不可重入、无续期、主从有问题
     * - Redisson：功能完善，生产环境首选
     * - Zookeeper：强一致性但性能不如Redis，适合并发不是特别高但对一致性要求高的场景
     */
        public OrderCreationResult handleVoucherOrder(VoucherOrder voucherOrder) {
            //1.获取用户
            Long userId = voucherOrder.getUserId();
            //2.创建锁对象 —— 【八股：锁的粒度为什么是 userId+voucherId？】
            // 一人一单的目标是"同一用户对同一张券不能重复下单"
            // 锁 userId+voucherId 精确覆盖这个目标：不同用户/不同券互不阻塞，吞吐最大化
            // 如果只锁 voucherId，不同用户之间也会互斥；锁粒度越小越好，能锁住目标即可
            RLock lock = redissonClient.getLock(
                    "lock:order:" + userId + ":" + voucherOrder.getVoucherId());
            //3.获取锁 —— 【八股：tryLock() vs lock()】
            // tryLock()：尝试获取锁，获取失败立即返回false，不会阻塞
            // lock()：阻塞等待，直到获取到锁
            // 这里是MQ消费线程（后台线程），阻塞等待可以接受——等锁期间消息不ack，不会丢
            // 若是HTTP请求线程则应改用tryLock快速失败，避免占满Tomcat线程池
            lock.lock();
            try {
                //直接调用，不会触发spring aop的事务管理
                //要通过代理调用，获取代理对象，才会被spring aop拦截
                // 【八股：Spring事务失效的常见场景】
                // 1. 同类中方法调用（this调用）：因为AOP代理只拦截外部调用
                //    → 解决：用AopContext.currentProxy()获取代理对象，或注入自己
                // 2. 方法不是public：@Transactional只能代理public方法
                // 3. 异常被try-catch吃掉了：Spring只在抛出未捕获异常时才回滚
                // 4. 数据库引擎不支持事务：比如MyISAM
                // 5. 多线程环境：事务和连接绑定在ThreadLocal，不同线程用不同连接
                return proxy.createVoucherOrder(voucherOrder);
            } catch (IllegalStateException e) {
                throw new RuntimeException(e);
            }finally {
                //释放锁 —— 【八股：为什么要在finally释放锁？】
                // 防止业务代码抛出异常导致锁无法释放，造成死锁
                // 即使有过期时间兜底，也应该主动释放，减少锁持有时间
                if (lock.isHeldByCurrentThread()) {
                    lock.unlock();
                }
            }
        }
    private IVoucherOrderService proxy;

    /**
     * 秒杀下单主入口 —— 【八股：秒杀系统的整体架构思路】
     *
     * 秒杀的核心矛盾：瞬时高并发 vs 数据库扛不住
     * 解决思路：
     * 1. 限流：入口处挡掉大部分请求（验证码、答题、令牌桶）
     * 2. 缓存：把库存放到Redis，内存操作比数据库快100倍
     * 3. 异步：能不实时做的就异步做（下单写库交给MQ）
     * 4. 削峰：用消息队列把瞬时请求摊平
     *
     * 本项目采用：Redis + Lua预检 + RabbitMQ异步下单
     * 性能从几百QPS提升到几万QPS
     */
    @Override
    public Result seckillVoucher(Long voucherId) {
        //获取用户id
        Long userId = UserHolder.getUser().getId();
        SeckillVoucher seckillVoucher = seckillVoucherService.getById(voucherId);
        if (seckillVoucher == null) {
            return Result.fail("秒杀券不存在");
        }
        Voucher voucher = voucherService.getById(voucherId);
        if (voucher == null || voucher.getPayValue() == null || voucher.getPayValue() <= 0) {
            return Result.fail("优惠券支付金额异常");
        }
        LocalDateTime now = LocalDateTime.now();
        if (seckillVoucher.getBeginTime() == null || seckillVoucher.getBeginTime().isAfter(now)) {
            return Result.fail("秒杀尚未开始");
        }
        if (seckillVoucher.getEndTime() == null || !seckillVoucher.getEndTime().isAfter(now)) {
            return Result.fail("秒杀已经结束");
        }
        ensureRedisStock(voucherId, seckillVoucher.getStock());
        //获取订单id —— 【八股：RedisIdWorker分布式ID生成器】
        // 为什么不用数据库自增ID？
        // 1. 分库分表后自增ID会重复
        // 2. ID暴露在URL中，会被爬虫遍历（别人能算出你有多少订单）
        // 雪花算法：1位符号位 + 41位时间戳 + 5位机房ID + 5位机器ID + 12位序列号
        // 本项目用Redis实现：时间戳 + 自增序列号
        long orderId = redisIdWorker.nextId("order");
        VoucherOrder order = new VoucherOrder();
        order.setId(orderId);
        order.setUserId(userId);
        order.setVoucherId(voucherId);
        order.setStatus(OrderStatus.UNPAID.getCode());
        order.setAmount(voucher.getPayValue());
        order.setCreateTime(now);
        String jsonStr = JSONUtil.toJsonStr(order);
        long epochSec = now.atZone(java.time.ZoneId.systemDefault()).toEpochSecond();

        //1.执行lua脚本 —— 【八股：为什么Lua脚本可以保证原子性？】
        // Redis是单线程模型，执行命令是串行的
        // Lua脚本会被当作一个整体执行，执行过程中不会被其他命令打断
        // 这就保证了"判断库存→判断是否下单→扣库存→记录订单"这几步是原子的
        // 如果不用Lua，多条命令之间可能被其他线程插入，导致超卖或重复下单
        Long result = stringRedisTemplate.execute(
                SECKILL_SCRIPT,
                Collections.emptyList(),
                voucherId.toString(), userId.toString(), String.valueOf(orderId), jsonStr,
                String.valueOf(epochSec),
                String.valueOf(java.util.concurrent.TimeUnit.MINUTES.toSeconds(
                        RedisConstants.SECKILL_PENDING_ORDER_TTL)),
                order.getAmount().toString()
        );
        //2.判断结果是否为0
        if (result == null) {
            return Result.fail("秒杀服务异常，请稍后重试");
        }
        int r = result.intValue();
        if(r!=0){
            //2.1.不为0，代表没有购买资格
            if (r == -1) return Result.fail("秒杀库存尚未初始化");
            return Result.fail(r==1?"库存不足":"不能重复下单");
        }
        // Redis Lua 已原子写入预订单和订单事件，异步消费者负责落库。
        return Result.ok(orderId);
    }

    @Override
    public VoucherOrder getOrderWithPending(Long orderId) {
        // 1. 先查 DB（真源）
        VoucherOrder order = getById(orderId);
        if (order != null) return order;
        // 2. DB 还未落库：再查 Redis pending 预订单
        try {
            String json = stringRedisTemplate.opsForValue().get(RedisConstants.SECKILL_PENDING_ORDER_KEY + orderId);
            if (json != null && !json.isEmpty()) {
                VoucherOrder pending = JSONUtil.toBean(json, VoucherOrder.class);
                // 合法性兜底：必须有 id/userId/voucherId/status
                if (pending != null && pending.getId() != null
                        && pending.getUserId() != null && pending.getVoucherId() != null
                        && pending.getStatus() != null) {
                    return pending;
                }
            }
        } catch (Exception e) {
            log.warn("读取 pending 预订单异常，orderId={}", orderId, e);
        }
        return null;
    }

    @Override
    public void evictPendingOrder(Long orderId, Long userId) {
        try {
            stringRedisTemplate.delete(RedisConstants.SECKILL_PENDING_ORDER_KEY + orderId);
            if (userId != null) {
                stringRedisTemplate.opsForZSet().remove(
                        RedisConstants.SECKILL_PENDING_USER_KEY + userId, String.valueOf(orderId));
            }
        } catch (Exception e) {
            log.warn("清理 pending 预订单缓存异常，orderId={}", orderId, e);
        }
    }

    // 旧的同步版 seckillVoucher（Redisson tryLock + AopContext.currentProxy 直接落库）
    // 已被上面"Lua 预检 + Stream 异步落库"版本取代，废弃死代码已删除

    /**
     * 创建优惠券订单（真正写数据库的地方）
     *
     * 【八股：乐观锁解决超卖问题】
     * 什么是超卖？
     * - 线程1查库存=1，判断>0，准备扣减
     * - 此时线程2也查库存=1，也判断>0
     * - 两个线程都扣减，结果库存变成-1，超卖了
     *
     * 悲观锁方案：select ... for update，加行锁，串行执行
     * - 优点：简单粗暴，一定不会超卖
     * - 缺点：性能差，并发度低
     *
     * 乐观锁方案：更新时判断条件
     * - 版本号机制：update ... set stock=stock-1 where id=? and version=?
     * - CAS方式：update ... set stock=stock-1 where id=? and stock > 0
     * - 优点：性能好，无锁竞争
     * - 缺点：高并发下成功率低（很多线程抢不到）
     *
     * 本项目用的是 stock > 0 的方式，这是乐观锁的一种变体
     * 因为库存业务只要还有库存就能扣，不需要比较版本号
     *
     * 【八股：@Transactional事务的传播行为】
     * 默认是REQUIRED：有事务就加入，没有就新建
     * 这里createVoucherOrder被handleVoucherOrder调用
     * 但handleVoucherOrder没有事务，所以createVoucherOrder会自己开启事务
     * 注意：必须通过代理对象调用，否则事务不生效
     */
    @Transactional
    public OrderCreationResult createVoucherOrder(VoucherOrder voucherOrder) {
        VoucherOrder existing = getById(voucherOrder.getId());
        if (existing != null) {
            evictPendingOrder(voucherOrder.getId(), voucherOrder.getUserId());
            return OrderCreationResult.ALREADY_PROCESSED;
        }
        // 【八股：设置订单初始状态】
        // 确保订单落库时状态为未支付、时间已记录
        voucherOrder.setStatus(OrderStatus.UNPAID.getCode());
        voucherOrder.setActiveFlag(1);
        if (voucherOrder.getAmount() == null || voucherOrder.getAmount() <= 0) {
            Voucher voucher = voucherService.getById(voucherOrder.getVoucherId());
            if (voucher == null || voucher.getPayValue() == null || voucher.getPayValue() <= 0) {
                throw new IllegalStateException("优惠券支付金额异常");
            }
            voucherOrder.setAmount(voucher.getPayValue());
        }
        if (voucherOrder.getCreateTime() == null) {
            voucherOrder.setCreateTime(LocalDateTime.now());
        }
        //一人一单
        //查询订单
        Long userId =voucherOrder.getUserId();
        // 【场景补丁：取消/退款后重新秒杀的可用性】
        //   Lua 在 Redis 层只做了 SISMEMBER 校验，但取消订单会 SREM Redis + 把 DB 行改为 CANCELLED(4)。
        //   原实现"count>0 就拦"会把历史 CANCELLED/REFUNDED 终态也视为有效单，导致：
        //   秒杀返回成功 → MQ 异步落库被这里静默 return → pending cache 永远是 pending →
        //   前端点"立即支付"就会看到「订单创建中 / 用户已经购买过一次了」。
        //   => 只统计 UNPAID/PAID/VERIFIED/REFUNDING 这 4 种"仍占资格"的状态为有效单。
            int count = query()
                    .eq("user_id", userId)
                    .eq("voucher_id", voucherOrder.getVoucherId())
                    .in("status", Arrays.asList(
                            OrderStatus.UNPAID.getCode(),
                            OrderStatus.PAID.getCode(),
                            OrderStatus.VERIFIED.getCode(),
                            OrderStatus.REFUNDING.getCode()
                    ))
                    .count();
            //判断是否存在
            if (count > 0) {
                //用户已经购买过了
                log.error("用户已经购买过一次了（仍存在 UNPAID/PAID/USED/REFUNDING 的有效单）");
                return OrderCreationResult.ACTIVE_ORDER_EXISTS;
            }
            //扣减库存 —— 【八股：乐观锁防止超卖的核心代码】
            // set stock = stock - 1 扣减库存
            // where voucher_id = ? and stock > 0  只有库存>0时才扣减
            // 这是利用MySQL的行锁 + 条件判断实现的乐观锁
            // 如果多个线程同时执行，MySQL的行锁会保证只有一个能执行成功
            // 其他线程执行时stock已经被减过了，stock>0不成立，更新失败
            boolean success = seckillVoucherService
                    .update()
                    .setSql("stock=stock-1")
                    .eq("voucher_id", voucherOrder.getVoucherId())
                    .gt("stock", 0)
                    .update();
            if (!success) {
                log.error("库存不足");
                return OrderCreationResult.OUT_OF_STOCK;
            }

            try {
                if (!save(voucherOrder)) {
                    throw new IllegalStateException("订单保存失败");
                }
            } catch (DuplicateKeyException duplicate) {
                TransactionAspectSupport.currentTransactionStatus().setRollbackOnly();
                return OrderCreationResult.ACTIVE_ORDER_EXISTS;
            }
            // 落库成功后清理 pending 缓存（DB 为真源，缓存只掩盖异步窗口期）
            evictPendingOrder(voucherOrder.getId(), userId);
            return OrderCreationResult.CREATED;
    }

    // ==================== 交易闭环模块新增方法 ====================

    /**
     * 恢复库存和一人一单记录（取消/退款/超时取消共用）
     *
     * 【八股：为什么取消订单要恢复库存？】
     * 秒杀时Lua脚本做了两件事：
     * 1. Redis库存-1（INCRBY stockKey -1）
     * 2. 记录一人一单（SADD orderKey userId）
     * 取消订单时必须逆向恢复：
     * 1. Redis库存+1（INCR stockKey）→ 让其他用户可以买
     * 2. DB库存+1（stock = stock + 1）→ 保持DB和Redis一致
     * 3. 删除一人一单记录（SREM orderKey userId）→ 让该用户可以重新下单
     *
     * 【八股：Redis和DB库存一致性】
     * 先恢复Redis再恢复DB，因为Redis是第一道防线（Lua脚本先查Redis）
     * 即使DB恢复失败，Redis已经恢复了，用户可以下单
     * DB恢复失败可以通过对账补偿
     */
    private void restoreRedisReservation(Long orderId, Long voucherId, Long userId,
                                         boolean restoreRedisStock,
                                         boolean releaseQualification) {
        SeckillVoucher voucher = seckillVoucherService.getById(voucherId);
        if (voucher == null || voucher.getStock() == null) {
            throw new IllegalStateException("恢复Redis秒杀库存失败，秒杀券不存在或库存为空: " + voucherId);
        }
        Long restored = executeRestoreScript(orderId, voucherId, userId,
                restoreRedisStock, releaseQualification, voucher.getStock());
        if (restored == null) {
            throw new IllegalStateException("恢复Redis秒杀预占失败: orderId=" + orderId);
        }
    }

    private Long executeRestoreScript(Long orderId, Long voucherId, Long userId,
                                      boolean restoreRedisStock,
                                      boolean releaseQualification,
                                      Integer databaseStock) {
        return stringRedisTemplate.execute(
                RESTORE_SECKILL_SCRIPT,
                Collections.emptyList(),
                voucherId.toString(), userId.toString(), orderId.toString(),
                restoreRedisStock ? "1" : "0",
                releaseQualification ? "1" : "0",
                databaseStock.toString()
        );
    }

    // 【八股：为什么用 setIfAbsent 而不是 set 预热库存？】
    // setIfAbsent(=SET NX)：key已存在时不覆盖
    // Redis里的库存是"已扣减后的余量"，若每次请求都用DB全量set覆盖，
    // 会把别人刚扣掉的库存加回来（超卖）；NX保证只在第一次冷启动时初始化
    // 注意已知局限：若DB库存被后台改动，Redis已存在的值不会刷新，需人工对账
    private void ensureRedisStock(Long voucherId, Integer stock) {
        if (stock == null || stock < 0) {
            throw new IllegalStateException("秒杀库存异常");
        }
        stringRedisTemplate.opsForValue().setIfAbsent(
                RedisConstants.SECKILL_STOCK_KEY + voucherId, stock.toString());
    }

    private void restoreStockAndOrderRecord(Long orderId, Long voucherId, Long userId,
                                            boolean restoreDatabaseStock) {
        restoreRedisReservation(orderId, voucherId, userId, true, true);
        if (restoreDatabaseStock) {
            boolean updated = seckillVoucherService.update()
                    .setSql("stock = stock + 1")
                    .eq("voucher_id", voucherId)
                    .update();
            if (!updated) {
                throw new IllegalStateException("恢复数据库库存失败");
            }
        }
    }

    private void saveRedisCompensationEvent(VoucherOrder order) {
        TransactionOutbox event = new TransactionOutbox();
        event.setEventKey("redis-compensation:" + order.getId());
        event.setEventType(TransactionOutboxPublisher.REDIS_COMPENSATION);
        event.setAggregateId(order.getId());
        Map<String, Object> payload = new HashMap<>();
        payload.put("id", order.getId());
        payload.put("userId", order.getUserId());
        payload.put("voucherId", order.getVoucherId());
        event.setPayload(JSONUtil.toJsonStr(payload));
        event.setStatus(0);
        event.setRetryCount(0);
        event.setNextRetryTime(LocalDateTime.now());
        event.setCreateTime(LocalDateTime.now());
        event.setUpdateTime(LocalDateTime.now());
        try {
            outboxMapper.insert(event);
        } catch (DuplicateKeyException duplicate) {
            log.debug("Redis补偿事件已存在: orderId={}", order.getId());
        }
    }

    private void tryRedisCompensation(VoucherOrder order) {
        try {
            restoreStockAndOrderRecord(
                    order.getId(), order.getVoucherId(), order.getUserId(), false);
        } catch (RuntimeException e) {
            log.warn("Redis补偿暂时失败，等待Outbox重试: orderId={}", order.getId(), e);
        }
    }

    @Override
    public void releaseRejectedReservation(VoucherOrder order, boolean restoreRedisStock,
                                           boolean releaseQualification) {
        restoreRedisReservation(order.getId(), order.getVoucherId(), order.getUserId(),
                restoreRedisStock, releaseQualification);
    }

    /**
     * 用户发起支付 —— 委托给PaymentService
     *
     * 【八股：职责分离/迪米特法则】
     * 订单服务不自己实现支付，只做参数组装和转发
     * 好处：支付逻辑的变化（换SDK、加风控、加对账）都在PaymentService内部，
     * 订单服务和Controller不感知——面向接口编程，降低耦合
     * （面试注意：这是简单委托，不必硬套"门面模式"，门面是"聚合多个子系统的复杂调用"）
     */
    @Override
    public Result payOrder(Long orderId, Integer payType) {
        // 构建支付DTO
        PaymentDTO dto = new PaymentDTO();
        dto.setOrderId(orderId);
        dto.setPayType(payType);
        // 委托给支付服务处理
        return paymentService.payOrder(dto);
    }

    /**
     * 查询订单详情（包含优惠券信息）
     *
     * 【八股：为什么不用JOIN SQL而是分两次查？】
     * 1. MyBatis-Plus的Service层不擅长多表JOIN，需要手写XML
     * 2. 两次单表查询性能也不差，且可以利用各自的索引
     * 3. 优惠券信息可以加缓存，减少DB查询
     * 4. 代码可读性更好，不需要写复杂的ResultMap
     */
    @Override
    public Result queryOrderById(Long orderId) {
        // 1. 使用 (DB + Redis pending) 合并逻辑，解决异步落库窗口"订单不存在"
        VoucherOrder order = getOrderWithPending(orderId);
        if (order == null) {
            return Result.fail("订单不存在");
        }
        Long currentUserId = UserHolder.getUser().getId();
        if (!currentUserId.equals(order.getUserId())) {
            return Result.fail("无权查看他人订单");
        }
        // 2. 查询优惠券信息
        Voucher voucher = voucherService.getById(order.getVoucherId());
        // 3. 组装返回数据
        Map<String, Object> data = new HashMap<>();
        data.put("order", order);
        data.put("voucher", voucher);
        // 标记是否来自 pending（未完成异步落库），前端可用于"创建中"展示
        VoucherOrder dbOrder = getById(orderId);
        data.put("pending", dbOrder == null);
        return Result.ok(data);
    }

    /**
     * 查询我的订单（可按状态筛选）
     *
     * 【八股：异步下单后订单列表从哪里来】
     * 订单列表的"真源"是 tb_voucher_order。但在异步落库窗口期（几十ms~几秒），
     * 刚秒杀成功的订单还没写DB，此时从 DB 查询会漏掉 → 用户秒杀完立刻跳 /orders 看不到。
     * 所以这里：
     *   1. 先查 DB（已经落库的真实订单，分页前 10 条）
     *   2. 再拿 Redis pending 索引（还没写 DB 的订单），与 DB 结果去重合并
     *   3. 最终返回的列表不遗漏 pending 订单，且状态筛选仍然生效。
     */
    @Override
    public Result queryMyOrders(Integer status) {
        // 获取当前登录用户
        Long userId = UserHolder.getUser().getId();
        // 1. DB 真实订单分页
        Page<VoucherOrder> page = query()
                .eq("user_id", userId)
                .eq(status != null, "status", status)
                .orderByDesc("create_time")
                .page(new Page<>(1, 10));
        List<VoucherOrder> records = new ArrayList<>(page.getRecords());
        Set<Long> seen = new HashSet<>();
        for (VoucherOrder o : records) seen.add(o.getId());

        // 2. 拼 Redis pending 预订单（只拿最近 20 条，最多补 20 个，避免脏数据）
        try {
            String userPendingKey = RedisConstants.SECKILL_PENDING_USER_KEY + userId;
            java.util.Set<String> pendingIds = stringRedisTemplate.opsForZSet()
                    .reverseRange(userPendingKey, 0, 19);
            if (pendingIds != null && !pendingIds.isEmpty()) {
                for (String idStr : pendingIds) {
                    long oid;
                    try { oid = Long.parseLong(idStr); } catch (Exception ignore) { continue; }
                    if (seen.contains(oid)) continue;
                    String json = stringRedisTemplate.opsForValue().get(
                            RedisConstants.SECKILL_PENDING_ORDER_KEY + oid);
                    if (json == null || json.isEmpty()) continue;
                    VoucherOrder pending = JSONUtil.toBean(json, VoucherOrder.class);
                    if (pending == null || pending.getId() == null
                            || !userId.equals(pending.getUserId()) || pending.getStatus() == null) continue;
                    if (status != null && !status.equals(pending.getStatus())) continue;
                    records.add(0, pending); // pending 订单放最前
                    seen.add(oid);
                }
            }
        } catch (Exception e) {
            log.warn("合并 pending 预订单到我的列表失败，userId={}", userId, e);
        }

        // 总数 = DB 总记录数 + 补齐的 pending 数（保守估计）
        long total = page.getTotal() + (records.size() - page.getRecords().size());

        // 3. 联表 Voucher 补充优惠券展示信息（标题/金额）—— 【为什么不直接 SQL JOIN 查列】
        //    真实工程里订单列表页只需要展示「券标题 + 应付金额」两列，
        //    直接 LEFT JOIN 也能做，但 tb_voucher 字段多 + 与 Redis pending 结果合并口径不一致，
        //    这里用"批量按主键 in 查 Voucher + Map 拼装"的方式更简洁，
        //    且能同时覆盖 DB + pending 两条来源的订单。
        if (!records.isEmpty()) {
            List<Long> voucherIds = records.stream()
                    .map(VoucherOrder::getVoucherId)
                    .filter(Objects::nonNull)
                    .distinct()
                    .collect(Collectors.toList());
            Map<Long, Voucher> voucherMap = Collections.emptyMap();
            if (!voucherIds.isEmpty()) {
                List<Voucher> vouchers = voucherService.listByIds(voucherIds);
                if (vouchers != null && !vouchers.isEmpty()) {
                    voucherMap = vouchers.stream()
                            .collect(Collectors.toMap(Voucher::getId, v -> v, (a, b) -> a));
                }
            }
            // Result 本身是泛型，外层只认 records 数组，所以每条 record 扩展成 Map（order + voucher）
            final Map<Long, Voucher> finalVoucherMap = voucherMap;
            List<Map<String, Object>> enriched = records.stream().map(o -> {
                Map<String, Object> row = new LinkedHashMap<>();
                // 先平铺订单字段 —— 复用 BeanUtil 反射属性拷贝，避免手写 DTO 且避免 JSON 转换的类型问题
                row.putAll(BeanUtil.beanToMap(o));
                Voucher voucher = finalVoucherMap.get(o.getVoucherId());
                row.put("voucher", voucher); // voucher 走 Jackson Long→String 序列化，前端直接读 title/payValue
                return row;
            }).collect(Collectors.toList());
            return Result.ok(enriched, total);
        }

        return Result.ok(records, total);
    }

    /**
     * 手动取消订单
     */
    @Override
    public Result cancelOrder(Long orderId) {
        // 1. 使用 DB+pending 统一入口（解决异步落库窗口下"订单不存在"）
        VoucherOrder order = getOrderWithPending(orderId);
        if (order == null) {
            return Result.fail("订单不存在");
        }
        // 2. 校验当前用户是否是订单所有者
        Long userId = UserHolder.getUser().getId();
        if (!order.getUserId().equals(userId)) {
            return Result.fail("无权操作他人订单");
        }
        CancellationOutcome outcome = cancelInDatabase(order, true);
        if (!outcome.cancelled) {
            VoucherOrder latest = getById(orderId);
            if (latest != null && latest.getStatus() == OrderStatus.CANCELLED.getCode()) {
                saveRedisCompensationEvent(latest);
                tryRedisCompensation(latest);
                return Result.ok();
            }
            String status = latest == null ? "未知" : OrderStatus.of(latest.getStatus()).getDesc();
            return Result.fail("当前订单状态不允许取消: " + status);
        }
        tryRedisCompensation(order);
        evictPendingOrder(orderId, userId);
        log.info("订单已手动取消，orderId={}, userId={}", orderId, userId);
        return Result.ok();
    }

    /**
     * 申请退款 —— 委托给PaymentService
     */
    @Override
    public Result refundOrder(Long orderId) {
        return paymentService.refundOrder(orderId);
    }

    /**
     * 处理超时订单（MQ延迟队列回调）
     *
     * 【八股：延迟队列的幂等性处理】
     * 延迟消息发出后，用户可能在30分钟内已经支付了
     * 消费延迟消息时必须先检查订单状态：
     * - 如果还是UNPAID → 执行取消（恢复库存）
     * - 如果已经PAID → 忽略（用户已支付，不能取消）
     *
     * 这是分布式系统中的幂等性设计：
     * 同一个消息可能被消费多次（网络重试），但业务结果必须一致
     *
     * 【八股：为什么不直接用cancelOrder？】
     * handleOrderTimeout是MQ回调，没有HTTP请求上下文
     * UserHolder.getUser()获取不到用户（没有经过登录拦截器）
     * 所以这里直接从订单中获取userId，不做用户校验
     */
    @Override
    public void handleOrderTimeout(Long orderId) {
        // 1. 查询订单（DB 为空时再看 pending）——解决：异步落库延迟久 + 延迟队列早到 导致的"订单不存在"
        VoucherOrder order = getOrderWithPending(orderId);
        if (order == null) {
            log.warn("超时取消失败，订单不存在: orderId={}", orderId);
            return;
        }
        CancellationOutcome outcome = cancelInDatabase(order, false);
        if (!outcome.cancelled) {
            VoucherOrder latest = getById(orderId);
            if (latest != null && latest.getStatus() == OrderStatus.CANCELLED.getCode()) {
                saveRedisCompensationEvent(latest);
                tryRedisCompensation(latest);
            }
            return;
        }
        tryRedisCompensation(order);
        evictPendingOrder(orderId, order.getUserId());
        log.info("订单超时自动取消成功: orderId={}, userId={}", orderId, order.getUserId());
    }

    private CancellationOutcome cancelInDatabase(VoucherOrder order, boolean manual) {
        return transactionTemplate.execute(status -> {
            int changed = lambdaUpdate()
                    .set(VoucherOrder::getStatus, OrderStatus.CANCELLED.getCode())
                    .set(VoucherOrder::getActiveFlag, null)
                    .set(VoucherOrder::getUpdateTime, LocalDateTime.now())
                    .eq(VoucherOrder::getId, order.getId())
                    .eq(VoucherOrder::getUserId, order.getUserId())
                    .eq(VoucherOrder::getStatus, OrderStatus.UNPAID.getCode())
                    .update() ? 1 : 0;
            if (changed == 1) {
                boolean stockUpdated = seckillVoucherService.update()
                        .setSql("stock = stock + 1")
                        .eq("voucher_id", order.getVoucherId())
                        .update();
                if (!stockUpdated) {
                    throw new IllegalStateException("恢复数据库库存失败");
                }
                saveRedisCompensationEvent(order);
                return new CancellationOutcome(true);
            }

            VoucherOrder current = getById(order.getId());
            if (current != null) {
                int changedAfterInsert = lambdaUpdate()
                        .set(VoucherOrder::getStatus, OrderStatus.CANCELLED.getCode())
                        .set(VoucherOrder::getActiveFlag, null)
                        .set(VoucherOrder::getUpdateTime, LocalDateTime.now())
                        .eq(VoucherOrder::getId, order.getId())
                        .eq(VoucherOrder::getUserId, order.getUserId())
                        .eq(VoucherOrder::getStatus, OrderStatus.UNPAID.getCode())
                        .update() ? 1 : 0;
                if (changedAfterInsert == 1) {
                    boolean stockUpdated = seckillVoucherService.update()
                            .setSql("stock = stock + 1")
                            .eq("voucher_id", order.getVoucherId())
                            .update();
                    if (!stockUpdated) {
                        throw new IllegalStateException("恢复数据库库存失败");
                    }
                    saveRedisCompensationEvent(order);
                    return new CancellationOutcome(true);
                }
                return new CancellationOutcome(false);
            }
            if (order.getCreateTime() == null) {
                order.setCreateTime(LocalDateTime.now());
            }
            int inserted = getBaseMapper().insertCancelledIfAbsent(
                    order, OrderStatus.CANCELLED.getCode());
            if (inserted == 1) {
                saveRedisCompensationEvent(order);
                return new CancellationOutcome(true);
            }
            boolean cancelledAfterConflict = lambdaUpdate()
                    .set(VoucherOrder::getStatus, OrderStatus.CANCELLED.getCode())
                    .set(VoucherOrder::getActiveFlag, null)
                    .set(VoucherOrder::getUpdateTime, LocalDateTime.now())
                    .eq(VoucherOrder::getId, order.getId())
                    .eq(VoucherOrder::getUserId, order.getUserId())
                    .eq(VoucherOrder::getStatus, OrderStatus.UNPAID.getCode())
                    .update();
            if (cancelledAfterConflict) {
                boolean stockUpdated = seckillVoucherService.update()
                        .setSql("stock = stock + 1")
                        .eq("voucher_id", order.getVoucherId())
                        .update();
                if (!stockUpdated) {
                    throw new IllegalStateException("恢复数据库库存失败");
                }
                saveRedisCompensationEvent(order);
            }
            return new CancellationOutcome(cancelledAfterConflict);
        });
    }

    private static final class CancellationOutcome {
        private final boolean cancelled;

        private CancellationOutcome(boolean cancelled) {
            this.cancelled = cancelled;
        }
    }
}
