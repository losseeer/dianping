from pydantic import BaseModel
from typing import Optional, Literal


class ReviewAnalysis(BaseModel):
    """单条评价的情感分析结果"""
    sentiment: Literal["positive", "neutral", "negative"]
    pros: list[str]
    cons: list[str]
    keyPhrases: list[str]


class BatchReviewAnalysis(BaseModel):
    """批量评价分析结果（用于 with_structured_output）"""
    reviews: list[ReviewAnalysis]


class ScoreBreakdown(BaseModel):
    """评分解读"""
    overall: float
    interpretation: str


class RecommendationResult(BaseModel):
    """LLM 生成的综合建议（用于 with_structured_output）"""
    recommendation: str
    scoreBreakdown: ScoreBreakdown


class SummaryRequest(BaseModel):
    """Agent1 请求体"""
    shopId: int
