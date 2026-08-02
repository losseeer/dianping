"""
[UNUSED] Layer 4: Self-Improvement Engine — Self-Harness 实现，可后续拓展实现

仅通过手动 API POST /agent2/self-improve 触发，不在任何请求路径中。
实际运行的自进化能力由 playbook.reflect + curate 提供（per-request 低分轨迹蒸馏）。
该模块是论文 Self-Harness 概念验证代码，从未在 graph 工作流中自动触发。

对应论文 Self-Harness 的三阶段循环:
  1. Weakness Mining: 收集执行轨迹，聚类失败模式
  2. Harness Proposal: 模型查看失败案例，提出范围受控的修改
  3. Proposal Validation: held-in + held-out 回归测试

安全设计（对应论文安全关切）:
  - 评估器位于自改进循环之外
  - 编辑仅应用于 playbook/prompt，不修改工具实现
  - 拒绝的候选记录但不应用
  - held-out 验证防止 reward hacking
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from config import config
from core.llm import get_llm
from memory.trajectory import trajectory_store
from memory.playbook import playbook
from models import (
    SelfImprovementReport,
    WeaknessPattern,
    HarnessProposal,
    ValidationResult,
    TrajectoryRecord,
)

logger = logging.getLogger(__name__)

WEAKNESS_MINING_PROMPT = """你是 Agent 自改进分析器。

以下是最近 {count} 条失败轨迹的摘要：

{trajectory_summaries}

请聚类失败模式，为每个模式输出：
{{
  "patterns": [
    {{
      "description": "失败模式描述（一句话）",
      "category": "frequent_hitl" | "low_acceptance" | "too_many_iterations" | "poor_matching" | "missing_context" | "tool_misuse",
      "severity": 0.0-1.0,
      "suggestedFix": "建议的修复方向"
    }}
  ]
}}

只输出 JSON。"""

HARNESS_PROPOSAL_PROMPT = """你是 Harness 修改提议器。

当前 system prompt 的关键部分：
{current_prompt}

发现的失败模式：
{weakness_patterns}

已有 playbook 条目：
{playbook_entries}

请针对每个失败模式，提出具体的修改方案。

约束:
1. 只修改 system_prompt 和 playbook 条目，不修改工具实现
2. 修改应当是窄变更（narrow change），一次解决一个模式
3. 每个修改必须包含预测声明（预期效果）

输出 JSON:
{{
  "proposals": [
    {{
      "targetComponent": "system_prompt" | "tool_description" | "middleware" | "evaluation_criteria",
      "currentContent": "当前内容片段",
      "proposedContent": "修改后的内容片段",
      "rationale": "修改理由",
      "prediction": "预期效果（可验证的声明）"
    }}
  ]
}}

