from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


# --- API 请求/响应模型 ---

class ChatRequest(BaseModel):
    """Agent2 对话请求体"""
    userId: int = Field(gt=0, description="必须是已登录用户的真实 user id（>0），拒绝匿名/占位 id")
    message: str
    x: Optional[float] = None
    y: Optional[float] = None
    threadId: Optional[str] = None


class ResumeRequest(BaseModel):
    """Agent2 恢复对话请求体"""
    userId: int = Field(gt=0, description="必须是已登录用户的真实 user id（>0），拒绝匿名/占位 id")
    threadId: str
    response: str
    x: Optional[float] = None
    y: Optional[float] = None


# --- 短期记忆：会话级上下文模型 ---

class ConversationTurn(BaseModel):
    """单轮对话记录"""
    role: Literal["user", "assistant"]
    content: str
    timestamp: str = ""


# --- 1. Trajectory & 可观测性模型 ---

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


# --- 2. Playbook 经验模型 ---

class PlaybookEntry(BaseModel):
    """ACE playbook 条目：结构化经验 (identifier, description)"""
    entryId: str
    category: Literal[
        "intent_parsing", "tool_selection", "hitl_trigger",
        "ranking", "context_gap",
    ]
    description: str
    source: Literal["reflection", "weakness_mining", "user_feedback", "distill_signal"] = "reflection"
    confidence: float = 0.5
    createdAt: str = ""
    timesApplied: int = 0
    timesHelpful: int = 0


# --- 3. 推荐质量自评模型 ---

class ReflectionResult(BaseModel):
    """推荐质量自评结果"""
    score: float = Field(ge=0.0, le=10.0)
    reasoning: str
    weaknesses: list[str] = []
    shouldReplan: bool = False
    replanHints: list[str] = []


# --- Eval Models ---


class EvalCompareRequest(BaseModel):
    """对比两次 eval 运行结果"""
    beforeRunId: str
    afterRunId: str
