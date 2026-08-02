"""Agent2 State definition"""
from typing import Optional
from pydantic import BaseModel

class AgentState(BaseModel):
    # 输入
    user_message: str = ""
    user_id: int = 0
    user_x: Optional[float] = None
    user_y: Optional[float] = None
    thread_id: str = ""

    # 记忆
    memory: dict = {}

    # ReAct 循环
    plan: str = ""
    tool_calls: list[dict] = []
    tool_results: list[dict] = []
    evaluation: str = ""

    # 推荐结果
    candidate_shops: list[dict] = []
    ranked_shops: list[dict] = []
    final_recommendation: str = ""

    # HITL
    hitl_needed: bool = False
    hitl_question: str = ""
    hitl_options: list[str] = []
    hitl_reason: str = ""
    hitl_count: int = 0            # HITL 次数（防止死循环）
    user_feedback: str = ""
    memory_updated: bool = False
    new_preferences: list[str] = []

    # Layer 1: Reflection
    reflection_score: float = 0.0
    reflection_notes: str = ""
    reflection_weaknesses: list[str] = []
    should_replan: bool = False
    replan_hints: list[str] = []

    # Layer 3: Trajectory tracking
    trajectory_id: str = ""
    node_logs: list[dict] = []
    decisions: list[dict] = []
    applied_playbook_entries: list[str] = []

    # 控制
    iteration_count: int = 0

    class Config:
        arbitrary_types_allowed = True


