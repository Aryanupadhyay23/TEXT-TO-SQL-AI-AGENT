"""SQL Self-Correction and Error Repair Node."""

from typing import Dict, Any
from chatbot.app.models import AgentState
from chatbot.app.llm.base import get_llm
from chatbot.app.schema.introspector import introspector
from chatbot.app.prompts.sql_repair import SQL_REPAIR_PROMPT
from chatbot.app.models import GeneratedSQL
from chatbot.utils.sql_helpers import clean_sql as _clean_sql, extract_sql_from_text as _extract_sql_from_text
from chatbot.utils.formatting import format_schema as _format_schema, format_rules as _format_rules

# Lazy-initialized structured chain for SQL repair
_repair_chain = None


def _get_repair_chain():
    """Lazy-initializes the SQL repair chain."""
    global _repair_chain
    if _repair_chain is None:
        _repair_chain = SQL_REPAIR_PROMPT | get_llm().with_structured_output(GeneratedSQL)
    return _repair_chain


async def _build_repair_context(state: AgentState) -> str:
    """Builds rich context for repair including schema and business rules."""
    sections = []

    # If schema_context exists in state, use it; otherwise fetch cached/live schema asynchronously
    schema = state.schema_context if (state.schema_context and state.schema_context.get("tables")) else await introspector.aget_schema()
    if schema and schema.get("tables"):
        sections.append(f"Database Schema:\n{_format_schema(schema)}")

    if state.retrieved_rules:
        sections.append(f"Business Rules:\n{_format_rules(state.retrieved_rules)}")

    return "\n\n".join(sections) if sections else "No specific schema metadata available."


async def sql_repair_node(state: AgentState) -> Dict[str, Any]:
    """LangGraph node: Self-corrects a failed SQL query using error diagnostics and schema context."""
    user_query = state.processed_query or state.user_input
    current_retry = state.retry_count + 1

    try:
        context_str = await _build_repair_context(state)
        result: GeneratedSQL = await _get_repair_chain().ainvoke({
            "user_query": user_query,
            "failed_sql": state.sql_query or "No previous query",
            "error_message": state.error or "Unknown database error",
            "context": context_str,
        })

        repaired_sql = _clean_sql(result.sql_query)
        return {
            "sql_query": repaired_sql,
            "retry_count": current_retry,
            "error": None,  # Reset error so next execution runs with clean slate
        }
    except Exception as e:
        err_msg = str(e)
        extracted_sql = _extract_sql_from_text(err_msg)
        if extracted_sql:
            return {
                "sql_query": extracted_sql,
                "retry_count": current_retry,
                "error": None,
            }
        return {
            "retry_count": current_retry,
            "error": f"SQL repair failed: {err_msg}",
        }

