# 快评双 Agent 设计方案（Python 微服务 + Java 后端 ES 同义词）

> 本文档从「实际落地代码」视角出发，描述两个 Agent 的部署方式、API 协议、LangGraph 图结构、四层 Harness Engineering、Playbook ACE 上下文、自进化蒸馏闭环，以及配套的 Java 后端关键支撑（ES synonym_graph 写入链路、三层匿名拦截、显式反馈 outcome 重判）。
>
> 面向读者：
> - 开发者：快速定位入口文件、工具实现、蒸馏批处理频率等
> - 面试者：从中抽取「四层架构 / Context Engineering / 信号管线 / 三态熔断器」的答辩要点
> - 测试：通过 §9 API 端点与 §11 防御矩阵构造针对 P0/P1/P2 的回归用例

---

## 一、总体架构

### 1.1 部署拓扑（HTTP 协议，天然可跨机器拆分）

```
┌───────────────────┐   HTTPS (Axios, JSON)    ┌────────────────────────────────┐
│  前端 :5173 (Vue3)│ ────────────────────────▶ │  Java Spring Boot 2.3 :8081     │
│  · requiresAuth   │                           │  · 14 个业务模块               │
│  · sendMessage    │                           │  · ShopSearch: ES+synonym_graph │
│    防御 userId≤0  │                           │  · @RateLimit / @CircuitBreaker │
└────────┬──────────┘                           └───────┬────────────────────────┘
         │                                              │
         │ chat (userId, threadId, msg)                │ HTTP /search、/shop/{id}
         │                                              │ 复用 Redis 缓存 / 业务逻辑
         ▼                                              ▼
  Python FastAPI 微服务 (独立进程，可拆机器)      ┌──────────────────────┐
   ┌───────────────────────┐   Agent1 as Tool   │  Redis :6379 共享     │
   │ Agent2 推荐 ReAct :8002│ ────────────────▶ │  · 登录 Token          │
   │ · LangGraph 7 节点    │   HTTP POST summary │  · 商铺缓存 / GEO      │
   │ · 4 层 Harness        │                     │  · Agent 会话 / Playbook│
   │ · 蒸馏守护进程        │                     │  · 轨迹 / PENDING_ZSET │
   └──────────┬────────────┘                     └──────────────────────┘
              │  LLM API (OpenAI/DeepSeek 兼容)  ┌──────────────────────┐
              │  Chat Completions / Tool Calling │  MySQL :3306 共享    │
              ▼                                  │  · tb_shop / pay_log  │
     LLM Provider                                │  · Agent 4 张记忆表   │
                                                 └──────────────────────┘
  ┌───────────────────────┐
  │ Agent1 摘要 Pipeline  │  FastAPI :8001
  │ · 两步 LLM: 分析+汇总 │  /agent1/summary（30min Redis 缓存）
  └───────────────────────┘
```

### 1.2 为什么 Agent 独立成微服务（而不是嵌进 Java）

| 对比维度 | 独立 Python 微服务（本方案） | 嵌入 Java（直接 LangChain4j） |
|---|---|---|
| 模型侧接入 | FastAPI + `langchain-openai` 一行切模型，兼容 OpenAI / DeepSeek / Qwen / Ollama | 需同时兼容多模型 SDK，升级 Java 版本风险高 |
| 图编排 | LangGraph StateGraph 原生，interrupt/resume、checkpoint 完善 | LangChain4j 图能力较弱，手写状态机成本高 |
| 记忆蒸馏管线 | asyncio daemon、ChromaDB 向量、LLM 生成改进方案都是 Python 生态成熟 | Java 侧向量库 + 批处理方案较老且资料少 |
| 部署伸缩 | Agent 任务是 I/O+LLM 长耗时，可单独扩副本 / 走 GPU 节点 | Java 交易节点不希望被 LLM 请求拖长尾延迟 |
| 成本 | 跨服务 HTTP 开销 ~1~3ms，相对 LLM 调用（1~5s）可忽略 | 进程内零开销，但对整体链路提升不显著 |

因此方案采用「Java 管业务 & 数据 & 高并发；Python 管 LLM 编排 & 记忆 & 蒸馏」的经典分工。Agent1/2 从后端取数据直接走 HTTP，复用 Java 层的 Redis 缓存、GEO、限流熔断，无需重写。

---

## 二、Agent 1：评价摘要 Pipeline（:8001）

### 2.1 定位

对单个商铺的探店笔记集合做 **情感分析 + 统计聚合 + 综合建议**。线性 Pipeline，无 HITL，不需要 LLM 在每一步决定下一步做什么（确定性流程）。

### 2.2 Pipeline 五步

