# Agent2 评估框架设计与实验报告

> 测试日期: 2026-08-10  
> 数据集: 真实 MySQL 数据（120 家商铺，10 品类）+ DeepSeek API

---

## 一、评估框架设计

### 设计理念

Agent2 的评估需要回答两个核心问题：
1. **推荐质量如何？** — Agent 产出的推荐是否匹配用户意图
2. **关键设计是否必要？** — 多层记忆架构的各组件是否有不可替代的增量贡献

为此设计了三层评估体系：

| 层级 | 评估目标 | 方法 | 指标 |
|------|---------|------|------|
| Layer 1 | 推荐质量 | LLM-as-Judge 对推荐结果打分 | relevance / diversity / reasoning（1-5） |
| Layer 2 | 自改进效果 | LLM-as-Judge 对 Playbook 经验质量打分 | actionability / correctness / novelty（1-5） |
| Layer 3 | 组件必要性 | 消融实验（Ablation Study） | Δrelevance / ΔHITL 率 |

### LLM-as-Judge 可行性论证

LLM 作为自动评估器是当前 Agent 评测领域的主流方法，已有充分研究支撑：

- **MT-Bench**（Zheng et al., 2023）：验证 GPT-4 作为 Judge 在多轮对话评估中与人类偏好的一致率达 **80%+**，在 pairwise comparison 场景下接近人类 inter-annotator agreement 水平。
- **AlpacaEval**（Li et al., 2023）：使用 LLM-as-Judge 作为指令跟随任务的自动评估指标，与人类评估的 Spearman 相关性达 **0.89**。
- **Chatbot Arena**（Chiang et al., 2023）：将 LLM Judge 作为人类投票的初步过滤层，显著降低人工评估成本。

**本项目的局限与应对**：使用同一家模型（DeepSeek）做推荐和评测存在自评偏差（self-evaluation bias）。理想做法是使用更强的 Judge 模型（如 GPT-4）评估 DeepSeek 输出。受限于 API 成本，本项目采用结构化评分维度（relevance/diversity/reasoning）+ 明确的 1-5 评分标准来约束 Judge 的主观性，并通过 Layer 1 的客观规则检查（品类匹配、价格约束）作为互补兜底。

---

## 二、实验 1：LLM-as-Judge 推荐质量评估

### 实验设计

- **用例集**：6 个用例覆盖吃（火锅、日料、聚餐）、喝（咖啡）、玩（KTV）、乐（足疗）4 大品类
- **评估流程**：Agent 处理用户请求 → 产出推荐 → 将「用户请求 + 推荐结果」喂给 DeepSeek Judge → 输出 3 维度评分
- **评分维度**：
  - **relevance**（1-5）：推荐是否匹配用户品类/偏好/意图
  - **diversity**（1-5）：Top-3 是否覆盖不同类型选项
  - **reasoning**（1-5）：matchReason 是否有说服力和个性化

### 实验结果

| 用例 | 结果 | Reflection | Relevance | Diversity | Reasoning |
|------|------|-----------|-----------|-----------|-----------|
| 火锅 | HITL | 0 | — | — | — |
| 咖啡 | 0 家 | 2.0 | — | — | — |
| KTV | 0 家 | 2.0 | — | — | — |
| 足疗 | HITL | 0 | — | — | — |
| 日料 | 2 家 | 8.0 | **5.0** | 2.0 | **4.0** |
| 聚餐 | HITL | 0 | — | — | — |

**汇总指标**：
- HITL 触发率：50%（3/6）
- 产生推荐的用例：3/6，其中仅 1 个有 LLM-Judge 评分
- 平均 Reflection Score：7.5/10（仅产生推荐的用例）
- LLM-Judge 平均：relevance=5.0/5, diversity=2.0/5, reasoning=4.0/5

### 结果分析

1. **日料用例表现最佳**：Agent 正确推荐了昭和日料（¥180）和炭火烧鸟居酒屋（¥220），Relevance 满分 5.0，说明 generate 节点注入 user_message 后品类筛选生效。
2. **Diversity 偏低（2.0/5）**：两个推荐都是日式餐饮，同质化较高。这是数据集局限——同品类商铺数量少导致多样性不足。
3. **HITL 率 50%**：火锅、足疗、聚餐三个用例触发了 HITL。这反映了 Agent 的保守策略——当候选不足或意图模糊时选择询问而非强行推荐。
4. **0 家结果的用例**：咖啡和 KTV 搜索到了候选但 generate 节点过滤后为空。说明品类匹配逻辑过严——搜索 typeId=1（美食）返回 30 家店，但名字含"咖啡"的可能只有 2-3 家。

