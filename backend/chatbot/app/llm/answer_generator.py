"""Natural Language Answer Generation Node."""

import json
from typing import Dict, Any
from langchain_core.output_parsers import StrOutputParser
from chatbot.app.models import AgentState
from chatbot.app.llm.base import get_llm
from chatbot.app.prompts.answer_generation import ANSWER_GENERATION_PROMPT
from chatbot.config.settings import settings

# Lazy-initialized native LCEL chain for natural language generation
_answer_chain = None

# Bounded conversation memory: keep the most recent turns only
MAX_HISTORY_TURNS = 10
MAX_HISTORY_RESULT_ROWS = 5


def _get_answer_chain():
    """Lazy-initializes the natural language answer generation chain using native LCEL."""
    global _answer_chain
    if _answer_chain is None:
        _answer_chain = ANSWER_GENERATION_PROMPT | get_llm() | StrOutputParser()
    return _answer_chain


def _format_results(results: Any) -> str:
    """Formats SQL results into readable text or Markdown table representation."""
    if not results:
        return "No records were found matching your criteria." if results is not None else "No data is currently available."

    if isinstance(results, list):
        # Limit rows in prompt based on .env configuration (default: 30) to maintain speed and avoid token bloat
        max_context_rows = getattr(settings, "LLM_MAX_ROWS_CONTEXT", 30)
        sample_rows = results[:max_context_rows]
        
        # If rows are dicts, format neatly as Markdown table
        if isinstance(sample_rows[0], dict):
            headers = list(sample_rows[0].keys())
            # Convert snake_case column names into user-friendly business titles
            clean_headers = [str(h).replace("_", " ").title() for h in headers]
            header_line = "| " + " | ".join(clean_headers) + " |"
            separator_line = "| " + " | ".join(["---"] * len(clean_headers)) + " |"
            data_lines = []
            for row in sample_rows:
                row_vals = [str(row.get(h, "")) for h in headers]
                data_lines.append("| " + " | ".join(row_vals) + " |")

            table_str = "\n".join([header_line, separator_line] + data_lines)
            if len(results) > max_context_rows:
                table_str += f"\n\n*(Note: Showing first {max_context_rows} of {len(results)} total records)*"
            return table_str

        # Fallback JSON string
        return json.dumps(sample_rows, default=str, indent=2)

    return str(results)


async def answer_generation_node(state: AgentState) -> Dict[str, Any]:
    """LangGraph node: Generates the final natural language answer for the user."""
    # 1. If human clarification was requested by the Self-RAG assessor
    if state.context_assessment_status == "ambiguous" and state.clarification_question:
        final_answer = state.clarification_question
        if state.clarification_options:
            options_str = "\n".join(f"- {opt}" for opt in state.clarification_options)
            final_answer += f"\n\n**Please specify which one you'd like to see:**\n{options_str}"
    # 2. If out of scope or direct response without SQL
    elif state.context_assessment_status == "out_of_scope" or state.intent == "out_of_scope":
        final_answer = state.direct_response or "I am sorry, but that information is not available in our e-commerce store database."
    elif state.direct_response and not state.sql_query:
        final_answer = state.direct_response
    else:
        # 2. Synthesize answer from SQL results or errors
        user_query = state.processed_query or state.user_input
        results_str = _format_results(state.sql_results)
        error_section = "Note: A technical issue occurred while retrieving the requested records." if state.error else ""
        row_count = len(state.sql_results) if isinstance(state.sql_results, list) else (1 if state.sql_results is not None else 0)

        if row_count > 0:
            result_context_header = (
                f"The database query executed successfully and returned {row_count} matching record(s) "
                f"fulfilling the user's criteria. Every record in the data below is an exact match for the requested question. "
                f"Synthesize and present these {row_count} record(s) directly to the user."
            )
        elif state.error:
            result_context_header = (
                "The database query could not be completed due to a technical error. "
                "Explain in plain business language that the request could not be fulfilled."
            )
        else:
            result_context_header = "The database query executed successfully but returned 0 matching records."

        try:
            final_answer = await _get_answer_chain().ainvoke({
                "user_query": user_query,
                "sql_query": state.sql_query or "No SQL query generated",
                "result_context_header": result_context_header,
                "results_summary": results_str,
                "error_section": error_section,
            })
            final_answer = final_answer.strip()
        except Exception:
            if state.sql_results:
                final_answer = _format_results(state.sql_results)
            elif state.error:
                final_answer = "We were unable to complete your request at this time. Please try rephrasing your question."
            else:
                final_answer = "I was unable to retrieve an answer for your request. Please try rephrasing your question."

    turn_record = {
        "question": state.user_input,
        "answer": final_answer,
        "sql": state.sql_query or "",
        "results": (state.sql_results or [])[:MAX_HISTORY_RESULT_ROWS],
    }
    updated_history = (list(state.history) + [turn_record])[-MAX_HISTORY_TURNS:]

    return {
        "final_answer": final_answer,
        "history": updated_history,
    }
