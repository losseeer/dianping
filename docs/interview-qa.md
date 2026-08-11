# 项目面试问答手册

> Interview Q&A
>
> 快评 Java 后端 + 智能推荐 Agent 项目 — 50 道深度面试题参考回答
> （Q1-Q35 基础+综合；Q36-Q50 为 2026-08 重构后的深度追问，紧扣实际代码）

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

**五、深度追问：Agent2 重构与自进化闭环（Q36-Q45）**

- evaluate 纯规则化 / replan_relax 规则放宽（Q36-Q37）
- fuzzy_mapping 编码 / outcome 重判入队 / 双保险批处理（Q38-Q40）
- 双阈值信号判定 / 偏好合并 / Chroma RAG / augment 匹配（Q41-Q44）
- PLAN prompt 硬约束验证（Q45）

**六、深度追问：后端工程细节（Q46-Q50）**

- @Lazy 循环依赖 / 逻辑过期 Double Check / rebuild 幂等（Q46-Q48）
- 熔断器探针超时 / 秒杀 Set 内存（Q49-Q50）

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

### Q17. LangGraph 状态图：节点分别是什么？条件路由怎么判断？【2026-08 重构后】

#### 节点及状态流转图（8 节点 + 1 条条件边）

```
  load_memory → plan → execute → evaluate
                                   │
                          ┌────────┼────────┐
                          ▼        ▼        ▼
                     interrupt   generate  replan_relax
                     (END)         │     (→ evaluate 二次判定)
                                   ▼
                              log_trajectory → END

  HITL resume: update_memory → plan（带着用户反馈重新规划）
```

**8 个节点**（`graph/builder.py`）：

1. `load_memory`：加载用户 9 维长期偏好 + 会话上下文摘要 + Playbook 经验库（含 augment_summary 模糊词补全）
2. `plan`：LLM 分析用户意图，输出 intent_analysis + tool_calls + hitl_needed
3. `execute`：执行工具调用（6 个白名单工具），候选商铺去重合并到 candidate_shops，过滤已推荐商铺
4. `evaluate`：**纯规则判定**（零 LLM），5 条规则判定 sufficient / insufficient / hitl_needed
5. `replan_relax`：**纯规则放宽**（零 LLM），maxPrice×1.25 / minScore−0.3 重搜，单轮最多一次
6. `update_memory`：HITL resume 后从用户反馈提取偏好，增量 merge 写 MySQL+Redis
7. `generate`：client-side 硬过滤（价格/评分/排除词）+ 偏好商圈提权后，LLM 生成 Top-5 推荐
8. `log_trajectory`：持久化轨迹 + 触发 Layer 4 自进化入队 + 离线触发 playbook.reflect()

> **【重构要点】** 旧版的 `reflect` 节点和 `should_replan` 条件边已从主请求路径移除。reflect 改为在 `log_trajectory` 内部按 `reflection_score < 6.0` 离线触发，不再阻塞主请求。replan 改为 `replan_relax` 纯规则节点，不调 LLM。

#### 条件路由判断（routing.py should_hitl / judge_candidates）

evaluate 之后有 3 条路径（`add_conditional_edges`）：

```python
def should_hitl(state) -> str:
    if hitl_needed and hitl_count <= 1:
        return "interrupt"      # HITL 打断，等用户补充
    if evaluation == "sufficient":
        return "generate"        # 候选充分，生成推荐
    if evaluation == "insufficient":
        if iteration_count >= AGENT2_MAX_ITERATIONS:  # 最多 3 轮
            return "generate"   # 超限强制生成
        return "relax"           # 规则放宽重搜，回 evaluate 二次判定
    return "generate"            # 异常兜底
```

#### 防止无限循环的三重保障

1. **replan_count 守卫**：replan_relax 内部检查 `replan_count >= 1` 直接返回空，单轮最多放宽一次
2. **evaluate 规则兜底**：replan_count ≥ 1 时 evaluate 强制 sufficient（规则 5），不会再走 relax
3. **iteration_count 硬上限**：`AGENT2_MAX_ITERATIONS = 3`，超限 routing 强制 generate

> **单轮最多一次 HITL**：`hitl_count >= 1` 后 evaluate 规则 1 强制 sufficient，避免反复打断用户。

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

#### 6 个白名单工具（`graph/nodes.py execute_tool`）

| 工具名 | 参数 | 何时用 |
|---|---|---|
| `search_shops_by_keyword` | keyword, [maxPrice], [minScore] | 细分类（日料/火锅/咖啡…）或具体店名；走 Java `/shop/search`（ES synonym_graph + 熔断器） |
| `search_shops_nearby` | typeId, x, y, [maxPrice], [minScore] | 泛化需求（找个吃饭的地方）或强调附近；先 `get_shop_types` 拿 typeId |
| `get_shop_detail` | shopId | 候选已拿到，只对 1~2 家重点补详情（不要全量调） |
| `get_shop_types` | — | 不知道 typeId 时先调；只返回大类，细分一律走 keyword 工具 |
| `get_review_summary` | shopId | Top-1/2 候选做好评度验证（调 Agent1，不要全量调） |
| `get_shop_reviews` | shopId, [limit] | Agent1 摘要为空时的降级手段 |