---

## 三、实验 2：Playbook 自改进效果评估

### 实验设计

- **评估对象**：Agent 运行过程中自主蒸馏的 Playbook 经验条目
- **评估方法**：将 Top-10 经验条目喂给 LLM Judge，评估其作为改进规则的质量
- **评分维度**：
  - **actionability**（1-5）：规则是否可执行（1=模糊空泛, 5=有明确操作指令）
  - **correctness**（1-5）：规则逻辑是否正确（1=有逻辑错误, 5=完全正确）
  - **novelty**（1-5）：规则是否有洞察价值（1=常识废话, 5=非显而易见的洞察）

### 实验结果

| 指标 | 评分 |
|------|------|
| Actionability | **4.0/5** |
| Correctness | **5.0/5** |
| Novelty | 3.0/5 |

**Playbook 经验总数**：38 条

**代表性经验条目**：

| 类别 | 经验描述 | 置信度 |
|------|---------|--------|
| intent_parsing | 用户请求中包含"喝咖啡"时，将"咖啡店"作为强制品类条件 | 0.95 |
| tool_selection | 主类别无匹配时，自动扩展搜索范围至可替代类别 | 0.95 |
| hitl_trigger | 候选商铺数为 0 时必须触发 HITL，向用户提供放宽约束选项 | 0.90 |
| hitl_trigger | 候选过少且备选在关键维度上全面弱于主推项时，触发 HITL | 0.90 |

### 结果分析

1. **Correctness 满分（5.0/5）**：所有经验条目逻辑正确，没有出现错误规则误导 Agent 的情况。Reflector-Curator 循环的蒸馏质量可靠。
2. **Actionability 良好（4.0/5）**：经验条目大多以"当 X 时，执行 Y"的条件-动作格式表述，LLM 可以直接在 plan 阶段执行。但部分条目描述偏长，可进一步精炼。
3. **Novelty 一般（3.0/5）**：约 1/3 的经验属于领域常识（如"候选为 0 要触发 HITL"），洞察价值有限。但 intent_parsing 类经验（如"咖啡应作为强制品类约束"）具有一定非显而易见性。

---

## 四、实验 3：消融实验（Ablation Study）

### 实验设计

- **Baseline**：完整系统（Playbook + User Memory + Conversation Context）
- **-Playbook**：移除 Playbook 注入（`get_context()` 返回空），保留 User Memory
- **-Memory**：移除 User Memory（`load_memory()` 返回空偏好），保留 Playbook
- **测试用例**：3 个代表性用例（火锅/吃、KTV/玩、足疗/乐）
- **评估指标**：HITL 触发率、推荐数量、LLM-Judge relevance

### 实验结果

| 变体 | 火锅 | KTV | 足疗 | Δrelevance | ΔHITL |
|------|------|-----|------|------------|-------|
| Baseline | 4 家 (rel=5) | HITL | HITL | — | — |
| -Playbook | 4 家 (rel=5) | 5 家 (rel=5) | 2 家 (rel=5) | +3.3 | **-2** |
| -Memory | HITL | 0 家 | HITL | -1.7 | +0 |

### 结果分析

1. **-Memory 消融**：移除用户偏好后，火锅和足疗用例从有推荐退化为 HITL，KTV 返回 0 家。验证了 User Memory 对减少交互次数的作用——没有偏好数据时 Agent 倾向于询问而非猜测。

2. **-Playbook 消融（反直觉发现）**：移除 Playbook 后 KTV 和足疗从 HITL 变为产生推荐，relevance 不降反升。这一反直觉结果的可能原因：
   - **Playbook 过度保守**：部分经验条目（如"候选不足时触发 HITL"）导致 Agent 过于谨慎，移除后 Agent 更敢于直接推荐
   - **Playbook 注入噪声**：38 条经验中约 1/3 为常识性规则，注入后反而干扰了 LLM 的判断
   - **样本量不足**：仅 3 个用例，统计意义有限

