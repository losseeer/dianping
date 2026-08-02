"""LangGraph nodes"""
import json
import logging
import uuid
import time
from langchain_core.messages import HumanMessage, SystemMessage
from config import config
from core.llm import get_llm
from core.guard import guard_user_message, validate_tool_calls, truncate_review_summary, limit_candidates_for_prompt
from core.java_api import java_api
from core.redis import get_redis
from memory.user import load_memory, save_memory
from memory.playbook import playbook
from improve.reflect import reflect_node
from memory.trajectory import trajectory_store
from graph.utils import _sv, timed_node, _parse_llm_json
from graph.prompts import PLAN_SYSTEM_PROMPT, EVALUATE_SYSTEM_PROMPT, GENERATE_SYSTEM_PROMPT, MEMORY_UPDATE_PROMPT
from graph.state import AgentState
from models import TrajectoryRecord, TrajectoryNodeLog

logger = logging.getLogger(__name__)

async def execute_tool(tool_name: str, params: dict) -> dict:
    """路由工具名到实际实现"""
    try:
        if tool_name == "search_shops_by_keyword":
            keyword = params.get("keyword", "")
            shops = await java_api.search_shops_by_name(keyword)
            for s in shops:
                if s.get("score") and s["score"] > 5:
                    s["score"] = s["score"] / 10.0
            return {"shops": shops, "count": len(shops)}

        elif tool_name == "search_shops_nearby":
            type_id = params.get("typeId")
            x = params.get("x") or params.get("user_x")
            y = params.get("y") or params.get("user_y")
            shops = await java_api.search_shops_nearby(type_id, x, y)
            max_price = params.get("maxPrice")
            min_score = params.get("minScore")
            if max_price:
                shops = [s for s in shops if s.get("avgPrice", 999) <= max_price]
            if min_score:
                shops = [s for s in shops if s.get("score", 0) / 10.0 >= min_score]
            for s in shops:
                if s.get("score") and s["score"] > 5:
                    s["score"] = s["score"] / 10.0
            return {"shops": shops, "count": len(shops)}

        elif tool_name == "get_shop_detail":
            shop_id = params.get("shopId")
            shop = await java_api.get_shop_detail(shop_id)
            if shop.get("score") and shop["score"] > 5:
                shop["score"] = shop["score"] / 10.0
            return {"shop": shop}

        elif tool_name == "get_shop_types":
            types = await java_api.get_shop_types()
            return {"types": types}

        elif tool_name == "get_review_summary":
            shop_id = params.get("shopId")
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"http://localhost:{config.AGENT1_PORT}/agent1/summary",
                    json={"shopId": shop_id},
                    timeout=60.0,
                )
                return resp.json()

        elif tool_name == "get_user_memory":
            user_id = params.get("userId")
            mem = await load_memory(user_id)
            return {"memory": mem}

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    except Exception as e:
        logger.error(f"Tool execution failed: {tool_name}, {e}", exc_info=True)
        return {"error": str(e)}


# ============================================================
# LangGraph 节点
# ============================================================

@timed_node("load_memory")
async def load_memory_node(state: AgentState) -> dict:
    """从 Redis 加载用户偏好记忆"""
    memory = await load_memory(state.user_id) if state.memory == {} else state.memory
    return {
        "memory": memory,
        "iteration_count": 0,
    }


