"""Agent2 file logging and structured workflow events.

The normal application logger is written to ``agent2/log/agent2.log``.
Workflow events use a separate JSONL file so one request can be reconstructed
by filtering on ``requestId``, ``threadId`` or ``trajectoryId``.
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
import time
import uuid
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Iterator


_LOG_DIR = Path(os.getenv("AGENT2_LOG_DIR", Path(__file__).resolve().parents[1] / "log"))
_APP_LOG = _LOG_DIR / "agent2.log"
_WORKFLOW_LOG = _LOG_DIR / "workflow.jsonl"
_MAX_PAYLOAD_CHARS = int(os.getenv("AGENT2_LOG_MAX_PAYLOAD_CHARS", "4000"))
_FULL_PAYLOADS = os.getenv("AGENT2_LOG_FULL_PAYLOADS", "0").lower() in {"1", "true", "yes", "on"}
_CONTEXT: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "agent2_workflow_context", default={}
)
_CONFIGURED = False

_SENSITIVE_KEYS = {
    "api_key", "apikey", "authorization", "cookie", "password", "secret",
    "token", "access_token", "refresh_token",
}


def _context() -> dict[str, Any]:
    return dict(_CONTEXT.get())


def update_workflow_context(**fields: Any) -> None:
    """Add correlation fields to the current async execution context."""
    current = _context()
    current.update({key: value for key, value in fields.items() if value not in (None, "")})
    _CONTEXT.set(current)


@contextmanager
def workflow_context(**fields: Any) -> Iterator[dict[str, Any]]:
    """Bind request correlation fields for all logs in this async task."""
    current = _context()
    current.update({key: value for key, value in fields.items() if value not in (None, "")})
    token = _CONTEXT.set(current)
    try:
        yield current
    finally:
        _CONTEXT.reset(token)


def _safe_value(value: Any, depth: int = 0) -> Any:
    """Make event data JSON-safe and bound log growth by default."""
    if depth > 5:
        return "<max-depth>"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        if _FULL_PAYLOADS:
            return value
        return value if len(value) <= _MAX_PAYLOAD_CHARS else value[:_MAX_PAYLOAD_CHARS] + "...(truncated)"
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text.lower() in _SENSITIVE_KEYS:
                result[key_text] = "<redacted>"
            else:
                result[key_text] = _safe_value(item, depth + 1)
        return result
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        if not _FULL_PAYLOADS and len(items) > 100:
            items = items[:100] + [f"<truncated {len(value) - 100} items>"]
        return [_safe_value(item, depth + 1) for item in items]
    try:
        return _safe_value(value.model_dump(), depth + 1)
    except AttributeError:
        return str(value)


class _ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        context = _context()
        record.request_id = context.get("requestId", "-")
        record.thread_id = context.get("threadId", "-")
        record.trajectory_id = context.get("trajectoryId", "-")
        record.user_id = context.get("userId", "-")
        return True


class _WorkflowFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event = getattr(record, "workflow_event", "log")
        data = getattr(record, "workflow_data", {})
        item = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "timestampMs": int(time.time() * 1000),
            "level": record.levelname,
            "logger": record.name,
            "event": event,
            "context": _context(),
            "data": _safe_value(data),
        }
        return json.dumps(item, ensure_ascii=False, default=str)


def configure_logging() -> None:
    """Configure Agent2 logging once per process."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    level_name = os.getenv("AGENT2_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)
    app_handler = RotatingFileHandler(
        _APP_LOG, maxBytes=20 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    app_handler.setLevel(level)
    app_handler.addFilter(_ContextFilter())
    app_handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s "
        "[request=%(request_id)s user=%(user_id)s thread=%(thread_id)s trajectory=%(trajectory_id)s] %(message)s"
    ))
    root.addHandler(app_handler)

    workflow_logger = logging.getLogger("agent2.workflow")
    workflow_logger.setLevel(logging.INFO)
    workflow_logger.propagate = False
    workflow_handler = RotatingFileHandler(
        _WORKFLOW_LOG, maxBytes=50 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    workflow_handler.setFormatter(_WorkflowFormatter())
    workflow_logger.addHandler(workflow_handler)
    _CONFIGURED = True


def workflow_event(event: str, level: int = logging.INFO, **data: Any) -> None:
    """Write one structured event to ``workflow.jsonl`` without affecting flow."""
    try:
        configure_logging()
        logging.getLogger("agent2.workflow").log(
            level,
            event,
            extra={"workflow_event": event, "workflow_data": data},
        )
    except Exception:
        # Observability must never break a recommendation request.
        logging.getLogger(__name__).debug("workflow event write failed", exc_info=True)


def new_request_id() -> str:
    return str(uuid.uuid4())


configure_logging()
