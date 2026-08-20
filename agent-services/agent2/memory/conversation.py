"""
会话上下文管理 — MySQL 持久化原始对话 + Redis 缓存压缩后的 bullet points。

助手回复冗长，原始拼接会撑爆 token 预算，故每次更新后 LLM 压缩为 bullet points 注入 plan prompt。

【重构 2026-08】压缩过程改为异步 fire-and-forget + dirty 标记的 piggyback 兜底：
- 写 MySQL 原始对话必须同步（保证下一轮立即可读）
- LLM 压缩用 asyncio.create_task() 放到事件循环后台，不阻塞请求返回
- 读路径若发现 miss 或 dirty，降级返回最近3轮原始对话，piggyback 触发后台压缩
"""

import asyncio
import json
import logging

from langchain_core.messages import HumanMessage

from core.config import config
from core.redis import get_redis
from core.llm import get_llm, call_llm, reset_token_usage
from core.mysql_store import (
    append_conversation_turn,
    load_conversation_turns,
    update_conversation_context,
)
from graph.utils import normalize_score

logger = logging.getLogger(__name__)
# 【八股：in-flight 去重——同 thread 并发压缩防护】
# 同一会话连续两轮对话会连调两次 append_turn，若不判重会同时起两个压缩任务：
# 浪费一次 LLM 调用，且两个任务写 Redis/MySQL 的顺序不确定（旧结果可能覆盖新结果）
# 这个 set 记录「正在压缩中」的 thread_id，任务结束（finally）才移除。
# 注：单进程方案，多 worker 部署时应改用 Redis SETNX 分布式判重
_compressing_threads: set[str] = set()

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


def _dirty_key(thread_id: str) -> str:
    return f"{_redis_key(thread_id)}:dirty"


def format_turns(turns: list[dict]) -> str:
    """格式化对话历史为文本"""
    lines = []
    for t in turns:
        prefix = "用户" if t["role"] == "user" else "助手"
        lines.append(f"{prefix}: {t['content']}")
    return "\n".join(lines)


async def _compress(thread_id: str, turns: list[dict]) -> str:
    """LLM 压缩全部历史对话为 bullet points，成功后写入 MySQL + Redis 并清除 dirty 标记。"""
    try:
        conv_text = format_turns(turns)
        prompt = SUMMARIZE_PROMPT.format(conversation=conv_text)
        response = await call_llm([HumanMessage(content=prompt)])
        compressed = response.content.strip()
        logger.debug(f"Conversation compressed: {len(turns)} turns → {len(compressed)} chars")

        # 写入 MySQL compressed_context 字段
        try:
            await update_conversation_context(thread_id, compressed)
        except Exception as e:
            logger.warning(f"update_conversation_context failed (non-fatal): {e}")

        r = get_redis()
        r.set(_redis_key(thread_id), compressed, ex=24 * 3600)
        # 压缩成功，清除 dirty 标记
        r.delete(_dirty_key(thread_id))

        return compressed
    except Exception as e:
        logger.warning(f"Conversation compression (async) failed: {e}")
        # 失败不清 dirty，留给 piggyback 重试；降级返回值调用方不会用到（异步场景）
        return format_turns(turns[-3:])


async def append_turn(thread_id: str, user_id: int, role: str, content: str) -> str:
    """
    追加一轮对话（返回空字符串：签名兼容旧调用方赋值，不阻塞）。

    同步：写 MySQL 原始对话 → 标记 dirty → 返回
    异步：fire-and-forget 触发 _compress 后台执行，完成后自动清 dirty
    """
    # 1. 写 MySQL 原始对话（必须同步，保证下一轮立即可读）
    try:
        existing = await load_conversation_turns(thread_id)
    except Exception as e:
        logger.warning(f"load_conversation_turns failed in append_turn: {e}")
        existing = []
    turn_index = len(existing) + 1
    try:
        await append_conversation_turn(thread_id, user_id, turn_index, role, content)
    except Exception as e:
        logger.warning(f"append_conversation_turn failed: {e}")

    # 2. 标记 dirty（piggyback 兜底用：万一台任务没跑完，下次请求补做）
    r = get_redis()
    r.setex(_dirty_key(thread_id), 24 * 3600, "1")

    # 3. 立刻 fire-and-forget 触发后台压缩（方案 A）
    # 【八股：fire-and-forget 的风险与兜底——为什么还要 dirty 标记？】
    # create_task 把协程排入事件循环就返回，主请求不等压缩完成（省 1~2s LLM 延迟）
    # 但后台任务可能失败甚至根本没跑（进程重启）——「发了就算完成」是不可靠投递
    # dirty 标记 = 持久化的「待办」：写 MySQL 原文后立刻置位，压缩成功才清除
    # 读路径发现 dirty 残留 → 说明后台没跑成 → piggyback 顺手补一次（最终一致性）
    # 同一模式也用在 improve/signals.py（piggyback + daemon 双触发）
    try:
        all_turns = await load_conversation_turns(thread_id)
    except Exception as e:
        logger.warning(f"reload turns for compress failed: {e}")
        all_turns = existing

    async def _bg_compress():
        """后台压缩任务：吞掉所有异常，不能让它崩主事件循环"""
        # 重置 token 计数：后台任务不应计入主请求的 tokenUsage 统计（asyncio Task 继承 context，set 会本地化生效）
        # 【八股：asyncio.Task 的上下文拷贝语义】
        # create_task 时框架 copy_context() 拷贝当前上下文给新任务，
        # 任务内 contextvar.set() 只写进自己的副本，主请求上下文不受影响——
        # 所以这里 reset_token_usage() 不会把主请求的统计清零
        try:
            reset_token_usage()
        except Exception:  # noqa: BLE001
            pass
        try:
            await _compress(thread_id, all_turns)
        except Exception as e:
            logger.warning(f"Background compress silently failed for thread {thread_id}: {e}")
        finally:
            _compressing_threads.discard(thread_id)

    try:
        loop = asyncio.get_running_loop()
        task = None
        if thread_id not in _compressing_threads:
            _compressing_threads.add(thread_id)
            task = loop.create_task(_bg_compress())

        def _log_done(t: asyncio.Task):
            try:
                if t.cancelled():
                    logger.debug(f"Compress task cancelled for {thread_id}")
                elif (exc := t.exception()) is not None:
                    logger.error(f"Compress task exception for {thread_id}: {exc}")
            except Exception:  # noqa: BLE001
                pass
            finally:
                _compressing_threads.discard(thread_id)
        if task:
            task.add_done_callback(_log_done)
    except RuntimeError:
        # 没有运行中的事件循环（比如单元测试直接调用），退化为同步 _compress，但不 await 其返回值
        logger.debug("No running loop, append_turn skipping background compress (will piggyback later)")

    # 4. 立即返回空串，不等待压缩完成（兼容旧调用方赋值表达式）
    return ""


