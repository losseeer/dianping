"""
Layer 3: Trajectory Store — AHE 三大可观测性支柱的实现

分层访问结构（对应 AHE Experience Observability）：
  Layer 1: 原始轨迹（完整 JSON，按需读取）
  Layer 2: 分析报告（每条轨迹的成功/失败原因摘要）
  Layer 3: 聚合洞察（跨轨迹统计 + 失败模式聚类）

Redis 存储结构：
  agent2:trajectory:{trajectoryId}    → 完整 TrajectoryRecord JSON
  agent2:trajectory:user:{userId}     → ZSet (score=timestamp, member=trajectoryId)
  agent2:trajectory:analysis:{trajId} → 分析报告 JSON
  agent2:trajectory:insights          → List of TrajectoryInsight JSON
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from config import config
from core.redis import get_redis
from models import TrajectoryRecord, TrajectoryNodeLog, TrajectoryInsight

logger = logging.getLogger(__name__)


class TrajectoryStore:
    """执行轨迹的持久化存储与分层访问"""

    def __init__(self):
        self.prefix = config.TRAJECTORY_KEY_PREFIX
        self.expiry = config.TRAJECTORY_EXPIRY_DAYS

    # ---- Layer 1: 原始轨迹 CRUD ----

    def save(self, record: TrajectoryRecord) -> str:
        """保存完整轨迹到 Redis"""
        r = get_redis()
        if not record.trajectoryId:
            record.trajectoryId = str(uuid.uuid4())
        if not record.createdAt:
            record.createdAt = datetime.now().isoformat()

        key = f"{self.prefix}{record.trajectoryId}"
        r.set(key, record.model_dump_json(), ex=self.expiry * 24 * 3600)

        # 加入用户轨迹索引（ZSet by timestamp）
        user_key = f"{self.prefix}user:{record.userId}"
        ts = datetime.fromisoformat(record.createdAt).timestamp()
        r.zadd(user_key, {record.trajectoryId: ts})
        # 只保留最近 N 条
        r.zremrangebyrank(user_key, 0, -config.TRAJECTORY_MAX_RECENT - 1)
        r.expire(user_key, self.expiry * 24 * 3600)

        return record.trajectoryId

    def get(self, trajectory_id: str) -> Optional[TrajectoryRecord]:
        """获取单条完整轨迹"""
        r = get_redis()
        raw = r.get(f"{self.prefix}{trajectory_id}")
        if raw:
            return TrajectoryRecord(**json.loads(raw))
        return None

    def get_by_user(self, user_id: int, limit: int = 20) -> list[TrajectoryRecord]:
        """获取用户最近的轨迹列表"""
        r = get_redis()
        user_key = f"{self.prefix}user:{user_id}"
        ids = r.zrevrange(user_key, 0, limit - 1)
        results = []
        for tid in ids:
            record = self.get(tid)
            if record:
                results.append(record)
        return results

    def get_recent(self, limit: int = 50) -> list[TrajectoryRecord]:
        """获取全局最近的轨迹（跨用户）"""
        r = get_redis()
        # 扫描所有用户索引
        all_ids = set()
        for key in r.scan_iter(match=f"{self.prefix}user:*"):
            ids = r.zrevrange(key, 0, limit - 1)
            all_ids.update(ids)
            if len(all_ids) >= limit:
                break

        # 按时间排序取最近的
        records = []
        for tid in list(all_ids)[:limit]:
            record = self.get(tid)
            if record:
                records.append(record)
        records.sort(key=lambda x: x.createdAt, reverse=True)
        return records[:limit]

    # ---- Layer 2: 分析报告 ----

    def save_analysis(self, trajectory_id: str, analysis: dict) -> None:
        """保存单条轨迹的分析报告"""
        r = get_redis()
        key = f"{self.prefix}analysis:{trajectory_id}"
        r.set(key, json.dumps(analysis, ensure_ascii=False), ex=self.expiry * 24 * 3600)

    def get_analysis(self, trajectory_id: str) -> Optional[dict]:
        """获取分析报告"""
        r = get_redis()
        raw = r.get(f"{self.prefix}analysis:{trajectory_id}")
        if raw:
            return json.loads(raw)
        return None

    def analyze_trajectory(self, record: TrajectoryRecord) -> dict:
        """
        生成单条轨迹的分析报告（无需 LLM，规则驱动）。
        对应 AHE Experience Observability 的第二层。
        """
        analysis = {
            "trajectoryId": record.trajectoryId,
            "userId": record.userId,
            "userMessage": record.userMessage,
            "outcome": record.outcome,
            "success": record.outcome in ("accepted", "unknown") and record.reflectionScore >= 6.0,
            "hitlTriggered": record.hitlTriggered,
            "hitlReason": record.hitlReason,
            "iterationCount": record.iterationCount,
            "candidateCount": record.candidateCount,
            "reflectionScore": record.reflectionScore,
            "reflectionNotes": record.reflectionNotes,
            "failureReasons": [],
            "nodeTimings": {},
        }

        # 节点耗时统计
        for log in record.nodeLogs:
            analysis["nodeTimings"][log.nodeName] = log.durationMs

        # 规则驱动失败原因检测
        if record.hitlTriggered and record.iterationCount >= config.AGENT2_MAX_ITERATIONS:
            analysis["failureReasons"].append("hitl_then_max_iterations")
        if record.candidateCount < config.AGENT2_MIN_CANDIDATES:
            analysis["failureReasons"].append("too_few_candidates")
        if record.candidateCount > config.AGENT2_MAX_CANDIDATES_FOOD:
            analysis["failureReasons"].append("too_many_candidates")
        if record.outcome == "rejected":
            analysis["failureReasons"].append("user_rejected")
        if record.reflectionScore > 0 and record.reflectionScore < config.PLAYBOOK_REFLECTION_THRESHOLD:
            analysis["failureReasons"].append("low_reflection_score")
        if not record.rankedShops:
            analysis["failureReasons"].append("empty_recommendation")

        self.save_analysis(record.trajectoryId, analysis)
        return analysis

    # ---- Layer 3: 聚合洞察 ----

    def get_insights(self) -> list[TrajectoryInsight]:
        """获取聚合洞察列表"""
        r = get_redis()
        raw = r.get(f"{self.prefix}insights")
        if raw:
            data = json.loads(raw)
            return [TrajectoryInsight(**item) for item in data]
        return []

    def compute_insights(self, trajectories: list[TrajectoryRecord]) -> list[TrajectoryInsight]:
        """
        从一批轨迹中计算聚合洞察。
        对应 AHE Experience Observability 的第三层。
        """
        if not trajectories:
            return []

        insights: list[TrajectoryInsight] = []
        now = datetime.now().isoformat()

        # 洞察 1: HITL 触发率
        hitl_count = sum(1 for t in trajectories if t.hitlTriggered)
        if hitl_count > 0:
            hitl_reasons: dict[str, int] = {}
            for t in trajectories:
                if t.hitlTriggered and t.hitlReason:
                    hitl_reasons[t.hitlReason] = hitl_reasons.get(t.hitlReason, 0) + 1
            top_reason = max(hitl_reasons, key=hitl_reasons.get) if hitl_reasons else "unknown"
            insights.append(TrajectoryInsight(
                insightId=f"insight_hitl_{now}",
                category="hitl_frequency",
                description=f"HITL triggered in {hitl_count}/{len(trajectories)} trajectories, top reason: {top_reason}",
                frequency=hitl_count,
                sampleTrajectoryIds=[t.trajectoryId for t in trajectories if t.hitlTriggered][:5],
                createdAt=now,
            ))

        # 洞察 2: 平均迭代次数
        avg_iter = sum(t.iterationCount for t in trajectories) / len(trajectories)
        if avg_iter > config.AGENT2_MAX_ITERATIONS * 0.8:
            insights.append(TrajectoryInsight(
                insightId=f"insight_iter_{now}",
                category="iteration_efficiency",
                description=f"Average iterations {avg_iter:.1f} approaching max {config.AGENT2_MAX_ITERATIONS}",
                frequency=len(trajectories),
                createdAt=now,
            ))

        # 洞察 3: 低接受率
        rejected = [t for t in trajectories if t.outcome == "rejected"]
        if len(rejected) > len(trajectories) * 0.3:
            insights.append(TrajectoryInsight(
                insightId=f"insight_reject_{now}",
                category="low_acceptance",
                description=f"Rejection rate {len(rejected)}/{len(trajectories)} ({len(rejected)/len(trajectories)*100:.0f}%)",
                frequency=len(rejected),
                sampleTrajectoryIds=[t.trajectoryId for t in rejected][:5],
                createdAt=now,
            ))

        # 洞察 4: 低反思评分
        low_score = [t for t in trajectories if 0 < t.reflectionScore < config.PLAYBOOK_REFLECTION_THRESHOLD]
        if low_score:
            insights.append(TrajectoryInsight(
                insightId=f"insight_score_{now}",
                category="low_reflection",
                description=f"{len(low_score)} trajectories with reflection score < {config.PLAYBOOK_REFLECTION_THRESHOLD}",
                frequency=len(low_score),
                sampleTrajectoryIds=[t.trajectoryId for t in low_score][:5],
                createdAt=now,
            ))

        # 洞察 5: 候选数量异常
        too_few = [t for t in trajectories if t.candidateCount < config.AGENT2_MIN_CANDIDATES]
        if too_few:
            insights.append(TrajectoryInsight(
                insightId=f"insight_few_{now}",
                category="candidate_scarcity",
                description=f"{len(too_few)} trajectories with < {config.AGENT2_MIN_CANDIDATES} candidates",
                frequency=len(too_few),
                sampleTrajectoryIds=[t.trajectoryId for t in too_few][:5],
                createdAt=now,
            ))

        # 持久化
        r = get_redis()
        r.set(
            f"{self.prefix}insights",
            json.dumps([i.model_dump() for i in insights], ensure_ascii=False),
            ex=self.expiry * 24 * 3600,
        )

        return insights

    # ---- 辅助方法 ----

    def update_outcome(self, trajectory_id: str, outcome: str, feedback: str = "") -> None:
        """更新轨迹的结果标注（用户接受/修改/拒绝）"""
        record = self.get(trajectory_id)
        if record:
            record.outcome = outcome
            if feedback:
                record.userFeedback = feedback
            self.save(record)

    def get_failure_trajectories(self, limit: int = 50) -> list[TrajectoryRecord]:
        """获取失败轨迹（用于 weakness mining）"""
        all_trajs = self.get_recent(limit)
        return [
            t for t in all_trajs
            if t.outcome == "rejected"
            or (t.reflectionScore > 0 and t.reflectionScore < config.PLAYBOOK_REFLECTION_THRESHOLD)
            or (t.hitlTriggered and t.iterationCount >= config.AGENT2_MAX_ITERATIONS)
        ]


# 全局实例
trajectory_store = TrajectoryStore()