> **【关键约束】** keyword 必须是「单个核心品类词」，禁止带地名/修饰/整句。同义词扩展交给 ES synonym_graph（keyword=寿司 → 自动召回日料/刺身/居酒屋），不需要 LLM 在 prompt 里手工列举。

#### 参数是 LLM 生成的吗？

**是的**。plan 节点 LLM 输出 JSON 格式的工具调用计划：

```json
{
  "reasoning": "用户想找日料，按 memory.maxPrice=120 传 maxPrice",
  "intent_analysis": {
    "keyword": "日料",
    "maxPrice": 120,
    "avoidKeywords": [],
    "preferredAreas": []
  },
  "tool_calls": [{"name": "search_shops_by_keyword", "params": {"keyword": "日料", "maxPrice": 120}}],
  "hitl_needed": false
}
```

#### 参数格式不对怎么处理？

本项目用**多层防御**处理 LLM 输出格式问题：

1. **JSON 解析容错**：`_parse_llm_json()` 先尝试标准 JSON 解析，失败后用正则提取 `{...}` 部分重试
2. **工具白名单校验**：`guard.validate_tool_calls()` 过滤非法工具名，只保留 6 个白名单工具
3. **Pydantic 强类型**：ChatRequest/ResumeRequest `userId: int = Field(gt=0)`，类型不匹配自动报错
4. **默认值兜底**：maxPrice/minScore 缺失时传 null，工具内部做 client-side 后过滤
5. **replan_relax 兜底**：工具执行返回候选不足时，规则放宽重搜（不依赖 LLM 重新规划）
6. **seen_shop_ids 去重**：execute_node 自动过滤已推荐商铺，LLM 不需要手动排除

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

`log_trajectory` 节点末尾，如果 `reflection_score` 存在且低于阈值，**离线触发** `playbook.reflect()` 蒸馏经验（不再有独立的 reflect 串行节点阻塞主请求）。

> **【两个不同的阈值，不要混淆】**
> - `PLAYBOOK_REFLECTION_THRESHOLD = 6.0`：在 `log_trajectory_node` 中，`reflection_score < 6.0` 触发 `playbook.reflect()` 蒸馏失败经验（写入 Playbook 经验库）
> - `reflectionScore < 4.0`：在 `signals.detect_acceptance` 中，`0 < reflectionScore < 4.0` 直接跳过蒸馏（烂轨迹不学，不作为 accepted 信号蒸馏偏好）
>
> 区别：前者是"反思一下这次哪里做得不好，提取操作规则"；后者是"这次太烂了，连偏好都不要从里面学"。一个 6 分触发反思，一个 4 分直接丢弃。

#### 触发蒸馏的流程

```
log_trajectory_node 末尾：
  if 0 < reflection_score < 6.0:   # PLAYBOOK_REFLECTION_THRESHOLD
      insights = await playbook.reflect(record)   # LLM 蒸馏操作规则
      await playbook.curate(insights, source="reflection")  # 去重合并

  # 同时 enqueue_for_distill(traj_id) 触发 Layer 4 信号管线
  # detect_acceptance 判定：reflectionScore < 4.0 → 直接跳过
```

#### 自评不准怎么办？

这是 LLM 自评的核心问题。本项目的缓解措施：

1. **置信度校准**：Playbook 条目的 confidence 不是 LLM 直接给的，而是通过 `timesHelpful / timesApplied` 计算——只有被多次应用且确实有效时，confidence 才会升高
2. **显式 outcome 双轨信号**：用户点击查看详情（accepted）或点踩（rejected）作为 ground truth，权重高于 LLM 自评。`detect_acceptance` 中 `outcome == "accepted"` 直接返回 True，覆盖隐式信号
3. **去重精炼**：`deduplicate()` 方法定期清理重复和低质量条目，防止 context collapse
4. **上限控制**：Playbook 最多 200 条（`PLAYBOOK_MAX_ENTRIES = 200`），超过按 confidence 排序裁剪
5. **低置信度不入库**：`PLAYBOOK_MIN_NOVELTY = 0.5`，curate 时 confidence < 0.5 的 insight 直接跳过

> **更彻底的方案：**显式 outcome 已经接入（`POST /agent2/trajectory/{id}/outcome`），用户反馈作为最高权重信号，清除 processed marker 后重新入队蒸馏，解决「信号判过一次就锁死」的半吊子链路。

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

