"""
LangGraph 状态图构建。

【重构 2026-08】新图拓扑：
  load_memory → plan → execute → evaluate → (interrupt / generate / relax)
    relax → replan_relax → evaluate  (规则放宽闭环，最多一轮：replan_count 守卫)
    generate → log_trajectory → END
    update_memory → plan  (HITL 用户反馈后重新规划)

Reflect 节点从主请求路径移除：不再串行等待 LLM 自评。
旧 reflect_with_timing / should_replan 均已停用，如外部仍有直接符号 import（如 eval/runner 遗留兼容路径），
请改用新的 signals/distill/worker 离线信号管线（improve/ 目录）。
Replan 改为 replan_relax 纯规则节点，不调用 LLM，单轮最多一次。
"""
from langgraph.graph import StateGraph, END
from graph.state import AgentState
from graph.nodes import (
    load_memory_node,
    plan_node,
    execute_node,
    evaluate_node,
    update_memory_node,
    generate_recommendation_node,
    replan_relax_node,
    log_trajectory_node,
)
from graph.routing import should_hitl


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("load_memory", load_memory_node)
    graph.add_node("plan", plan_node)
    graph.add_node("execute", execute_node)
    graph.add_node("evaluate", evaluate_node)
    graph.add_node("update_memory", update_memory_node)
    graph.add_node("generate", generate_recommendation_node)
    graph.add_node("replan_relax", replan_relax_node)  # 新增：规则级放宽
    graph.add_node("log_trajectory", log_trajectory_node)

    graph.set_entry_point("load_memory")

    # 主链路
    graph.add_edge("load_memory", "plan")
    graph.add_edge("plan", "execute")
    graph.add_edge("execute", "evaluate")
    graph.add_edge("update_memory", "plan")  # HITL 用户反馈写记忆后重新 plan

    # evaluate → 三路分叉
    graph.add_conditional_edges(
        "evaluate",
        should_hitl,
        {
            # HITL 打断：LangGraph interrupt/resume 机制，用户补充后从 update_memory 再进图
            "interrupt": END,
            # 候选充足或兜底 → 生成最终推荐
            "generate": "generate",
            # 0 < 候选 < MIN_CANDIDATES 且 replan_count=0 → 规则放宽重搜，回 evaluate 二次判定
            "relax": "replan_relax",
        },
    )

    # Replan 规则放宽后 → 重新回到 evaluate 判定候选是否足够
    # （此时 replan_count 已=1，evaluate 规则会兜底 sufficient，绝无死循环）
    graph.add_edge("replan_relax", "evaluate")

    # 生成推荐 → 落盘轨迹 → 结束
    graph.add_edge("generate", "log_trajectory")
    graph.add_edge("log_trajectory", END)

    return graph


compiled_graph = build_graph().compile()
