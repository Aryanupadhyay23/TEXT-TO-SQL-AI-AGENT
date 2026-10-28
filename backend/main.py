import sys
import asyncio

# On Windows, SelectorEventLoop is required for asyncmy with SSL
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except (RuntimeError, AttributeError):
        pass

import logging
import os
from logging.handlers import RotatingFileHandler

from conf.app import app
from chatbot.routes import router as chatbot_router

# Create hidden .logs directory so watchfiles ignores log file modifications
os.makedirs(".logs", exist_ok=True)

# Configure logging with rotation (10MB max size, keep 5 backups)
log_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

file_handler = RotatingFileHandler(".logs/chatbot.log", maxBytes=10 * 1024 * 1024, backupCount=5)
file_handler.setFormatter(log_formatter)
file_handler.addFilter(lambda record: not record.name.startswith("watchfiles"))

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

# Apply to root logger so all app loggers inherit this
logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])
watchfiles_logger = logging.getLogger("watchfiles")
watchfiles_logger.setLevel(logging.WARNING)
watchfiles_logger.propagate = False
watchfiles_main_logger = logging.getLogger("watchfiles.main")
watchfiles_main_logger.setLevel(logging.WARNING)
watchfiles_main_logger.propagate = False

# Include Chatbot API routers (/api/chat)
app.include_router(chatbot_router)

# Health check endpoints
@app.get("/")
async def read_root():
    return {"status": "online", "detail": "Standalone Chatbot API is running."}

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "chatbot-api"}