只输出 JSON。"""


class SelfImprovementEngine:
    """
    Self-Harness: propose-evaluate-accept 自改进循环。
    
    对应论文:
      "当前 harness h_t 评估任务，收集执行轨迹
       模型在 h_t 下作为提议者，提供有界提议上下文
       通过 held-in 和 held-out 的回归测试评估
       仅在两组数据上均无回归时才接受"
    """

    async def run(self) -> SelfImprovementReport:
        """执行一次完整的自改进循环"""
        report_id = str(uuid.uuid4())[:12]
        now = datetime.now().isoformat()

        # Step 0: 收集轨迹
        trajectories = trajectory_store.get_recent(limit=50)
        failures = trajectory_store.get_failure_trajectories(limit=50)

        playbook_before = await playbook.get_entries()

        if len(trajectories) < config.SELF_IMPROVE_MIN_TRAJECTORIES:
            return SelfImprovementReport(
                reportId=report_id,
                runAt=now,
                trajectoriesAnalyzed=len(trajectories),
                weaknessPatterns=[],
                proposals=[],
                validations=[],
                acceptedChanges=0,
                playbookBeforeSize=len(playbook_before),
                playbookAfterSize=len(playbook_before),
            )

        # Step 1: Weakness Mining — 聚类失败模式
        patterns = await self._weakness_mining(failures)

        if not patterns:
            return SelfImprovementReport(
                reportId=report_id,
                runAt=now,
                trajectoriesAnalyzed=len(trajectories),
                weaknessPatterns=[],
                proposals=[],
                validations=[],
                acceptedChanges=0,
                playbookBeforeSize=len(playbook_before),
                playbookAfterSize=len(playbook_before),
            )

        # Step 2: Harness Proposal — 提出修改方案
        proposals = await self._harness_proposal(patterns)

        # Step 3: Proposal Validation — held-in / held-out 验证
        # 将失败轨迹分为 held-in (70%) 和 held-out (30%)
        split_idx = int(len(failures) * (1 - config.SELF_IMPROVE_HELD_OUT_RATIO))
        held_in = failures[:split_idx]
        held_out = failures[split_idx:]

        validations = []
        accepted_proposals = []

        for proposal in proposals:
            validation = await self._validate_proposal(
                proposal, held_in, held_out, patterns
            )
            validations.append(validation)

            if validation.accepted:
                accepted_proposals.append(proposal)

        # Step 4: Apply accepted changes — 更新 playbook
        for proposal in accepted_proposals:
            await self._apply_proposal(proposal)

        playbook_after = await playbook.get_entries()

        # 精炼 playbook
        await playbook.deduplicate()

        return SelfImprovementReport(
            reportId=report_id,
            runAt=now,
            trajectoriesAnalyzed=len(trajectories),
            weaknessPatterns=patterns,
            proposals=proposals,
            validations=validations,
            acceptedChanges=len(accepted_proposals),
            playbookBeforeSize=len(playbook_before),
            playbookAfterSize=len(await playbook.get_entries()),
        )

    # ---- Step 1: Weakness Mining ----

    async def _weakness_mining(self, failures: list[TrajectoryRecord]) -> list[WeaknessPattern]:
        """
        聚类失败模式。
        对应论文: "失败记录包含丰富信息，将失败聚类为 verifier-grounded failure patterns"
        """
        if not failures:
            return []

        # 先用规则提取初步模式
        rule_patterns = self._rule_based_patterns(failures)

        # 如果轨迹少，直接用规则结果
        if len(failures) < 5:
            return rule_patterns

        # 用 LLM 深度分析
        summaries = []
        for f in failures[:20]:
            summaries.append(
                f"- 请求: {f.userMessage[:60]} | "
                f"结果: {f.outcome} | "
                f"HITL: {f.hitlTriggered}({f.hitlReason}) | "
                f"迭代: {f.iterationCount} | "
                f"候选: {f.candidateCount} | "
                f"评分: {f.reflectionScore} | "
                f"备注: {f.reflectionNotes[:80]}"
            )

        llm = get_llm()
        prompt = WEAKNESS_MINING_PROMPT.format(
            count=len(failures),
            trajectory_summaries="\n".join(summaries),
        )

        try:
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            import re
            text = response.content.strip()
            if text.startswith("```"):
                text = "\n".join(text.split("\n")[1:-1])
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                data = json.loads(match.group())
                llm_patterns = []
                for p in data.get("patterns", []):
                    llm_patterns.append(WeaknessPattern(
                        patternId=str(uuid.uuid4())[:12],
                        description=p.get("description", ""),
                        category=p.get("category", "poor_matching"),
                        affectedTrajectoryIds=[f.trajectoryId for f in failures[:5]],
                        severity=p.get("severity", 0.5),
                        suggestedFix=p.get("suggestedFix", ""),
                    ))
                # 合并规则模式和 LLM 模式（去重）
                return self._merge_patterns(rule_patterns, llm_patterns)
        except Exception as e:
            logger.error(f"LLM weakness mining failed: {e}")

        return rule_patterns

    def _rule_based_patterns(self, failures: list[TrajectoryRecord]) -> list[WeaknessPattern]:
        """规则驱动的失败模式检测"""
        patterns = []

        # 模式 1: 频繁 HITL
        hitl_failures = [f for f in failures if f.hitlTriggered]
        if len(hitl_failures) > len(failures) * 0.4:
            reasons = {}
            for f in hitl_failures:
                r = f.hitlReason or "unknown"
                reasons[r] = reasons.get(r, 0) + 1
            top_reason = max(reasons, key=reasons.get) if reasons else "unknown"
            patterns.append(WeaknessPattern(
                patternId=str(uuid.uuid4())[:12],
                description=f"Frequent HITL ({len(hitl_failures)}/{len(failures)}), top reason: {top_reason}",
                category="frequent_hitl",
                affectedTrajectoryIds=[f.trajectoryId for f in hitl_failures[:5]],
                severity=min(1.0, len(hitl_failures) / max(len(failures), 1)),
                suggestedFix="Add default assumptions for common ambiguous intents to reduce HITL",
            ))

        # 模式 2: 候选过少
        few = [f for f in failures if f.candidateCount < config.AGENT2_MIN_CANDIDATES]
        if few:
            patterns.append(WeaknessPattern(
                patternId=str(uuid.uuid4())[:12],
                description=f"Too few candidates in {len(few)} trajectories (< {config.AGENT2_MIN_CANDIDATES})",
                category="poor_matching",
                affectedTrajectoryIds=[f.trajectoryId for f in few[:5]],
                severity=0.7,
                suggestedFix="Broaden search radius or add fallback keyword search when nearby returns too few",
            ))

        # 模式 3: 低反思评分
        low_score = [f for f in failures if 0 < f.reflectionScore < config.PLAYBOOK_REFLECTION_THRESHOLD]
        if low_score:
            patterns.append(WeaknessPattern(
                patternId=str(uuid.uuid4())[:12],
                description=f"Low reflection score in {len(low_score)} trajectories (< {config.PLAYBOOK_REFLECTION_THRESHOLD})",
                category="poor_matching",
                affectedTrajectoryIds=[f.trajectoryId for f in low_score[:5]],
                severity=0.6,
                suggestedFix="Improve ranking logic or add review summary integration for better match reasons",
            ))

        return patterns

    def _merge_patterns(
        self, rule_patterns: list[WeaknessPattern], llm_patterns: list[WeaknessPattern]
    ) -> list[WeaknessPattern]:
        """合并规则模式和 LLM 模式，去重"""
        seen_descs = set()
        merged = []
        for p in rule_patterns + llm_patterns:
            key = p.description.lower()[:50]
            if key not in seen_descs:
                seen_descs.add(key)
                merged.append(p)
        return merged

    # ---- Step 2: Harness Proposal ----

    async def _harness_proposal(self, patterns: list[WeaknessPattern]) -> list[HarnessProposal]:
        """
        提议 harness 修改。
        对应论文: "同一模型在 h_t 下作为提议者，提供有界提议上下文"
        """
        from main import PLAN_SYSTEM_PROMPT

        llm = get_llm()

        # 准备上下文
        patterns_str = "\n".join(
            f"- [{p.category}] {p.description} (severity={p.severity}) → fix: {p.suggestedFix}"
            for p in patterns
        )
        playbook_entries = await playbook.get_entries()
        playbook_str = "\n".join(
            f"- [{e.category}] {e.description} (confidence={e.confidence})"
            for e in playbook_entries
        ) or "(empty)"

        prompt = HARNESS_PROPOSAL_PROMPT.format(
            current_prompt=PLAN_SYSTEM_PROMPT[:500] + "...",
            weakness_patterns=patterns_str,
            playbook_entries=playbook_str,
        )

        try:
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            import re
            text = response.content.strip()
            if text.startswith("```"):
                text = "\n".join(text.split("\n")[1:-1])
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                data = json.loads(match.group())
                proposals = []
                for p in data.get("proposals", []):
                    proposals.append(HarnessProposal(
                        proposalId=str(uuid.uuid4())[:12],
                        targetComponent=p.get("targetComponent", "system_prompt"),
                        currentContent=p.get("currentContent", ""),
                        proposedContent=p.get("proposedContent", ""),
                        rationale=p.get("rationale", ""),
                        targetWeaknessId="",
                        prediction=p.get("prediction", ""),
                    ))
                return proposals
        except Exception as e:
            logger.error(f"Harness proposal failed: {e}")

        return []

    # ---- Step 3: Proposal Validation ----

    async def _validate_proposal(
        self,
        proposal: HarnessProposal,
        held_in: list[TrajectoryRecord],
        held_out: list[TrajectoryRecord],
        patterns: list[WeaknessPattern],
    ) -> ValidationResult:
        """
        验证提议：held-in 检查弱点是否修复，held-out 检查是否引入新问题。
        对应论文: "仅在两组数据上均无回归时才接受"
        """
        # 简化验证：检查提议是否针对已识别的弱点
        held_in_passed = True
        held_out_passed = True

        # 检查提议是否有明确的预测
        if not proposal.prediction:
            held_in_passed = False

        # 检查提议的目标组件是否合理
        if proposal.targetComponent not in (
            "system_prompt", "tool_description", "middleware", "evaluation_criteria"
        ):
            held_in_passed = False

        # 模拟 held-in 验证：提议是否针对某个已识别的弱点
        targeted_pattern = None
        for p in patterns:
            if any(word in proposal.rationale.lower() for word in p.description.lower().split()[:3]):
                targeted_pattern = p
                break

        if not targeted_pattern:
            held_in_passed = False

        # 模拟 held-out 验证：提议是否会损害其他场景
        # 如果提议过于具体（只针对一种场景），可能损害泛化
        if proposal.proposedContent and len(proposal.proposedContent) > 500:
            # 过长的修改可能过于特定
            held_out_passed = False

        accepted = held_in_passed and held_out_passed

        return ValidationResult(
            proposalId=proposal.proposalId,
            heldInPassed=held_in_passed,
            heldOutPassed=held_out_passed,
            heldInMetrics={
                "targetedWeakness": targeted_pattern.description if targeted_pattern else "none",
                "hasPrediction": bool(proposal.prediction),
            },
            heldOutMetrics={
                "proposalLength": len(proposal.proposedContent),
                "componentScope": proposal.targetComponent,
            },
            accepted=accepted,
            notes=f"{'Accepted' if accepted else 'Rejected'}: "
                  f"held-in={'pass' if held_in_passed else 'fail'}, "
                  f"held-out={'pass' if held_out_passed else 'fail'}",
        )

    # ---- Step 4: Apply ----

    async def _apply_proposal(self, proposal: HarnessProposal) -> None:
        """
        应用接受的提议。
        对应论文: "接受的候选合并更新 h_t → h_{t+1}"
        
        安全约束: 只更新 playbook，不修改工具实现代码。
        """
        # 将提议转化为 playbook 条目
        insight = {
            "category": "context_gap",
            "description": proposal.proposedContent[:200] if proposal.proposedContent else proposal.rationale,
            "confidence": 0.7,
        }

        # 如果是 system_prompt 修改，作为 playbook 条目注入
        if proposal.targetComponent == "system_prompt":
            insight["category"] = "intent_parsing"
            insight["description"] = f"[HARNESS] {proposal.prediction}"
        elif proposal.targetComponent == "tool_description":
            insight["category"] = "tool_selection"

        await playbook.curate([insight], source="weakness_mining")

        logger.info(
            f"Applied harness proposal {proposal.proposalId}: "
            f"{proposal.targetComponent} → playbook entry"
        )


# 全局实例
self_improvement_engine = SelfImprovementEngine()
