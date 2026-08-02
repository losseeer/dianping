# 黑马点评 双 Agent 设计方案（Python 微服务）

---

## 一、总体架构

两个 Agent 以独立 Python 微服务形式部署，通过 HTTP REST 调用 Java 后端获取业务数据：

| 组件 | 语言 | 端口 | 框架 | 模式 |
|------|------|------|------|------|
| Java 后端 | Java | 8081 | SpringBoot | 数据提供方（REST API） |
| Agent 1: 评价摘要 | Python | 8001 | FastAPI | 线性 Pipeline，无 HITL |
| Agent 2: 商户推荐 | Python | 8002 | FastAPI + LangGraph | ReAct + HITL + 长期记忆 |

**关键设计决策**：

- Python Agent 通过 HTTP 调 Java API 获取数据，而非直接查 MySQL。这样复用了 Java 层已有的 Redis 缓存（商铺 GEO、逻辑过期缓存）和业务逻辑（如 distance 计算），避免重复实现。
- Agent 2 可调用 Agent 1 的摘要 API 作为"子工具"，形成 Agent 间协作。
- 存储采用 MySQL 持久化 + Redis 缓存架构：用户偏好记忆（`tb_agent_preferences`）、Playbook 经验条目（`tb_agent_playbook`）、会话对话历史（`tb_agent_conversations`）均以 MySQL 为 source of truth，Redis 为缓存层。
- Playbook 向量索引使用 Chroma 持久化存储（`chroma_data/`），支持 HNSW 近似最近邻语义检索。

---

## 二、Agent 1：评价摘要 Agent

### 2.1 定位与模式

**定位**：对某个商铺/景点的全量评价做自动化分析，输出结构化摘要。

**模式**：线性 Pipeline——步骤是确定性的，不需要 LLM 在每一步做"该不该调用工具"的判断。只有两处需要 LLM：
1. 逐条分析评价的情感和优缺点
2. 最终汇总生成综合建议

### 2.2 API 设计

```
POST /agent1/summary
Body: { "shopId": 5 }
Response: {
  "shopId": 5,
  "shopName": "海底捞火锅(水晶城购物中心店)",
  "totalReviews": 2764,
  "positiveRate": 0.87,          // 好评率 87%
  "avgLikedPerReview": 156,     // 平均每条点赞数
  "topPros": [                   // 提炼出的 Top 优点
    "服务贴心周到",
    "食材新鲜品质好",
    "营业时间长（到凌晨7点）"
  ],
  "topCons": [                   // 提炼出的 Top 缺点
    "人均价格偏高（104元）",
    "高峰期排队时间长"
  ],
  "keyPhrases": [                // 高频关键词
    "服务好", "毛肚", "虾滑", "排队"
  ],
  "recommendation": "综合评价较高，服务是核心优势。适合看重服务体验的用餐场景，但预算敏感者可考虑平价替代。",
  "scoreBreakdown": {            // 评分补充解读
    "overall": 4.9,
    "interpretation": "4.9/5 属于顶级评分，4125的销量说明高复购率"
  }
}
```

### 2.3 Pipeline 五步流程

#### Step 1 — 数据采集

调用 Java 后端两个 API：
- `GET /shop/{shopId}` → 商铺详情（名称、评分、均价、销量、评论数）
- 需新增：`GET /blog/of/shop?shopId={id}&limit=all` → 该商铺全量评价

> **当前缺失**：Java 后端没有"按 shopId 查评价"的 API。BlogController 只有 `/blog/of/user`（按用户查）和 `/blog/hot`（热门），缺少 `/blog/of/shop`。需要 Java 端补一个。

#### Step 2 — LLM 逐条情感分析

将每条评价内容喂给 LLM，提取：

