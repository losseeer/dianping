-- 幂等恢复一次秒杀资格。
-- ARGV[1] voucherId, ARGV[2] userId, ARGV[3] orderId,
-- ARGV[4] whether to restore Redis stock,
-- ARGV[5] whether to release one-user-one-order record,
-- ARGV[6] current database stock, used only when the Redis stock key is absent
local voucherId = ARGV[1]
local userId = ARGV[2]
local orderId = ARGV[3]
local bootstrapStock = ARGV[6]

local restoredKey = 'seckill:restored:' .. orderId
local stockKey = 'seckill:stock:' .. voucherId
local bootstrapped = false
if redis.call('exists', stockKey) == 0 then
    redis.call('set', stockKey, bootstrapStock)
    bootstrapped = true
end
local stockRestored = 0
if ARGV[4] == '1' then
    if redis.call('set', restoredKey, '1', 'NX') then
        if not bootstrapped then
            local cachedStock = tonumber(redis.call('get', stockKey))
            local databaseStock = tonumber(bootstrapStock)
            if cachedStock ~= nil and databaseStock ~= nil and cachedStock < databaseStock then
                redis.call('incr', stockKey)
            end
        end
        stockRestored = 1
    end
end
if ARGV[5] == '1' then
    redis.call('srem', 'seckill:order:' .. voucherId, userId)
end
redis.call('del', 'seckill:order:pending:' .. orderId)
redis.call('zrem', 'seckill:order:pending:user:' .. userId, orderId)
return stockRestored
