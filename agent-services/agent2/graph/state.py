"""Agent2 状态定义"""
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
    evaluation: str = ""  # sufficient / insufficient（纯规则判定后写入，保留字段以兼容旧代码读取）

    # 推荐结果
    candidate_shops: list[dict] = []
    ranked_shops: list[dict] = []
    final_recommendation: str = ""
    recommended_shop_ids: list[int] = []  # 本会话已推荐过的商铺 ID（跨轮次去重）

    # HITL
    hitl_needed: bool = False
    hitl_question: str = ""
    hitl_options: list[str] = []
    hitl_reason: str = ""
    hitl_count: int = 0            # 单轮 HITL 次数：0 或 1，超过后强制 Generate
    user_feedback: str = ""
    memory_updated: bool = False
    new_preferences: list[str] = []

    # 反思（保留字段以兼容外部 import 和 eval 采集；重构后请求路径内不再写入/读取）
    reflection_score: float = 0.0
    reflection_notes: str = ""
    reflection_weaknesses: list[str] = []
    should_replan: bool = False  # 逻辑上已由 replan_count > 0 替代，但保留字段兼容旧路由/eval
    replan_hints: list[str] = []

    # --- 新增：新流程控制字段 ---
    replan_count: int = 0         # 单轮 Replan（规则放宽）次数：0 或 1，超过后不再放宽
    relaxed_shops: list[dict] = []  # Replan 放宽后追加的候选，带 source=relaxed 标记（用于 Generate 标注）

    # 轨迹跟踪
    trajectory_id: str = ""
    node_logs: list[dict] = []
    decisions: list[dict] = []
    applied_playbook_entries: list[str] = []

    # 控制
    iteration_count: int = 0

    class Config:
        arbitrary_types_allowed = True