```
对以下评价内容进行结构化分析，输出 JSON：

评价内容：{content}

输出格式：
{
  "sentiment": "positive" | "neutral" | "negative",
  "pros": ["服务好", "食材新鲜"],
  "cons": ["价格偏高", "排队久"],
  "keyPhrases": ["毛肚", "虾滑", "排队"]
}
```

**批量策略**：当前数据量下（每商铺评价数 < 3000），可以一次喂 5-10 条给 LLM 批量分析，减少 API 调用次数。如果评价数超过 500，先按 liked 数排序取 top 200 做代表性分析，再抽样底部 50 做负面代表性分析。

#### Step 3 — 汇总统计

纯代码计算（无需 LLM）：

- `totalReviews` = 评价总数（来自 shop.comments 字段）
- `positiveRate` = sentiment 为 positive 的占比
- `topPros` = 所有评价的 pros 合并后，按出现频次排序取 Top3
- `topCons` = 同理取 Top3
- `keyPhrases` = 所有 keyPhrases 合并后频次排序取 Top5
- `avgLikedPerReview` = 总 liked 数 / 评价数

#### Step 4 — LLM 生成综合建议

将 Step 1 的商铺详情 + Step 3 的统计结果一起喂给 LLM：

```
你是一个客观的评价分析师。请根据以下数据为用户生成一份商铺评价综合摘要：

商铺：{name}
评分：{score}/5 | 均价：{avgPrice}元 | 销量：{sold} | 评论数：{comments}

评价统计：
- 好评率：{positiveRate}
- 最常提到的优点：{topPros}
- 最常提到的缺点：{topCons}
- 高频关键词：{keyPhrases}

输出 JSON：
{
  "recommendation": "一段100字左右的综合建议，客观评价优缺点，给出适用人群建议",
  "scoreBreakdown": {
    "overall": 4.9,
    "interpretation": "评分解读和销量印证"
  }
}
```

#### Step 5 — 结构化输出

合并 Step 3 统计 + Step 4 LLM 输出 → 返回最终 JSON。

### 2.4 缓存策略

评价摘要结果缓存到 Redis，key = `agent1:summary:{shopId}`，TTL = 30min。

理由：评价数据变化频率低（每小时可能有几条新评价），30 分钟的缓存窗口在新鲜度和性能之间取得平衡。商铺详情更新时，Java 端的缓存删除逻辑可以联动清除这个 key。

---

## 三、Agent 2：商户推荐 Agent

### 3.1 定位与模式

**定位**：根据用户需求 + 长期偏好记忆，搜索、筛选、排序并推荐 Top-k 商铺。支持多轮交互，用户可以在对话中完善偏好。

**模式**：LangGraph StateGraph 实现 ReAct 循环 + HITL 断点 + 长期记忆读写。

### 3.2 API 设计

```
POST /agent2/chat
Body: {
  "userId": 1010,
  "message": "我想找附近人均100以下的火锅",
  "x": 120.15,          // 用户经度
  "y": 30.32,           // 用户纬度
  "threadId": "xxx"     // LangGraph thread_id，用于恢复中断的对话
}
Response (两种情况):

情况A — 正常推荐结果：
{
  "type": "recommendation",
  "shops": [
    {
      "id": 1, "name": "103茶餐厅", "distance": 0.35,
      "avgPrice": 80, "score": 3.7,
      "matchReason": "人均80符合预算，距离仅350m，评价摘要显示服务周到",
      "reviewSummary": { ... }  // 调用 Agent1 获取
    },
    ...
  ],
  "memoryUpdated": true,    // 本次交互是否更新了长期记忆
  "newPreferences": ["偏好安静环境"]  // 新增的偏好
}

情况B — HITL 中断，等待用户反馈：
{
  "type": "interrupt",
  "question": "我找到了3家符合你预算的美食商铺。你对环境有什么偏好？比如安静还是热闹？",
  "options": ["偏好安静", "偏好热闹", "无所谓"],
  "threadId": "xxx"       // 用户回复时携带此 ID 恢复对话
}
```