---

## 五、深度追问：Agent2 重构与自进化闭环

> 这一节是面试官针对 2026-08 重构后的代码细节做的深度追问，每一题都对应实际代码，不是纯理论。

### Q36. evaluate 为什么从 LLM 判断改成纯规则？5 条规则是什么？损失了什么灵活性？

#### 改的原因

旧版 evaluate 让 LLM 判断候选是否"充分"（sufficient/insufficient/vague），有三个问题：

1. **延迟**：多一次 LLM 调用，端到端 P95 从 ~2s 涨到 ~4s
2. **抖动**：同样的候选数（比如 2 家），LLM 时而判 sufficient 时而判 vague，导致同一输入两次结果不同
3. **成本**：每次请求多消耗 ~800 token，1200 次对话多花约 100 万 token

#### 5 条规则（`nodes.py evaluate_node`）

| 规则 | 条件 | 判定 | 理由 |
|---|---|---|---|
| 1 | hitl_count ≥ 1 | sufficient | 已打断过用户，不再二次打断 |
| 2 | has_searched 且 candidate ≥ MIN_CANDIDATES(3) | sufficient | 候选充足 |
| 3 | candidate == 0 且 hitl_count == 0 | hitl_needed | 没找到，问用户放宽哪一项 |
| 4 | 0 < candidate < 3 且 replan_count == 0 | insufficient | 候选偏少，走规则放宽 |
| 5 | 0 < candidate < 3 且 replan_count ≥ 1 | sufficient | 放宽过仍少，硬推 |

#### 损失了什么灵活性？

损失了"LLM 能理解语义层面的候选是否充分"的能力。比如候选 5 家但都是同一家连锁的不同分店，LLM 可能判"多样性不足"走 replan，纯规则只看数量会判 sufficient。

**但这个损失是可接受的**：①多样性由 generate 节点的 client-side 过滤 + LLM Top-5 选择保证；②replan_relax 的规则放宽能覆盖"候选偏少"的最常见场景；③换来的延迟降低和稳定性提升远大于损失。

> **面试追问点**：如果规则覆盖不了所有场景怎么办？答：evaluate 规则只负责"候选数够不够"这种结构化判断，语义质量判断交给 generate 节点的 LLM。分层职责清晰。

### Q37. replan_relax 为什么不用 LLM 重新规划？maxPrice×1.25 / minScore−0.3 这两个系数怎么来的？

#### 不用 LLM 重新规划的原因

1. **LLM replan 不可控**：LLM 可能换工具、换 keyword，导致完全不同的搜索方向，候选集不连续
2. **延迟**：又多一次 LLM 调用
3. **候选不足的最常见原因是筛选太严**：价格上限太低、评分下限太高。规则放宽这两个参数就能解决 80% 的情况

#### 系数怎么来的

- **maxPrice × 1.25**：用户说"人均 100 以内"但只找到 1 家，放宽到 125 元是合理的人均上浮（一顿饭涨 25 元可接受）。1.5× 太激进（150 元可能超出预算），1.1× 太保守（110 元可能还是找不到）
- **minScore − 0.3（下限 3.0）**：评分 4.5 降到 4.2 是合理的质量妥协；下限 3.0 防止放宽到垃圾商铺（3.0 以下基本是差评店）

#### 单轮最多一次的守卫

`replan_relax_node` 内部 `if replan_count >= 1: return {}`，加上 evaluate 规则 5 兜底，保证不会无限放宽。放宽过一轮还是候选少，说明这个商圈/品类本身就少，硬推 + 标注 source="relaxed" 让用户知道。

> **为什么标注 source="relaxed"？** generate 节点会在推荐文案里明确写「为您放宽条件额外找到：」，让用户知道这些候选不完全是按原始条件匹配的，管理用户预期。

### Q38. fuzzy_mapping 为什么编码在 description 字符串里而不是单独建列/建表？正则解析的性能开销？

#### 编码格式

```
description = "[fuzzy_mapping] trigger:"附近" normalized:"约5km范围内" evidence:max_distance=4.20@5shops"
```

用正则 `_MAPPING_RE` 解析出 trigger 和 normalized。

#### 为什么不单独建列/建表？

1. **零 schema 变更**：tb_agent_playbook 表结构不变，Playbook 条目的 category="intent_parsing" + description 就能存，不需要 DDL 迁移
2. **复用现有 RAG 链路**：Chroma 向量索引直接对 description 做 embedding，fuzzy_mapping 条目和普通经验条目走同一条检索路径
3. **向后兼容**：普通经验条目（reflection 产出的）description 是自然语言，fuzzy_mapping 条目 description 是结构化编码，两者共存互不干扰。`parse_mapping_description` 解析失败就当普通条目处理

#### 正则解析的性能开销

