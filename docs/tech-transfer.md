# 技术迁移与工程落地指南

> Tech Transfer & Engineering

*快评项目可迁移模式 x 大厂业务场景映射 x 通用工程落地实践*

## 目录

### 一、可迁移技术模式 — 大厂业务场景映射

- 1.1 高并发秒杀架构
- 1.2 缓存策略体系（穿透/击穿/雪崩）
- 1.3 分布式锁与资源互斥
- 1.4 延迟队列与订单状态机
- 1.5 限流与熔断降级
- 1.6 Redis 数据结构应用（GEO/BitMap/ZSet）
- 1.7 Agent 架构与 ReAct 工作流
- 1.8 三层记忆架构与自改进机制
- 1.9 评测体系与质量保障

### 二、通用工程落地知识

- 2.1 容器化部署（Docker）
- 2.2 服务编排（Kubernetes）
- 2.3 CI/CD 持续集成与部署
- 2.4 监控与可观测性
- 2.5 配置中心与环境管理
- 2.6 灰度发布与流量控制
- 2.7 压测与容量规划

---

## 一、可迁移技术模式 — 大厂业务场景映射

以下从本项目中提炼 9 个核心技术模式，逐一映射到各大厂的真实业务场景，说明迁移要点和面试加分角度。

### 1. 高并发秒杀架构

*Redis + Lua + MQ*

#### 核心技术点

Redis + Lua 脚本原子预检（库存检查 → 一人一单 → 扣库存 → 记录订单四步原子化）→ RabbitMQ 异步下单 → 消费端分布式锁兜底防重复。将数据库压力转移到内存，QPS 从百级提升到万级。

#### 大厂场景映射

| 公司 | 业务场景 | 技术对应 |
| --- | --- | --- |
| 美团 | 优惠券秒杀、红包雨 | Redis 预扣库存 + MQ 异步落库 |
| 滴滴 | 高峰期打车匹配 | 司机资源原子抢占 + 异步派单 |
| 拼多多 | 百亿补贴限时秒杀 | Redis Cluster 分片 + Kafka 削峰 |
| 京东 | 618/双11 预售抢购 | 多级缓存 + 限流 + 异步下单 |
| 12306 | 火车票抢票 | 余票 Redis 预扣 + 排队机制 |

#### 迁移要点

- **核心思路不变**：限流挡入口 → 缓存扛压力 → 异步削峰值，三步是所有秒杀场景的通用解法
- **MQ 选型**：本项目用 RabbitMQ（万级 QPS），大厂场景换成 Kafka（百万级 QPS）或 RocketMQ（事务消息）
- **库存预热**：活动开始前将库存写入 Redis，活动期间全程不查 DB
- **防超卖兜底**：DB 层加乐观锁 `WHERE stock > 0`，即使 Redis 出问题也不会超卖

> **面试加分点**
> 能说清楚"为什么用 Lua 而不是分布式锁"——Lua 天然原子（Redis 单线程），一次网络往返完成 4 步操作；分布式锁有获取/释放开销且有锁竞争。Lua 适合秒杀这种高频简单逻辑，分布式锁适合业务逻辑复杂需要多步 DB 操作的场景。

### 2. 缓存策略体系（穿透 / 击穿 / 雪崩）

*Cache Aside + 逻辑过期*

#### 核心技术点

三件套防护 + Cache Aside 写策略：**穿透**用空值缓存 + 布隆过滤器；**击穿**用逻辑过期 + 异步线程重建（互斥锁保证只有一个线程重建）；**雪崩**用随机 TTL；写操作用"先更新 DB 再删除缓存"。

#### 大厂场景映射

| 公司 | 业务场景 | 缓存策略应用 |
| --- | --- | --- |
| 淘宝 | 商品详情页 | 多级缓存（本地 Caffeine + Redis + DB） |
| 美团 | 店铺信息查询 | 逻辑过期 + 异步重建 + 二级缓存 |
| 抖音 | 视频推荐 Feed 流 | 缓存预热 + 穿透防护 + 降级策略 |
| 微信 | 朋友圈内容 | 写扩散 + 读扩散 + 缓存 |

#### 迁移要点