```
Step 1. HTTP GET /shop/{shopId} + GET /blog/of/shop?shopId=&limit=topN
         ↓ 取商铺详情 + 评价集合（评价不足 200 条时全拿；否则按 liked DESC 取 top 200 + bottom 50）
Step 2. LLM 批量情感分析
         输入 5~10 条一批（减少 API 调用次数）
         输出每条: {sentiment, pros[], cons[], keyPhrases[]}
         ↓
Step 3. 纯代码聚合（无需 LLM，性能关键）
         totalReviews = shop.comments
         positiveRate = positive / total_analyzed
         topPros / topCons = 所有 pros/cons 词频 Top3
         keyPhrases = 短语词频 Top5
         avgLikedPerReview = sum(liked) / len(reviews)
         ↓
Step 4. LLM 生成综合建议 + 评分解读
         把商铺详情 + Step 3 统计喂给 LLM
         输出: {recommendation(100字左右), scoreBreakdown(overall+interpretation)}
         ↓
Step 5. 返回 JSON → Redis 缓存 agent1:summary:{shopId} TTL=30min
```

### 2.3 API 契约

```http
POST http://127.0.0.1:8001/agent1/summary
Content-Type: application/json

{ "shopId": 5 }

 {
  "shopId": 5,
  "shopName": "海底捞火锅(水晶城购物中心店)",
  "totalReviews": 2764,
  "positiveRate": 0.87,
  "avgLikedPerReview": 156,
  "topPros": ["服务贴心周到","食材新鲜品质好","营业时间长（到凌晨7点）"],
  "topCons": ["人均价格偏高（104元）","高峰期排队时间长"],
  "keyPhrases": ["服务好","毛肚","虾滑","排队"],
  "recommendation": "综合评价较高，服务是核心优势。适合看重服务体验的用餐场景，但预算敏感者可考虑平价替代。",
  "scoreBreakdown": { "overall": 4.9, "interpretation": "4.9/5 属于顶级评分，4125 销量说明高复购率" }
}
```

**缓存策略**：`agent1:summary:{shopId}` → TTL 30 min。商铺详情/评价被编辑时，Java BlogUpdateController 联动 `DEL agent1:summary:*` 即可。

---

## 三、Agent 2：智能推荐 Agent（:8002）—— 核心篇章

### 3.1 Harness Engineering 四层架构总图（v2.0 已落地）

```
┌────────────────────────────────────────────────────────────────────┐
│  Layer 4 · Self-Improvement / 自改进蒸馏                            │
│  signals.py (入队 + piggyback + daemon) → worker.py(批处理)          │
│   → distill.py(playbook/偏好蒸馏) → memory/playbook.py + preferences│
│   · propose-evaluate-accept · outcome 重判入队 · 退化告警           │
├────────────────────────────────────────────────────────────────────┤
│  Layer 3 · Observability / AHE 三支柱                               │
│  · ComponentObs：timed_node 装饰器记录每节点耗时/LLM调用次数        │
│  · ExperienceObs：TrajectoryStore(原始→分析→洞察 分层访问)          │
│  · DecisionObs：DecisionLog(推理文本 + 预测 + 验证)                 │
├────────────────────────────────────────────────────────────────────┤
│  Layer 2 · Context Engineering (ACE 演化式上下文)                   │
│  · Playbook: Generator + Reflector + Curator 三件套                │
│    fuzzy_mapping 条目 → MySQL tb_agent_playbook + Chroma(HNSW)     │
│  · 推理消费: augment_summary 输出 [Playbook 规范化补全] 行          │
├────────────────────────────────────────────────────────────────────┤
│  Layer 1 · Workflow (LangGraph StateGraph)                         │
│  load_memory → plan → execute → evaluate → should_hitl             │
│    ├─ HITL interrupt → resume → update_memory                      │
│    ├─ generate_recommendation → log_trajectory                      │
│    └─ replan_relax (规则放宽重搜) → evaluate (兜底 sufficient)       │
├────────────────────────────────────────────────────────────────────┤
│  Base Model: ChatOpenAI (兼容 deepseek / qwen / ollama)            │
└────────────────────────────────────────────────────────────────────┘
```

> 架构灵感来源：Lilian Weng《Harness Engineering for Self-Improvement》2026-07-04 论文 + Zhang et al. 2025 ACE 上下文 + Lin et al. 2026 AHE 可观测性。本实现是这三篇的工程化聚合体。
>
> **【2026-08 重构】** 主图移除了旧的 `reflect_node / should_replan` 串行节点，evaluate 改为纯规则判定（零 LLM），replan 改为 `replan_relax_node`（规则放宽筛选重搜，单轮最多一次）。Reflect 仅在 `log_trajectory` 内部按 `reflection_score < PLAYBOOK_REFLECTION_THRESHOLD` 时离线触发 Playbook 反思，不再阻塞主请求路径。

### 3.2 Layer 1 · LangGraph 节点详解（7 个节点 + 1 条条件边）

