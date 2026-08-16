"""
[DEV ONLY] Agent2 端到端集成测试 — 真实 MySQL 数据 + DeepSeek LLM + Redis

模拟 3 轮对话: 找火锅 → 表达偏好 → 换一家
生产环境可删除，替代方案: eval/runner.py 离线评测
"""

import asyncio
import json
import os
import uuid

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def run_test():
    print("=" * 70)
    print("Agent2 端到端集成测试 — 真实 MySQL 数据 + DeepSeek LLM")
    print("=" * 70)

    # 注入真实 MySQL 数据源
    import core.shop_api_http as jc
    from core.shop_api_mysql import shop_api_mysql as real_api
    original = jc.shop_api
    jc.shop_api = real_api

    # Mock get_review_summary（Agent1 未启动时避免连接失败）
    import graph.nodes as gn
    _orig_exec = gn.execute_tool
    async def _patched(tool_name, params):
        if tool_name == "get_review_summary":
            return {"recommendation": "评价分析中", "topPros": [], "topCons": []}
        return await _orig_exec(tool_name, params)
    gn.execute_tool = _patched

    # ---- 导入核心模块 ----
    from graph.builder import run_graph
    from graph.state import AgentState
    from memory.conversation import append_turn, get_context_summary, clear_conversation, save_last_shops
    from memory.preferences import load_memory
    from memory.trajectory import trajectory_store
    from memory.playbook import playbook
    from core.redis import get_redis

    r = get_redis()
    for k in r.keys("agent2:*"): r.delete(k)
    for k in r.keys("user:*"): r.delete(k)

    thread_id = f"test-{uuid.uuid4().hex[:8]}"
    user_id, x, y = 9999, 120.17, 30.31
    clear_conversation(thread_id)

    # --- Round 1: 找火锅 ---
    print("\n" + "=" * 70)
    print('Round 1 — "附近有什么好吃的火锅"')
    print("=" * 70)

    msg1 = "附近有什么好吃的火锅"
    await append_turn(thread_id, user_id, "user", msg1)

    mem = await load_memory(user_id)
    conv = await get_context_summary(thread_id)
    pb = await playbook.get_context(user_query=msg1, max_entries=5)
    print(f"[记忆]  {json.dumps(mem.get('preferences', {}), ensure_ascii=False)[:80]}")
    print(f"[会话]  {conv[:100]}")
    print(f"[经验]  {pb[:100]}")

    s1 = AgentState(user_message=msg1, user_id=user_id, user_x=x, user_y=y, thread_id=thread_id)
    out1 = AgentState(**(await run_graph(s1.model_dump())))

    print(f"\n>>> 结果: HITL={out1.hitl_needed}  候选={len(out1.candidate_shops)}  迭代={out1.iteration_count}")
    if out1.hitl_needed:
        print(f"    HITL 提问: {out1.hitl_question}")
    if out1.ranked_shops:
        for i, s in enumerate(out1.ranked_shops[:5], 1):
            print(f"    {i}. {s.get('name','?')} ¥{s.get('avgPrice','?')} score={s.get('score','?')} | {s.get('matchReason','')[:60]}")
    print(f">>> [reflect] score={out1.reflection_score:.1f} | {out1.reflection_notes[:80]}")
    if out1.trajectory_id:
        print(f">>> [轨迹] {out1.trajectory_id}")

    asst1 = out1.final_recommendation or json.dumps((out1.ranked_shops or [])[:3], ensure_ascii=False)
    await append_turn(thread_id, user_id, "assistant", asst1[:300])
    save_last_shops(thread_id, out1.ranked_shops or [])

    # --- Round 2: 表达偏好 ---
    print("\n" + "=" * 70)
    print('Round 2 — "预算100以下，喜欢安静"')
    print("=" * 70)

    msg2 = "预算100以下，喜欢安静的环境"
    await append_turn(thread_id, user_id, "user", msg2)
    conv2 = await get_context_summary(thread_id)
    print(f"[会话]\n{conv2[:250]}\n")

    s2 = AgentState(user_message=msg2, user_id=user_id, user_x=x, user_y=y, thread_id=thread_id)
    out2 = AgentState(**(await run_graph(s2.model_dump())))

    mem2 = await load_memory(user_id)
    print(f"[记忆]  {json.dumps(mem2.get('preferences', {}), ensure_ascii=False)[:120]}")

    if out2.hitl_needed:
        print(f">>> HITL: {out2.hitl_question}")
    if out2.ranked_shops:
        for i, s in enumerate(out2.ranked_shops[:5], 1):
            print(f"    {i}. {s.get('name','?')} ¥{s.get('avgPrice','?')} score={s.get('score','?')} | {s.get('matchReason','')[:60]}")
    print(f">>> [reflect] score={out2.reflection_score:.1f} | {out2.reflection_notes[:80]}")

    asst2 = out2.final_recommendation or json.dumps((out2.ranked_shops or [])[:3], ensure_ascii=False)
    await append_turn(thread_id, user_id, "assistant", asst2[:300])
    save_last_shops(thread_id, out2.ranked_shops or [])

    # --- Round 3: 多轮对话 ---
    print("\n" + "=" * 70)
    print('Round 3 — "换一家更便宜的"')
    print("=" * 70)

    msg3 = "换一家更便宜的"
    await append_turn(thread_id, user_id, "user", msg3)

    conv3 = await get_context_summary(thread_id)
    print(f"[会话上下文 LLM压缩]\n{conv3[:300]}\n")

    s3 = AgentState(user_message=msg3, user_id=user_id, user_x=x, user_y=y, thread_id=thread_id)
    out3 = AgentState(**(await run_graph(s3.model_dump())))

    if out3.ranked_shops:
        for i, s in enumerate(out3.ranked_shops[:5], 1):
            print(f"    {i}. {s.get('name','?')} ¥{s.get('avgPrice','?')} score={s.get('score','?')} | {s.get('matchReason','')[:60]}")
    print(f">>> [reflect] score={out3.reflection_score:.1f} | {out3.reflection_notes[:80]}")

    await append_turn(thread_id, user_id, "assistant", (out3.final_recommendation or "")[:300])
    save_last_shops(thread_id, out3.ranked_shops or [])

    # --- 报告 ---
    print("\n" + "=" * 70)
    print("测试报告")
    print("=" * 70)

    trajs = trajectory_store.get_by_user(user_id)
    print(f"\n[轨迹] {len(trajs)} 条:")
    for t in trajs:
        print(f"  {t.trajectoryId}: \"{t.userMessage[:40]}\" score={t.reflectionScore} n={t.candidateCount} HITL={t.hitlTriggered}")

    pb_entries = await playbook.get_entries()
    print(f"\n[Playbook] {len(pb_entries)} 条:")
    for e in pb_entries[:5]:
        print(f"  [{e.category}] {e.description[:60]} (conf={e.confidence:.2f})")
    if len(pb_entries) > 5:
        print(f"  ... 还有 {len(pb_entries) - 5} 条")

    print("\n" + "=" * 70)
    print("集成测试完成 — 全部使用真实 MySQL 数据")
    print("=" * 70)

    jc.shop_api = original
    gn.execute_tool = _orig_exec


if __name__ == "__main__":
    asyncio.run(run_test())
