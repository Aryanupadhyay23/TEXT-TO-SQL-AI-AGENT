import os
from pathlib import Path
from dotenv import load_dotenv

# Load universal .env.tts file
_conf_dir = Path(__file__).resolve().parent
_backend_dir = _conf_dir.parent
_root_dir = _backend_dir.parent

_root_env_tts = _root_dir / ".env.tts"
_backend_env_tts = _backend_dir / ".env.tts"

if _root_env_tts.exists():
    load_dotenv(dotenv_path=_root_env_tts, override=True)
elif _backend_env_tts.exists():
    load_dotenv(dotenv_path=_backend_env_tts, override=True)
else:
    load_dotenv(override=True)

# Chatbot Database settings
CHATBOT_DB_NAME = os.getenv("CHATBOT_DB_NAME", "ecommerce_db")
CHATBOT_DB_USER = os.getenv("CHATBOT_DB_USER", "root")
CHATBOT_DB_PASS = os.getenv("CHATBOT_DB_PASSWORD") or os.getenv("CHATBOT_DB_PASS", "")
CHATBOT_DB_HOST = os.getenv("CHATBOT_DB_HOST", "localhost")
CHATBOT_DB_PORT = int(os.getenv("CHATBOT_DB_PORT", "3306"))
CHATBOT_DB_SSL = os.getenv("CHATBOT_DB_SSL", "true" if "aivencloud" in (os.getenv("CHATBOT_DB_HOST") or "") else "false").lower() in ("true", "1", "yes", "required")
CHATBOT_DB_SSL_CA = os.getenv("CHATBOT_DB_SSL_CA", "")
CHATBOT_DB_TIMEOUT = int(os.getenv("CHATBOT_DB_TIMEOUT") or os.getenv("DB_TIMEOUT_SECONDS") or "10")

# Fallback generic DB vars
DB_NAME = CHATBOT_DB_NAME
DB_USER = CHATBOT_DB_USER
DB_PASS = CHATBOT_DB_PASS
DB_HOST = CHATBOT_DB_HOST
DB_PORT = CHATBOT_DB_PORT
DB_SSL = CHATBOT_DB_SSL

# CORS
_allow_origins = os.getenv("ALLOW_ORIGINS", "https://aryan-projects.duckdns.org,http://aryan-projects.duckdns.org,http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000,http://localhost:5174,http://127.0.0.1:5174")
ALLOW_ORIGINS = [origin.strip() for origin in _allow_origins.split(",") if origin.strip()]

# EC2 Reverse Proxy & Port Settings
FASTAPI_ROOT_PATH = os.getenv("FASTAPI_ROOT_PATH", "/chatbot-backend")
HOST_PORT_FRONTEND = int(os.getenv("HOST_PORT_FRONTEND", "8503"))
HOST_PORT_BACKEND = int(os.getenv("HOST_PORT_BACKEND", "8002"))
