# 项目面试问答手册

> Interview Q&A
>
> 快评 Java 后端 + 智能推荐 Agent 项目 — 35 道深度面试题参考回答

## 目录

**一、快评项目（Java 后端）**

- 秒杀与交易闭环（Q1-Q5）
- 缓存策略（Q6-Q10）
- 系统防护与鉴权（Q11-Q13）
- Redis 数据结构应用（Q14-Q16）

**二、智能推荐 Agent 项目**

- ReAct 工作流（Q17-Q19）
- 三层记忆架构（Q20-Q23）
- Self-Improvement 机制（Q24-Q25）
- 评测体系（Q26-Q27）

**三、基础知识 & 综合能力（Q28-Q32）**

**四、压力测试 / 开放题（Q33-Q35）**

---

## 一、快评项目（Java 后端）

## 秒杀与交易闭环

### Q1. Redis + Lua 秒杀原子预检：Lua 脚本逻辑？为什么选 Lua 而不是 Redisson 分布式锁？

**Lua 脚本的完整逻辑（4 步原子执行）：**

```lua
-- 1. 参数：voucherId, userId, orderId
-- 2. 构造 key：seckill:stock:{voucherId} 和 seckill:order:{voucherId}

-- Step 1: 判断库存
local stock = tonumber(redis.call('get', stockKey))
if stock == nil then return -1 end   -- 库存未预热
if stock <= 0 then return 1 end      -- 库存不足

-- Step 2: 一人一单判断（SISMEMBER O(1)）
if redis.call('sismember', orderKey, userId) == 1 then
    return 2  -- 重复下单
end

-- Step 3: 扣库存
redis.call('incrby', stockKey, -1)

-- Step 4: 记录订单 + 发消息到 Stream
redis.call('sadd', orderKey, userId)
redis.call('xadd', 'stream.orders', '*', 'userId', userId, 'voucherId', voucherId, 'id', orderId)
return 0  -- 成功
```

返回值约定：-1=库存未预热，0=成功，1=库存不足，2=重复下单。

#### 为什么选 Lua 而不是 Redisson 分布式锁？

两者都能保证原子性，但核心区别在于**性能和实现复杂度**：

- **Lua 脚本**：一次网络往返完成全部操作，Redis 单线程模型保证执行期间不被打断。无锁竞争、无等待、无死锁风险。QPS 可达数万。
- **Redisson 分布式锁**：需要加锁 → 执行业务 → 释放锁，至少 3 次网络往返。高并发下大量线程争抢同一把锁，变成串行执行，吞吐量急剧下降。还有锁续期、锁释放失败等边界问题。

本项目策略是**分层使用**：Lua 脚本做 Redis 层面的原子预检（库存检查 + 一人一单 + 扣库存），这是最高频路径；Redisson 锁只在 MQ 消费端做兜底保护，防止消息重复消费导致的重复下单。这样既保证高性能，又有可靠性兜底。

> **一句话总结：**Lua 脚本是"无锁原子操作"，适合高频的简单判断+操作组合；Redisson 锁是"互斥锁"，适合需要执行复杂业务逻辑（如数据库操作）的场景。本项目两者结合，Lua 做预检、锁做兜底。

### Q2. 一人一单的实现：Redis 里怎么记录用户是否已下单？用什么数据结构？10 万张券的内存问题？布隆过滤器？

**数据结构：Redis Set**

key 为 `seckill:order:{voucherId}`，value 是所有已下单用户的 userId 集合。判断是否重复下单用 `SISMEMBER`，时间复杂度 O(1)，性能极佳。

#### 10 万张券的内存分析

假设 10 万用户参与秒杀，每个 userId 是 Long 类型（8 字节），Set 的 overhead 大约每个元素 50-80 字节（包括指针、 SDS 结构等）。10 万个元素大约占用 **5-8 MB**，对 Redis 来说微不足道（Redis 单实例通常配置几 GB 内存）。所以**在 10 万量级下不需要布隆过滤器**。

#### 什么时候需要布隆过滤器？

- **百万级用户**：Set 占用 50-80 MB，仍然可接受，但可以考虑优化。
- **千万级用户**：Set 占用 500-800 MB，此时布隆过滤器的优势显现——同样数据只需 10-20 MB（约 1/10）。
- **多场秒杀同时进行**：100 个秒杀活动 × 10 万用户 = 1000 万元素，Set 占用 500-800 MB，布隆过滤器只需 ~100 MB。

> **布隆过滤器的代价：**有误判率（false positive），可能把没下过单的用户误判为已下单，导致该用户无法下单。对于秒杀场景，宁可误杀不可超卖，这个代价是可以接受的。但需要权衡——如果误判率太高会影响用户体验。

### Q3. 死信队列超时取消：TTL 设在消息上还是队列上？队头阻塞问题？延迟队列 vs 死信队列怎么选？

**本项目的实现：TTL 同时设置在队列和消息上**

在 `QueueConfig.java` 中，`orderDelayQueue` 同时配置了队列级 TTL（`x-message-ttl = 1800000`，即 30 分钟）和消息级 TTL。两者取较小值生效。实际业务中消息级 TTL 也设为 30 分钟，所以效果一致。

#### TTL 设置在队列上的问题：队头阻塞

队列级 TTL 是**按队列维度统一过期**的。如果用户 A 在 10:00 下单、用户 B 在 10:15 下单，消息按先进先出排列。RabbitMQ 检查 TTL 时**只检查队头消息**：

- 10:30：A 的消息过期，进入死信队列 ✓
- B 的消息本来应该在 10:45 才过期，但由于 A 的消息一直排在前面挡住了，B 的消息在 10:30 才被检查到
- 结果：B 的消息实际在 10:30 就被判定过期了，比预期的 10:45 提前了 15 分钟

这就是**队头阻塞问题**——后面的消息即使先过期，也要等前面的消息过期后才能被处理。

#### 延迟队列（Delay Plugin）vs 死信队列方案对比

| 维度 | 死信队列 + TTL | Delay Plugin |
| --- | --- | --- |
| 额外插件 | 不需要 | 需要安装 |
| 队头阻塞 | 有 | 无 |
| 不同 TTL | 需要为每个 TTL 建一个队列 | 消息级灵活设置 |
| 性能 | TTL 短时性能好 | 延迟消息存在 Mnesia 表，大量消息有性能瓶颈 |

**本项目选死信队列的原因**：不需要额外安装插件，且订单超时时间统一为 30 分钟（所有消息 TTL 相同），队头阻塞不影响正确性——所有消息都在 30 分钟后过期，顺序无差异。如果业务需要不同订单不同超时时间，则应切换到 Delay Plugin。

### Q4. 支付回调幂等性：怎么防止重复处理？用什么机制？

**本项目用「唯一键 + 状态机判断」方案**，在 `PaymentServiceImpl.handlePayNotify()` 中实现：

```java
// 1. 查 PayLog（支付流水记录）
PayLog payLog = payLogService.query().eq("order_id", orderId)...one();

// 2. 幂等性检查：如果 PayLog 已是成功状态(status=2)，直接返回
if (payLog.getStatus() != null && payLog.getStatus() == 2) {
    log.info("支付回调重复处理，PayLog已是成功状态");
    return Result.ok("已处理");  // 幂等返回
}

// 3. 更新 PayLog 状态为成功
payLog.setStatus(2);
payLogService.updateById(payLog);

// 4. 状态机校验：只有 UNPAID → PAID 才允许
OrderStatus currentStatus = OrderStatus.of(order.getStatus());
if (!currentStatus.canTransitionTo(OrderStatus.PAID)) {
    return Result.fail("订单状态不允许支付");
}
order.setStatus(OrderStatus.PAID.getCode());
voucherOrderService.updateById(order);
```

**机制分析：**

- **第一层防护（状态判断）**：检查 PayLog 的 status 字段，如果已经是 2（成功），说明之前处理过了，直接返回成功。这是最核心的幂等手段。
- **第二层防护（状态机校验）**：`canTransitionTo()` 方法确保只有 UNPAID 状态的订单才能转为 PAID。如果回调重复来时订单已经是 PAID，状态机会拒绝转换。

> **为什么不用分布式锁？**分布式锁适合防止并发重复执行，但支付回调的幂等更强调"结果一致"。状态判断 + 状态机校验已经足够：即使两个回调同时到达，数据库的行锁会保证只有一个 UPDATE 成功（另一个因为 status 已变而 affected rows=0）。如果要更严格，可以加唯一索引或乐观锁（`UPDATE ... WHERE status = 1`），让数据库层面保证只更新一次。

