import asyncio
import json
import time
from pathlib import Path
from typing import Any, Iterable

from chatbot.app.database.connection import build_ssl_context, db_manager, use_sync_db_fallback
from chatbot.config.settings import settings

PERMISSIONS_FILE = Path(__file__).resolve().parent.parent.parent / "config" / "schema_permissions.json"
SCHEMA_FILES_DIR = Path(__file__).resolve().parent.parent.parent / "schema_files"
FALLBACK_RETRY_SECONDS = 60


class SchemaIntrospector:
    """Introspects MySQL database schema, filters with permissions, and caches in memory."""

    def __init__(self):
        self.permissions = self._load_permissions()
        self._schema_cache: dict | None = None
        self._fallback_cache: dict | None = None
        self._fallback_until: float = 0.0

    def _load_permissions(self) -> dict:
        """Loads allowed/blocked tables and columns from config."""
        if PERMISSIONS_FILE.exists():
            with open(PERMISSIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"allowed_tables": ["*"], "blocked_tables": [], "blocked_columns": {}}

    def is_allowed(self, table: str, column: str = None) -> bool:
        """Checks if a table (and optionally column) is permitted (case-insensitive)."""
        if not table:
            return False

        table_lower = table.strip().lower()
        allowed_tables = [t.strip().lower() for t in self.permissions.get("allowed_tables", ["*"])]
        blocked_tables = [t.strip().lower() for t in self.permissions.get("blocked_tables", [])]
        blocked_cols = self.permissions.get("blocked_columns", {})

        if table_lower in blocked_tables:
            return False
        if "*" not in allowed_tables and table_lower not in allowed_tables:
            return False

        if column:
            col_lower = column.strip().lower()
            blocked = [c.strip().lower() for c in blocked_cols.get("*", [])]
            for tbl_key, cols in blocked_cols.items():
                if tbl_key.strip().lower() == table_lower:
                    blocked.extend([c.strip().lower() for c in cols])
            if col_lower in blocked:
                return False

        return True

    def _load_fallback_from_schema_files(self) -> dict:
        """Fallback to load schema from schema_files directory if DB is unreachable."""
        schema = {"database": settings.DB_NAME, "tables": {}, "relationships": []}
        tables_dir = SCHEMA_FILES_DIR / "schema_of_table"
        if tables_dir.exists():
            for p in tables_dir.glob("*.json"):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    tbl = data.get("table_name", p.stem)
                    columns = []
                    for col in data.get("columns", []):
                        if self.is_allowed(tbl, col.get("name")):
                            columns.append({
                                "name": col.get("name"),
                                "type": col.get("data_type", "varchar"),
                                "primary_key": bool(col.get("primary_key", False)),
                            })
                    schema["tables"][tbl] = {"columns": columns, "foreign_keys": []}
                except Exception:
                    continue

        join_file = SCHEMA_FILES_DIR / "join_information" / "join_information.json"
        if join_file.exists():
            try:
                with open(join_file, "r", encoding="utf-8") as f:
                    join_data = json.load(f)
                for rel in join_data.get("relationships", []):
                    t1, c1 = rel.get("from_table"), rel.get("from_column")
                    t2, c2 = rel.get("to_table"), rel.get("to_column")
                    if self.is_allowed(t1, c1) and self.is_allowed(t2, c2):
                        r = {"from_table": t1, "from_column": c1, "to_table": t2, "to_column": c2}
                        if t1 in schema["tables"]:
                            schema["tables"][t1]["foreign_keys"].append(r)
                        schema["relationships"].append(r)
            except Exception:
                pass

        return schema

    def _apply_columns(self, schema: dict, rows: Iterable[dict]) -> None:
        for row in rows:
            tbl = row["TABLE_NAME"]
            col = row["COLUMN_NAME"]
            if not self.is_allowed(tbl, col):
                continue

            if tbl not in schema["tables"]:
                schema["tables"][tbl] = {"columns": [], "foreign_keys": []}

            schema["tables"][tbl]["columns"].append({
                "name": col,
                "type": row["DATA_TYPE"],
                "primary_key": (row["COLUMN_KEY"] == "PRI"),
            })

    def _apply_relationships(self, schema: dict, rows: Iterable[dict]) -> None:
        for row in rows:
            t1, c1 = row["TABLE_NAME"], row["COLUMN_NAME"]
            t2, c2 = row["REFERENCED_TABLE_NAME"], row["REFERENCED_COLUMN_NAME"]

            if self.is_allowed(t1, c1) and self.is_allowed(t2, c2):
                rel = {"from_table": t1, "from_column": c1, "to_table": t2, "to_column": c2}
                if t1 in schema["tables"]:
                    schema["tables"][t1]["foreign_keys"].append(rel)
                schema["relationships"].append(rel)

    def _cache_or_fallback(self, schema: dict) -> dict:
        """Serves the schema-file fallback briefly, retrying the live DB once the TTL expires."""
        if self._schema_cache is not None:
            return self._schema_cache
        now = time.monotonic()
        if self._fallback_cache is None or now >= self._fallback_until:
            self._fallback_cache = self._load_fallback_from_schema_files()
            self._fallback_until = now + FALLBACK_RETRY_SECONDS
        return self._fallback_cache

    async def _introspect_async(self) -> dict:
        """Fetches schema from MySQL over the native async pool and caches it in memory."""
        if use_sync_db_fallback():
            return await asyncio.to_thread(self._introspect_sync)

        schema = {"database": settings.DB_NAME, "tables": {}, "relationships": []}

        try:
            async with db_manager.acquire_dict_cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, COLUMN_KEY
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = %s
                    ORDER BY TABLE_NAME, ORDINAL_POSITION;
                    """,
                    (settings.DB_NAME,),
                )
                self._apply_columns(schema, await cursor.fetchall())

                await cursor.execute(
                    """
                    SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                    FROM information_schema.KEY_COLUMN_USAGE
                    WHERE TABLE_SCHEMA = %s AND REFERENCED_TABLE_NAME IS NOT NULL;
                    """,
                    (settings.DB_NAME,),
                )
                self._apply_relationships(schema, await cursor.fetchall())

            self._schema_cache = schema
            return schema
        except Exception:
            return self._cache_or_fallback(schema)

    def _introspect_sync(self) -> dict:
        """Synchronous PyMySQL fallback for non-async callers (Streamlit frontend)."""
        schema: dict[str, Any] = {"database": settings.DB_NAME, "tables": {}, "relationships": []}

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
                    cursor.execute(
                        """
                        SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, COLUMN_KEY
                        FROM information_schema.COLUMNS
                        WHERE TABLE_SCHEMA = %s
                        ORDER BY TABLE_NAME, ORDINAL_POSITION;
                        """,
                        (settings.DB_NAME,),
                    )
                    self._apply_columns(schema, cursor.fetchall())

                    cursor.execute(
                        """
                        SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                        FROM information_schema.KEY_COLUMN_USAGE
                        WHERE TABLE_SCHEMA = %s AND REFERENCED_TABLE_NAME IS NOT NULL;
                        """,
                        (settings.DB_NAME,),
                    )
                    self._apply_relationships(schema, cursor.fetchall())
            finally:
                conn.close()

            self._schema_cache = schema
            return schema
        except Exception:
            return self._cache_or_fallback(schema)

    async def introspect(self) -> dict:
        """Fetches schema from MySQL over the native async pool."""
        return await self._introspect_async()

    async def aget_schema(self, force_refresh: bool = False) -> dict:
        """Returns cached schema or introspects the database asynchronously."""
        if not force_refresh:
            if self._schema_cache is not None:
                return self._schema_cache
            if self._fallback_cache is not None and time.monotonic() < self._fallback_until:
                return self._fallback_cache
        return await self._introspect_async()

    def get_schema(self, force_refresh: bool = False) -> dict:
        """Returns cached schema or introspects the database synchronously."""
        if not force_refresh:
            if self._schema_cache is not None:
                return self._schema_cache
            if self._fallback_cache is not None and time.monotonic() < self._fallback_until:
                return self._fallback_cache
        return self._introspect_sync()


introspector = SchemaIntrospector()
