"""
信号管线：轨迹「接受信号」判定 + 待处理队列 + 幂等去重标记 + 后台蒸馏 daemon。

队列设计（纯 Redis，零依赖）：
  - PENDING_ZSET    ：待蒸馏队列（zset，score = 轨迹落盘秒级时间戳，value = trajectory_id）
  - PROCESSED_PREFIX：processed marker hash（key 存在即已处理，24h TTL，避免重复蒸馏）
  - DISTILL_LAST_KEY：上次 piggyback 扫描完成时间（避免同一进程扫得太勤）

蒸馏执行 — 双保险：
  A) Piggyback（近实时）：每次轨迹落盘入队后 fire-and-forget 触发一批，≥30s 节流，单轮 ≤2.5s / ≤4 条。
  B) Daemon loop（兜底）：FastAPI 启动时起一个后台 asyncio 任务，每 5 分钟扫一批（≤16 条），保证 piggyback 没来得及跑的也会被兜底处理。

信号策略（阶段 4）：
  「用户接受推荐」→ 作为 Playbook 蒸馏的 ground-truth 信号。
  - 显式信号（未来接入）：TrajectoryRecord.outcome == "accepted"
  - 隐式信号（阶段 4 默认启用）：outcome == "unknown"（用户无负反馈）且 candidateCount>0（有推荐结果）且 HITL<=1（流程没走歪）
  - 负信号（跳过蒸馏）：outcome == "rejected"，或 reflection_score < 4（烂轨迹不学）
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from core.config import config
from core.redis import get_redis
from core.models import TrajectoryRecord

logger = logging.getLogger(__name__)

PENDING_ZSET = f"{config.MEMORY_KEY_PREFIX}distill:pending"
PROCESSED_PREFIX = f"{config.MEMORY_KEY_PREFIX}distill:done:"
DISTILL_LAST_KEY = f"{config.MEMORY_KEY_PREFIX}distill:last_scan"
PROCESSED_TTL = 24 * 3600
MIN_COOL_SECONDS = 60           # 轨迹落盘后至少 60s 才蒸馏（等用户继续交互，避免 5s 内被抢跑）
PIGGYBACK_MIN_INTERVAL = 30     # piggyback 扫描最少间隔 30s（避免大流量下反复扫）
MAX_PER_BATCH = 8
DAEMON_INTERVAL_SECONDS = 300   # 兜底 daemon loop：5 分钟跑一批
DAEMON_BATCH_SIZE = 16

_acceptance_negative_outcomes = {"rejected", "timeout"}


# ---------- 入队 / 状态查询 ----------

def enqueue_for_distill(trajectory_id: str, schedule_piggyback: bool = True) -> None:
    """轨迹落盘后调用：写入待处理 zset，score=now，24h 过期；默认触发一次 piggyback fire-and-forget。"""
    if not trajectory_id:
        return
    r = get_redis()
    now = int(time.time())
    r.zadd(PENDING_ZSET, {trajectory_id: now})
    r.expire(PENDING_ZSET, PROCESSED_TTL)

    if schedule_piggyback and piggyback_should_run():
        # fire-and-forget：不等待，不 catch；worker 内部自己处理异常并记录日志
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                from improve.worker import piggyback_scan  # 延迟 import 避免循环
                loop.create_task(piggyback_scan())
        except RuntimeError:
            # 无运行中的 event loop（例如测试/脚本）——跳过，等 daemon loop 兜底
            pass


def is_processed(trajectory_id: str) -> bool:
    return bool(get_redis().exists(f"{PROCESSED_PREFIX}{trajectory_id}"))


def mark_processed(trajectory_id: str, status: str = "ok") -> None:
    get_redis().setex(
        f"{PROCESSED_PREFIX}{trajectory_id}",
        PROCESSED_TTL,
        status or "ok",
    )


# ---------- 信号判定 ----------

def detect_acceptance(record: TrajectoryRecord) -> bool:
    """
    阶段 4 信号判定：返回 True 表示可以蒸馏；False 跳过。

    优先级：
    1. 显式接受 outcome == "accepted" → True（未来接入用户显式反馈时生效，默认 outcome 现在是 unknown）
    2. 显式拒绝 outcome in rejected_set → False
    3. 烂轨迹：reflection_score ∈ (0,4) 或 candidateCount=0 或 HITL 触发且候选不足 → False（不学）
    4. 隐式接受（默认）：outcome == "unknown" 且 candidateCount > 0 且 hitlTriggered=False 或 (hitlTriggered 但 candidateCount>=AGENT2_MIN_CANDIDATES) → True
    5. 其他 → False
    """
    if not record or not record.trajectoryId:
        return False

    # 1) 显式接受
    if record.outcome == "accepted":
        return True
    # 2) 显式拒绝
    if record.outcome in _acceptance_negative_outcomes:
        return False
    # 3) 烂轨迹
    if 0 < record.reflectionScore < 4.0:
        return False
    if record.candidateCount <= 0:
        return False
    # 4) 隐式接受：unknown + 有候选 + (没打 HITL，或 HITL 但最后也≥3 家)
    if record.outcome in ("unknown", None):
        if not record.hitlTriggered:
            return True
        if record.hitlTriggered and record.candidateCount >= max(3, config.AGENT2_MIN_CANDIDATES):
            return True
    return False


# ---------- 出队（worker / piggyback 用） ----------

def pop_pending_batch(
    max_items: int = MAX_PER_BATCH,
    min_cool_seconds: int = MIN_COOL_SECONDS,
) -> list[str]:
    """
    取一批「已冷却」的 trajectory_id 列表（不做 zrem，由 worker 调 mark_processed 去重，避免 crash 丢任务）。
    - 扫 score 在 [0, now-min_cool] 的元素
    - 结果只取前 max_items
    """
    r = get_redis()
    now = int(time.time())
    max_score = now - min_cool_seconds
    ids_bytes = r.zrangebyscore(PENDING_ZSET, 0, max_score, 0, max_items)
    ids = [b.decode() if isinstance(b, bytes) else b for b in ids_bytes]
    # 幂等预过滤：已处理的先从 zset 移除（省得下次再扫），剩下的作为本批
    out: list[str] = []
    to_rem: list[str] = []
    for tid in ids:
        if is_processed(tid):
            to_rem.append(tid)
        else:
            out.append(tid)
    if to_rem:
        r.zrem(PENDING_ZSET, *to_rem)
    return out


def _set_last_scan_ts() -> None:
    get_redis().set(DISTILL_LAST_KEY, str(int(time.time())), ex=PROCESSED_TTL)


def _last_scan_elapsed_seconds() -> int:
    raw = get_redis().get(DISTILL_LAST_KEY)
    if not raw:
        return 9999999
    try:
        return max(0, int(time.time()) - int(raw))
    except (TypeError, ValueError):
        return 9999999


def piggyback_should_run() -> bool:
    """piggyback 节流：返回 True 才能触发 worker 扫描一次"""
    return _last_scan_elapsed_seconds() >= PIGGYBACK_MIN_INTERVAL


def piggyback_mark_started() -> None:
    _set_last_scan_ts()


# ---------- Daemon Loop（兜底后台任务）----------

_DAEMON_TASK_KEY = "_distill_daemon_task"


async def _distill_daemon_loop(
    interval_seconds: int = DAEMON_INTERVAL_SECONDS,
    batch_size: int = DAEMON_BATCH_SIZE,
) -> None:
    """
    后台 asyncio 循环：每 `interval_seconds` 秒调一次 `process_pending_batch`（兜底策略）。
    与 Piggyback（近实时）互补：
      · 用户流量正常 → Piggyback 先跑，Daemon loop 通常看到空批。
      · 异常（LLM 慢导致请求线阻塞、或重启漏跑一批）→ Daemon loop 5 min 后补捞。
    """
    from improve.worker import process_pending_batch  # 延迟 import 避免循环
    logger.info(
        "[distill] daemon started — every %ds, batch=%d. "
        "Piggyback (30s throttle, ≤4 per request) 先跑，本循环作为兜底。",
        interval_seconds, batch_size,
    )
    while True:
        try:
            stats = await process_pending_batch(max_items=batch_size, min_cool_seconds=MIN_COOL_SECONDS)
            if stats.scanned:
                logger.info(
                    "[distill] daemon tick: scanned=%d playbook_added=%d pref_users=%d "
                    "skip_no_signal=%d errors=%d elapsed=%.0fms",
                    stats.scanned, stats.playbook_added, stats.pref_updated_users,
                    stats.skipped_no_signal, stats.errored, stats.elapsed_ms,
                )
        except asyncio.CancelledError:
            logger.info("[distill] daemon stopped (cancelled).")
            return
        except Exception as e:  # noqa: BLE001
            logger.error("[distill] daemon tick failed (will retry after %ds): %s", interval_seconds, e)
        await asyncio.sleep(interval_seconds)


def start_distill_daemon(app: Any, interval_seconds: int = DAEMON_INTERVAL_SECONDS, batch_size: int = DAEMON_BATCH_SIZE) -> asyncio.Task:
    """
    在 FastAPI 启动时调用：创建 daemon task，挂到 app.state 上，shutdown 时 cancel。
    用法：
        @app.on_event("startup")
        async def _startup():
            app.state._distill_daemon = start_distill_daemon(app)

        @app.on_event("shutdown")
        async def _shutdown():
            t = getattr(app.state, "_distill_daemon", None)
            if t and not t.done(): t.cancel()
    """
    task = asyncio.create_task(
        _distill_daemon_loop(interval_seconds=interval_seconds, batch_size=batch_size),
        name="agent2-distill-daemon",
    )
    setattr(app.state, _DAEMON_TASK_KEY, task)

    def _log_done(t: asyncio.Task) -> None:
        try:
            t.result()
        except asyncio.CancelledError:
            pass
        except Exception as e:  # noqa: BLE001
            logger.error("[distill] daemon exited with exception (NOT restarted): %s", e)
    task.add_done_callback(_log_done)
    return task


def cancel_distill_daemon(app: Any) -> None:
    """shutdown 时调用：取消 daemon task。对已取消/已完成任务安全。"""
    t = getattr(app.state, _DAEMON_TASK_KEY, None)
    if t and not t.done():
        t.cancel()