### Q5. 订单状态机：完整的状态流转图？哪些转换允许？退款失败状态怎么回滚？

**完整状态流转图：**

```
  ┌──────────┐    支付成功    ┌──────────┐    核销      ┌──────────┐
  │  待支付   │ ──────────→  │  已支付   │ ─────────→  │  已核销   │
  │  UNPAID  │              │   PAID    │             │  VERIFIED │
  └────┬─────┘              └─────┬────┘             └──────────┘
       │                          │                     (终态)
  超时取消                     申请退款
       │                          │
       ▼                          ▼
  ┌──────────┐              ┌──────────┐    退款成功   ┌──────────┐
  │  已取消   │              │  退款中   │ ─────────→ │  已退款   │
  │ CANCELLED│              │ REFUNDING│             │  REFUNDED│
  └──────────┘              └──────────┘             └──────────┘
      (终态)                     │                      (终态)
                           退款失败(回滚)
                                 │
                                 ▼
                            回到 PAID
```

**允许的转换（canTransitionTo 方法）：**

- `UNPAID → PAID`（支付成功）
- `UNPAID → CANCELLED`（超时取消 / 手动取消）
- `PAID → VERIFIED`（核销/消费）
- `PAID → REFUNDING`（申请退款）
- `REFUNDING → REFUNDED`（退款成功）

**不允许的转换：**

- `VERIFIED → 任何状态`：已核销的订单不能退款（已消费）
- `CANCELLED → 任何状态`：终态
- `REFUNDED → 任何状态`：终态
- `PAID → CANCELLED`：已支付的不能直接取消，必须走退款流程

#### 退款失败的状态回滚

当前实现中退款是异步的：`PAID → REFUNDING`（同步改状态）→ 发送 MQ 消息 → 异步处理退款 → 成功则 `REFUNDING → REFUNDED`。如果退款失败（第三方退款 API 返回错误），需要做**状态回滚**：

- 将订单状态从 `REFUNDING` 回滚到 `PAID`
- 通知用户退款失败，可以重新发起退款
- 记录失败原因，供运营人员人工处理

> **改进建议：**可以增加 `REFUND_FAILED` 状态，区分"退款处理中"和"退款失败"，让用户知道退款结果。当前实现如果退款失败，消息会留在 MQ 中重试，达到最大重试次数后进入死信队列，由运营人工处理。

---

## 缓存策略

### Q6. 缓存击穿的逻辑过期方案：逻辑过期字段存在哪？发现过期后怎么处理？怎么保证只有一个线程重建？

**逻辑过期字段存在 Redis 的 value 中**，封装在 `RedisData` 对象里：

```java
class RedisData {
    LocalDateTime expireTime;  // 逻辑过期时间
    Object data;               // 实际数据
}
```

存储时用 `setWithLogicalExpire(key, value, time, unit)`，Redis 本身**不设置 TTL**（永久有效），但 value 里记录了逻辑过期时间。

#### 查询时的处理流程（queryWithLogicalExpire）

1. **查 Redis**：如果缓存未命中，直接返回 null（逻辑过期方案要求缓存预热，不会 miss）
2. **命中，反序列化**：取出 data 和 expireTime
3. **判断是否逻辑过期**：`if (expireTime.isAfter(LocalDateTime.now()))` → 未过期，直接返回数据
4. **已过期**：尝试获取互斥锁 `tryLock(lockKey)`
5. **获取锁成功**：开独立线程（`CACHE_REBUILD_EXECUTOR.submit()`）异步重建缓存，查 DB → 写回 Redis → 更新逻辑过期时间 → 释放锁
6. **获取锁失败**：说明已有其他线程在重建，直接返回旧数据（不等待）
7. **无论是否获取锁**：都返回过期的旧数据给用户

> **核心设计思想：**牺牲一致性换取可用性。用户拿到的是过期数据，但不会因为缓存重建而阻塞等待。只有一个线程持有锁去做重建，其他线程直接返回旧数据。重建完成后锁释放，后续请求拿到的就是新数据了。

### Q7. 缓存穿透的缓存空值：TTL 设多久？恶意打会不会撑爆内存？其他兜底方案？

**空值缓存的 TTL 设为 2 分钟**（`CACHE_NULL_TTL = 2 * 60`），相对较短。原因：

- 空值本身没有业务价值，不应长期占用内存
- 2 分钟足以挡住短时间的恶意攻击（攻击脚本通常在几分钟内探测）
- 如果数据后来被创建了，2 分钟后缓存过期，下次查询会命中 DB 并写入正确值

#### 恶意打大量不存在的 key 会不会撑爆 Redis？

**理论上会**。如果攻击者用 100 万个不同的不存在 key 来打，每个空值缓存即使只有几十字节，也会占用几十 MB 到上百 MB。但实际中：

- Redis 有 `maxmemory` 配置 + 淘汰策略（LRU/LFU），内存满了会自动淘汰
- 可以在网关层做限流，限制单 IP 的请求频率
- 可以对空值缓存加**前缀标记**，定期扫描清理 `null:` 开头的 key

#### 更完善的兜底方案：布隆过滤器

在 Redis 前加一层布隆过滤器，存储所有合法的 key。查询时先过布隆过滤器：

- 布隆过滤器说"不存在" → 直接返回，不查 Redis 也不查 DB
- 布隆过滤器说"存在" → 可能存在（有误判率），继续查 Redis

这样即使攻击者用百万个不存在 key 来打，布隆过滤器会挡掉 99.9% 以上，不会到达 Redis。本项目目前用空值缓存方案，简单够用；如果需要更强的防护，可以叠加布隆过滤器。

### Q8. 缓存雪崩的随机过期时间：怎么加随机？范围多大？互斥锁怎么控制 DB 查询线程数？

**随机过期时间的实现**：在基础 TTL 上加一个随机值

```java
public void set(String key, Object value, Long time, TimeUnit unit) {
    // 基础TTL + 随机1-10分钟
    Random random = new Random();
    long randomTTL = time + random.nextInt(600); // 600秒=10分钟
    stringRedisTemplate.opsForValue().set(key, JSONUtil.toJsonStr(value),
        randomTTL, TimeUnit.SECONDS);
}
```

**随机范围**：在基础 TTL 基础上加 0-10 分钟的随机值。比如基础 TTL 是 30 分钟，实际过期时间在 30-40 分钟之间随机分布。

**目的**：避免大量 key 在同一时刻过期，导致 DB 瞬间承受大量请求。

#### 互斥锁控制 DB 查询线程数

当缓存大量失效时，用**互斥锁**保证同一时间只有一个线程去查 DB，其他线程等待或返回旧数据：

```java
public <R, ID> R queryWithMutex(String keyPrefix, ID id, ...) {
    String key = keyPrefix + id;
    String json = redis.get(key);
    if (StrUtil.isNotBlank(json)) return JSONUtil.toBean(json, type);

    // 缓存未命中
    String lockKey = LOCK_CACHE_KEY + id;
    try {
        boolean isLock = tryLock(lockKey);
        if (!isLock) {
            // 获取锁失败，短暂等待后重试
            Thread.sleep(50);
            return queryWithMutex(keyPrefix, id, ...); // 递归重试
        }
        // 获取锁成功，查 DB 并重建缓存
        R r = dbFallback.apply(id);
        this.set(key, r, time, unit);
        return r;
    } finally {
        unlock(lockKey);
    }
}
```

**锁的实现**：用 Redis 的 `SETNX`（set if not exists），获取锁就是 `setnx lockKey 1`，释放锁就是 `del lockKey`。锁有超时时间防止死锁。同一 key 的查询请求串行化，避免 DB 被打爆。

### Q9. Cache Aside 模式：为什么删缓存而不是更新缓存？为什么不先删再更新 DB？删缓存失败怎么办？

#### 为什么是删除缓存而不是更新缓存？

- **性能**：删除是 O(1) 操作，更新缓存可能涉及复杂计算（如多表 JOIN 聚合），每次写操作都更新缓存浪费资源
- **一致性**：如果一个写操作只修改了部分字段，更新缓存需要重新查全量数据，容易出错；删缓存更简单可靠
- **懒加载**：删缓存后，下次读时自然会触发缓存重建（lazy load），避免频繁更新

