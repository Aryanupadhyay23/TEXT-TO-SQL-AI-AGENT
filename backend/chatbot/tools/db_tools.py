"""Database live execution and introspection tool (run_sql)."""

from langchain_core.tools import tool
from chatbot.utils.formatting import format_markdown_table


@tool
def run_sql(sql: str) -> str:
    """Executes a read-only SQL query on the live MySQL database (ecommerce_db).
    Use this to:
    1. Inspect tables or schema: 'SHOW TABLES;', 'DESCRIBE orders;', or 'SHOW CREATE TABLE shipments;'
    2. Probe distinct values: 'SELECT DISTINCT status FROM orders;' or 'SELECT payment_method FROM payments LIMIT 5;'
    3. Dry-run and test a candidate query before finalizing: 'SELECT ... LIMIT 5;'
    Input: A valid read-only SQL statement (SELECT, SHOW, DESCRIBE, EXPLAIN).
    Output: Markdown formatted table or exact MySQL error message.
    """
    clean_query = sql.strip().rstrip(";")
    if not clean_query:
        return "Error: Empty SQL query provided."

    # Prevent accidental runaway SELECT by injecting LIMIT 20 if no limit present
    sql_upper = clean_query.upper()
    if sql_upper.startswith("SELECT") and "LIMIT" not in sql_upper:
        clean_query = f"{clean_query} LIMIT 20"

    # Read-only and permission validation
    from chatbot.app.sql.validator import validator
    from chatbot.app.sql.executor import SQLExecutor

    is_valid, err = validator.validate(clean_query)
    if not is_valid:
        return f"Validation Error: {err}"

    try:
        executor = SQLExecutor()
        result = executor.execute_sync(clean_query)
        if not result["success"]:
            return f"MySQL Execution Error: {result.get('error', 'Unknown error')}"

        return format_markdown_table(result["columns"], result["rows"], max_rows=10)
    except Exception as e:
        return f"Execution Exception: {str(e)}"
