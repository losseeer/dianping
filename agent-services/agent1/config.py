import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Java 后端
    JAVA_API_BASE_URL: str = os.getenv("JAVA_API_BASE_URL", "http://localhost:8081")

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "127.0.0.1")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))

    # LLM
    LLM_API_BASE: str = os.getenv("LLM_API_BASE", "https://api.openai.com/v1")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")

    # Agent1
    AGENT1_PORT: int = int(os.getenv("AGENT1_PORT", "8001"))
    AGENT1_CACHE_TTL: int = int(os.getenv("AGENT1_CACHE_TTL", "1800"))


config = Config()