#### 为什么不先删缓存再更新 DB？

先删缓存再更新 DB 有**并发不一致**问题：

```
线程A: 删除缓存 → (此时DB还没更新)
线程B:        读缓存(miss) → 读DB(旧值) → 写入缓存(旧值)
线程A: 更新DB(新值)
结果: 缓存是旧值, DB是新值 → 不一致!
```

先更新 DB 再删缓存也有理论上的不一致场景，但概率极低（需要读线程读 DB 拿到旧值后阻塞，写线程更新 DB 并删缓存后，读线程才写入旧值到缓存），且可以通过延迟双删解决。

#### 更新 DB 成功但删缓存失败怎么办？

- **重试机制**：删除失败时重试 3 次，每次间隔递增
- **消息队列补偿**：删除失败时发一条 MQ 消息，消费者异步重试删除
- **binlog 订阅**：用 Canal 订阅 MySQL binlog，发现数据变更后自动删缓存（阿里方案，最可靠但最复杂）
- **缓存 TTL 兜底**：即使删除失败，缓存也有 TTL，过期后自然失效

本项目用**缓存 TTL 兜底** + 简单重试，对于学习项目足够。生产环境建议用 binlog 订阅方案。

### Q10. Redisson 分布式锁：WatchDog 续期机制原理？默认续期时间？线程挂了锁怎么释放？

#### WatchDog 续期机制原理

Redisson 的可重入锁用 Redis Hash 结构存储：`key=锁名, field=线程ID, value=重入次数`。

当调用 `lock.tryLock()` 不指定 leaseTime 时，WatchDog 机制启动：

1. **初始设置**：锁的 TTL 默认 30 秒
2. **定时续期**：每 10 秒（`watchdogTimeout / 3`）检查一次，如果当前线程还持有锁，就续期到 30 秒
3. **循环续期**：只要业务还在执行，锁就一直被续期，不会过期

**默认续期时间**：`lockWatchdogTimeout = 30 秒`，续期间隔 = 30/3 = 10 秒。

> **关键注意：**如果手动指定了 `leaseTime`（如 `lock.tryLock(10, 30, TimeUnit.SECONDS)`），WatchDog **不会启动**，锁会在指定时间后自动过期。这是常见踩坑点。

#### 持有锁的线程挂了，锁会自动释放吗？

**会**。如果线程崩溃，WatchDog 的定时任务也会随之停止（定时任务运行在该线程的上下文中或由该线程的锁持有的引用驱动），不再续期。锁的 TTL 到期后（30 秒），Redis 自动删除该 key，锁释放。其他等待的线程可以获取到锁。

这就是 WatchDog 设计的平衡点：

- 不指定 TTL（用 WatchDog）：业务没执行完时锁不会过期（防止误释放），线程挂了 30 秒后自动释放（防止死锁）
- 指定 TTL：确定业务能在指定时间内完成，不需要续期，简单高效

---

## 系统防护与鉴权

### Q11. 三态熔断器：滑动窗口怎么实现？窗口大小？半开状态怎么探测？放多少请求？

#### 滑动窗口的实现（简化版）

本项目用**简化版滑动窗口**：记录 `lastFailureTime`（上次失败时间），每次请求时检查 `now - lastFailureTime > slidingWindow`，如果超过窗口大小就重置计数器。

```java
private void checkAndResetSlidingWindow(BreakerInfo breaker, CircuitBreaker cb) {
    long now = System.currentTimeMillis();
    if (breaker.getLastFailureTime() > 0 &&
            now - breaker.getLastFailureTime() > cb.slidingWindow()) {
        breaker.resetCounters(); // 窗口过期，重置计数
    }
}
```

**窗口大小**：通过注解 `@CircuitBreaker(slidingWindow = 60000)` 配置，默认 60 秒。即只统计最近 60 秒内的失败次数。

**精确版滑动窗口**：可以用环形数组（Ring Buffer）记录每个请求的时间戳，查询时过滤窗口外的请求。或者用 Redis ZSet（score=时间戳），`ZREMRANGEBYSCORE` 清理旧数据后 `ZCARD` 统计。

#### 半开状态怎么探测

**只放行 1 个探测请求**：

```java
if (state == BreakerState.HALF_OPEN) {
    // CAS 保证只有一个线程能设 probeSent=true
    if (!breaker.getProbeSent().compareAndSet(false, true)) {
        return doFallback(joinPoint, circuitBreaker); // 其他请求降级
    }
    log.info("放行探测请求");
}
// 执行原方法
try {
    Object result = joinPoint.proceed();
    // 探测成功 → CLOSED
    breaker.getState().set(BreakerState.CLOSED);
    breaker.resetCounters();
} catch (Exception e) {
    // 探测失败 → 重新 OPEN
    breaker.getState().set(BreakerState.OPEN);
    breaker.setOpenTime(System.currentTimeMillis());
}
```

**为什么只放 1 个？**如果放多个，万一服务还没恢复，大量探测请求又会失败，造成二次伤害。只放 1 个，成功才完全恢复，失败就继续熔断。

**状态转换**：CLOSED →（失败次数达阈值）→ OPEN →（超过 recoveryTimeout）→ HALF_OPEN →（探测成功）→ CLOSED /（探测失败）→ OPEN

### Q12. Guava RateLimiter 限流：令牌桶 vs 漏桶？为什么选令牌桶？突发流量怎么处理？

#### 令牌桶 vs 漏桶算法对比

| 维度 | 令牌桶 | 漏桶 |
| --- | --- | --- |
| 核心思想 | 匀速生成令牌，请求消耗令牌 | 请求先进队列，匀速流出 |
| 突发流量 | 允许突发（可预消费） | 不允许突发（匀速流出） |
| 队列 | 无队列，拿不到令牌直接拒绝 | 有队列，排队等待 |
| 适用场景 | 秒杀（允许短暂突发） | 流量整形（匀速消费） |

**为什么选令牌桶？**秒杀场景下流量是突发的——开抢瞬间大量请求涌入，之后迅速衰减。令牌桶允许突发流量，在桶里有积攒令牌时可以一次性消耗多个令牌，更适合这种场景。漏桶强制匀速，会导致开抢瞬间大量请求被拒绝。

#### 令牌桶的预消费机制

Guava RateLimiter 的 `tryAcquire()` 实现：

- 每秒生成 `qps` 个令牌（如 50 QPS = 每秒 50 个令牌）
- 令牌可以积攒（最多积攒 1 秒的量，即 50 个）
- 突发流量来时，如果桶里有 50 个积攒令牌，可以一次性消耗 50 个，相当于允许 1 秒的突发流量
- 令牌用完后，后续请求只能按每秒 50 个的速度获取令牌

这就是**预消费**：允许当前请求"借"未来一小段时间的令牌，应对突发流量。

### Q13. 双层拦截器：RefreshTokenInterceptor 和 LoginInterceptor 分别做什么？为什么要拆两层？每次查 Redis 的性能问题？

#### 两层拦截器的职责

- **第一层 RefreshTokenInterceptor（order=0）**：拦截所有路径（`/**`）。有 Token 就解析用户存入 ThreadLocal + 刷新 Token 有效期 30 分钟。没有 Token 也放行，不做登录校验。
- **第二层 LoginInterceptor（order=1）**：只拦截需要登录的路径（如 `/order/**`、`/user/info`）。检查 ThreadLocal 里有没有用户，没有就返回 401。

#### 为什么要拆两层？

如果只有一层登录拦截器：**用户浏览商铺（不需要登录的路径）时 Token 不会被刷新**。用户浏览了 30 分钟后点"下单"，Token 已过期被拦截，直接掉线。体验很差。

拆成两层后：第一层拦截所有请求，只要有 Token 就刷新，用户一直在浏览就一直有效。第二层只负责校验登录状态，不查 Redis（从 ThreadLocal 取，第一层已经存好了）。

#### 每次请求都查 Redis 的性能问题

确实有性能开销：每个请求查一次 Redis（`HGETALL`），Redis 响应时间通常 0.5-2ms，对于普通 Web 请求可以接受。

**优化方案（如果需要）：**