**可忽略**。Playbook 上限 200 条，augment_summary 每次最多对 200 条做 `parse_mapping_description`，正则匹配是 O(n) 级别，200 条 < 1ms。比 LLM 调用快 4 个数量级。

#### 重复命中时怎么更新？

`add_mapping_entries` 对相同 trigger+normalized 的条目做**指数加权更新**：

```python
updated_conf = (match_e.confidence * old_hits + new_conf) / new_hits
match_e.confidence = min(1.0, updated_conf + 0.03)  # +3% 命中奖励
match_e.timesApplied = new_hits
```

不是简单覆盖，而是按历史命中次数加权——命中越多次的条目，新 confidence 对它的影响越小（越稳定）。+3% 是命中奖励，鼓励被反复验证的规则。

### Q39. outcome 重判入队：为什么必须清除 processed marker？不清除会怎样？

#### 不清除会怎样

`pop_pending_batch` 出队时会先做幂等预过滤：

```python
for tid in ids:
    if is_processed(tid):   # processed marker 存在 → 直接跳过
        to_rem.append(tid)
    else:
        out.append(tid)
```

如果 outcome 更新后不清除 `agent2:distill:done:{trajectory_id}`，下次出队时 `is_processed` 返回 True，这条轨迹直接被跳过——**更精准的显式信号（用户点了查看详情=accepted）永远不会被学到**。

#### 完整重判流程

```python
# main.py update_trajectory_outcome
trajectory_store.update_outcome(traj_id, outcome, feedback)
r.delete(f"{PROCESSED_PREFIX}{trajectory_id}")      # 1. 清除 processed marker
enqueue_for_distill(traj_id, schedule_piggyback=True)  # 2. 重新入队 + piggyback kick
```

- **步骤 1**：清除 marker，让 `pop_pending_batch` 能重新捞出这条轨迹
- **步骤 2**：重新入队 ZSet（score=now）+ 触发 piggyback fire-and-forget 近实时蒸馏

#### 为什么 piggyback kick 而不是等 daemon？

显式反馈是高权重信号（用户明确表达满意/不满意），应该尽快学习生效。piggyback 30s 节流后立即跑一批，比 daemon 5min 兜底快 10 倍。如果是隐式信号（outcome=unknown），可以容忍 5min 延迟；显式信号不行。

> **这是"自进化真闭环"的关键差异点**：很多项目做了"用户反馈→存 outcome"就停了，但 outcome 存了不重新蒸馏等于没存。清除 marker + 重入队才让显式信号真正闭环。

### Q40. piggyback 30s 节流 + daemon 5min 兜底，为什么不只用一个？各自覆盖什么失败场景？

#### 两个机制各自的参数

| 机制 | 触发方式 | 频率 | 单批上限 | 时间预算 |
|---|---|---|---|---|
| Piggyback | log_trajectory 后 fire-and-forget | 30s 节流 | 4 条 | 2.5s |
| Daemon | FastAPI startup 后台 asyncio 循环 | 5min | 16 条 | 无限制 |

#### 为什么不只用 piggyback？

1. **piggyback 依赖请求线程触发**：如果没有新请求（比如凌晨低峰），轨迹一直堆在 ZSet 里没人触发 piggyback
2. **piggyback 有 30s 节流**：大流量下可能漏掉部分轨迹（30s 内只跑一次，最多 4 条，积压超过 4 条的只能等下一轮）
3. **piggyback 有 2.5s 时间预算**：超了就留给下一轮，可能一直跑不完

#### 为什么不只用 daemon？

1. **5min 延迟太长**：用户刚反馈 accepted，要等 5min 才学到，下一轮对话可能还没生效
2. **daemon 是空轮询**：没有请求时也在跑，浪费资源

#### 互补关系

- **正常流量**：piggyback 先跑，daemon 通常看到空批（ZSet 已被 piggyback 清空）
- **异常场景**（LLM 慢导致请求线阻塞 / 重启漏跑一批 / 大流量积压）：daemon 5min 后补捞

> **MIN_COOL_SECONDS = 60**：轨迹落盘后至少等 60s 才蒸馏。原因是用户可能在 30s 内连续 follow-up（"换一家"→"再换一家"），过早蒸馏会把不稳定的单次请求当经验。等 60s 让交互稳定下来再学。

### Q41. detect_acceptance 有两个阈值：reflectionScore<4 跳过、<6 触发 reflect，为什么不一样？

这是两个不同维度的判断，不要混淆：

#### 阈值 4.0：detect_acceptance 的"烂轨迹跳过"

```python
# signals.py detect_acceptance
if 0 < record.reflectionScore < 4.0:
    return False  # 烂轨迹不学，不作为 accepted 信号蒸馏偏好
```