async def get_context_summary(thread_id: str) -> str:
    """
    获取会话上下文摘要，用于注入 plan prompt。

    优先级：
      Redis 缓存命中 且 无 dirty 标记 → 直接返回
      否则 → 降级返回最近3轮原始对话，有 dirty 时顺便 piggyback kick 一次后台压缩
    """
    r = get_redis()
    cached = r.get(_redis_key(thread_id))
    dirty = r.get(_dirty_key(thread_id))

    cached_str = None
    if cached:
        cached_str = cached.decode("utf-8") if isinstance(cached, bytes) else cached

    # 命中缓存且没有 dirty 标记 → 直接用（90% 场景走这里）
    if cached_str and not dirty:
        return cached_str

    # === 降级路径：要么 miss，要么 dirty ===
    try:
        turns = await load_conversation_turns(thread_id)
    except Exception as e:
        logger.warning(f"load_conversation_turns failed in get_context_summary: {e}")
        turns = []
    if not turns:
        return "(新会话，无历史上下文)"

    # dirty 且缓存 miss → piggyback kick 一次后台压缩（方案 B 兜底），不等待
    # 【八股：piggyback（搭便车）模式——用读请求补写路径的洞】
    # 后台压缩任务失败/进程重启后，dirty 标记会一直挂着。
    # 与其起定时任务轮询，不如让下一次读请求「顺路」发现并补做：
    # - 有流量 → 自然自愈，且天然按需（没流量就不浪费 LLM 调用）
    # - 读请求本身不等待补做完成，仍然降级返回最近3轮原文（正确性不丢，只是 token 多一点）
    if dirty and not cached_str and thread_id not in _compressing_threads:
        async def _bg_compress_piggyback():
            try:
                reset_token_usage()
            except Exception:  # noqa: BLE001
                pass
            try:
                await _compress(thread_id, turns)
            except Exception as e:
                logger.warning(f"Piggyback compress silently failed: {e}")
            finally:
                _compressing_threads.discard(thread_id)
        try:
            loop = asyncio.get_running_loop()
            _compressing_threads.add(thread_id)
            task = loop.create_task(_bg_compress_piggyback())
            task.add_done_callback(lambda _: _compressing_threads.discard(thread_id))
        except RuntimeError:
            logger.debug("No running loop, piggyback compress skipped (next request will retry)")

    # 降级：返回最近3轮原始对话（正确性比压缩更好，只是 token 稍多）
    return format_turns(turns[-3:])


def clear_conversation(thread_id: str) -> None:
    """清除 Redis 缓存（MySQL 数据保留不删，用于长期分析）"""
    r = get_redis()
    r.delete(_redis_key(thread_id))
    r.delete(_last_shops_key(thread_id))
    r.delete(_recommended_ids_key(thread_id))


# --- 结构化商铺数据（独立于摘要文本） ---

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
            parts.append(f"{normalize_score(s['score']):.1f}分")
        if s.get("distance") is not None:
            parts.append(f"{s['distance']:.2f}km")
        lines.append(f"- {'  '.join(parts)}")
    return "\n".join(lines)


# --- 已推荐商铺去重（会话级） ---

def _recommended_ids_key(thread_id: str) -> str:
    return f"{config.CONVERSATION_KEY_PREFIX}recommended_ids:{thread_id}"


def get_recommended_ids(thread_id: str) -> list[int]:
    """获取本会话已推荐过的商铺 ID 列表（用于多轮去重）。"""
    r = get_redis()
    raw = r.get(_recommended_ids_key(thread_id))
    if not raw:
        return []
    data = json.loads(raw) if isinstance(raw, bytes) else json.loads(raw)
    return data if isinstance(data, list) else []


def add_recommended_ids(thread_id: str, shop_ids: list[int]) -> None:
    """将本轮推荐的商铺 ID 追加到会话级去重列表。"""
    if not shop_ids:
        return
    existing = set(get_recommended_ids(thread_id))
    existing.update(shop_ids)
    r = get_redis()
    r.set(_recommended_ids_key(thread_id), json.dumps(list(existing), ensure_ascii=False),
          ex=config.CONVERSATION_TTL_HOURS * 3600)
