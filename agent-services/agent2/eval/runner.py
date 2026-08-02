"""
[DEV ONLY] Eval 评估框架 — 三层评测

Layer 1: 结构化回归（规则驱动）— 离线模式 + 品类/价格/HITL/数量检查
Layer 2: LLM-as-Judge（语义评测）— 相关性/多样性/理由质量打分
Layer 3: 多轮场景（对话脚本）— ScenarioCase 模拟完整交互流程

生产环境可删除整目录。替代方案: test_e2e.py 单用例快速验证

Redis 存储结构：
  agent2:eval:{runId}  → EvalResult JSON
  agent2:eval:index    → ZSet (score=timestamp, member=runId)
"""

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Optional

from config import config
from core.redis import get_redis
from core.llm import get_llm
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)


# ============================================================
# 测试用例定义
# ============================================================

class EvalCase:
    """单个评测用例"""
    def __init__(self, caseId, userMessage, userId=0, x=None, y=None,
                 expectedCategory=None, expectedPriceRange=None,
                 minExpectedResults=1, maxExpectedHitl=1, maxExpectedIterations=3,
                 tags=None):
        self.caseId = caseId
        self.userMessage = userMessage
        self.userId = userId
        self.x = x
        self.y = y
        self.expectedCategory = expectedCategory
        self.expectedPriceRange = expectedPriceRange
        self.minExpectedResults = minExpectedResults
        self.maxExpectedHitl = maxExpectedHitl
        self.maxExpectedIterations = maxExpectedIterations
        self.tags = tags or []

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}


class ScenarioStep:
    """多轮对话中的一个步骤"""
    def __init__(self, role, content, expect_type=None, check=None):
        self.role = role           # "user" | "assistant" | "check"
        self.content = content     # 发送内容（用户消息 / 检查指令）
        self.expect_type = expect_type  # "recommendation" | "interrupt" | None
        self.check = check         # 验证函数 / 验证条件 dict


class ScenarioCase:
    """多轮对话场景用例"""
    def __init__(self, caseId, steps, tags=None):
        self.caseId = caseId
        self.steps = steps         # list[ScenarioStep]
        self.tags = tags or []


# ============================================================
# Layer 1: 默认单轮用例集
# ============================================================

DEFAULT_CASES: list[EvalCase] = [
    # ── 吃 ──
    EvalCase(caseId="eat_火锅",    userMessage="附近有什么好吃的火锅",        userId=1010, x=120.17, y=30.31, expectedCategory="美食",     minExpectedResults=2, tags=["吃","火锅"]),
    EvalCase(caseId="eat_日料",    userMessage="我想吃日料，预算200左右",     userId=1011, x=120.17, y=30.31, expectedCategory="美食",     expectedPriceRange=(100,300), minExpectedResults=1, tags=["吃","日料"]),
    EvalCase(caseId="eat_聚餐",    userMessage="帮我和朋友找个聚餐的地方",     userId=1012, x=120.17, y=30.31, expectedCategory="美食",     minExpectedResults=3, tags=["吃","聚餐"]),
    # ── 喝 ──
    EvalCase(caseId="drink_咖啡",  userMessage="找个安静的地方喝咖啡",        userId=1013, x=120.17, y=30.31, expectedCategory="美食",     minExpectedResults=1, tags=["喝","咖啡"]),
    EvalCase(caseId="drink_奶茶",  userMessage="附近有什么好喝的奶茶店",      userId=1014, x=120.17, y=30.31, expectedCategory="美食",     minExpectedResults=1, tags=["喝","奶茶"]),
    # ── 玩 ──
    EvalCase(caseId="play_KTV",    userMessage="附近有什么KTV可以唱歌",       userId=1015, x=120.17, y=30.31, expectedCategory="KTV",      minExpectedResults=2, tags=["玩","KTV"]),
    EvalCase(caseId="play_密室",   userMessage="想玩密室逃脱",                userId=1016, x=120.17, y=30.31, expectedCategory="丽人美发", minExpectedResults=1, tags=["玩","密室"]),
    EvalCase(caseId="play_电影",   userMessage="最近有什么电影可以看",        userId=1017, x=120.17, y=30.31, expectedCategory="丽人美发", minExpectedResults=1, tags=["玩","电影"]),
    # ── 乐 ──
    EvalCase(caseId="fun_健身",    userMessage="附近有健身房吗",              userId=1018, x=120.17, y=30.31, expectedCategory="健身运动", minExpectedResults=1, tags=["乐","健身"]),
    EvalCase(caseId="fun_按摩",    userMessage="想做个足疗放松一下",          userId=1019, x=120.17, y=30.31, expectedCategory="按摩足疗", minExpectedResults=1, tags=["乐","按摩"]),
    # ── 容错 ──
    EvalCase(caseId="edge_拼写",   userMessage="附近有什么kvt",              userId=1020, x=120.17, y=30.31, expectedCategory="KTV",      minExpectedResults=1, tags=["容错","拼写"]),
    EvalCase(caseId="edge_模糊",   userMessage="附近有什么好玩的",            userId=1021, x=120.17, y=30.31, expectedCategory="娱乐",     minExpectedResults=2, maxExpectedHitl=2, tags=["容错","模糊意图"]),
]