- **本地缓存**：用 Caffeine 缓存 Token → UserDTO 映射，TTL 30 秒。同一个 Token 30 秒内不查 Redis。但缺点是 Token 失效后最长 30 秒延迟才感知到（如用户主动退出登录）
- **JWT 替代 Redis Session**：Token 本身包含用户信息（签名验证），不需要查 Redis。但缺点是无法主动让 Token 失效（黑名单机制增加复杂度）
- **批量查询**：不适用单请求场景

> **当前方案的选择理由：**Redis 查询 1ms 左右，对于本项目 QPS（几百到几千）完全不是瓶颈。引入本地缓存会增加一致性问题（用户退出后本地缓存还认为有效），得不偿失。等 QPS 真到瓶颈时再优化。

---

## Redis 数据结构应用

### Q14. GEO 附近商铺：底层实现什么数据结构？按距离排序原理？能查"3 公里内评分最高的 10 家店"吗？

#### 底层实现：GeoHash + ZSet

Redis GEO 底层用 **ZSet** 实现，member 是商铺 ID，score 是 **GeoHash 编码值**。GeoHash 将二维经纬度编码成一维整数，使得地理位置相近的点，其 GeoHash 编码也相近。

GeoHash 编码原理：将经纬度分别做二分编码，然后交叉组合，形成一个 52 位整数。编码的前缀相同意味着在同一个网格区域内。

#### 按距离排序的原理

`GEOSEARCH` 命令的实现：

1. 根据中心点坐标计算 GeoHash 范围（确定搜索的网格区域）
2. 从 ZSet 中取出该范围内的所有商铺
3. 用 Haversine 公式精确计算每个商铺到中心点的球面距离
4. 按距离排序后返回

#### 能直接查"3 公里内评分最高的 10 家店"吗？

**不能直接做到**。GEO 只支持按距离排序（`ASC` / `DESC`），不支持按评分排序。需要**二次过滤**：

- 方案 1：用 `GEOSEARCH BYRADIUS 3 km COUNT N` 取出 3 公里内的商铺，然后在应用层按评分排序取 Top 10
- 方案 2：用 Redis ZSet 单独存储商铺评分（score=评分，member=商铺 ID），先从 GEO 取出 3 公里内的 ID，再用 `ZREVRANGEBYSCORE` 按评分排序
- 方案 3（推荐）：用 Elasticsearch 做复合查询，同时按距离过滤 + 评分排序，效率最高

### Q15. BitMap 签到：连续签到天数怎么用位运算算？

#### 数据结构：BitMap

用 Redis BitMap 存储用户签到记录，key 为 `sign:{userId}:{yyyyMM}`，每月一个 BitMap。第 N 位表示当月第 N 天是否签到（1=签到，0=未签到）。

写入签到：`SETBIT sign:1010:202608 3 1`（8 月 3 号签到）

#### 连续签到天数的位运算思路

以 8 月 3 号为例，计算从 7 月 28 号到 8 月 3 号连续签到了多少天：

```java
// 1. 取本月签到数据（8月1-3号）
Long augustBits = stringRedisTemplate.opsForValue()
    .bitOperations("sign:1010:202608").get(); // BITFIELD sign:... GET u3 0

// 2. 取上月签到数据（7月28-31号）
Long julyBits = stringRedisTemplate.opsForValue()
    .bitOperations("sign:1010:202607").get(); // BITFIELD sign:... GET u4 27

// 3. 拼接：7月28-31 + 8月1-3 → 7位
// 7月部分: bit 28,29,30,31 → 对应拼接后的 bit 0,1,2,3
// 8月部分: bit 1,2,3 → 对应拼接后的 bit 4,5,6

// 4. 位运算：从最低位开始，遇到第一个0就停止
int count = 0;
long combined = (julyBits << 3) | augustBits; // 拼接
while ((combined & 1) != 0) {
    count++;
    combined >>>= 1;
}
// count = 连续签到天数
```

**核心位运算**：从最低位（今天）开始，逐位右移检查。遇到 1 就计数，遇到 0 就停止。这样就能算出从今天往前连续签到了多少天。

> **为什么用 BitMap？**一个用户一个月只需 31 位 = 4 字节存储，1 亿用户每月签到数据仅约 400 MB。相比用数据库表存储，节省 100 倍以上空间。

### Q16. ZSet 点赞排行榜：score 是什么？同一时间点赞的两个人怎么排？时间维度怎么处理？

#### ZSet 数据结构设计

key 为 `blog:liked:{blogId}`，member 是 userId，score 是**时间戳**（点赞的时间）。

```java
// 点赞时写入
stringRedisTemplate.opsForZSet().add(
    "blog:liked:" + blogId, userId.toString(), System.currentTimeMillis()
);
```

score 用时间戳，`ZREVRANGEBYSCORE` 或 `ZRANGE` 按时间排序：

- score 升序排列（`ZRANGE`）→ 最早点赞的排在前面
- score 降序排列（`ZREVRANGE`）→ 最新点赞的排在前面

#### 同一时间点赞的两个人怎么排？

**时间戳精度问题**：`System.currentTimeMillis()` 是毫秒级，两个人在同一毫秒点赞的概率很低。但如果确实同时（如高并发场景），ZSet 的排序规则是**先按 score 排，score 相同时按 member 的字典序排**。所以同一毫秒点赞的用户，会按 userId 的字符串大小排序。

#### 如果要"最新点赞排在前面"怎么做？

- score 用时间戳，取 `ZREVRANGE`（降序）即可让最新点赞的排前面
- 如果需要点赞数排行（不是时间排行），应该用另一个 ZSet：score=点赞数，member=博客 ID
- 两个 ZSet 职责分离：一个管"谁点了赞+时间"，一个管"哪个博客点赞最多"

> **为什么用 ZSet 而不是 Set？**Set 只能判断"是否已点赞"（SISMEMBER），但无法排序。ZSet 在 Set 基础上增加了 score，既能判断存在（ZSCORE 返回 null 表示不存在），又能按时间排序（ZRANGE），一物两用。

---

## 二、智能推荐 Agent 项目

## ReAct 工作流

### Q17. LangGraph 8 节点状态图：8 个节点分别是什么？条件路由怎么判断？最多 3 轮重规划超过了怎么办？

#### 8 个节点及状态流转图

```
  load_memory → plan → execute → evaluate
                                   │
                          ┌────────┼────────┐
                          ▼        ▼        ▼
                     interrupt   generate  replan
                     (END)         │     (→ plan)
                                   ▼
                                reflect
                                   │
                              ┌────┴────┐
                              ▼         ▼
                           replan      log
                          (→ plan)   (→ END)
```

**8 个节点**：

1. `load_memory`：加载用户长期记忆 + 会话上下文摘要 + Playbook 经验库
2. `plan`：LLM 分析用户意图，选择工具调用策略（调用哪些工具、参数是什么）
3. `execute`：执行工具调用（6 个白名单工具），获取商铺候选集
4. `evaluate`：评估候选集是否充分（品类匹配？数量够？需要追问用户？）
5. `generate`：生成推荐结果 + matchReason + 格式化输出
6. `reflect`：反思推荐质量，自评打分，蒸馏经验
7. `update_memory`：更新用户偏好记忆 + 会话上下文
8. `log_trajectory`：记录完整执行轨迹，供评测和 Playbook 改进使用

#### 条件路由判断（routing.py）

evaluate 之后有 3 条路径：

```python
def should_hitl(state) -> str:
    if hitl_needed:
        return "interrupt"      # 信息不足，中断等待用户补充
    elif evaluation == "sufficient":
        return "generate"        # 候选集充分，生成推荐
    elif iteration_count >= MAX_ITERATIONS:  # 最多3轮
        return "generate"       # 超过上限，强制生成
    else:
        return "replan"          # 重新规划
```

reflect 之后有 2 条路径：如果 `should_replan=True` → 回到 plan 重新规划；否则 → log_trajectory → END。

#### 超过 3 轮怎么办？

当 `iteration_count >= 3` 时，不再重新规划，直接跳到 `generate` 强制生成推荐。这样防止 Agent 陷入无限循环。同时会记录"因达到最大迭代次数而强制生成"的标记，供后续反思和评测分析。

### Q18. HITL 人工接管：中断状态存了什么？为什么不用 LangGraph 的 checkpoint？恢复时从断点继续还是从头？

#### Redis 存储的中断状态

中断时将整个 `AgentState` 序列化存入 Redis，key 为 `agent2:interrupt:{thread_id}`：

