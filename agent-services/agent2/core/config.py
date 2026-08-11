import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # --- 环境配置（.env 读取，部署时修改） ---

    # Java 后端
    JAVA_API_BASE_URL: str = os.getenv("JAVA_API_BASE_URL", "http://localhost:8081")

    # MySQL（长期记忆持久化）
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "dingping")

    # Redis（缓存层）
    REDIS_HOST: str = os.getenv("REDIS_HOST", "127.0.0.1")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))

    # LLM
    LLM_API_BASE: str = os.getenv("LLM_API_BASE", "https://api.openai.com/v1")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")

    # Agent 端口
    AGENT1_PORT: int = int(os.getenv("AGENT1_PORT", "8001"))
    AGENT2_PORT: int = int(os.getenv("AGENT2_PORT", "8002"))

    # --- 业务常量（代码级默认值，不暴露到 .env） ---

    # Agent2 ReAct 工作流参数
    AGENT2_MAX_CANDIDATES_FOOD: int = 20
    AGENT2_MAX_CANDIDATES_OTHER: int = 10
    AGENT2_MIN_CANDIDATES: int = 3
    AGENT2_MAX_ITERATIONS: int = 3

    # Memory: 用户偏好（中期记忆）
    MEMORY_KEY_PREFIX: str = "user:"
    MEMORY_EXPIRY_DAYS: int = 90

    # 短期记忆：会话级上下文
    CONVERSATION_KEY_PREFIX: str = "agent2:conversation:"
    CONVERSATION_MAX_TURNS: int = 30
    CONVERSATION_TTL_HOURS: int = 24

    # Trajectory Store（可观测性）
    TRAJECTORY_KEY_PREFIX: str = "agent2:trajectory:"
    TRAJECTORY_EXPIRY_DAYS: int = 30
    TRAJECTORY_MAX_RECENT: int = 100

    # Playbook（经验上下文 ACE）
    PLAYBOOK_KEY: str = "agent2:playbook"
    PLAYBOOK_MAX_ENTRIES: int = 200
    PLAYBOOK_REFLECTION_THRESHOLD: float = 6.0
    PLAYBOOK_MIN_NOVELTY: float = 0.5  # 经验条目 confidence 门槛，低于此值不入选（confidence 范围 0.0-1.0）

    # Token 限制（防止 prompt 膨胀）
    TOKEN_CHARS_PER_TOKEN: int = 2
    TOKEN_MAX_PER_REQUEST: int = 30000
    TOKEN_MAX_CANDIDATES_IN_PROMPT: int = 10
    TOKEN_MAX_REVIEW_SUMMARY_CHARS: int = 300
    TOKEN_MAX_CONVERSATION_CHARS: int = 1500

    # Self-Improvement（自进化引擎）
    SELF_IMPROVE_MIN_TRAJECTORIES: int = 5
    SELF_IMPROVE_HELD_OUT_RATIO: float = 0.3

    # Eval
    EVAL_KEY_PREFIX: str = "agent2:eval:"

    # ChromaDB 向量持久化路径（包外目录，避免运行时数据混入源码）
    CHROMA_PERSIST_DIR: str = os.getenv(
        "CHROMA_PERSIST_DIR",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "chroma")
    )


config = Config()