| 节点 | 文件 | 输入/输出 | 关键动作 |
|---|---|---|---|
| **load_memory** | nodes.py | 读取 userId → 回填 state.memory + state.playbook_context + state.conversation | 1) preferences.load_memory(user_id) 从 MySQL+Redis 加载 9 维偏好；2) conversation.load_recent(userId, n=10) 近期对话摘要；3) playbook.augment_summary(user_message, memory) → Top-K 经验 + fuzzy_mapping 规范化补全行 |
| **plan** | prompts.py PLAN_SYSTEM_PROMPT + nodes.py plan_node() | LLM JSON 输出 intent_analysis + tool_calls + hitl_needed | 【强约束】遇到 `[Playbook 规范化补全]` 必须直接映射为 tool_calls.params（附近→nearby 工具；便宜→maxPrice=120）；memory.priceRange.max 自动填进 maxPrice；likedCategories 映射 keyword；frequentAreas 填 preferredAreas；avoidFactors 填 avoidKeywords |
| **execute** | nodes.py execute_node + core/shop_api_*.py | 路由 tool_calls → 各 HTTP 工具实现 | 6 个工具：`search_shops_by_keyword / search_shops_nearby / get_shop_detail / get_shop_types / get_review_summary → Agent1 / get_shop_reviews`。工具参数全部强校验（Pydantic）。工具结果按 shopId 去重合并到 candidate_shops；过滤 recommended_shop_ids 防止跨轮重复推荐 |
| **evaluate** (纯规则) | nodes.py evaluate_node | 规则判定 sufficient / insufficient / hitl_needed | **零 LLM 调用**。5 条规则：①已 HITL 过→强制 sufficient ②候选≥MIN_CANDIDATES 且已搜索→sufficient ③候选=0 且 hitl_count=0→HITL ④0<候选<MIN 且 replan_count=0→insufficient ⑤0<候选<MIN 且 replan_count≥1→sufficient 兜底。保障单轮最多一次 HITL，避免无限循环 |
| **should_hitl** (条件边) | routing.py | 分支 interrupt / generate / relax | 3 路分叉：①hitl_needed → interrupt（END，等用户反馈）②sufficient → generate ③insufficient → relax（进入规则放宽） |
| **replan_relax** (规则放宽) | nodes.py replan_relax_node | 复制上次 search_* 参数 → maxPrice×1.25 / minScore−0.3（下限 3.0）→ 重搜 → 去重合并 | **零 LLM 调用**。命中放宽标记 source="relaxed"，写入 relaxed_shops + 合并 candidate_shops；replan_count 守卫单轮最多一次；执行后回到 evaluate 二次判定（兜底 sufficient） |
| **update_memory** | nodes.py update_memory_node | HITL resume 后把用户选择 → 增量 merge memory | 调用 preferences.save_memory(userId, patch=…) 双写 MySQL+Redis，merge 策略：list 去重追加，priceRange 冲突取最新，avoidFactors 覆盖 foodPreferences |
| **generate_recommendation** | prompts.py GENERATE_SYSTEM_PROMPT + nodes.py generate_node | LLM 生成 Top-5 推荐 + 每家 matchReason | 先从 PLAN 输出的 intent_analysis 提取 maxPrice/minScore/avoidKeywords/preferredAreas，Python 侧 client-side 硬过滤 + 偏好商圈提权，再喂给 LLM Top-5 选择 + 文案生成；候选数 token 截断；relaxed 候选明确标注「为您放宽条件额外找到」 |
| **log_trajectory** | nodes.py log_trajectory_node → trajectory.py TrajectoryStore.save | 写入 state 全量节点日志 + decisionLog + 工具结果 | 保存成功后调用 `enqueue_for_distill(traj_id)` → 触发 Layer 4 自进化；若 reflection_score < 阈值，离线触发 playbook.reflect() 蒸馏失败经验 |

### 3.3 9 维偏好 JSON Schema（MySQL tb_agent_preferences）

```json
{
  "userId": 1010,
  "likedCategories": ["type_1", "type_8"],
  "foodPreferences": ["火锅", "日料", "烧烤"],
  "priceRange": { "min": null, "max": 120 },
  "environmentPreference": ["安静", "有氛围感"],
  "avoidFactors": ["排队久", "太吵", "不吃辣"],
  "frequentAreas": ["西湖区·大关", "拱墅·运河上街"],
  "specialRequirements": "需要停车位 / 适合带娃",
  "lastUpdated": "2026-08-11T22:30:00",
  "interactionCount": 14,
  "version": 3
}
```

**写入策略**（增量合并，不覆盖）：
- 数组字段：新值 append + 去重（SET 语义）
- priceRange：新 max 与旧 max 取更保守（更小），除非用户明确说「放宽预算」
- avoidFactors：与 foodPreferences 冲突 → 把冲突项从 foodPreferences 迁移进 avoidFactors
- TTL：MySQL 永不过期；Redis 30 天；lastUpdated 超 90 天 → LLM plan 时提示「偏好可能过时」

### 3.4 Playbook ACE：Generator + Reflector + Curator

| 组件 | 文件 | 作用 |
|---|---|---|
| Generator | 整个 graph 流程本身 | 每一次对话就是一次新的"经验生成" |
| Reflector (playbook.reflect) | playbook.py | 输入成功/失败轨迹 → LLM 生成 3~8 条 candidate fuzzy_mapping：(trigger, normalized, confidence, evidence) |
| Curator (playbook.curate + deduplicate) | playbook.py + `POST /agent2/playbook/deduplicate` | 与历史条目语义相似度 > 0.82 合并（取高置信度）；总条目上限 200，淘汰低置信度；对新增条目再写一条 `encoded_description` 便于后续向量检索 |