```json
{
    "user_message": "找附近火锅",
    "user_id": 1010,
    "user_x": 120.17, "user_y": 30.31,
    "thread_id": "xxx",
    "iteration_count": 1,
    "hitl_needed": true,
    "hitl_question": "您的预算范围是多少？",
    "tool_results": [...],        // 已执行的工具结果
    "candidate_shops": [...],     // 已获取的候选商铺
    "conversation_summary": "...",
    "playbook_context": "..."
}
```

#### 为什么不用 LangGraph 的 checkpoint 机制？

- **可控性**：LangGraph 的 checkpoint 是框架内部的，存储格式和生命周期不由我们控制。自定义 Redis 存储可以精确控制存什么、存多久、何时清理
- **查询方便**：自定义存储可以直接通过 Redis 命令查询中断状态（如"有多少中断的会话"），checkpoint 不方便做这种查询
- **解耦**：中断后的恢复可能需要跨进程、跨服务，自定义存储不依赖 LangGraph 运行时状态
- **业务定制**：需要在中断状态中附加业务字段（如 hitl_question），checkpoint 的格式不一定支持

#### 恢复时从断点继续还是从头？

**从断点继续**。具体来说是从 `plan` 节点继续执行——因为 HITL 中断发生在 evaluate 之后，用户补充信息后需要重新 plan（带着新的用户输入重新规划）。但之前 execute 阶段获取的候选商铺会保留在 state 中，不会重新查（除非 plan 决定换工具）。这比从头开始高效得多。

### Q19. 工具调用：6 个白名单工具分别是什么？参数是 LLM 生成的吗？格式不对怎么处理？

#### 6 个白名单工具

1. **search_by_category**：按品类搜索商铺（参数：typeId, x, y, limit）
2. **search_by_keyword**：按关键词全文搜索（参数：keyword, x, y, limit）
3. **search_nearby**：按距离搜索附近商铺（参数：x, y, radius, limit）
4. **get_shop_detail**：获取商铺详情（参数：shopId）
5. **get_shop_reviews**：获取商铺评价（参数：shopId, limit）
6. **filter_by_tags**：按标签过滤商铺（参数：tags, shopIds）

#### 参数是 LLM 生成的吗？

**是的**。在 plan 节点，LLM 根据用户消息 + 上下文，输出一个 JSON 格式的工具调用计划：

```json
{
    "tool": "search_by_category",
    "params": {"typeId": 1, "x": 120.17, "y": 30.31, "limit": 20},
    "reasoning": "用户想找火锅，先按美食品类搜索"
}
```

#### 参数格式不对怎么处理？

本项目用**多层防御**处理 LLM 输出格式问题：

1. **JSON 解析容错**：`_parse_llm_json()` 先尝试标准 JSON 解析，失败后用正则提取 `{...}` 部分重试
2. **参数类型校验**：Pydantic 模型自动校验参数类型，typeId 传了字符串会自动转为 int
3. **默认值兜底**：如果必填参数缺失，使用合理默认值（如 limit 默认 10）
4. **重规划机制**：如果工具执行失败（如 typeId 不存在），evaluate 节点会判定为"不充分"，触发 replan 让 LLM 重新选择工具和参数

> **关键设计：**不要完全信任 LLM 的输出。每个工具的参数都有 schema 约束，LLM 的输出只是"建议"，最终执行前要过一道类型检查和范围校验。这是 Agent 系统的通用设计原则。

---

## 三层记忆架构

### Q20. 短期记忆 vs 长期记忆：为什么把数值信息独立存储？LLM 上下文里不是已经有了吗？遇到过什么数值丢失问题？

#### 短期记忆的结构

短期记忆存储两部分：**会话上下文摘要**（bullet points 格式，注入 plan prompt）+ **上一轮推荐商铺的结构化快照**（独立存储在 Redis）。

结构化快照的格式：

```json
[{"name": "海底捞", "avgPrice": 150, "score": 45, "distance": 1.2},
 {"name": "小肥羊", "avgPrice": 120, "score": 42, "distance": 2.5}]
```

#### 为什么要把数值独立存储？

因为 **LLM 压缩摘要时会丢失精确数值**。具体场景：

- 用户说"上次推荐的火锅太贵了，有没有便宜点的"——Agent 需要知道上次推荐的精确价格来做比较
- 如果只依赖压缩摘要，摘要里可能只写了"推荐了海底捞"，价格信息在压缩过程中被丢弃了
- LLM 压缩策略明确要求"涉及已推荐内容时，保留店名即可，价格/评分/距离通过结构化数据单独提供"——就是为了避免数值在压缩中丢失

> **实际遇到过的问题：**在一次测试中，用户说"上次推荐的店比这次近吗？"，Agent 无法回答，因为压缩摘要里只写了店名，距离信息丢失了。改为结构化独立存储后，Agent 可以精确比较"上次 1.2km，这次 0.8km，确实更近"。

### Q21. Playbook 经验库：条目是什么格式？Reflector 怎么蒸馏规则？举个例子？

#### Playbook 条目格式

每条条目是**结构化 JSON**，包含 category + description + confidence：

```json
{
    "entryId": "a1b2c3d4e5f6",
    "category": "intent_parsing",      // 5个分类之一
    "description": "用户提及环境偏好时，将其作为关键筛选条件过滤商铺",
    "confidence": 0.8,                 // 0.0-1.0
    "source": "reflection",            // 来源
    "timesApplied": 3,                 // 被应用次数
    "timesHelpful": 2                  // 被认为有效的次数
}
```

5 个 category 分类：`intent_parsing`（意图解析）、`tool_selection`（工具选择）、`hitl_trigger`（HITL 触发时机）、`ranking`（排序策略）、`context_gap`（上下文盲区）。

#### Reflector 蒸馏流程

每次推荐完成后，`reflect` 节点将完整的执行轨迹（用户消息、推荐结果、HITL 是否触发、迭代次数、评分等）交给 LLM，用专门的 REFLECT_PROMPT 提取**可执行的操作规则**（而非描述性总结）。

蒸馏 prompt 的核心要求：

- 必须是"可被下次执行直接遵循的规则"，不是描述失败原因
- 必须是"跨用户通用的操作经验"，不针对特定用户

#### 具体例子

**场景**：用户说"找个安静的地方喝咖啡"，Agent 直接推荐了 3 家咖啡店，但用户不满意"不是说安静的吗？"。Reflector 分析后生成：

```json
{
    "category": "intent_parsing",
    "description": "用户提及环境偏好（如安静、氛围好）时，应将其作为关键筛选条件过滤商铺，而不仅仅是按品类搜索",
    "confidence": 0.7
}
```

Curator 检查是否已有相似条目，如果没有就新增。下次用户说"安静的地方"，这条规则会被 RAG 检索出来注入 plan prompt，Agent 就会优先用 `filter_by_tags` 工具按"安静"标签过滤。

### Q22. ChromaDB 语义检索：K 值取多少？怎么确定？不相关条目会不会干扰？阈值过滤？

#### K 值设置

K 值（注入条目数）默认取 **8**（`top_k=8`），通过 `get_context_rag()` 方法的 `top_k` 参数控制。

**确定方式**：通过实验调优。测试了 3、5、8、12 四个值：

- K=3：太少，经常遗漏相关规则，Agent 表现和不加 Playbook 差别不大
- K=5：可以，但有些复杂场景（多条件推荐）信息不够
- K=8：效果最好，覆盖了大部分相关规则，又不会 token 膨胀
- K=12：开始出现不相关条目，LLM 反而被干扰，推荐质量下降

#### 不相关条目会不会干扰 LLM？

**会**，这是 RAG 系统的通病。本项目用**混合评分机制**缓解：

```python
# 混合评分 = 语义相似度 × 0.7 + 置信度 × 0.3
sim = max(0.0, 1.0 - distance)  # Chroma cosine distance → 相似度
combined = sim * 0.7 + entry.confidence * 0.3

# 未被检索到的条目，仅用低权重置信度
combined = entry.confidence * 0.15
```

语义相似度权重 70%，置信度权重 30%。这样既考虑了相关性（Chroma 向量检索），又考虑了规则的历史有效性（confidence 基于 timesHelpful/timesApplied 计算）。

#### 阈值过滤

当前实现**没有做硬性阈值过滤**，而是用混合评分排序取 Top-K。原因：