**含义**：评分 < 4 说明这次推荐很烂（比如候选 0 家、HITL 3 次还说不对），从烂推荐里蒸馏"用户偏好"会学错（用户不满意不等于偏好这些店）。所以直接跳过 preference_distill。

#### 阈值 6.0：log_trajectory 的"触发 reflect 蒸馏操作规则"

```python
# nodes.py log_trajectory_node
if state.reflection_score > 0 and state.reflection_score < config.PLAYBOOK_REFLECTION_THRESHOLD:  # 6.0
    insights = await playbook.reflect(record)  # LLM 蒸馏操作规则
```

**含义**：评分 < 6 说明这次不够好，让 LLM 反思"哪里做得不好"，提取**可执行的操作规则**（如"环境偏好应优先于价格筛选"）。这些规则是跨用户通用的，写入 Playbook 经验库。

#### 为什么不一样？

| 维度 | 阈值 4.0（detect_acceptance） | 阈值 6.0（log_trajectory reflect） |
|---|---|---|
| 学什么 | 用户偏好（per-user） | 操作规则（全局） |
| 从哪种轨迹学 | 成功轨迹（accepted） | 不够好的轨迹（反思） |
| 为什么阈值不同 | 偏好学习要求轨迹质量高（烂轨迹学偏） | 反思恰恰要从不够好的轨迹里学（太好的没东西可反思） |

> **本质区别**：4.0 是"这个轨迹能不能当成功样本学偏好"，6.0 是"这个轨迹值不值得反思提取操作规则"。一个管"偏好蒸馏的门槛"，一个管"操作规则反思的门槛"。

### Q42. 9 维偏好合并：priceRange 为什么取更保守（更小）？avoidFactors 和 foodPreferences 冲突怎么处理？

#### priceRange 取更保守的原因

```python
# preferences.py 合并策略
# 新 max 与旧 max 取更小，除非用户明确说「放宽预算」
new_max = min(old_max, new_max) if old_max else new_max
```

**场景**：用户这轮说"人均 100 以内"，上轮说"人均 150 以内"。如果取更大（150），可能推荐 120 的店用户觉得贵。取更小（100）更安全——用户预算只会越来越清晰（收窄），不会莫名放宽。

**例外**：用户明确说"好一点/贵点/放宽预算"时，不取 min 而是取新值。这由 plan 节点的 LLM 在 intent_analysis 里判断，通过 MEMORY_UPDATE_PROMPT 传给 save_memory。

#### avoidFactors 和 foodPreferences 冲突处理

```python
# 冲突解决：把冲突项从 foodPreferences 迁移到 avoidFactors
# 例：foodPreferences 有"火锅"，avoidFactors 新增"不吃辣"
# → 火锅多为辣味，从 foodPreferences 移除"火锅"
```

**为什么迁移而不是都保留？** 如果 foodPreferences 保留"火锅"而 avoidFactors 保留"不吃辣"，下次推荐时 plan 节点会矛盾：memory 说喜欢火锅但 avoidKeywords 排除辣——可能搜不到任何店。迁移后 foodPreferences 去掉火锅，避免矛盾。

#### 数组字段的合并策略

- **likedCategories / foodPreferences / frequentAreas**：append + 去重（SET 语义），新值追加不覆盖旧值
- **avoidFactors**：覆盖式追加（新的 avoid 会把冲突的 foodPreferences 项迁移过来）
- **environmentPreference**：append + 去重

> **90 天过期**：lastUpdated 超 90 天，plan 时 LLM 会提示"偏好可能过时"。防止用户 3 年前的偏好还在影响当前推荐。

### Q43. Chroma HNSW 为什么用 cosine 不用 L2？混合评分 0.7/0.3 怎么调的？Chroma 挂了怎么办？

#### 为什么用 cosine 不用 L2

- **cosine**：衡量方向相似性，不关心向量长度。Playbook 条目的 embedding 长度可能因 description 长短不同而不同，cosine 能消除长度差异
- **L2**：衡量绝对距离，长 description 的向量模长大，会被 L2 判为"远"，不公平

对于语义匹配（"这条规则和用户查询说的是不是一回事"），cosine 是标准选择。Chroma 配置 `"hnsw:space": "cosine"`。

#### 混合评分 0.7/0.3 怎么调的

```python
# playbook.py get_context_rag
sim = max(0.0, 1.0 - distances[e.entryId])  # Chroma cosine distance → 相似度
combined = sim * 0.7 + e.confidence * 0.3
```

- **0.7 给语义相似度**：RAG 的核心是"检索相关条目"，相关性应该占主导
- **0.3 给置信度**：置信度代表规则的历史有效性（timesHelpful/timesApplied），作为次要修正

调参过程：试过 1.0/0（纯语义）、0.5/0.5、0.7/0.3、0.3/0.7。纯语义会召回"语义相关但 confidence 极低的低质量规则"；0.5/0.5 让 confidence 权重过大，退化为纯置信度排序；0.7/0.3 效果最好——相关性主导，置信度做 tiebreaker。

