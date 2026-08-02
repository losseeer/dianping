"""
Layer 2: Playbook Manager — ACE (Agentic Context Engineering) 实现

将上下文视为 evolving playbook，而非不断增长的 prompt。

三个核心组件（对应论文 ACE 框架）：
  Generator  → Agent2 执行流程本身（已有）
  Reflector  → reflect() 从轨迹蒸馏成功/失败洞察
  Curator    → curate() 将洞察整理为结构化条目 (entryId, description)，增量合并

RAG 检索（语义相关性过滤）：
  创建/更新条目时 → embed(description) → 存入 Chroma 向量库
  Plan 阶段 → embed(用户查询 + 会话摘要) → Chroma 语义检索 Top-K → 置信度加权 → 注入 prompt
  降级策略：Embedding / Chroma 不可用时，回退到纯置信度排序

存储架构:
  MySQL: tb_agent_playbook（source of truth，断电不丢）
  Redis: agent2:playbook → 条目 JSON 缓存
  Chroma: ./chroma_data/ → 向量持久化（entryId → embedding）"""

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Optional

from config import config
from core.redis import get_redis
from core.llm import get_llm
from models import PlaybookEntry, TrajectoryRecord
from core.mysql import load_playbook_entries, save_playbook_entry, delete_playbook_entry
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

# ---- Chroma / Embedding 配置 ----
CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(__file__), "chroma_data")
CHROMA_COLLECTION = "playbook_entries"
# 使用 ChromaDB 内置 ONNX 模型，本地运行，无需 API（384维，首次自动下载 ~80MB）

REFLECT_PROMPT = """你是一个推荐系统的反思分析器。

以下是一次商户推荐执行的完整轨迹。请从中提炼**可执行的操作规则**（而不是描述失败原因）。

用户请求: {user_message}
最终推荐: {recommendation}
候选数量: {candidate_count}
HITL 触发: {hitl_triggered}
HITL 原因: {hitl_reason}
迭代次数: {iterations}
反思评分: {reflection_score}
反思备注: {reflection_notes}
用户反馈: {user_feedback}
执行结果: {outcome}

要求:
1. 每条 insight 必须是**可以被下次执行直接遵循的规则**，而不是对本次失败的描述
   - ✗ "未能将安静偏好作为筛选条件"（描述了失败）
   - ✓ "用户提及环境偏好时，将其作为关键筛选条件过滤商铺"（给出行动规则）

2. 规则应该是**跨用户通用的**操作经验，不针对特定用户
   - ✗ "这个用户偏好安静环境"（属于用户偏好记忆，不是全局经验）
   - ✓ "环境偏好应优先于价格和距离作为筛选条件"（全局操作规则）

3. category 只能是以下之一：
   - intent_parsing: 意图解析规则（如如何识别用户偏好）
   - tool_selection: 工具选择策略（如什么场景用哪个工具）
   - hitl_trigger: HITL 触发时机（如什么情况下该打断用户问偏好）
   - ranking: 排序策略（如候选排序时各种因素的权重）
   - context_gap: 上下文盲区（如哪些隐含信息需要从上下文推断）
   
   注意：没有 user_preference 类别——偏好记忆属于 per-user memory，不属于 playbook 全局经验。

每条规则格式：
{{
  "category": "intent_parsing" | "tool_selection" | "hitl_trigger" | "ranking" | "context_gap",
  "description": "一条可执行的操作规则",
  "confidence": 0.0-1.0
}}

只输出 JSON：
{{
  "insights": [
    {{"category": "...", "description": "...", "confidence": ...}}
  ]
}}"""


