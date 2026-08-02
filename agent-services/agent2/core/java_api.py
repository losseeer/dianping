import httpx
import logging
from typing import Any, Optional

from config import config

logger = logging.getLogger(__name__)


class JavaApiClient:
    """调用 Java 后端 REST API 获取业务数据"""

    def __init__(self, base_url: str = config.JAVA_API_BASE_URL):
        self.base_url = base_url
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _get(self, path: str, params: dict = None) -> dict:
        client = await self._get_client()
        resp = await client.get(path, params=params)
        resp.raise_for_status()
        data = resp.json()
        # Java 后端统一返回 { success: bool, data: ..., errorMsg: ... }
        if not data.get("success", False):
            raise ValueError(f"Java API error: {data.get('errorMsg', 'unknown')}")
        return data.get("data", {})

    # ---- 商铺相关 ----

    async def get_shop_detail(self, shop_id: int) -> dict:
        return await self._get(f"/shop/{shop_id}")

    async def search_shops_by_name(self, keyword: str, page: int = 1) -> list:
        data = await self._get("/shop/of/name", {"name": keyword, "current": page})
        return data if isinstance(data, list) else []

    async def search_shops_nearby(
        self, type_id: int, x: float, y: float, current: int = 1
    ) -> list:
        data = await self._get(
            "/shop/of/type", {"typeId": type_id, "x": x, "y": y, "current": current}
        )
        return data if isinstance(data, list) else []

    async def get_shop_types(self) -> list:
        data = await self._get("/shop-type/list")
        return data if isinstance(data, list) else []

    # ---- 评价相关 ----

    async def get_shop_reviews(self, shop_id: int, current: int = 1) -> list:
        data = await self._get("/blog/of/shop", {"shopId": shop_id, "current": current})
        return data if isinstance(data, list) else []

    async def get_hot_reviews(self, current: int = 1) -> list:
        data = await self._get("/blog/hot", {"current": current})
        return data if isinstance(data, list) else []

    # ---- 用户相关 ----

    async def get_user_by_id(self, user_id: int) -> dict:
        return await self._get(f"/user/{user_id}")


# 全局实例
java_api = JavaApiClient()
