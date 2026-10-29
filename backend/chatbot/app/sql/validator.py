import re
from typing import Optional, Tuple

import sqlparse

from chatbot.app.schema.introspector import introspector

# Keywords that alter data/schema or execute server-side code
FORBIDDEN_KEYWORDS = (
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE",
    "REPLACE", "GRANT", "REVOKE", "LOCK", "UNLOCK", "RENAME", "EXEC",
    "EXECUTE", "CALL",
)

FORBIDDEN_KEYWORD_PATTERN = re.compile(r"\b(?:" + "|".join(FORBIDDEN_KEYWORDS) + r")\b", re.IGNORECASE)
FORBIDDEN_CLAUSE_PATTERNS = (
    re.compile(r"\bINTO\s+(?:OUTFILE|DUMPFILE)\b", re.IGNORECASE),
    re.compile(r"\bFOR\s+UPDATE\b", re.IGNORECASE),
)

# CTE names are declared as `WITH name AS (` (optionally RECURSIVE)
CTE_PATTERN = re.compile(
    r"(?:\bWITH\b(?:\s+RECURSIVE\b)?|,)\s*(`?[A-Za-z_][\w$]*`?)\s+AS\s*\(",
    re.IGNORECASE,
)
# A projection of `*` or `table.*` (COUNT(*) is intentionally not matched)
WILDCARD_PROJECTION = re.compile(
    r"(?:\bSELECT\b|,)\s*(?:\bDISTINCT\b\s*)?(?:`?[A-Za-z_][\w$]*`?\s*\.\s*)?\*\s*(?=,|\bFROM\b|$)",
    re.IGNORECASE | re.DOTALL,
)

COMMENT_PATTERN = re.compile(r"--[^\n]*|#[^\n]*|/\*.*?\*/", re.DOTALL)
STRING_LITERAL_PATTERN = re.compile(r"'(?:[^'\\]|\\.|'')*'|\"(?:[^\"\\]|\\.)*\"", re.DOTALL)
QUOTED_IDENTIFIER_PATTERN = re.compile(r"`(?:[^`]|``)*`")

FIRST_KEYWORD_PATTERN = re.compile(r"^\s*([A-Za-z]+)")