class PlaybookManager:
    """ACE 式演化上下文管理器（MySQL 持久化 + Redis 缓存 + Chroma 向量检索）"""

    def __init__(self):
        self.key = config.PLAYBOOK_KEY
        self.max_entries = config.PLAYBOOK_MAX_ENTRIES  # 200
        self._embedding_client = None
        self._chroma_client = None
        self._collection = None

    # ==== Chroma 客户端 ====

    def _get_chroma_collection(self):
        """懒加载 Chroma 持久化集合"""
        if self._collection is None:
            import chromadb
            os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)
            self._chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
            self._collection = self._chroma_client.get_or_create_collection(
                name=CHROMA_COLLECTION,
                embedding_function=self._get_embedding_client(),
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    # ==== Embedding（ChromaDB ONNX 内置模型，本地运行零 API 调用）====

    def _get_embedding_client(self):
        """懒加载 ONNX embedding 函数（all-MiniLM-L6-v2，384维）"""
        if self._embedding_client is None:
            from chromadb.utils import embedding_functions
            self._embedding_client = embedding_functions.ONNXMiniLM_L6_V2()
        return self._embedding_client

    async def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        """批量计算 embedding（本地模型，ONNX 返回 numpy array 转 list）"""
        if not texts:
            return []
        try:
            import asyncio
            ef = self._get_embedding_client()
            vectors = await asyncio.to_thread(ef, texts)
            # ONNX 返回 numpy array，转为 Python list
            return [v.tolist() if hasattr(v, 'tolist') else list(v) for v in vectors]
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return []

    async def _embed_one(self, text: str) -> Optional[list[float]]:
        """计算单条文本的 embedding"""
        results = await self._embed_texts([text])
        return results[0] if results else None

    # ==== 向量索引（Chroma 持久化）====

    async def _sync_vectors(self, entries: list[PlaybookEntry]) -> None:
        """增量同步向量到 Chroma：只 embed 新条目并 upsert"""
        collection = self._get_chroma_collection()
        existing_ids = set(collection.get()["ids"])

        to_embed = [(e.entryId, e.description) for e in entries if e.entryId not in existing_ids]
        if not to_embed:
            return

        ids, texts = zip(*to_embed)
        vectors = await self._embed_texts(list(texts))
        valid_ids, valid_vecs = [], []
        for entry_id, vec in zip(ids, vectors):
            if vec:
                valid_ids.append(entry_id)
                valid_vecs.append(vec)

        if valid_ids:
            import asyncio
            await asyncio.to_thread(
                collection.upsert,
                ids=valid_ids,
                embeddings=valid_vecs,
            )
            logger.debug(f"Chroma upserted {len(valid_ids)} vectors")

    async def rebuild_index(self) -> int:
        """全量重建向量索引（embedding 模型切换后调用）"""
        entries = await self.get_entries()
        if not entries:
            return 0

        collection = self._get_chroma_collection()
        # 清空重建
        import asyncio
        await asyncio.to_thread(collection.delete, where={})

        ids = [e.entryId for e in entries]
        texts = [e.description for e in entries]
        vectors = await self._embed_texts(texts)

        valid_ids, valid_vecs = [], []
        for entry_id, vec in zip(ids, vectors):
            if vec:
                valid_ids.append(entry_id)
                valid_vecs.append(vec)

        if valid_ids:
            await asyncio.to_thread(
                collection.upsert,
                ids=valid_ids,
                embeddings=valid_vecs,
            )
        logger.info(f"Chroma index rebuilt: {len(valid_ids)} entries")
        return len(valid_ids)

    # ==== 读取（read-through cache）====

    async def get_entries(self) -> list[PlaybookEntry]:
        """获取所有 playbook 条目：Redis 命中→返回 | miss→查 MySQL→回填 Redis"""
        r = get_redis()
        raw = r.get(self.key)
        if raw:
            data = json.loads(raw)
            return [PlaybookEntry(**item) for item in data]
        try:
            rows = await load_playbook_entries()
            entries = [PlaybookEntry(**row) for row in rows]
            self._cache(entries)
            return entries
        except Exception as e:
            logger.error(f"Playbook MySQL load failed: {e}")
            return []

    # ==== RAG 检索 ====

    async def get_context_rag(
        self,
        user_query: str,
        conversation_summary: str = "",
        top_k: int = 8,
    ) -> str:
        """
        RAG 检索：Chroma 语义匹配 + 置信度加权排序。

        步骤:
          1. 构造检索查询（用户消息 + 会话摘要）
          2. Embed 查询 → Chroma 向量检索 Top-K×2 候选
          3. 候选按相似度 × 置信度加权排序 → Top-K
          4. 降级：embedding / Chroma 失败时回退到纯置信度排序

        Args:
            user_query: 用户当前消息
            conversation_summary: 会话上下文摘要
            top_k: 最终注入条目数
        """
        entries = await self.get_entries()
        if not entries:
            return "(暂无历史经验)"

        # 1. 构造检索查询
        query_parts = [user_query]
        if conversation_summary and conversation_summary not in (
            "(新会话，无历史上下文)", "(暂无历史经验)"
        ):
            query_parts.append(conversation_summary[:200])
        query_text = " | ".join(query_parts)

        # 2. Embed 查询向量
        query_vec = await self._embed_one(query_text)

        # 3. Chroma 语义检索
        try:
            if query_vec is not None:
                import asyncio
                collection = self._get_chroma_collection()
                # 多取一些候选，再按置信度加权筛选
                n_candidates = min(top_k * 2, len(entries))
                results = await asyncio.to_thread(
                    collection.query,
                    query_embeddings=[query_vec],
                    n_results=n_candidates,
                    include=["distances"],
                )
                retrieved_ids = set(results["ids"][0]) if results["ids"] else set()
                distances = {
                    rid: d for rid, d in zip(results["ids"][0], results["distances"][0])
                } if results["ids"] else {}
            else:
                retrieved_ids = set()
                distances = {}
        except Exception as e:
            logger.warning(f"Chroma query failed: {e}, fallback to confidence")
            retrieved_ids = set()
            distances = {}

        # 4. 混合评分：Chroma 距离 → 相似度，结合置信度
        if retrieved_ids:
            scored = []
            for e in entries:
                if e.entryId in distances:
                    # Chroma cosine distance: 0=完全相同, 2=完全相反
                    sim = max(0.0, 1.0 - distances[e.entryId])
                    combined = sim * 0.7 + e.confidence * 0.3
                else:
                    # 未被检索到的条目，仅用低权重置信度
                    combined = e.confidence * 0.15
                    sim = 0.0
                scored.append((combined, sim, e))
            scored.sort(key=lambda x: x[0], reverse=True)
        else:
            # 降级：纯置信度排序
            logger.warning("Chroma unavailable, falling back to confidence ranking")
            scored = [(e.confidence, 0.0, e) for e in entries]
            scored.sort(key=lambda x: x[0], reverse=True)

        # 5. 取 Top-K
        selected = scored[:top_k]
        lines = []
        for combined_score, sim, e in selected:
            lines.append(f"- [{e.category}] {e.description}")
        return "\n".join(lines)

    # ==== 原有 get_context（保持兼容）====

    async def get_context(
        self,
        max_entries: int = 10,
        user_query: str = "",
        conversation_summary: str = "",
        use_rag: bool = True,
    ) -> str:
        """
        返回注入到 system prompt 的上下文文本。

        use_rag=True 且有查询文本 → Chroma 语义检索 Top-K
        否则 → 纯置信度排序（降级策略）
        """
        if use_rag and user_query:
            return await self.get_context_rag(user_query, conversation_summary, top_k=max_entries)

        entries = await self.get_entries()
        scored = sorted(
            entries,
            key=lambda e: e.confidence * (1 + e.timesApplied * 0.1),
            reverse=True,
        )
        selected = scored[:max_entries]
        if not selected:
            return "(暂无历史经验)"

        lines = []
        for e in selected:
            lines.append(f"- [{e.category}] {e.description}")
        return "\n".join(lines)

    # ---- Reflector: 从轨迹蒸馏洞察 ----

    async def reflect(self, record: TrajectoryRecord) -> list[dict]:
        """ACE Reflector: 从单条轨迹蒸馏经验洞察"""
        llm = get_llm()
        prompt = REFLECT_PROMPT.format(
            user_message=record.userMessage,
            recommendation=record.finalRecommendation[:500],
            candidate_count=record.candidateCount,
            hitl_triggered=record.hitlTriggered,
            hitl_reason=record.hitlReason or "无",
            iterations=record.iterationCount,
            reflection_score=record.reflectionScore,
            reflection_notes=record.reflectionNotes or "无",
            user_feedback=record.userFeedback or "无",
            outcome=record.outcome,
        )

        try:
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            import re
            text = response.content.strip()
            if text.startswith("```"):
                text = "\n".join(text.split("\n")[1:-1])
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                data = json.loads(match.group())
                return data.get("insights", [])
        except Exception as e:
            logger.error(f"Playbook reflection failed: {e}")
        return []

    # ---- Curator: 合并到结构化条目 ----

    async def curate(self, insights: list[dict], source: str = "reflection") -> int:
        """ACE Curator: 将洞察整理为结构化条目，增量合并到 playbook。返回新增条目数。"""
        if not insights:
            return 0

        existing = await self.get_entries()
        existing_descs = {e.description.lower().strip() for e in existing}
        now = datetime.now().isoformat()
        added = 0

        for insight in insights:
            desc = insight.get("description", "").strip()
            if not desc:
                continue

            if desc.lower().strip() in existing_descs:
                for e in existing:
                    if e.description.lower().strip() == desc.lower().strip():
                        e.confidence = min(1.0, e.confidence + 0.1)
                        break
                continue

            entry = PlaybookEntry(
                entryId=str(uuid.uuid4())[:12],
                category=insight.get("category", "context_gap"),
                description=desc,
                source=source,
                confidence=insight.get("confidence", 0.5),
                createdAt=now,
                timesApplied=0,
                timesHelpful=0,
            )
            existing.append(entry)
            existing_descs.add(desc.lower().strip())
            added += 1

        # 限制 playbook 大小
        if len(existing) > self.max_entries:
            existing.sort(key=lambda e: e.confidence, reverse=True)
            existing = existing[:self.max_entries]

        await self._save(existing)
        return added

    # ---- 应用追踪 ----

    async def record_application(self, entry_ids: list[str], helpful: bool) -> None:
        """记录 playbook 条目被应用及是否有效"""
        entries = await self.get_entries()
        for e in entries:
            if e.entryId in entry_ids:
                e.timesApplied += 1
                if helpful:
                    e.timesHelpful += 1
                if e.timesApplied > 0:
                    e.confidence = min(1.0, e.timesHelpful / e.timesApplied)
        await self._save(entries)

    # ---- 去重精炼 ----

    async def deduplicate(self) -> int:
        """定期去重精炼，防止 context collapse。返回移除的条目数。"""
        entries = await self.get_entries()
        if len(entries) <= 5:
            return 0

        seen: dict[str, PlaybookEntry] = {}
        removed = 0
        for e in entries:
            key = e.description.lower().strip()[:60]
            if key in seen:
                if e.confidence > seen[key].confidence:
                    # 删除被替换的旧条目
                    try:
                        await delete_playbook_entry(seen[key].entryId)
                    except Exception:
                        pass
                    seen[key] = e
                else:
                    try:
                        await delete_playbook_entry(e.entryId)
                    except Exception:
                        pass
                removed += 1
            else:
                seen[key] = e

        await self._save(list(seen.values()))
        return removed

    # ---- 内部方法 ----

    async def _save(self, entries: list[PlaybookEntry]) -> None:
        """双写: MySQL（持久化）+ Redis（更新缓存 + 更新向量索引）"""
        # 1. 写 MySQL（逐条 UPSERT）
        for e in entries:
            try:
                await save_playbook_entry(e.model_dump())
            except Exception as ex:
                logger.error(f"MySQL playbook save failed for entry {e.entryId}: {ex}")

        # 2. 更新 Redis 缓存
        self._cache(entries)

        # 3. 增量同步向量到 Chroma
        try:
            await self._sync_vectors(entries)
        except Exception as ex:
            logger.warning(f"Chroma sync skipped: {ex}")

    def _cache(self, entries: list[PlaybookEntry]) -> None:
        """更新 Redis 缓存"""
        r = get_redis()
        r.set(
            self.key,
            json.dumps([e.model_dump() for e in entries], ensure_ascii=False),
        )


# 全局实例
playbook = PlaybookManager()