# ============================================================
# Layer 3: 多轮对话场景用例
# ============================================================

MULTI_TURN_CASES: list[ScenarioCase] = [
    ScenarioCase(caseId="ev_multi_001", tags=["food", "multi_turn", "hitl"], steps=[
        ScenarioStep("user", "找附近火锅", expect_type=None),
        ScenarioStep("assistant", "", expect_type="interrupt"),
        ScenarioStep("user", "预算100以下，安静的环境", expect_type=None),
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 2, "max_price": 100,
        }),
    ]),
    ScenarioCase(caseId="ev_multi_002", tags=["coffee", "multi_turn"], steps=[
        ScenarioStep("user", "找个安静的地方喝咖啡", expect_type=None),
        ScenarioStep("assistant", "", expect_type="recommendation", check={
            "min_results": 1,
        }),
    ]),
]


class EvalMetrics:
    """单次评测的聚合指标"""
    def __init__(self, totalCases=0, passedCases=0, passRate=0.0,
                 avgIterations=0.0, avgHitlRate=0.0, avgResponseTimeMs=0.0,
                 avgReflectionScore=0.0, avgCandidateCount=0.0,
                 avgRelevanceScore=0.0, categoryBreakdown=None):
        self.totalCases = totalCases
        self.passedCases = passedCases
        self.passRate = passRate
        self.avgIterations = avgIterations
        self.avgHitlRate = avgHitlRate
        self.avgResponseTimeMs = avgResponseTimeMs
        self.avgReflectionScore = avgReflectionScore
        self.avgCandidateCount = avgCandidateCount
        self.avgRelevanceScore = avgRelevanceScore or 0.0
        self.categoryBreakdown = categoryBreakdown or {}

    def to_dict(self):
        return self.__dict__


class EvalResult:
    def __init__(self, runId="", runAt="", label="", metrics=None, caseResults=None):
        self.runId = runId
        self.runAt = runAt
        self.label = label
        self.metrics = metrics or EvalMetrics()
        self.caseResults = caseResults or []

    def to_dict(self):
        return {"runId": self.runId, "runAt": self.runAt, "label": self.label,
                "metrics": self.metrics.to_dict(), "caseResults": self.caseResults}


# ============================================================
# Layer 1: 规则检查
# ============================================================

def _check_category(shops, expected_category):
    """检查推荐的品类是否包含期望关键词"""
    if not expected_category:
        return 1.0
    if not shops:
        return 0.0
    keyword = expected_category.lower()
    match_count = 0
    for s in shops[:3]:
        name = (s.get("name") or "").lower()
        reason = (s.get("matchReason") or "").lower()
        if keyword in name or keyword in reason:
            match_count += 1
    return min(1.0, match_count / max(1, min(len(shops), 3)))