用户回复偏好后：
```
POST /agent2/chat/resume
Body: {
  "userId": 1010,
  "threadId": "xxx",
  "response": "偏好安静"   // 用户选择的偏好
}
```

### 3.3 LangGraph 状态定义

```python
class AgentState(TypedDict):
    # 输入
    user_message: str          # 用户原始消息
    user_id: int               # 用户 ID
    user_x: float              # 用户经度
    user_y: float              # 用户纬度

    # 记忆
    memory: dict               # 从 Redis 加载的用户偏好

    # ReAct 循环
    plan: str                  # LLM 的推理/计划
    tool_calls: list           # 本次要调用的工具列表
    tool_results: list         # 工具执行结果
    evaluation: str            # LLM 对结果的评估

    # 推荐结果
    candidate_shops: list      # 候选商铺（经工具查询得到）
    ranked_shops: list         # 排序后的 Top-k 商铺
    final_recommendation: str  # 最终推荐文本

    # HITL
    hitl_needed: bool          # 是否需要中断等待用户反馈
    hitl_question: str         # 向用户提问的内容
    user_feedback: str         # 用户反馈内容
    memory_updated: bool       # 是否更新了长期记忆

    # 控制
    iteration_count: int       # ReAct 循环次数（防止无限循环）
```

### 3.4 LangGraph 状态图节点详解

#### Node 1 — load_memory

```python
def load_memory(state: AgentState) -> AgentState:
    key = f"user:{state['user_id']}:preferences"
    raw = redis.get(key)
    memory = json.loads(raw) if raw else DEFAULT_MEMORY
    state["memory"] = memory
    state["iteration_count"] = 0
    return state
```

从 Redis 加载用户偏好记忆。如果没有记忆，使用默认空模板。

#### Node 2 — plan (LLM 推理)

这是 ReAct 的核心：LLM 收到用户消息 + 已有记忆 + 已有工具结果，决定下一步做什么。

System Prompt（关键部分）：

```
你是"探店推荐官"，一个了解杭州本地吃喝玩乐的智能推荐助手。

你的任务是根据用户需求 + 用户偏好记忆，搜索并推荐最合适的商铺。

当前用户偏好记忆：
{memory}

工作规则：
1. 解析用户意图：类别、价格范围、距离要求、特殊偏好
2. 选择合适的工具获取数据
3. 如果搜索结果需要结合用户偏好做二次筛选（如"偏好安静"→优先低评论数商铺），在 plan 中明确说明筛选逻辑
4. 如果用户意图模糊（如只说"找个地方吃饭"），考虑中断询问用户偏好
5. 最多循环3轮，避免无限查询

可用工具：
- search_shops_by_keyword(keyword, page)
- search_shops_nearby(typeId, x, y, maxPrice, minScore, page)
- get_shop_detail(shopId)
- get_shop_reviews(shopId, limit)
- get_shop_types()
- get_review_summary(shopId)  ← 调用 Agent1 的 API
- get_user_memory(userId)
```

#### Node 3 — execute (工具执行)

路由 `tool_name` 到对应实现：

| tool_name | 实现 |
|-----------|------|
| `search_shops_by_keyword` | HTTP GET → Java `/shop/of/name` |
| `search_shops_nearby` | HTTP GET → Java `/shop/of/type` + 内存二次过滤 |
| `get_shop_detail` | HTTP GET → Java `/shop/{id}` |
| `get_shop_reviews` | HTTP GET → Java `/blog/of/shop`（需新增） |
| `get_shop_types` | HTTP GET → Java `/shop-type/list` |
| `get_review_summary` | HTTP POST → Agent1 `/agent1/summary` |
| `get_user_memory` | Redis `GET user:{id}:preferences` |

#### Node 4 — evaluate (评估结果)

LLM 评估当前数据是否足够生成推荐。三种判断：

