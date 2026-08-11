"""Agent2: 商户推荐 Agent — Harness Engineering 四层架构。

1. Workflow（ReAct 工作流）/ 2. Context（经验上下文）/ 3. Observability（可观测性）/ 4. Self-Improvement（自进化）。
"""

import json
import logging
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import config
from core.llm import LLMBusyError
from graph.hitl import save_hitl_state, load_hitl_state, delete_hitl_state
from core.guard import guard_user_message
from core.llm import reset_token_usage, get_token_usage
from core.shop_api_http import shop_api
from memory.preferences import load_memory
from memory.playbook import playbook
from eval.runner import eval_runner
from memory.trajectory import trajectory_store
from core.models import ChatRequest, ResumeRequest
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


def _save_interrupt_state(thread_id: str, state: AgentState) -> None:
    """序列化 AgentState 并写入 HITL 中断状态，供 resume 接口恢复"""
    save_hitl_state(thread_id, state.model_dump_json())


# --- 核心 API（生产必需，不可删） ---

@app.post("/agent2/chat")
async def chat_endpoint(req: ChatRequest):
    """商户推荐对话入口"""
    try:
        from memory.conversation import append_turn, save_last_shops, get_recommended_ids, add_recommended_ids

        # 防御性校验：拒绝匿名 userId
        if not req.userId or req.userId <= 0:
            return {"type": "error", "error": "请先登录后再使用AI美食助手"}

        thread_id = req.threadId or str(uuid.uuid4())

        clean_msg = guard_user_message(req.message)
        await append_turn(thread_id, req.userId, "user", clean_msg)

        initial_state = AgentState(
            user_message=clean_msg,
            user_id=req.userId,
            user_x=req.x,
            user_y=req.y,
            thread_id=thread_id,
            recommended_shop_ids=get_recommended_ids(thread_id),
        )

        reset_token_usage()
        result_state = await compiled_graph.ainvoke(initial_state.model_dump())
        state = AgentState(**result_state)
        token_usage = get_token_usage()

        if state.hitl_needed:
            _save_interrupt_state(thread_id, state)
            return {
                "type": "interrupt",
                "question": state.hitl_question,
                "options": state.hitl_options,
                "threadId": thread_id,
                "tokenUsage": token_usage,
            }
        else:
            assistant_msg = state.final_recommendation or json.dumps(state.ranked_shops[:3], ensure_ascii=False)
            await append_turn(thread_id, req.userId, "assistant", assistant_msg)
            save_last_shops(thread_id, state.ranked_shops or [])
            # 保存本轮推荐的商铺 ID，供下一轮去重
            _new_ids = [s.get("id") or s.get("shopId") for s in (state.ranked_shops or []) if s.get("id") or s.get("shopId")]
            if _new_ids:
                add_recommended_ids(thread_id, _new_ids)
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
                "tokenUsage": token_usage,
            }

    except LLMBusyError as e:
        logger.warning(f"Agent2 chat LLM busy: {e}")
        return {"type": "busy", "message": "当前访问高峰，请稍后重试", "detail": str(e)}
    except Exception as e:
        logger.error(f"Agent2 chat failed: {e}", exc_info=True)
        return {"error": str(e), "type": "error"}