- 如果设阈值（如 sim > 0.5），可能导致某些用例完全没规则注入，退化为无 Playbook
- Playbook 条目数量目前不多（几十条），即使有少量不相关的条目，LLM 通常能忽略
- 未来可以增加软阈值：sim < 0.2 的条目直接丢弃，只保留低权重但不完全排除

### Q23. 消融实验："移除 Playbook 后 66% 用例退化为 HITL 中断"这个结论怎么得出的？实验设计？为什么退化为 HITL 就说明 Playbook 有价值？

#### 实验设计

用 `run_ablation()` 方法运行 5 组实验：Baseline（全部模块）+ 4 个消融变体（移除 Playbook / 移除 Memory / 移除 Conversation / 移除 HITL）。

每组实验用**同一套 12 个测试用例**（DEFAULT_CASES），涵盖吃/喝/玩/乐/容错 5 个品类。消融通过 monkey-patch 临时替换模块函数实现：

```python
# no_playbook 变体：把 playbook.get_context 替换为空返回
async def empty_context(*a, **kw):
    return "(暂无历史经验)"
patch_targets = [(pb.playbook, "get_context", empty_context)]
```

对比指标：passRate（通过率）、avgRelevanceScore（LLM-Judge 相关性评分）、avgHitlRate（HITL 触发率）、avgCandidateCount（候选数量）。

#### "66% 退化为 HITL 中断"的含义

Baseline 中 12 个用例有 ~4 个直接产生推荐（不需要 HITL）。移除 Playbook 后，其中 ~8 个用例（66%）的 Agent 在 evaluate 节点判断为"信息不足"，触发 HITL 中断向用户追问，而不是直接推荐。

#### 为什么退化为 HITL 就说明 Playbook 有价值？

因为 Playbook 提供的是**跨用户通用的操作经验**，让 Agent 在信息不完全时也能做出合理决策。例如 Playbook 中有一条"用户未指定预算时，默认搜索 100-300 元价格区间"的规则。有这条规则时，Agent 会直接推荐；没有时，Agent 不确定价格范围，就触发 HITL 追问"您的预算是多少？"

> **面试官可能的追问：**"有没有可能 Playbook 让 Agent 更激进了，反而降低了推荐质量？"——这个可能性确实存在。Playbook 规则可能让 Agent 在不该推荐的时候也推荐了。消融实验通过 LLM-as-Judge 的 avgRelevanceScore 评分来验证：Baseline 的相关性评分是否高于 no_playbook 变体。如果 Baseline 评分更高，说明 Playbook 不仅让 Agent 更果断，而且推荐质量也更好。

---

## Self-Improvement 机制

### Q24. Reflector-Curator 自评：评分标准是什么？低于多少分触发蒸馏？自评不准怎么办？

#### 评分标准

reflect 节点让 LLM 对本次推荐打分，评分维度包括：

- **意图匹配度**：推荐是否匹配用户的品类/偏好/意图
- **候选充分性**：候选商铺数量是否足够
- **HITL 必要性**：是否在不必要的时候触发了 HITL
- **理由质量**：matchReason 是否有说服力

综合评分 0-10 分，存储在 `reflectionScore`。

#### 触发蒸馏的阈值

当 `reflectionScore < 7` 或推荐执行中有异常（如 HITL 触发、迭代超过 2 轮、候选数量不足），触发 reflect 蒸馏流程。也有些规则是在**成功**时蒸馏的——"什么做得好"也是经验。

#### 自评不准怎么办？

这是 LLM 自评的核心问题。本项目的缓解措施：

1. **置信度校准**：Playbook 条目的 confidence 不是 LLM 直接给的，而是通过 `timesHelpful / timesApplied` 计算——只有被多次应用且确实有效时，confidence 才会升高
2. **去重精炼**：`deduplicate()` 方法定期清理重复和低质量条目，防止 context collapse（规则膨胀到不可用）
3. **上限控制**：Playbook 最多 200 条（`PLAYBOOK_MAX_ENTRIES = 200`），超过就按 confidence 排序裁剪
4. **外部验证**：评测体系的 LLM-as-Judge 是独立评分（不是自评），可以作为客观验证手段

> **更彻底的方案：**引入用户反馈（点赞/踩）作为 ground truth，替代 LLM 自评。如果用户对推荐点了踩，说明推荐确实不好，直接触发 reflect 蒸馏。这是最可靠的信号，但需要前端支持。

### Q25. 自改进循环：propose-evaluate-accept 流程？LLM 能改什么不能改什么？怎么防止改坏？回滚机制？

#### propose-evaluate-accept 流程

本项目的自改进不是让 LLM 直接改代码，而是**演进上下文（Playbook）**：

1. **Propose（提议）**：Reflector 从执行轨迹中蒸馏出新的操作规则（propose 新的 Playbook 条目）
2. **Evaluate（评估）**：Curator 检查新规则是否与已有条目重复（description 去重），评估合理性
3. **Accept（接受）**：如果不重复，加入 Playbook；如果重复，增加已有条目的 confidence（+0.1，上限 1.0）

#### LLM 能改什么？不能改什么？

**能改的（Playbook 层面）：**

- 新增操作规则（如"环境偏好应优先于价格筛选"）
- 调整已有规则的置信度
- 触发 HITL 的时机判断
- 排序策略的权重建议

**不能改的（系统层面）：**

- 工具定义和参数 schema（代码层面，LLM 不能改）
- 状态机的流转逻辑（routing.py，硬编码）
- 系统 prompt 的核心指令
- 数据库结构

#### 怎么防止改坏？回滚机制？

- **置信度衰减**：confidence = timesHelpful / timesApplied。如果一条规则被应用了 10 次但只有 2 次有效，confidence = 0.2，排名靠后，几乎不会被注入 prompt
- **自然淘汰**：当 Playbook 超过 200 条上限时，按 confidence 排序裁剪，低质量规则自动被淘汰
- **MySQL 持久化**：所有 Playbook 条目存 MySQL（source of truth），可以查历史记录做审计
- **消融实验验证**：定期跑 ablation 实验对比 Baseline，如果 passRate 下降说明改进有问题，可以回滚到之前的 Playbook 快照

> **回滚机制改进方向：**当前没有自动回滚。可以增加"版本号"机制——每次 Playbook 变更记录版本号，如果新版本的评测 passRate 低于旧版本，自动回滚到上一版本。

---

## 评测体系

### Q26. LLM-as-Judge：评分 prompt 怎么设计？怎么保证一致性？同一输入评两次分不一样怎么办？

#### 评分 prompt 设计

```
你是推荐质量评估器。对以下推荐打分（1-5）。

用户请求: {query}
推荐结果: {shops}

评分维度:
- relevance: 推荐是否匹配用户的品类/偏好/意图（1=完全不匹配, 5=完全匹配）
- diversity: Top-3 是否覆盖不同类型的选项（1=同质化, 5=多样化）
- reasoning: matchReason 是否有说服力和个性化（1=敷衍模板, 5=有理有据）

只输出 JSON: {"relevance": 4, "diversity": 3, "reasoning": 4}
```

**设计要点**：

- 每个维度有明确的 1-5 分锚点定义（1 分是什么样，5 分是什么样）
- 只输入店铺名、价格、matchReason（前 80 字），控制 token 消耗
- 要求输出纯 JSON，方便解析

#### 怎么保证一致性和稳定性？

1. **固定 prompt**：prompt 模板固定不变，不包含随机示例（few-shot 的示例会引入偏差）
2. **结构化输出**：要求输出 JSON 格式，减少 LLM 自由发挥的空间
3. **temperature=0**：LLM 调用时设置低 temperature，降低随机性
4. **多次采样取均值**：对同一输入评 3 次取平均值（牺牲性能换稳定性）

#### 同一输入评两次分不一样怎么办？

这是 LLM 评分的固有缺陷。缓解措施：

- 分数差距在 ±1 分以内视为正常波动（4 分和 3 分差异不大）
- 如果差距 ≥ 2 分（如一次 2 分一次 4 分），说明评分标准不够明确，需要优化 prompt 的锚点定义
- 可以引入"评审组"机制：多个 LLM（如 GPT-4 + Claude）各评一次，取共识

### Q27. 双层评测体系：Layer 1 规则有哪些？Layer 1 过但 Layer 2 低分说明什么？反过来呢？

#### Layer 1 结构化回归检查规则

