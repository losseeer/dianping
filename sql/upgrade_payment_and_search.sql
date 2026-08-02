-- =====================================================================
-- 交易闭环 & 搜索推荐模块 - SQL迁移脚本
-- 执行前请确保已连接到 dingping 数据库
-- =====================================================================
use dingping;
-- ==========================================
-- 模块一：交易闭环 - 支付流水表
-- ==========================================

-- 支付流水表
DROP TABLE IF EXISTS `tb_pay_log`;
CREATE TABLE `tb_pay_log` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    `order_id` BIGINT NOT NULL COMMENT '业务订单号（tb_voucher_order.id）',
    `user_id` BIGINT NOT NULL COMMENT '用户id',
    `pay_type` TINYINT NOT NULL COMMENT '支付方式 1余额 2支付宝 3微信',
    `trade_no` VARCHAR(64) DEFAULT NULL COMMENT '第三方支付流水号',
    `amount` BIGINT NOT NULL DEFAULT 0 COMMENT '支付金额（分）',
    `status` TINYINT NOT NULL DEFAULT 1 COMMENT '支付状态 1待支付 2成功 3失败 4已退款',
    `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `pay_time` DATETIME DEFAULT NULL COMMENT '支付完成时间',
    `refund_time` DATETIME DEFAULT NULL COMMENT '退款时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_trade_no` (`trade_no`),
    KEY `idx_order_id` (`order_id`),
    KEY `idx_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='支付流水表';


-- ==========================================
-- 更新现有 tb_voucher_order 表
-- 添加默认值，确保新订单初始状态正确
-- ==========================================

-- 为已有订单补充默认状态（如果status为NULL）
UPDATE `tb_voucher_order` SET `status` = 2 WHERE `status` IS NULL;  -- 历史订单默认标记为已支付
UPDATE `tb_voucher_order` SET `pay_type` = 1 WHERE `pay_type` IS NULL;  -- 历史订单默认余额支付
UPDATE `tb_voucher_order` SET `create_time` = NOW() WHERE `create_time` IS NULL;

-- 设置status默认值为1（待支付）
ALTER TABLE `tb_voucher_order` MODIFY COLUMN `status` INT NOT NULL DEFAULT 1 COMMENT '订单状态 1待支付 2已支付 3已核销 4已取消 5退款中 6已退款';
ALTER TABLE `tb_voucher_order` MODIFY COLUMN `pay_type` INT DEFAULT NULL COMMENT '支付方式 1余额 2支付宝 3微信';


-- ==========================================
-- 模块二：搜索与推荐 - tb_shop 表新增 tags 字段
-- ==========================================

-- 为商铺表添加tags字段，用于ES全文搜索（幂等：先检查是否存在）
SET @col_exists = (SELECT COUNT(*) FROM information_schema.columns
    WHERE table_schema = 'dingping' AND table_name = 'tb_shop' AND column_name = 'tags');
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE `tb_shop` ADD COLUMN `tags` VARCHAR(255) DEFAULT NULL COMMENT ''商铺标签，逗号分隔，如：好吃,牛排,火锅''',
    'SELECT "tags 字段已存在，跳过" AS msg');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 为已有商铺补充标签数据（基于类型和评分）
UPDATE `tb_shop` SET `tags` = CONCAT('好吃,热门,评分高') WHERE `score` >= 40 AND `tags` IS NULL;
UPDATE `tb_shop` SET `tags` = CONCAT('性价比,推荐') WHERE `score` >= 30 AND `score` < 40 AND `tags` IS NULL;
UPDATE `tb_shop` SET `tags` = '普通' WHERE `tags` IS NULL;


-- ==========================================
-- 验证脚本
-- ==========================================

-- 验证支付流水表
SELECT 'tb_pay_log 表创建成功' AS `message` FROM DUAL WHERE EXISTS (
    SELECT 1 FROM information_schema.tables WHERE table_schema = 'dingping' AND table_name = 'tb_pay_log'
);

-- 验证订单表状态字段
SELECT 'tb_voucher_order.status 默认值设置成功' AS `message`
FROM information_schema.columns
WHERE table_schema = 'dingping' AND table_name = 'tb_voucher_order' AND column_name = 'status' AND column_default = '1';

-- 验证商铺表tags字段
SELECT 'tb_shop.tags 字段添加成功' AS `message`
FROM information_schema.columns
WHERE table_schema = 'dingping' AND table_name = 'tb_shop' AND column_name = 'tags';