**向量侧**：ChromaDB HNSW (cosine)，每条 entry 存向量 + entryId。Plan 节点前通过 `playbook.get_context(user_message, n=8)` 做 Top-K 语义检索（混合评分 = Chroma 相似度 × 0.7 + 置信度 × 0.3），避免「只拿最高置信度的几条」导致长尾问题；Chroma 不可用时降级为纯置信度排序。

**Stage 4 fuzzy_mapping 写入路径**：`add_mapping_entries` 把 `(trigger, normalized, confidence)` 编码为 `[fuzzy_mapping] trigger:"X" normalized:"Y" evidence:Z` 字符串存到 Playbook description 字段；`augment_summary` 用正则解析，按 trigger 长度降序匹配用户消息，命中后追加 `[Playbook 规范化补全]` 行注入会话上下文。重复命中时 confidence 指数加权更新 + timesApplied+1，形成"越用越准"的演化。

---

## 四、Agent2 自进化蒸馏真闭环（Layer 4）

> 这是与「半吊子自进化」实现的核心区别。关键差异：学了必须用、反馈必须学、学了不退化、隐式显式两条轨都走同一条蒸馏管线。

### 4.1 完整数据流

```
───────────────────────── 推理侧（每轮都消费经验） ─────────────────────────
用户消息
  → load_memory_node
    → preferences.load → 9 维偏好
    → playbook.augment_summary(user_msg, memory)
       · Chroma RAG Top-K 相关条目
       · fuzzy_mapping 凑成一行 [Playbook 规范化补全] 附近→约5km / 便宜→人均≤120
    → conversation.load_recent 近期对话
  → PLAN prompt 强约束: 见到补全行必须落到 tool_calls.params; priceRange.max 自动填 maxPrice
  → execute → evaluate (纯规则) → (relax → replan_relax → evaluate)? → generate → log_trajectory

───────────────────────── 学习侧（每轮都产出经验） ─────────────────────────
log_trajectory_node 末尾:
  trajectory_store.save(TrajectoryRecord(userId, messages, tool_calls, nodeLogs, outcome=unknown))
  → signals.enqueue_for_distill(traj_id, schedule_piggyback=True)
       ↓
  ① piggyback fire-and-forget (防抖 30s，队列 ≥ 4 条或队列 oldest ≥ 30s 立即执行)
  ② daemon_loop 每 300s 兜底扫一批 (max_items=16)  ← 双保险
       ↓
  worker.pop_pending_batch → signals.detect_acceptance(traj) ← 双轨信号判定
      ├─ 显式信号: outcome=accepted（直接蒸馏，高权重）
      │            outcome=rejected（跳过蒸馏，失败模式）
      └─ 隐式信号: outcome=unknown
           · 烂轨迹跳过：reflection_score ∈ (0,4) / candidateCount=0 / HITL 触发但候选不足
           · 隐式接受：outcome=unknown 且 candidateCount>0 且（没 HITL 或 HITL 但候选≥3）
       ↓
  improve/distill.py ← 两类蒸馏解耦，互不影响
      ├─ playbook_distill(record) → fuzzy_mapping entries[]
      │     → playbook.add_mapping_entries(entries, origin_trajectory_id)
      │         → MySQL tb_agent_playbook UPSERT + Chroma add + Redis cache DEL
      └─ preference_distill(record) → 偏好 patch
            → preferences.save_memory(userId, patch, method="distill_merge")
                → SQL 增量 UPDATE + Redis HMSET
       ↓
  signals.mark_processed(traj_id, ok=True) ← 避免重复蒸馏（24h TTL）

───────────────────────── 显式反馈 → 重判入队（解决"判过一次就锁死"） ──
用户点击详情 / 点踩：前端调用
POST /agent2/trajectory/{id}/outcome?outcome=accepted&feedback=看了详情
  → trajectory_store.update_outcome(traj_id, outcome, feedback)
  → redis.delete(agent2:distill:processed:{id})     ← 清除"已处理"锁
  → enqueue_for_distill(traj_id, schedule_piggyback=True)  ← 显式信号立即重新走 detect_acceptance (高权)
```

### 4.2 信号判定规则（signals.detect_acceptance）

实际代码采用纯规则判定（零 LLM），优先级如下：

| 优先级 | 条件 | 结果 | 行为 |
|---|---|---|---|
| 1 | `outcome == "accepted"` | True | 直接蒸馏（显式接受，最高权重） |
| 2 | `outcome in {"rejected","timeout"}` | False | 跳过蒸馏 |
| 3 | `0 < reflectionScore < 4.0` | False | 烂轨迹不学 |
| 3 | `candidateCount <= 0` | False | 推荐空集不学 |
| 4 | `outcome in ("unknown", None)` 且 `candidateCount > 0` 且 (未 HITL 或 HITL 但候选 ≥ max(3, MIN)) | True | 隐式接受，蒸馏 |
| 5 | 其他 | False | 默认跳过 |

