"""Application and Database Settings Configuration."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load single .env.tts file from backend root
backend_env = Path(__file__).resolve().parent.parent.parent / ".env.tts"
if backend_env.exists():
    load_dotenv(dotenv_path=backend_env, override=True)
else:
    load_dotenv()


def _to_bool(val: str, default: bool = True) -> bool:
    """Safely converts string values ('true', 'yes', '1', 'false', 'no', '0') to boolean."""
    if val is None:
        return default
    return str(val).strip().lower() in ("true", "1", "yes", "on")


def _to_int(val: str, default: int = 100) -> int:
    """Safely parses integers with a fallback default."""
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _to_float(val: str, default: float = 0.5) -> float:
    """Safely parses floats with a fallback default."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


class Settings:
    """Database and application configuration loaded from environment variables."""

    # Database connection parameters loaded from backend/.env
    DB_HOST: str = os.getenv("CHATBOT_DB_HOST") or os.getenv("DB_HOST", "localhost")
    DB_PORT: int = _to_int(os.getenv("CHATBOT_DB_PORT") or os.getenv("DB_PORT"), 3306)
    DB_NAME: str = os.getenv("CHATBOT_DB_NAME") or os.getenv("DB_NAME", "ecommerce_db")
    DB_USER: str = os.getenv("CHATBOT_DB_USER") or os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("CHATBOT_DB_PASSWORD") or os.getenv("CHATBOT_DB_PASS") or os.getenv("DB_PASSWORD", "")
    DB_SSL: bool = _to_bool(os.getenv("CHATBOT_DB_SSL", "true" if "aivencloud" in (os.getenv("CHATBOT_DB_HOST") or "") else "false"))
    DB_SSL_CA: str = os.getenv("CHATBOT_DB_SSL_CA", "")

    # Security and guardrail configurations
    DB_READ_ONLY: bool = _to_bool(os.getenv("DB_READ_ONLY"), True)
    DB_TIMEOUT_SECONDS: int = _to_int(os.getenv("DB_TIMEOUT_SECONDS"), 10)
    MAX_SQL_RETRIES: int = _to_int(os.getenv("MAX_SQL_RETRIES") or os.getenv("CHATBOT_MAX_RETRIES"), 6)

    # Row Limit Permissions (Admin controlled)
    ENABLE_ROW_LIMIT: bool = _to_bool(os.getenv("ENABLE_ROW_LIMIT"), True)
    DB_MAX_ROWS: int = _to_int(os.getenv("DB_MAX_ROWS"), 100)
    LLM_MAX_ROWS_CONTEXT: int = _to_int(os.getenv("LLM_MAX_ROWS_CONTEXT"), 30)

    # Single LLM Configuration (Used for all use cases)
    LLM_PROVIDER: str = (
        os.getenv("LLM_PROVIDER")
        or os.getenv("UNIFIED_LLM_PROVIDER")
        or os.getenv("REASONING_LLM_PROVIDER")
        or "ollama"
    )
    LLM_MODEL: str = (
        os.getenv("OLLAMA_MODEL")
        or os.getenv("LLM_MODEL")
        or os.getenv("UNIFIED_LLM_MODEL")
        or os.getenv("REASONING_LLM_MODEL")
        or "gemma4:31b-cloud"
    )
    OLLAMA_NUM_CTX: int = _to_int(os.getenv("OLLAMA_NUM_CTX") or os.getenv("LLM_NUM_CTX"), 131072)

    # API Keys & Endpoints
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST") or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL") or os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_API_KEY_ONE: str = os.getenv("OLLAMA_API_KEY_ONE", "")
    OLLAMA_API_KEY_SECOND: str = os.getenv("OLLAMA_API_KEY_SECOND", "")
    OLLAMA_API_KEY_THIRD: str = os.getenv("OLLAMA_API_KEY_THIRD", "")
    OLLAMA_API_KEY: str = (
        os.getenv("OLLAMA_API_KEY_ONE")
        or os.getenv("OLLAMA_API_KEY", "")
    )

    @property
    def ollama_api_keys(self) -> list[str]:
        """Returns non-empty Ollama API keys in fallback priority order."""
        candidates = [
            self.OLLAMA_API_KEY_ONE,
            self.OLLAMA_API_KEY_SECOND,
            self.OLLAMA_API_KEY_THIRD,
            os.getenv("OLLAMA_API_KEY", ""),
        ]
        keys: list[str] = []
        for k in candidates:
            k_clean = (k or "").strip()
            if k_clean and k_clean not in keys:
                keys.append(k_clean)
        return keys

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # Nomic Embedding Configuration
    EMBEDDING_MODEL_KEY: str = os.getenv("EMBEDDING_MODEL_KEY", "")
    EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME", "nomic-embed-text-v1.5")
    EMBEDDING_BASE_URL: str = os.getenv("EMBEDDING_BASE_URL", "https://nomicapi.duckdns.org/v1")
    EMBEDDING_CHUNK_SIZE: int = _to_int(os.getenv("EMBEDDING_CHUNK_SIZE"), 10)
    EMBEDDING_DIMENSION: int = _to_int(os.getenv("EMBEDDING_DIMENSION"), 768)

    # Retrieval Settings (Top-K per store)
    RETRIEVAL_TOP_K: int = _to_int(os.getenv("RETRIEVAL_TOP_K"), 5)
    RETRIEVAL_TOP_K_SQL_PAIRS: int = _to_int(
        os.getenv("RETRIEVAL_TOP_K_SQL_PAIRS") or os.getenv("RETRIEVAL_TOP_K"), 5
    )
    RETRIEVAL_TOP_K_RULES: int = _to_int(
        os.getenv("RETRIEVAL_TOP_K_RULES") or os.getenv("RETRIEVAL_TOP_K"), 5
    )
    RETRIEVAL_TOP_K_TABLES: int = _to_int(
        os.getenv("RETRIEVAL_TOP_K_TABLES") or os.getenv("RETRIEVAL_TOP_K"), 5
    )

    # Retrieval Hybrid RRF Fusion Weights (Controlled via .env)
    RETRIEVAL_SEMANTIC_WEIGHT: float = _to_float(os.getenv("RETRIEVAL_SEMANTIC_WEIGHT"), 0.5)
    RETRIEVAL_BM25_WEIGHT: float = _to_float(os.getenv("RETRIEVAL_BM25_WEIGHT"), 0.5)
    RETRIEVAL_RRF_C: int = _to_int(os.getenv("RETRIEVAL_RRF_C"), 60)

    # Server API Settings
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = _to_int(os.getenv("API_PORT"), 8000)

    # Checkpointer & Conversation Memory Settings
    SQLITE_CHECKPOINT_PATH: str = os.getenv("SQLITE_CHECKPOINT_PATH", "chatbot/data/checkpoints.sqlite")
    UPSTASH_REDIS_REST_URL: str = os.getenv("UPSTASH_REDIS_REST_URL", "")
    UPSTASH_REDIS_REST_TOKEN: str = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")

    # EC2 Reverse Proxy & Port Settings
    FASTAPI_ROOT_PATH: str = os.getenv("FASTAPI_ROOT_PATH", "/chatbot-backend")
    HOST_PORT_FRONTEND: int = _to_int(os.getenv("HOST_PORT_FRONTEND"), 8503)
    HOST_PORT_BACKEND: int = _to_int(os.getenv("HOST_PORT_BACKEND"), 8002)


settings = Settings()
