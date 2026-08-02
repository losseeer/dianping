"""
MySQL 直连适配器 — 替代 Java REST API，直接查询 tb_shop / tb_shop_type / tb_blog_comments

接口与 core/java_api.py 完全一致，可直接替换使用。
"""

import asyncio
from core.mysql import get_pool
import aiomysql


class MySQLApi:
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

    async def search_shops_by_name(self, keyword, page=1):
        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    "SELECT id, name, type_id as typeId, avg_price as avgPrice, "
                    "score, sold, comments, x, y, address, images "
                    "FROM tb_shop WHERE name LIKE %s LIMIT 20",
                    (f"%{keyword}%",)
                )
                rows = await cur.fetchall()
                for r in rows:
                    r["distance"] = 0.0
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
                rows = await cur.fetchall()
                for r in rows:
                    gx = r.get("x") or 0
                    gy = r.get("y") or 0
                    r["distance"] = round(((gx - x)**2 + (gy - y)**2)**0.5, 2) if x else 0
                rows.sort(key=lambda r: r.get("distance", 99))
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
                rows = await cur.fetchall()
                for r in rows:
                    r["title"] = "用户评价"
                return rows

    async def get_hot_reviews(self, current=1):
        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    "SELECT id, user_id as userId, shop_id as shopId, content, liked "
                    "FROM tb_blog_comments ORDER BY liked DESC LIMIT 10"
                )
                rows = await cur.fetchall()
                for r in rows:
                    r["title"] = "热门评价"
                return rows

    async def get_user_by_id(self, user_id):
        return {"id": user_id, "nickName": f"用户{user_id}", "icon": ""}

    async def close(self):
        pass  # 连接池由 mysql.py 管理


mysql_api = MySQLApi()