**为什么需要 outcome 重判入队**：95% 的交互在结束时刻 `outcome=unknown`，信号判定只能看隐式信号（噪声很大）。如果 3 天后用户点了查看详情或差评，没有「清除 processed marker + 重入队」的机制，这个更精准的显式信号就会被永久忽略。`POST /agent2/trajectory/{id}/outcome` 接口解决了这个半吊子链路。

---

## 五、工具列表与参数契约（Agent2 专用，已落地的 6 个）

| tool_name | 参数 | 返回 | 何时用 |
|---|---|---|---|
| **search_shops_by_keyword** | keyword: str (单品类词,不可带杭州), maxPrice:int\|null, minScore:float\|null | Shop[20] + 高亮片段 + 相关度 score | 用户提到细分类（日料/火锅/咖啡…）或具体店名；走 Java `/shop/search`（ES synonym_graph 扩展同义词 + 熔断器） |
| **search_shops_nearby** | typeId:int, x:float, y:float, maxPrice:int\|null, minScore:float\|null | Shop[20] + 距离 | 用户强调附近 / 商圈泛化；先 `get_shop_types` 拿 typeId；走 Java `/shop/of/type` 再结合 Redis GEO；maxPrice/minScore 客户端侧后过滤 |
| **get_shop_detail** | shopId:int | 商铺详情 full dto | 在 candidate top-5 中对 1~2 家补全营业时间/地址/图片，不要全量调（避免 LLM timeout） |
| **get_shop_types** | — | {id, name} 列表 | 用户说"火锅/唱歌/按摩"不知道 typeId 时先调；**细分一律走 keyword 工具，别硬塞 typeId** |
| **get_review_summary** | shopId:int | Agent1 summary JSON（见 §2.3） | Top-1/2 候选在生成推荐前做好评度验证；不要全量调（减少 80% Agent1 调用） |
| **get_shop_reviews** | shopId:int, limit:int=20 | Blog[20] 文本 + liked | Agent1 API 失败/摘要为空时的降级手段 |

### 5.1 Keyword 全局规则（强约束）

所有 keyword 参数必须是「单个核心品类词」，禁止带杭州、禁止带句子。示例：

| 用户说法 | 正确 keyword | 错误 keyword |
|---|---|---|
| 推荐杭州好吃的日料店 | 日料 | 杭州好吃的日料店 / 推荐日料 |
| 来几家萧山区的寿司吧 | 寿司 | 萧山区寿司 |
| 便宜点的川湘菜 | 川菜 / 湘菜 | 便宜的川菜（"便宜"→走 maxPrice 参数） |

同义词扩展交给 ES synonym_graph：keyword=寿司 → shop_search_synonym 扩展成 寿司/日料/日式/和食/刺身/居酒屋 → 召回自动覆盖全部同义家族 → 不需要 LLM 在 prompt 里手工列。

### 5.2 Follow-up 标准动作（系统已自动过滤 seen_shop_ids，无需 LLM 手动排除）

| 用户说法 | 动作 |
|---|---|
| 换一家 / 再来几家 / 换几家 | 同工具同参数即可，seen_shop_ids 自动剔除已推荐 |
| 更便宜点 / 人均再低点 | maxPrice = 上一轮最高均价 × 0.7（或 memory.priceRange.max 取保守者） |
| 更近点 / 近一点 | 保持参数重搜（结果本身按距离 + 评分综合排序） |
| 不要 X / 不吃辣 / 不要火锅 | avoidKeywords.append(X)；搜索参数不变；GENERATE 硬性过滤 |
| 换个商圈 / 西湖区的有没有 | preferredAreas.append；搜索参数不变；GENERATE 优先排序 |

---

## 六、Java 后端 ES 同义词写入链路（与 Agent 强相关）

### 6.1 为什么这是 Agent 设计文档的一部分

Agent2 工具 `search_shops_by_keyword` 的召回质量 100% 取决于 Java 侧 ES 是否真的把同义词 filter 写进去了。**这是 P0 级断口：只写了 ElasticsearchConfiguration 类，但没有触发索引重建的话 synonym_graph 永远在 settings 里缺位，用户搜"寿司"召不回"日料店"，Agent 表现就是查不到。**

### 6.2 链路全景