1. **品类匹配**（`_check_category`）：推荐的商铺名或 matchReason 是否包含期望品类关键词。如期望"美食"，推荐"海底捞"→ 匹配
2. **价格范围**（`_check_price`）：推荐商铺的价格是否在期望范围内。如期望 100-300 元，推荐 ¥150 → 匹配
3. **HITL 评分**（`_calc_hitl_score`）：HITL 触发次数越少越好，但不应始终为 0（合理 HITL 是必要的）
4. **结果数量**：推荐商铺数 ≥ minExpectedResults

综合判定：`len(shops) >= minExpectedResults AND categoryScore >= 0.5`

#### Layer 1 过但 Layer 2 低分说明什么？

**说明推荐结构正确但语义质量差**。例如：

- Layer 1 检查品类匹配"美食" → 推荐了"肯德基"→品类匹配 ✓
- 但 Layer 2 LLM-as-Judge 发现：用户说"找个安静的地方聚餐"，肯德基虽然品类对但不适合聚餐，relevance 打 2 分
- 说明 Agent 能按品类搜到商铺，但**对用户深层意图的理解不够**

#### Layer 2 高分但 Layer 1 不过说明什么？

**说明推荐看似合理但不符合规则约束**。例如：

- Layer 2 LLM-as-Judge 觉得推荐质量不错，relevance 打 4 分
- 但 Layer 1 检查发现推荐数量不足（minExpectedResults=3，实际只有 1 个）→ 不过
- 说明 Agent 的推荐方向对，但**候选集获取能力不够**（可能工具调用参数太严格，过滤掉了太多结果）

> **设计意义：**两层评测互补——Layer 1 保证"基础正确性"（品类对、数量够），Layer 2 保证"语义质量"（推荐合理、理由充分）。只有两层都过的推荐才是真正好的推荐。

---

## 三、基础知识 & 综合能力

### Q28. MySQL 索引优化：B+ 树 vs Hash 索引？索引失效场景？最左前缀原则？覆盖索引？

#### B+ 树索引 vs Hash 索引

| 维度 | B+ 树 | Hash 索引 |
| --- | --- | --- |
| 结构 | 多叉平衡树，叶子节点有序链表 | 哈希表，key→value |
| 范围查询 | 支持（叶子链表遍历） | 不支持 |
| 排序 | 支持 ORDER BY | 不支持 |
| 等值查询 | O(log n) | O(1) 更快 |
| InnoDB 支持 | 默认 | 不支持（Memory 引擎支持） |

#### 索引失效的常见场景

- **对索引列做运算或函数**：`WHERE YEAR(create_time) = 2026` → 失效，应改为 `WHERE create_time >= '2026-01-01'`
- **隐式类型转换**：`WHERE phone = 13800138000`（phone 是 varchar，传了 int）→ 失效
- **LIKE 以 %开头**：`WHERE name LIKE '%火锅'` → 失效；`LIKE '火锅%'` → 走索引
- **OR 连接非索引列**：`WHERE a=1 OR b=2`，如果 b 没索引则整体失效
- **不满足最左前缀**：联合索引 `(a,b,c)`，查询只用 b 和 c → 失效

#### 最左前缀原则

联合索引 `(a, b, c)` 的 B+ 树按 a→b→c 的顺序排列。查询条件必须从最左列开始匹配：

- `WHERE a=1` → ✓ 走索引
- `WHERE a=1 AND b=2` → ✓ 走索引
- `WHERE a=1 AND b=2 AND c=3` → ✓ 走索引
- `WHERE b=2 AND c=3` → ✗ 不走索引（缺少最左列 a）
- `WHERE a=1 AND c=3` → ⚠ a 走索引，c 不走（中间跳过了 b）

#### 覆盖索引

查询所需的列全部包含在索引中，不需要回表（回主键索引取数据）。例如索引 `(name, price)`，查询 `SELECT name, price FROM shop WHERE name='火锅'` → 直接从索引树取数据，不需要回表，性能更好。这就是为什么 `SELECT *` 不好的原因——它总是需要回表。

### Q29. Elasticsearch：倒排索引原理？IK 分词器的两种模式？TF-IDF / BM25 原理？

#### 倒排索引原理

正排索引：文档 ID → 词列表。倒排索引反过来：**词 → 文档 ID 列表**。

```
文档1: "杭州好吃的火锅"  → 分词 → [杭州, 好吃, 火锅]
文档2: "杭州日料推荐"    → 分词 → [杭州, 日料, 推荐]

倒排索引:
  杭州 → [文档1, 文档2]
  好吃 → [文档1]
  火锅 → [文档1]
  日料 → [文档2]
  推荐 → [文档2]
```

搜索"杭州火锅"时，分词为 [杭州, 火锅]，找到两个倒排链表取交集 → [文档1]，直接定位到包含这些词的文档，不需要遍历所有文档。

#### IK 分词器两种模式

- **ik_smart（智能分词）**：粗粒度，做最少的切分。"杭州好吃的火锅" → [杭州, 好吃的, 火锅]。适合精确匹配、不希望过度分词的场景
- **ik_max_word（细粒度）**：最多切分。"杭州好吃的火锅" → [杭州, 好吃, 的, 火锅]。适合搜索场景，分得越细，召回率越高

本项目索引时用 `ik_max_word`（多分词提高召回），搜索时用 `ik_smart`（精准查询减少噪音）。

#### 相关度评分：TF-IDF vs BM25

- **TF-IDF**：词频（TF）× 逆文档频率（IDF）。词在文档中出现越多，TF 越高；在所有文档中出现越多，IDF 越低（"的"在所有文档都有，IDF 低，权重低）
- **BM25**：TF-IDF 的改进版。引入了**饱和函数**和**文档长度归一化**。词频不会无限增长（出现 100 次和 10 次的差异不像 TF-IDF 那么大），长文档会被惩罚（避免长文档因为字多而评分高）。ES 5.0+ 默认用 BM25

### Q30. RabbitMQ：怎么保证消息不丢失？消息积压怎么处理？

#### 消息不丢失的三层保障

| 环节 | 问题 | 解决方案 |
| --- | --- | --- |
| 生产者 | 消息发到 Broker 丢失 | ① publisher confirm 机制 ② 事务模式（性能差） |
| Broker | 消息在内存中，宕机丢失 | ① 队列持久化（durable=true）② 消息持久化（deliveryMode=2）③ 交换机持久化 |
| 消费者 | 消息还没处理完就 ack 了，宕机丢失 | 手动 ack：处理成功后才 ack，失败则 nack 重投 |

#### 消息积压怎么处理

- **紧急扩容**：增加消费者实例，提高消费速度
- **批量消费**：一次消费多条消息（`prefetch` 调大）
- **降级处理**：非核心业务暂停消费，把资源让给核心业务
- **消息转移**：把积压消息转移到另一个队列，异步慢慢消费，不阻塞正常流程
- **根因分析**：是消费者处理太慢？还是生产者突然发太多？对症下药

本项目通过 RabbitMQ 的 Stream（`stream.orders`）做秒杀订单异步消费，消费端有 pending-list 兜底机制：消费失败的消息进入 pending-list，可以重新消费。

### Q31. 为什么从后端转向 Agent 开发？最大区别是什么？做 Agent 遇到的最大挑战？

#### 转向 Agent 开发的原因

后端开发的核心是**确定性**——输入确定、流程确定、输出确定，重点在性能、并发、一致性。而 Agent 开发的核心是**不确定性**——LLM 的输出不可预测，工具调用可能失败，用户意图可能模糊。这种不确定性带来了全新的工程挑战，也更有创造空间。

#### 最大区别

| 维度 | 传统后端 | Agent 开发 |
| --- | --- | --- |
| 流程控制 | 硬编码 if-else | LLM 决策 + 状态机 |
| 输出确定性 | 100% 确定 | 概率性，需要容错 |
| 测试方式 | 单元测试 + 集成测试 | 评测集 + LLM-as-Judge + 消融实验 |
| 核心挑战 | 并发、性能、一致性 | prompt 工程、上下文管理、可控性 |
| 调试方式 | 断点 + 日志 | 轨迹分析 + prompt 对比 |

#### 最大挑战

**LLM 输出的不可控性**。传统后端写一个 if-else，行为完全确定。但 LLM 可能：

- 生成的 JSON 格式不对（多了换行、带了 markdown 标记）
- 调用了不存在的工具或传了错误参数
- 同样的输入两次运行结果不同
- 在不需要 HITL 的时候中断，在需要的时候直接推荐了

