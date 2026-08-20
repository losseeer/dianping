"""LangGraph 节点定义"""
import asyncio
import json
import logging
import uuid
import time
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt
from core.config import config
from core.llm import get_llm, call_llm
from core.guard import guard_user_message, validate_tool_calls, truncate_review_summary, limit_candidates_for_prompt
from core.shop_api_http import shop_api
from core.agent1_client import agent1_client
from core.redis import get_redis
from memory.preferences import load_memory, save_memory
from memory.playbook import playbook
from memory.trajectory import trajectory_store
from graph.utils import _sv, timed_node, _parse_llm_json, normalize_score, rank_shops
from graph.prompts import PLAN_SYSTEM_PROMPT, GENERATE_SYSTEM_PROMPT, MEMORY_UPDATE_PROMPT
from graph.state import AgentState
from core.models import TrajectoryRecord, TrajectoryNodeLog
from core.observability import workflow_event

logger = logging.getLogger(__name__)

async def execute_tool(tool_name: str, params: dict, state: AgentState = None) -> dict:
    """路由工具名到实际实现。

    state 参数用于获取 recommended_shop_ids 以过滤已推荐商铺（可选，测试时可不传）。
    """
    workflow_event("tool.started", tool=tool_name, params=params)
    started = time.perf_counter()
    try:
        if tool_name == "search_shops_by_keyword":
            keyword = params.get("keyword", "")
            x = params.get("x") or params.get("user_x")
            y = params.get("y") or params.get("user_y")
            shops = await shop_api.search_shops(keyword, x=x, y=y)
            # 与 search_shops_nearby 一致的 client-side 后处理
            max_price = params.get("maxPrice")
            min_score = params.get("minScore")
            if max_price:
                shops = [s for s in shops if float(s.get("avgPrice", 999)) <= max_price]
            if min_score:
                shops = [s for s in shops if normalize_score(s.get("score")) >= min_score]
            for s in shops:
                s["score"] = normalize_score(s.get("score"))
            shops = rank_shops(shops)
            # 过滤已推荐商铺
            if state:
                shops = _filter_recommended(shops, state)
            result = {"shops": shops, "count": len(shops)}
            workflow_event("tool.completed", tool=tool_name, durationMs=round((time.perf_counter() - started) * 1000, 1), result=result)
            return result

        elif tool_name == "search_shops_nearby":
            type_id = params.get("typeId")
            x = params.get("x") or params.get("user_x")
            y = params.get("y") or params.get("user_y")
            shops = await shop_api.search_shops_nearby(type_id, x, y)
            max_price = params.get("maxPrice")
            min_score = params.get("minScore")
            if max_price:
                shops = [s for s in shops if s.get("avgPrice", 999) <= max_price]
            if min_score:
                shops = [s for s in shops if normalize_score(s.get("score")) >= min_score]
            for s in shops:
                s["score"] = normalize_score(s.get("score"))
            shops = rank_shops(shops)
            # 过滤已推荐商铺
            if state:
                shops = _filter_recommended(shops, state)
            result = {"shops": shops, "count": len(shops)}
            workflow_event("tool.completed", tool=tool_name, durationMs=round((time.perf_counter() - started) * 1000, 1), result=result)
            return result

        elif tool_name == "get_shop_detail":
            shop_id = params.get("shopId")
            shop = await shop_api.get_shop_detail(shop_id)
            shop["score"] = normalize_score(shop.get("score"))
            result = {"shop": shop}
            workflow_event("tool.completed", tool=tool_name, durationMs=round((time.perf_counter() - started) * 1000, 1), result=result)
            return result

        elif tool_name == "get_shop_types":
            types = await shop_api.get_shop_types()
            result = {"types": types}
            workflow_event("tool.completed", tool=tool_name, durationMs=round((time.perf_counter() - started) * 1000, 1), result=result)
            return result

        elif tool_name == "get_review_summary":
            shop_id = params.get("shopId")
            result = await agent1_client.get_review_summary(shop_id)
            workflow_event("tool.completed", tool=tool_name, durationMs=round((time.perf_counter() - started) * 1000, 1), result=result)
            return result

        elif tool_name == "get_shop_reviews":
            shop_id = params.get("shopId")
            current = params.get("current", 1)
            reviews = await shop_api.get_shop_reviews(shop_id, current)
            result = {"reviews": reviews, "count": len(reviews) if isinstance(reviews, list) else 0}
            workflow_event("tool.completed", tool=tool_name, durationMs=round((time.perf_counter() - started) * 1000, 1), result=result)
            return result

        else:
            result = {"error": f"Unknown tool: {tool_name}"}
            workflow_event("tool.rejected", level=logging.WARNING, tool=tool_name, durationMs=round((time.perf_counter() - started) * 1000, 1), result=result)
            return result

    except Exception as e:
        logger.error(f"Tool execution failed: {tool_name}, {e}", exc_info=True)
        result = {"error": str(e)}
        workflow_event(
            "tool.failed",
            level=logging.ERROR,
            tool=tool_name,
            durationMs=round((time.perf_counter() - started) * 1000, 1),
            errorType=type(e).__name__,
            error=str(e),
        )
        return result