1. **数据充足** → 进入条件分支判断是否需要 HITL
2. **数据不足** → 回到 plan 继续查询（最多 3 轮）
3. **用户意图模糊** → 标记 `hitl_needed = True`

#### Conditional Edge — should_hitl?

```python
def should_hitl(state: AgentState) -> str:
    if state["hitl_needed"]:
        return "interrupt"      # → HITL 断点
    elif state["evaluation"] == "sufficient":
        return "generate"       # → 直接生成推荐
    else:
        return "replan"         # → 回到 plan 继续查询
```

#### Node 5 — HITL interrupt

LangGraph 的 `interrupt_before` 机制：在执行此节点前暂停，将 `hitl_question` 返回给前端。用户通过 `/chat/resume` 接口恢复。

**什么时候触发 HITL**：

| 触发场景 | 向用户提问 |
|----------|-----------|
| 用户只说"找个地方吃饭" | "你想吃什么类型的？火锅、日料、西餐？" |
| 搜索结果太多（>10家） | "你对环境有什么偏好？安静还是热闹？" |
| 搜索结果太少（0-1家） | "附近符合条件的选择不多，可以放宽价格吗？" |
| 用户记忆为空（首次交互） | "平时喜欢什么类型的店？我帮你记住偏好" |

#### Node 6 — update_memory

用户反馈后，LLM 从反馈中提取偏好，写入 Redis：

```
用户说："我喜欢安静的环境，不太喜欢排队"

请从用户反馈中提取偏好，输出 JSON：
{
  "newPreferences": {
    "environmentPreference": ["安静"],
    "avoidFactors": ["排队久"]
  }
}
```

合并到现有记忆（不覆盖已有字段，追加新字段），写入 Redis。

#### Node 7 — generate_recommendation

LLM 综合所有信息生成最终推荐：

- 候选商铺列表 + Agent1 摘要 + 用户偏好记忆
- LLM 做排序（考虑偏好匹配度、距离、评分、价格）
- 输出 Top-k（默认 k=5）+ 每家的推荐理由

### 3.5 长期记忆 Schema

Redis key：`user:{userId}:preferences`

```json
{
  "userId": 1010,
  "preferences": {
    "likedCategories": ["美食"],
    "priceRange": {
      "min": null,
      "max": 100
    },
    "environmentPreference": ["安静", "环境好"],
    "avoidFactors": ["排队久", "太吵"],
    "foodPreferences": ["火锅", "日料"],
    "frequentAreas": ["大关", "运河上街"],
    "specialRequirements": "偏好有停车位"
  },
  "lastUpdated": "2026-07-22T19:00:00",
  "interactionCount": 5,
  "version": 1
}
```

**记忆更新策略**：

- **增量合并**：新偏好追加到已有字段，不覆盖。如已有 `environmentPreference: ["安静"]`，用户再说"喜欢有氛围感的"，合并为 `["安静", "有氛围感"]`。
- **遗忘机制**：`lastUpdated` 超过 30 天的偏好项降低权重（但不删除，LLM 在 plan 时可以判断"这个偏好可能已经过时"）。
- **冲突处理**：如果用户说"我不喜欢火锅了"，LLM 提取出冲突信号，将火锅从 `foodPreferences` 移到 `avoidFactors`。

### 3.6 HITL 交互示例

**Round 1 — 用户首次请求，记忆为空**：

```
用户: "帮我找个吃饭的地方"

Agent 内部:
  load_memory → 空
  plan → "用户意图模糊，只知道要吃饭。先查类型列表，然后中断询问偏好。"
  execute → get_shop_types()
  evaluate → "需要 HITL"
  interrupt →

返回前端:
  {
    "type": "interrupt",
    "question": "你想吃什么类型的？还有你对价格和环境有什么偏好？",
    "options": ["美食-随便", "火锅", "日料", "西餐"]
  }
```

**Round 2 — 用户回复**：

