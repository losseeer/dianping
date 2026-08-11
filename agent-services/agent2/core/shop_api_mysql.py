"""
MySQL 直连适配器 — 替代 Java REST API，直接查询 tb_shop / tb_shop_type / tb_blog_comments

接口与 core/shop_api_http.py 完全一致，可直接替换使用。
"""

from core.mysql_store import get_pool
from graph.utils import rank_shops
import aiomysql


class ShopApiMysql:
    """MySQL 直接查询（绕过 Java 后端）"""

    async def get_shop_detail(self, shop_id):
        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    "SELECT id, name, type_id as typeId, avg_price as avgPrice, "
                    "score, sold, comments, x, y, address, images, open_hours as openHours "
                    "FROM tb_shop WHERE id = %s", (shop_id,)
                )
                row = await cur.fetchone()
                if row:
                    row["distance"] = 0.0
                return row or {}

    async def search_shops(self, keyword, page=1, x=None, y=None):
        """多字段 LIKE 搜索（对齐后端 ES multi_match 的 name/area/address/tags 字段）。
        tags 字段在 MySQL 侧用 area 兜底（与 ShopSearchServiceImpl.searchFallback 一致）。
        传入 x,y 时计算距离并按 评分50%+距离50% 综合排序。"""
        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    "SELECT id, name, type_id as typeId, avg_price as avgPrice, "
                    "score, sold, comments, x, y, address, images, area "
                    "FROM tb_shop WHERE name LIKE %s OR area LIKE %s OR address LIKE %s "
                    "ORDER BY score DESC, sold DESC LIMIT 20",
                    (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%")
                )
                rows = list(await cur.fetchall())
                for r in rows:
                    gx = r.get("x") or 0
                    gy = r.get("y") or 0
                    r["distance"] = round(((gx - x)**2 + (gy - y)**2)**0.5, 2) if x else 0.0
                # 有坐标时按 评分+距离 综合排序，无坐标时 rank_shops 退化为纯评分排序
                rows = rank_shops(rows)
                return rows

    async def search_shops_nearby(self, type_id, x, y, current=1):
        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    "SELECT id, name, type_id as typeId, avg_price as avgPrice, "
                    "score, sold, comments, x, y, address, images "
                    "FROM tb_shop WHERE type_id = %s "
                    "ORDER BY score DESC LIMIT 20",
                    (type_id,)
                )
                rows = list(await cur.fetchall())
                for r in rows:
                    gx = r.get("x") or 0
                    gy = r.get("y") or 0
                    r["distance"] = round(((gx - x)**2 + (gy - y)**2)**0.5, 2) if x else 0
                # 评分50% + 距离50% 综合排序（替换原来的纯距离排序）
                rows = rank_shops(rows)
                return rows

    async def get_shop_types(self):
        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT id, name, icon, sort FROM tb_shop_type ORDER BY sort")
                return await cur.fetchall()

    async def get_shop_reviews(self, shop_id, current=1):
        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    "SELECT id, user_id as userId, shop_id as shopId, content, liked "
                    "FROM tb_blog_comments WHERE shop_id = %s LIMIT 10",
                    (shop_id,)
                )
                rows = list(await cur.fetchall())
                for r in rows:
                    r["title"] = "用户评价"
                return rows

    async def close(self):
        pass  # 连接池由 mysql.py 管理


shop_api_mysql = ShopApiMysql()