- **多级缓存**：本地缓存（Caffeine/Guava Cache）→ 分布式缓存（Redis Cluster）→ DB，逐层兜底
- **逻辑过期适用场景**：高热点 key，能容忍短时间脏数据。不能用于金融/库存等强一致场景
- **Cache Aside 为什么删缓存不更新缓存**：避免并发写导致缓存和 DB 不一致；删除是幂等的，更新不是
- **删除缓存失败补偿**：消息队列重试 / 订阅 binlog（Canal）异步删缓存

> **大厂进阶方案**：美团/阿里用 Canal 订阅 MySQL binlog，通过 MQ 广播到各服务异步删缓存，彻底解决"删缓存失败"问题。这就是"最终一致性"的工程实践。

### 3. 分布式锁与资源互斥

*Redisson + WatchDog*

#### 核心技术点

Redisson 可重入锁 + WatchDog 自动续期（默认 30s 过期，每 10s 续期一次）。锁粒度精确到 userId（一人一单），消费端分布式锁兜底防重复消费。

#### 大厂场景映射

| 公司 | 业务场景 | 锁的用途 |
| --- | --- | --- |
| 蚂蚁 | 交易防重 | 同一笔交易只处理一次 |
| 美团 | 订单创建防重 | 同一用户短时间内不重复下单 |
| 滴滴 | 司机抢单互斥 | 一个订单只被一个司机抢到 |
| 京东 | 库存扣减 | 防止并发扣减导致超卖 |
| 微信 | 红包拆领 | 一个红包只被拆一次 |

#### 迁移要点

- **锁粒度**：越细越好。锁 userId 而不是锁 voucherId，不同用户之间不互斥
- **WatchDog 续期原理**：底层用 Netty 的 HashedWheelTimer 定时任务，每 `lockWatchdogTimeout/3` 秒检查一次锁是否还被当前线程持有，是则续期到 30s
- **主从一致性**：Redis 主从切换可能丢锁。Redisson 提供 RedLock（红锁），在多个独立 Redis 节点都加锁成功才算成功。但 RedLock 有争议（Martin Kleppmann vs antirez 论战），生产中更多用 ZooKeeper/etcd 做强一致锁
- **替代方案**：ZooKeeper（CP，强一致）、etcd（K8s 内置）、DB 排他锁（简单但性能差）

### 4. 延迟队列与订单状态机

*RabbitMQ DLX + TTL*

#### 核心技术点

订单创建后发送到延迟队列（TTL 30min），过期后进入死信队列，消费者监听死信队列执行超时取消。订单状态机：UNPAID → PAID → COMPLETED / CANCELLED / REFUNDING → REFUNDED，状态转换前校验合法性。

#### 大厂场景映射

| 公司 | 业务场景 | 延迟时间 | 技术方案 |
| --- | --- | --- | --- |
| 美团 | 外卖订单超时取消 | 15-30 min | RocketMQ 延迟消息 |
| 淘宝 | 待付款订单关闭 | 30 min | RocketMQ 定时消息 |
| 携程 | 机票订单超时 | 30 min | RabbitMQ DLX + TTL |
| 滴滴 | 订单超时重派 | 3-5 min | Redis ZSet 时间轮 |
| 微信 | 红包 24h 退款 | 24 h | 定时任务扫表 + MQ |

#### 迁移要点

- **TTL 设在消息上 vs 队列上**：设在队列上会有"队头阻塞"问题——后面的消息即使先过期也要等前面的过期。本项目将 TTL 设在消息上避免此问题
- **方案选型**：RabbitMQ DLX 适合万级延迟消息；RocketMQ 延迟消息（固定 18 个级别）适合十万级；Redis ZSet 时间轮适合短延迟 + 高吞吐；Kafka + 时间轮适合百万级
- **状态机设计**：用枚举 + `canTransitionTo()` 方法限制非法转换。退款失败时状态回滚到 PAID，不留在 REFUNDING
- **支付回调幂等**：查 PayLog 状态，已成功直接返回；用 `UPDATE ... WHERE status = 1` 乐观锁防并发

> **面试加分点**
> 面试官常问"如果延迟消息丢了怎么办"：① 消息持久化 ② 定时任务兜底（每分钟扫一遍超时未支付的订单）③ 消费端幂等设计。延迟队列不是唯一手段，而是和定时任务配合使用。

### 5. 限流与熔断降级

*令牌桶 + 三态熔断器*

#### 核心技术点