未被检索到的条目用 `confidence * 0.15`（低权重兜底），保证它们有机会进入 Top-K 但不会挤掉更相关的条目。

#### Chroma 挂了怎么办

```python
try:
    results = await asyncio.to_thread(collection.query, ...)
    retrieved_ids = set(results["ids"][0])
except Exception as e:
    logger.warning(f"Chroma query failed: {e}, fallback to confidence")
    retrieved_ids = set()
    distances = {}

# 降级：纯置信度排序
if retrieved_ids:
    # 混合评分
else:
    scored = [(e.confidence, 0.0, e) for e in entries]  # 纯置信度
```

Chroma 不可用时降级为纯置信度排序，Agent 仍能工作（只是检索质量下降）。这是**优雅降级**原则：向量检索是增强不是必需，挂了不能让整个 Agent 不可用。

### Q44. augment_summary 为什么按 trigger 长度降序匹配？不排序会出什么 bug？

```python
# playbook.py augment_summary
triggers_sorted = sorted(by_trigger.keys(), key=len, reverse=True)
for trigger in triggers_sorted:
    if trigger in text:
        ...
```

#### 不排序会出什么 bug

假设 Playbook 里有两条 fuzzy_mapping：
- trigger = "近" → normalized = "约1km内"
- trigger = "附近" → normalized = "约5km内"

如果按字典序（"近" < "附近"），先匹配"近"：用户说"附近有什么火锅"，"近"是"附近"的子串，会命中"近→约1km"，导致规范化补全是"约1km内"而不是"约5km内"——**短 trigger 抢了长 trigger 的匹配**。

按长度降序：先匹配"附近"（命中），再匹配"近"（已被"附近"覆盖，可跳过或都命中但取高分）。保证最长 trigger 优先匹配，避免短前缀劫持。

#### 同 trigger 多 normalized 怎么选

```python
bucket.sort(key=lambda x: x[0], reverse=True)  # 按 score 降序
top_score, top_entry, top_parsed = bucket[0]  # 取最高分
```

score = `confidence * (1.0 + 0.1 * timesApplied)`，综合置信度和应用次数。同一 trigger 有多个 normalized（比如"便宜"→"人均80以内"和"便宜"→"人均100以内"），选历史应用次数多且置信度高的那个。

### Q45. PLAN prompt 硬约束「Playbook 补全必须落到 tool_calls.params」——怎么验证 LLM 真执行了？没执行怎么办？

#### 验证方式

**无法 100% 验证**。LLM 可能 reasoning 里写了"按 Playbook 补全 maxPrice=120"，但 tool_calls.params 里没带 maxPrice。这是 LLM 的固有不可控性。

但可以通过以下方式**提高执行率 + 事后检测**：

1. **prompt 层面强约束**：PLAN_SYSTEM_PROMPT 里用「硬约束」「必须」「务必」等强语气，并给正反例
2. **reasoning 字段要求说明**：要求 LLM 在 reasoning 里写明"依据 [Playbook 规范化补全] 做了哪些偏好注入"，强制 LLM 显式思考
3. **示例驱动**：prompt 里给一个完整示例（用户消息 + Playbook 补全 + 正确 tool_calls 输出），让 LLM 模仿
4. **事后检测**：execute_node 执行前可以校验 tool_calls.params 是否包含 Playbook 补全的参数（当前未实现，是改进方向）

#### 没执行怎么办

- **兜底 1**：generate 节点会从 intent_analysis 提取 maxPrice/minScore/avoidKeywords 做 client-side 硬过滤，即使 plan 没传 maxPrice 给搜索工具，generate 阶段也会过滤掉超价的候选
- **兜底 2**：memory.priceRange.max 也会注入 PLAN prompt，LLM 即使忽略 Playbook 补全，也可能从 memory 里读到偏好
- **兜底 3**：replan_relax 的规则放宽会兜底候选不足的场景

> **设计哲学**：不依赖 LLM 100% 执行硬约束，而是用多层兜底保证即使 LLM 没执行，最终推荐质量也不会崩。Playbook 补全是"锦上添花"，不是"唯一防线"。

---

## 六、深度追问：后端工程细节

### Q46. @Lazy 打破循环依赖：CGLIB 代理原理？为什么不重构掉循环依赖？

#### 循环依赖的产生

```
VoucherOrderServiceImpl 依赖 IPaymentService（payOrder 委托给支付服务）
PaymentServiceImpl 依赖 VoucherOrderServiceImpl（退款时要恢复订单）
```

#### @Lazy 的 CGLIB 代理原理

`@Lazy` 注入的不是真实对象，而是 Spring 在运行时生成的 CGLIB 代理：

