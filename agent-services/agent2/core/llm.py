import asyncio as _asyncio
import contextvars
import logging
import os as _os
import random
import time
import uuid
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage

from core.config import config
from core.observability import workflow_event

logger = logging.getLogger(__name__)


# ========== 配置（环境变量） ==========

_LLM_MAX_CONCURRENCY: int = int(_os.getenv("LLM_MAX_CONCURRENCY", "2"))
_LLM_RPM: int = int(_os.getenv("LLM_RPM", "0"))           # 0=不限速，>0=令牌桶生效
_LLM_QUEUE_TIMEOUT: float = float(_os.getenv("LLM_QUEUE_TIMEOUT", "30"))
_LLM_MAX_RETRIES: int = int(_os.getenv("LLM_MAX_RETRIES", "5"))


# ========== 异常 ==========

class LLMBusyError(Exception):
    """排队超时或令牌桶耗尽，调用方应降级处理。"""


# ========== 令牌桶（RPM 限流） ==========

class _TokenBucket:
    """
    匀速令牌桶：按 RPM/60 的速率填充令牌，每次调用消耗 1 个。
    容量 = RPM（允许短时突发到 RPM 积攒量）。
    当 RPM=0 时退化为直通（不限速）。
    """

    def __init__(self, rpm: int):
        self.rpm = rpm
        self.capacity = max(rpm, 1)
        self.refill_rate = rpm / 60.0 if rpm > 0 else 0  # tokens/s
        self._tokens = float(self.capacity)
        self._last_refill = time.monotonic()
        self._lock = _asyncio.Lock()

    async def acquire(self, timeout: float = 30.0) -> None:
        """获取 1 个令牌，超时抛 LLMBusyError。RPM=0 时直接返回。"""
        if self.rpm <= 0:
            return

        deadline = time.monotonic() + timeout
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                # 计算还需等多久才能凑够 1 个令牌
                needed = 1.0 - self._tokens
                wait = needed / self.refill_rate

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise LLMBusyError(
                    f"令牌桶 RPM={self.rpm} 耗尽，排队 {timeout:.0f}s 超时"
                )
            await _asyncio.sleep(min(wait, remaining, 1.0))

    def _refill(self) -> None:
        """按经过时间填充令牌（调用前需持有锁）。"""
        now = time.monotonic()
        elapsed = now - self._last_refill
        if elapsed > 0 and self.refill_rate > 0:
            self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_rate)
        self._last_refill = now


# ========== 全局单例（延迟初始化） ==========

_llm_sem: _asyncio.Semaphore | None = None
_llm_bucket: _TokenBucket | None = None


def _get_sem() -> _asyncio.Semaphore:
    global _llm_sem
    if _llm_sem is None:
        _llm_sem = _asyncio.Semaphore(_LLM_MAX_CONCURRENCY)
    return _llm_sem


def _get_bucket() -> _TokenBucket:
    global _llm_bucket
    if _llm_bucket is None:
        _llm_bucket = _TokenBucket(_LLM_RPM)
    return _llm_bucket


# ========== Token 用量（contextvars 隔离） ==========

class TokenUsage:
    """单次请求的 Token 用量累加器（async 安全，通过 contextvars 隔离）"""
    def __init__(self):
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0
        self.call_count = 0

    def add(self, input_tokens: int, output_tokens: int, total_tokens: Optional[int] = None):
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_tokens += total_tokens if total_tokens is not None else (input_tokens + output_tokens)
        self.call_count += 1

    def to_dict(self) -> dict:
        return {
            "inputTokens": self.input_tokens,
            "outputTokens": self.output_tokens,
            "totalTokens": self.total_tokens,
            "llmCallCount": self.call_count,
        }

    def reset(self):
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0
        self.call_count = 0


_token_ctx: contextvars.ContextVar[TokenUsage] = contextvars.ContextVar(
    "token_usage", default=TokenUsage(),
)


def get_token_usage() -> dict:
    return _token_ctx.get().to_dict()


def reset_token_usage() -> TokenUsage:
    usage = TokenUsage()
    _token_ctx.set(usage)
    return usage