@app.post("/agent2/chat/resume")
async def resume_endpoint(req: ResumeRequest):
    """恢复中断的对话"""
    try:
        from memory.conversation import append_turn, save_last_shops, get_recommended_ids, add_recommended_ids

        # 防御性校验：拒绝匿名 userId
        if not req.userId or req.userId <= 0:
            return {"type": "error", "error": "请先登录后再使用AI美食助手"}

        thread_id = req.threadId
        raw = load_hitl_state(thread_id)
        if not raw:
            return {"error": "Thread not found or expired", "type": "error"}
        state = AgentState(**raw)

        clean_feedback = guard_user_message(req.response)
        await append_turn(thread_id, state.user_id, "user", clean_feedback)

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

        reset_token_usage()
        result_state = await compiled_graph.ainvoke(state_dict)
        state = AgentState(**result_state)
        token_usage = get_token_usage()

        if state.hitl_needed:
            _save_interrupt_state(thread_id, state)
            return {
                "type": "interrupt",
                "question": state.hitl_question,
                "options": state.hitl_options,
                "threadId": thread_id,
                "tokenUsage": token_usage,
            }
        else:
            delete_hitl_state(thread_id)
            assistant_msg = state.final_recommendation or json.dumps(state.ranked_shops[:3], ensure_ascii=False)
            await append_turn(thread_id, state.user_id, "assistant", assistant_msg)
            save_last_shops(thread_id, state.ranked_shops or [])
            # 保存本轮推荐的商铺 ID，供下一轮去重
            _new_ids = [s.get("id") or s.get("shopId") for s in (state.ranked_shops or []) if s.get("id") or s.get("shopId")]
            if _new_ids:
                add_recommended_ids(thread_id, _new_ids)
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
                "tokenUsage": token_usage,
            }

    except LLMBusyError as e:
        logger.warning(f"Agent2 resume LLM busy: {e}")
        return {"type": "busy", "message": "当前访问高峰，请稍后重试", "detail": str(e)}
    except Exception as e:
        logger.error(f"Agent2 resume failed: {e}", exc_info=True)
        return {"error": str(e), "type": "error"}


# ---- 可观测性 API ----
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
    """
    更新轨迹 outcome（显式信号：accepted/rejected）并重新触发一次蒸馏入队。

    【闭环说明 · 断口 3 修复】
    轨迹落盘时 outcome 默认是 "unknown"，信号管线走「隐式信号」判定。
    如果用户/前端在交互后调用本接口（如「用户点击查看某家详情 → accepted；用户说推荐不行 → rejected」），
    需要：
      1. 写入 outcome → trajectory_store 更新 record
      2. 清除 processed marker（否则 signals.pop_pending_batch 会认为它已处理，永远不重新走信号判定）
      3. 重新入队 PENDING_ZSET + 触发 piggyback kick → 立即按显式信号重新蒸馏 → Playbook/偏好更新

    这样显式反馈才能闭环：用户反馈 → outcome 变更 → 信号重判 → 学到经验 → 下次推理通过 Playbook augment + memory 生效。
    """
    trajectory_store.update_outcome(trajectory_id, outcome, feedback)

    # Stage4 重判入队
    try:
        from improve.signals import mark_processed, is_processed, PROCESSED_PREFIX, enqueue_for_distill
        from core.redis import get_redis
        r = get_redis()
        # 先清理 processed marker（无论 key 存在与否都安全），这样下次出队时不会被判「已处理」直接跳过
        r.delete(f"{PROCESSED_PREFIX}{trajectory_id}")
        # 重新入队（默认会触发 piggyback fire-and-forget，近实时地跑一次蒸馏）
        enqueue_for_distill(trajectory_id, schedule_piggyback=True)
        logger.info(f"[Stage4] outcome={outcome} re-enqueued trajectory={trajectory_id} for distill re-eval")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[Stage4] re-enqueue distill after outcome update failed silently: {e}")

    return {"status": "updated", "trajectoryId": trajectory_id, "outcome": outcome, "reEnqueuedForDistill": True}


# ---- Playbook 经验库 API ----
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


@app.on_event("startup")
async def startup():
    """启动时：拉起自进化蒸馏 daemon（兜底后台任务，每 5 分钟补跑一批轨迹蒸馏）"""
    from improve.signals import start_distill_daemon
    start_distill_daemon(app)


@app.on_event("shutdown")
async def shutdown():
    from improve.signals import cancel_distill_daemon
    cancel_distill_daemon(app)
    await shop_api.close()
    from core.agent1_client import agent1_client
    await agent1_client.close()
    from core.mysql_store import close_pool
    await close_pool()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=config.AGENT2_PORT)
