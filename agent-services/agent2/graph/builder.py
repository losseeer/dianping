"""LangGraph graph builder"""
from langgraph.graph import StateGraph, END
from graph.state import AgentState
from graph.nodes import (load_memory_node, plan_node, execute_node, evaluate_node, update_memory_node, generate_recommendation_node, reflect_with_timing, log_trajectory_node)
from graph.routing import should_hitl, should_replan

def _parse_llm_json(text: str) -> dict:
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


# ============================================================
# 构建 LangGraph
# ============================================================

def build_graph() -> StateGraph:
    """
    构建 Agent2 的 LangGraph 状态图。
    
    流程:
      load_memory → plan → execute → evaluate → should_hitl
        → interrupt (END)
        → generate → reflect → should_replan
          → replan → plan
          → log_trajectory (END)
        → replan → plan
    """
    graph = StateGraph(AgentState)

    graph.add_node("load_memory", load_memory_node)
    graph.add_node("plan", plan_node)
    graph.add_node("execute", execute_node)
    graph.add_node("evaluate", evaluate_node)
    graph.add_node("update_memory", update_memory_node)
    graph.add_node("generate", generate_recommendation_node)
    graph.add_node("reflect", reflect_with_timing)
    graph.add_node("log_trajectory", log_trajectory_node)

    graph.set_entry_point("load_memory")

    graph.add_edge("load_memory", "plan")
    graph.add_edge("plan", "execute")
    graph.add_edge("execute", "evaluate")
    graph.add_edge("update_memory", "plan")

    # evaluate 后的条件路由
    graph.add_conditional_edges(
        "evaluate",
        should_hitl,
        {
            "interrupt": END,
            "generate": "generate",
            "replan": "plan",
        },
    )

    # generate → reflect → should_replan
    graph.add_edge("generate", "reflect")
    graph.add_conditional_edges(
        "reflect",
        should_replan,
        {
            "replan": "plan",
            "log": "log_trajectory",
        },
    )

    graph.add_edge("log_trajectory", END)

    return graph


compiled_graph = build_graph().compile()