# ========== LLM 客户端 ==========

def get_llm() -> ChatOpenAI:
    thinking = _os.getenv("LLM_THINKING", "disabled")
    extra_body = {}
    if thinking == "disabled":
        extra_body["thinking"] = {"type": "disabled"}

    return ChatOpenAI(
        model=config.LLM_MODEL,
        api_key=config.LLM_API_KEY,
        base_url=config.LLM_API_BASE,
        temperature=0.3,
        max_retries=0,   # 禁用 openai client 内置重试，由 call_llm 手动退避
        timeout=120,
        extra_body=extra_body,
    )


# ========== Retry-After 解析 ==========

def _extract_retry_after(exc: Exception) -> Optional[float]:
    """从 429 异常的响应头中解析 Retry-After（秒），解析失败返回 None。"""
    try:
        resp = getattr(exc, "response", None)
        if resp is None:
            return None
        headers = getattr(resp, "headers", None) or {}
        # HTTP header: Retry-After 可为秒数或 HTTP-date
        ra = headers.get("Retry-After") or headers.get("retry-after")
        if not ra:
            return None
        try:
            return float(ra)
        except ValueError:
            # HTTP-date 格式，简单兜底：不解析，交给指数退避
            return None
    except Exception:
        return None


# ========== 统一调用入口 ==========