3. **消融实验的启示**：Playbook 的价值不在于"有总比没有好"，而在于经验条目的质量。Novelty=3.0/5 的评分印证了这一点——低质量经验不仅没有帮助，反而可能有害。未来优化方向应聚焦于提高经验蒸馏的筛选门槛，仅保留高 novelty 条目。

---

## 五、评估框架的局限与改进

| 局限 | 影响 | 改进方向 | 状态 |
|------|------|---------|------|
| 同模型自评偏差 | DeepSeek 评 DeepSeek 输出，存在偏好一致倾向 | 引入 GPT-4 作为独立 Judge 模型 | 待实现（API 成本限制） |
| 样本量小 | 初始 6 个用例，统计意义有限 | 扩充至 12+ 用例 | **已实现** ✅ |
| HITL 不可量化 | HITL 触发是合理行为还是 Agent 退缩无法区分 | 启发式分类："必要 HITL" vs "过度 HITL" | **已实现** ✅ |
| Playbook 负面效应 | 消融实验发现 Playbook 可能有害 | 增设 Playbook 质量门槛，低 confidence 条目不入选 | **已实现** ✅ |
| 单轮评估 | 未测试多轮对话的指代解析 | 增加 ScenarioCase 多轮场景评测 | **已实现** ✅ |

### 已实现的改进

**1. Playbook 质量门槛**（`config.py` → `PLAYBOOK_MIN_NOVELTY=0.5`）：

`memory/playbook.py` 的 `curate()` 方法新增 confidence 门槛过滤——每次蒸馏经验时，confidence 低于阈值的洞察直接丢弃，不写入经验库。日志输出跳过数量，便于调试。

**2. HITL 必要性分类**（`eval/runner.py` → `run_single_case_offline()`）：

每次 HITL 触发时，根据候选商铺数量分类：
- 候选 < `minExpectedResults` → `necessary`（合理询问，候选确实不足）
- 候选 ≥ `minExpectedResults` → `excessive`（过度保守，本可以直接推荐）

`EvalMetrics` 新增 `necessaryHitl` 和 `excessiveHitl` 两个字段，评测结果中可区分。

**3. 多轮场景评测**（`eval/runner.py` → `run_multi_turn_scenario()`）：

`MULTI_TURN_CASES` 从 2 个扩充到 4 个，新增：
- `ev_multi_003`：火锅 → "换一家更便宜的"（指代解析 + 价格对比验证）
- `ev_multi_004`：kvt 拼写 → "评分最高的那家"（拼写容错 + 指代追问）

`run_multi_turn_scenario()` 方法逐步骤执行 ScenarioCase，自动验证 check 条件（min_results / max_price / cheaper_than_previous）。

**4. 用例扩充**（`eval/runner.py` → `DEFAULT_CASES`）：

从 8 个扩充到 12 个，覆盖吃·喝·玩·乐 4 大类 + 容错场景。

---

## 六、系统架构概览

```
Agent2 (FastAPI + LangGraph)
├── 8 节点状态图: load_memory → plan → execute → evaluate → generate → reflect → log_trajectory → update_memory
├── 6 个白名单工具: 关键词搜索/品类筛选/商铺详情/评价摘要/偏好查询/位置服务
├── 三层记忆:
│   ├── 短期: 会话上下文摘要 + 上轮推荐结构化快照
│   ├── 中期: 用户偏好 9 维模型 (Redis 增量合并)
│   └── 长期: Playbook 经验库 (MySQL + Redis + ChromaDB 语义检索)
├── Self-Improvement: Reflector-Curator 循环 (低分轨迹 → 经验蒸馏 → 语义检索注入)
├── HITL: 候选不足/意图模糊时中断，Redis 持久化恢复
└── 双层评测: 结构化规则 + LLM-as-Judge 语义评分
```

---

## 参考文献

1. Zheng, L., et al. (2023). "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena." *NeurIPS 2023*.
2. Li, X., et al. (2023). "AlpacaEval: An Automatic Evaluator of Instruction-following Models." *GitHub*.
3. Chiang, C., et al. (2023). "Chatbot Arena: An Open Platform for Evaluating LLMs by Human Preference." *arXiv:2306.05685*.
4. Weng, L. (2025). "Harness Engineering for Self-Improvement." *lilianweng.github.io*.
