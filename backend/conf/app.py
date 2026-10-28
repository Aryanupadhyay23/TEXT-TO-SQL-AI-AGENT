import logging
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from conf.database import chatbot_db_manager
from conf.settings import ALLOW_ORIGINS

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup event: Initialize database connection pool & HTTP client pool
    try:
        await chatbot_db_manager.init(raise_on_fail=False)
    except Exception:
        logger.warning("Chatbot DB init failed during startup", exc_info=True)

    app.state.http_client = httpx.AsyncClient(timeout=10.0)

    yield

    # Shutdown event: Close HTTP client and DB pool
    try:
        await app.state.http_client.aclose()
    except Exception:
        logger.warning("Error closing HTTP client", exc_info=True)

    try:
        await chatbot_db_manager.close()
    except Exception:
        logger.warning("Error closing Chatbot DB connection pool", exc_info=True)


app = FastAPI(
    title="Standalone Chatbot API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