解决方案就是本项目的**多层防御设计**：JSON 解析容错、参数 schema 校验、状态机兜底、评测体系持续验证。本质上是用工程手段约束 LLM 的不确定性。

### Q32. 未来规划：Agent 技术发展怎么看？Harness Engineering 怎么理解？接下来深入研究哪个方向？

#### 对 Agent 技术发展的看法

Agent 正从"demo 阶段"走向"生产阶段"。核心趋势：

- **从单 Agent 到多 Agent 协作**：单个 Agent 能力有限，多 Agent 分工协作（如 planner + executor + critic）能处理更复杂的任务
- **从 prompt 驱动到 memory 驱动**：上下文工程（Context Engineering）会取代 prompt 工程，成为核心竞争力。Agent 的上下文怎么组织、怎么压缩、怎么检索，决定了 Agent 的智能水平
- **从 LLM-as-Tool 到 LLM-as-System**：不再只是用 LLM 做单次推理，而是用 LLM 构建完整的系统（状态机 + 工作流 + 记忆 + 评测）

#### Harness Engineering 的理解

Harness 原意是"马具/线束"，在 Agent 领域指**LLM 的运行时框架**——包裹在 LLM 外层的所有工程化基础设施：

- **上下文管理**：怎么组织 prompt、怎么注入记忆、怎么压缩历史
- **工具调度**：LLM 能调用哪些工具、参数怎么校验、结果怎么处理
- **流程控制**：状态机、条件路由、重试策略、异常处理
- **评测反馈**：怎么评估 Agent 表现、怎么从失败中学习

本质上，LLM 是"引擎"，Harness 是"底盘+转向+刹车"。引擎再强，没有好的 Harness 也跑不稳。本项目的 LangGraph 状态机、Playbook 自改进、HITL 中断恢复、双层评测，都是在做 Harness Engineering。

#### 接下来想深入研究的方向

- **多 Agent 协作框架**：研究 LangGraph 的多 Agent 模式（supervisor-worker），探索如何让多个 Agent 分工协作
- **长期记忆的规模化**：当前 Playbook 只有几十条规则，如何扩展到上万条而不崩溃（分层检索、动态裁剪、自动摘要）
- **Agent 可观测性**：引入 LangSmith / LangFuse 做轨迹追踪，分析 Agent 决策链路，定位失败原因

---

## 四、压力测试 / 开放题

### Q33. 秒杀 QPS 从 50 提升到 5 万，架构哪些地方先扛不住？怎么优化？

#### 瓶颈分析（按层级）

1. **Tomcat 线程池**（~200 线程）：5 万 QPS 意味着每个请求平均 4ms 完成，200 线程理论 QPS = 200 / 0.004 = 50000。刚好卡住，但实际有 GC、IO 等开销，会先扛不住。**优化**：增加 Tomcat 线程数、用异步 Servlet（WebFlux）
2. **Redis 单实例**：Redis 单线程，QPS 上限约 10 万。5 万 QPS 下如果每个请求 1 次 Redis 调用没问题，但如果多次调用（Lua + token 查询 + 缓存查询）会接近上限。**优化**：Redis Cluster 分片、读写分离、Lua 脚本合并操作减少网络往返
3. **MySQL**：异步下单消费者写 DB，5 万 QPS 的下单消息通过 MQ 削峰，DB 实际承受的 QPS 取决于消费速度。如果消费太慢会导致消息积压。**优化**：分库分表（按 userId 取模）、批量插入、增加消费者实例
4. **RabbitMQ**：5 万 QPS 的消息写入，RabbitMQ 单机约 3-5 万 QPS。**优化**：Kafka 替代（单 partition 数万 QPS，多 partition 百万级）、或 RocketMQ
5. **网络带宽**：5 万 QPS × 每个请求 ~1KB = 50MB/s = 400Mbps，需要千兆网卡。**优化**：万兆网卡 + CDN + 静态资源分离

#### 优化路线图

```
50 QPS (当前) → 1000 QPS → 10000 QPS → 50000 QPS

1000 QPS: 增加连接池、优化 SQL、缓存命中率
10000 QPS: Redis Cluster + MQ 削峰 + 服务拆分
50000 QPS: Kafka 替代 RabbitMQ + 分库分表
           + 多级缓存（本地 Caffeine + Redis）
           + 异步化（WebFlux / 响应式编程）
           + 弹性伸缩（K8s 自动扩缩容）
```

### Q34. 单体项目拆微服务：怎么拆？拆哪些服务？服务间怎么通信？分布式事务怎么处理？

#### 服务拆分方案

| 服务 | 职责 | 独立扩展理由 |
| --- | --- | --- |
| 用户服务 | 登录、注册、Token 管理 | 读多写少，可独立缓存 |
| 商铺服务 | 商铺查询、GEO 搜索、ES 全文搜索 | 读量大，需要独立 ES 集群 |
| 秒杀服务 | 秒杀预检、库存管理 | 高并发，需要独立 Redis 集群 |
| 订单服务 | 下单、查询、取消 | 写操作多，需要分库分表 |
| 支付服务 | 支付、回调、退款 | 涉及第三方对接，需要独立隔离 |
| 社交服务 | 点赞、签到、关注 | Redis 操作密集，独立缓存 |

#### 服务间通信方式

- **同步调用（HTTP/RPC）**：用户服务调用商铺服务查信息。适合实时性要求高的场景
- **异步消息（MQ）**：秒杀服务发消息给订单服务。适合解耦、削峰场景
- **事件驱动**：支付成功后发事件，多个服务订阅（订单服务改状态、通知服务发消息、积分服务加积分）

#### 分布式事务处理

- **最终一致性（推荐）**：大部分场景不需要强一致性。订单创建 + 库存扣减通过 MQ 实现，如果扣减失败则补偿回滚订单
- **TCC（Try-Confirm-Cancel）**：支付 + 订单状态更新需要强一致性的场景。Try 阶段预留资源，Confirm 确认，Cancel 回滚
- **Saga 模式**：长流程事务拆成多个本地事务，每步有对应的补偿操作。适合退款流程（改订单状态 → 调退款 API → 恢复库存 → 删除一人一单记录）
- **Seata AT 模式**：自动生成回滚 SQL，对业务侵入最小。但性能开销大，适合对一致性要求极高的场景

### Q35. Agent 项目从 120 家扩展到 10 万家商铺，推荐流程哪些地方变慢？怎么优化？

#### 瓶颈分析

1. **工具调用变慢**：`search_by_category` 和 `search_nearby` 当前查 MySQL，120 条数据全表扫描很快，10 万条需要加索引。如果用 ES，需要重建索引和优化查询
2. **LLM 上下文膨胀**：execute 返回的候选商铺可能从 5-10 个变成几十个，注入 prompt 的 token 数急剧增长，LLM 推理变慢
3. **Playbook RAG 检索**：Chroma 向量库规模增长不明显（Playbook 条目数和商铺数无关），但检索质量可能下降
4. **排序阶段变慢**：10 万商铺中选出 Top-N 需要更高效的排序算法

#### 优化方案

- **引入 ES**：商铺搜索从 MySQL 迁移到 Elasticsearch，支持全文搜索 + 复合过滤 + 分页，10 万级数据毫秒级响应
- **两阶段召回**：第一阶段用 ES 快速召回 Top 100 候选（粗排），第二阶段用 LLM 对 Top 10 做精排（matchReason 生成）。避免把 100 个商铺全塞给 LLM
- **向量搜索**：用商铺的 embedding 向量做语义召回（"氛围好的餐厅"→ 向量近邻搜索），补充关键词搜索的不足
- **缓存热门查询**：常见查询（如"附近火锅"）的结果缓存到 Redis，TTL 5 分钟，80% 请求走缓存不查 ES
- **分片检索**：按城市/区域分片，"杭州的火锅"只搜杭州分片，减少搜索范围
- **异步预加载**：用户打开 App 时预加载附近热门商铺到本地，减少首次搜索延迟

> **核心思路：**从"LLM 直接处理全量数据"变为"搜索引擎粗筛 → LLM 精排"。这是推荐系统的经典架构——召回层用工程手段（ES/向量搜索）快速缩小范围，排序层用 LLM 做个性化推荐。Agent 不是要替代搜索引擎，而是要在搜索引擎的基础上做更智能的决策。