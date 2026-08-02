"""Conditional routing for LangGraph"""
from config import config
from graph.utils import _sv


def should_hitl(state) -> str:
    """evaluate 之后的路由"""
    hitl_needed = _sv(state, "hitl_needed", False)
    evaluation = _sv(state, "evaluation", "")
    iteration_count = _sv(state, "iteration_count", 0)

    if hitl_needed:
        return "interrupt"
    elif evaluation == "sufficient":
        return "generate"
    elif iteration_count >= config.AGENT2_MAX_ITERATIONS:
        return "generate"
    else:
        return "replan"


def should_replan(state) -> str:
    """reflect 之后的路由"""
    should_replan = _sv(state, "should_replan", False)
    if should_replan:
        return "replan"
    return "log"
