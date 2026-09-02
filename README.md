# 🍽️ 快评——高并发本地生活服务平台（Spring Boot + 双 LLM Agent）

> 基于 Spring Boot + Redis + RabbitMQ + Elasticsearch 的本地生活服务平台，覆盖商户搜索、秒杀抢券、支付退款、社交互动、个性化推荐。并通过 FastAPI + LangGraph 接入两个独立 Agent 微服务（评价摘要 / 智能推荐），支持 ReAct 多轮对话、长期记忆、从真实交互中**自进化蒸馏经验**。

[![Spring Boot](https://img.shields.io/badge/Spring%20Boot-2.3.12-brightgreen.svg)](https://spring.io/projects/spring-boot)
[![JDK](https://img.shields.io/badge/JDK-1.8-orange.svg)](https://www.oracle.com/java/)
[![Maven](https://img.shields.io/badge/Maven-3.9.8-blue.svg)](https://maven.apache.org/)
[![Redis](https://img.shields.io/badge/Redis-7.0-red.svg)](https://redis.io/)
[![RabbitMQ](https://img.shields.io/badge/RabbitMQ-3.x-orange.svg)](https://www.rabbitmq.com/)
[![Elasticsearch](https://img.shields.io/badge/Elasticsearch-7.17-green.svg)](https://www.elastic.co/)
[![Python](https://img.shields.io/badge/Python-3.10+-yellow.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.4.8-6B46C1.svg)](https://github.com/langchain-ai/langgraph)

---

## 📖 目录

- [项目简介](#项目简介)
- [系统架构](#系统架构)
- [技术栈](#技术栈)
- [核心亮点速览（面试差异化）](#核心亮点速览面试差异化)
- [功能模块](#功能模块)
- [项目结构](#项目结构)
- [快速开始](#快速开始)
- [API 概览](#api-概览)
- [架构亮点详解](#架构亮点详解)
- [文档索引](#文档索引)

---

## 项目简介

快评是一个**前后端分离 + 双智能体微服务**的本地生活服务平台。核心链路：

1. **Java 交易后端**：以 **Redis 为核心**深度优化高并发，综合使用 String/Hash/Set/ZSet/GEO/BitMap/HyperLogLog/Lua 脚本 8 种数据结构，集成 RabbitMQ 异步解耦、Elasticsearch 全文搜索，实现秒杀抢券、支付退款、社交互动、协同过滤推荐、熔断降级。
2. **Agent1 评价摘要**（FastAPI，:8001）：线性 Pipeline，两步 LLM 完成情感分析 + 结构化建议，30 分钟 Redis 缓存。
3. **Agent2 智能推荐**（FastAPI + LangGraph，:8002）：按论文 Harness Engineering v2.0 架构落地 **4 层结构（Workflow / Context Engineering / Observability / Self-Improvement）**，支持多轮 ReAct、HITL 人工介入、9 维用户偏好记忆，并通过「隐式信号 + 显式 outcome」双轨入队蒸馏 → Playbook 结构化经验库 + 用户偏好收敛，**能从每一次真实对话中持续改进推荐策略**。

### 核心业务模块一览

| # | 模块 | 核心技术 |
|---|------|----------|
| 1 | 短信登录 | Redis Token 替代 Session + 双层拦截器（刷新 / 鉴权分离） |
| 2 | 商户查询缓存 | Cache Aside + 穿透/击穿/雪崩三防 + 逻辑过期异步重建 |
| 3 | 优惠券秒杀 | Redis Lua 原子预检 + Redisson WatchDog 锁 + RabbitMQ 异步下单 + 死信 TTL 超时回库存 |
| 4 | 附近商户 | Redis GEO + GEORADIUS 距离排序 |
| 5 | UV 统计 | HyperLogLog 概率去重，百万级 UV 仅需 12KB 内存 |
| 6 | 用户签到 | BitMap 位图 + 位运算连续签到统计 |
| 7 | 好友关注 | Set 交集求共同关注 |
| 8 | 达人探店 | ZSet 点赞排行榜 + 探店笔记发布 |
| 9 | 博客评论 | 评论 CRUD + 点赞 |
| 10 | 支付闭环 | 发起支付 → 回调确认 → 退款 → 延迟队列超时取消 |
| 11 | 推荐系统 | 协同过滤 + GEO 附近热门 + 全站排行榜 + 断路器降级 |
| 12 | 全文搜索 | Elasticsearch + IK 双 analyzer (index ik_max_word / search ik_smart) + **Synonym Graph Filter 同义词扩展** + 高亮 + 相关度排序 + **断路器 fallback 到 MySQL LIKE** |
| 13 | 评价摘要 Agent | LangChain Pipeline + 情感分析 + Redis 30min 缓存 |
| 14 | 推荐对话 Agent | LangGraph ReAct + HITL + 9 维偏好记忆 + Playbook ACE + **自进化蒸馏闭环** |

---

## 系统架构

```
┌──────────────────────────────────────────────────────────────────────┐
│                       前端 (Vue 3 + TS + Vite + Pinia)                │
│                       · 路由守卫拦截 /agent 未登录                     │
│                       · AgentChat.vue / Search.vue / Seckill.vue      │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ HTTPS / Axios 封装（统一错误提示）
┌──────────────────────────────▼───────────────────────────────────────┐
│                Java Spring Boot :8081（交易 + 业务 + 搜索）            │
│  ┌─────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────────┐ │
│  │ Interceptor  │ │ Controller │ │  Service   │ │   Listener (MQ)  │ │
│  │ · 双层鉴权   │ │ 14 个模块  │ │ 14 个 Impl │ │ 秒杀/支付/延迟    │ │
│  │ · 限流熔断   │ │            │ │            │ │                  │ │
│  └─────────────┘ └────────────┘ └────────────┘ └──────────────────┘ │
│  ┌─────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────────┐ │
│  │ AOP 切面     │ │ Redisson   │ │ MyBatisPlus│ │ Elasticsearch7   │ │
│  │·@RateLimit   │ │ 分布式锁   │ │   ORM      │ │·synonym_graph    │ │
│  │  令牌桶      │ │ WatchDog   │ │  分页      │ │·IK双analyzer     │ │
│  │·@CircuitBreaker三态熔断器    │ │            │ │·search_analyzer  │ │
│  │  fallback→MySQL             │ │            │ │  synonyms 扩展    │ │
│  └─────────────┘ └────────────┘ └────────────┘ └──────────────────┘ │
└──────┬────────┬──────────┬────────────┬────────────────────────────┘
       │        │          │            │
┌──────▼───┐ ┌──▼────┐ ┌───▼─────┐ ┌───▼──────────┐
│  MySQL    │ │ Redis │ │RabbitMQ │ │Elasticsearch │
│  :3306    │ │:6379  │ │ :5672    │ │   :9200       │
│  8 张核心 │ │ 共享  │ │ 3 个DLX │ │ IK + synonyms│
│ +支付+搜索│ │        │ │          │ │  rebuild 接口│
└────┬─────┘ └──┬─────┘ └─────────┘ └──────────────┘
     │          │ 共享（Token / 缓存 / 锁 / 轨迹 / 记忆）
┌─────▼──────────▼──────────────────────────────────────────────────────┐
│           Python Agent 微服务 (FastAPI, 独立部署 可拆机器)              │
│  ┌────────────────────────────────────┐  ┌────────────────────────────┐ │
│  │  Agent1 :8001  评价摘要 Pipeline   │  │  Agent2 :8002  智能推荐    │ │
│  │  · 两阶段 LLM: 逐条分析 + 汇总     │──│  · LangGraph ReAct 7 节点  │ │
│  │  · 30min Redis 缓存               │  │  · 9 维偏好 + Playbook ACE │ │
│  └────────────────────────────────────┘  │  · HITL 人工介入 4 场景   │ │
│                                          │  · 四层 Harness Engineering│ │
│                                          │  · 自进化蒸馏闭环 (信号→入 │ │
│                                          │    队→piggyback+守护进程→  │ │
│                                          │    playbook+偏好→推理侧消费)│ │
│                                          └────────────────────────────┘ │
│                        LLM Provider (OpenAI / DeepSeek 兼容)            │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 技术栈

### Java 后端

| 技术 | 版本 | 用途 |
|------|------|------|
| Spring Boot | 2.3.12.RELEASE | 应用框架 |
| MyBatis-Plus | 3.4.3.4 | ORM + 分页 |
| Spring Data Redis | — | 8 种数据结构业务落地 |
| Redisson | 3.13.6 | 可重入分布式锁 + WatchDog |
| Spring AMQP RabbitMQ | — | 秒杀异步下单 + 死信超时回滚 |
| Spring Data Elasticsearch + 原生 High Level Client | 7.17 | ES 索引建表 + synonym_graph 配置 + 查询 |
| Guava | 31.1 | RateLimiter 令牌桶限流 |
| mysql-connector-java | 8.0.28 | JDBC 驱动 |
| Lombok / Hutool 5.7.17 | — | 代码简化 + 工具库 |
| IK Analyzer | 7.17 | ES 中文分词（index=ik_max_word / search=ik_smart） |

### Python Agent 微服务（Agent1 + Agent2）

| 技术 | 版本 | 用途 |
|------|------|------|
| FastAPI | 0.115.x | Web 框架 + Pydantic 校验 |
| Uvicorn | 0.34.x | ASGI 服务器 |
| LangChain | 0.3.x | LLM 抽象 + Tool Calling |
| LangGraph | 0.4.x | ReAct 状态图 + interrupt/resume HITL |
| LangChain-OpenAI | 0.3.x | LLM 接入（兼容 DeepSeek/Qwen API） |
| Redis (redis-py 5.2.x + aiomysql) | — | 共享缓存 + MySQL 持久化 |
| ChromaDB | 0.5.x | Playbook 向量索引（HNSW） |
| HTTPX | 0.28.x | 异步 HTTP 客户端（调用 Java 后端 / Agent1） |

### 前端

| 技术 | 用途 |
|------|------|
| Vue 3 + TypeScript + Vite 5 | 主框架 |
| Pinia + Vue Router 4 | 状态管理 + 路由（带 requiresAuth 守卫） |
| Element Plus + Tailwind 3 | 组件库 + 样式 |
| Axios | 请求封装（统一错误提示 / Token 注入） |

---

## 核心亮点速览（面试差异化）

> 与「黑马点评原版训练项目」相比，本项目做了 **7 个方向的扩展和深度改造**，用于面试时拉开差距：

1. **支付闭环**：新增 PayLog 支付流水 + 退款 + 30 分钟死信超时取消 + 库存恢复，从「抢券就结束」延伸到完整交易生命周期。
2. **ES 同义词检索（真正写入）**：在 ES 索引 settings 中注册 `shop_synonyms` synonym_graph filter（14 组同义词表 synonyms.txt） + IK 双 analyzer；并通过 `elasticsearch.init.rebuild-on-startup=true` 确保首次启动真正写入；**`POST /shop/search/rebuild-index` 管理接口**在同义词更新后无需重启服务即可让 filter 生效。
3. **接口熔断 + 限流 AOP**：`@RateLimit` 令牌桶（登录 5QPS/秒杀 50QPS/搜索 100QPS）；`@CircuitBreaker` 自定义三态熔断器，商铺详情熔断直查 MySQL，ES 搜索熔断回退到 MySQL LIKE 多字段兜底。
4. **双 Agent 微服务**：
   - Agent1（Pipeline）：评价情感分析 + 结构化摘要，Redis 30min 缓存。
   - Agent2（ReAct + 记忆）：Harness Engineering 四层架构 + Playbook ACE 演化上下文 + 9 维用户偏好 + 自进化蒸馏。
5. **Agent2 自进化闭环（真闭环，不是半吊子）**：
   - **隐式信号（对话结束 outcome=unknown） + 显式 outcome（前端点查看=accepted / 点踩=rejected）**两条管线。
   - 入队 → piggyback 近实时 + 5 分钟 daemon loop 兜底双保险批处理。
   - `playbook_distill` 从推荐成功样本蒸馏「用户模糊说法 → 规范化工具参数」映射 → Playbook fuzzy_mapping。
   - `preference_distill` 从不稳定请求中抽取稳定的类目/价格/商圈偏好 → MySQL+Redis 双写。
   - **推理侧真正消费**：PLAN prompt 硬约束「遇到 [Playbook 规范化补全] 必须落到 tool_calls 参数」；memory.priceRange.max 自动传 maxPrice；likedCategories 自动映射 keyword。
   - **显式 outcome 更新后**：清理 processed marker + 重新入队蒸馏 piggyback kick（`POST /agent2/trajectory/{id}/outcome` 端点）。
6. **三层匿名请求拦截**（userId≤0 防御）：前端路由 `meta.requiresAuth=true`；前端 `sendMessage` 拦截 userId≤0；后端 Pydantic `Field(gt=0)` + handler 再次防御；清理历史脏数据（tb_agent_* user=0 记录 + Redis user:0:*）。
7. **可观测性 + 评测框架**：每节点耗时 + 工具调用 + 决策理由持久化到轨迹；benchmark 8 用例覆盖 6 项指标；支持 before/after 逐用例对比 + 退化检测。

---

## 功能模块

### Redis 8 种数据结构全景图

| 数据结构 | 应用场景 | 关键 Key 前缀 |
|----------|----------|--------------|
| **String** | 商铺缓存（逻辑过期防击穿）、验证码、Token、分布式锁 | `cache:shop:{id}`, `login:token:`, `login:code:` |
| **Hash** | 用户信息（多字段） | `login:token:{token}` |
| **Set** | 关注列表、共同关注（交集） | `follows:{userId}` |
| **ZSet** | 点赞排行榜（时间戳作为 score 天然排序） | `blog:liked:{blogId}` |
| **GEO** | 附近商户搜索（GEORADIUSBYMEMBER + 距离排序） | `shop:geo` |
| **BitMap** | 用户签到（按月 Bitmap，setbit + bitcount 统计连续） | `sign:{userId}:{yyyyMM}` |
| **HyperLogLog** | UV 独立访客统计（PFADD / PFCOUNT） | `uv:page:{pageId}` |
| **Lua 脚本** | 秒杀原子预检（库存+一人一单+扣库存） | `seckill.lua` |

### 秒杀下单全链路

```
用户点击秒杀 → Lua 脚本（Redis 原子预检，2 次网络 RTT → 1 次）
  ├─ 库存不足 / 一人一单重复 → 直接返回 fail
  └─ 扣减 Redis 库存 + 写 Set 记录 userId → 返回 orderId（预生成）
       ↓
  发送 RabbitMQ 消息 → SeckillVoucherListener 异步落库（DB 订单 + DB 库存扣减）
       ↓
  发送延迟消息（TTL 30 分钟）到 ORDER_DELAY_QUEUE
       ↓
  过期 → 死信交换机 → ORDER_CANCEL_QUEUE → OrderDelayListener
       ↓
  若仍 UNPAID：取消订单 + 恢复 Redis 与 DB 库存
```

### 支付闭环

```
发起支付 /pay → 生成 PayLog(PAYING) + 返回支付链接
  ↓
支付回调 /pay/notify → 状态 PAID → MQ 通知下游
  ↓
申请退款 /pay/refund/{id} → REFUNDING → REFUNDED → 恢复库存
```

### 缓存三防（Cache Aside）

```
读: Redis → 命中 → 返回
    Redis → 未命中 → Redisson tryLock → 查DB → 写Redis → unlock
写: 更新 DB → 删除 Redis Key（不是更新，避免双写竞态）
防击穿: 逻辑过期字段（逻辑时间 + 子线程异步重建，读线程返回旧值）
防穿透: 空值缓存 2 分钟 + 布隆过滤器（入口层）
防雪崩: 过期时间加 ±30% 随机抖动 + 热点 Key 多级锁
```

### ES 同义词链路

```
classpath:synonyms.txt（14 组：日料/寿司/居酒屋；火锅/铜锅/涮锅；…）
  ↓  ElasticsearchConfiguration.buildIndexSettings()
  settings.analysis.filter.shop_synonyms = synonym_graph（expand=true）
  analyzer.shop_index_ik    = ik_max_word + lowercase    ← 建索引用，召回最大化
  analyzer.shop_search_synonym = ik_smart + lowercase + shop_synonyms  ← 搜索时同义词扩展
  ↓  DROP→CREATE→PUT MAPPING
  ShopDoc.name/tags/area/address 字段 mapping: analyzer=shop_index_ik, search_analyzer=shop_search_synonym
  ↓  同义词更新后触发
  方式A: application.yaml: elasticsearch.init.rebuild-on-startup=true → 重启一次
  方式B: POST /shop/search/rebuild-index → 服务运行期间直接 DROP+CREATE+IMPORT（推荐，零停服）
  ↓  查询
  用户搜"寿司"→ shop_search_synonym 扩展成「寿司/日料/日式/刺身…」→ 召回扩大 3~8 倍
```

---

## 项目结构

```
dianping/
├── pom.xml                                  # Maven 依赖配置
├── README.md                                # 本文件
├── dianping-frontend/                       # Vue 3 + TS + Vite 前端
│   ├── src/
│   │   ├── api/ (12 个模块：shop/agent/voucher/payment…)
│   │   ├── components/ (shop/blog/voucher 卡片)
│   │   ├── views/ (Search.vue / Seckill.vue / AgentChat.vue …)
│   │   ├── router/index.ts                  # 带 requiresAuth 守卫
│   │   └── utils/request.ts                 # Axios 统一封装
│   └── package.json / tailwind.config.js / vite.config.ts
├── src/main/java/com/hmdp/
│   ├── HmDianPingApplication.java
│   ├── annotation/                          # @RateLimit @CircuitBreaker
│   ├── aspect/                              # RateLimitAspect CircuitBreakerAspect
│   ├── config/
│   │   ├── ElasticsearchConfiguration.java  # synonyms.txt 加载 + index settings + DROP+CREATE+IMPORT
│   │   ├── RedissonConfig / MvcConfig / MybatisConfig / QueueConfig
│   │   └── WebExceptionAdvice
│   ├── controller/ (14 个模块: User/Shop/ShopSearch/Voucher/VoucherOrder/Pay/Order/Follow/Blog/BlogComments/Recommend/Upload…)
│   ├── document/ShopDoc.java                # ES 文档：name/tags/area/address 都带 search_analyzer=shop_search_synonym
│   ├── dto/ / entity/ / enums/ / model/
│   ├── interceptor/                         # RefreshTokenInterceptor + LoginInterceptor 双层
│   ├── listener/                            # SeckillVoucherListener / PayNotifyListener / OrderDelayListener
│   ├── mapper/ (MyBatis-Plus + VoucherMapper.xml)
│   ├── repository/ShopDocRepository.java    # Spring Data ES Repository
│   ├── service/  14 × I*Service + 14 × impl
│   └── utils/ (CacheClient 三防 / RedisIdWorker / SimpleRedisLock / UserHolder / PasswordEncoder…)
├── src/main/resources/
│   ├── application.yaml                     # 含 elasticsearch.init.rebuild-on-startup
│   ├── seckill.lua / unlock.lua
│   ├── synonyms.txt                         # 14 组中文同义词，供 synonym_graph 消费
│   └── mapper/VoucherMapper.xml
├── sql/ (按服务分层)
│   ├── backend/schema/001_core.sql          # 核心表 + 索引
│   ├── backend/schema/002_payment_and_search.sql  # pay_log + tb_shop search 相关
│   ├── backend/data/001_test_data.sql       # 测试数据
│   └── agent2/schema/agent2_tables.sql      # tb_agent_conversations/preferences/playbook/trajectory
├── agent-services/                          # Python 双 Agent 独立微服务（可拆机器部署）
│   ├── requirements.txt                     # 共享依赖清单
│   ├── start.sh                             # 一键启动 agent1:8001 + agent2:8002
│   ├── agent1/                              # 评价摘要 Agent（线性 Pipeline）
│   │   ├── main.py / config.py / llm.py
│   │   ├── models.py / java_api_client.py / redis_client.py
│   │   └── .env.example
│   └── agent2/                              # 推荐 Agent（LangGraph + 四层 Harness）
│       ├── main.py                          # FastAPI 入口（chat/resume + 轨迹 + playbook + memory + self-improve + benchmark + outcome 重判入队）
│       ├── core/                            # 基础设施 (llm / redis / mysql / guard / models / agent1_client / shop_api_*)
│       ├── graph/                           # LangGraph：state / prompts（Playbook硬约束） / nodes / routing / builder / hitl / reflect / utils
│       ├── memory/                          # 分层记忆 (conversation / preferences / trajectory / playbook + Chroma RAG)
│       ├── improve/                         # 自进化：signals.py（入队/piggyback/daemon） + worker.py（批处理） + distill.py（Playbook/偏好蒸馏）
│       ├── eval/                            # 评测：runner.py + run_all_experiments.py + before/after compare
│       ├── tests/test_e2e.py                # 端到端冒烟
│       └── .env.example
└── docs/                                    # 文档集合（见下方「文档索引」）
```

---

## 快速开始

### 环境要求

- JDK 1.8+ / Maven 3.6+
- MySQL 8.0+ / Redis 7.0+ / RabbitMQ 3.x
- Elasticsearch 7.17 + IK Analyzer 7.17（可选，但搜索和同义词需要）
- Python 3.10+（可选，仅 Agent 服务需要）

### 一分钟启动（手动）

```bash
# 1) 启动中间件（Docker 示例）
docker run -d --name mysql -p 3306:3306 \
  -e MYSQL_ALLOW_EMPTY_PASSWORD=yes -e MYSQL_DATABASE=dianping mysql:8.0
docker run -d --name redis -p 6379:6379 redis:7-alpine
docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=guest -e RABBITMQ_DEFAULT_PASS=guest rabbitmq:3-management
docker run -d --name es -p 9200:9200 -e discovery.type=single-node elasticsearch:7.17.10
# ES 可选：安装 IK 插件（容器内） elasticsearch-plugin install https://github.com/medcl/elasticsearch-analysis-ik/releases/download/v7.17.10/elasticsearch-analysis-ik-7.17.10.zip

# 2) 导入数据库
mysql -h127.0.0.1 -uroot dianping < sql/backend/schema/001_core.sql
mysql -h127.0.0.1 -uroot dianping < sql/backend/schema/002_payment_and_search.sql
mysql -h127.0.0.1 -uroot dianping < sql/agent2/schema/agent2_tables.sql
mysql -h127.0.0.1 -uroot dianping < sql/backend/data/001_test_data.sql

# 3) 启动 Java 后端
#   application.yaml 中 elasticsearch.init.rebuild-on-startup=true 默认已开启，
#   首次启动会 DROP→重建 shop 索引 → synonym_graph filter 真正写入 → MySQL→ES 导入全量商铺。
mvn -DskipTests spring-boot:run
# 监听 :8081；同义词/analyzer 更新后可直接调：
curl -X POST http://127.0.0.1:8081/shop/search/rebuild-index  # 零停服重建

# 4) 前端（另一个终端）
cd dianping-frontend && npm install && npm run dev  # :5173

# 5) Agent 微服务（另一个终端）
cd agent-services && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cp agent1/.env.example agent1/.env && cp agent2/.env.example agent2/.env  # 填 LLM API Key
bash start.sh
# Agent1 :8001/docs    Agent2 :8002/docs
```

> 详细中间件配置（ES IK 插件、RabbitMQ DLX 交换机、Redis 集群、死信 TTL 调整等）见 [docs/SETUP.md](docs/SETUP.md)。

---

## API 概览

### 用户 / 商户 / 秒杀 / 支付 / 订单 / 社交 / 推荐

| 方法 | 路径 | 说明 | 保护 |
|------|------|------|------|
| POST | `/user/code` | 发验证码 | `@RateLimit(1 QPS)` |
| POST | `/user/login` | 登录 | `@RateLimit(5 QPS)` |
| POST | `/user/logout` | 清 Redis Token | 需登录 |
| GET  | `/user/me · /user/sign · /user/sign/count` | 个人信息 / 签到 / 连续天数 | 需登录 |
| GET  | `/shop/{id}` | 商户详情 | `@CircuitBreaker(fallback=MySQL)` |
| GET  | `/shop-type/list` | 类型列表 | Redis 缓存 |
| GET  | `/shop/of/type · /shop/of/name` | 类型 / 名称查（兜底 MySQL） | — |
| GET  | `/shop/search` | **ES 全文搜索（IK + synonym_graph + 高亮）** | `@CircuitBreaker(fallback=MySQL LIKE)` |
| POST | `/shop/search/sync · /shop/search/import · /shop/search/rebuild-index` | 全量同步 / 单条导入 / **同义词强制重建索引** | 需登录 (rebuild) |
| POST | `/voucher-order/seckill/{id}` | 秒杀（Lua + MQ） | `@RateLimit(50 QPS)` + 分布式锁 |
| POST | `/voucher/seckill` | 新增秒杀券 | 需登录 |
| POST | `/pay · /pay/notify · /pay/refund/{id} · /pay/refund/callback` | 支付四接口 | 需登录 |
| GET  | `/order/{id} · /order/list` · POST `/order/cancel/{id}` | 订单管理 | 需登录 |
| PUT  | `/follow/{id}/{isFollow}` · GET `/follow/common/{id}` | 关注 / 共同关注 | 需登录 |
| POST/PUT/GET | `/blog · /blog/hot · /blog/like/{id} · /blog-comments/*` | 探店 / 评论 | 需登录 (写) |
| GET  | `/recommend/shops · /recommend/nearby · /recommend/hot` | 协同过滤 / 附近 / 全站热榜 | — |

### Agent 微服务（HTTP 直连）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `:8001/agent1/summary` | 商铺评价情感分析 + 摘要（30min 缓存） |
| POST | `:8002/agent2/chat · /agent2/chat/resume` | Agent2 多轮推荐 + HITL resume |
| POST | `:8002/agent2/trajectory/{id}/outcome` | **显式反馈 outcome + 重判入队蒸馏** |
| GET  | `:8002/agent2/trajectory/{id} · /agent2/trajectory/user/{id} · /agent2/insights` | 轨迹 / 洞察（Layer 3 可观测） |
| GET  | `:8002/agent2/playbook` · POST `:8002/agent2/playbook/deduplicate` | ACE 演化式 Playbook |
| GET  | `:8002/agent2/memory/{userId}` · POST `:8002/agent2/memory/{userId}` | 用户偏好读写 |
| POST | `:8002/agent2/self-improve` | Layer 4 自改进 propose-evaluate-accept |
| GET/POST | `:8002/agent2/benchmark/*` | 评测框架 + before/after compare |

---

## 架构亮点详解

### 1. 双层拦截器 + Redis Token（集群共享鉴权）

```
请求 → RefreshTokenInterceptor (order=0, 全路径)
         ├─ 解析 Authorization → Redis HGETALL login:token:{token}
         ├─ 命中 → 刷新 30min TTL → 写入 UserHolder(ThreadLocal)
         └─ 没 token 也放行（不拦截，允许匿名浏览）
       → LoginInterceptor (order=1, 只拦 /blog /voucher-order /pay 等需登录路径)
         └─ UserHolder 非空 → 通过；否则 401
```

解决了「每次请求都刷新 TTL + 匿名请求不挂登录态」的矛盾，天然支持 Nginx 多实例集群。

### 2. CacheClient 三防工具类

| 问题 | 策略 | 实现 |
|------|------|------|
| 穿透（查不存在的 id → DB 打穿） | 缓存空值 + 短 TTL | `cache:null:{id}` 设 2 分钟 |
| 雪崩（同时大量 Key 过期 → DB 瞬间压满） | 过期时间 TTL 上叠加 ±30% 随机抖动 | CacheClient.setWithRandomExpire |
| 击穿（热点 Key 过期瞬间 → 成千请求打 DB） | 逻辑过期 + 子线程异步重建 + 双检 | RedisData.expireTime（逻辑时间）；tryLock 仅一个线程重建，其他直接返回旧数据 |

### 3. Redis + Lua 秒杀原子预检 + MQ 异步下单

秒杀链路是面试 T0 考点。本项目实现了工业界经典的「Redis 内存裁定 + MQ 异步落库」：

- **为什么 Lua？** 库存判定 + 一人一单 + 扣库存 + 写入 userId set = 4 个命令非原子不可，Lua 让 4 个操作一次 RTT 在 Redis 服务端串行执行，天然无并发竞态。
- **为什么不同步落 DB？** DB 单行写 QPS 约 1k~3k，Redis 单 key 写可达 80k+，异步落库把峰值削平。
- **为什么死信回滚？** 防止用户抢到券但不支付一直占坑。TTL 30min 自动取消 + 恢复库存。

### 4. ES Synonym Graph Filter + 熔断器

索引 settings 的关键配置（本项目 `ElasticsearchConfiguration.buildIndexSettings()` 生成）：

```
analysis.filter.shop_synonyms.type       = synonym_graph
analysis.filter.shop_synonyms.expand     = true
analysis.filter.shop_synonyms.synonyms   = [日料,日本料理,日式,和食,寿司,刺身,居酒屋 ; 火锅,铜锅,涮锅,串串香,麻辣烫 ; ...]
analysis.analyzer.shop_index_ik.tokenizer   = ik_max_word    # 建索引细粒度拆分，召回更广
analysis.analyzer.shop_search_synonym.tokenizer = ik_smart   # 搜索：粗粒度拆分，再 synonym_graph 扩展同义词
```

**为什么 synonym_graph 而不是普通 synonym filter？** synonym_graph 保留了「多词条同义词（日本料理 = 日料）」的位置偏移关系，不会产生假匹配（比如把"日"和"料"各自乱配对），对于短语级 query 精度显著更好。

**熔断器保障高可用**：ES 宕机时，`@CircuitBreaker` 连续 5 次失败 → OPEN 30s → HALF_OPEN 探测，期间所有 `/shop/search` 请求走 `searchFallback()`：对 tb_shop.name/area/address/tags 四字段 MySQL LIKE + 全量评分倒排，用户无感降级。

### 5. Agent2 四层 Harness + 自进化真闭环

```
推理侧（每次对话都消费经验）：
  load_memory → playbook.augment_summary([Playbook 规范化补全] 行)
              + memory: likedCategories / priceRange.max / frequentAreas / avoidFactors
   → PLAN prompt 强约束：Playbook 补全必须落到 tool_calls.params；priceRange.max 自动传 maxPrice
   → execute → evaluate → generate → reflect → log_trajectory

学习侧（每次结束都产出经验）：
  log_trajectory → TrajectoryStore.save
    → enqueue_for_distill → PENDING_ZSET
      → piggyback fire-and-forget 近实时扫描（防抖 15s）
      → daemon loop 5 分钟兜底批处理
       → detect_acceptance: 隐式信号 + 显式 outcome 双轨
       → playbook_distill → fuzzy_mapping 条目写入 tb_agent_playbook + Chroma
       → preference_distill → likedCategories/priceRange/frequentAreas 增量合并写 MySQL+Redis
       → mark_processed

用户点击"查看详情/再来几家"后：
  前端调 POST /agent2/trajectory/{id}/outcome?outcome=accepted&feedback=看了详情
   → 更新 trajectory.outcome
   → 清除 processed marker（保证它能重新出队）
   → enqueue_for_distill + piggyback kick（显式 accepted 立即蒸馏）
```

### 6. AOP 限流 + 熔断

两处注解使用点：

- `@RateLimit(permitsPerSecond = 50, fallbackMsg = "活动太火爆了，请稍后再试")` 修饰 `VoucherOrderController#seckillVoucher`
- `@CircuitBreaker(fallback = "searchFallback")` 修饰 `ShopSearchServiceImpl#search`

自定义三态熔断器状态机：

```
CLOSED → 正常放行，失败计数
  连续 failureThreshold=5 次失败 → 跳 OPEN
OPEN → 直接 fallback，不打后端
  TTL 30s 后 → HALF_OPEN
HALF_OPEN → 放 3 个探针请求
  全部成功 → CLOSED；任一失败 → 再 OPEN
```

---

## 文档索引

| 文档 | 说明 |
|------|------|
| [docs/SETUP.md](docs/SETUP.md) | 中间件安装与配置指南（ES IK / RabbitMQ DLX / 环境变量） |
| [docs/agent-design.md](docs/agent-design.md) | Agent 设计方案：Harness 四层架构、工具、Playbook、自进化闭环 |
| [docs/简历项目经历.md](docs/简历项目经历.md) | 两个项目各 550 字简历版本（技术亮点 + 量化指标） |
| [docs/面试八股清单.md](docs/面试八股清单.md) | 面试知识点与 T0/T1/T2 八股汇总 |
| [docs/interview-qa.md](docs/interview-qa.md) | 项目答辩 Q&A（为什么选 Lua？为什么死信？为什么 synonym_graph？） |
| [docs/tech-transfer.md](docs/tech-transfer.md) | 技术转让与交接文档：模块负责人 / 常见排障手册 |
| [docs/perf-report.md](docs/perf-report.md) | 性能压测报告（秒杀 QPS / 缓存命中率 / ES 搜索耗时） |
| [docs/agent2_test_report.md](docs/agent2_test_report.md) | Agent2 功能测试报告（P0/P1/P2 缺陷 + 修复建议） |
| [docs/orginal_README.md](docs/orginal_README.md) | 原始训练项目 README，保留做基线对比 |

---

## License

本项目仅用于**学习、面试展示和技能复盘**，不用于商业用途。部分基础骨架参考了黑马点评训练项目，但支付、ES 同义词、熔断限流、双 Agent、Harness Engineering 自进化链路等为扩展实现。