```
classpath:synonyms.txt（14 组同义词）
 日料,日本料理,日式,和食,寿司,刺身,居酒屋
 火锅,铜锅,涮锅,串串香,麻辣烫,冒菜
 烧烤,烤肉,烤串,撸串,炭火烧肉
 川菜,川味,川湘菜,辣味
 粤菜,粤式,茶餐厅,港式
 咖啡,咖啡店,咖啡馆,Cafe
 奶茶,茶饮,饮品,果茶
 酒吧,酒馆,清吧,鸡尾酒吧
 KTV,卡拉OK,唱歌,练歌房
 SPA,水疗,按摩,养生馆
 美甲,美睫,美甲店,美甲沙龙
 亲子,儿童乐园,亲子游乐
 健身,健身房,运动健身
 海鲜,海味,海鲜大排档,海鲜餐厅
      ↓ ElasticsearchConfiguration.loadSynonyms() ClassPathResource 逐行清洗去空
      ↓ buildIndexSettings()
settings.analysis.filter.shop_synonyms.type     = synonym_graph     # 保留短语级位置偏移，精度优于普通 synonym
              filter.shop_synonyms.expand   = true
              filter.shop_synonyms.synonyms = synLines (上面 14 行)
       analyzer.shop_index_ik    = ik_max_word + lowercase         ← 建索引：最细粒度拆分，召回最大化
       analyzer.shop_search_synonym = ik_smart + lowercase + shop_synonyms ← 搜索：最准粒度 + 同义词扩展召回
      ↓ rebuildIndexInternal(force=true)
  DROP shop（存在就删）
  CREATE shop(settings=上面)
  PUT MAPPING:
    name/area/address/tags 四字段 → analyzer=shop_index_ik, search_analyzer=shop_search_synonym
    (IK 细粒度建索引 → 文档被拆成更多 token → 召回面广；搜索粗粒度→查询词少歧义→同义词扩展更准)
  ← importAllShops() tb_shop → ES ShopDoc 导入
      ↓
  两种触发方式（保证 filter 真的写入 ES 而不是 settings 缺位）：
  A. application.yaml elasticsearch.init.rebuild-on-startup=true
      → Spring Boot 启动时 ApplicationRunner.run() 自动执行 rebuildIndexInternal(rebuildOnStartup)
      → 【至少在首次部署 / 修改 synonyms.txt 后设置一次】之后可改回 false 避免每次重启都重导
  B. POST /shop/search/rebuild-index 管理接口 (ShopSearchController)
      → 线上服务运行期间随时可调用，零停服重建 + 重导
      → 用于：修改 synonyms.txt、新增 analyzer 配置、修正 mapping 后一键修复
      ↓
  ES _analyze 验证（必须跑一次，确认同义词被扩展）：
  POST /shop/_analyze {"analyzer":"shop_search_synonym","text":"寿司"}
  → tokens 至少包含：寿司 / 日料 / 日式 / 刺身 / 居酒屋
```

### 6.3 与 @CircuitBreaker 的高可用组合

- 常态：`GET /shop/search` → ShopSearchServiceImpl.search → ElasticsearchRestTemplate multiMatchQuery（4 字段 + 高亮 + BM25 评分）→ 返回。
- ES 宕机或连续 5 次失败：`@CircuitBreaker` 从 CLOSED → OPEN 30s。期间所有 search 调 `searchFallback()`：`tb_shop WHERE name LIKE %kw% OR area LIKE %kw% OR address LIKE %kw% OR tags LIKE %kw%` + 评分倒排。
- 30s 后 HALF_OPEN 放行 3 条探针：全部成功 → CLOSED；任一失败 → 再 OPEN。
- 对 Agent2 来说：**这一切是透明的**，Java 接口返回格式一致，Agent 不需要知道底层用的是 ES 还是 MySQL。

---

## 七、HITL 断点 / Resume 协议

### 7.1 HITL 触发场景（对应 §3.2 evaluate 规则 3）

| 触发场景 | 向用户提问（hitl_question） | hitl_options |
|---|---|---|
| 候选数 = 0 且 hitl_count = 0 | 「抱歉，当前条件下没有找到合适的店。你愿意放宽哪一项呢？」 | ["扩大搜索距离","降低评分要求","提高人均预算","换个菜系/类别"] |
| evaluate 判定意图 vague（基于规则） | （规则化模板，不再依赖 LLM 生成，避免抖动） | — |

**单轮最多一次 HITL**：`hitl_count >= 1` 后再走 evaluate 强制 sufficient，避免反复打断用户。

### 7.2 Resume 协议

```http
POST /agent2/chat         → 第一次请求，若命中 HITL，响应 type=interrupt, threadId=xxx
POST /agent2/chat/resume  → Body: { userId, threadId, response: "<用户选的选项文本>" }
```

- threadId 是 LangGraph 的 `config.configurable.thread_id`，配合 HITL state 序列化到 Redis，节点状态不用自行持久化。
- 前端在用户从「推荐列表 → 查看详情 → 返回列表」整个会话生命周期里 threadId 保持不变；开新一轮对话时重新生成。

---

## 八、三层匿名请求防御（userId ≤ 0 的 P0 防护矩阵）

> 问题根因：未登录前端默认 userId=0，如果不拦截会把匿名用户的偏好都写到 `user_id=0` 上，多用户共享同一条记忆，互相污染。

