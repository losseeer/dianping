-- =====================================================================
-- 秒杀Lua脚本 —— 【八股：为什么用Lua脚本保证原子性？】
--
-- 【八股：Redis单线程模型】
-- Redis是单线程的，所有命令按顺序串行执行
-- 但单条命令是原子的，多条命令之间可能被其他客户端插入
-- Lua脚本的作用就是把多条命令打包成一个整体，Redis一次性执行完
-- 这样就保证了"判断库存→判断是否下单→扣库存→记录订单→发消息"的原子性
--
-- 【八股：Lua脚本的执行规则】
-- 1. Redis执行Lua脚本时，不会执行其他命令或脚本，原子性有保障
-- 2. 脚本执行时间不能太长，否则会阻塞其他请求（Redis是单线程的！）
-- 3. KEYS[1..N] 是脚本操作的Redis键，ARGV[1..N] 是参数
--
-- 【八股：返回值约定】
-- -1：库存key不存在（还没预热）
--  0：秒杀成功
--  1：库存不足
--  2：重复下单
-- =====================================================================

-- 1.参数列表
--1.1.优惠券id
local voucherId=ARGV[1]
--1.2.用户id
local userId=ARGV[2]
--1.3.订单id
local orderId=ARGV[3]

-- 2.数据key
--2.1.库存key
local stockKey='seckill:stock:' .. voucherId
--2.2.订单key
local orderKey='seckill:order:' .. voucherId

-- 3.脚本业务
--3.1.判断库存是否充足
local stock = tonumber(redis.call('get', stockKey))
if stock == nil then
    --print("库存获取失败: " .. stockKey)
    return -1
end

if (stock<= 0) then
    --3.2.库存不足，返回1
    return 1
end
--3.3.判断用户是否下单
-- 【八股：为什么用Set存订单？】
-- SISMEMBER O(1) 判断用户是否已经下单
-- 一人一单的核心判断：如果用户ID已经在Set里，说明已经下过单了
-- 用Set而不是其他结构，就是因为SISMEMBER判断存在的性能最好
if(redis.call('sismember',orderKey,userId)==1) then
    --3.4.存在，说明重复下单，返回2
    return 2
end
-- 3.5.扣库存 incrby stockKey -1
-- 【八股：incrby的原子性】
-- Redis的INCRBY命令本身就是原子的
-- 但"判断库存 + 扣减库存"如果分开执行就不是原子的
-- 放在Lua脚本里，整个流程才是原子的
redis.call('incrby',stockKey,-1)
-- 3.6.下单(保存)用户 sadd orderKey userId
redis.call('sadd',orderKey,userId)
-- 3.7. 发消息到消息队列中 XADD  stream.orders * k1 v1 k2 v2
-- 【八股：为什么Lua脚本里直接发消息到Stream？】
-- 把"扣库存+记录订单+发消息"都放在Lua里原子执行
-- 确保只要库存扣了，消息就一定发出去了（要么都成功，要么都失败）
-- 后续消费者从Stream里消费消息，异步创建数据库订单
redis.call('xadd','stream.orders','*', 'userId',userId,'voucherId',voucherId,'id',orderId)
