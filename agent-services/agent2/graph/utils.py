"""Graph 工具：计时、state 辅助、JSON 解析、interrupt 载荷提取"""
import json
import time
from functools import wraps
from typing import Optional

from langgraph.errors import GraphInterrupt

from core.observability import workflow_event

def _sv(state, key, default=None):
    """统一获取 state 值 — 兼容 dict 和 AgentState"""
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def extract_hitl_interrupt(result: dict) -> Optional[dict]:
    """从图执行结果中提取 HITL interrupt 载荷（evaluate 内 interrupt() 触发）；无中断返回 None。

    LangGraph 中断时 ainvoke 返回值带 "__interrupt__" 键（Interrupt 对象列表），
    被打断节点（evaluate）本轮写入未提交，故 hitl_* 字段需由调用方用本载荷合成。
    """
    for intr in (result or {}).get("__interrupt__") or []:
        value = getattr(intr, "value", None)
        if isinstance(value, dict) and value.get("question"):
            return value
    return None


def timed_node(name: str):
    """节点计时装饰器 — 记录每个节点的耗时和输入/输出摘要"""
    def decorator(func):
        @wraps(func)
        async def wrapper(state) -> dict:
            start = time.time()
            input_summary = _summarize_state(state, name)
            workflow_event(
                "node.started",
                node=name,
                inputSummary=input_summary,
                iterationCount=_sv(state, "iteration_count", 0),
            )
            try:
                result = await func(state)
            except GraphInterrupt:
                # 图内 HITL 暂停（evaluate 调 interrupt()）不是节点失败
                workflow_event(
                    "node.interrupted",
                    node=name,
                    durationMs=round((time.time() - start) * 1000, 1),
                )
                raise
            except Exception as exc:
                workflow_event(
                    "node.failed",
                    node=name,
                    durationMs=round((time.time() - start) * 1000, 1),
                    errorType=type(exc).__name__,
                    error=str(exc),
                )
                raise
            elapsed = (time.time() - start) * 1000
            output_summary = _summarize_result(result)

            node_log = {
                "nodeName": name,
                "inputSummary": input_summary[:200],
                "outputSummary": output_summary[:200],
                "llmCalls": 1 if any(k in name for k in ("plan", "evaluate", "generate", "memory")) else 0,
                "durationMs": round(elapsed, 1),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }

            existing_logs = _sv(state, "node_logs", []) or []
            existing_logs = list(existing_logs) if isinstance(existing_logs, list) else []
            existing_logs.append(node_log)

            result["node_logs"] = existing_logs
            workflow_event(
                "node.completed",
                node=name,
                durationMs=round(elapsed, 1),
                outputSummary=output_summary,
                nodeLog=node_log,
            )
            return result
        return wrapper
    return decorator


def _summarize_state(state, node_name: str) -> str:
    """生成节点输入摘要"""
    if node_name == "plan":
        msg = _sv(state, "user_message", "")
        mem = _sv(state, "memory", {})
        it = _sv(state, "iteration_count", 0)
        return f"msg={msg[:50] if msg else ''}, mem={bool(mem)}, iter={it}"
    elif node_name == "execute":
        tc = _sv(state, "tool_calls", []) or []
        cs = _sv(state, "candidate_shops", []) or []
        return f"tool_calls={len(tc)}, candidates={len(cs)}"
    elif node_name == "evaluate":
        cs = _sv(state, "candidate_shops", []) or []
        tr = _sv(state, "tool_results", []) or []
        return f"candidates={len(cs)}, results={len(tr)}"
    elif node_name == "generate":
        cs = _sv(state, "candidate_shops", []) or []
        mem = _sv(state, "memory", {})
        return f"candidates={len(cs)}, mem={bool(mem)}"
    return ""


def _summarize_result(result: dict) -> str:
    """生成节点输出摘要"""
    if not result:
        return ""
    parts = []
    for k, v in result.items():
        if isinstance(v, list):
            parts.append(f"{k}={len(v)}")
        elif isinstance(v, str) and len(v) > 50:
            parts.append(f"{k}={v[:50]}...")
        elif isinstance(v, (int, float, bool)):
            parts.append(f"{k}={v}")
    return ", ".join(parts[:5])


def _parse_llm_json(text: str) -> dict:
    """从 LLM 输出中提取 JSON"""
    import re
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        return {}


def normalize_score(score) -> float:
    """将后端评分（0-10）归一化到 0-5，兼容已归一化的值"""
    if score is None:
        return 0
    return score / 10.0 if score > 5 else score


def rank_shops(shops: list[dict], score_weight: float = 0.5, distance_weight: float = 0.5) -> list[dict]:
    """
    综合排序：评分 + 距离加权（默认各 50%）。

    归一化：
      score_norm   = score / 5.0                    （0-5 → 0-1，越高越好）
      distance_norm = 1 - dist / max_dist           （越近越好，clamp [0,1]）

    当 distance 全为 0（无坐标信息）时退化为纯评分排序。
    """
    if not shops:
        return shops

    # 取本批次最大距离作为归一化分母
    distances = [float(s.get("distance") or 0) for s in shops]
    max_dist = max(distances) if distances else 0.0

    def _rank_key(s: dict) -> float:
        score = float(s.get("score") or 0)
        score_norm = min(score / 5.0, 1.0) if score > 0 else 0.0

        dist = float(s.get("distance") or 0)
        if max_dist > 0:
            distance_norm = max(0.0, 1.0 - dist / max_dist)
        else:
            distance_norm = 0.0  # 无距离信息时不影响评分排序

        return score_weight * score_norm + distance_weight * distance_norm

    return sorted(shops, key=_rank_key, reverse=True)