@timed_node("plan")
async def plan_node(state: AgentState) -> dict:
    """
    LLM 推理——分析意图、决定调用哪些工具。
    注入三段上下文：会话级摘要（短期）+ 用户偏好（长期 per-user）+ Agent经验（长期 global）
    """
    llm = get_llm()

    memory_str = json.dumps(state.memory.get("preferences", {}), ensure_ascii=False)

    # 会话级短期记忆：多轮对话上下文摘要（截断防止 token 爆炸）
    conversation_summary = "(无会话历史)"
    last_shops_text = ""
    thread_id = _sv(state, "thread_id", "")
    if thread_id:
        from memory.conversation import get_context_summary, get_last_shops
        conversation_summary = await get_context_summary(thread_id)
        max_chars = config.TOKEN_MAX_CONVERSATION_CHARS
        if len(conversation_summary) > max_chars:
            conversation_summary = conversation_summary[:max_chars] + "\n...(上下文已截断)"
        last_shops_text = get_last_shops(thread_id) or "(无上轮推荐)"

    # RAG 检索：语义匹配 Playbook 条目
    playbook_context = await playbook.get_context(
        max_entries=8,
        user_query=_sv(state, "user_message", ""),
        conversation_summary=conversation_summary,
    )

    prompt = PLAN_SYSTEM_PROMPT.format(
        memory=memory_str,
        playbook=playbook_context,
        conversation=conversation_summary,
        last_shops=last_shops_text,
    )

    context_msg = f"用户消息：{guard_user_message(state.user_message)}"
    if state.tool_results:
        context_msg += f"\n\n已有的工具执行结果：\n{json.dumps(state.tool_results[-5:], ensure_ascii=False)}"
    if state.candidate_shops:
        context_msg += f"\n\n已有候选商铺：{len(state.candidate_shops)} 家"
    if state.replan_hints:
        context_msg += f"\n\n重规划提示：{json.dumps(state.replan_hints, ensure_ascii=False)}"

    response = await llm.ainvoke([
        SystemMessage(content=prompt),
        HumanMessage(content=context_msg),
    ])

    parsed = _parse_llm_json(response.content)

    # Layer 1: 工具调用白名单校验
    raw_tool_calls = [tc for tc in (parsed.get("tool_calls") or []) if isinstance(tc, dict)]
    valid_tool_calls, rejected = validate_tool_calls(raw_tool_calls)

    # Layer 3: Decision logging
    decision = {
        "node": "plan",
        "decision": "tool_calls" if parsed.get("tool_calls") else "hitl" if parsed.get("hitl_needed") else "unknown",
        "reasoning": parsed.get("reasoning", "")[:200],
        "prediction": f"Expected {len(parsed.get('tool_calls', []))} tool calls, HITL={parsed.get('hitl_needed', False)}",
        "verified": None,
    }

    return {
        "plan": parsed.get("reasoning", ""),
        "tool_calls": valid_tool_calls,
        # 防止死循环：已被 HITL 中断过 → 不再中断，直接选默认策略继续
        "hitl_needed": parsed.get("hitl_needed", False) and state.hitl_count == 0,
        "hitl_question": parsed.get("hitl_question") or "",
        "hitl_options": parsed.get("hitl_options") or [],
        "hitl_count": state.hitl_count + (1 if parsed.get("hitl_needed", False) else 0),
        "iteration_count": state.iteration_count + 1,
        "decisions": state.decisions + [decision] if state.decisions else [decision],
    }


@timed_node("execute")
async def execute_node(state: AgentState) -> dict:
    """执行工具调用"""
    results = []
    new_candidates = list(state.candidate_shops) if state.candidate_shops else []

    for tc in state.tool_calls:
        tool_name = tc.get("name")
        params = tc.get("params", {})
        if state.user_x and "x" not in params:
            params["user_x"] = state.user_x
        if state.user_y and "y" not in params:
            params["user_y"] = state.user_y

        result = await execute_tool(tool_name, params)
        results.append({"tool": tool_name, "params": params, "result": result})

        if "shops" in result:
            for s in result["shops"]:
                if not any(c.get("id") == s.get("id") for c in new_candidates):
                    new_candidates.append(s)

    return {
        "tool_results": state.tool_results + results,
        "candidate_shops": new_candidates,
    }


@timed_node("evaluate")
async def evaluate_node(state: AgentState) -> dict:
    """LLM 评估当前数据是否足够"""
    llm = get_llm()

    summary_parts = []
    for tr in state.tool_results[-5:]:
        tool = tr.get("tool")
        result = tr.get("result", {})
        if "shops" in result:
            summary_parts.append(f"{tool}: 找到 {result.get('count', 0)} 家商铺")
        elif "shop" in result:
            summary_parts.append(f"{tool}: {result['shop'].get('name', '未知')}")
        elif "types" in result:
            summary_parts.append(f"{tool}: 获取了类型列表")
        elif "memory" in result:
            summary_parts.append(f"{tool}: 获取了用户记忆")
        else:
            summary_parts.append(f"{tool}: {json.dumps(result, ensure_ascii=False)[:100]}")

    tool_results_summary = "\n".join(summary_parts)
    memory_str = json.dumps(state.memory.get("preferences", {}), ensure_ascii=False)

    prompt = EVALUATE_SYSTEM_PROMPT.format(
        tool_results_summary=tool_results_summary,
        candidate_count=len(state.candidate_shops),
        memory=memory_str,
    )

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    parsed = _parse_llm_json(response.content)

    evaluation = parsed.get("evaluation", "insufficient")

    updates = {
        "evaluation": evaluation,
    }

    # Layer 3: Decision logging
    decision = {
        "node": "evaluate",
        "decision": evaluation,
        "reasoning": parsed.get("reasoning", "")[:200],
        "prediction": f"Will {'generate' if evaluation == 'sufficient' else 'replan' if evaluation == 'insufficient' else 'interrupt'}",
        "verified": None,
    }
    updates["decisions"] = state.decisions + [decision] if state.decisions else [decision]

    if evaluation == "hitl_needed":
        # 防止死循环：已被 HITL 中断过 → 不再中断，直接生成推荐
        updates["hitl_needed"] = state.hitl_count == 0
        updates["hitl_question"] = parsed.get("hitl_question") or "你能告诉我更多偏好吗？"
        updates["hitl_options"] = parsed.get("hitl_options") or []
        updates["hitl_reason"] = parsed.get("hitl_reason") or ""
        updates["hitl_count"] = state.hitl_count + 1
    elif evaluation == "insufficient":
        raw_next = parsed.get("next_tool_calls", [])
        updates["tool_calls"], _ = validate_tool_calls(raw_next)

    return updates


