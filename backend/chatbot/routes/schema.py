"""
Database Schema and Records Inspection Routes

Endpoints for inspecting relational database structure and records:
- GET /api/chat/schema: List all tables, columns, data types, keys, and relationships
- GET /api/chat/schema/tables/{table_name}/records: Preview up to 100 records for a table
"""

import re
import decimal
import datetime
import logging
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from auth.deps import get_current_user
from chatbot.app.schema.introspector import introspector
from conf.database import chatbot_db_manager
from conf.settings import CHATBOT_DB_NAME

logger = logging.getLogger(__name__)

router = APIRouter()


def _serialize_value(val: Any) -> Any:
    """Safely converts non-JSON-serializable objects (Decimal, datetime, bytes) to native types."""
    if isinstance(val, (datetime.datetime, datetime.date, datetime.time)):
        return val.isoformat()
    if isinstance(val, decimal.Decimal):
        return float(val) if (val % 1) else int(val)
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return val


@router.get("/schema")
async def get_database_schema(
    current_user: dict = Depends(get_current_user),
):
    """
    Returns detailed schema definition for all allowed database tables:
    columns, primary keys, foreign keys, row counts, and relational graph.
    """
    try:
        # 1. Fetch cached or introspected schema
        schema = await introspector.aget_schema()

        # 2. Enrich with actual table row counts and comments from information_schema
        table_stats = {}
        async with chatbot_db_manager.acquire_dict_cursor() as cursor:
            await cursor.execute(
                """
                SELECT TABLE_NAME, TABLE_ROWS, TABLE_COMMENT
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = %s
                """,
                (CHATBOT_DB_NAME,),
            )
            stats_rows = await cursor.fetchall()
            for row in stats_rows:
                t_name = row["TABLE_NAME"]
                table_stats[t_name] = {
                    "rows_estimate": row.get("TABLE_ROWS") or 0,
                    "comment": row.get("TABLE_COMMENT") or "",
                }

        formatted_tables: List[Dict[str, Any]] = []
        for tbl_name, tbl_meta in schema.get("tables", {}).items():
            if not introspector.is_allowed(tbl_name):
                continue

            stats = table_stats.get(tbl_name, {})
            formatted_tables.append({
                "name": tbl_name,
                "columns": tbl_meta.get("columns", []),
                "foreign_keys": tbl_meta.get("foreign_keys", []),
                "rows_estimate": stats.get("rows_estimate", 0),
                "comment": stats.get("comment", ""),
                "total_columns": len(tbl_meta.get("columns", [])),
            })

        formatted_tables.sort(key=lambda t: t["name"])

        return {
            "database": CHATBOT_DB_NAME,
            "total_tables": len(formatted_tables),
            "tables": formatted_tables,
            "relationships": schema.get("relationships", []),
        }
    except Exception as e:
        logger.exception("Failed to retrieve schema: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch database schema: {str(e)}",
        )


@router.get("/schema/tables/{table_name}/records")
async def get_table_records(
    table_name: str,
    limit: int = Query(default=100, ge=1, le=100, description="Max 100 rows"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    search: Optional[str] = Query(default=None, description="Optional search filter across text columns"),
    current_user: dict = Depends(get_current_user),
):
    """
    Returns up to 100 rows for the specified table with pagination, column names,
    and optional text filter.
    """
    clean_table = table_name.strip()

    # Validate table name security
    if not re.match(r"^[a-zA-Z0-9_]+$", clean_table):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid table name format.",
        )

    if not introspector.is_allowed(clean_table):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access to table '{clean_table}' is restricted.",
        )

    try:
        async with chatbot_db_manager.acquire_dict_cursor() as cursor:
            # 1. Verify table exists in current database schema
            await cursor.execute(
                """
                SELECT COLUMN_NAME, DATA_TYPE, COLUMN_KEY
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                ORDER BY ORDINAL_POSITION
                """,
                (CHATBOT_DB_NAME, clean_table),
            )
            col_rows = await cursor.fetchall()
            if not col_rows:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Table '{clean_table}' not found in database.",
                )

            columns = [c["COLUMN_NAME"] for c in col_rows if introspector.is_allowed(clean_table, c["COLUMN_NAME"])]
            if not columns:
                return {
                    "table_name": clean_table,
                    "total_records": 0,
                    "limit": limit,
                    "offset": offset,
                    "columns": [],
                    "records": [],
                }

            col_select = ", ".join(f"`{c}`" for c in columns)

            # 2. Build Count and Select queries
            where_clause = ""
            params: list = []

            if search and search.strip():
                search_term = f"%{search.strip()}%"
                text_cols = [c["COLUMN_NAME"] for c in col_rows if c["DATA_TYPE"] in ("varchar", "text", "char", "mediumtext", "longtext")]
                if text_cols:
                    conditions = [f"`{c}` LIKE %s" for c in text_cols]
                    where_clause = f"WHERE {' OR '.join(conditions)}"
                    params = [search_term] * len(text_cols)

            # Count total matching rows
            count_sql = f"SELECT COUNT(*) AS total FROM `{clean_table}` {where_clause}"
            await cursor.execute(count_sql, tuple(params))
            count_res = await cursor.fetchone()
            total_records = count_res["total"] if count_res else 0

            # Fetch rows with pagination
            select_sql = f"SELECT {col_select} FROM `{clean_table}` {where_clause} LIMIT %s OFFSET %s"
            fetch_params = params + [limit, offset]
            await cursor.execute(select_sql, tuple(fetch_params))
            raw_rows = await cursor.fetchall()

            # Serialize values (dates, decimals, etc.)
            serialized_rows = []
            for r in raw_rows:
                row_dict = {k: _serialize_value(v) for k, v in r.items()}
                serialized_rows.append(row_dict)

            return {
                "table_name": clean_table,
                "total_records": total_records,
                "limit": limit,
                "offset": offset,
                "columns": columns,
                "records": serialized_rows,
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to fetch records for table %s: %s", clean_table, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading records from '{clean_table}': {str(e)}",
        )
