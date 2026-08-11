"""
MySQL 异步客户端 — 长期记忆持久化层

使用 aiomysql 异步驱动连接 dingping 数据库。
MySQL 是 source of truth，Redis 是缓存层。

表结构:
  tb_agent_preferences — 用户偏好（per-user）
  tb_agent_playbook    — Agent经验条目（global）
"""

import json
import logging
from datetime import datetime
from typing import Optional

import aiomysql

from core.config import config

logger = logging.getLogger(__name__)

_pool: Optional[aiomysql.Pool] = None


async def get_pool() -> aiomysql.Pool:
    """获取连接池（单例）"""
    global _pool
    if _pool is None:
        _pool = await aiomysql.create_pool(
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            db=config.MYSQL_DATABASE,
            autocommit=True,
            minsize=2,
            maxsize=10,
            charset="utf8mb4",
        )
    return _pool


async def close_pool():
    """关闭连接池"""
    global _pool
    if _pool:
        _pool.close()
        await _pool.wait_closed()
        _pool = None


# --- preferences 表 CRUD（用户级长期记忆） ---

async def load_preferences(user_id: int) -> Optional[dict]:
    """从 MySQL 读取用户偏好"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT preferences, interaction_count, version, last_updated "
                "FROM tb_agent_preferences WHERE user_id = %s",
                (user_id,),
            )
            row = await cur.fetchone()
            if row:
                prefs = json.loads(row["preferences"]) if isinstance(row["preferences"], str) else row["preferences"]
                return {
                    "userId": user_id,
                    "preferences": prefs.get("preferences", prefs),
                    "lastUpdated": row["last_updated"].isoformat() if row["last_updated"] else None,
                    "interactionCount": row["interaction_count"],
                    "version": row["version"],
                }
    return None


async def save_preferences(user_id: int, memory: dict) -> None:
    """写入/更新用户偏好到 MySQL（UPSERT）"""
    pool = await get_pool()
    prefs_json = json.dumps(memory, ensure_ascii=False)
    interaction_count = memory.get("interactionCount", 0)
    version = memory.get("version", 1)

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO tb_agent_preferences (user_id, preferences, interaction_count, version) "
                "VALUES (%s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE "
                "  preferences = VALUES(preferences), "
                "  interaction_count = VALUES(interaction_count), "
                "  version = VALUES(version)",
                (user_id, prefs_json, interaction_count, version),
            )
    logger.debug(f"MySQL preferences saved for user {user_id}")


# --- playbook 表 CRUD（Agent 级长期记忆） ---

async def load_playbook_entries() -> list[dict]:
    """从 MySQL 读取所有 playbook 条目"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT entry_id, category, description, source, confidence, "
                "times_applied, times_helpful, created_at "
                "FROM tb_agent_playbook ORDER BY confidence DESC"
            )
            rows = await cur.fetchall()
            return [
                {
                    "entryId": r["entry_id"],
                    "category": r["category"],
                    "description": r["description"],
                    "source": r["source"],
                    "confidence": float(r["confidence"]),
                    "timesApplied": r["times_applied"],
                    "timesHelpful": r["times_helpful"],
                    "createdAt": r["created_at"].isoformat() if r["created_at"] else "",
                }
                for r in rows
            ]


async def save_playbook_entry(entry: dict) -> None:
    """写入/更新单个 playbook 条目（UPSERT）"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO tb_agent_playbook "
                "(entry_id, category, description, source, confidence, times_applied, times_helpful) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE "
                "  category = VALUES(category), "
                "  description = VALUES(description), "
                "  source = VALUES(source), "
                "  confidence = VALUES(confidence), "
                "  times_applied = VALUES(times_applied), "
                "  times_helpful = VALUES(times_helpful)",
                (
                    entry["entryId"],
                    entry["category"],
                    entry["description"],
                    entry.get("source", "reflection"),
                    entry.get("confidence", 0.5),
                    entry.get("timesApplied", 0),
                    entry.get("timesHelpful", 0),
                ),
            )


async def delete_playbook_entry(entry_id: str) -> None:
    """删除 playbook 条目"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM tb_agent_playbook WHERE entry_id = %s",
                (entry_id,),
            )


# --- conversation 表 CRUD（MySQL 持久化 + Redis 缓存） ---

async def append_conversation_turn(
    thread_id: str, user_id: int, turn_index: int, role: str, content: str
) -> None:
    """追加一轮对话到 MySQL"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO tb_agent_conversations "
                "(thread_id, user_id, turn_index, role, content) "
                "VALUES (%s, %s, %s, %s, %s)",
                (thread_id, user_id, turn_index, role, content[:500]),
            )


async def load_conversation_turns(thread_id: str) -> list[dict]:
    """从 MySQL 加载会话历史（按轮次排序）"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT thread_id, user_id, turn_index, role, content, compressed_context, created_at "
                "FROM tb_agent_conversations WHERE thread_id = %s "
                "ORDER BY turn_index ASC",
                (thread_id,),
            )
            rows = await cur.fetchall()
            return [
                {
                    "threadId": r["thread_id"],
                    "userId": r["user_id"],
                    "turnIndex": r["turn_index"],
                    "role": r["role"],
                    "content": r["content"],
                    "compressedContext": r["compressed_context"],
                    "createdAt": r["created_at"].isoformat() if r["created_at"] else "",
                }
                for r in rows
            ]


async def update_conversation_context(thread_id: str, compressed: str) -> None:
    """更新最新一轮的压缩上下文（缓存，避免每次重算）"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE tb_agent_conversations "
                "SET compressed_context = %s "
                "WHERE thread_id = %s "
                "ORDER BY turn_index DESC LIMIT 1",
                (compressed, thread_id),
            )
