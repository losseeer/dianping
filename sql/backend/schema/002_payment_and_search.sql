-- =====================================================================
-- 交易闭环 & 搜索推荐模块 - SQL迁移脚本
-- 执行前请确保已连接到 dingping 数据库
-- =====================================================================
use dingping;
-- ==========================================
-- 模块一：交易闭环 - 支付流水表
-- ==========================================

-- 支付流水表
CREATE TABLE IF NOT EXISTS `tb_pay_log` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    `order_id` BIGINT NOT NULL COMMENT '业务订单号（tb_voucher_order.id）',
    `user_id` BIGINT NOT NULL COMMENT '用户id',
    `pay_type` TINYINT NOT NULL COMMENT '支付方式 1余额 2支付宝 3微信',
    `trade_no` VARCHAR(64) DEFAULT NULL COMMENT '第三方支付流水号',
    `amount` BIGINT NOT NULL DEFAULT 0 COMMENT '支付金额（分）',
    `status` TINYINT NOT NULL DEFAULT 1 COMMENT '支付状态 1待支付 2成功 3失败 4已退款',
    `pending_flag` TINYINT NULL DEFAULT 1 COMMENT '待支付流水唯一约束标记，终态为NULL',
    `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `pay_time` DATETIME DEFAULT NULL COMMENT '支付完成时间',
    `refund_time` DATETIME DEFAULT NULL COMMENT '退款时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_trade_no` (`trade_no`),
    KEY `idx_order_id` (`order_id`),
    KEY `idx_user_id` (`user_id`),
    UNIQUE KEY `uk_pending_order` (`order_id`, `pending_flag`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='支付流水表';

CREATE TABLE IF NOT EXISTS `tb_transaction_outbox` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `event_key` VARCHAR(128) NOT NULL,
    `event_type` VARCHAR(32) NOT NULL,
    `aggregate_id` BIGINT NOT NULL,
    `payload` TEXT NOT NULL,
    `status` TINYINT NOT NULL DEFAULT 0 COMMENT '0待发送 1已发送 2发送中',
    `retry_count` INT NOT NULL DEFAULT 0,
    `next_retry_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_event_key` (`event_key`),
    KEY `idx_outbox_pending` (`status`, `next_retry_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='交易事件Outbox';


-- ==========================================
-- 更新现有 tb_voucher_order 表
-- 添加默认值，确保新订单初始状态正确
-- ==========================================

-- 为已有订单补充默认状态（如果status为NULL）
UPDATE `tb_voucher_order` SET `status` = 2 WHERE `status` IS NULL;  -- 历史订单默认标记为已支付
UPDATE `tb_voucher_order` SET `pay_type` = 1 WHERE `pay_type` IS NULL;  -- 历史订单默认余额支付
UPDATE `tb_voucher_order` SET `create_time` = NOW() WHERE `create_time` IS NULL;

-- 设置status默认值为1（待支付）
ALTER TABLE `tb_voucher_order` MODIFY COLUMN `status` TINYINT(1) UNSIGNED NOT NULL DEFAULT 1 COMMENT '订单状态 1待支付 2已支付 3已核销 4已取消 5退款中 6已退款';
ALTER TABLE `tb_voucher_order` MODIFY COLUMN `pay_type` TINYINT(1) UNSIGNED NULL DEFAULT NULL COMMENT '支付方式 1余额 2支付宝 3微信';

SET @col_exists = (SELECT COUNT(*) FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'tb_voucher_order' AND column_name = 'active_flag');
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE `tb_voucher_order` ADD COLUMN `active_flag` TINYINT NULL DEFAULT 1 COMMENT ''有效订单唯一约束标记，终态为NULL'' AFTER `status`',
    'SELECT "active_flag 已存在，跳过" AS msg');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
UPDATE `tb_voucher_order`
SET `active_flag` = IF(`status` IN (1, 2, 3, 5), 1, NULL);

SET @col_exists = (SELECT COUNT(*) FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'tb_voucher_order' AND column_name = 'amount');
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE `tb_voucher_order` ADD COLUMN `amount` BIGINT NULL DEFAULT NULL COMMENT ''下单金额快照（分）'' AFTER `active_flag`',
    'SELECT "amount 已存在，跳过" AS msg');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
UPDATE `tb_voucher_order` o
JOIN `tb_voucher` v ON v.id = o.voucher_id
SET o.amount = v.pay_value
WHERE o.amount IS NULL;

SET @col_exists = (SELECT COUNT(*) FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'tb_pay_log' AND column_name = 'pending_flag');
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE `tb_pay_log` ADD COLUMN `pending_flag` TINYINT NULL DEFAULT 1 COMMENT ''待支付流水唯一约束标记，终态为NULL'' AFTER `status`',
    'SELECT "pending_flag 已存在，跳过" AS msg');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
UPDATE `tb_pay_log` SET `pending_flag` = IF(`status` = 1, 1, NULL);
ALTER TABLE `tb_pay_log`
    MODIFY COLUMN `pending_flag` TINYINT NULL DEFAULT 1 COMMENT '待支付流水唯一约束标记，终态为NULL';

-- 查询索引。MySQL 8.0 不支持 CREATE INDEX IF NOT EXISTS，因此通过 information_schema 幂等创建。
SET @idx_exists = (SELECT COUNT(*) FROM information_schema.statistics
    WHERE table_schema = DATABASE() AND table_name = 'tb_voucher_order'
      AND index_name = 'idx_user_status_time');
SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX `idx_user_status_time` ON `tb_voucher_order` (`user_id`, `status`, `create_time`)',
    'SELECT "idx_user_status_time 已存在，跳过" AS msg');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @idx_exists = (SELECT COUNT(*) FROM information_schema.statistics
    WHERE table_schema = DATABASE() AND table_name = 'tb_pay_log'
      AND index_name = 'uk_pending_order');
UPDATE `tb_pay_log` p
JOIN (
    SELECT `order_id`, MAX(`id`) AS keep_id
    FROM `tb_pay_log`
    WHERE `status` = 1
    GROUP BY `order_id`
    HAVING COUNT(*) > 1
) duplicated ON duplicated.order_id = p.order_id
SET p.status = 3, p.pending_flag = NULL
WHERE p.status = 1 AND p.id <> duplicated.keep_id;
SET @sql = IF(@idx_exists = 0,
    'CREATE UNIQUE INDEX `uk_pending_order` ON `tb_pay_log` (`order_id`, `pending_flag`)',
    'SELECT "uk_pending_order 已存在，跳过" AS msg');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @idx_exists = (SELECT COUNT(*) FROM information_schema.statistics
    WHERE table_schema = DATABASE() AND table_name = 'tb_voucher_order'
      AND index_name = 'uk_active_user_voucher');
SET @sql = IF(@idx_exists = 0,
    'CREATE UNIQUE INDEX `uk_active_user_voucher` ON `tb_voucher_order` (`user_id`, `voucher_id`, `active_flag`)',
    'SELECT "uk_active_user_voucher 已存在，跳过" AS msg');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @idx_exists = (SELECT COUNT(*) FROM information_schema.statistics
    WHERE table_schema = DATABASE() AND table_name = 'tb_voucher_order'
      AND index_name = 'idx_user_voucher_status');
SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX `idx_user_voucher_status` ON `tb_voucher_order` (`user_id`, `voucher_id`, `status`)',
    'SELECT "idx_user_voucher_status 已存在，跳过" AS msg');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;


-- ==========================================
-- 模块二：搜索与推荐 - tb_shop 表新增 tags 字段
-- ==========================================

-- 为商铺表添加tags字段，用于ES全文搜索（幂等：先检查是否存在）
SET @col_exists = (SELECT COUNT(*) FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'tb_shop' AND column_name = 'tags');
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
    SELECT 1 FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'tb_pay_log'
);

-- 验证订单表状态字段
SELECT 'tb_voucher_order.status 默认值设置成功' AS `message`
FROM information_schema.columns
WHERE table_schema = DATABASE() AND table_name = 'tb_voucher_order' AND column_name = 'status' AND column_default = '1';

-- 验证商铺表tags字段
SELECT 'tb_shop.tags 字段添加成功' AS `message`
FROM information_schema.columns
WHERE table_schema = DATABASE() AND table_name = 'tb_shop' AND column_name = 'tags';
