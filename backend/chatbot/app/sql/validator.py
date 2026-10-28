from typing import Tuple, Optional
import sqlparse
from chatbot.app.schema.introspector import introspector

# Forbidden SQL keywords that alter or mutate data/schema
FORBIDDEN_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "CREATE", "REPLACE", "GRANT", "REVOKE", "LOCK", "UNLOCK",
    "RENAME", "EXEC", "EXECUTE", "CALL", "INTO OUTFILE", "INTO DUMPFILE"
}


class SQLValidator:
    """Validates SQL query safety, read-only compliance, and permission rules."""

    def _extract_tables(self, statement) -> set:
        """Extracts table names following FROM and JOIN clauses."""
        tables = set()
        from_or_join = False

        for token in statement.tokens:
            if token.is_whitespace:
                continue

            if isinstance(token, sqlparse.sql.Where):
                from_or_join = False
                continue

            if token.ttype in (sqlparse.tokens.Keyword, sqlparse.tokens.Keyword.DML):
                val = token.value.upper()
                if val in ("FROM", "JOIN", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL JOIN", "CROSS JOIN"):
                    from_or_join = True
                    continue
                elif val in ("WHERE", "GROUP BY", "ORDER BY", "LIMIT", "HAVING", "SET", "VALUES"):
                    from_or_join = False
                    continue

            if from_or_join:
                if isinstance(token, sqlparse.sql.IdentifierList):
                    for id_token in token.get_identifiers():
                        name = id_token.get_real_name() or id_token.get_name()
                        if name:
                            tables.add(name.strip("`'\" ").lower())
                    from_or_join = False
                elif isinstance(token, sqlparse.sql.Identifier):
                    name = token.get_real_name() or token.get_name()
                    if name:
                        tables.add(name.strip("`'\" ").lower())
                    from_or_join = False
                elif token.ttype in (sqlparse.tokens.Name, sqlparse.tokens.String):
                    name = token.value.strip("`'\" ").lower()
                    if name:
                        tables.add(name)
                    from_or_join = False

        return tables

    def validate(self, sql: str) -> Tuple[bool, Optional[str]]:
        """Validates that a SQL string is safe to execute and satisfies permissions."""
        if not sql or not sql.strip():
            return False, "SQL query is empty."

        clean_sql = sql.strip().rstrip(";")
        parsed = sqlparse.parse(clean_sql)

        if not parsed:
            return False, "Failed to parse SQL query."

        # Disallow multiple semicolon-separated statements (prevent injection)
        if len(parsed) > 1:
            return False, "Multiple SQL statements are not permitted."

        statement = parsed[0]
        statement_type = statement.get_type().upper()
        sql_upper = clean_sql.upper().strip()

        # Enforce read-only queries only (SELECT, SHOW, DESCRIBE, EXPLAIN)
        allowed_starts = ("SELECT", "SHOW", "DESCRIBE", "DESC", "EXPLAIN")
        if statement_type != "SELECT" and not sql_upper.startswith(allowed_starts):
            return False, f"Only read-only queries (SELECT, SHOW, DESCRIBE, EXPLAIN) are allowed. Got: '{statement_type}'"

        # Check for forbidden mutation keywords anywhere in query tokens
        for kw in FORBIDDEN_KEYWORDS:
            if f" {kw} " in f" {sql_upper} ":
                return False, f"Forbidden keyword detected: '{kw}'."

        # 1. Enforce allowed_tables whitelist on extracted FROM/JOIN tables
        tables = self._extract_tables(statement)
        for tbl in tables:
            if not introspector.is_allowed(tbl):
                return False, f"Access to table '{tbl}' is not permitted by schema permissions."

        # 2. Check tokens for blocked tables and sensitive/blocked columns
        blocked_tables = {t.strip().lower() for t in introspector.permissions.get("blocked_tables", [])}
        blocked_columns = set()
        for col in introspector.permissions.get("blocked_columns", {}).get("*", []):
            blocked_columns.add(col.strip().lower())
        for tbl_name, cols in introspector.permissions.get("blocked_columns", {}).items():
            if tbl_name != "*" and isinstance(cols, list):
                blocked_columns.update(c.strip().lower() for c in cols)

        for token in statement.flatten():
            token_val = token.value.strip("`'\" ").lower()
            if token_val in blocked_tables:
                return False, f"Access to table '{token_val}' is blocked by permissions."
            if token_val in blocked_columns:
                return False, f"Access to column '{token_val}' is blocked by permissions."

        return True, None


validator = SQLValidator()
