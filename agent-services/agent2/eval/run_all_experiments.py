"""
完整实验运行脚本
运行三组实验并保存 JSON 结果：
  1. Baseline 评测（60 条单轮用例）：推荐质量 + 轨迹评估 + 效率
  2. 多轮场景评测（20 个场景）：ACSR + 指代消解 + 偏好修正
  3. 消融实验（A0/A1/A2/A4）：组件必要性 + replan 有效性
"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime

# 确保项目根目录在 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.shop_api_http as jc
from core.shop_api_mysql import shop_api_mysql
from core.redis import get_redis
from core.config import config

import graph.nodes as gn
from eval.runner import (
    EvalRunner, EvalCase, DEFAULT_CASES, MULTI_TURN_CASES,
    eval_runner, _get_patches, _apply_patches, _restore_patches,
    _compute_deltas, _compare_replan, run_experiments,
)


OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "eval_results")


def setup_mock():
    """Mock Agent1 未启动的部分"""
    _orig_exec = gn.execute_tool

    async def _patched(tool_name, params):
        if tool_name == "get_review_summary":
            return {"recommendation": "分析中", "topPros": [], "topCons": []}
        return await _orig_exec(tool_name, params)

    gn.execute_tool = _patched
    jc.shop_api = shop_api_mysql
    return _orig_exec


def teardown_mock(_orig_exec):
    gn.execute_tool = _orig_exec
    jc.shop_api = None


def clear_redis():
    r = get_redis()
    for k in r.keys("agent2:*"):
        r.delete(k)


async def run_baseline_eval():
    """实验 1: Baseline 60 条单轮用例评测"""
    print("\n" + "=" * 70)
    print("实验 1: Baseline 单轮评测（60 条用例）")
    print("=" * 70)

    clear_redis()
    runner = EvalRunner()
    start = time.time()
    result = await runner.run_eval(label="baseline_60", judge=True, mode="offline")
    elapsed = time.time() - start

    print(f"\n耗时: {elapsed:.1f}s")
    m = result.metrics
    print(f"通过率: {m.passRate:.2%} ({m.passedCases}/{m.totalCases})")
    print(f"平均迭代: {m.avgIterations}")
    print(f"HITL 触发率: {m.avgHitlRate:.2%}")
    print(f"平均候选数: {m.avgCandidateCount}")
    print(f"平均相关性(LLM-Judge): {m.avgRelevanceScore}")
    print(f"平均反思分数: {m.avgReflectionScore}")
    print(f"P50/P95 延迟: {m.p50ResponseTimeMs}ms / {m.p95ResponseTimeMs}ms")
    print(f"平均 Token: {m.avgTotalTokens} (in={m.avgInputTokens}, out={m.avgOutputTokens})")
    print(f"平均 LLM 调用次数: {m.avgLlmCallCount}")

    return result.to_dict()


async def run_multi_turn_eval():
    """实验 2: 多轮场景评测（20 个场景）"""
    print("\n" + "=" * 70)
    print("实验 2: 多轮场景评测（20 个场景）")
    print("=" * 70)

    clear_redis()
    runner = EvalRunner()
    start = time.time()
    results = []
    for i, scenario in enumerate(MULTI_TURN_CASES):
        print(f"  [{i+1}/20] {scenario.caseId} ({','.join(scenario.tags)})...", end=" ", flush=True)
        t0 = time.time()
        try:
            res = await runner.run_multi_turn_scenario(scenario)
            results.append(res)
            status = "PASS" if res["passed"] else "FAIL"
            print(f"{status} ({time.time()-t0:.1f}s)")
        except Exception as e:
            results.append({"caseId": scenario.caseId, "passed": False, "error": str(e)})
            print(f"ERROR ({time.time()-t0:.1f}s): {e}")

    elapsed = time.time() - start
    passed = sum(1 for r in results if r.get("passed"))
    print(f"\n耗时: {elapsed:.1f}s")
    print(f"通过率: {passed}/{len(results)} ({passed/len(results):.2%})")

    return {"scenarios": results, "summary": {"total": len(results), "passed": passed, "passRate": round(passed/len(results), 4)}}


async def run_ablation_experiments():
    """实验 3: 消融实验（A0/A1/A2/A4）"""
    print("\n" + "=" * 70)
    print("实验 3: 消融实验（A0 baseline / A1 no_playbook / A2 no_memory / A4 no_replan）")
    print("=" * 70)

    # 用 20 条代表性用例（避免 60×4=240 次 LLM 调用耗时过长）
    # 覆盖 6 大品类、不同约束复合度
    ablation_cases = []
    categories_seen = {}
    for case in DEFAULT_CASES:
        cat = case.tags[0] if case.tags else "other"
        if categories_seen.get(cat, 0) < 4:
            ablation_cases.append(case)
            categories_seen[cat] = categories_seen.get(cat, 0) + 1
    print(f"使用 {len(ablation_cases)} 条代表性用例 × 4 变体 = {len(ablation_cases)*4} 次运行")

    runner = EvalRunner()
    runner.cases = ablation_cases

    start = time.time()
    result = await runner.run_ablation(
        variants=["baseline", "no_playbook", "no_memory", "no_replan"],
        cases=ablation_cases,
        judge=True,
    )
    elapsed = time.time() - start
    print(f"\n耗时: {elapsed:.1f}s")

    # 打印对比摘要
    print("\n--- 消融对比（vs baseline）---")
    baseline_m = result["variants"].get("baseline", {})
    for v in ["no_playbook", "no_memory", "no_replan"]:
        v_m = result["variants"].get(v, {})
        deltas = result["deltas"].get(v, {})
        print(f"\n[{v}]")
        for key in ["passRate", "avgCSR", "avgRelevanceScore", "avgTrajectoryScore", "avgTotalTokens", "avgResponseTimeMs"]:
            if key in deltas:
                d = deltas[key]
                print(f"  {key}: {d['baseline']} → {d['variant']} (Δ={d['delta']:+.4f}, {d['deltaPct']:+.1f}%)")

    # Replan 对比
    rc = result.get("replanComparison", {})
    print(f"\n--- Replan 有效性（baseline vs no_replan）---")
    print(f"触发 replan 的案例数: {rc.get('totalReplanCases', 0)}")
    print(f"replan 有效案例数: {rc.get('effectiveCount', 0)}")
    print(f"replan 成功率: {rc.get('replanSuccessRate', 0):.2%}")
    print(f"平均 ΔCSR: {rc.get('avgDeltaCSR', 0):+.4f}")
    print(f"平均 ΔReflectionScore: {rc.get('avgDeltaReflectionScore', 0):+.2f}")
    print(f"平均 ΔCandidateCount: {rc.get('avgDeltaCandidateCount', 0):+.2f}")
    print(f"平均 ΔTotalTokens: {rc.get('avgDeltaTotalTokens', 0):+.1f}")

    return result


async def main():
    print("=" * 70)
    print("Agent2 完整实验评估")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"LLM: {config.LLM_MODEL}")
    print(f"MySQL: {config.MYSQL_DATABASE}")
    print("=" * 70)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    _orig_exec = setup_mock()

    all_results = {}

    try:
        # 实验 1: Baseline 单轮评测
        all_results["exp1_baseline"] = await run_baseline_eval()

        # 实验 2: 多轮场景评测
        all_results["exp2_multi_turn"] = await run_multi_turn_eval()

        # 实验 3: 消融实验
        all_results["exp3_ablation"] = await run_ablation_experiments()

        # 实验 4: Playbook 自进化（run_experiments 内置）
        print("\n" + "=" * 70)
        print("实验 4: Playbook 自进化效果 + 消融实验（run_experiments）")
        print("=" * 70)
        clear_redis()
        exp4 = await run_experiments()
        all_results["exp4_self_improvement"] = exp4

    finally:
        teardown_mock(_orig_exec)

    # 保存结果
    output_file = os.path.join(OUTPUT_DIR, f"full_eval_{timestamp}.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)

    print("\n" + "=" * 70)
    print(f"全部实验完成！结果已保存: {output_file}")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    return output_file


if __name__ == "__main__":
    output_file = asyncio.run(main())