| 防御层 | 位置 | 拦截逻辑 | 失败时行为 |
|---|---|---|---|
| L1 前端路由守卫 | `dianping-frontend/src/router/index.ts` | `/agent` 路由设置 `meta.requiresAuth=true`。导航时校验 Pinia userStore 是否有 token + userId>0，否则 `router.push('/login')` | 用户点击「AI 推荐」tab 直接被重定向到登录页 |
| L2 前端 sendMessage 防御 | AgentChat.vue `handleSend()` | 发送前 `if (userId<=0) { ElMessage.warning('请先登录后再使用 AI 推荐'); return }` 并阻止请求 | 绕过路由守卫（直接改 URL hash）或 Pinia 失效时仍能拦截 |
| L3 后端 Pydantic + handler 防御 | `agent2/core/models.py` ChatRequest/ResumeRequest `userId: int = Field(gt=0)` + `main.py` chat/ resume handler 再次 `if userId <= 0 return 400` | 直接 curl `curl -d '{"userId":0,…}' :8002/agent2/chat` 也会被结构化返回错误"userId 必须大于 0" |

**脏数据清理（一次性）**：
```sql
DELETE FROM tb_agent_conversations  WHERE user_id = 0;
DELETE FROM tb_agent_preferences    WHERE user_id = 0;
DELETE FROM tb_agent_playbook       WHERE user_id = 0;
DELETE FROM tb_agent_trajectories   WHERE user_id = 0;
```
```bash
redis-cli --scan --pattern "user:0:*"       | xargs redis-cli DEL
redis-cli --scan --pattern "agent2:*:0*"    | xargs redis-cli DEL
```

---

## 九、API 端点总览

### 9.1 Agent2 全部端点（FastAPI `/agent2/*` 挂载）

| 方法 | 路径 | 层 | 关键作用 |
|---|---|---|---|
| POST | `/chat` | L1 | 推荐对话入口（含 ThreadLocal 级限流 3 req/min/user，防刷） |
| POST | `/chat/resume` | L1 | HITL 恢复对话 |
| GET  | `/memory/{userId}` | L2 | 读用户 9 维偏好（读 Redis 空则读 MySQL + 回填） |
| POST | `/memory/{userId}` | L2 | 写偏好 patch（增量 merge） |
| GET  | `/playbook` | L2 | 读 Playbook 当前条目（fuzzy_mapping 列表 + 置信度 top 20） |
| POST | `/playbook/deduplicate` | L2 | 手工触发 Curator 去重 + 语义合并 + 淘汰低置信度 |
| POST | `/playbook/rebuild-index` | L2 | 全量重建 Chroma 向量索引（embedding 模型切换后调用） |
| GET  | `/trajectory/{id}` | L3 | 单条轨迹原始 + analysis + insights 三层可观测 |
| GET  | `/trajectory/user/{userId}` | L3 | 用户维度轨迹列表（按时间 ZSet） |
| GET  | `/insights` | L3 | 全量聚合洞察（近 50 条失败模式 topN） |
| **POST** | **`/trajectory/{id}/outcome`** | **L4** | **显式反馈 accepted/rejected + 清除 processed marker + 重新入队蒸馏（§4.1 重判入队）** |
| GET  | `/eval/cases` | Eval | 默认 8 条测试用例（food/budget/preference/vague/typo…） |
| POST | `/eval/run` | Eval | 跑一遍基准，落 DB，返回 runId |
| GET  | `/eval/results` | Eval | 历史基准列表 |
| GET  | `/eval/{runId}` | Eval | 单次基准详情（逐用例分数 + 退化告警） |
| GET  | `/eval/compare?before=&after=` | Eval | before/after 对比表 + 改进/退化统计 + 最终 PASS/FAIL 判定 |
| GET  | `/health` | 运维 | 生产健康检查（必保留） |

### 9.2 Agent1 端点 + Java ShopSearch 管理接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `:8001/agent1/summary` | Agent1 评价摘要（30min 缓存） |
| GET  | `:8081/shop/search` | ES 全文搜索（synonym_graph + IK 双 analyzer + 熔断器） |
| **POST** | **`:8081/shop/search/rebuild-index`** | **同义词热更新——强制 DROP→CREATE→PUT MAPPING→IMPORT，不需要重启 Java（§6.2 方式 B）** |
| POST | `:8081/shop/search/sync` | 全量 tb_shop → ES 导入 |
| POST | `:8081/shop/search/import` | 单条商铺导入 ES |

---

## 十、目录结构（实际落地代码，与设计一致）