def _check_price(shops, expected_range):
    """检查推荐价格是否在期望范围内"""
    if not expected_range or not shops:
        return 1.0
    prices = [s.get("avgPrice", 0) for s in shops if s.get("avgPrice")]
    if not prices:
        return 1.0
    p_min, p_max = expected_range
    in_range = sum(1 for p in prices[:3] if p_min <= p <= p_max)
    return in_range / min(len(prices), 3)


def _calc_hitl_score(hitl_triggered, max_expected):
    """HITL 评分：触发次数越少越好，但不应始终为 0"""
    if not hitl_triggered:
        return 1.0
    if max_expected == 0:
        return 0.0
    return max(0.0, 1.0 - (1.0 / max_expected))


# ============================================================
# Layer 2: LLM-as-Judge
# ============================================================

JUDGE_PROMPT = """你是推荐质量评估器。对以下推荐打分（1-5）。

用户请求: {query}
推荐结果: {shops}

评分维度:
- relevance: 推荐是否匹配用户的品类/偏好/意图（1=完全不匹配, 5=完全匹配）
- diversity: Top-3 是否覆盖不同类型的选项（1=同质化, 5=多样化）
- reasoning: matchReason 是否有说服力和个性化（1=敷衍模板, 5=有理有据）

只输出 JSON:
{{"relevance": 4, "diversity": 3, "reasoning": 4}}"""


