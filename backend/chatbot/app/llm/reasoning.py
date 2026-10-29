"""Query Understanding & Intent Classification Node using Native Structured Output."""

from typing import List, Dict, Any

from chatbot.app.llm.base import get_llm
from chatbot.app.prompts.query_understanding import QUERY_UNDERSTANDING_PROMPT
from chatbot.app.models import AgentState, QueryAnalysis

# Lazy-initialized structured output chain
_chain = None


def _get_chain():
    """Lazy-initializes the query understanding chain."""
    global _chain
    if _chain is None:
        _chain = QUERY_UNDERSTANDING_PROMPT | get_llm().with_structured_output(QueryAnalysis)
    return _chain


def _format_history(history: List[Dict[str, Any]]) -> str:
    """Helper to format previous conversation turns for the LLM without leaking raw row results."""
    if not history:
        return "No previous conversation history."
    formatted_turns = []
    for i, t in enumerate(history[-10:], 1):
        formatted_turns.append(
            f"Turn {i}:\n"
            f"  User: {t.get('question', '')}\n"
            f"  SQL: {t.get('sql', '')}\n"
            f"  Assistant: {t.get('answer', '')}"
        )
    return "\n\n".join(formatted_turns)


async def query_understanding_node(state: AgentState) -> Dict[str, Any]:
    """LangGraph node: Analyzes user input using LLM with structured output asynchronously."""
    try:
        analysis: QueryAnalysis = await _get_chain().ainvoke({
            "user_input": state.user_input,
            "history": _format_history(state.history),
        })
        res = analysis.model_dump()
        is_out_of_scope = (analysis.intent == "out_of_scope")
        is_greeting = (analysis.intent == "greeting")
        # Reset per-turn transient fields so previous turn state doesn't leak into new turn
        res.update({
            "clarification_question": None,
            "clarification_options": [],
            "context_assessment_status": "out_of_scope" if is_out_of_scope else None,
            "re_retrieval_count": 0,
            "sql_query": None,
            "sql_results": None,
            "error": None,
            "final_answer": None,
            "query_variations": [],
            "search_queries": [],
            "retrieved_examples": [],
            "retrieved_rules": [],
            "retrieved_tables": [],
            "value_hints": [],
            "is_context_sufficient": False,
            "schema_context": {},
            "retry_count": 0,
        })
        if is_out_of_scope and not res.get("direct_response"):
            res["direct_response"] = (
                "I am an e-commerce assistant specialized solely in querying our store database. "
                "Out-of-scope questions will not be answered. Please ask about products, orders, customers, inventory, coupons, or sales revenue."
            )
        elif is_greeting and not res.get("direct_response"):
            res["direct_response"] = (
                "Hello! I am your AI e-commerce assistant. How can I help you explore store sales, products, orders, customers, or inventory today?"
            )
        return res
    except Exception as e:
        return {
            "intent": "database_query",
            "direct_response": None,
            "is_follow_up": False,
            "processed_query": state.user_input,
            "clarification_question": None,
            "clarification_options": [],
            "context_assessment_status": None,
            "re_retrieval_count": 0,
            "sql_query": None,
            "sql_results": None,
            "error": str(e),
            "final_answer": None,
            "query_variations": [],
            "search_queries": [],
            "retrieved_examples": [],
            "retrieved_rules": [],
            "retrieved_tables": [],
            "value_hints": [],
            "is_context_sufficient": False,
            "schema_context": {},
            "retry_count": 0,
        }
