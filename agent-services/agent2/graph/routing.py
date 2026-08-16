"""
LangGraph 条件路由。

【重构 2026-08】judge_candidates 负责 evaluate → 四种去向的判定（纯规则）。
HITL 打断不再走路由（原 "interrupt": END 已移除）：
evaluate 命中 HITL 时直接调用 langgraph.types.interrupt() 暂停图执行，
用户反馈经 Command(resume=...) 恢复后 evaluate 确定性重放，产生 evaluation="feedback" 路由到 update_memory。
"""
from core.config import config
from graph.utils import _sv
from core.observability import workflow_event


def should_hitl(state) -> str:
    """
    evaluate 之后的路由（请求路径的核心分叉点）。
    返回值必须和 builder.py 里 add_conditional_edges 的 mapping 严格一致：
      - feedback  → update_memory（interrupt(resume) 后 evaluate 重放产生：提取偏好 → 重新 plan）
      - generate  → 进入最终推荐生成 LLM
      - relax     → 进入 replan_relax 节点（规则放宽重搜，再回 evaluate 二次判定）
      - replan    → 回 plan 节点（预备性工具结果闭环，如 get_shop_types→search_shops_nearby）
    """
    evaluation = _sv(state, "evaluation", "")
    iteration_count = _sv(state, "iteration_count", 0)

    # 1. HITL 反馈已回填（Command(resume) 后 evaluate 重放）→ update_memory
    if evaluation == "feedback":
        workflow_event("graph.routed", fromNode="evaluate", route="feedback", evaluation=evaluation)
        return "feedback"

    # 2. sufficient（或 HITL 过了兜底 sufficient）→ generate
    if evaluation == "sufficient":
        workflow_event("graph.routed", fromNode="evaluate", route="generate", evaluation=evaluation)
        return "generate"

    # 3. replan：只执行了预备性工具还没搜索 → 回 plan 闭环（死循环由 evaluate 的 iteration_count 守卫保证不会发生）
    if evaluation == "replan":
        workflow_event("graph.routed", fromNode="evaluate", route="replan", evaluation=evaluation)
        return "replan"

    # 4. insufficient → relax（规则放宽），但最多执行一次，这里再用 iteration_count 兜底
    #    如果 iteration_count 已经到 MAX（说明循环异常，但 evaluate 规则理论不会出现）→ 强制 generate 保底
    if evaluation == "insufficient":
        if iteration_count >= config.AGENT2_MAX_ITERATIONS:
            workflow_event("graph.routed", fromNode="evaluate", route="generate", evaluation=evaluation, reason="max_iterations")
            return "generate"
        workflow_event("graph.routed", fromNode="evaluate", route="relax", evaluation=evaluation)
        return "relax"

    # 5. 异常兜底（未知 evaluation 脏数据场景）→ 保底 generate
    workflow_event("graph.routed", fromNode="evaluate", route="generate", evaluation=evaluation, reason="fallback")
    return "generate"
