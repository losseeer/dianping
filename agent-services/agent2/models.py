from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


# ============================================================
# API 请求/响应模型
# ============================================================

class ChatRequest(BaseModel):
    """Agent2 对话请求体"""
    userId: int
    message: str
    x: Optional[float] = None
    y: Optional[float] = None
    threadId: Optional[str] = None


class ResumeRequest(BaseModel):
    """Agent2 恢复对话请求体"""
    userId: int
    threadId: str
    response: str
    x: Optional[float] = None
    y: Optional[float] = None


# ============================================================
# 短期记忆：会话级上下文模型
# ============================================================

class ConversationTurn(BaseModel):
    """单轮对话记录"""
    role: Literal["user", "assistant"]
    content: str
    timestamp: str = ""


# ============================================================
# Layer 3: Trajectory & Observability Models (AHE)
# ============================================================

class TrajectoryNodeLog(BaseModel):
    """单个节点的执行日志 — Component Observability"""
    nodeName: str
    inputSummary: str = ""
    outputSummary: str = ""
    llmCalls: int = 0
    durationMs: float = 0.0
    timestamp: str = ""


class DecisionLog(BaseModel):
    """LLM 决策日志 — Decision Observability"""
    node: str
    decision: str = ""
    reasoning: str = ""
    prediction: str = ""
    verified: Optional[bool] = None


class TrajectoryRecord(BaseModel):
    """完整执行轨迹 — 存储在 Redis"""
    trajectoryId: str = ""
    userId: int = 0
    threadId: str = ""
    userMessage: str = ""
    nodeLogs: list[TrajectoryNodeLog] = []
    decisions: list[DecisionLog] = []
    candidateCount: int = 0
    hitlTriggered: bool = False
    hitlReason: str = ""
    iterationCount: int = 0
    finalRecommendation: str = ""
    rankedShops: list[dict] = []
    userFeedback: str = ""
    outcome: Literal["accepted", "modified", "rejected", "unknown"] = "unknown"
    reflectionScore: float = 0.0
    reflectionNotes: str = ""
    createdAt: str = ""


class TrajectoryInsight(BaseModel):
    """聚合洞察 — Experience Observability 第三层"""
    insightId: str = ""
    category: str = ""
    description: str = ""
    frequency: int = 0
    sampleTrajectoryIds: list[str] = []
    createdAt: str = ""


# ============================================================
# Layer 2: Playbook Models (ACE)
# ============================================================

class PlaybookEntry(BaseModel):
    """ACE playbook 条目 �� 结构化经验 (identifier, description)"""
    entryId: str
    category: Literal[
        "intent_parsing", "tool_selection", "hitl_trigger",
        "ranking", "context_gap",
    ]
    description: str
    source: Literal["reflection", "weakness_mining", "user_feedback"] = "reflection"
    confidence: float = 0.5
    createdAt: str = ""
    timesApplied: int = 0
    timesHelpful: int = 0


# ============================================================
# Layer 1: Reflection Models
# ============================================================

class ReflectionResult(BaseModel):
    """推荐质量自评结果"""
    score: float = Field(ge=0.0, le=10.0)
    reasoning: str
    weaknesses: list[str] = []
    shouldReplan: bool = False
    replanHints: list[str] = []


# ============================================================
# Layer 4: Self-Improvement Models (Self-Harness)
# ============================================================

class WeaknessPattern(BaseModel):
    """聚类后的失败模式"""
    patternId: str
    description: str
    category: Literal[
        "frequent_hitl", "low_acceptance", "too_many_iterations",
        "poor_matching", "missing_context", "tool_misuse",
    ]
    affectedTrajectoryIds: list[str] = []
    severity: float = 0.5
    suggestedFix: str = ""


class HarnessProposal(BaseModel):
    """提议的 harness 修改"""
    proposalId: str
    targetComponent: Literal[
        "system_prompt", "tool_description", "tool_implementation",
        "middleware", "evaluation_criteria",
    ]
    currentContent: str = ""
    proposedContent: str = ""
    rationale: str = ""
    targetWeaknessId: str = ""
    prediction: str = ""


class ValidationResult(BaseModel):
    """held-in / held-out 验证结果"""
    proposalId: str
    heldInPassed: bool = False
    heldOutPassed: bool = False
    heldInMetrics: dict = {}
    heldOutMetrics: dict = {}
    accepted: bool = False
    notes: str = ""


class SelfImprovementReport(BaseModel):
    """一次自改进循环的完整报告"""
    reportId: str = ""
    runAt: str = ""
    trajectoriesAnalyzed: int = 0
    weaknessPatterns: list[WeaknessPattern] = []
    proposals: list[HarnessProposal] = []
    validations: list[ValidationResult] = []
    acceptedChanges: int = 0
    playbookBeforeSize: int = 0
    playbookAfterSize: int = 0


# ============================================================
# Eval Models
# ============================================================


class EvalCompareRequest(BaseModel):
    """对比两次 eval 运行结果"""
    beforeRunId: str
    afterRunId: str
