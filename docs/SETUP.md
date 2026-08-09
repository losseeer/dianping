# 🛠️ 黑马点评 — 中间件与开发环境配置指南

> 本文档涵盖项目运行所需的全部中间件安装与配置说明，包括 MySQL、Redis、RabbitMQ、Elasticsearch 以及 LLM API。

---

## 目录

- [1. 前置环境](#1-前置环境)
- [2. MySQL](#2-mysql)
- [3. Redis](#3-redis)
- [4. RabbitMQ](#4-rabbitmq)
- [5. Elasticsearch](#5-elasticsearch)
- [6. LLM API（OpenAI 兼容）](#6-llm-apiopenai-兼容)
- [7. Python Agent 服务](#7-python-agent-服务)
- [8. 快速启动检查清单](#8-快速启动检查清单)
- [9. 端口与凭证速查表](#9-端口与凭证速查表)

---

## 1. 前置环境

### 1.1 Java 8

```bash
# macOS (已内置 JDK 1.8 则跳过)
export JAVA_HOME=/Library/Java/JavaVirtualMachines/jdk-1.8.jdk/Contents/Home
export PATH=$JAVA_HOME/bin:$PATH
```

### 1.2 Maven

```bash
# 已安装到 ~/maven，确认可用：
~/maven/bin/mvn --version
```

> 注意：新的终端窗口需执行 `source ~/.zshrc` 使环境变量生效。

---

## 2. MySQL

### 2.1 安装

```bash
# macOS（Homebrew）
brew install mysql@8.0
brew services start mysql@8.0

# 或 Docker（推荐，一键可用）
docker run -d --name mysql \
  -p 3306:3306 \
  -e MYSQL_ALLOW_EMPTY_PASSWORD=yes \
  -e MYSQL_DATABASE=dingping \
  mysql:8.0
```

### 2.2 初始化数据库

```bash
# 导入后端基础表（tb_shop / tb_user / tb_voucher 等）
mysql -h 127.0.0.1 -u root dingping < sql/backend/schema/001_core.sql

# 导入支付 & 搜索模块表（tb_pay_log 等）
mysql -h 127.0.0.1 -u root dingping < sql/backend/schema/002_payment_and_search.sql

# 导入 Agent2 相关表（tb_agent_preferences / tb_agent_playbook / tb_agent_conversations）
mysql -h 127.0.0.1 -u root dingping < sql/agent2/schema/001_agent_tables.sql

# 可选：导入后端测试数据
mysql -h 127.0.0.1 -u root dingping < sql/backend/data/001_test_data.sql
```

Agent1 当前不持有独立 MySQL 表，详见 `sql/agent1/schema/README.md`。

### 2.3 配置位置

| 配置项 | 值 |
|--------|-----|
| 地址 | `127.0.0.1:3306` |
| 数据库 | `dingping` |
| 用户名 | `root` |
| 密码 | 无（本地开发） |

> 修改配置：`src/main/resources/application.yaml` → `spring.datasource`

---

## 3. Redis

### 3.1 安装

```bash
# macOS（Homebrew）
brew install redis
brew services start redis

# 或 Docker
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

### 3.2 验证

```bash
redis-cli ping
# 应返回 PONG
```

### 3.3 配置位置

| 配置项 | 文件 |
|--------|------|
| Spring Data Redis | `src/main/resources/application.yaml` → `spring.redis` |
| Redisson（分布式锁） | `src/main/java/com/hmdp/config/RedissonConfig.java` |
| Python Agent | `agent-services/agent1/.env` / `agent-services/agent2/.env` |

> 默认地址 `127.0.0.1:6379`，无密码。

---

## 4. RabbitMQ

### 4.1 安装

```bash
# macOS（Homebrew）
brew install rabbitmq
brew services start rabbitmq

# 或 Docker（含管理面板）
docker run -d --name rabbitmq \
  -p 5672:5672 -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=guest \
  -e RABBITMQ_DEFAULT_PASS=guest \
  rabbitmq:3-management
```

### 4.2 验证

- 管理面板：http://localhost:15672 （用户名/密码：`guest`/`guest`）
- 端口 `5672` 正常监听即可

### 4.3 用途

- **秒杀异步下单**：Lua 脚本预检通过后发 MQ 消息，异步落库
- **订单超时取消**：死信队列 + TTL 实现 30 分钟延迟取消
- **支付通知**：异步推送（短信/App Push）

> 队列定义：`src/main/java/com/hmdp/config/QueueConfig.java`

---

## 5. Elasticsearch

### 5.1 安装

```bash
# macOS（Homebrew）
brew install elasticsearch
brew services start elasticsearch

# 或 Docker（单节点，适合开发）
docker run -d --name es \
  -p 9200:9200 -p 9300:9300 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  elasticsearch:7.17.0
```

### 5.2 安装 IK 分词器（可选）

IK 分词器提升中文搜索精度。如果 GitHub Release 不可用，可跳过——ES 标准分词器也能工作。

```bash
# 本地下载后手动安装
curl -L -o /tmp/ik.zip "https://github.com/infinilabs/analysis-ik/releases/download/v7.17.0/elasticsearch-analysis-ik-7.17.0.zip"
docker cp /tmp/ik.zip es:/tmp/
docker exec es elasticsearch-plugin install file:///tmp/elasticsearch-analysis-ik-7.17.0.zip
docker restart es
```

### 5.3 同步数据

启动 Java 后端后，调用同步接口：

```bash
curl -X POST http://localhost:8081/shop/search/sync
```

或通过 `ShopSearchController` 的单条导入接口逐条同步。

### 5.4 配置位置

- `src/main/resources/application.yaml` → `elasticsearch.rest.uris`
- 文档映射：`src/main/java/com/hmdp/document/ShopDoc.java`
- Repository：`src/main/java/com/hmdp/repository/ShopDocRepository.java`

---

## 6. LLM API（OpenAI 兼容）

项目中的 Python Agent 服务（Agent1 / Agent2）依赖 LLM 进行评价分析和推荐推理。

### 6.1 支持的 LLM 提供商

任何兼容 OpenAI Chat Completions API 的服务均可使用，包括：

| 提供商 | API Base URL |
|--------|-------------|
| OpenAI 官方 | `https://api.openai.com/v1` |
| Azure OpenAI | `https://<your-resource>.openai.azure.com/` |
| DeepSeek | `https://api.deepseek.com/v1` |
| 通义千问（阿里云） | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 本地 Ollama | `http://localhost:11434/v1` |
| 其他兼容代理 | 自定义地址 |

### 6.2 配置方式

在每个 Agent 目录下创建 `.env` 文件：

```bash
# agent-services/agent1/.env
LLM_API_BASE=https://api.openai.com/v1
LLM_API_KEY=sk-your-api-key-here
LLM_MODEL=gpt-4o-mini
```

```bash
# agent-services/agent2/.env
LLM_API_BASE=https://api.openai.com/v1
LLM_API_KEY=sk-your-api-key-here
LLM_MODEL=gpt-4o-mini
```

> 参考示例：`agent-services/agent1/.env.example`、`agent-services/agent2/.env.example`

### 6.3 推荐的模型选择

| 场景 | 推荐模型 | 理由 |
|------|---------|------|
| 评价情感分析（Agent1） | `gpt-4o-mini` / `deepseek-chat` | 速度快、成本低，分类任务够用 |
| 推荐推理（Agent2） | `gpt-4o` / `deepseek-chat` | 需要较强的推理能力 |

---

## 7. Python Agent 服务

### 7.1 环境准备

```bash
cd agent-services

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 7.2 配置 .env 文件

```bash
# 方式一：手动复制并编辑
cp agent1/.env.example agent1/.env
cp agent2/.env.example agent2/.env
vim agent1/.env   # 填写 LLM_API_KEY
vim agent2/.env   # 填写 LLM_API_KEY

# 方式二：一键启动脚本会自动处理
bash start.sh
```

### 7.3 启动服务

```bash
# 一键启动两个 Agent
bash start.sh

# 或分别启动
cd agent1 && python main.py &     # → http://localhost:8001
cd agent2 && python main.py &     # → http://localhost:8002
```

### 7.4 Agent 端口说明

| Agent | 端口 | 功能 |
|-------|------|------|
| Agent1 | `8001` | 评价摘要 — 情感分析 + 统计汇总 + LLM 综合建议 |
| Agent2 | `8002` | 店铺推荐 — 多轮对话 + HITL + Playbook + 记忆系统 |

---

## 8. 快速启动检查清单

按顺序执行，确保每步通过后再进入下一步：

```
□ 1. MySQL    → mysql -h 127.0.0.1 -u root -p290390 dingping -e "SELECT 1"
□ 2. Redis    → redis-cli ping                        → PONG
□ 3. RabbitMQ → curl -s http://localhost:15672        → 管理页面可访问
□ 4. ES       → curl -s http://localhost:9200          → 返回 JSON
□ 5. LLM Key  → 已填写 agent1/.env 和 agent2/.env
```

全部通过后：

```bash
# 终端 1：启动 Java 后端
export JAVA_HOME=/Library/Java/JavaVirtualMachines/jdk-1.8.jdk/Contents/Home
~/maven/bin/mvn spring-boot:run

# 终端 2：启动 Python Agent
cd agent-services && bash start.sh
```

---

## 9. 端口与凭证速查表

| 中间件 | 端口 | 用户名 | 密码 | 备注 |
|--------|------|--------|------|------|
| **Java 后端** | `8081` | — | — | Spring Boot 主服务 |
| **MySQL** | `3306` | `root` | `290390` | 数据库 `dingping` |
| **Redis** | `6379` | — | — | 缓存 + 分布式锁 + 消息队列 |
| **RabbitMQ** | `5672` | `guest` | `guest` | 管理面板 `15672` |
| **Elasticsearch** | `9200` | — | — | 集群通信 `9300` |
| **Agent1** | `8001` | — | — | 评价摘要服务 |
| **Agent2** | `8002` | — | — | 店铺推荐服务 |
| **LLM API** | 取决于提供商 | `sk-xxx` | — | 在各自 `.env` 中配置 |

---

> 📌 **提示**：如果仅需运行 Java 后端核心功能（不涉及 Agent 和 ES），只需启动 **MySQL + Redis + RabbitMQ** 三者即可。
