"""
Database Service for Live MySQL Operations
Connects to live Aiven MySQL (ecommerce_db) for table record previews and health check.
"""

from typing import Tuple, Optional
import re

import pandas as pd

TABLE_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_]+$")


def fetch_live_table_preview(table_name: str, limit: int = 25) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """Fetches live records for a table directly from live Aiven MySQL database."""
    if not TABLE_NAME_PATTERN.fullmatch(table_name or ""):
        return None, f"Invalid table name: {table_name!r}"
    try:
        safe_limit = max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        safe_limit = 25

    try:
        from chatbot.app.sql.executor import SQLExecutor
        executor = SQLExecutor()
        query = f"SELECT * FROM `{table_name}` LIMIT {safe_limit};"
        res = executor.execute_sync(query)
        if res.get("success"):
            df = pd.DataFrame(res.get("rows", []))
            return df, None
        return None, res.get("error", "Unknown MySQL error")
    except Exception as e:
        return None, str(e)


def check_db_health() -> bool:
    """Verifies that the database connection pool is operational."""
    try:
        from chatbot.app.sql.executor import SQLExecutor
        executor = SQLExecutor()
        res = executor.execute_sync("SELECT 1;")
        return bool(res.get("success"))
    except Exception:
        return False
