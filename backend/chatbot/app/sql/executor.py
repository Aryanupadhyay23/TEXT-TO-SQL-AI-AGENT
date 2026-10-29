import asyncio
import re
import time
from typing import Dict, Any

import sqlparse

from chatbot.app.database.connection import build_ssl_context, db_manager, use_sync_db_fallback
from chatbot.app.sql.validator import validator
from chatbot.app.models import AgentState
from chatbot.config.settings import settings


class SQLExecutor:
    """Safely executes SQL queries using the shared asyncmy connection pool."""

    def _classify_error(self, error_message: str) -> str:
        """Classifies SQL error for targeted repair by the agent."""
        msg = error_message.lower()
        if "unknown column" in msg:
            return "unknown_column"
        if "doesn't exist" in msg or "unknown table" in msg:
            return "unknown_table"
        if "syntax" in msg or "near" in msg:
            return "syntax_error"
        if "timeout" in msg or "timed out" in msg:
            return "query_timeout"
        if "ambiguous" in msg:
            return "ambiguous_column"
        return "execution_error"

    @staticmethod
    def _failure(start_time: float, error: str, error_type: str) -> Dict[str, Any]:
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "execution_time": round(time.time() - start_time, 4),
            "error": error,
            "error_type": error_type,
        }

    @staticmethod
    def _has_top_level_limit(sql: str) -> bool:
        try:
            statement = sqlparse.parse(sql)[0]
        except Exception:
            return False
        for token in statement.tokens:
            if token.ttype is sqlparse.tokens.Keyword and token.normalized.upper() == "LIMIT":
                return True
            if token.ttype is sqlparse.tokens.Keyword and token.normalized.upper() in ("FOR", "LOCK"):
                return True
        return False

    def _apply_row_cap(self, sql: str) -> str:
        """Caps result size at the SQL level so the driver never buffers the full table."""
        if not settings.ENABLE_ROW_LIMIT:
            return sql
        clean_sql = sql.strip().rstrip(";")
        if not re.match(r"^(SELECT|WITH)\b", clean_sql, re.IGNORECASE):
            return sql
        if self._has_top_level_limit(clean_sql) or re.search(r"\bLIMIT\s+\d+\s*,\s*\d+\s*$", clean_sql, re.IGNORECASE):
            return sql
        return f"{clean_sql}\nLIMIT {int(settings.DB_MAX_ROWS)}"

    async def execute(self, sql: str) -> Dict[str, Any]:
        """Validates and executes SQL against the native async pool."""
        if use_sync_db_fallback():
            return await asyncio.to_thread(self.execute_sync, sql)

        start_time = time.time()
        is_valid, validation_error = validator.validate(sql)
        if not is_valid:
            return self._failure(start_time, validation_error, "validation_error")

        try:
            async with db_manager.acquire_dict_cursor() as cursor:
                await cursor.execute(self._apply_row_cap(sql))
                if settings.ENABLE_ROW_LIMIT:
                    rows = await cursor.fetchmany(settings.DB_MAX_ROWS)
                else:
                    rows = await cursor.fetchall()
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                rows = list(rows or [])
                return {
                    "success": True,
                    "columns": columns,
                    "rows": rows,
                    "row_count": len(rows),
                    "execution_time": round(time.time() - start_time, 4),
                    "error": None,
                    "error_type": None,
                }
        except Exception as e:
            error_str = str(e)
            return self._failure(start_time, error_str, self._classify_error(error_str))

    def execute_sync(self, sql: str) -> Dict[str, Any]:
        """Synchronous PyMySQL fallback for non-async callers (Streamlit frontend)."""
        start_time = time.time()
        is_valid, validation_error = validator.validate(sql)
        if not is_valid:
            return self._failure(start_time, validation_error, "validation_error")
        try:
            import pymysql
            from pymysql.cursors import DictCursor as PyMySQLDictCursor

            conn = pymysql.connect(
                host=settings.DB_HOST,
                port=settings.DB_PORT,
                user=settings.DB_USER,
                password=settings.DB_PASSWORD,
                database=settings.DB_NAME,
                charset="utf8mb4",
                ssl=build_ssl_context(),
                cursorclass=PyMySQLDictCursor,
                connect_timeout=settings.DB_TIMEOUT_SECONDS,
                read_timeout=settings.DB_TIMEOUT_SECONDS,
            )
            try:
                with conn.cursor() as cursor:
                    cursor.execute(self._apply_row_cap(sql))
                    if settings.ENABLE_ROW_LIMIT:
                        rows = cursor.fetchmany(settings.DB_MAX_ROWS)
                    else:
                        rows = cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description] if cursor.description else []
                    rows = list(rows or [])
                    return {
                        "success": True,
                        "columns": columns,
                        "rows": rows,
                        "row_count": len(rows),
                        "execution_time": round(time.time() - start_time, 4),
                        "error": None,
                        "error_type": None,
                    }
            finally:
                conn.close()
        except Exception as e:
            error_str = str(e)
            return self._failure(start_time, error_str, self._classify_error(error_str))


executor = SQLExecutor()


async def sql_execution_node(state: AgentState) -> Dict[str, Any]:
    """LangGraph node: Validates and executes the generated SQL query."""
    if not state.sql_query:
        return {
            "sql_results": None,
            "execution_time": 0.0,
            "error": "No SQL query generated to execute.",
        }

    result = await executor.execute(state.sql_query)

    if result["success"]:
        return {
            "sql_results": result["rows"],
            "execution_time": result["execution_time"],
            "error": None,
        }
    else:
        err_msg = f"[{result['error_type']}] {result['error']}"
        return {
            "sql_results": None,
            "execution_time": result["execution_time"],
            "error": err_msg,
        }