Guava RateLimiter 令牌桶限流（AOP 注解 `@RateLimit`）+ 自研三态熔断器（CLOSED → OPEN → HALF_OPEN）。滑动窗口统计失败率，CAS 保证状态转换原子性，半开状态放少量请求探测恢复。

#### 大厂场景映射

| 公司 | 中间件 | 应用场景 |
| --- | --- | --- |
| 阿里 | Sentinel | 接口限流 + 熔断降级 + 系统自适应保护 |
| 美团 | OCTO + Shepherd | 服务治理 + API 网关限流 |
| Netflix | Hystrix（已停更）/ Resilience4j | 熔断器 + 舱壁隔离 + 降级 |
| 字节 | 内部限流中间件 | 基于 QPS + 资源水位的多维限流 |

#### 迁移要点

- **令牌桶 vs 漏桶**：令牌桶允许突发（预消费令牌），适合秒杀；漏桶匀速输出，适合保护下游
- **滑动窗口实现**：本项目用数组 + 时间片实现，每个时间片记录请求数和失败数。大厂用 LeapArray（Sentinel）或 HystrixCollapser
- **半开探测**：放 N 个请求过去，全部成功 → CLOSED；有失败 → 重新 OPEN。默认放 5-10 个
- **大厂实践**：阿里 Sentinel 支持"慢调用比例"熔断（RT > 阈值的请求占比超限则熔断），比纯异常率更早发现问题

> **生产建议**：自研熔断器适合学习和面试展示，生产环境直接用 Sentinel 或 Resilience4j。Sentinel 的优势是自带控制台、规则动态推送、热点参数限流。

### 6. Redis 数据结构应用（GEO / BitMap / ZSet）

*LBS + 签到 + 排行榜*

#### 核心技术点

三种 Redis 数据结构的业务化应用：**GEO** 实现附近商铺按距离排序（底层 GeoHash + ZSet）；**BitMap** 实现用户签到与连续天数计算（位运算）；**ZSet** 实现点赞排行榜（score = 点赞数 + 时间戳）。

#### 大厂场景映射

| 数据结构 | 公司场景 | 业务用途 |
| --- | --- | --- |
| **GEO** | 美团 / 滴滴 / 高德 | 附近商铺 / 附近司机 / 附近 POI |
| **BitMap** | 京东 / 美团 | 签到打卡 / 用户活跃度统计 / 布隆过滤器 |
| **ZSet** | 抖音 / 微信 / 淘宝 | 点赞排行 / 热搜榜 / 销量排行 / 延迟队列 |

#### 迁移要点

- **GEO 底层**：Redis GEO 基于 GeoHash 编码 + ZSet 存储。`GEOSEARCH` 命令做矩形/圆形范围查询，按距离排序。不能直接做"评分最高的店"，需要二次过滤或用 ES 复合查询
- **BitMap 连续签到**：从今天往前遍历位图，遇到 0 就停。用 `BITCOUNT` 统计月签到次数，`BITFIELD` 读取指定位
- **ZSet 排行榜**：score 用"点赞数 × 10^10 + (MAX_TIMESTAMP - 当前时间戳)"实现"同点赞数按时间排序"。大厂用 Redis ZSet 做实时排行榜，百万人同时刷新不压 DB
- **内存优化**：10 万用户签到只占 ~12KB（10 万 bit ÷ 8），比 Set 存 userId 省 100 倍内存

### 7. Agent 架构与 ReAct 工作流

*LangGraph + 状态机 + HITL*

#### 核心技术点

LangGraph 8 节点状态图（load_memory → plan → execute → evaluate → generate/reflect/replan）+ 条件路由 + HITL 人工接管（中断状态 Redis 持久化）+ 工具白名单调用 + Prompt 注入防御。

#### 大厂场景映射

| 公司 | Agent 产品 | 架构对应 |
| --- | --- | --- |
| 阿里 | 小蜜 / 通义 | 智能客服 Agent（多轮对话 + 工具调用 + 人工接管） |
| 美团 | 商家智能助手 | 经营建议 Agent（数据分析 + 推荐 + 人工审核） |
| 字节 / Coze | 扣子 / 豆包 | 低代码 Agent 平台（工作流编排 + 插件 + 知识库） |
| GitHub | Copilot | 代码 Agent（ReAct + 工具调用 + 上下文管理） |
| 腾讯 | ima / 元宝 | 知识库问答 Agent（RAG + 记忆 + 工作流） |

