import asyncmy
import asyncio
import logging
import os
import ssl
import sys

# On Windows, SelectorEventLoop is required for asyncmy with SSL
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except (RuntimeError, AttributeError):
        pass
from asyncmy.cursors import DictCursor
from typing import Optional
from contextlib import asynccontextmanager
from conf.settings import (
    CHATBOT_DB_NAME,
    CHATBOT_DB_USER,
    CHATBOT_DB_PASS,
    CHATBOT_DB_HOST,
    CHATBOT_DB_PORT,
    CHATBOT_DB_SSL,
    CHATBOT_DB_SSL_CA,
    CHATBOT_DB_TIMEOUT,
)

logger = logging.getLogger(__name__)

class MySQLManager:
    def __init__(
        self,
        db_name: str,
        db_user: str,
        db_pass: str,
        db_host: str,
        db_port: int,
        use_ssl: bool = False,
        ssl_ca: str = "",
        min_size: int = 4,
        max_size: int = 16,
        timeout: int = 10,
    ):
        self._pool: Optional[asyncmy.Pool] = None
        self._last_error: Optional[Exception] = None
        self._current_lock: Optional[asyncio.Lock] = None
        self._current_lock_loop = None
        
        cfg = dict(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_pass,
            db=db_name,
            minsize=min_size,
            maxsize=max_size,
            charset="utf8mb4",
            autocommit=False,
            pool_recycle=300,
            connect_timeout=timeout,
            read_timeout=timeout,
        )
        
        if use_ssl:
            if ssl_ca and os.path.exists(ssl_ca):
                ssl_ctx = ssl.create_default_context(cafile=ssl_ca)
            else:
                ssl_ctx = ssl.create_default_context()
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE
            cfg["ssl"] = ssl_ctx
            logger.info(f"MySQL SSL enabled for {db_host}:{db_port}")

        self._cfg = cfg

    def _is_pool_healthy(self) -> bool:
        """Checks if connection pool is active and bound to the current running event loop."""
        if self._pool is None:
            return False
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            return False
            
        pool_loop = getattr(self._pool, "_loop", None)
        if pool_loop is not None:
            if pool_loop.is_closed() or pool_loop != current_loop:
                return False
        elif hasattr(self._pool, "closed") and self._pool.closed:
            return False
            
        return True

    @property
    def _lock(self) -> asyncio.Lock:
        """Returns an asyncio.Lock bound to the current running event loop."""
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.Lock()
            
        if self._current_lock is None or self._current_lock_loop != current_loop:
            self._current_lock = asyncio.Lock()
            self._current_lock_loop = current_loop
        return self._current_lock

    async def init(self, raise_on_fail: bool = False):
        await self._ensure_pool(raise_on_fail=raise_on_fail)

    async def _ensure_pool(self, raise_on_fail: bool = False):
        if self._is_pool_healthy():
            return
        async with self._lock:
            if self._is_pool_healthy():
                return
            # Old pool is dead or attached to a closed/different loop
            self._pool = None
            try:
                self._pool = await asyncmy.create_pool(**self._cfg)
                self._last_error = None
                logger.info(f"MySQL connection pool initialized for database: {self._cfg['db']}")
            except Exception as exc:
                self._pool = None
                self._last_error = exc
                if raise_on_fail:
                    raise
                logger.warning(
                    f"MySQL pool init failed for {self._cfg['db']}; will retry on demand: {exc}"
                )

    async def close(self):
        if self._pool:
            try:
                self._pool.close()
                await self._pool.wait_closed()
            except Exception:
                pass
            self._pool = None
            logger.info("MySQL connection pool closed.")

    # FAST path (tuples)
    @asynccontextmanager
    async def acquire_tuple_cursor(self):
        if not self._is_pool_healthy():
            await self._ensure_pool(raise_on_fail=False)
            if not self._is_pool_healthy():
                err_msg = f"DB pool not available: {self._last_error}" if self._last_error else "DB pool not available"
                raise RuntimeError(err_msg) from self._last_error
        async with self._pool.acquire() as conn:
            cur = conn.cursor()
            try:
                yield cur
                while await cur.nextset():
                    pass
                await conn.commit()
            except BaseException:
                await conn.rollback()
                raise
            finally:
                await cur.close()

    # API path (dicts)
    @asynccontextmanager
    async def acquire_dict_cursor(self):
        if not self._is_pool_healthy():
            await self._ensure_pool(raise_on_fail=False)
            if not self._is_pool_healthy():
                err_msg = f"DB pool not available: {self._last_error}" if self._last_error else "DB pool not available"
                raise RuntimeError(err_msg) from self._last_error
        async with self._pool.acquire() as conn:
            cur = conn.cursor(DictCursor)
            try:
                yield cur
                while await cur.nextset():
                    pass
                await conn.commit()
            except BaseException:
                await conn.rollback()
                raise
            finally:
                await cur.close()


chatbot_db_manager = MySQLManager(
    CHATBOT_DB_NAME,
    CHATBOT_DB_USER,
    CHATBOT_DB_PASS,
    CHATBOT_DB_HOST,
    CHATBOT_DB_PORT,
    use_ssl=CHATBOT_DB_SSL,
    ssl_ca=CHATBOT_DB_SSL_CA,
    timeout=CHATBOT_DB_TIMEOUT,
)
db_manager = chatbot_db_manager