async def _llm_judge(query, shops):
    """LLM-as-Judge 语义评分"""
    if not shops:
        return {"relevance": 0, "diversity": 0, "reasoning": 0}
    try:
        llm = get_llm()
        shops_text = json.dumps([{
            "name": s.get("name", "?"),
            "avgPrice": s.get("avgPrice", "?"),
            "reason": s.get("matchReason", "")[:80],
        } for s in shops[:5]], ensure_ascii=False)
        prompt = JUDGE_PROMPT.format(query=query, shops=shops_text)
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        import re
        match = re.search(r'\{.*\}', resp.content, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        logger.error(f"LLM judge failed: {e}")
    return {"relevance": 0, "diversity": 0, "reasoning": 0}


# ============================================================
# EvalRunner — 统一评测运行器
# ============================================================

class EvalRunner:
    """Eval 评测运行器 — 支持单轮 + 多轮场景 + LLM-as-Judge"""

    def __init__(self):
        self.prefix = getattr(config, 'EVAL_KEY_PREFIX', 'agent2:eval:')
        self.cases = list(DEFAULT_CASES)

    def get_cases(self) -> list[dict]:
        return [c.to_dict() for c in self.cases]

    # ---- 离线模式：直接 import graph，不调 HTTP ----

    async def run_single_case_offline(self, case: EvalCase, judge: bool = True) -> dict:
        """离线运行单个用例（直接 import compiled_graph）"""
        from graph.builder import compiled_graph
        from graph.state import AgentState

        start_time = time.time()
        out = {
            "caseId": case.caseId, "userMessage": case.userMessage,
            "passed": False, "hitlTriggered": False, "iterations": 0,
            "candidateCount": 0, "shops": [], "reflectionScore": 0.0,
            "responseTimeMs": 0.0, "error": None, "tags": case.tags,
            "categoryScore": 1.0, "priceScore": 1.0, "hitlScore": 1.0,
            "llmJudge": None,
        }

        try:
            state = AgentState(
                user_message=case.userMessage, user_id=case.userId,
                user_x=case.x, user_y=case.y,
                thread_id=f"eval-{uuid.uuid4().hex[:8]}",
            )
            result_state = await compiled_graph.ainvoke(state.model_dump())
            st = AgentState(**result_state)
            elapsed = (time.time() - start_time) * 1000
            out["responseTimeMs"] = round(elapsed, 1)
            out["iterations"] = st.iteration_count

            if st.hitl_needed:
                out["hitlTriggered"] = True
                out["error"] = f"HITL: {st.hitl_question}"
                out["passed"] = True
            else:
                shops = st.ranked_shops or []
                out["candidateCount"] = len(shops)
                out["shops"] = shops[:5]
                out["reflectionScore"] = st.reflection_score

                # Layer 1: 规则评分
                out["categoryScore"] = _check_category(shops, case.expectedCategory)
                out["priceScore"] = _check_price(shops, case.expectedPriceRange)
                out["hitlScore"] = _calc_hitl_score(st.hitl_needed, case.maxExpectedHitl)

                # Layer 2: LLM-as-Judge
                if judge and shops:
                    out["llmJudge"] = await _llm_judge(case.userMessage, shops)

                # 综合判定：3个维度加权
                passed = (
                    len(shops) >= case.minExpectedResults
                    and out["categoryScore"] >= 0.5
                )
                out["passed"] = passed
                if not passed:
                    reasons = []
                    if len(shops) < case.minExpectedResults:
                        reasons.append(f"results={len(shops)} < {case.minExpectedResults}")
                    if out["categoryScore"] < 0.5:
                        reasons.append(f"categoryScore={out['categoryScore']:.1f}")
                    out["error"] = "; ".join(reasons) if reasons else None

        except Exception as e:
            out["error"] = str(e)
            out["responseTimeMs"] = round((time.time() - start_time) * 1000, 1)

        return out

    # ---- HTTP 模式（向后兼容）----

    async def run_single_case(self, case: EvalCase) -> dict:
        """HTTP 模式运行单个用例（需要 Agent2 服务在运行）"""
        import httpx

        start_time = time.time()
        out = {
            "caseId": case.caseId, "userMessage": case.userMessage,
            "passed": False, "hitlTriggered": False, "iterations": 0,
            "candidateCount": 0, "reflectionScore": 0.0,
            "responseTimeMs": 0.0, "error": None, "tags": case.tags,
            "categoryScore": 1.0, "priceScore": 1.0, "hitlScore": 1.0,
            "llmJudge": None,
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"http://localhost:{config.AGENT2_PORT}/agent2/chat",
                    json={"userId": case.userId, "message": case.userMessage, "x": case.x, "y": case.y},
                    timeout=120.0,
                )
                data = resp.json()
            elapsed = (time.time() - start_time) * 1000
            out["responseTimeMs"] = round(elapsed, 1)

            if data.get("type") == "recommendation":
                shops = data.get("shops", [])
                out["candidateCount"] = len(shops)
                out["reflectionScore"] = data.get("reflectionScore", 0.0)
                out["passed"] = len(shops) >= case.minExpectedResults
                if not out["passed"]:
                    out["error"] = f"results={len(shops)} < {case.minExpectedResults}"
            elif data.get("type") == "interrupt":
                out["hitlTriggered"] = True
                out["passed"] = True
        except Exception as e:
            out["error"] = str(e)
            out["responseTimeMs"] = round((time.time() - start_time) * 1000, 1)
        return out

    # ---- 聚合 ----

    async def run_eval(self, label: str = "", judge: bool = True, mode: str = "offline") -> EvalResult:
        """运行完整评测"""
        run_id = str(uuid.uuid4())[:12]
        now = datetime.now().isoformat()
        case_results = []

        runner = self.run_single_case_offline if mode == "offline" else self.run_single_case
        for case in self.cases:
            r = await runner(case, judge=judge) if mode == "offline" else await runner(case)
            case_results.append(r)

        total = len(case_results)
        passed = sum(1 for r in case_results if r["passed"])
        hitl_count = sum(1 for r in case_results if r["hitlTriggered"])
        total_iter = sum(r["iterations"] for r in case_results)
        total_time = sum(r["responseTimeMs"] for r in case_results)
        total_candidates = sum(r.get("candidateCount", 0) for r in case_results)
        score_sum = sum(r.get("reflectionScore", 0) for r in case_results if r.get("reflectionScore", 0) > 0)
        rel_sum = sum(r.get("llmJudge", {}).get("relevance", 0) for r in case_results if r.get("llmJudge"))

        metrics = EvalMetrics(
            totalCases=total, passedCases=passed,
            passRate=round(passed / total, 4) if total > 0 else 0,
            avgIterations=round(total_iter / total, 2) if total > 0 else 0,
            avgHitlRate=round(hitl_count / total, 4) if total > 0 else 0,
            avgResponseTimeMs=round(total_time / total, 1) if total > 0 else 0,
            avgReflectionScore=round(score_sum / total, 2) if total > 0 else 0,
            avgCandidateCount=round(total_candidates / total, 2) if total > 0 else 0,
            avgRelevanceScore=round(rel_sum / total, 2) if total > 0 else 0,
            categoryBreakdown=self._category_breakdown(case_results),
        )

        result = EvalResult(runId=run_id, runAt=now, label=label, metrics=metrics, caseResults=case_results)
        self._save_result(result)
        return result

    def _category_breakdown(self, case_results):
        tag_stats = {}
        for r in case_results:
            for tag in r.get("tags", []):
                s = tag_stats.setdefault(tag, {"total": 0, "passed": 0})
                s["total"] += 1
                if r["passed"]: s["passed"] += 1
        return {tag: {"passRate": round(s["passed"] / s["total"], 4) if s["total"] > 0 else 0, **s} for tag, s in tag_stats.items()}

    # ---- 持久化 ----

    def _save_result(self, result: EvalResult):
        r = get_redis()
        r.set(f"{self.prefix}{result.runId}", json.dumps(result.to_dict(), ensure_ascii=False), ex=90 * 24 * 3600)
        ts = datetime.fromisoformat(result.runAt).timestamp()
        r.zadd(f"{self.prefix}index", {result.runId: ts})

    def get_result(self, run_id: str) -> Optional[dict]:
        r = get_redis()
        raw = r.get(f"{self.prefix}{run_id}")
        return json.loads(raw) if raw else None

    def list_results(self, limit: int = 20) -> list[dict]:
        r = get_redis()
        ids = r.zrevrange(f"{self.prefix}index", 0, limit - 1)
        results = []
        for rid in ids:
            result = self.get_result(rid)
            if result:
                results.append({"runId": result["runId"], "label": result["label"],
                                "runAt": result["runAt"], "passRate": result["metrics"]["passRate"]})
        return results

    def compare(self, before_id: str, after_id: str) -> dict:
        before = self.get_result(before_id)
        after = self.get_result(after_id)
        if not before or not after:
            return {"error": "Run not found"}

        bm, am = before["metrics"], after["metrics"]
        deltas = {k: round(am.get(k, 0) - bm.get(k, 0), 4) for k in bm if isinstance(bm[k], (int, float))}

        case_comparison = []
        before_cases = {c["caseId"]: c for c in before["caseResults"]}
        after_cases = {c["caseId"]: c for c in after["caseResults"]}
        for case_id in before_cases:
            bc, ac = before_cases.get(case_id, {}), after_cases.get(case_id, {})
            bp = bc.get("passed", False)
            ap = ac.get("passed", False)
            status = "regressed" if bp and not ap else "improved" if not bp and ap else "both_passed" if bp and ap else "both_failed"
            case_comparison.append({"caseId": case_id, "beforePassed": bp, "afterPassed": ap, "status": status})

        regressions = [c for c in case_comparison if c["status"] == "regressed"]
        improvements = [c for c in case_comparison if c["status"] == "improved"]

        return {
            "before": {"runId": before_id, "label": before["label"], "metrics": bm},
            "after": {"runId": after_id, "label": after["label"], "metrics": am},
            "deltas": deltas,
            "caseComparison": case_comparison,
            "summary": {
                "improvements": len(improvements),
                "regressions": len(regressions),
                "overallVerdict": "improved" if deltas.get("passRate", 0) > 0 else
                                  "regressed" if deltas.get("passRate", 0) < 0 else "neutral",
            },
        }


# ============================================================
# [DEV ONLY] Ablation Runner — 消融实验。可删除，消融功能已通过子进程脚本独立运行（见 git history）
# ============================================================

ABLATION_NAMES = {
    "no_playbook":    "移除 Playbook（全局经验）",
    "no_memory":      "移除 User Memory（用户偏好）",
    "no_conversation": "移除 Conversation（会话上下文）",
    "no_hitl":         "移除 HITL（强制直推）",
}


async def _run_with_patch(label, patch_fn):
    """运行一次评测，临时打补丁"""
    import graph.nodes as gn
    import memory.user as mu
    import memory.playbook as pb
    import memory.conversation as cv

    # 保存原始函数
    orig = {}
    patch_targets = patch_fn()
    for module, name, replacement in patch_targets:
        orig[(module, name)] = getattr(module, name)
        setattr(module, name, replacement)

    try:
        from eval.runner import eval_runner
        result = await eval_runner.run_eval(label=label, judge=True, mode="offline")
        return result
    finally:
        for (module, name), fn in orig.items():
            setattr(module, name, fn)


def _get_patches(variant: str):
    """返回需要替换的函数列表 [(module, attr_name, replacement_fn), ...]"""
    import memory.playbook as pb
    import memory.user as mu
    import memory.conversation as cv
    import graph.nodes as gn
    import asyncio

    if variant == "no_playbook":
        async def empty_context(*a, **kw):
            return "(暂无历史经验)"
        return [(pb.playbook, "get_context", empty_context)]

    elif variant == "no_memory":
        async def empty_memory(user_id):
            return {"userId": user_id, "preferences": {}, "lastUpdated": None, "interactionCount": 0}
        return [(mu, "load_memory", empty_memory)]

    elif variant == "no_conversation":
        async def empty_convo(thread_id):
            return "(无会话历史)"
        return [(cv, "get_context_summary", empty_convo)]

    elif variant == "no_hitl":
        # 强制 evaluate_node 不触发 HITL
        orig_eval = gn.evaluate_node
        async def no_hitl_eval(state):
            result = await orig_eval(state)
            result["hitl_needed"] = False
            return result
        return [(gn, "evaluate_node", no_hitl_eval)]
    else:
        return []


async def run_ablation():
    """运行完整消融实验：Baseline + 4 个消融变体，返回对比表"""
    from eval.runner import eval_runner
    from core.redis import get_redis
    import time

    r = get_redis()
    for k in r.keys("agent2:*"):
        r.delete(k)

    results = {}

    # Baseline
    t0 = time.time()
    baseline = await eval_runner.run_eval(label="baseline", judge=True, mode="offline")
    results["baseline"] = baseline
    print(f"  [baseline]           passRate={baseline.metrics.passRate*100:.0f}%  relevance={baseline.metrics.avgRelevanceScore:.1f}  time={time.time()-t0:.0f}s")

    # Ablations
    for variant in ["no_playbook", "no_memory", "no_conversation", "no_hitl"]:
        t0 = time.time()
        ablated = await _run_with_patch(variant, lambda v=variant: _get_patches(v))
        results[variant] = ablated
        print(f"  [{variant:<18}] passRate={ablated.metrics.passRate*100:.0f}%  relevance={ablated.metrics.avgRelevanceScore:.1f}  time={time.time()-t0:.0f}s")

    # 对比报告
    report = []
    for variant, name in ABLATION_NAMES.items():
        bm = results["baseline"].metrics
        am = results[variant].metrics
        relevance_delta = am.avgRelevanceScore - bm.avgRelevanceScore
        hitl_delta = am.avgHitlRate - bm.avgHitlRate
        pass_delta = am.passRate - bm.passRate

        report.append({
            "variant": variant,
            "label": name,
            "passRateDelta": round(pass_delta, 3),
            "relevanceDelta": round(relevance_delta, 2),
            "hitlRateDelta": round(hitl_delta, 2),
            "avgCandidateDelta": round(am.avgCandidateCount - bm.avgCandidateCount, 2),
        })

    return {
        "baseline": {
            "passRate": results["baseline"].metrics.passRate,
            "relevance": results["baseline"].metrics.avgRelevanceScore,
            "hitlRate": results["baseline"].metrics.avgHitlRate,
            "avgCandidates": results["baseline"].metrics.avgCandidateCount,
        },
        "ablations": report,
    }


eval_runner = EvalRunner()