```
用户: "火锅吧，不要太贵的"

Agent 内部:
  update_memory → 写入 {likedCategories: ["美食"], foodPreferences: ["火锅"], priceRange: {max: null}}
  plan → "火锅→美食typeId=1, 附近搜索, 不太贵→价格无上限但优先低价"
  execute → search_shops_nearby(typeId=1, x=120.15, y=30.32)
  evaluate → "找到9家，需要二次筛选。获取评价摘要辅助排序。"
  execute → get_review_summary(shopId=1), get_review_summary(shopId=7)
  evaluate → "数据充足，可以生成推荐"

返回前端:
  {
    "type": "recommendation",
    "shops": [
      {"id": 7, "name": "炉鱼", "avgPrice": 85, "score": 4.7,
       "matchReason": "烤鱼风味接近火锅，价格合适，好评率87%，常被提到食材新鲜"},
      {"id": 2, "name": "蔡馬洪涛烤肉·铜锅涮羊肉", "avgPrice": 85,
       "matchReason": "铜锅涮羊肉=火锅风格，营业到凌晨3点，适合夜宵"},
      {"id": 1, "name": "103茶餐厅", "avgPrice": 80,
       "matchReason": "最便宜且最近（350m），港式茶餐厅，风格偏轻食"}
    ],
    "memoryUpdated": true,
    "newPreferences": ["美食", "火锅"]
  }
```

**Round 3 — 用户进一步反馈**：

```
用户: "炉鱼不错，但我不喜欢太吵的地方"

Agent 内部:
  update_memory → 增量写入 {environmentPreference: ["安静"], avoidFactors: ["太吵"]}
  plan → "用户偏好安静，重新排序候选商铺。评论数少的=不太吵。"
  evaluate → "不需要重新搜索，只需重新排序已有候选"
  generate →

返回:
  重新排序推荐 + 确认记忆已更新
```

---

## 四、Tool Schema 详细定义（Agent 2 专用）

### search_shops_nearby

```json
{
  "name": "search_shops_nearby",
  "description": "搜索用户附近的指定类型商铺。返回按距离排序的商铺列表，附带距离信息。支持价格上限和最低评分过滤。",
  "parameters": {
    "type": "object",
    "properties": {
      "typeId": {
        "type": "integer",
        "description": "1=美食 2=KTV 3=丽人美发 4=健身运动 5=按摩足疗 6=美容SPA 7=亲子游乐 8=酒吧 9=轰趴馆 10=美睫美甲"
      },
      "x": { "type": "number", "description": "用户经度" },
      "y": { "type": "number", "description": "用户纬度" },
      "maxPrice": { "type": "integer", "description": "人均价格上限（可选）" },
      "minScore": { "type": "integer", "description": "最低评分1-5（可选）" }
    },
    "required": ["typeId", "x", "y"]
  }
}
```

### get_review_summary（调用 Agent1）

```json
{
  "name": "get_review_summary",
  "description": "获取某个商铺的评价综合摘要，包含好评率、优缺点、高频关键词和综合建议。这是 Agent1 的输出，调用此工具可以快速获得商铺的评价概况，不需要自己逐条分析。",
  "parameters": {
    "type": "object",
    "properties": {
      "shopId": { "type": "integer", "description": "商铺ID" }
    },
    "required": ["shopId"]
  }
}
```

### search_shops_by_keyword

```json
{
  "name": "search_shops_by_keyword",
  "description": "按商铺名称关键字搜索。用于用户提到了具体商铺名（如'海底捞'）的场景。",
  "parameters": {
    "type": "object",
    "properties": {
      "keyword": { "type": "string", "description": "商铺名称关键字" }
    },
    "required": ["keyword"]
  }
}
```

### get_shop_detail

```json
{
  "name": "get_shop_detail",
  "description": "获取商铺完整详情：地址、均价、评分、销量、营业时间等。",
  "parameters": {
    "type": "object",
    "properties": {
      "shopId": { "type": "integer" }
    },
    "required": ["shopId"]
  }
}
```

