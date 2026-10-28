import time
import asyncio
from typing import Dict, Any
from chatbot.app.database.connection import db_manager
from chatbot.app.sql.validator import validator
from chatbot.app.models import AgentState
from chatbot.config.settings import settings


class SQLExecutor:
    """Safely executes SQL queries using centralized chatbot_db_manager."""

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

    async def execute(self, sql: str) -> Dict[str, Any]:
        """Validates and executes SQL query safely in a dedicated thread pool to eliminate event-loop socket conflicts."""
        return await asyncio.to_thread(self.execute_sync, sql)

    def execute_sync(self, sql: str) -> Dict[str, Any]:
        """Synchronous wrapper using PyMySQL to prevent any asyncio event-loop conflicts."""
        start_time = time.time()
        is_valid, validation_error = validator.validate(sql)
        if not is_valid:
            return {
                "success": False,
                "columns": [],
                "rows": [],
                "row_count": 0,
                "execution_time": round(time.time() - start_time, 4),
                "error": validation_error,
                "error_type": "validation_error",
            }
        try:
            import pymysql
            from pymysql.cursors import DictCursor as PyMySQLDictCursor
            import ssl

            ssl_ctx = None
            if settings.DB_SSL:
                ssl_ctx = ssl.create_default_context()
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE

            conn = pymysql.connect(
                host=settings.DB_HOST,
                port=settings.DB_PORT,
                user=settings.DB_USER,
                password=settings.DB_PASSWORD,
                database=settings.DB_NAME,
                charset="utf8mb4",
                ssl=ssl_ctx,
                cursorclass=PyMySQLDictCursor,
                connect_timeout=settings.DB_TIMEOUT_SECONDS,
                read_timeout=settings.DB_TIMEOUT_SECONDS,
            )
            try:
                with conn.cursor() as cursor:
                    cursor.execute(sql)
                    if settings.ENABLE_ROW_LIMIT:
                        rows = cursor.fetchmany(settings.DB_MAX_ROWS)
                    else:
                        rows = cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description] if cursor.description else []
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
            return {
                "success": False,
                "columns": [],
                "rows": [],
                "row_count": 0,
                "execution_time": round(time.time() - start_time, 4),
                "error": error_str,
                "error_type": self._classify_error(error_str),
            }


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