class SQLValidator:
    """Validates SQL query safety, read-only compliance, and permission rules."""

    @staticmethod
    def _strip_comments(sql: str) -> str:
        return COMMENT_PATTERN.sub(" ", sql)

    def _strip_for_keyword_scan(self, sql: str) -> str:
        """Removes strings, quoted identifiers, and comments so literals cannot trigger or hide checks."""
        text = self._strip_comments(sql)
        text = STRING_LITERAL_PATTERN.sub("''", text)
        return QUOTED_IDENTIFIER_PATTERN.sub(" ", text)

    @staticmethod
    def _has_subquery(token) -> bool:
        subquery_pattern = re.compile(r"\b(?:SELECT|WITH)\b", re.IGNORECASE)
        if isinstance(token, sqlparse.sql.Parenthesis):
            return bool(subquery_pattern.search(token.value))
        if not isinstance(token, sqlparse.sql.TokenList):
            return False
        for child in token.tokens:
            if isinstance(child, sqlparse.sql.Parenthesis):
                if subquery_pattern.search(child.value):
                    return True
            elif isinstance(child, sqlparse.sql.TokenList) and SQLValidator._has_subquery(child):
                return True
        return False

    def _add_table_name(self, name: Optional[str], tables: set, cte_names: set) -> None:
        if not name:
            return
        for part in str(name).split(","):
            candidate = part.split(".")[-1].strip().strip("`'\"()").lower()
            if not candidate or candidate == "dual" or candidate in cte_names:
                continue
            tables.add(candidate)

    def _add_table_ref(self, token, tables: set, cte_names: set) -> None:
        if isinstance(token, sqlparse.sql.Identifier):
            if self._has_subquery(token):
                self._collect_tables(token.tokens, tables, cte_names)
            else:
                self._add_table_name(token.get_real_name() or token.get_name(), tables, cte_names)
        elif isinstance(token, sqlparse.sql.Parenthesis):
            if self._has_subquery(token):
                self._collect_tables(token.tokens, tables, cte_names)
            else:
                self._collect_table_refs(token.tokens, tables, cte_names)
        elif isinstance(token, sqlparse.sql.Function):
            return
        else:
            self._add_table_name(str(token), tables, cte_names)

    def _collect_table_refs(self, token_list, tables: set, cte_names: set) -> None:
        for token in token_list:
            if token.is_whitespace or token.ttype in sqlparse.tokens.Comment:
                continue
            if token.ttype in sqlparse.tokens.Punctuation:
                continue
            self._add_table_ref(token, tables, cte_names)

    def _collect_tables(self, token_list, tables: set, cte_names: set) -> None:
        """Walks a token list, collecting table names after every FROM/JOIN at any depth."""
        expecting = False
        for token in token_list:
            if token.is_whitespace or token.ttype in sqlparse.tokens.Comment:
                continue

            if isinstance(token, sqlparse.sql.Where):
                self._collect_tables(token.tokens, tables, cte_names)
                expecting = False
                continue

            if isinstance(token, sqlparse.sql.IdentifierList):
                if expecting:
                    for identifier in token.get_identifiers():
                        self._add_table_ref(identifier, tables, cte_names)
                    expecting = False
                else:
                    for identifier in token.get_identifiers():
                        if self._has_subquery(identifier):
                            self._collect_tables(identifier.tokens, tables, cte_names)
                continue

            if isinstance(token, sqlparse.sql.Identifier):
                if self._has_subquery(token):
                    self._collect_tables(token.tokens, tables, cte_names)
                elif expecting:
                    self._add_table_name(token.get_real_name() or token.get_name(), tables, cte_names)
                expecting = False
                continue

            if isinstance(token, sqlparse.sql.Parenthesis):
                if self._has_subquery(token):
                    self._collect_tables(token.tokens, tables, cte_names)
                elif expecting:
                    self._collect_table_refs(token.tokens, tables, cte_names)
                expecting = False
                continue

            if isinstance(token, sqlparse.sql.Function):
                if self._has_subquery(token):
                    self._collect_tables(token.tokens, tables, cte_names)
                expecting = False
                continue

            if isinstance(token, sqlparse.sql.TokenList):
                if self._has_subquery(token):
                    self._collect_tables(token.tokens, tables, cte_names)
                expecting = False
                continue

            if token.ttype in sqlparse.tokens.Keyword:
                keyword = token.normalized.upper()
                if keyword == "FROM" or keyword.endswith("JOIN"):
                    expecting = True
                elif keyword in (
                    "WHERE", "GROUP BY", "ORDER BY", "HAVING", "LIMIT", "UNION",
                    "ON", "USING", "SET", "VALUES", "SELECT",
                ):
                    expecting = False
                continue

            if expecting:
                if token.ttype in (sqlparse.tokens.Name, sqlparse.tokens.Name.Builtin):
                    self._add_table_name(token.value, tables, cte_names)
                expecting = False

    def _extract_tables(self, sql: str) -> set:
        """Extracts table names after FROM/JOIN anywhere in the statement, excluding CTE names."""
        text = self._strip_comments(sql)
        cte_names = {
            match.group(1).strip("`").lower()
            for match in CTE_PATTERN.finditer(STRING_LITERAL_PATTERN.sub("''", text))
        }
        try:
            statement = sqlparse.parse(text)[0]
        except (IndexError, sqlparse.exceptions.SQLParseError):
            return set()

        tables: set = set()
        self._collect_tables(statement.tokens, tables, cte_names)
        return tables

    def _extract_blocked_columns(self) -> set:
        blocked_columns = set()
        permissions = introspector.permissions.get("blocked_columns", {})
        for cols in permissions.values():
            if isinstance(cols, list):
                blocked_columns.update(c.strip().lower() for c in cols)
        return blocked_columns

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
        scan_text = self._strip_for_keyword_scan(clean_sql)
        first_kw_match = FIRST_KEYWORD_PATTERN.match(scan_text)
        first_kw = first_kw_match.group(1).upper() if first_kw_match else ""

        # Enforce read-only queries only (SELECT / WITH, SHOW, DESCRIBE, EXPLAIN)
        allowed_starts = {"SELECT", "WITH", "SHOW", "DESCRIBE", "DESC", "EXPLAIN"}
        if statement_type != "SELECT" and first_kw not in allowed_starts:
            return False, (
                "Only read-only queries (SELECT, SHOW, DESCRIBE, EXPLAIN) are allowed. "
                f"Got: '{statement_type or first_kw}'"
            )

        # SHOW/DESCRIBE statements legitimately contain words like CREATE (SHOW CREATE TABLE)
        if first_kw not in {"SHOW", "DESCRIBE", "DESC"}:
            keyword_hit = FORBIDDEN_KEYWORD_PATTERN.search(scan_text)
            if keyword_hit:
                return False, f"Forbidden keyword detected: '{keyword_hit.group(0).upper()}'."
            for pattern in FORBIDDEN_CLAUSE_PATTERNS:
                if pattern.search(scan_text):
                    return False, "Query contains a forbidden clause (file output or row locking)."

        # 1. Enforce allowed_tables whitelist on extracted FROM/JOIN tables
        blocked_tables = {t.strip().lower() for t in introspector.permissions.get("blocked_tables", [])}
        tables = self._extract_tables(clean_sql)
        for tbl in tables:
            if not introspector.is_allowed(tbl):
                return False, f"Access to table '{tbl}' is not permitted by schema permissions."
            if tbl in blocked_tables:
                return False, f"Access to table '{tbl}' is blocked by permissions."

        # 2. Reject wildcard projections when column-level restrictions exist,
        #    since `*` would silently expose blocked columns.
        blocked_columns = self._extract_blocked_columns()
        if blocked_columns and WILDCARD_PROJECTION.search(scan_text):
            return False, (
                "Wildcard projections (SELECT *) are not permitted while column restrictions "
                "are configured. List the required columns explicitly."
            )

        # 3. Check identifiers (not string literals) for blocked columns
        if blocked_columns:
            for token in statement.flatten():
                if token.is_whitespace:
                    continue
                if token.ttype in sqlparse.tokens.Comment:
                    continue
                if token.ttype in sqlparse.tokens.Literal.String:
                    continue
                token_val = token.value.strip("`'\" ").lower()
                if token_val in blocked_columns:
                    return False, f"Access to column '{token_val}' is blocked by permissions."

        return True, None


validator = SQLValidator()
