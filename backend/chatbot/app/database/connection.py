"""
Centralized Chatbot Database Connection

Uses the readymade chatbot_db_manager from backend/conf/database.py.
"""

import asyncio
import logging
import os
import ssl
import sys

from conf.database import chatbot_db_manager as db_manager

__all__ = ["db_manager", "use_sync_db_fallback", "build_ssl_context"]

logger = logging.getLogger(__name__)
_warned_sync_fallback = False


def use_sync_db_fallback() -> bool:
    """asyncmy's SSL handshake fails on the Windows Proactor event loop.

    Uvicorn uses Proactor on Windows unless it runs with --reload/--workers,
    so use the thread-based PyMySQL path on that loop instead.
    """
    global _warned_sync_fallback
    if sys.platform != "win32":
        return False
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return False
    if not isinstance(loop, asyncio.ProactorEventLoop):
        return False
    if not _warned_sync_fallback:
        _warned_sync_fallback = True
        logger.warning(
            "Windows Proactor event loop detected; using thread-based DB fallback. "
            "Run uvicorn with --reload or use a SelectorEventLoop for native async DB access."
        )
    return True


def build_ssl_context():
    """Builds a PyMySQL SSL context that verifies the server when a CA is configured."""
    from chatbot.config.settings import settings

    if not settings.DB_SSL:
        return None
    if settings.DB_SSL_CA and os.path.exists(settings.DB_SSL_CA):
        context = ssl.create_default_context(cafile=settings.DB_SSL_CA)
        context.verify_mode = ssl.CERT_REQUIRED
        context.check_hostname = True
        return context
    # No CA file available (managed cloud certs): encryption without verification
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context
