"""
Layer 1: Reflect — 推荐质量自评节点

对应论文 Pattern 1 (Workflow Automation):
  "模型通过 agent runtime 分析自身执行轨迹和失败案例，据此迭代改进"

在 generate_recommendation 之后新增 reflect 节点：
  1. LLM 自评推荐质量（候选匹配度、理由充分性、多样性）
  2. 评分低于阈值 → 触发重规划（修改查询策略/放宽条件）
  3. 记录反思结果到轨迹，供 Playbook Reflector 蒸馏经验
"""

import json
import logging
import time

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from typing import Literal

from core.llm import get_llm
from config import config
from models import ReflectionResult

logger = logging.getLogger(__name__)

REFLECT_SYSTEM_PROMPT = """你是推荐质量评估器。请评估以下推荐结果的质量。

## 当前会话上下文（前面发生了什么）
{conversation}

## 用户当前请求
{user_message}

## 用户偏好记忆
{memory}

## 推荐结果
{recommendation}

评估维度（每项 0-10 分）：
1. 匹配度: 推荐结果是否匹配用户请求中的类别/价格/距离等约束（结合会话上下文理解"换一家"等指代）
2. 多样性: 推荐列表是否覆盖不同选项（而非同质化），是否重复了之前推荐过的内容
3. 理由充分性: 每个推荐的 matchReason 是否有说服力
4. 完整性: 是否遗漏了明显应该包含的选项

注意：如果用户请求涉及指代（如"换一家"、"更便宜的"），必须结合会话上下文判断：
- 用户上一轮得到了什么推荐
- 当前推荐是否真的"更换"了
- 价格/评分是否真的"更好"

请输出 JSON:
{{
  "score": 0-10 的总评分,
  "reasoning": "评估理由",
  "weaknesses": ["发现的问题1", "发现的问题2"],
  "shouldReplan": true/false,
  "replanHints": ["重规划提示1", "重规划提示2"]
}}

shouldReplan=true 当且仅当 score < {threshold} 且存在可通过重规划修复的问题。"""


async def reflect_node(state) -> dict:
    """
    LangGraph 节点: 自评推荐质量。
    
    对应论文: "模型分析自身执行轨迹和失败案例，据此迭代改进"
    通过 agent runtime（而非静态 prompt）进行自检。
    """
    from memory.user import load_memory
    from memory.conversation import get_context_summary

    llm = get_llm()
    start = time.time()

    # 获取 state 字段
    user_message = state.user_message if hasattr(state, "user_message") else state.get("user_message", "")
    thread_id = state.thread_id if hasattr(state, "thread_id") else state.get("thread_id", "")
    memory = state.memory if hasattr(state, "memory") else state.get("memory", {})
    ranked_shops = state.ranked_shops if hasattr(state, "ranked_shops") else state.get("ranked_shops", [])
    final_rec = state.final_recommendation if hasattr(state, "final_recommendation") else state.get("final_recommendation", "")
    iteration_count = state.iteration_count if hasattr(state, "iteration_count") else state.get("iteration_count", 0)

    memory_str = json.dumps(memory.get("preferences", {}), ensure_ascii=False) if memory else "{}"
    rec_str = json.dumps(ranked_shops[:5], ensure_ascii=False) if ranked_shops else final_rec[:500]

    # 获取会话上下文（多轮对话历史）
    conversation_str = "(首轮对话，无历史)"
    if thread_id:
        try:
            conversation_str = await get_context_summary(thread_id)
            # 截断防止 token 爆炸
            if len(conversation_str) > 600:
                conversation_str = conversation_str[:600] + "..."
        except Exception:
            pass

    prompt = REFLECT_SYSTEM_PROMPT.format(
        conversation=conversation_str,
        user_message=user_message,
        memory=memory_str,
        recommendation=rec_str,
        threshold=config.PLAYBOOK_REFLECTION_THRESHOLD,
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
            result = ReflectionResult(**data)
        else:
            result = ReflectionResult(score=7.0, reasoning="Failed to parse reflection", shouldReplan=False)
    except Exception as e:
        logger.error(f"Reflection failed: {e}")
        result = ReflectionResult(score=7.0, reasoning=f"Reflection error: {e}", shouldReplan=False)

    elapsed = (time.time() - start) * 1000

    updates = {
        "reflection_score": result.score,
        "reflection_notes": result.reasoning,
        "reflection_weaknesses": result.weaknesses,
    }

    # 如果评分低且未超过最大迭代次数，触发重规划
    if result.shouldReplan and iteration_count < config.AGENT2_MAX_ITERATIONS:
        updates["should_replan"] = True
        updates["replan_hints"] = result.replanHints
        updates["iteration_count"] = iteration_count + 1
        logger.info(f"Reflection triggered replan (score={result.score}, iteration={iteration_count + 1})")
    else:
        updates["should_replan"] = False

    return updates