1. Spring 启动时发现 `VoucherOrderServiceImpl` 依赖 `IPaymentService`，但 `PaymentServiceImpl` 还没创建（循环了）
2. `@Lazy` 让 Spring 先注入一个 CGLIB 代理对象（不触发真实 Bean 创建）
3. 第一次调用 `paymentService.payOrder()` 时，代理才从容器中获取真实的 `PaymentServiceImpl` Bean 并委托调用
4. 此时 `PaymentServiceImpl` 已经创建完毕（它依赖的 `VoucherOrderServiceImpl` 已注册），循环打破

#### 为什么不重构掉循环依赖？

理想情况应该重构，但本项目的循环依赖有业务合理性：

- **VoucherOrderService** 是订单领域的门面，对外暴露 `payOrder` 入口（门面模式）
- **PaymentService** 是支付领域，退款时需要操作订单（恢复状态、恢复库存）

两者确实需要互相调用。重构方案是引入第三层（如 `OrderPaymentFacade`），但增加一层抽象对学习项目收益不大。`@Lazy` 是 Spring 官方推荐的循环依赖解决方案（配合 `spring.main.allow-circular-references=true`），安全且零侵入。

> **Spring Boot 2.6+ 默认禁用循环依赖**，需要显式开启。本项目用 `@Lazy` 是更优雅的方式，不依赖全局配置。

### Q47. CacheClient 逻辑过期方案缺 Double Check，具体什么风险？怎么补？

#### 缺 Double Check 的风险

```java
// 当前实现（简化）
if (isLock) {
    // 拿到锁后直接重建，没有二次检查缓存
    CACHE_REBUILD_EXECUTOR.submit(() -> {
        R r1 = dbFallback.apply(id);
        this.setWithLogicalExpire(key, r1, time, unit);
    });
}
```

**风险场景**：
1. 线程 A 发现缓存过期，获取锁成功，开始重建（查 DB 需 200ms）
2. 线程 A 重建期间，缓存仍是旧值（过期数据），其他线程返回旧值 ✓
3. 线程 A 重建完成，写回新值，释放锁
4. 线程 B 在线程 A 释放锁后获取锁，**没有检查缓存已被 A 重建**，又查一次 DB 重建——**重复重建，浪费 DB 查询**

#### 怎么补

```java
if (isLock) {
    // Double Check：拿锁后再查一次缓存，可能已被别的线程重建
    json = stringRedisTemplate.opsForValue().get(key);
    RedisData redisData = JSONUtil.toBean(json, RedisData.class);
    if (redisData.getExpireTime().isAfter(LocalDateTime.now())) {
        // 已被重建，直接返回，不再查 DB
        return JSONUtil.toBean((JSONObject) redisData.getData(), type);
    }
    // 确实还需要重建
    CACHE_REBUILD_EXECUTOR.submit(() -> { ... });
}
```

#### 影响评估

当前不补的风险是**偶发重复 DB 查询**（概率低：需要两个线程先后拿锁且都不检查）。对学习项目影响不大，但面试时被问到要能说出这个缺陷和补法。

> **代码里已注释说明**：`// 本代码里没有做二次检查，其实是可以优化的点`。这种主动标注已知缺陷比假装完美更好。

### Q48. ES rebuild-index 接口并发调用会怎样？怎么保证幂等/安全？

#### 并发调用的风险

`rebuildIndexInternal(force=true)` 执行 DROP → CREATE → PUT MAPPING → IMPORT 四步：

1. **DROP 不是原子的**：线程 A DROP 后还没 CREATE，线程 B 也来 DROP（索引已不存在，报错）或 CREATE（冲突）
2. **IMPORT 重复**：两个线程都 IMPORT 全量数据，ES 会 upsert（按 _id 覆盖），数据不会翻倍但浪费 IO
3. **查询空窗**：DROP 到 IMPORT 完成期间，所有搜索查不到数据（或走熔断器降级 MySQL）

#### 当前如何保证安全

**当前没有加锁**，靠两点保证：

1. **管理接口需登录**：`POST /shop/search/rebuild-index` 需登录态，不是公开接口，不会被恶意刷
2. **运维约定**：同义词更新是低频操作（改 synonyms.txt 后手动调一次），不会并发

#### 生产环境应该怎么做

```java
// 方案 1：Redis 分布式锁
RLock lock = redissonClient.getLock("lock:es:rebuild");
if (!lock.tryLock(0, 600, TimeUnit.SECONDS)) {
    return Result.fail("索引重建正在进行中，请稍后");
}
try {
    rebuildIndexInternal(true);
} finally {
    lock.unlock();
}

// 方案 2：别名零停机重建（推荐）
// 1. CREATE shop_v2 (新索引，新同义词)
// 2. IMPORT 全量数据到 shop_v2
// 3. POST /_aliases 把 shop 别名从 shop_v1 切到 shop_v2
// 4. DELETE shop_v1
// 优点：零查询空窗，可回滚（切回 shop_v1）
```

