"""
Agent2: 商户推荐 Agent — Harness Engineering 增强版

四层 Harness 架构:
  Layer 1 Workflow:  load_memory → plan → execute → evaluate → generate → reflect → log_trajectory
  Layer 2 Context:   plan 节点注入 ACE playbook 上下文（演化式）
  Layer 3 Observability: 每节点输入/输出/耗时/决策记录到 TrajectoryStore（分层访问）
  Layer 4 Self-Improvement: /agent2/self-improve 端点执行 propose-evaluate-accept 循环

参考: Lilian Weng《Harness Engineering for Self-Improvement》
"""

import json
import logging
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import config
from core.redis import get_redis, save_hitl_state, load_hitl_state, delete_hitl_state
from core.guard import guard_user_message
from core.java_api import java_api
from memory.user import load_memory
from memory.playbook import playbook
from eval.runner import eval_runner
from memory.trajectory import trajectory_store
from models import ChatRequest, ResumeRequest
from graph.state import AgentState
from graph.builder import compiled_graph
from graph.nodes import update_memory_node

logger = logging.getLogger(__name__)

app = FastAPI(title="Agent2 - Shop Recommendation (Harness Enhanced)", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 核心 API（生产必需，不可删）
# ============================================================

@app.post("/agent2/chat")
async def chat_endpoint(req: ChatRequest):
    """商户推荐对话入口"""
    try:
        from memory.conversation import append_turn, save_last_shops

        thread_id = req.threadId or str(uuid.uuid4())

        clean_msg = guard_user_message(req.message)
        append_turn(thread_id, req.userId, "user", clean_msg)

        initial_state = AgentState(
            user_message=clean_msg,
            user_id=req.userId,
            user_x=req.x,
            user_y=req.y,
            thread_id=thread_id,
        )

        result_state = await compiled_graph.ainvoke(initial_state.model_dump())
        state = AgentState(**result_state)

        if state.hitl_needed:
            _save_interrupt_state(thread_id, state)
            return {
                "type": "interrupt",
                "question": state.hitl_question,
                "options": state.hitl_options,
                "threadId": thread_id,
            }
        else:
            assistant_msg = state.final_recommendation or json.dumps(state.ranked_shops[:3], ensure_ascii=False)
            append_turn(thread_id, req.userId, "assistant", assistant_msg)
            save_last_shops(thread_id, state.ranked_shops or [])
            return {
                "type": "recommendation",
                "shops": state.ranked_shops,
                "finalRecommendation": state.final_recommendation,
                "memoryUpdated": state.memory_updated,
                "newPreferences": state.new_preferences,
                "threadId": thread_id,
                "reflectionScore": state.reflection_score,
                "reflectionNotes": state.reflection_notes,
                "trajectoryId": state.trajectory_id,
            }

    except Exception as e:
        logger.error(f"Agent2 chat failed: {e}", exc_info=True)
        return {"error": str(e), "type": "error"}


@app.post("/agent2/chat/resume")
async def resume_endpoint(req: ResumeRequest):
    """恢复中断的对话"""
    try:
        from memory.conversation import append_turn, save_last_shops

        thread_id = req.threadId
        raw = load_hitl_state(thread_id)
        if not raw:
            return {"error": "Thread not found or expired", "type": "error"}
        state = AgentState(**raw)

        clean_feedback = guard_user_message(req.response)
        append_turn(thread_id, state.user_id, "user", clean_feedback)

        state.user_feedback = clean_feedback
        state.hitl_needed = False
        if req.x:
            state.user_x = req.x
        if req.y:
            state.user_y = req.y

        updated = await update_memory_node(state)
        state_dict = state.model_dump()
        for k, v in updated.items():
            state_dict[k] = v

        delete_hitl_state(thread_id)

        result_state = await compiled_graph.ainvoke(state_dict)
        state = AgentState(**result_state)

        if state.hitl_needed:
            _save_interrupt_state(thread_id, state)
            return {
                "type": "interrupt",
                "question": state.hitl_question,
                "options": state.hitl_options,
                "threadId": thread_id,
            }
        else:
            assistant_msg = state.final_recommendation or json.dumps(state.ranked_shops[:3], ensure_ascii=False)
            append_turn(thread_id, state.user_id, "assistant", assistant_msg)
            save_last_shops(thread_id, state.ranked_shops or [])
            return {
                "type": "recommendation",
                "shops": state.ranked_shops,
                "finalRecommendation": state.final_recommendation,
                "memoryUpdated": state.memory_updated,
                "newPreferences": state.new_preferences,
                "threadId": thread_id,
                "reflectionScore": state.reflection_score,
                "reflectionNotes": state.reflection_notes,
                "trajectoryId": state.trajectory_id,
            }

    except Exception as e:
        logger.error(f"Agent2 resume failed: {e}", exc_info=True)
        return {"error": str(e), "type": "error"}


# ---- Layer 3: Trajectory & Observability API ----
# [DEV ONLY] 开发调试用，生产环境可删除。替代方案: test_e2e.py 直接调 trajectory_store

@app.get("/agent2/trajectory/{trajectory_id}")
async def get_trajectory(trajectory_id: str):
    record = trajectory_store.get(trajectory_id)
    if not record:
        return {"error": "Trajectory not found"}
    return {"trajectory": record.model_dump(), "analysis": trajectory_store.get_analysis(trajectory_id)}


@app.get("/agent2/trajectory/user/{user_id}")
async def get_user_trajectories(user_id: int, limit: int = 20):
    records = trajectory_store.get_by_user(user_id, limit)
    return {"trajectories": [r.model_dump() for r in records], "count": len(records)}


@app.get("/agent2/insights")
async def get_insights():
    trajectories = trajectory_store.get_recent(limit=50)
    insights = trajectory_store.compute_insights(trajectories)
    return {"insights": [i.model_dump() for i in insights], "totalTrajectories": len(trajectories)}


@app.post("/agent2/trajectory/{trajectory_id}/outcome")
async def update_trajectory_outcome(trajectory_id: str, outcome: str, feedback: str = ""):
    trajectory_store.update_outcome(trajectory_id, outcome, feedback)
    return {"status": "updated", "trajectoryId": trajectory_id, "outcome": outcome}


# ---- Layer 2: Playbook API ----
# [DEV ONLY] 开发调试用，生产环境可删除。替代方案: eval/runner.py 或 Python REPL 直接调 playbook 对象

@app.get("/agent2/playbook")
async def get_playbook():
    entries = await playbook.get_entries()
    return {
        "entries": [e.model_dump() for e in entries],
        "count": len(entries),
        "contextPreview": await playbook.get_context(),
    }


@app.post("/agent2/playbook/deduplicate")
async def deduplicate_playbook():
    removed = await playbook.deduplicate()
    return {"removed": removed, "remaining": len(await playbook.get_entries())}


@app.post("/agent2/playbook/rebuild-index")
async def rebuild_playbook_index():
    count = await playbook.rebuild_index()
    return {"status": "ok", "indexedEntries": count}


# ---- Layer 4: Self-Improvement API ----
# [UNUSED] 手动触发，未集成到 graph 工作流。真实自进化由 playbook.reflect+curate 自动运行

@app.post("/agent2/self-improve")
async def self_improve():
    from improve.self_improve import self_improvement_engine
    report = await self_improvement_engine.run()
    return report.model_dump()


# ---- Eval API ----
# [DEV ONLY] 离线评估用，生产环境可删除。替代方案: eval/runner.py 直接 import 运行

@app.get("/agent2/eval/cases")
async def get_eval_cases():
    cases = eval_runner.get_cases()
    return {"cases": [c.model_dump() for c in cases], "count": len(cases)}


@app.post("/agent2/eval/run")
async def run_eval(label: str = ""):
    result = await eval_runner.run_eval(label=label)
    return result.model_dump()


@app.get("/agent2/eval/results")
async def list_eval_results(limit: int = 20):
    return eval_runner.list_results(limit)


@app.get("/agent2/eval/{run_id}")
async def get_eval_result(run_id: str):
    result = eval_runner.get_result(run_id)
    if not result:
        return {"error": "Run not found"}
    return result.model_dump()


@app.get("/agent2/eval/compare")
async def compare_eval(before: str, after: str):
    return eval_runner.compare(before, after)


# ---- 其他 API ----
# [DEV ONLY] 开发调试用，生产环境可删除

@app.get("/agent2/memory/{user_id}")
async def get_memory_endpoint(user_id: int):
    return await load_memory(user_id)


@app.get("/agent2/health")
async def health():
    """[KEEP] 生产运维健康检查"""
    return {"status": "ok", "service": "agent2-shop-recommendation", "version": "2.0.0"}


@app.on_event("shutdown")
async def shutdown():
    await java_api.close()
    from core.mysql import close_pool
    await close_pool()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=config.AGENT2_PORT)