#### 迁移要点

- **状态机是 Agent 的骨架**：LangGraph 的条件路由让 Agent 行为可控。纯 ReAct 循环（Think → Act → Observe）在复杂任务中容易发散，状态机约束了决策空间
- **HITL 是安全阀**：LLM 不确定时主动中断，等人工确认后恢复。这在金融、医疗、法律等高风险场景是刚需。阿里小蜜在涉及退款、投诉时自动转人工
- **中断恢复**：LangGraph 自带 checkpoint，但生产环境用 Redis 持久化更可控——存 conversationId、中断节点、中断时的状态快照，恢复时从断点节点继续执行
- **工具白名单**：只暴露 6 个安全工具，LLM 不能调用任意函数。参数用 Pydantic schema 校验，格式不对直接报错不执行

> **面试加分点**
> 能说清楚"为什么用 LangGraph 而不是纯 LangChain Agent"——LangChain 的 AgentExecutor 是黑盒循环，不可控；LangGraph 是白盒状态机，每个节点的输入/输出/路由条件都可见可调，适合生产环境。

### 8. 三层记忆架构与自改进机制

*短期 + 长期 + Playbook RAG*

#### 核心技术点

三层记忆：短期（会话上下文摘要 + 结构化商铺快照）→ 长期（用户偏好向量库）→ Playbook（经验规则库 + ChromaDB 语义检索）。Reflector 从执行轨迹蒸馏改进规则，Curator 评估后写入 Playbook。消融实验证明移除 Playbook 后 66% 用例退化为 HITL 中断。

#### 大厂场景映射

| 公司 | 场景 | 记忆/自改进应用 |
| --- | --- | --- |
| 阿里 | 小蜜客服 | 对话记忆 + 话术经验积累 + 质检反馈闭环 |
| 字节 | 推荐系统 | 用户短期兴趣 + 长期画像 + 实时反馈调整策略 |
| 美团 | 商家助手 | 经营经验知识库 + 案例检索 + 策略自优化 |
| OpenAI | ChatGPT Memory | 跨会话记忆 + 用户偏好学习 + 主动记住/忘记 |

#### 迁移要点

- **数值独立存储的原因**：LLM 上下文窗口有限且会截断，结构化数值（价格、评分、距离）放在 state 中独立传递，不依赖 LLM"记住"。这解决了 LLM 输出推荐理由时价格写错的问题
- **Playbook 格式**：结构化条目——category（类别）+ description（规则描述）+ confidence（置信度）。Reflector 用 LLM 分析失败轨迹，生成"如果遇到 X 情况，应该 Y"的规则
- **RAG 检索**：Chroma 向量检索 Top-K（默认 8），混合评分 = 语义相似度 × 0.7 + 置信度 × 0.3。检索失败时降级为纯置信度排序
- **自改进防退化**：propose-evaluate-accept 循环。新规则先写入候选区，评估通过才入正式库。低分规则自动淘汰。有回滚机制——记录每次更新，可恢复到任意版本

> **大厂趋势**：OpenAI 的 Memory 功能、Coze 的知识库 + 长期记忆、LangChain 的 LangGraph Memory Store，都在做类似的事情——让 Agent 具备"经验积累"能力，而非每次对话都从零开始。

### 9. 评测体系与质量保障

*双层评测 + LLM-as-Judge*

#### 核心技术点

Layer 1 结构化回归检查（JSON 格式合法性、字段完整性、状态机校验、工具参数 schema 校验）→ Layer 2 语义评分（LLM-as-Judge 从相关性、多样性、理由质量三维度打分）+ 消融实验验证组件价值。

#### 大厂场景映射

| 公司 | 场景 | 评测应用 |
| --- | --- | --- |
| OpenAI | 模型评估 | Evals 框架 + 人工标注 + 自动化基准测试 |
| 字节 | 豆包/Coze | Bot 质量评分 + 用户反馈 + A/B 测试 |
| 阿里 | 通义/小蜜 | 对话质量自动评估 + 人工抽检 + badcase 治理 |
| 腾讯 | ima/元宝 | 回答质量评分 + 安全审核 + 幻觉检测 |

#### 迁移要点

