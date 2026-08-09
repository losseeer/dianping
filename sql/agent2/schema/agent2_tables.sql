-- =====================================================================
-- Agent 用户偏好长期记忆表 - SQL迁移脚本
-- 执行前请确保已连接到 dingping 数据库
-- =====================================================================

USE dingping;

-- Agent 用户偏好表（MySQL 为 source of truth，Redis 为缓存）
DROP TABLE IF EXISTS `tb_agent_preferences`;
CREATE TABLE `tb_agent_preferences` (
    `user_id` BIGINT UNSIGNED NOT NULL COMMENT '用户ID（关联 tb_user.id）',
    `preferences` JSON NOT NULL COMMENT '偏好JSON：likedCategories/priceRange/environmentPreference/avoidFactors/foodPreferences/frequentAreas/specialRequirements',
    `last_updated` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
    `interaction_count` INT NOT NULL DEFAULT 0 COMMENT '交互次数（每次更新偏好+1）',
    `version` INT NOT NULL DEFAULT 1 COMMENT '记忆版本号（schema变更时递增）',
    PRIMARY KEY (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='Agent用户偏好长期记忆（MySQL持久化 + Redis缓存）';

-- 验证
SELECT 'tb_agent_preferences 表创建成功' AS `message` FROM DUAL WHERE EXISTS (
    SELECT 1 FROM information_schema.tables WHERE table_schema = 'dingping' AND table_name = 'tb_agent_preferences'
);


-- ==========================================
-- Agent Playbook 经验条目表（全局长期记忆）
-- ==========================================

DROP TABLE IF EXISTS `tb_agent_playbook`;
CREATE TABLE `tb_agent_playbook` (
    `entry_id` VARCHAR(32) NOT NULL COMMENT '条目ID',
    `category` VARCHAR(32) NOT NULL COMMENT '分类：intent_parsing/tool_selection/hitl_trigger/ranking/context_gap',
    `description` TEXT NOT NULL COMMENT '经验描述',
    `source` VARCHAR(32) NOT NULL DEFAULT 'reflection' COMMENT '来源：reflection/weakness_mining/user_feedback',
    `confidence` DECIMAL(3,2) NOT NULL DEFAULT 0.50 COMMENT '置信度 0.00-1.00',
    `times_applied` INT NOT NULL DEFAULT 0 COMMENT '被应用次数',
    `times_helpful` INT NOT NULL DEFAULT 0 COMMENT '有效次数',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`entry_id`),
    KEY `idx_category` (`category`),
    KEY `idx_confidence` (`confidence`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='Agent全局经验Playbook（MySQL持久化 + Redis缓存）';

-- 验证
SELECT 'tb_agent_playbook 表创建成功' AS `message` FROM DUAL WHERE EXISTS (
    SELECT 1 FROM information_schema.tables WHERE table_schema = 'dingping' AND table_name = 'tb_agent_playbook'
);


-- ==========================================
-- Agent 会话对话历史表（MySQL 持久化 + Redis 缓存）
-- ==========================================

DROP TABLE IF EXISTS `tb_agent_conversations`;
CREATE TABLE `tb_agent_conversations` (
    `thread_id` VARCHAR(64) NOT NULL COMMENT '会话ID',
    `user_id` BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    `turn_index` INT NOT NULL COMMENT '对话轮次序号（从1开始）',
    `role` VARCHAR(16) NOT NULL COMMENT '角色：user/assistant',
    `content` TEXT NOT NULL COMMENT '对话内容（截断500字）',
    `compressed_context` TEXT DEFAULT NULL COMMENT '压缩后的bullet points摘要（缓存，避免每次重算）',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`thread_id`, `turn_index`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_thread_created` (`thread_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='Agent会话对话历史（MySQL持久化）';

-- 验证
SELECT 'tb_agent_conversations 表创建成功' AS `message` FROM DUAL WHERE EXISTS (
    SELECT 1 FROM information_schema.tables WHERE table_schema = 'dingping' AND table_name = 'tb_agent_conversations'
);
