"""
LangGraph 条件路由。

【重构 2026-08】简化为：judge_candidates 负责 evaluate → 三种去向的判定（纯规则）。
原 should_hitl 函数名保留（避免外部 import/eval/runner 报错），内部逻辑升级为 judge_candidates。
原 should_replan 保留但逻辑作废（新图里不再走到 Reflect→Replan 路径），仅用于兼容旧代码/脚本 import。
"""
from core.config import config
from graph.utils import _sv


def should_hitl(state) -> str:
    """
    evaluate 之后的路由（请求路径的核心分叉点）。
    返回值必须和 builder.py 里 add_conditional_edges 的 mapping 严格一致：
      - interrupt → 进入 HITL 打断（end 用户交互）
      - generate  → 进入最终推荐生成 LLM
      - relax     → 进入 replan_relax 节点（规则放宽重搜，再回 evaluate 二次判定）
    """
    # 1. HITL 优先：evaluate 标记 hitl_needed=True 且 hitl_count 刚好到 1（说明是本轮刚触发的第一次）→ interrupt
    hitl_needed = _sv(state, "hitl_needed", False)
    evaluation = _sv(state, "evaluation", "")
    iteration_count = _sv(state, "iteration_count", 0)
    hitl_count = _sv(state, "hitl_count", 0) or 0

    if hitl_needed and hitl_count <= 1:
        return "interrupt"

    # 2. sufficient（或 HITL 过了兜底 sufficient）→ generate
    if evaluation == "sufficient":
        return "generate"

    # 3. insufficient → relax（规则放宽），但最多执行一次，这里再用 iteration_count 兜底
    #    如果 iteration_count 已经到 MAX（说明循环异常，但 evaluate 规则理论不会出现）→ 强制 generate 保底
    if evaluation == "insufficient":
        if iteration_count >= config.AGENT2_MAX_ITERATIONS:
            return "generate"
        return "relax"

    # 4. 异常兜底（hitl_needed=False 但 evaluation=hitl_needed 的脏数据场景）→ 保底 generate
    return "generate"


def should_replan(state) -> str:
    """
    【兼容保留，不再触发 Replan】
    Reflect 节点已从主路径移除；该函数保留以避免旧 import/eval/runner/测试直接崩溃。
    永远返回 "log"（直接记轨迹结束）。如果新图意外通过这条边也不会走到死循环。
    """
    _ = state  # noqa: F841
    return "log"
