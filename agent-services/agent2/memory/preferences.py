"""
用户偏好记忆 — MySQL 持久化 + Redis read-through 缓存。

读取 Redis 命中→返回 | miss→查 MySQL→回填；写入 MySQL→更新 Redis。
"""

# 【八股：缓存读写模式对比——本项目两处用不同模式】
# - Cache-Aside（旁路缓存）：应用同时维护 DB 和缓存。读:miss→查DB→回填；
#   写:先写DB再删缓存。最常用，本项目 Java 侧 ShopService 用的是它（更新后删缓存）
# - Read-Through（读穿透）：读路径 miss 时由缓存层自动回源回填，应用无感知 miss（本文件）
# - Write-Through（写穿透）：写时同步写缓存+DB（本文件 save_memory 接近此模式）
# - Write-Back（写回）：写只进缓存，异步批量刷 DB——性能最高但宕机丢数据，本项目未用
import json
import logging
from datetime import datetime

from core.config import config
from core.redis import get_redis
from core.mysql_store import load_preferences, save_preferences

logger = logging.getLogger(__name__)


async def load_memory(user_id: int) -> dict:
    """
    Read-through cache: 先查 Redis → miss 查 MySQL → 回填 Redis
    """
    r = get_redis()
    key = f"{config.MEMORY_KEY_PREFIX}{user_id}:preferences"

    raw = r.get(key)
    if raw:
        return json.loads(raw)

    # Redis miss → 查 MySQL
    mysql_data = await load_preferences(user_id)
    if mysql_data:
        r.set(key, json.dumps(mysql_data, ensure_ascii=False),
              ex=config.MEMORY_EXPIRY_DAYS * 24 * 3600)
        logger.debug(f"Redis cache miss, loaded from MySQL for user {user_id}")
        return mysql_data

    # MySQL 也没有 → 返回默认空记忆
    return _default_memory(user_id)


async def save_memory(user_id: int, memory: dict) -> None:
    """
    双写: MySQL（持久化）+ Redis（更新缓存）
    先写 MySQL（source of truth），成功后再更新 Redis 缓存。
    """
    # 1. 增量合并
    existing = await load_memory(user_id)
    merged = _merge_memory(existing, memory)
    merged["lastUpdated"] = datetime.now().isoformat()
    merged["interactionCount"] = merged.get("interactionCount", 0) + 1

    # 2. 写 MySQL（source of truth）
    # 【八股：双写的顺序与降级——先 DB 后缓存】
    # 顺序：MySQL 是事实源，必须先落库。若反过来先写 Redis 再写 MySQL，
    # MySQL 失败后缓存里就是「从未存在过」的脏数据，TTL 内无法自愈
    # 降级取舍（可讲的权衡点）：MySQL 写失败时仍然更新 Redis——
    # 好处：偏好是体验增强数据而非交易数据，缓存可用比强一致更重要
    # 代价：Redis 过期前存在不一致窗口（最长 MEMORY_EXPIRY_DAYS），且重启后偏好回退
    # 若是订单/库存等强一致数据，这里必须抛异常回滚而不是吞掉
    try:
        await save_preferences(user_id, merged)
    except Exception as e:
        logger.error(f"MySQL save failed for user {user_id}: {e}")
        # MySQL 写失败不阻塞流程，Redis 仍然更新（降级策略）

    r = get_redis()
    key = f"{config.MEMORY_KEY_PREFIX}{user_id}:preferences"
    r.set(key, json.dumps(merged, ensure_ascii=False),
          ex=config.MEMORY_EXPIRY_DAYS * 24 * 3600)


def _default_memory(user_id: int) -> dict:
    return {
        "userId": user_id,
        "preferences": {
            "likedCategories": [],
            "priceRange": {"min": None, "max": None},
            "environmentPreference": [],
            "avoidFactors": [],
            "foodPreferences": [],
            "frequentAreas": [],
            "specialRequirements": None,
        },
        "lastUpdated": None,
        "interactionCount": 0,
        "version": 1,
    }


def _merge_memory(existing: dict, new_data: dict) -> dict:
    """增量合并记忆——不覆盖已有字段，追加新值

    【八股：为什么用「合并」而不是「覆盖」？——记忆的写放大与丢失更新】
    LLM 每次只提取出部分偏好（这轮提到喜欢吃辣，下轮提到不吃香菜），
    若整体覆盖，后一次会冲掉前一次学到的内容（丢失更新）。
    合并语义：列表字段取并集去重（set(old+new)），priceRange 收窄区间
    （max 取更小、min 取更大——偏好只会更精确），specialRequirements 语义不同才覆盖
    """
    prefs = existing.get("preferences", {})
    new_prefs = new_data.get("preferences", {})

    # 列表类型字段：追加而非覆盖
    list_fields = [
        "likedCategories",
        "environmentPreference",
        "avoidFactors",
        "foodPreferences",
        "frequentAreas",
    ]
    for field in list_fields:
        old_vals = prefs.get(field, [])
        new_vals = new_prefs.get(field, [])
        merged = list(set(old_vals + new_vals))
        prefs[field] = merged

    # priceRange：取更窄的范围
    old_range = prefs.get("priceRange", {})
    new_range = new_prefs.get("priceRange", {})
    if new_range.get("max") is not None:
        if old_range.get("max") is None:
            prefs["priceRange"]["max"] = new_range["max"]
        else:
            prefs["priceRange"]["max"] = min(old_range["max"], new_range["max"])
    if new_range.get("min") is not None:
        if old_range.get("min") is None:
            prefs["priceRange"]["min"] = new_range["min"]
        else:
            prefs["priceRange"]["min"] = max(old_range["min"], new_range["min"])

    # specialRequirements：新值覆盖旧值
    if new_prefs.get("specialRequirements"):
        prefs["specialRequirements"] = new_prefs["specialRequirements"]

    existing["preferences"] = prefs
    return existing
