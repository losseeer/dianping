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
# 【八股：令牌桶 vs 漏桶 vs 固定窗口计数器限流】
# - 固定窗口：临界突刺问题（窗口边界两侧瞬间 2 倍流量）
# - 滑动窗口：解决突刺，但实现稍复杂（Redis 用 ZSet 记时间戳）
# - 漏桶：恒定速率流出，绝对平滑但无法应对突发
# - 令牌桶：匀速放令牌 + 桶容量允许突发，兼顾平滑与弹性（Guava RateLimiter 同原理）
# 这里限的是对 LLM API 的请求速率（RPM），保护配额和钱包

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
        # 【八股：惰性填充（lazy refill）——为什么不需要后台定时器？】
        # 令牌数不实时更新，而是记录上次填充时间戳，acquire 时按 elapsed×rate 补算
        # 好处：零线程/零定时器开销，空闲时不消耗任何资源；时间差计算是 O(1)
        self._tokens = float(self.capacity)
        # 【八股：time.monotonic vs time.time】
        # monotonic 单调递增、不受系统时间回拨/NTP 校时影响，专用于测量时间间隔
        # time.time 是墙钟时间，回拨会导致 elapsed 为负、限流失效
        self._last_refill = time.monotonic()
        # 【八股：单线程 asyncio 里为什么还要加锁？】
        # 事件循环虽是单线程，但 await 会让出控制权——check-then-act（先读 _tokens 再减）
        # 两个协程间可能交错执行，造成超发。asyncio.Lock 是协程级互斥，挂起等待而非阻塞线程
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

# 【八股：为什么用 contextvars 而不是 threading.local？】
# asyncio 是单线程多协程并发：一个线程里同时跑着 N 个请求的协程
# threading.local 按线程隔离——同一线程里所有协程共享一份，token 统计会串号
# contextvars 按「上下文」隔离——每个 asyncio.Task 创建时拷贝一份上下文
# （contextvars.copy_context()），各协程 set/get 互不影响，是 asyncio 的事实标准
# 对应关系：ThreadLocal 之于线程 == ContextVar 之于协程
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
        # 【八股：为什么 max_retries=0 禁用 SDK 内置重试？】
        # openai client 默认自带 2 次重试。若外层 call_llm 再做 5 次指数退避重试，
        # 两层叠加最坏 5×3=15 次请求，放大对限流 API 的压力（重试风暴）
        # 正确做法：重试只在一个层面做。这里统一收口到 call_llm 手动退避，
        # 可以精确控制哪些错误可重试、退避多久、并打点日志
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
            # 【八股：哪些 HTTP 状态码可以安全重试？】
            # 可重试：429（限流，稍后可能恢复）+ 5xx（服务端临时故障/网关超时）
            # 不可重试：4xx（400 参数错、401 鉴权错、403 无权限）——重试同样的请求必然再失败，
            # 无脑重试只会浪费配额。这是重试设计的通用原则：只重试「可能自愈」的故障
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
    # 【八股：指数退避为什么要加 jitter（抖动）？】
    # 服务端限流恢复的瞬间，所有失败客户端会按同样的 1s/2s/4s 节奏同时重试（惊群效应），
    # 刚恢复的服务再次被打垮，形成同步震荡。加 0~30% 随机抖动把重试时间打散
    # AWS/Google 官方重试建议均为「指数退避 + full/equal jitter」
    # 【八股：为什么要优先遵守 Retry-After？】
    # Retry-After 是服务端明确告知的恢复时间，比客户端猜测的退避更准确；
    # 但也要设上限（cap×3=30s），防止恶意/异常的 header 让客户端长时间挂起
    if retry_after is not None:
        return min(retry_after, cap * 3)  # Retry-After 最多 30s
    exp = min(base * (2 ** (attempt - 1)), cap)
    jitter = random.uniform(0, exp * 0.3)   # 0~30% 抖动
    return exp + jitter