```
agent-services/
├── requirements.txt
├── start.sh
├── agent1/                                  # 评价摘要 Pipeline
│   ├── main.py                              # FastAPI 入口（summary 接口 + 缓存）
│   ├── config.py / llm.py / models.py
│   ├── java_api_client.py                   # HTTP 调 Java /shop + /blog/of/shop
│   └── redis_client.py
└── agent2/                                  # 推荐 Agent + 四层 Harness
    ├── main.py                              # FastAPI：chat/resume/memory/playbook/trajectory/
    │                                        #            eval/outcome重判入队 + startup daemon
    ├── core/                                # 基础设施
    │   ├── config.py                        # 配置（trajectory TTL/playbook cap/daemon 300s 等）
    │   ├── models.py                        # Pydantic + Field(gt=0) 守卫
    │   ├── guard.py                         # 注入防护 + TokenBudget（单轮预算）
    │   ├── llm.py                           # LLM 客户端（重试/超时/兼容多家）
    │   ├── redis.py / mysql_store.py        # Redis / aiomysql 连接
    │   ├── shop_api_http.py / shop_api_mysql.py  # execute 工具的实际取数实现
    │   └── agent1_client.py                 # execute 工具调用 Agent1 的 summary 封装
    ├── graph/                               # Layer 1 Workflow
    │   ├── builder.py                       # build_graph 边 + interrupt_before
    │   ├── state.py                         # AgentState TypedDict
    │   ├── prompts.py                       # PLAN_SYSTEM_PROMPT(带 Playbook 硬约束) / GENERATE_*
    │   ├── nodes.py                         # 7 个节点实现（含 replan_relax 纯规则）
    │   ├── routing.py                       # should_hitl 条件边
    │   ├── hitl.py                          # HITL 中断状态序列化（save/load/delete）
    │   ├── reflect.py                       # reflect 评分 Prompt（离线触发）
    │   └── utils.py                         # timed_node / safe_json_parse / rank_shops
    ├── memory/                              # Layer 2 Context + 持久化
    │   ├── conversation.py                  # 对话上下文（加载近期 + 回写）
    │   ├── preferences.py                   # 9 维用户偏好（MySQL+Redis 双写 + 增量合并）
    │   ├── trajectory.py                    # Layer 3 TrajectoryStore.save/update_outcome/get_user
    │   └── playbook.py                      # Playbook：Generator/Reflector/Curator + Chroma RAG
    ├── improve/                             # Layer 4 Self-Improvement
    │   ├── signals.py                       # enqueue_for_distill / piggyback / daemon_loop /
    │                                        # detect_acceptance / mark_processed / clear_processed
    │   ├── worker.py                        # process_pending_batch(playbook+偏好蒸馏) / retry
    │   └── distill.py                       # playbook_distill / preference_distill
    ├── eval/                                # 评测框架
    │   ├── runner.py                        # run_single_case / compare
    │   └── run_all_experiments.py           # 一键跑 before-after + 输出退化报告
    └── tests/test_e2e.py                    # 端到端冒烟（关键接口各 1 条）
```

---

## 十一、防御矩阵速查（面试 / 测试必备）

| 风险点 | 防御手段 | 位置 |
|---|---|---|
| userId=0 匿名记忆污染 | 三层防线（路由→sendMessage→Pydantic+handler）+ 一次性脏数据清理 | §8 |
| ES 同义词不生效 | rebuild-on-startup=true + rebuild-index 管理接口 + _analyze 手工验证 | §6.2 |
| ES 宕机搜不到 | @CircuitBreaker fallback MySQL LIKE 4 字段兜底 | §6.3 |
| 秒杀超卖 | Lua 原子预检 + Redisson WatchDog 锁 + RabbitMQ 异步落库 | README §3 |
| 订单抢了不支付占坑 | 死信队列 TTL 30min + 超时自动取消并回库 | README §3 |
| LLM 规划忽略 Playbook 经验 | PLAN prompt 硬约束 + reasoning 字段要求说明注入 | §3.2 plan 节点 |
| 显式 outcome 反馈不学习 | outcome 更新后清除 processed marker + 重入队 + piggyback kick | §4.2 |
| LLM 推理无限循环 | replan_count 守卫单轮最多一次 + hitl_count 强制 sufficient | §3.2 evaluate 节点 |
| prompt token 爆炸 | Playbook ACE（结构化条目上限 200）替代无限追加历史对话；recent conversation top 10；candidates 按 score Top-N 截断 | §3.4 |
| LLM 工具参数越界 | guard.validate_tool_calls 白名单校验 + Pydantic 强类型 + 关键词禁带地名 | §5.1 |

---

## 十二、未来扩展点（预留，不是 TODO）

1. Agent1 对比模式：两个 shopId → 生成对比建议（哪家更适合约会、哪家更适合商务）
2. Agent2 「今天去哪里」探索模式：无明确需求时，按记忆 + 商圈热度自动生成每日推荐卡片
3. 偏好语义嵌入：用户模糊偏好（喜欢有氛围感的）embedding 存储，后续 query 用向量相似度匹配 Playbook 条目而不是只靠 keyword
4. 多模态：Agent2 生成推荐时，直接展示每家店的实拍图（从 tb_shop.images 拉）+ 推荐理由卡片，而不是纯文本
5. 蒸馏日志可回放：每一条 playbook entry 记录 origin_trajectory_id，回溯它「是从哪一次成功对话学出来的」，便于人工 review 蒸馏质量

---

*文档版本：v2.2（与代码状态 2026-08-11 对齐：evaluate 纯规则化 / replan_relax 规则放宽 / synonym_graph rebuild 接口 + outcome 重判入队 + PLAN Playbook 硬约束 + 三层匿名拦截）*
