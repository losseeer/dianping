"""Graph utilities: timing, state helpers, JSON parsing"""
import json
import time

def _sv(state, key, default=None):
    """统一获取 state 值 — 兼容 dict 和 AgentState"""
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def timed_node(name: str):
    """节点计时装饰器 — 记录每个节点的耗时和输入/输出摘要"""
    def decorator(func):
        async def wrapper(state) -> dict:
            start = time.time()
            input_summary = _summarize_state(state, name)
            result = await func(state)
            elapsed = (time.time() - start) * 1000

            node_log = {
                "nodeName": name,
                "inputSummary": input_summary[:200],
                "outputSummary": _summarize_result(result)[:200],
                "llmCalls": 1 if any(k in name for k in ("plan", "evaluate", "generate", "memory")) else 0,
                "durationMs": round(elapsed, 1),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }

            existing_logs = _sv(state, "node_logs", []) or []
            existing_logs = list(existing_logs) if isinstance(existing_logs, list) else []
            existing_logs.append(node_log)

            result["node_logs"] = existing_logs
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