### get_shop_types

```json
{
  "name": "get_shop_types",
  "description": "获取所有商铺类型ID和名称映射。当用户用口语表达（如'火锅'、'唱歌'）时，先查此列表确认typeId。",
  "parameters": { "type": "object", "properties": {} }
}
```

---

## 五、Java 后端需要补充的 API

当前 Java 后端缺少两个 Agent 需要的关键接口：

### 5.1 按商铺 ID 查评价（必须）

```java
@GetMapping("/blog/of/shop")
public Result queryBlogByShopId(
    @RequestParam("shopId") Long shopId,
    @RequestParam(value = "current", defaultValue = "1") Integer current) {
    Page<Blog> page = blogService.query()
        .eq("shop_id", shopId)
        .page(new Page<>(current, SystemConstants.MAX_PAGE_SIZE));
    return Result.ok(page.getRecords());
}
```

### 5.2 商铺类型列表（已有但确认可用）

```java
@GetMapping("/shop-type/list")
public Result queryShopTypeList() {
    // 返回所有类型，带 ID 和名称
}
```

> ShopTypeController 已有此接口（Redis 缓存版本），确认返回格式包含 id 和 name 字段即可。

---

## 六、评分解读约定

Shop 表中 `score` 字段存储方式是 **1~5 分乘 10**（避免小数），所以：

- `score = 37` → 实际评分 3.7/5
- `score = 49` → 实际评分 4.9/5
- `score = 46` → 实际评分 4.6/5

Agent 在返回给用户时需要做 `score / 10.0` 的转换。在 tool 返回中直接返回转换后的值，避免 LLM 混淆。

---

## 七、设计对比总结

| 维度 | Agent 1（评价摘要） | Agent 2（商户推荐） |
|------|---------------------|---------------------|
| 模式 | 线性 Pipeline | LangGraph StateGraph (ReAct) |
| HITL | 无 | 有（interrupt + resume） |
| LLM 调用次数 | 2次（分析 + 摘要） | 3-6次（plan + evaluate + generate，可能多轮） |
| 记忆 | 无 | Redis 长期记忆 + 增量更新 |
| 输入 | shopId | userId + message + 位置 |
| 输出 | 结构化 JSON | 推荐列表 + 推荐理由 / 或提问 |
| 缓存 | Redis 30min TTL | 对话状态由 LangGraph checkpoint 管理 |
| 调用方 | 前端直接调用 / Agent2 内部调用 | 前端直接调用 |
| 框架 | FastAPI + LangChain LLM | FastAPI + LangGraph |

---

## 八、未来扩展方向

1. **Agent 1 增加对比模式**：输入两个 shopId，生成对比摘要（哪家更适合什么场景）
2. **Agent 2 增加"探索"模式**：用户没有明确需求时，Agent 主动推荐基于记忆的"今天可能想去的店"
3. **记忆进化**：从简单的 JSON 结构升级为向量嵌入——用户描述偏好后，用 embedding 存储语义，搜索时做向量相似度匹配
4. **多 Agent 协调**：Agent 2 推荐后，用户点进某家店，前端自动调用 Agent 1 展示评价摘要，形成完整的交互闭环

---

## 九、Agent2 Harness Engineering 增强（v2.0）

参考 Lilian Weng《Harness Engineering for Self-Improvement》(2026-07-04)。

核心论点：Agent 能力提升不只来自模型参数，更多来自外部 Harness 层的演化。优化路径：
`instruction prompts → structured context → workflow → harness code → optimizer code`

### 9.1 四层架构

```
Layer 4: Self-Improvement (Self-Harness)     ← propose-evaluate-accept 自改循环
Layer 3: Observability (AHE 三支柱)            ← 组件/经验/决策可观测性
Layer 2: Context Engineering (ACE)             ← Reflector-Curator 演化式上下文
Layer 1: Workflow (LangGraph StateGraph)       ← plan→execute→evaluate→generate→reflect→log
         ──────────────────────────────
         Base Model (LLM: ChatOpenAI)
```