async def call_llm(messages: list[BaseMessage]) -> BaseMessage:
    """统一的 LLM 调用入口，自动记录 token usage 到当前上下文。

    四层防护：
      1. 令牌桶 RPM 限流（LLM_RPM>0 时生效，匀速消耗）
      2. Semaphore 并发限制（LLM_MAX_CONCURRENCY，默认 2）
      3. 指数退避 + jitter + Retry-After 重试（LLM_MAX_RETRIES，默认 5）
      4. 队列超时降级（LLM_QUEUE_TIMEOUT，默认 30s）

    用法:
        response = await call_llm([HumanMessage(content=prompt)])
    """
    from openai import RateLimitError, APIStatusError

    llm = get_llm()
    sem = _get_sem()
    bucket = _get_bucket()
    max_attempts = _LLM_MAX_RETRIES
    last_err: Exception | None = None
    response = None
    call_id = str(uuid.uuid4())
    message_payload = [
        {"type": getattr(message, "type", type(message).__name__), "content": message.content}
        for message in messages
    ]
    started = time.perf_counter()
    workflow_event(
        "llm.started",
        callId=call_id,
        model=config.LLM_MODEL,
        messageCount=len(messages),
        messages=message_payload,
    )

    for attempt in range(1, max_attempts + 1):
        # ① 令牌桶限流（RPM=0 时直通）
        try:
            await bucket.acquire(timeout=_LLM_QUEUE_TIMEOUT)
        except LLMBusyError:
            if attempt == max_attempts:
                logger.warning(f"call_llm 令牌桶耗尽，放弃 (attempt={attempt})")
                workflow_event(
                    "llm.busy",
                    level=logging.WARNING,
                    callId=call_id,
                    attempt=attempt,
                    reason="rate_limit_queue_timeout",
                )
                raise
            delay = _backoff_delay(attempt)
            logger.warning(f"call_llm 令牌桶排队超时，{delay:.1f}s 后重试 (attempt={attempt}/{max_attempts})")
            workflow_event(
                "llm.retry_scheduled",
                level=logging.WARNING,
                callId=call_id,
                attempt=attempt,
                reason="rate_limit_queue_timeout",
                delayMs=round(delay * 1000, 1),
            )
            await _asyncio.sleep(delay)
            continue

        # ② 并发信号量（带超时，避免无限排队）
        try:
            await _asyncio.wait_for(sem.acquire(), timeout=_LLM_QUEUE_TIMEOUT)
        except _asyncio.TimeoutError:
            workflow_event(
                "llm.busy",
                level=logging.WARNING,
                callId=call_id,
                attempt=attempt,
                reason="concurrency_queue_timeout",
            )
            raise LLMBusyError(
                f"并发槽位已满 (max={_LLM_MAX_CONCURRENCY})，排队 {_LLM_QUEUE_TIMEOUT:.0f}s 超时"
            )

        try:
            # ③ 实际调用
            response = await llm.ainvoke(messages)
            break

        except (RateLimitError, APIStatusError) as e:
            last_err = e
            status = getattr(e, "status_code", None)
            # 非限流/服务端错误：不重试，直接抛
            if status not in (429, 500, 502, 503, 504):
                workflow_event(
                    "llm.failed",
                    level=logging.ERROR,
                    callId=call_id,
                    attempt=attempt,
                    statusCode=status,
                    errorType=type(e).__name__,
                    error=str(e),
                )
                raise
            if attempt == max_attempts:
                logger.warning(f"call_llm 放弃重试 (attempt={attempt}, status={status}): {e}")
                workflow_event(
                    "llm.failed",
                    level=logging.ERROR,
                    callId=call_id,
                    attempt=attempt,
                    statusCode=status,
                    errorType=type(e).__name__,
                    error=str(e),
                )
                raise
            # ④ 退避：优先 Retry-After，否则指数退避 + jitter
            retry_after = _extract_retry_after(e)
            delay = _backoff_delay(attempt, retry_after=retry_after)
            logger.warning(
                f"call_llm 限流/错误 status={status}, {delay:.1f}s 后重试 "
                f"(attempt={attempt}/{max_attempts})"
                + (f" [Retry-After={retry_after}]" if retry_after else "")
            )
            workflow_event(
                "llm.retry_scheduled",
                level=logging.WARNING,
                callId=call_id,
                attempt=attempt,
                statusCode=status,
                reason="retryable_api_error",
                delayMs=round(delay * 1000, 1),
            )
            await _asyncio.sleep(delay)

        except Exception as e:
            last_err = e
            if attempt == max_attempts:
                workflow_event(
                    "llm.failed",
                    level=logging.ERROR,
                    callId=call_id,
                    attempt=attempt,
                    errorType=type(e).__name__,
                    error=str(e),
                )
                raise
            delay = _backoff_delay(attempt)
            logger.warning(f"call_llm 异常: {e}, {delay:.1f}s 后重试 (attempt={attempt}/{max_attempts})")
            workflow_event(
                "llm.retry_scheduled",
                level=logging.WARNING,
                callId=call_id,
                attempt=attempt,
                reason="unexpected_error",
                delayMs=round(delay * 1000, 1),
                errorType=type(e).__name__,
            )
            await _asyncio.sleep(delay)

        finally:
            sem.release()

    if response is None:
        raise last_err  # type: ignore[misc]

    # 提取 token usage
    try:
        usage_meta = getattr(response, "usage_metadata", None)
        if usage_meta:
            _token_ctx.get().add(
                input_tokens=usage_meta.get("input_tokens", 0),
                output_tokens=usage_meta.get("output_tokens", 0),
                total_tokens=usage_meta.get("total_tokens"),
            )
        else:
            resp_meta = getattr(response, "response_metadata", {}) or {}
            token_usage = resp_meta.get("token_usage", {})
            if token_usage:
                _token_ctx.get().add(
                    input_tokens=token_usage.get("prompt_tokens", 0),
                    output_tokens=token_usage.get("completion_tokens", 0),
                    total_tokens=token_usage.get("total_tokens"),
                )
    except Exception as e:
        logger.warning(f"Failed to extract token usage: {e}")

    workflow_event(
        "llm.completed",
        callId=call_id,
        attempt=attempt,
        durationMs=round((time.perf_counter() - started) * 1000, 1),
        tokenUsage=get_token_usage(),
        response=getattr(response, "content", ""),
    )

    return response


def _backoff_delay(attempt: int, retry_after: Optional[float] = None, base: float = 1.0, cap: float = 10.0) -> float:
    """指数退避 + jitter，优先使用 Retry-After。"""
    if retry_after is not None:
        return min(retry_after, cap * 3)  # Retry-After 最多 30s
    exp = min(base * (2 ** (attempt - 1)), cap)
    jitter = random.uniform(0, exp * 0.3)   # 0~30% 抖动
    return exp + jitter