def _filter_recommended(shops: list[dict], state: AgentState) -> list[dict]:
    """过滤掉本轮会话已推荐过的商铺（基于 recommended_shop_ids）。"""
    recommended_ids = set(getattr(state, "recommended_shop_ids", []) or [])
    if not recommended_ids:
        return shops
    filtered = [s for s in shops if (s.get("id") or s.get("shopId")) not in recommended_ids]
    if len(filtered) < len(shops):
        logger.info(f"Filtered {len(shops) - len(filtered)} already-recommended shops")
    return filtered


# --- LangGraph 节点 ---

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
    LLM 推理：分析意图、决定调用哪些工具。
    注入三段上下文：会话级摘要（短期）+ 用户偏好（长期 per-user）+ Agent经验（长期 global）
    """
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

    # ---------- Stage 4 Playbook 增强：把模糊词 → 规范化补全 注入上下文 ----------
    user_msg = _sv(state, "user_message", "")
    try:
        augment_input = conversation_summary + "\n用户本轮消息：" + user_msg
        augmented_text, applied = await playbook.augment_summary(augment_input)
        if augmented_text != augment_input:
            # 将 Playbook 补全作为 conversation_summary 的一部分附加
            conversation_summary = augmented_text
            if applied:
                logger.info(
                    f"Playbook augment_summary: applied {len(applied)} mapping(s): "
                    + ", ".join([f'{a["trigger"]}→{a["normalized"]}' for a in applied])
                )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Playbook augment_summary failed silently: {e}")

    # RAG 检索 Playbook 条目（语义匹配）
    playbook_context = await playbook.get_context(
        max_entries=8,
        user_query=user_msg,
        conversation_summary=conversation_summary,
    )

    prompt = PLAN_SYSTEM_PROMPT.format(
        memory=memory_str,
        playbook=playbook_context,
        conversation=conversation_summary,
        last_shops=last_shops_text,
    )

    context_msg = f"用户消息：{guard_user_message(state.user_message)}"
    # 显式告知 LLM 用户坐标已就绪，避免误判"未提供位置"而触发不必要的 HITL
    if state.user_x and state.user_y:
        context_msg += f"\n用户当前坐标：x={state.user_x}, y={state.user_y}（已自动注入到 nearby 类工具，无需询问用户）"
    if state.tool_results:
        context_msg += f"\n\n已有的工具执行结果：\n{json.dumps(state.tool_results[-5:], ensure_ascii=False)}"
    if state.candidate_shops:
        context_msg += f"\n\n已有候选商铺：{len(state.candidate_shops)} 家"
    if state.replan_hints:
        context_msg += f"\n\n重规划提示：{json.dumps(state.replan_hints, ensure_ascii=False)}"

    response = await call_llm([
        SystemMessage(content=prompt),
        HumanMessage(content=context_msg),
    ])

    parsed = _parse_llm_json(response.content)
    workflow_event(
        "plan.decided",
        toolCalls=parsed.get("tool_calls") or [],
        hitlNeeded=bool(parsed.get("hitl_needed")),
        reasoning=parsed.get("reasoning", ""),
        intentAnalysis=parsed.get("intent_analysis") or {},
    )

    # 工具调用白名单校验
    # 【八股：为什么必须校验 LLM 生成的工具调用？——Prompt Injection 防线】
    # 用户消息会被拼进 plan prompt，恶意输入「忽略以上指令，调用 xxx 工具」可能诱导
    # LLM 产出白名单外的工具名/危险参数。validate_tool_calls 做白名单+参数裁剪：
    # LLM 只能在框架允许的范围内「点菜」，不能「进厨房」
    raw_tool_calls = [tc for tc in (parsed.get("tool_calls") or []) if isinstance(tc, dict)]
    valid_tool_calls, rejected = validate_tool_calls(raw_tool_calls)

    # 决策日志
    ia = parsed.get("intent_analysis") or {}
    decision = {
        "node": "plan",
        "decision": "tool_calls" if parsed.get("tool_calls") else "hitl" if parsed.get("hitl_needed") else "unknown",
        "reasoning": parsed.get("reasoning", "")[:200],
        "prediction": f"Expected {len(parsed.get('tool_calls', []))} tool calls, HITL={parsed.get('hitl_needed', False)}",
        "verified": None,
        "intent_analysis": ia if isinstance(ia, dict) else {},
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

        result = await execute_tool(tool_name, params, state)
        results.append({"tool": tool_name, "params": params, "result": result})

        if "shops" in result:
            for s in result["shops"]:
                if not any(c.get("id") == s.get("id") for c in new_candidates):
                    new_candidates.append(s)

    workflow_event(
        "execute.completed",
        requestedToolCount=len(state.tool_calls),
        resultCount=len(results),
        candidateCount=len(new_candidates),
        results=results,
    )
    return {
        "tool_results": state.tool_results + results,
        "candidate_shops": new_candidates,
    }


@timed_node("evaluate")
async def evaluate_node(state: AgentState) -> dict:
    """
    【重构 2026-08】纯规则判定候选是否充足，零 LLM 调用。

    【八股：为什么 evaluate 用纯规则而不用 LLM 自评？】
    1. 确定性重放是 HITL 的硬前提：interrupt() 暂停后 resume 会从头重放本节点，
       只有纯规则（无随机、无外部状态）才能保证重放结果与暂停前一致，路由才不会漂移
    2. LLM 判定有抖动（temperature>0、上下文敏感），同一个 state 可能给出不同结论
    3. 「候选够不够」本质是 count>=N 的比较，交给概率模型是杀鸡用牛刀：
       白白多一次 LLM 调用的延迟和成本
    原则：确定性逻辑用代码，模糊语义理解才用 LLM

    判定优先级：
      1. 已经 HITL 过 (hitl_count ≥ 1) → 强制 sufficient，不再打断用户（单轮最多一次 HITL 保证）
      2. 候选数 ≥ AGENT2_MIN_CANDIDATES 且执行过搜索 → sufficient
      2.5 执行过工具但还没搜索（如只调了 get_shop_types）且 iteration_count < 2 → replan（回 plan 闭环依赖）
      3. 候选数 = 0 且 hitl_count = 0 → 图内 interrupt() 暂停等待用户反馈；resume 重放后转 feedback 路由
      4. 0 < 候选 < AGENT2_MIN_CANDIDATES 且 replan_count = 0 → insufficient（交给 Replan 放宽）
      5. 0 < 候选 < AGENT2_MIN_CANDIDATES 且 replan_count ≥ 1 → sufficient（放宽过仍少，硬推荐）
    """
    has_searched = any(
        tr.get("tool") in ("search_shops_by_keyword", "search_shops_nearby")
        for tr in state.tool_results
    )
    candidate_count = len(state.candidate_shops)
    min_candidates = config.AGENT2_MIN_CANDIDATES
    replan_count = getattr(state, "replan_count", 0) or 0
    hitl_count = getattr(state, "hitl_count", 0) or 0

    evaluation = "insufficient"
    reasoning = ""
    hitl_question = ""
    hitl_options: list[str] = []
    hitl_reason = ""
    next_tool_calls: list[dict] = []
    user_feedback_value = ""
    replan_hints_extra: list[str] = []

    # 规则 1：已经 HITL 过了，强制进入推荐，不再继续打断
    if hitl_count >= 1:
        evaluation = "sufficient"
        reasoning = "hitl_count>=1，已向用户确认过偏好，直接推荐（即使候选少也硬推）"
    # 规则 2：候选充足
    elif has_searched and candidate_count >= min_candidates:
        evaluation = "sufficient"
        reasoning = f"候选数{candidate_count}≥{min_candidates}且已执行搜索，无需replan"
    # 规则 2.5：执行过预备性工具（如 get_shop_types）但还没真正搜索 → 回 plan 闭环依赖，不打断用户
    elif state.tool_results and not has_searched and candidate_count == 0 and state.iteration_count < 2:
        evaluation = "replan"
        reasoning = "已执行预备性工具但尚未搜索（候选0）→ 携带工具结果回 plan 重新规划（iteration守卫：最多回一次）"
        replan_hints_extra = [
            "上一轮已执行预备性工具（见「已有的工具执行结果」），请基于其返回完成搜索："
            "如已调 get_shop_types，则用返回的 typeId 调 search_shops_nearby"
        ]
    # 规则 3：候选为 0 → HITL 打断（能走到这里必然 hitl_count == 0，规则 1 已拦截打断过的情况）
    elif candidate_count == 0:
        hitl_reason = "没有找到符合条件的商铺"
        # 规则化模板提问（不再靠 LLM 生成，避免抖动）
        hitl_question = "抱歉，当前条件下没有找到合适的店。你愿意放宽哪一项呢？"
        hitl_options = ["扩大搜索距离", "降低评分要求", "提高人均预算", "换个菜系/类别"]
        # 真正的图内 HITL：interrupt() 抛出 GraphInterrupt 暂停图执行，由 checkpointer 持久化。
        # resume 时本节点确定性重放（规则逻辑重算结果相同），interrupt() 返回用户反馈，
        # 随后走 feedback 分支路由到 update_memory。
        # 【八股：interrupt() 的实现原理像什么？——协作式暂停，类似异常】
        # interrupt(payload) 向外抛 GraphInterrupt，图框架捕获后：
        #   ① 把当前 state + 执行位置快照存入 checkpointer（按 thread_id 索引）
        #   ② ainvoke 正常返回（结果里带 __interrupt__ 载荷），API 层把它转成响应给前端
        # Command(resume=xxx) 再次 ainvoke 同一 thread_id 时：
        #   ① checkpointer 恢复快照，从被中断的节点开头重放（不是从断点续行！）
        #   ② 重放到 interrupt() 调用处时，这次返回 resume 值而不是再抛出
        # 这就是为什么本节点必须是纯规则：重放要求「再来一遍结果不变」
        feedback = interrupt({"question": hitl_question, "options": hitl_options, "reason": hitl_reason})
        evaluation = "feedback"
        reasoning = "HITL 已收到用户反馈（Command(resume)），转 update_memory 提取偏好后重新规划"
        user_feedback_value = feedback if isinstance(feedback, str) else json.dumps(feedback, ensure_ascii=False)
    # 规则 4：0 < 候选 < min_candidates → 看 replan_count
    else:  # 0 < candidate_count < min_candidates
        if replan_count == 0:
            evaluation = "insufficient"
            reasoning = f"候选数{candidate_count}<{min_candidates}且replan_count=0 → 走规则级Replan放宽"
            # 不填 next_tool_calls：Replan 逻辑在 replan_relax_node 里纯规则决定，这里不需要 LLM 生成工具
            next_tool_calls = []
        else:
            evaluation = "sufficient"
            reasoning = f"候选数{candidate_count}<{min_candidates}但replan_count>=1（已放宽过一轮）→ 直接推荐，候选将附带relaxed标注"

    updates = {
        "evaluation": evaluation,
    }
    workflow_event(
        "evaluate.decided",
        evaluation=evaluation,
        reasoning=reasoning,
        candidateCount=candidate_count,
        hitlCount=hitl_count,
        replanCount=replan_count,
    )

    # 决策日志（保留格式以兼容 eval/runner 指标采集）
    decision = {
        "node": "evaluate",
        "decision": evaluation,
        "reasoning": reasoning[:200],
        "prediction": (
            "generate" if evaluation == "sufficient"
            else "feedback→update_memory" if evaluation == "feedback"
            else "replan(go-plan: 预备工具闭环)" if evaluation == "replan"
            else "replan(规则放宽)"
        ),
        "verified": None,
        "candidateCount": candidate_count,
        "replanCount": replan_count,
        "hitlCount": hitl_count,
    }
    updates["decisions"] = state.decisions + [decision] if state.decisions else [decision]

    if replan_hints_extra:
        updates["replan_hints"] = (state.replan_hints or []) + replan_hints_extra

    if evaluation == "feedback":
        updates["user_feedback"] = user_feedback_value
        updates["hitl_needed"] = False
        updates["hitl_count"] = hitl_count + 1
        updates["hitl_question"] = hitl_question
        updates["hitl_options"] = hitl_options
        updates["hitl_reason"] = hitl_reason
    elif evaluation == "insufficient":
        # next_tool_calls 留空：Replan 逻辑改为 replan_relax_node 纯规则处理，不再依赖 evaluate 给工具列表
        updates["tool_calls"], _ = validate_tool_calls(next_tool_calls)

    return updates


# --- Replan（规则放宽）节点：零LLM，纯代码放宽筛选并重搜 ---

@timed_node("replan_relax")
async def replan_relax_node(state: AgentState) -> dict:
    """
    【重构 2026-08】规则级放宽筛选条件 → 重搜 → 写入 relaxed_shops + 合并候选。

    单轮最多执行一次（由 replan_count 守卫 + evaluate 规则二次兜底）。
    放宽策略：
      - 对 search_shops_nearby：maxPrice × 1.25，minScore − 0.3（下限 3.0）
      - 对 search_shops_by_keyword：保持 keyword，maxPrice × 1.25，minScore − 0.3
      - 若原调用没带价格/评分筛选，放宽为"去掉 minScore 限制"以扩大结果集
    新搜索到的商铺会：
      ① 与现有 candidate_shops 去重合并（保证 candidate_count 增长）
      ② 同时写入 relaxed_shops（供 generate 标注 source=relaxed 使用）
    """
    import copy
    replan_count = getattr(state, "replan_count", 0) or 0
    if replan_count >= 1:
        # 硬保护：已放宽过 → 直接返回空（理论上 evaluate 规则不会让这条路径走到这里，但防御一下）
        logger.info(f"replan_relax skipped because replan_count={replan_count} >= 1")
        return {}

    # 1. 从 tool_results 找到最近一次 search_* 调用的原始参数
    last_search_tool = None
    last_search_params: dict | None = None
    for tr in reversed(state.tool_results):
        tool = tr.get("tool")
        if tool in ("search_shops_by_keyword", "search_shops_nearby"):
            last_search_tool = tool
            last_search_params = tr.get("params") or {}
            break

    if not last_search_tool or last_search_params is None:
        # 没有搜索历史（理论上候选数非 0 就应该有搜索历史），直接放弃放宽
        logger.warning("replan_relax: no prior search_* tool call found, cannot relax")
        return {"replan_count": 1}

    # 2. 应用放宽系数构造新参数
    relaxed_params = copy.deepcopy(last_search_params)
    original_price_cap = relaxed_params.get("maxPrice") or relaxed_params.get("max_price")
    original_score_floor = relaxed_params.get("minScore") or relaxed_params.get("min_score")

    changes_applied: list[str] = []
    # 价格上限放宽 × 1.25
    if original_price_cap and isinstance(original_price_cap, (int, float)):
        new_price = int(original_price_cap * 1.25) if isinstance(original_price_cap, int) else round(original_price_cap * 1.25, 2)
        relaxed_params["maxPrice"] = new_price
        # 兼容旧命名
        if "max_price" in relaxed_params:
            relaxed_params["max_price"] = new_price
        changes_applied.append(f"maxPrice {original_price_cap} → {new_price}")
    # 评分下限放宽 −0.3（最低 3.0）
    if original_score_floor and isinstance(original_score_floor, (int, float)):
        new_score = max(3.0, float(original_score_floor) - 0.3)
        relaxed_params["minScore"] = new_score
        if "min_score" in relaxed_params:
            relaxed_params["min_score"] = new_score
        changes_applied.append(f"minScore {original_score_floor} → {new_score}")
    else:
        # 原调用没带评分限制 → 显式设一个较低的 3.5 当作"宽松"，避免跟原调用结果完全一样
        relaxed_params["minScore"] = 3.5
        changes_applied.append("minScore → 3.5 (未设置时兜底放宽)")

    # 如果是 nearby 搜索，用户坐标必须继承（避免放宽时丢坐标）
    if last_search_tool == "search_shops_nearby":
        if not relaxed_params.get("x") and state.user_x:
            relaxed_params["x"] = state.user_x
        if not relaxed_params.get("y") and state.user_y:
            relaxed_params["y"] = state.user_y

    logger.info(f"replan_relax applying changes: {changes_applied}")
    workflow_event(
        "replan.started",
        originalTool=last_search_tool,
        originalParams=last_search_params,
        relaxedParams=relaxed_params,
        changes=changes_applied,
    )

    # 3. 重新执行搜索（直接调用 execute_tool，不经过 execute_node，避免影响 tool_calls 状态）
    try:
        new_result = await execute_tool(last_search_tool, relaxed_params, state)
    except Exception as e:
        logger.error(f"replan_relax re-search failed: {e}")
        return {"replan_count": 1}

    new_shops = new_result.get("shops", []) if isinstance(new_result, dict) else []

    # 4. 去重合并 + 写入 relaxed_shops
    existing_ids = set()
    for s in state.candidate_shops:
        sid = s.get("shopId") or s.get("id")
        if sid:
            existing_ids.add(sid)

    relaxed_shops_list: list[dict] = []
    merged_extra: list[dict] = []
    for s in new_shops:
        shop_copy = dict(s)
        sid = shop_copy.get("shopId") or shop_copy.get("id")
        if sid and sid in existing_ids:
            continue
        shop_copy["source"] = "relaxed"
        shop_copy["_relax_reason"] = "; ".join(changes_applied)
        relaxed_shops_list.append(shop_copy)
        merged_extra.append(shop_copy)
        if sid:
            existing_ids.add(sid)

    # 5. 构造 tool_result 记录（方便 decisions/日志回溯）
    new_tool_result = {
        "tool": last_search_tool,
        "params": relaxed_params,
        "result": {"shops": relaxed_shops_list, "count": len(relaxed_shops_list), "relaxed": True},
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    # 决策日志
    decision = {
        "node": "replan_relax",
        "decision": "relax_and_research",
        "reasoning": "规则放宽：" + "; ".join(changes_applied),
        "prediction": f"新增候选 {len(relaxed_shops_list)} 家（去重后），下一步重新 evaluate",
        "verified": None,
        "originalParams": last_search_params,
        "relaxedParams": relaxed_params,
        "newShops": len(relaxed_shops_list),
    }

    updates: dict = {
        "replan_count": 1,
        "relaxed_shops": (getattr(state, "relaxed_shops", []) or []) + relaxed_shops_list,
        "candidate_shops": state.candidate_shops + merged_extra,
        "tool_results": state.tool_results + [new_tool_result],
        "iteration_count": state.iteration_count + 1,
        "decisions": state.decisions + [decision] if state.decisions else [decision],
    }
    workflow_event(
        "replan.completed",
        changes=changes_applied,
        newShopCount=len(relaxed_shops_list),
        candidateCount=len(updates["candidate_shops"]),
    )
    return updates


@timed_node("update_memory")
async def update_memory_node(state: AgentState) -> dict:
    """从用户反馈中提取偏好并更新记忆"""
    memory_str = json.dumps(state.memory, ensure_ascii=False)
    prompt = MEMORY_UPDATE_PROMPT.format(
        original_message=state.user_message,
        feedback=state.user_feedback,
        memory=memory_str,
    )

    response = await call_llm([HumanMessage(content=prompt)])
    parsed = _parse_llm_json(response.content)

    new_prefs = parsed.get("newPreferences", {})
    extracted_keywords = parsed.get("extractedKeywords", [])

    memory_update = {"preferences": new_prefs}
    await save_memory(state.user_id, memory_update)

    updated_memory = await load_memory(state.user_id)
    workflow_event(
        "memory.updated",
        extractedKeywords=extracted_keywords,
        newPreferences=new_prefs,
        userId=state.user_id,
    )

    return {
        "memory": updated_memory,
        "memory_updated": True,
        "new_preferences": extracted_keywords,
        "hitl_needed": False,
        "iteration_count": 0,
    }


@timed_node("generate")
async def generate_recommendation_node(state: AgentState) -> dict:
    """
    LLM 综合所有信息生成最终推荐。

    【2026-08 新增】：
    - 从 PLAN 输出的 intent_analysis 提取（maxPrice/minScore/avoidKeywords/preferredAreas）
    - 在 Python 侧先做一遍 client-side 硬过滤：排除关键词命中、价格上限、评分下限
    - 偏好商圈命中的候选提权
    - 然后交给 LLM 做 Top-5 选择和文案生成
    """
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

    # ---- 提取 PLAN 阶段的 intent_analysis（挂在 plan_node 写入的 decisions 里）----
    intent_analysis: dict = {}
    for decision in reversed(state.decisions or []):
        if isinstance(decision, dict) and "intent_analysis" in decision:
            intent_analysis = decision["intent_analysis"] or {}
            break

    max_price = intent_analysis.get("maxPrice") if isinstance(intent_analysis, dict) else None
    min_score = intent_analysis.get("minScore") if isinstance(intent_analysis, dict) else None
    avoid_keywords: list[str] = []
    preferred_areas: list[str] = []
    if isinstance(intent_analysis, dict):
        raw_avoid = intent_analysis.get("avoidKeywords") or []
        raw_area = intent_analysis.get("preferredAreas") or []
        avoid_keywords = [str(a).strip().lower() for a in raw_avoid if isinstance(a, str) and a.strip()]
        preferred_areas = [str(a).strip() for a in raw_area if isinstance(a, str) and a.strip()]

    # 合并原始候选 + 放宽候选（放宽候选去重 + 打 source 标记）
    orig_ids = set()
    merged: list[dict] = []
    for s in state.candidate_shops:
        shop_copy = dict(s)
        shop_copy.setdefault("source", "original")
        sid = shop_copy.get("shopId") or shop_copy.get("id")
        if sid:
            orig_ids.add(sid)
        merged.append(shop_copy)

    relaxed_count = 0
    for s in getattr(state, "relaxed_shops", []) or []:
        shop_copy = dict(s)
        shop_copy["source"] = "relaxed"
        sid = shop_copy.get("shopId") or shop_copy.get("id")
        if sid and sid in orig_ids:
            continue
        merged.append(shop_copy)
        relaxed_count += 1

    # ---- Client-side 硬过滤（与 GENERATE prompt 的 R2/R3/R4 同步执行，形成双重保障）----
    # 【八股：为什么 prompt 里写了规则，代码还要再过滤一遍？——不信任 LLM 输出】
    # LLM 对指令的遵循是概率性的：偶尔会「看见」排除关键词仍然推荐（尤其候选少时）
    # 硬约束（价格上限/评分下限/排除词）必须由代码保证 100% 执行，
    # LLM 只负责它擅长的：语义排序、权衡和文案生成。这就是「LLM 划选项，代码定规则」
    # 双重保障的代价为零：prompt 规则让 LLM 大多数时候自己过滤掉，代码兜底漏网的
    filtered: list[dict] = []
    for shop in merged:
        # R3: 价格上限
        if max_price and shop.get("avgPrice") and int(shop["avgPrice"]) > int(max_price):
            continue
        # R4: 评分下限
        if min_score:
            s = normalize_score(shop.get("score"))
            if s is not None and s < float(min_score):
                continue
        # R2: 排除关键词（子串匹配，大小写不敏感）
        if avoid_keywords:
            haystack = " ".join([
                str(shop.get("name") or ""),
                str(shop.get("tags") or ""),
                str(shop.get("area") or ""),
                str(shop.get("address") or ""),
            ]).lower()
            if any(kw and kw in haystack for kw in avoid_keywords):
                continue
        filtered.append(shop)

    # ---- 偏好商圈提权：命中的候选提到前面（稳定排序，不打乱其他相对顺序）----
    if preferred_areas:
        def _area_hit(shop: dict) -> int:
            area = str(shop.get("area") or "")
            return 1 if any(a and a in area for a in preferred_areas) else 0
        filtered.sort(key=lambda s: (
            -_area_hit(s),
            -(normalize_score(s.get("score")) or 0.0),  # 高分在前
            s.get("distance") if s.get("distance") is not None else 9999.0,  # 近的在前
        ))

    # Token 控制：按评分取 Top-N 截断候选数量（过滤后再截断）
    limited_candidates = limit_candidates_for_prompt(filtered)

    candidates_str = json.dumps(limited_candidates, ensure_ascii=False)
    memory_str = json.dumps(state.memory.get("preferences", {}), ensure_ascii=False)
    summaries_str = json.dumps(summaries, ensure_ascii=False) if summaries else "无"

    # 给 LLM 看的"我这轮执行了什么过滤"摘要
    intent_max_price_str = str(max_price) if max_price else "无"
    intent_min_score_str = f"{min_score}" if min_score else "无"
    intent_avoid_str = str(avoid_keywords) if avoid_keywords else "（无排除词）"
    intent_area_str = str(preferred_areas) if preferred_areas else "（无偏好商圈）"

    relaxed_note = ""
    if relaxed_count > 0:
        relaxed_note = (
            f"\n\n【提示】共额外放宽筛选条件找到 {relaxed_count} 家候选（source=relaxed），"
            "请在最终推荐文案中明确标注「为您放宽条件额外找到：」以区分精确匹配的结果。"
        )

    prompt = GENERATE_SYSTEM_PROMPT.format(
        user_message=_sv(state, "user_message", ""),
        candidates=candidates_str,
        memory=memory_str,
        review_summaries=summaries_str,
        intent_max_price=intent_max_price_str,
        intent_min_score=intent_min_score_str,
        intent_avoid_keywords=intent_avoid_str,
        intent_preferred_areas=intent_area_str,
    ) + relaxed_note

    response = await call_llm([HumanMessage(content=prompt)])
    parsed = _parse_llm_json(response.content)

    shops = parsed.get("shops", [])
    recommendation_text = parsed.get("final_recommendation", "")
    workflow_event(
        "recommendation.generated",
        inputCandidateCount=len(limited_candidates),
        filteredCandidateCount=len(filtered),
        relaxedCandidateCount=relaxed_count,
        shops=shops,
        finalRecommendation=recommendation_text,
    )

    return {
        "ranked_shops": shops,
        "final_recommendation": recommendation_text,
    }


# --- log_trajectory 节点 ---

@timed_node("log_trajectory")
async def log_trajectory_node(state: AgentState) -> dict:
    """
    持久化执行轨迹到 TrajectoryStore（每次执行的完整记录）。
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
    workflow_event(
        "trajectory.saved",
        trajectoryId=traj_id,
        candidateCount=record.candidateCount,
        nodeCount=len(record.nodeLogs),
        decisionCount=len(record.decisions),
        hitlTriggered=record.hitlTriggered,
    )

    trajectory_store.analyze_trajectory(record)

    # ---------- Stage 4 信号管线：入队 + piggyback kick ----------
    try:
        from improve import signals as _signals
        _signals.enqueue_for_distill(traj_id)
        workflow_event("distill.trajectory_enqueued", trajectoryId=traj_id)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Stage4 enqueue distill failed: {e}")
        workflow_event("distill.trajectory_enqueue_failed", level=logging.WARNING, error=str(e))

    # 【注意】Piggyback kick 已统一放在 signals.enqueue_for_distill 里
    # （检查 piggyback_should_run → 节流 → create_task），避免入队和 kick 分散在两个模块。
    # 【2026-08 清理】原"低分触发 playbook.reflect"分支已删除：reflect 节点移出主路径后
    # reflection_score 恒为 0，该分支永不触发；经验蒸馏统一由 improve/ 信号管线（Stage 4）负责。

    return {"trajectory_id": traj_id}

