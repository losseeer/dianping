"""HITL 中断状态管理（LangGraph 工作流组件）"""

import json
from typing import Optional

from core.redis import get_redis

_HITL_KEY_PREFIX = "agent2:interrupt:"
_HITL_TTL = 3600  # 1h


def save_hitl_state(thread_id: str, state_json: str) -> None:
    """保存 HITL 中断状态到 Redis"""
    get_redis().set(f"{_HITL_KEY_PREFIX}{thread_id}", state_json, ex=_HITL_TTL)


def load_hitl_state(thread_id: str) -> Optional[dict]:
    """从 Redis 加载 HITL 中断状态"""
    raw = get_redis().get(f"{_HITL_KEY_PREFIX}{thread_id}")
    if raw:
        return json.loads(raw)
    return None


def delete_hitl_state(thread_id: str) -> None:
    """清除 HITL 中断状态"""
    get_redis().delete(f"{_HITL_KEY_PREFIX}{thread_id}")
