"""
离线蒸馏 Worker（阶段 4）。

三种运行方式：
A) Piggyback（默认线上用）：每次请求 log_trajectory 后 fire-and-forget 触发 `piggyback_scan()`，最多处理 4 条，≥30s 才跑一次。
B) CLI 单次：`python -m improve.worker --once --max-items 20`（补历史轨迹时用）
C) CLI 长轮询：`python -m improve.worker --loop --interval 300`（作为独立守护进程跑，可选）
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from core.llm import reset_token_usage
from memory.trajectory import trajectory_store
from memory.playbook import playbook
from memory.preferences import save_memory as save_user_preferences
from improve.signals import (
    pop_pending_batch,
    detect_acceptance,
    mark_processed,
    piggyback_should_run,
    piggyback_mark_started,
    MIN_COOL_SECONDS,
)
from improve.distill import playbook_distill, preference_distill
from core.observability import workflow_event

logger = logging.getLogger(__name__)

PIGGYBACK_MAX = 4          # piggyback 单次最多处理 4 条（避免主线程被拖太久）
PIGGYBACK_TIME_BUDGET = 2.5  # piggyback 单轮最多跑 2.5s，超了就留给下轮/CLI
DAEMON_INTERVAL_SECONDS = 300   # 兜底 daemon loop：5 分钟跑一批
DAEMON_BATCH_SIZE = 16


@dataclass
class WorkerStats:
    scanned: int = 0
    skipped_already_processed: int = 0
    skipped_no_signal: int = 0
    playbook_added: int = 0
    pref_updated_users: int = 0
    errored: int = 0
    elapsed_ms: float = 0.0


async def process_pending_batch(
    max_items: int = 8,
    min_cool_seconds: int = 60,
    time_budget: float | None = None,
    mode: str = "daemon_or_cli",
) -> WorkerStats:
    """
    主处理逻辑：从 pending zset 拉一批→信号判定→蒸馏→写库→标记 processed。
    单条异常不影响其它条。

    time_budget：单轮时间预算（秒），每条处理前检查，超了停止、剩余留给下一轮
    （piggyback 路径用它保证不拖慢主服务）。
    """
    stats = WorkerStats()
    t0 = time.perf_counter()

    ids = pop_pending_batch(max_items=max_items, min_cool_seconds=min_cool_seconds)
    workflow_event(
        "distill.batch_started",
        mode=mode,
        requestedCount=max_items,
        selectedCount=len(ids),
    )
    if not ids:
        stats.elapsed_ms = (time.perf_counter() - t0) * 1000
        return stats

    for tid in ids:
        # 单轮时间预算超了 → 停，剩余留给下一轮
        if time_budget is not None and (time.perf_counter() - t0) > time_budget:
            logger.info("Distill time budget exceeded; leaving remaining for next round.")
            break
        stats.scanned += 1
        try:
            record = trajectory_store.get(tid)
            if record is None:
                # 轨迹过期或被删 → 标记 processed 避免下次再扫
                mark_processed(tid, "missing_record")
                workflow_event("distill.trajectory_skipped", trajectoryId=tid, reason="missing_record")
                continue

            accepted = detect_acceptance(record)
            workflow_event(
                "distill.signal_evaluated",
                trajectoryId=tid,
                accepted=accepted,
                outcome=record.outcome,
                candidateCount=record.candidateCount,
                reflectionScore=record.reflectionScore,
            )
            if not accepted:
                mark_processed(tid, "no_signal")
                stats.skipped_no_signal += 1
                workflow_event("distill.trajectory_skipped", trajectoryId=tid, reason="no_signal")
                continue

            # Playbook 映射蒸馏
            mappings = playbook_distill(record)
            if mappings:
                added = await playbook.add_mapping_entries(
                    mappings, origin_trajectory_id=record.trajectoryId
                )
                stats.playbook_added += added

            # 用户偏好蒸馏
            preference_updated = False
            if record.userId > 0:
                pref_patch = preference_distill(record)
                if pref_patch:
                    await save_user_preferences(record.userId, pref_patch)
                    stats.pref_updated_users += 1
                    preference_updated = True

            mark_processed(tid, "ok")
            workflow_event(
                "distill.trajectory_completed",
                trajectoryId=tid,
                mode=mode,
                preferenceUpdated=preference_updated,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"distill failed [{mode}] for trajectory {tid}: {e}")
            stats.errored += 1
            workflow_event("distill.trajectory_failed", level=logging.ERROR, trajectoryId=tid, mode=mode, errorType=type(e).__name__, error=str(e))
            try:
                mark_processed(tid, f"error:{type(e).__name__}")
            except Exception:  # noqa: BLE001
                pass

    stats.elapsed_ms = (time.perf_counter() - t0) * 1000
    if stats.scanned:
        logger.info(
            "Distill batch done [%s]: scanned=%d playbook_added=%d pref_users=%d "
            "skip_no_signal=%d errors=%d elapsed=%.0fms",
            mode, stats.scanned, stats.playbook_added, stats.pref_updated_users,
            stats.skipped_no_signal, stats.errored, stats.elapsed_ms,
        )
    workflow_event(
        "distill.batch_completed",
        mode=mode,
        scanned=stats.scanned,
        playbookAdded=stats.playbook_added,
        preferenceUsers=stats.pref_updated_users,
        skippedNoSignal=stats.skipped_no_signal,
        errors=stats.errored,
        elapsedMs=round(stats.elapsed_ms, 1),
    )
    return stats


async def piggyback_scan() -> WorkerStats:
    """
    请求 fire-and-forget 路径调用：短平快处理几条，节流 ≥30s。
    返回统计（调用方通常不关心）。
    """
    try:
        reset_token_usage()
    except Exception:  # noqa: BLE001
        pass

    if not piggyback_should_run():
        workflow_event("distill.piggyback_skipped", reason="throttled")
        return WorkerStats()
    piggyback_mark_started()

    return await process_pending_batch(
        max_items=PIGGYBACK_MAX,
        min_cool_seconds=MIN_COOL_SECONDS,
        time_budget=PIGGYBACK_TIME_BUDGET,
        mode="piggyback",
    )


# ---------- Daemon Loop（兜底后台任务，FastAPI 生命周期管理）----------

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
    logger.info(
        "[distill] daemon started — every %ds, batch=%d. "
        "Piggyback (30s throttle, ≤4 per request) 先跑，本循环作为兜底。",
        interval_seconds, batch_size,
    )
    workflow_event(
        "distill.daemon_started",
        intervalSeconds=interval_seconds,
        batchSize=batch_size,
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
            workflow_event("distill.daemon_stopped")
            return
        except Exception as e:  # noqa: BLE001
            logger.error("[distill] daemon tick failed (will retry after %ds): %s", interval_seconds, e)
            workflow_event("distill.daemon_tick_failed", level=logging.ERROR, errorType=type(e).__name__, error=str(e))
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


# ---------- CLI ----------

async def _run_once(max_items: int) -> int:
    stats = await process_pending_batch(max_items=max_items, min_cool_seconds=1)
    print(
        f"[distill] scanned={stats.scanned} playbook_added={stats.playbook_added} "
        f"pref_users={stats.pref_updated_users} skip_no_signal={stats.skipped_no_signal} "
        f"errors={stats.errored} elapsed_ms={stats.elapsed_ms:.0f}"
    )
    return 0


async def _run_loop(interval_seconds: int, max_items: int) -> int:
    """CLI 长轮询模式：复用与 in-process daemon 相同的循环，只是入口从命令行启动。"""
    print(f"[distill] loop mode: every {interval_seconds}s, batch={max_items} (Ctrl+C to stop)")
    try:
        await _distill_daemon_loop(interval_seconds=interval_seconds, batch_size=max_items)
    except KeyboardInterrupt:
        print("\n[distill] stopped by user")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="improve.worker")
    parser.add_argument("--once", action="store_true", help="跑一批就退出")
    parser.add_argument("--loop", action="store_true", help="长轮询守护")
    parser.add_argument("--interval", type=int, default=300, help="长轮询间隔秒，默认 300")
    parser.add_argument("--max-items", type=int, default=16, help="每批最大条数")
    args = parser.parse_args()

    # 配置 logging（CLI 独立运行时）
    from core.observability import configure_logging
    configure_logging()

    if args.loop:
        return asyncio.run(_run_loop(args.interval, args.max_items))
    return asyncio.run(_run_once(args.max_items))


if __name__ == "__main__":
    raise SystemExit(main())
