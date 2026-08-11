"""Agent1 HTTP 客户端 — 封装对 Agent1 评价摘要服务的调用。

与 ShopApiHttp 同层，但职责不同：
- ShopApiHttp 调用 Java 后端 REST API 获取业务数据
- Agent1Client 调用 Agent1 FastAPI 微服务获取评价摘要

设计要点：
- 复用全局 httpx.AsyncClient（避免每次请求新建连接）
- timeout 15s（Agent1 通常不慢，超时大概率是 LLM 阻塞）
- 失败时返回空摘要而非抛异常，避免 Agent2 工作流中断
"""

import logging
from typing import Optional

import httpx

from core.config import config

logger = logging.getLogger(__name__)


class Agent1Client:
    """调用 Agent1 评价摘要服务"""

    def __init__(self):
        self._base_url = f"http://localhost:{config.AGENT1_PORT}"
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=15.0,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def get_review_summary(self, shop_id: int) -> dict:
        """获取商铺评价摘要（调用 Agent1 POST /agent1/summary）。

        失败时返回空摘要（不抛异常），保证 Agent2 工作流不被 Agent1 故障阻断。
        """
        client = await self._get_client()
        try:
            resp = await client.post("/agent1/summary", json={"shopId": shop_id})
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Agent1 get_review_summary(shopId={shop_id}) failed: {e}")
            return {
                "shopId": shop_id,
                "shopName": "",
                "totalReviews": 0,
                "positiveRate": 0,
                "recommendation": "评价摘要服务暂时不可用",
                "topPros": [],
                "topCons": [],
                "keyPhrases": [],
            }


agent1_client = Agent1Client()