### 9.2 Layer 1: Workflow — 新增 reflect + log_trajectory 节点

**论文对应**: Pattern 1 (Workflow Automation) — "模型通过 agent runtime 分析自身执行轨迹和失败案例，据此迭代改进"

增强后的 LangGraph 流程:
```
load_memory → plan → execute → evaluate → should_hitl
  → interrupt (END)
  → generate → reflect → should_replan
    → replan → plan
    → log_trajectory (END)
  → replan → plan
```

- **reflect 节点**: LLM 自评推荐质量（匹配度/多样性/理由充分性/完整性），评分 < 6.0 触发重规划
- **log_trajectory 节点**: 持久化完整执行轨迹到 Redis，触发 playbook reflection

### 9.3 Layer 2: Context Engineering — ACE 演化式 Playbook

**论文对应**: ACE (Agentic Context Engineering, Zhang et al. 2025) — "上下文作为 evolving playbook，而非不断增长的 prompt"

三个组件:
- **Generator**: Agent2 执行流程本身（已有）
- **Reflector** (`playbook.reflect()`): 从轨迹蒸馏经验洞察，输出结构化条目
- **Curator** (`playbook.curate()`): 增量合并到 playbook，定期去重精炼

Playbook 条目格式: `(entryId, category, description, confidence)`。

存储架构:
- MySQL `tb_agent_playbook`：source of truth，200 条上限
- Redis `agent2:playbook`：条目 JSON 缓存（read-through cache）
- Chroma `chroma_data/`：向量持久化存储，支持 HNSW 语义检索

Plan 节点通过 RAG 检索 Top-K（默认 8）条最相关条目注入 prompt，而非按置信度取 Top-N。

### 9.4 Layer 3: Observability — AHE 三大可观测性支柱

**论文对应**: AHE (Agentic Harness Engineering, Lin et al. 2026) — "harness 进化的瓶颈在于可观测性"

| 支柱 | 实现 | 文件 |
|------|------|------|
| Component Observability | 每节点输入/输出/耗时/LLM调用次数记录 | `timed_node` 装饰器 in main.py |
| Experience Observability | 分层访问: 原始轨迹→分析报告→聚合洞察 | `TrajectoryStore` in trajectory.py |
| Decision Observability | LLM 决策推理 + 预测声明 + 验证结果 | `DecisionLog` in models.py |

Redis 存储结构:
```
agent2:trajectory:{trajId}       → 完整 TrajectoryRecord
agent2:trajectory:user:{userId}  → ZSet (score=timestamp)
agent2:trajectory:analysis:{id}  → 分析报告
agent2:trajectory:insights       → 聚合洞察列表
```

### 9.5 Layer 4: Self-Improvement — Self-Harness propose-evaluate-accept

**论文对应**: Self-Harness (Zhang et al. 2026) — "propose-evaluate-accept 循环"

三阶段循环 (`/agent2/self-improve` 端点):

1. **Weakness Mining**: 收集失败轨迹，规则 + LLM 双重聚类失败模式
2. **Harness Proposal**: LLM 查看失败案例 + 当前 prompt，提出范围受控的修改方案
3. **Proposal Validation**: held-in (70%) 检查弱点修复 + held-out (30%) 检查无新回归

安全设计:
- 评估器位于自改进循环之外
- 编辑仅应用于 playbook/prompt，不修改工具实现
- 拒绝的候选记录但不应用
- held-out 验证防止 reward hacking

### 9.6 Benchmark 先验评测

**论文对应**: 论文七大挑战之一 "Weak and Fuzzy Evaluators" — "自改进循环最适合评估指标可测量且客观的任务"

