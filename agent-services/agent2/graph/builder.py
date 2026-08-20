"""
LangGraph 状态图构建。

【八股：为什么用状态机图而不是 while 循环 + if/else？】
1. 显式状态转移：节点+边把「执行到哪、下一步去哪」变成一等公民，可画出拓扑图审查
2. 防死循环：图里的环（plan↔evaluate）必须带守卫计数器（iteration/replan/hitl_count），
   while 循环靠人肉纪律，图框架靠路由函数约束
3. HITL 硬依赖 checkpoint：interrupt() 暂停时框架把整个 state 快照持久化到 checkpointer，
   进程都不用活着；Command(resume) 从快照点恢复继续跑。while 循环无法「暂停在某个 await
   并保存现场」——这是选 LangGraph 的决定性理由
4. 可观测：每个节点天然是打点/计时边界（timed_node 装饰器）

【重构 2026-08】新图拓扑：
  load_memory → plan → execute → evaluate → (feedback / generate / relax / replan)
    evaluate 命中 HITL 时图内 interrupt() 暂停（checkpointer 持久化线程状态），
    Command(resume=用户反馈) 恢复后 evaluate 重放 → feedback 路由：
    feedback → update_memory → plan  (提取偏好后重新规划)
    relax → replan_relax → evaluate  (规则放宽闭环，最多一轮：replan_count 守卫)
    replan → plan  (预备性工具闭环，如 get_shop_types→search：携带工具结果回 plan，最多一轮：iteration_count 守卫)
    generate → log_trajectory → END
  update_memory 仅经 feedback 路由进入（图内可达），不再由 main.py 图外直调。

Reflect 节点从主请求路径移除：不再串行等待 LLM 自评。
经验蒸馏统一走 improve/ 信号管线（Stage 4）。
Replan 改为 replan_relax 纯规则节点，不调用 LLM，单轮最多一次。

Checkpointer 说明：InMemorySaver 进程级保存（重启丢失）。
HITL 的跨重启兜底：main.py 将打断时的快照另存 Redis（hitl.py），
resume 时若 checkpointer 无该线程（服务重启过），用 Command(goto="update_memory") 从快照进图。
生产环境如需跨重启的图内恢复，可替换为 Redis/Postgres 实现的 BaseCheckpointSaver。
"""
import uuid

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, END
from graph.state import AgentState
from graph.utils import extract_hitl_interrupt
from graph.nodes import (
    load_memory_node,
    plan_node,
    execute_node,
    evaluate_node,
    update_memory_node,
    generate_recommendation_node,
    replan_relax_node,
    log_trajectory_node,
)
from graph.routing import should_hitl


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("load_memory", load_memory_node)
    graph.add_node("plan", plan_node)
    graph.add_node("execute", execute_node)
    graph.add_node("evaluate", evaluate_node)
    graph.add_node("update_memory", update_memory_node)
    graph.add_node("generate", generate_recommendation_node)
    graph.add_node("replan_relax", replan_relax_node)  # 新增：规则级放宽
    graph.add_node("log_trajectory", log_trajectory_node)

    graph.set_entry_point("load_memory")

    # 主链路
    graph.add_edge("load_memory", "plan")
    graph.add_edge("plan", "execute")
    graph.add_edge("execute", "evaluate")
    graph.add_edge("update_memory", "plan")  # feedback 路由进入：HITL 用户反馈提取偏好后重新 plan

    # evaluate → 四路分叉
    # 【八股：条件路由为什么必须是纯函数？】
    # should_hitl 只读 state 返回下一节点名，无副作用、无 IO、无随机
    # 纯函数路由保证：同一 state 永远路由到同一节点 → HITL resume 重放时
    # 图能确定性地走到同一个位置，这是中断恢复正确性的前提
    graph.add_conditional_edges(
        "evaluate",
        should_hitl,
        {
            # interrupt(resume) 后 evaluate 重放产生 → 提取偏好后重新规划
            "feedback": "update_memory",
            # 候选充足或兜底 → 生成最终推荐
            "generate": "generate",
            # 0 < 候选 < MIN_CANDIDATES 且 replan_count=0 → 规则放宽重搜，回 evaluate 二次判定
            "relax": "replan_relax",
            # 执行过预备性工具但还没搜索（候选0）→ 携带工具结果回 plan 闭环（iteration 守卫最多回一次）
            "replan": "plan",
        },
    )

    # Replan 规则放宽后 → 重新回到 evaluate 判定候选是否足够
    # （此时 replan_count 已=1，evaluate 规则会兜底 sufficient，绝无死循环）
    graph.add_edge("replan_relax", "evaluate")

    # 生成推荐 → 落盘轨迹 → 结束
    graph.add_edge("generate", "log_trajectory")
    graph.add_edge("log_trajectory", END)

    return graph


compiled_graph = build_graph().compile(checkpointer=InMemorySaver())


async def run_graph(state_dict: dict) -> dict:
    """统一图执行入口。

    1. 以 thread_id 绑定 checkpointer（interrupt() 恢复依赖线程状态）
    2. HITL 中断时把 interrupt 载荷规范化回 hitl_* 状态字段——被中断的 evaluate
       本轮写入不会提交，调用方（main/eval/tests）仍可像以前一样读 state.hitl_needed /
       hitl_question，无需感知 __interrupt__ 协议。
    """
    thread_id = state_dict.get("thread_id") or str(uuid.uuid4())
    result = await compiled_graph.ainvoke(
        state_dict, config={"configurable": {"thread_id": thread_id}}
    )
    payload = extract_hitl_interrupt(result)
    normalized = {k: v for k, v in (result or {}).items() if k != "__interrupt__"}
    if payload:
        normalized["hitl_needed"] = True
        normalized["hitl_question"] = payload.get("question", "")
        normalized["hitl_options"] = payload.get("options") or []
        normalized["hitl_reason"] = payload.get("reason", "")
        normalized["hitl_count"] = (normalized.get("hitl_count") or 0) + 1
    return normalized
