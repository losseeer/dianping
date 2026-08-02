"""
会话上下文管理 — MySQL 持久化 + Redis 缓存

存储多轮对话历史，始终压缩为 bullet points 摘要注入 plan prompt。

存储:
  MySQL: tb_agent_conversations（source of truth，断电不丢）
  Redis: agent2:conversation:{threadId} → 压缩后的 bullet points 字符串（缓存层，TTL 24h）

压缩策略:
  用户消息简短、助手回复冗长，原始拼接会快速撑爆 token 预算。
  因此每次对话更新后直接 LLM 压缩为 bullet points，plan prompt 始终看到一致格式。

Redis key: agent2:conversation:{threadId}  → 压缩后的 bullet points（缓存）
MySQL table: tb_agent_conversations        → 原始对话记录（持久化）
"""

import json
import logging

from langchain_core.messages import HumanMessage

from config import config
from core.redis import get_redis
from core.llm import get_llm
from core.mysql import (
    append_conversation_turn,
    load_conversation_turns,
    update_conversation_context,
)

logger = logging.getLogger(__name__)

SUMMARIZE_PROMPT = """你是对话上下文压缩器。请将以下多轮对话压缩为简洁的 bullet points 摘要。

要求:
1. 只保留对后续推荐有用的信息（用户意图、偏好、已推荐内容、反馈、关键决策）
2. 每条 bullet point 不超过 50 字
3. 最多 12 条
4. 按时间顺序排列
5. 涉及「已推荐内容」时，保留店名即可，价格/距离/评分等数值通过结构化数据单独提供，不在此处重复

对话历史:
{conversation}

输出 bullet points（每行一条，以 - 开头）:"""


def _redis_key(thread_id: str) -> str:
    return f"{config.CONVERSATION_KEY_PREFIX}{thread_id}"


def format_turns(turns: list[dict]) -> str:
    """格式化对话历史为文本"""
    lines = []
    for t in turns:
        prefix = "用户" if t["role"] == "user" else "助手"
        lines.append(f"{prefix}: {t['content']}")
    return "\n".join(lines)


async def _compress(thread_id: str, turns: list[dict]) -> str:
    """LLM 压缩全部历史对话为 bullet points"""
    try:
        llm = get_llm()
        conv_text = format_turns(turns)
        prompt = SUMMARIZE_PROMPT.format(conversation=conv_text)
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        compressed = response.content.strip()
        logger.debug(f"Conversation compressed: {len(turns)} turns → {len(compressed)} chars")

        # 写入 MySQL（最新一轮的 compressed_context 字段）
        await update_conversation_context(thread_id, compressed)

        # 写入 Redis 缓存（24h TTL）
        r = get_redis()
        r.set(_redis_key(thread_id), compressed, ex=24 * 3600)

        return compressed
    except Exception as e:
        logger.error(f"Conversation compression failed: {e}")
        # 降级：返回最近 3 轮的原始对话
        return format_turns(turns[-3:])


async def append_turn(thread_id: str, user_id: int, role: str, content: str) -> str:
    """
    追加一轮对话。
    1. 写入 MySQL（持久化）
    2. 读取全部历史，LLM 压缩为 bullet points
    3. 缓存到 Redis
    返回压缩后的上下文文本
    """
    # 1. 写入 MySQL
    existing = await load_conversation_turns(thread_id)
    turn_index = len(existing) + 1
    await append_conversation_turn(thread_id, user_id, turn_index, role, content)

    # 2. 重新加载全部历史（含刚写入的）
    all_turns = await load_conversation_turns(thread_id)

    # 3. 始终压缩为 bullet points
    return await _compress(thread_id, all_turns)


async def get_context_summary(thread_id: str) -> str:
    """
    获取会话上下文摘要，用于注入 plan prompt。
    优先读 Redis 缓存，miss 则重新压缩。
    """
    # 1. 先查 Redis 缓存
    r = get_redis()
    cached = r.get(_redis_key(thread_id))
    if cached:
        return cached.decode("utf-8") if isinstance(cached, bytes) else cached

    # 2. miss → 查 MySQL 重新压缩
    turns = await load_conversation_turns(thread_id)
    if not turns:
        return "(新会话，无历史上下文)"

    return await _compress(thread_id, turns)


def clear_conversation(thread_id: str) -> None:
    """清除 Redis 缓存（MySQL 数据保留不删，用于长期分析）"""
    r = get_redis()
    r.delete(_redis_key(thread_id))
    r.delete(_last_shops_key(thread_id))


# ============================================================
# 结构化商铺数据（独立于摘要文本）
# ============================================================

def _last_shops_key(thread_id: str) -> str:
    return f"{config.CONVERSATION_KEY_PREFIX}last_shops:{thread_id}"


def save_last_shops(thread_id: str, shops: list[dict]) -> None:
    """保存上一轮推荐商铺的结构化数据（名称/价格/评分/距离），不压缩"""
    if not shops:
        return
    compact = [{
        "name": s.get("name", ""),
        "avgPrice": s.get("avgPrice"),
        "score": s.get("score"),
        "distance": s.get("distance"),
    } for s in shops[:5]]
    r = get_redis()
    r.set(_last_shops_key(thread_id), json.dumps(compact, ensure_ascii=False),
          ex=config.CONVERSATION_TTL_HOURS * 3600)


def get_last_shops(thread_id: str) -> str:
    """获取上一轮推荐商铺的结构化列表（用于注入 plan prompt）"""
    r = get_redis()
    raw = r.get(_last_shops_key(thread_id))
    if not raw:
        return ""
    data = json.loads(raw) if isinstance(raw, bytes) else json.loads(raw)
    if not data:
        return ""
    lines = []
    for s in data:
        parts = [s.get("name", "?")]
        if s.get("avgPrice"):
            parts.append(f"¥{s['avgPrice']}")
        if s.get("score"):
            parts.append(f"{s['score'] / 10 if s['score'] > 5 else s['score']:.1f}分")
        if s.get("distance") is not None:
            parts.append(f"{s['distance']:.2f}km")
        lines.append(f"- {'  '.join(parts)}")
    return "\n".join(lines)
