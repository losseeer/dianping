# 🍽️ 快评——高并发本地生活服务平台

> 基于 Spring Boot + Redis 的本地生活服务平台，覆盖商户搜索、秒杀抢券、支付退款、社交互动等核心场景，并通过 FastAPI 接入 LLM Agent，实现评价摘要与个性化推荐。

[![Spring Boot](https://img.shields.io/badge/Spring%20Boot-2.3.12-brightgreen.svg)](https://spring.io/projects/spring-boot)
[![JDK](https://img.shields.io/badge/JDK-1.8-orange.svg)](https://www.oracle.com/java/)
[![Maven](https://img.shields.io/badge/Maven-3.9.8-blue.svg)](https://maven.apache.org/)
[![Redis](https://img.shields.io/badge/Redis-7.0-red.svg)](https://redis.io/)
[![Python](https://img.shields.io/badge/Python-3.10+-yellow.svg)](https://www.python.org/)

---

## 📖 目录

- [项目简介](#项目简介)
- [系统架构](#系统架构)
- [技术栈](#技术栈)
- [功能模块](#功能模块)
- [项目结构](#项目结构)
- [快速开始](#快速开始)
- [API 概览](#api-概览)
- [架构亮点](#架构亮点)
- [文档索引](#文档索引)

---

## 项目简介

快评是一个**前后端分离**的本地生活服务平台，面向商户搜索、优惠券秒杀、支付退款和内容互动等场景。项目以 **Redis 为核心**，综合使用 Redis 多种数据结构、RabbitMQ、Elasticsearch，以及基于 **LangChain/LangGraph** 的 LLM Agent 微服务，形成 Java 交易后端与 Python 智能服务协作的架构。

### 核心业务模块

| # | 模块 | 核心技术 |
|---|------|----------|
| 1 | 短信登录 | Redis Token 替代 Session + 双层拦截器 |
| 2 | 商户查询缓存 | Cache Aside 模式 + 缓存穿透/雪崩/击穿防护 |
| 3 | 优惠券秒杀 | Redis + Lua 原子预检 + RabbitMQ 异步下单 |
| 4 | 附近的商户 | Redis GEO 地理位置搜索 |
| 5 | UV 统计 | HyperLogLog 概率去重 |
| 6 | 用户签到 | BitMap 位图 + 位运算连续签到统计 |
| 7 | 好友关注 | Set 集合交集求共同关注 |
| 8 | 达人探店 | ZSet 点赞排行榜 + Blog 发布 |
| 9 | 博客评论 | 评论 CRUD + 点赞 |
| 10 | 支付闭环 | 发起支付 → 回调确认 → 退款 → 订单超时取消 |
| 11 | 推荐系统 | 协同过滤 + GEO 附近热门 + 全站排行 + 熔断降级 |
| 12 | 全文搜索 | Elasticsearch + IK 分词 + 高亮 + 相关度排序 |

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 (Vue/Nuxt)                        │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP
┌──────────────────────▼──────────────────────────────────────┐
│                  Java SpringBoot :8081                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐  │
│  │ Interceptor│ │Controller│ │ Service  │ │   Listener    │  │
│  │ (双层鉴权) │ │ (13个API)│ │ (14个Impl)│ │ (MQ Consumer) │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐  │
│  │  AOP 切面  │ │  Redisson│ │ MyBatisPlus│ │ Elasticsearch │  │
│  │ (限流+熔断)│ │ (分布式锁)│ │  (ORM)    │ │  (全文搜索)   │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────────┘  │
└──────┬───────┬─────────┬──────────┬─────────────────────────┘
       │       │         │          │
┌──────▼──┐ ┌──▼───┐ ┌───▼────┐ ┌──▼──────────┐
│  MySQL   │ │Redis │ │RabbitMQ │ │Elasticsearch │
│  :3306   │ │:6379 │ │ :5672   │ │   :9200      │
└──────────┘ └──┬───┘ └─────────┘ └──────────────┘
                │ 共享 Redis
┌───────────────▼────────────────────────────────┐
│         Python Agent 微服务 (FastAPI)            │
│  ┌──────────────────┐  ┌──────────────────────┐│
│  │ Agent1 :8001     │  │ Agent2 :8002         ││
│  │ 评价摘要分析      │──│ 智能店铺推荐          ││
│  │ (线性Pipeline)   │  │ (ReAct + HITL + 记忆) ││
│  └──────────────────┘  └──────────────────────┘│
│              LLM API (OpenAI 兼容)               │
└─────────────────────────────────────────────────┘
```

---

## 技术栈

### Java 后端

| 技术 | 版本 | 用途 |
|------|------|------|
| Spring Boot | 2.3.12 | 应用框架 |
| MyBatis-Plus | 3.4.3 | ORM + 分页 |
| Spring Data Redis | 2.6.2 | Redis 数据访问 |
| Redisson | 3.13.6 | 分布式锁 |
| Spring AMQP (RabbitMQ) | — | 消息队列 |
| Spring Data Elasticsearch | — | 全文搜索 |
| Guava | 31.1 | RateLimiter 令牌桶限流 |
| Hutool | 5.7.17 | 工具类库 |
| Lombok | — | 代码简化 |
| MySQL Connector | 8.0.28 | 数据库驱动 |
| Lettuce | 6.1.6 | Redis 连接池 |

### Python Agent

| 技术 | 版本 | 用途 |
|------|------|------|
| FastAPI | 0.115 | Web 框架 |
| Uvicorn | 0.34 | ASGI 服务器 |
| LangChain | 0.3.25 | LLM 编排 |
| LangGraph | 0.4.8 | Agent 状态图 |
| LangChain-OpenAI | 0.3.18 | OpenAI 模型集成 |
| Redis | 5.2.1 | 共享缓存 |
| ChromaDB | 0.5.23 | Playbook 向量存储 |
| HTTPX | 0.28.1 | 异步 HTTP 客户端 |

---

## 功能模块

### Redis 数据结构全景图

每种 Redis 数据结构在项目中都有对应的业务落地：

| 数据结构 | 应用场景 | 关键 Key 前缀 |
|----------|----------|--------------|
| **String** | 商铺缓存、验证码、Token、分布式锁 | `cache:shop:`, `login:token:`, `login:code:` |
| **Hash** | 用户信息存储（多字段） | `login:token:{token}` |
| **Set** | 关注列表、共同关注 | `follows:{userId}` |
| **Sorted Set** | 点赞排行榜（按时间排序） | `blog:liked:{blogId}` |
| **GEO** | 附近商铺搜索（按距离排序） | `shop:geo` |
| **BitMap** | 用户签到（按月统计） | `sign:{userId}:{yyyyMM}` |
| **HyperLogLog** | UV 独立访客统计 | `uv:page:{pageId}` |
| **Redis Stream** | 历史秒杀异步下单方案（当前使用 RabbitMQ） | `stream.orders`（旧方案注释） |
| **Lua 脚本** | 秒杀资格原子预检 | `seckill.lua` |

### 核心流程

#### 秒杀下单全链路

```
用户点击秒杀 → Lua脚本(Redis原子预检)
  ├─ 库存检查 → 库存不足 → 返回失败
  ├─ 一人一单 → 重复下单 → 返回失败
  └─ 扣库存+记录 → 发送MQ消息 → 返回订单ID
       ↓
  SeckillVoucherListener (MQ Consumer)
       ↓
  异步保存订单到DB + 扣减DB库存
       ↓
  发送延迟消息(30min TTL) → OrderDelayListener
       ↓
  超时未支付 → 自动取消 → 恢复库存
```

#### 支付闭环

```
发起支付 → 生成支付流水(PAYING) → 返回支付链接
   ↓
支付回调(/pay/notify) → 更新状态(PAID) → MQ异步通知
   ↓
申请退款 → 状态流转(REFUNDING → REFUNDED) → 恢复库存
```

#### 缓存策略（Cache Aside）

```
读请求:
  Redis查询 → 命中 → 直接返回
             → 未命中 → 加互斥锁 → 查DB → 写Redis → 返回
             
写请求:
  更新DB → 删除Redis缓存（保证最终一致性）
  
高一致性场景（如商户信息更新）:
  Redisson读写锁 → 写时禁止读，避免脏数据
```

---

## 项目结构

```
dianping/
├── pom.xml                          # Maven 依赖配置
├── src/main/java/com/hmdp/
│   ├── HmDianPingApplication.java   # 启动类
│   ├── annotation/                  # 自定义注解 (RateLimit, CircuitBreaker)
│   ├── aspect/                      # AOP 切面 (限流切面, 熔断切面)
│   ├── config/                      # 配置类 (MVC, MyBatis, Redisson, Queue, ES)
│   ├── controller/                  # 控制器 (13个 API 模块)
│   │   ├── UserController.java      # 用户登录/登出/签到
│   │   ├── ShopController.java      # 商户查询
│   │   ├── ShopSearchController.java # ES 全文搜索
│   │   ├── VoucherOrderController.java # 秒杀下单
│   │   ├── PaymentController.java   # 支付
│   │   ├── OrderController.java     # 订单管理
│   │   ├── BlogController.java      # 探店笔记
│   │   ├── BlogCommentsController.java # 评论
│   │   ├── FollowController.java    # 关注取关
│   │   ├── RecommendController.java # 推荐
│   │   └── UploadController.java    # 文件上传
│   ├── dto/                         # 数据传输对象
│   ├── entity/                      # 数据库实体
│   ├── document/                    # ES 文档映射
│   ├── repository/                  # ES Repository
│   ├── interceptor/                 # 拦截器 (双层 Token 鉴权)
│   ├── listener/                    # MQ 消费者 (秒杀/支付/延迟)
│   ├── mapper/                      # MyBatis Mapper
│   ├── service/                     # 服务接口 (14个)
│   │   └── impl/                    # 服务实现 (14个)
│   └── utils/                       # 工具类 (CacheClient, RedisIdWorker, SimpleRedisLock...)
├── src/main/resources/
│   ├── application.yaml             # 应用配置
│   ├── seckill.lua                  # 秒杀 Lua 脚本
│   ├── unLock.lua                   # 分布式锁释放脚本
│   └── db/hmdp.sql                  # 数据库初始化 SQL
├── agent-services/                  # Python Agent 微服务
│   ├── requirements.txt             # Python 依赖
│   ├── start.sh                     # 一键启动脚本
│   ├── agent1/                      # Agent1: 评价摘要
│   │   ├── main.py                  # FastAPI 入口
│   │   ├── config.py                # 配置 (环境变量)
│   │   ├── llm.py                   # LLM 调用封装
│   │   ├── models.py                # 数据模型
│   │   └── .env.example             # 环境变量示例
│   └── agent2/                      # Agent2: 智能推荐
│       ├── main.py                  # FastAPI 入口（路由）
│       ├── config.py                # 配置
│       ├── models.py                # 数据模型
│       ├── core/                    # 基础设施
│       │   ├── llm.py               # LLM 客户端
│       │   ├── redis.py             # Redis 客户端 + HITL 状态
│       │   ├── mysql.py             # MySQL 异步客户端
│       │   ├── java_api.py          # Java 后端 API 客户端
│       │   └── guard.py             # 注入防护 + Token 预算
│       ├── graph/                   # LangGraph 图
│       │   ├── state.py             # AgentState
│       │   ├── prompts.py           # System Prompts
│       │   ├── nodes.py             # 8 个节点
│       │   ├── routing.py           # 条件路由
│       │   ├── utils.py             # 计时/JSON 解析
│       │   └── builder.py           # build_graph()
│       ├── memory/                  # 分层记忆与经验库
│       │   ├── user.py              # 用户偏好记忆
│       │   ├── conversation.py      # 会话上下文
│       │   ├── trajectory.py        # 轨迹存储
│       │   └── playbook.py          # Playbook 经验库 + RAG
│       ├── improve/                 # 反思与自改进
│       │   ├── reflect.py           # 反思自评
│       │   └── self_improve.py      # Self-Harness 实验框架
│       ├── eval/                    # Agent 评测
│       │   └── runner.py            # Benchmark / A-B 评测
│       └── .env.example             # 环境变量示例
└── docs/                            # 文档
    ├── SETUP.md                     # 中间件配置指南
    ├── agent-design.md              # Agent 设计方案
    └── 面试八股清单.md               # 面试知识点汇总
```

---

## 快速开始

### 环境要求

- **JDK**: 1.8+
- **Maven**: 3.6+
- **MySQL**: 8.0+
- **Redis**: 7.0+
- **RabbitMQ**: 3.x
- **Elasticsearch**: 7.17+ (可选，仅搜索功能需要)
- **Python**: 3.10+ (可选，仅 Agent 服务需要)

### 一分钟启动（Docker）

```bash
# 1. 启动中间件
docker run -d --name mysql -p 3306:3306 \
  -e MYSQL_ALLOW_EMPTY_PASSWORD=yes -e MYSQL_DATABASE=dingping mysql:8.0

docker run -d --name redis -p 6379:6379 redis:7-alpine

docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=guest -e RABBITMQ_DEFAULT_PASS=guest rabbitmq:3-management

# 2. 导入数据库
mysql -h 127.0.0.1 -u root dingping < src/main/resources/db/hmdp.sql

# 3. 启动 Java 后端
export JAVA_HOME=/Library/Java/JavaVirtualMachines/jdk-1.8.jdk/Contents/Home
~/maven/bin/mvn spring-boot:run
# 服务启动在 http://localhost:8081

# 4. (可选) 启动 Python Agent
cd agent-services && bash start.sh
# Agent1 → http://localhost:8001
# Agent2 → http://localhost:8002
```

> 详细配置说明请参阅 [docs/SETUP.md](docs/SETUP.md)

---

## API 概览

### 用户模块

| 方法 | 路径 | 说明 | 限流 |
|------|------|------|------|
| POST | `/user/code` | 发送验证码 | 1 QPS |
| POST | `/user/login` | 登录 | 5 QPS |
| POST | `/user/logout` | 登出（清除 Redis Token） | — |
| GET | `/user/me` | 获取当前用户 | — |
| POST | `/user/sign` | 每日签到 | — |
| GET | `/user/sign/count` | 连续签到天数 | — |

### 商户模块

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/shop/{id}` | 商户详情（含熔断降级） |
| GET | `/shop-type/list` | 商户类型列表 |
| GET | `/shop/search` | ES 全文搜索（关键词+类型+商圈） |
| POST | `/shop/search/sync` | 全量同步到 ES |
| POST | `/shop/search/import` | 单条商户导入 ES |

### 秒杀模块

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/voucher-order/seckill/{voucherId}` | 秒杀下单（Lua 预检 + MQ 异步） |
| POST | `/voucher/seckill` | 新增秒杀券 |

### 支付模块

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/pay` | 发起支付 |
| POST | `/pay/notify` | 支付回调 |
| POST | `/pay/refund/{id}` | 申请退款 |
| POST | `/pay/refund/callback` | 退款回调 |

### 订单模块

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/order/{id}` | 查询订单详情 |
| GET | `/order/list` | 查询当前用户订单 |
| POST | `/order/cancel/{id}` | 取消订单 |

### 社交模块

| 方法 | 路径 | 说明 |
|------|------|------|
| PUT | `/follow/{id}/{isFollow}` | 关注/取关 |
| GET | `/follow/common/{id}` | 共同关注 |
| POST | `/blog` | 发布探店笔记 |
| GET | `/blog/hot` | 热门笔记 |
| PUT | `/blog/like/{id}` | 点赞笔记 |
| POST | `/blog-comments` | 发表评论 |
| GET | `/blog-comments/blog/{blogId}` | 查询评论 |
| DELETE | `/blog-comments/{id}` | 删除评论 |

### 推荐模块

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/recommend/shops` | 个性化推荐（协同过滤） |
| GET | `/recommend/nearby` | 附近热门 |
| GET | `/recommend/hot` | 全站热门排行 |

### Agent 模块

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `:8001/agent1/summary` | 评价摘要分析 |
| POST | `:8002/agent2/recommend` | 智能店铺推荐 |

---

## 架构亮点

### 1. 双层拦截器 + Redis Token 鉴权

```
请求 → RefreshTokenInterceptor (order=0, 拦截所有)
       ├─ 解析 Token → 查 Redis → 刷新有效期 → 写入 ThreadLocal
       └─ 无 Token 也放行（不校验登录）
     → LoginInterceptor (order=1, 只拦截需登录路径)
       └─ 检查 ThreadLocal 是否有用户 → 无则拦截 401
```

### 2. Cache Aside + 缓存三防

- **缓存穿透**：缓存空值 + 短 TTL（2 分钟）
- **缓存雪崩**：随机过期时间 + 互斥锁控制 DB 查询线程数
- **缓存击穿**：逻辑过期 + 子线程异步重建 + 双重检测

### 3. Redis + Lua 秒杀原子预检

Lua 脚本完成：库存检查 → 一人一单 → 扣库存 → 记录订单，并返回订单 ID；Java 业务层收到结果后发送 RabbitMQ 消息，实现 Redis 原子预检与 MQ 异步下单解耦。

### 4. 死信队列实现订单超时取消

```
订单消息 → ORDER_DELAY_QUEUE (TTL 30min)
         → [过期] → ORDER_DEAD_EXCHANGE
         → ORDER_CANCEL_QUEUE → OrderDelayListener 消费
```

### 5. LLM Agent 双智能体协作

- **Agent1**：线性 Pipeline 评价分析（情感分类 → 统计汇总 → LLM 综合建议）
- **Agent2**：ReAct 模式推荐（多轮对话 + HITL 人工介入 + Playbook 经验 + 反思学习）
- Agent2 可调用 Agent1 的摘要 API 作为子工具

### 6. AOP 限流 + 熔断保护

- **@RateLimit**：Guava RateLimiter 令牌桶，秒杀 50 QPS / 搜索 100 QPS / 验证码 1 QPS
- **@CircuitBreaker**：手动熔断器（CLOSED → OPEN → HALF_OPEN），保护商铺详情和 ES 搜索；商铺详情熔断后直查 MySQL，ES 搜索熔断后使用 MySQL LIKE 兜底

---

## 文档索引

| 文档 | 说明 |
|------|------|
| [docs/SETUP.md](docs/SETUP.md) | 中间件安装与配置指南 |
| [docs/agent-design.md](docs/agent-design.md) | Python Agent 设计方案 |
| [docs/面试八股清单.md](docs/面试八股清单.md) | 面试知识点与八股汇总 |
| [docs/orginal_README.md](docs/orginal_README.md) | 原始项目 README |

---

## License

本项目仅用于学习与面试展示，不用于商业用途。
