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
)
from improve.distill import playbook_distill, preference_distill

logger = logging.getLogger(__name__)

PIGGYBACK_MAX = 4          # piggyback 单次最多处理 4 条（避免主线程被拖太久）
PIGGYBACK_TIME_BUDGET = 2.5  # piggyback 单轮最多跑 2.5s，超了就留给下轮/CLI


@dataclass
class WorkerStats:
    scanned: int = 0
    skipped_already_processed: int = 0
    skipped_no_signal: int = 0
    playbook_added: int = 0
    pref_updated_users: int = 0
    errored: int = 0
    elapsed_ms: float = 0.0


async def process_pending_batch(max_items: int = 8, min_cool_seconds: int = 60) -> WorkerStats:
    """
    主处理逻辑：从 pending zset 拉一批→信号判定→蒸馏→写库→标记 processed。
    单条异常不影响其它条。
    """
    stats = WorkerStats()
    t0 = time.perf_counter()

    ids = pop_pending_batch(max_items=max_items, min_cool_seconds=min_cool_seconds)
    if not ids:
        stats.elapsed_ms = (time.perf_counter() - t0) * 1000
        return stats

    for tid in ids:
        stats.scanned += 1
        try:
            record = trajectory_store.get(tid)
            if record is None:
                # 轨迹过期或被删 → 标记 processed 避免下次再扫
                mark_processed(tid, "missing_record")
                continue

            accepted = detect_acceptance(record)
            if not accepted:
                mark_processed(tid, "no_signal")
                stats.skipped_no_signal += 1
                continue

            # Playbook 映射蒸馏
            mappings = playbook_distill(record)
            if mappings:
                added = await playbook.add_mapping_entries(
                    mappings, origin_trajectory_id=record.trajectoryId
                )
                stats.playbook_added += added

            # 用户偏好蒸馏
            if record.userId > 0:
                pref_patch = preference_distill(record)
                if pref_patch:
                    await save_user_preferences(record.userId, pref_patch)
                    stats.pref_updated_users += 1

            mark_processed(tid, "ok")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"distill worker failed for trajectory {tid}: {e}")
            stats.errored += 1
            try:
                mark_processed(tid, f"error:{type(e).__name__}")
            except Exception:  # noqa: BLE001
                pass

    stats.elapsed_ms = (time.perf_counter() - t0) * 1000
    if stats.scanned:
        logger.info(
            "Distill worker batch done: scanned=%d playbook_added=%d pref_users=%d "
            "skip_no_signal=%d errors=%d elapsed=%.0fms",
            stats.scanned, stats.playbook_added, stats.pref_updated_users,
            stats.skipped_no_signal, stats.errored, stats.elapsed_ms,
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
        return WorkerStats()
    piggyback_mark_started()

    t0 = time.perf_counter()
    stats = WorkerStats()
    ids = pop_pending_batch(max_items=PIGGYBACK_MAX, min_cool_seconds=60)
    if not ids:
        return stats

    for tid in ids:
        # 单轮时间预算超了 → 停，剩余留给下一轮
        if (time.perf_counter() - t0) > PIGGYBACK_TIME_BUDGET:
            logger.info("Piggyback time budget exceeded; leaving remaining for next round.")
            break
        stats.scanned += 1
        try:
            record = trajectory_store.get(tid)
            if record is None:
                mark_processed(tid, "missing_record")
                continue
            if not detect_acceptance(record):
                mark_processed(tid, "no_signal")
                stats.skipped_no_signal += 1
                continue

            mappings = playbook_distill(record)
            if mappings:
                added = await playbook.add_mapping_entries(mappings, origin_trajectory_id=record.trajectoryId)
                stats.playbook_added += added
            if record.userId > 0:
                patch = preference_distill(record)
                if patch:
                    await save_user_preferences(record.userId, patch)
                    stats.pref_updated_users += 1
            mark_processed(tid, "ok")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Piggyback distill failed for {tid}: {e}")
            stats.errored += 1
            try:
                mark_processed(tid, f"error:{type(e).__name__}")
            except Exception:  # noqa: BLE001
                pass

    stats.elapsed_ms = (time.perf_counter() - t0) * 1000
    if stats.scanned:
        logger.info(
            "Piggyback distill: scanned=%d +playbook=%d +pref_users=%d skip_no_signal=%d err=%d elapsed=%.0fms",
            stats.scanned, stats.playbook_added, stats.pref_updated_users,
            stats.skipped_no_signal, stats.errored, stats.elapsed_ms,
        )
    return stats


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
    print(f"[distill] loop mode: every {interval_seconds}s, batch={max_items} (Ctrl+C to stop)")
    while True:
        try:
            await _run_once(max_items)
        except KeyboardInterrupt:
            print("\n[distill] stopped by user")
            return 0
        except Exception as e:  # noqa: BLE001
            logger.error(f"Distill loop tick failed: {e}")
        await asyncio.sleep(interval_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(prog="improve.worker")
    parser.add_argument("--once", action="store_true", help="跑一批就退出")
    parser.add_argument("--loop", action="store_true", help="长轮询守护")
    parser.add_argument("--interval", type=int, default=300, help="长轮询间隔秒，默认 300")
    parser.add_argument("--max-items", type=int, default=16, help="每批最大条数")
    args = parser.parse_args()

    # 配置 logging（CLI 独立运行时）
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.loop:
        return asyncio.run(_run_loop(args.interval, args.max_items))
    return asyncio.run(_run_once(args.max_items))


if __name__ == "__main__":
    raise SystemExit(main())