> **方案 2（别名切换）是 ES 索引重建的最佳实践**，但实现复杂。本项目用方案 DROP+CREATE 足够学习场景，面试时要能说出方案 2。

### Q49. @CircuitBreaker HALF_OPEN 只放 1 个探针，探针超时（不是抛异常）怎么处理？

#### 当前实现对超时的处理

**当前实现只捕获 Throwable**：

```java
try {
    Object result = joinPoint.proceed();  // 探针请求
    // 成功 → CLOSED
} catch (Throwable e) {
    // 失败 → 重新 OPEN
}
```

如果探针请求**超时**（比如 ES 响应慢，HTTP 调用 30s 没返回），`joinPoint.proceed()` 会抛 `SocketTimeoutException`，被 catch 捕获 → 探测失败 → 重新 OPEN。

**所以超时被当作失败处理**，这是正确的——超时说明服务还没恢复，不应该转 CLOSED。

#### 探针超时的潜在问题

1. **HALF_OPEN 阻塞**：探针请求一直不返回（比如 ES 假死），HALF_OPEN 状态会一直持续到超时
2. **其他请求被降级**：HALF_OPEN 期间 `probeSent=true`，其他请求都走 fallback，直到探针完成

#### 优化方向

- **给探针加独立超时**：比如 ES 正常请求超时 5s，探针超时设 2s（更短），快速判断服务是否恢复
- **HALF_OPEN 加超时**：如果探针 10s 没返回，强制重新 OPEN，不要一直卡在 HALF_OPEN
- **放多个探针**：当前只放 1 个，可以放 3 个，2/3 成功就转 CLOSED（更鲁棒，但实现复杂）

#### 为什么只用 CAS 不用 synchronized

```java
if (!breaker.getProbeSent().compareAndSet(false, true)) {
    return doFallback(joinPoint, circuitBreaker);  // 其他请求降级
}
```

- **CAS 无锁**：`AtomicBoolean.compareAndSet` 是无锁操作，性能高于 synchronized
- **保证唯一性**：CAS 保证只有一个线程能把 probeSent 从 false 改成 true，即只放行 1 个探针
- **状态转换也用 CAS**：`breaker.getState().compareAndSet(BreakerState.OPEN, BreakerState.HALF_OPEN)` 保证 OPEN→HALF_OPEN 只发生一次

> **synchronized 的问题**：高并发下 synchronized 会阻塞其他线程，而 CAS 是非阻塞的（失败的线程直接返回 fallback）。熔断器是高频路径，不能用阻塞锁。

### Q50. 秒杀 Lua 脚本用 SADD userId 到 Set，10 万并发下 Set 内存？为什么不用 BitMap/布隆过滤器？

#### Set 内存分析

10 万用户秒杀，Set 存 10 万个 userId（字符串）：

- 每个 userId 字符串约 10 字节（如 "10101234"）+ Redis 对象 overhead 约 50-80 字节
- 10 万元素 ≈ 5-8 MB

**Redis 单实例通常配几 GB 内存，8 MB 微不足道**。而且秒杀结束后可以 `DEL seckill:order:{voucherId}` 释放。

#### 为什么不用 BitMap？

- **BitMap 需要连续整数 ID**：userId 必须是 1~N 连续整数才能用 BitMap（第 N 位表示用户 N）。但本项目 userId 是 RedisIdWorker 生成的（时间戳+序列号），不是连续的
- **BitMap 适合稀疏签到**：签到场景每天 1 位，10 万用户 30 天 = 30 万位 = 37.5 KB。秒杀场景是单次记录，Set 更自然

#### 为什么不用布隆过滤器？

- **布隆过滤器有误判**：布隆过滤器说"存在"可能不存在（false positive），导致合法用户被误判为"已下单"无法下单。秒杀场景宁可超卖不可误杀合法用户（业务上超卖可人工补偿，误杀合法用户影响口碑）
- **Set 精确**：SISMEMBER 100% 精确，没误判
- **Set 支持 SREM**：取消订单时要删除一人一单记录（`SREM seckill:order:{voucherId} userId`），布隆过滤器不支持删除

#### 什么时候该换布隆过滤器

- **千万级用户 + 多场秒杀同时进行**：100 个秒杀 × 1000 万用户 = 10 亿元素，Set 占 50-80 GB，布隆过滤器只需 ~1 GB
- **能容忍误判**：如果是营销活动（不是核心交易），误判几个用户可接受

> **本项目 10 万量级 Set 完全够用**。布隆过滤器是"空间优化"手段，不是"功能升级"，在空间不是瓶颈时引入只会增加复杂度。