- **双层评测逻辑**：Layer 1 是"格式对不对"，Layer 2 是"内容好不好"。Layer 1 过了但 Layer 2 低分 → 格式正确但语义错误（如推荐了不相关的商铺）；Layer 1 没过 → 直接拦截，不需要跑 Layer 2
- **LLM-as-Judge 一致性**：同一输入评两次分不一样是固有问题。解决方案：① temperature 设 0 ② 多次采样取平均 ③ 设计 rubric（评分标准）让 LLM 按 rubric 逐项打分 ④ 人工校准 LLM 评分
- **消融实验设计**：控制变量——同一组测试用例，分别跑"有 Playbook"和"无 Playbook"两组，对比 HITL 中断率和推荐质量分数。66% 退化说明 Playbook 显著减少了不必要的 HITL 中断

---

## 二、通用工程落地知识

从开发到生产，项目需要经历容器化、编排、CI/CD、监控等工程化改造。以下覆盖面试常考的工程落地知识。

### 2.1 容器化部署（Docker）

*Dockerfile + Compose*

#### 为什么要容器化

- **环境一致**："在我机器上能跑" → 开发/测试/生产环境完全一致
- **快速部署**：秒级启动，比虚拟机轻量百倍
- **资源隔离**：CPU/内存限制，互不干扰
- **弹性伸缩**：配合 K8s 自动扩缩容

#### Java 后端 Dockerfile（多阶段构建）

```dockerfile
# ---- Stage 1: 构建 ----
FROM maven:3.9-openjdk-11 AS builder
WORKDIR /build
COPY pom.xml .
RUN mvn dependency:go-offline      # 依赖缓存层
COPY src ./src
RUN mvn package -DskipTests

# ---- Stage 2: 运行 ----
FROM openjdk:11-jre-slim
WORKDIR /app
COPY --from=builder /build/target/hmdp-1.0.jar app.jar
EXPOSE 8081
ENV JAVA_OPTS="-Xms256m -Xmx512m -XX:+UseG1GC"
ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]
```

多阶段构建的好处：最终镜像不包含 Maven 和源码，体积从 1GB+ 降到 ~200MB。依赖缓存层单独一层，pom.xml 没变时不重新下载依赖。

#### Python Agent Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app

# 系统依赖（ChromaDB 需要 sqlite3）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc sqlite3 && rm -rf /var/lib/apt/lists/*

# 依赖先装（利用缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 代码后装（代码变化不重装依赖）
COPY . .

