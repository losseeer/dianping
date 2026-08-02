import os
from dotenv import load_dotenv

load_dotenv()


class Config:
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

    # Agent1（Agent2 调用 Agent1 API 时需要）
    AGENT1_PORT: int = int(os.getenv("AGENT1_PORT", "8001"))

    # Agent2
    AGENT2_PORT: int = int(os.getenv("AGENT2_PORT", "8002"))
    AGENT2_MAX_CANDIDATES_FOOD: int = int(os.getenv("AGENT2_MAX_CANDIDATES_FOOD", "20"))
    AGENT2_MAX_CANDIDATES_OTHER: int = int(os.getenv("AGENT2_MAX_CANDIDATES_OTHER", "10"))
    AGENT2_MIN_CANDIDATES: int = int(os.getenv("AGENT2_MIN_CANDIDATES", "3"))
    AGENT2_MAX_ITERATIONS: int = int(os.getenv("AGENT2_MAX_ITERATIONS", "3"))

    # Memory
    MEMORY_KEY_PREFIX: str = os.getenv("MEMORY_KEY_PREFIX", "user:")
    MEMORY_EXPIRY_DAYS: int = int(os.getenv("MEMORY_EXPIRY_DAYS", "90"))

    # 短期记忆：会话级上下文（Redis 缓存层，MySQL 为 source of truth）
    CONVERSATION_KEY_PREFIX: str = os.getenv("CONVERSATION_KEY_PREFIX", "agent2:conversation:")
    CONVERSATION_MAX_TURNS: int = int(os.getenv("CONVERSATION_MAX_TURNS", "30"))

    # Trajectory Store (Layer 3)
    TRAJECTORY_KEY_PREFIX: str = os.getenv("TRAJECTORY_KEY_PREFIX", "agent2:trajectory:")
    TRAJECTORY_EXPIRY_DAYS: int = int(os.getenv("TRAJECTORY_EXPIRY_DAYS", "30"))
    TRAJECTORY_MAX_RECENT: int = int(os.getenv("TRAJECTORY_MAX_RECENT", "100"))

    # Playbook (Layer 2 - ACE)
    PLAYBOOK_KEY: str = os.getenv("PLAYBOOK_KEY", "agent2:playbook")
    PLAYBOOK_MAX_ENTRIES: int = int(os.getenv("PLAYBOOK_MAX_ENTRIES", "200"))
    PLAYBOOK_REFLECTION_THRESHOLD: float = float(os.getenv("PLAYBOOK_REFLECTION_THRESHOLD", "6.0"))

    # Token 限制（防止 prompt 膨胀 / 成本爆炸）
    # 保守估算: 中文 ≈1.5 字符/token，按 2 字符/token 估算
    TOKEN_CHARS_PER_TOKEN: int = int(os.getenv("TOKEN_CHARS_PER_TOKEN", "2"))
    TOKEN_MAX_PER_REQUEST: int = int(os.getenv("TOKEN_MAX_PER_REQUEST", "30000"))
    TOKEN_MAX_CANDIDATES_IN_PROMPT: int = int(os.getenv("TOKEN_MAX_CANDIDATES_IN_PROMPT", "10"))
    TOKEN_MAX_REVIEW_SUMMARY_CHARS: int = int(os.getenv("TOKEN_MAX_REVIEW_SUMMARY_CHARS", "300"))
    TOKEN_MAX_CONVERSATION_CHARS: int = int(os.getenv("TOKEN_MAX_CONVERSATION_CHARS", "1500"))

    # Self-Improvement (Layer 4)
    SELF_IMPROVE_MIN_TRAJECTORIES: int = int(os.getenv("SELF_IMPROVE_MIN_TRAJECTORIES", "5"))
    SELF_IMPROVE_HELD_OUT_RATIO: float = float(os.getenv("SELF_IMPROVE_HELD_OUT_RATIO", "0.3"))

    # Benchmark
    EVAL_KEY_PREFIX: str = os.getenv("EVAL_KEY_PREFIX", "agent2:eval:")


config = Config()