测试用例集 (8 个默认用例): 覆盖 food/budget/preference/vague_intent/typo 等场景

指标体系:
| 指标 | 含义 | 优化方向 |
|------|------|---------|
| passRate | 测试通过率 | 越高越好 |
| avgIterations | 平均迭代次数 | 越少越好 |
| avgHitlRate | HITL 触发率 | 适中（不为 0，不过高） |
| avgResponseTimeMs | 平均响应时间 | 越少越好 |
| avgReflectionScore | 平均自评质量 | 越高越好 |
| avgCandidateCount | 平均候选数 | 适中 |

对比功能: `compare(before, after)` 输出逐用例对比 + 退化/改进统计 + 整体判定

### 9.7 API 端点总览

| 端点 | 方法 | 层 | 用途 |
|------|------|---|------|
| `/agent2/chat` | POST | 1 | 推荐对话入口 |
| `/agent2/chat/resume` | POST | 1 | 恢复中断对话 |
| `/agent2/trajectory/{id}` | GET | 3 | 获取单条轨迹 |
| `/agent2/trajectory/user/{id}` | GET | 3 | 用户轨迹列表 |
| `/agent2/insights` | GET | 3 | 聚合洞察 |
| `/agent2/trajectory/{id}/outcome` | POST | 3 | 标注结果 |
| `/agent2/playbook` | GET | 2 | Playbook 条目 |
| `/agent2/playbook/deduplicate` | POST | 2 | 去重精炼 |
| `/agent2/self-improve` | POST | 4 | 触发自改进循环 |
| `/agent2/benchmark/cases` | GET | - | 测试用例列表 |
| `/agent2/benchmark/run` | POST | - | 运行 benchmark |
| `/agent2/benchmark/results` | GET | - | 运行记录列表 |
| `/agent2/benchmark/{id}` | GET | - | 单次结果 |
| `/agent2/benchmark/compare` | GET | - | 对比两次结果 |

### 9.8 文件结构

两个 Agent 微服务完全独立，各自有自己的 config/models/redis/llm/java_api_client，无 shared 目录：

```
agent-services/
  requirements.txt      # 共享依赖（两个 Agent 依赖相同）
  start.sh              # 从各自目录启动
  agent1/               # 评价摘要 Agent（独立微服务）
    __init__.py
    .env.example
    main.py             # Pipeline 入口
    config.py           # Agent1 专属配置
    models.py           # Agent1 专属模型（ReviewAnalysis 等）
    redis_client.py     # Redis 连接
    llm.py              # LLM 实例
    java_api_client.py  # Java API 客户端
  agent2/               # 商户推荐 Agent（独立微服务 + 四层 Harness）
    __init__.py
    .env.example
    main.py             # [MODIFIED] 集成四层架构 + 新 API 端点
    config.py           # Agent2 专属配置（含 trajectory/playbook/self-improve/benchmark）
    models.py           # Agent2 专属模型（12 个 schema）
    redis_client.py     # Redis 连接
    llm.py              # LLM 实例
    java_api_client.py  # Java API 客户端
    mysql_client.py     # [NEW] MySQL 异步客户端（aiomysql）
    memory.py           # 用户偏好记忆（MySQL持久化 + Redis缓存）
    conversation.py     # [NEW] 会话上下文管理（MySQL持久化 + Redis缓存 + LLM压缩）
    reflect.py          # [NEW] Layer 1: 推荐质量自评节点
    trajectory.py       # [NEW] Layer 3: 轨迹持久化与分层访问
    playbook.py         # [NEW] Layer 2: ACE 演化式上下文管理 + Chroma 向量检索
    evaluator.py        # [NEW] Benchmark 评测框架
    self_improve.py     # [NEW] Layer 4: Self-Harness 自改进引擎
    chroma_data/        # [NEW] Chroma 向量持久化目录
    self_improve.py     # [NEW] Layer 4: Self-Harness 自改进引擎
```