@timed_node("update_memory")
async def update_memory_node(state: AgentState) -> dict:
    """从用户反馈中提取偏好并更新记忆"""
    llm = get_llm()

    memory_str = json.dumps(state.memory, ensure_ascii=False)
    prompt = MEMORY_UPDATE_PROMPT.format(
        original_message=state.user_message,
        feedback=state.user_feedback,
        memory=memory_str,
    )

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    parsed = _parse_llm_json(response.content)

    new_prefs = parsed.get("newPreferences", {})
    extracted_keywords = parsed.get("extractedKeywords", [])

    memory_update = {"preferences": new_prefs}
    await save_memory(state.user_id, memory_update)

    updated_memory = await load_memory(state.user_id)

    return {
        "memory": updated_memory,
        "memory_updated": True,
        "new_preferences": extracted_keywords,
        "hitl_needed": False,
        "iteration_count": 0,
    }


@timed_node("generate")
async def generate_recommendation_node(state: AgentState) -> dict:
    """LLM 综合所有信息生成最终推荐"""
    llm = get_llm()

    summaries = {}
    for tr in state.tool_results:
        if tr.get("tool") == "get_review_summary":
            result = tr.get("result", {})
            if "shopName" in result:
                summaries[result.get("shopId")] = truncate_review_summary({
                    "positiveRate": result.get("positiveRate"),
                    "topPros": result.get("topPros"),
                    "topCons": result.get("topCons"),
                    "recommendation": result.get("recommendation"),
                })

    # Token 控制: 截断候选数量（按评分取 Top-N）
    limited_candidates = limit_candidates_for_prompt(state.candidate_shops)

    candidates_str = json.dumps(limited_candidates, ensure_ascii=False)
    memory_str = json.dumps(state.memory.get("preferences", {}), ensure_ascii=False)
    summaries_str = json.dumps(summaries, ensure_ascii=False) if summaries else "无"

    prompt = GENERATE_SYSTEM_PROMPT.format(
        candidates=candidates_str,
        memory=memory_str,
        review_summaries=summaries_str,
    )

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    parsed = _parse_llm_json(response.content)

    shops = parsed.get("shops", [])
    recommendation_text = parsed.get("final_recommendation", "")

    return {
        "ranked_shops": shops,
        "final_recommendation": recommendation_text,
    }


# ---- Layer 1: reflect 节点 (从 reflect.py 导入，加 timing) ----

@timed_node("reflect")
async def reflect_with_timing(state: AgentState) -> dict:
    """推荐质量自评 — 薄包装 reflect_node 添加 timing"""
    return await reflect_node(state)


# ---- Layer 3: log_trajectory 节点 ----

@timed_node("log_trajectory")
async def log_trajectory_node(state: AgentState) -> dict:
    """
    持久化执行轨迹到 TrajectoryStore。
    对应 AHE Experience Observability: 每次执行的完整记录。
    """
    record = TrajectoryRecord(
        trajectoryId=state.trajectory_id or str(uuid.uuid4()),
        userId=state.user_id,
        threadId=state.thread_id,
        userMessage=state.user_message,
        nodeLogs=[
            TrajectoryNodeLog(**log) for log in state.node_logs
        ],
        decisions=state.decisions,
        candidateCount=len(state.candidate_shops),
        hitlTriggered=state.hitl_needed,
        hitlReason=state.hitl_reason,
        iterationCount=state.iteration_count,
        finalRecommendation=state.final_recommendation,
        rankedShops=state.ranked_shops,
        userFeedback=state.user_feedback,
        outcome="unknown",
        reflectionScore=state.reflection_score,
        reflectionNotes=state.reflection_notes,
        createdAt=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )

    traj_id = trajectory_store.save(record)

    # 生成分析报告
    trajectory_store.analyze_trajectory(record)

    # Layer 2: 如果反思评分低，触发 playbook reflection
    if state.reflection_score > 0 and state.reflection_score < config.PLAYBOOK_REFLECTION_THRESHOLD:
        try:
            insights = await playbook.reflect(record)
            if insights:
                await playbook.curate(insights, source="reflection")
                logger.info(f"Playbook updated with {len(insights)} insights from trajectory {traj_id}")
        except Exception as e:
            logger.error(f"Playbook reflection failed: {e}")

    return {"trajectory_id": traj_id}


