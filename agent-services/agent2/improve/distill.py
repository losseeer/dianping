"""
蒸馏层（阶段 4）：从「已接受的轨迹」蒸馏两类经验。

设计原则：v1 全部零 LLM 调用（纯规则 + 结果反推），可解释，无并发压力。

【八股：为什么蒸馏用规则反推而不是让 LLM 总结？】
1. 成本与并发：蒸馏在后台批量跑（daemon 一次 16 条），LLM 方案每条轨迹多一次调用
   且要挤占 call_llm 的令牌桶/信号量配额，与在线请求抢资源
2. 可解释/可审计：max_distance=4.2@5shops 这样的 evidence 字符串就是学习依据，
   出错能定位；LLM 蒸馏的结论无法追溯
3. 无幻觉：「用户接受的最远店 4.2km → 学到附近≈4km」是从数据必然推出的，
   LLM 可能编造不存在的模式
4. 代价是覆盖面窄：只能学到预定义的模糊词模式（附近/便宜/高档），
   泛化能力换确定性——工程上 v1 先规则跑通，v2 再考虑 LLM 扩展

A) Playbook 蒸馏：用户模糊表达 → Agent 实际规范化参数 的映射（意图解析经验）
   - 例：用户说"附近"，最终推荐都在 ~5km 内 → 学到 trigger:"附近" → normalized:"约5km范围内"
   - 条目以 description="[fuzzy_mapping] ..." 编码，零 schema 变更
   - 相同 trigger 冲突：各自保留条目，confidence×(1+timesApplied) 打分，augment 时选高分

B) 用户偏好蒸馏：从最终推荐结果反推用户偏好增量（跨会话积累）
   - likedCategories（按 typeId 聚类型）
   - priceRange.max（仅当用户消息出现价格类模糊词时才学，避免过拟合）
   - frequentAreas（按 shop.area 字段聚）
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass
from typing import Optional

from core.models import TrajectoryRecord

logger = logging.getLogger(__name__)

# ---------- 常见模糊词 ----------
FUZZY_NEAR = ("附近", "近一点", "离得近", "周边", "周围", "不远的", "旁边")
FUZZY_CHEAP = ("便宜", "划算", "不贵", "平价", "性价比高", "实惠", "人均低")
FUZZY_EXPENSIVE = ("高档", "贵一点", "好点的", "精致的", "高端", "上档次")

# description 里的编码格式（augment 时用同一正则解析）
_MAPPING_PREFIX = "[fuzzy_mapping]"
_MAPPING_RE = re.compile(
    r'\[fuzzy_mapping\]\s+trigger:"([^"]+)"\s+normalized:"([^"]+)"(\s+evidence:[^\s]*)?'
)


@dataclass
class DistillOutcome:
    playbook_mappings: list[dict]   # [{trigger, normalized, confidence, evidence}]
    preference_patch: dict           # 直接传给 preferences.save_memory(user_id, …) 的 {"preferences":…} 结构


# ---------- A) Playbook 蒸馏 ----------

def playbook_distill(record: TrajectoryRecord) -> list[dict]:
    """从单条接受轨迹蒸馏 fuzzy_mapping 列表。空列表表示没东西可学。"""
    if not record or not record.userMessage:
        return []
    msg = record.userMessage
    shops = record.rankedShops or []
    sample = shops[:5]  # 最多用前 5 家反推，避免长尾污染
    if not sample:
        return []

    out: list[dict] = []
    n = len(sample)

    # ---- A1. 附近 → 实际距离 ----
    # 【八股：置信度与样本量挂钩——弱证据不出强结论】
    # n>=3 家店佐证给 0.7，只有 1~2 家给 0.5：样本越小，反推结论越可能是巧合
    # （只推荐了 1 家 3.9km 的店 ≠ 用户心中的"附近"就是 4km）
    # 后续相同 trigger 再蒸馏出相似条目时 confidence 会随 timesApplied 累积，
    # 相当于多次观测的贝叶斯式增强
    if any(k in msg for k in FUZZY_NEAR):
        dists = [float(s.get("distance") or 0) for s in sample if s.get("distance") is not None]
        if dists:
            max_d = max(dists)
            if max_d > 0:
                # 反推 radius：取 max(3, 向上取整到 1km)
                radius_km = max(1, int(round(max_d)))
                radius_km = max(radius_km, 3)  # 附近默认至少 3km，避免 0 距离的误判
                conf = 0.7 if n >= 3 else 0.5
                out.append({
                    "trigger": "附近",
                    "normalized": f"约{radius_km}km范围内",
                    "confidence": conf,
                    "evidence": f"max_distance={max_d:.2f}@{n}shops",
                })

    # ---- A2. 便宜/划算 → 实际人均上限 ----
    if any(k in msg for k in FUZZY_CHEAP):
        prices = [int(s.get("avgPrice") or 0) for s in sample if s.get("avgPrice")]
        if prices:
            max_p = max(prices)
            if max_p > 0:
                conf = 0.7 if n >= 3 else 0.5
                out.append({
                    "trigger": "便宜",
                    "normalized": f"人均{max_p}元以内",
                    "confidence": conf,
                    "evidence": f"max_avgPrice={max_p}@{n}shops",
                })

    # ---- A3. 高档/贵一点 → 实际人均下限 ----
    if any(k in msg for k in FUZZY_EXPENSIVE):
        prices = [int(s.get("avgPrice") or 0) for s in sample if s.get("avgPrice")]
        if prices:
            min_p = min(p for p in prices if p > 0) if any(p > 0 for p in prices) else 0
            if min_p > 0:
                conf = 0.7 if n >= 3 else 0.5
                out.append({
                    "trigger": "高档",
                    "normalized": f"人均至少{min_p}元",
                    "confidence": conf,
                    "evidence": f"min_avgPrice={min_p}@{n}shops",
                })

    return out


def encode_mapping_description(m: dict) -> str:
    """把 trigger/normalized/evidence 编码成 description 字符串（固定格式供 augment 解析）。"""
    evidence = m.get("evidence") or ""
    tail = f" evidence:{evidence}" if evidence else ""
    return f'{_MAPPING_PREFIX} trigger:"{m["trigger"]}" normalized:"{m["normalized"]}"{tail}'


def parse_mapping_description(description: str) -> Optional[dict]:
    """从 description 反解 trigger/normalized；非 fuzzy_mapping 返回 None"""
    if not description or not description.startswith(_MAPPING_PREFIX):
        return None
    m = _MAPPING_RE.search(description)
    if not m:
        return None
    return {"trigger": m.group(1), "normalized": m.group(2)}


# ---------- B) 用户偏好蒸馏 ----------

def preference_distill(record: TrajectoryRecord) -> dict:
    """
    蒸馏出用户偏好增量（结构与 preferences.save_memory 兼容的 preferences 子 dict）。
    空 dict 表示没东西可学。
    """
    if not record or record.userId <= 0:
        return {}
    shops = record.rankedShops or []
    sample = shops[:5]
    if not sample:
        return {}

    msg = record.userMessage or ""
    prefs: dict = {}

    # ---- B1. likedCategories：typeId → 名称映射（通过 shop.name 兜底，type_id 已知但缺映射表时跳过）
    # 这里先聚 typeId 的计数；真正的 name 需要 shop_api.get_shop_types()，worker 层按需传入补充
    type_ids = [s.get("typeId") for s in sample if s.get("typeId")]
    if type_ids:
        top_type, cnt = Counter(type_ids).most_common(1)[0]
        if cnt >= max(2, len(sample) // 2):  # 过半或至少 2 家
            # stage 4 v1：由于蒸馏层单独跑可能没 shop_api，这里存 raw typeId，后续若拿映射表再转
            # 作为兜底，用 "type_{id}" 作为类别名，不会干扰已有的 string likedCategories
            prefs.setdefault("likedCategories", [])
            prefs["likedCategories"].append(f"type_{top_type}")

    # ---- B2. priceRange.max：仅当用户消息出现价格类模糊词时学习（避免"随便"学出很窄的价格偏好）
    # 【八股：防过拟合——相关性不等于因果】
    # 若无条件学习，用户说「随便推荐」而结果恰好都 ≤80 元，也会学出 max=80 的窄偏好，
    # 之后推荐全被这个伪偏好过滤掉。只有用户明确表达过价格意图（便宜/预算/人均），
    # 结果价格才可信为「用户接受的上限」。样本选择性偏差是所有从结果反推偏好
    # 系统的头号陷阱（推荐系统里的反馈循环/信息茧房同源问题）
    has_price_hint = any(k in msg for k in (*FUZZY_CHEAP, *FUZZY_EXPENSIVE, "人均", "预算", "价位", "价格"))
    if has_price_hint:
        prices = [int(s.get("avgPrice") or 0) for s in sample if s.get("avgPrice")]
        if prices:
            max_p = max(prices)
            min_p = min(p for p in prices if p > 0) if any(p > 0 for p in prices) else None
            pr: dict = {}
            if max_p > 0:
                pr["max"] = max_p
            if min_p:
                pr["min"] = min_p
            if pr:
                prefs["priceRange"] = pr

    # ---- B3. frequentAreas：shop.area 字段聚
    areas = [s.get("area") for s in sample if isinstance(s.get("area"), str) and s.get("area").strip()]
    if areas:
        top_area, cnt_area = Counter(areas).most_common(1)[0]
        if cnt_area >= max(2, len(sample) // 2):
            prefs.setdefault("frequentAreas", [])
            prefs["frequentAreas"].append(top_area)

    if not prefs:
        return {}
    return {"preferences": prefs}