EXPOSE 8002
CMD ["python", "main.py"]
```

#### Docker Compose 编排（开发环境一键启动）

```yaml
version: "3.8"
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: dingping
    ports: ["3306:3306"]
    volumes: ["mysql_data:/var/lib/mysql"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  rabbitmq:
    image: rabbitmq:3.12-management
    ports: ["5672:5672", "15672:15672"]   # 15672 = 管理界面

  elasticsearch:
    image: elasticsearch:7.17.9
    environment:
      discovery.type: single-node
      ES_JAVA_OPTS: "-Xms256m -Xmx256m"
    ports: ["9200:9200"]

  backend:
    build: .
    ports: ["8081:8081"]
    depends_on: [mysql, redis, rabbitmq, elasticsearch]
    environment:
      SPRING_PROFILES_ACTIVE: prod

  agent:
    build: ./agent-services
    ports: ["8002:8002"]
    depends_on: [redis, mysql]

volumes:
  mysql_data:
```

#### 镜像优化最佳实践

- **用 slim/alpine 基础镜像**：`openjdk:11` → `openjdk:11-jre-slim`，减少 ~400MB
- **合并 RUN 指令**：每条 RUN 产生一层，合并后减少层数
- **.dockerignore**：排除 `node_modules`、`.git`、`target` 等，加快构建
- **非 root 用户运行**：`RUN useradd -m appuser && USER appuser`，安全加固

> **面试加分点**
> 面试官常问"Docker 和虚拟机的区别"：Docker 共享宿主内核，启动秒级，资源占用 MB 级；虚拟机有完整内核，启动分钟级，资源占用 GB 级。Docker 适合微服务部署，虚拟机适合强隔离场景。

### 2.2 服务编排（Kubernetes）

*K8s Deployment + Service + HPA*

#### K8s 核心概念

| 概念 | 类比 | 作用 |
| --- | --- | --- |
| Pod | 一个进程组 | K8s 最小调度单位，包含 1-N 个容器 |
| Deployment | 进程管理器 | 管理 Pod 副本数、滚动更新、回滚 |
| Service | 负载均衡器 | 给 Pod 提供固定 IP 和 DNS 名，负载均衡 |
| Ingress | Nginx/网关 | HTTP 七层路由，外部流量入口 |
| ConfigMap | 配置文件 | 管理环境变量和配置文件 |
| Secret | 密码箱 | 加密存储密码、Token、密钥 |
| HPA | 自动扩缩容 | 根据 CPU/内存/自定义指标自动调整 Pod 数 |

#### Java 后端 K8s 部署清单

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hmdp-backend
spec:
  replicas: 3                      # 3 个副本
  selector:
    matchLabels:
      app: hmdp-backend
  template:
    metadata:
      labels:
        app: hmdp-backend
    spec:
      containers:
      - name: backend
        image: registry.cn-hangzhou.aliyuncs.com/myrepo/hmdp:1.0
        ports:
        - containerPort: 8081
        resources:
          requests:                 # 调度时保证的资源
            cpu: "250m"
            memory: "512Mi"
          limits:                    # 硬上限，超过会被限流或 OOMKill
            cpu: "500m"
            memory: "1Gi"
        env:
        - name: SPRING_REDIS_HOST
          valueFrom:
            configMapKeyRef:
              name: hmdp-config
              key: redis-host
        - name: MYSQL_PASSWORD
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: password
        livenessProbe:              # 存活探针：失败则重启容器
          httpGet:
            path: /api/health
            port: 8081
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:             # 就绪探针：失败则从负载均衡摘除
          httpGet:
            path: /api/ready
            port: 8081
          initialDelaySeconds: 20
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: hmdp-backend-svc
spec:
  selector:
    app: hmdp-backend
  ports:
  - port: 80
    targetPort: 8081
  type: ClusterIP                   # 集群内部访问
```

#### HPA 自动扩缩容

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: hmdp-backend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: hmdp-backend
  minReplicas: 3                    # 最少 3 个
  maxReplicas: 20                   # 最多 20 个
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70       # CPU 使用率超 70% 就扩容
```

> **大厂 K8s 实践**：阿里 ACK、华为 CCE、腾讯 TKE 都是 K8s 托管服务。大厂在 K8s 之上还会做：Service Mesh（Istio/Linkerd）做流量治理、Operator 做有状态应用管理、Knative 做 Serverless。

### 2.3 CI/CD 持续集成与部署

*GitHub Actions / Jenkins*

#### CI/CD 流水线设计

```text
代码推送 → 代码检查 → 单元测试 → 构建 Docker 镜像 → 推送镜像仓库
    → 部署到 Staging → 集成测试 → 人工审批 → 部署到 Production
    → 健康检查 → 流量切换（灰度）→ 旧版本下线
```

#### GitHub Actions 示例

```yaml
name: Build and Deploy

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4

    - name: Set up JDK 11
      uses: actions/setup-java@v4
      with:
        java-version: '11'
        distribution: 'temurin'

    - name: Cache Maven
      uses: actions/cache@v3
      with:
        path: ~/.m2
        key: ${{ runner.os }}-m2-${{ hashFiles('pom.xml') }}

    - name: Build
      run: mvn package -DskipTests

    - name: Run Tests
      run: mvn test

    - name: Build Docker Image
      run: docker build -t hmdp:${{ github.sha }} .

    - name: Push to Registry
      run: |
        docker tag hmdp:${{ github.sha }} $REGISTRY/hmdp:${{ github.sha }}
        docker push $REGISTRY/hmdp:${{ github.sha }}

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
    - name: Deploy to K8s
      run: |
        kubectl set image deployment/hmdp-backend \
          backend=$REGISTRY/hmdp:${{ github.sha }}
        kubectl rollout status deployment/hmdp-backend
```

#### 工具选型对比

| 工具 | 适用场景 | 特点 |
| --- | --- | --- |
| GitHub Actions | 开源项目 / GitHub 仓库 | 免运维、生态丰富、免费额度 |
| GitLab CI | 私有化部署 | 与 GitLab 一体化、.gitlab-ci.yml |
| Jenkins | 传统企业 / 复杂流水线 | 插件最多、学习成本高、需运维 |
| ArgoCD | K8s GitOps | Git 作为唯一真相源、声明式部署 |

### 2.4 监控与可观测性

*Metrics + Logging + Tracing*

#### 可观测性三支柱

| 维度 | 回答的问题 | 工具栈 | 本项目指标 |
| --- | --- | --- | --- |
| **Metrics** | 系统在发生什么？（聚合数据） | Prometheus + Grafana | QPS、RT、错误率、缓存命中率 |
| **Logging** | 具体发生了什么？（明细） | ELK / Loki + Grafana | 异常日志、慢查询、MQ 消费失败 |
| **Tracing** | 请求经过了哪里？（链路） | SkyWalking / Jaeger | 秒杀请求 → Redis → MQ → DB 全链路 |

#### Spring Boot Actuator + Prometheus 集成

```yaml
# application.yaml
management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics,prometheus
  metrics:
    tags:
      application: hmdp-backend
    export:
      prometheus:
        enabled: true
```

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'hmdp-backend'
    metrics_path: '/actuator/prometheus'
    static_configs:
      - targets: ['hmdp-backend:8081']
```

#### 关键监控指标（RED 方法）

- **Rate（速率）**：每秒请求数（QPS），按接口分组
- **Errors（错误）**：HTTP 5xx 比例、异常率
- **Duration（延迟）**：P50/P95/P99 响应时间
- **业务指标**：缓存命中率、秒杀成功率、MQ 消费延迟、订单状态分布

#### 告警规则示例

```yaml
# Prometheus AlertManager
groups:
- name: hmdp-alerts
  rules:
  - alert: HighErrorRate
    expr: |
      rate(http_server_requests_seconds_count{status=~"5.."}[5m])
      / rate(http_server_requests_seconds_count[5m]) > 0.05
    for: 2m
    labels: { severity: critical }
    annotations:
      summary: "错误率超过 5%"

  - alert: RedisDown
    expr: redis_up == 0
    for: 30s
    labels: { severity: critical }

  - alert: MQConsumerLag
    expr: rabbitmq_queue_messages_ready > 10000
    for: 5m
    labels: { severity: warning }
    annotations:
      summary: "MQ 消息积压超过 1 万"
```

### 2.5 配置中心与环境管理

*Nacos / Apollo*

#### 为什么需要配置中心

- **环境隔离**：dev/test/prod 配置不同，不用改代码
- **动态刷新**：修改配置不重启服务（如限流阈值、熔断策略）
- **版本管理**：配置变更可回滚，有审计日志
- **统一管理**：多服务共享配置，避免散落各处

#### 方案对比

| 方案 | 公司 | 特点 |
| --- | --- | --- |
| Nacos | 阿里 | 配置 + 注册中心一体，Spring Cloud 原生支持 |
| Apollo | 携程 | 配置中心专业方案，UI 完善，权限管理强 |
| K8s ConfigMap | 原生 | 简单轻量，无动态刷新（需 Operator） |
| AWS Parameter Store | 亚马逊 | 云原生集成，按需付费 |

#### 本项目配置拆分

```yaml
# Nacos 配置分组
Group: HMDP
  Data ID: hmdp-common.yaml    # 公共配置（Redis、MQ 地址）
  Data ID: hmdp-db.yaml        # 数据库配置（分环境）
  Data ID: hmdp-redis.yaml     # Redis 配置
  Data ID: hmdp-mq.yaml        # RabbitMQ 配置
  Data ID: hmdp-agent.yaml     # Agent 配置（LLM API Key、模型参数）

Namespace:
  - dev                        # 开发环境
  - test                       # 测试环境
  - prod                       # 生产环境
```

### 2.6 灰度发布与流量控制

*蓝绿 / 金丝雀 / 流量染色*

#### 发布策略对比

| 策略 | 原理 | 适用场景 | 风险 |
| --- | --- | --- | --- |
| **滚动更新** | 逐个替换 Pod，新旧共存 | K8s 默认策略 | 回滚慢 |
| **蓝绿部署** | 两套环境，瞬时切换 | 需要双倍资源 | 资源成本高 |
| **金丝雀发布** | 先放 5% 流量到新版本 | 大厂标配 | 需要流量控制能力 |
| **流量染色** | 特定标记的请求路由到新版本 | 全链路灰度 | 需要网关 + 链路透传 |

#### 金丝雀发布 K8s 实现

```yaml
# 两套 Deployment：v1（稳定版）和 v2（灰度版）
# 用 Service 的 selector + weight 控制流量分配

# 方案 1：K8s 原生（通过 Pod 副本数比例）
# v1: 19 replicas, v2: 1 replica → v2 承担 ~5% 流量

# 方案 2：Nginx Ingress（精确流量比例）
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: hmdp-canary
  annotations:
    nginx.ingress.kubernetes.io/canary: "true"
    nginx.ingress.kubernetes.io/canary-weight: "5"   # 5% 流量到灰度
spec:
  rules:
  - http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: hmdp-backend-v2
            port:
              number: 80
```

#### 流量染色（全链路灰度）

大厂做全链路灰度的核心思路：

1. 网关给灰度请求打上 `X-Gray: true` 的 Header
2. 下游服务通过链路追踪（如 SkyWalking）透传这个 Header
3. 每个服务根据 Header 路由到对应的灰度版本
4. 灰度流量只读灰度 Redis/DB（通过影子库或标记隔离）

阿里内部叫"全链路压测标记"，用相同的机制做线上压测——打标的请求走影子库，不影响真实数据。

### 2.7 压测与容量规划

*JMeter / wrk / 全链路压测*

#### 压测工具选型

| 工具 | 适用场景 | 特点 |
| --- | --- | --- |
| JMeter | HTTP 接口 / 复杂场景 | GUI 操作、插件丰富、支持分布式 |
| wrk | 快速 HTTP 压测 | 轻量、单机可打 10 万+ QPS |
| Gatling | 高并发场景 | Scala DSL、报告精美、基于 Netty |
| Locust | Python 场景 | Python 脚本、分布式、Web UI |

#### 容量规划方法论

- **单机容量**：找到单实例的 QPS 上限（逐步加压直到 RT 飙升或错误率上升）
- **容量公式**：所需实例数 = 目标 QPS ÷ 单机 QPS × 安全系数（1.5-2）
- **水位监控**：CPU < 70%、内存 < 80%、线程池 < 80%、RT P99 < 200ms
- **全链路压测**：模拟真实用户路径（首页 → 搜索 → 秒杀 → 支付），发现链路瓶颈

> **大厂压测实践**：阿里双 11 前做全链路压测，用"影子库 + 影子队列 + 压测标记"隔离压测流量和真实流量。字节的 Profiler 做线上性能采样，发现慢接口自动告警。

#### 本项目压测要点

- **秒杀接口**：用 wrk 压 `POST /api/voucher-order/seckill/{id}`，观察 Redis QPS、MQ 积压、DB 写入速度
- **缓存查询**：对比有缓存和无缓存的 RT 差异（预期 10-100 倍）
- **熔断器**：模拟下游超时，观察熔断器状态转换（CLOSED → OPEN → HALF_OPEN）
- **限流器**：超 QPS 阈值时返回 429，观察令牌桶预消费行为

---

## 总结：从项目到生产的完整路径

#### 技术能力的可迁移性

本项目的 9 个核心技术模式，覆盖了大厂面试中最高频的考察领域。这些模式的底层逻辑（限流 → 缓存 → 异步 → 削峰）是通用的，不同的只是具体的中间件选型和规模。

#### 工程能力的补全路径

| 阶段 | 做什么 | 产出 |
| --- | --- | --- |
| **1. 本地跑通** | Docker Compose 一键启动所有依赖 | docker-compose.yml |
| **2. 镜像化** | 写 Dockerfile，构建镜像推到仓库 | Dockerfile + CI/CD Pipeline |
| **3. K8s 部署** | 写 Deployment/Service/HPA 清单 | k8s/ 目录下的 YAML |
| **4. 监控接入** | Actuator + Prometheus + Grafana | 监控大盘 + 告警规则 |
| **5. 灰度发布** | Ingress 金丝雀 + 流量染色 | 灰度发布脚本 |
| **6. 压测验证** | 单机容量 → 集群容量 → 全链路 | 压测报告 + 容量规划 |

> **面试一句话总结**：这个项目不仅实现了高并发秒杀和 AI Agent 推荐的业务逻辑，还具备了从 Docker 容器化 → K8s 编排 → CI/CD 自动化 → Prometheus 监控 → 灰度发布的完整工程化能力，是一个"能上生产"的项目，而不是一个"只能跑在本地"的 demo。
