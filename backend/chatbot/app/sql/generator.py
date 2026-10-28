import re
import uuid
import logging
from typing import List, Dict, Any, Optional
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage
from chatbot.app.models import AgentState, GeneratedSQL
from chatbot.app.llm.base import get_llm
from chatbot.app.prompts.sql_generation import SQL_GENERATION_PROMPT
from chatbot.tools import run_sql, search_knowledge_and_examples
from chatbot.utils.formatting import (
    format_examples as _format_examples,
    format_rules as _format_rules,
    format_value_hints as _format_value_hints,
    format_schema as _format_schema,
)
from chatbot.utils.sql_helpers import clean_sql, extract_sql_from_text

logger = logging.getLogger(__name__)

# Lazy-initialized structured LLM chain
_sql_chain = None
_llm_with_tools = None


def _get_tools_model():
    """Lazy-initializes LLM with dual bound tools (run_sql & search_knowledge_and_examples)."""
    global _llm_with_tools
    if _llm_with_tools is None:
        tools = [run_sql, search_knowledge_and_examples]
        _llm_with_tools = get_llm().bind_tools(tools)
    return _llm_with_tools


def _get_sql_chain():
    """Lazy-initializes the SQL generation chain."""
    global _sql_chain
    if _sql_chain is None:
        _sql_chain = SQL_GENERATION_PROMPT | get_llm().with_structured_output(GeneratedSQL)
    return _sql_chain


def _build_context(state: AgentState) -> str:
    """Builds a structured prompt context containing schema, join paths, value hints, and few-shots."""
    sections = []

    # 1. Target Schema & Relational Join Paths (Pruned & Connected)
    if state.schema_context and state.schema_context.get("tables"):
        sections.append(f"### DATABASE SCHEMA & JOIN PATHS\n{_format_schema(state.schema_context)}")

    # 2. Database Literal Mappings & Filter Hints (From Entity Catalog Grounding)
    if state.value_hints:
        val_text = _format_value_hints(state.value_hints)
        if val_text:
            sections.append(f"### VALUE MAPPINGS & FILTER HINTS\n{val_text}")

    # 3. Retrieved Business Rules
    if state.retrieved_rules:
        sections.append(f"### BUSINESS RULES & KPI DEFINITIONS\n{_format_rules(state.retrieved_rules)}")

    # 4. Retrieved Few-Shot Examples
    if state.retrieved_examples:
        sections.append(
            f"### HELPFUL REFERENCE QUERY SAMPLES\n"
            f"*(These are reference sample queries to help you understand the appropriate tables, joins, and filters. Adapt them to fit the user's request.)*\n"
            f"{_format_examples(state.retrieved_examples)}"
        )

    return "\n\n".join(sections) if sections else "No prior context available."


async def sql_generation_node(state: AgentState) -> Dict[str, Any]:
    """LangGraph node: Generates SQL with autonomous tool fallback (run_sql & search_knowledge_and_examples)."""
    user_query = state.processed_query or state.user_input
    context_str = _build_context(state)

    messages = SQL_GENERATION_PROMPT.format_messages(
        user_query=user_query,
        context=context_str,
    )

    tool_map = {
        "run_sql": run_sql,
        "search_knowledge_and_examples": search_knowledge_and_examples,
    }

    tools_model = _get_tools_model()
    max_tool_iterations = 3
    tool_iteration = 0
    generated_sql = None

    try:
        while tool_iteration < max_tool_iterations:
            response = await tools_model.ainvoke(messages)
            tool_calls = getattr(response, "tool_calls", None) or []

            if not tool_calls:
                # Fast-path or completion: LLM emitted text/SQL directly
                content = response.content if isinstance(response.content, str) else str(response.content)
                extracted = extract_sql_from_text(content)
                if extracted:
                    generated_sql = extracted
                    break

                # If tool calls were made earlier, ask model for the final query given message history
                if tool_iteration > 0:
                    messages.append(response)
                    messages.append(HumanMessage(content="Please provide the final executable MySQL SELECT query inside a ```sql ... ``` block."))
                    final_res = await tools_model.ainvoke(messages)
                    final_content = final_res.content if isinstance(final_res.content, str) else str(final_res.content)
                    extracted = extract_sql_from_text(final_content)
                    if extracted:
                        generated_sql = extracted
                        break

                # Fallback to structured chain if raw text output isn't a direct SQL statement
                try:
                    res: GeneratedSQL = await _get_sql_chain().ainvoke({
                        "user_query": user_query,
                        "context": context_str,
                    })
                    generated_sql = clean_sql(res.sql_query)
                except Exception:
                    generated_sql = extract_sql_from_text(content)
                break

            # Tool Exploration Path: execute requested tool calls
            messages.append(response)
            for tc in tool_calls:
                t_name = tc.get("name")
                t_args = tc.get("args", {})
                t_id = tc.get("id") or str(uuid.uuid4())

                tool_func = tool_map.get(t_name)
                if tool_func:
                    try:
                        logger.info("Agent invoking tool: %s with args: %s", t_name, t_args)
                        t_output = await tool_func.ainvoke(t_args)
                    except Exception as err:
                        t_output = f"Tool execution failed: {err}"
                else:
                    t_output = f"Unknown tool: '{t_name}'. Allowed tools are: {list(tool_map.keys())}"

                messages.append(ToolMessage(content=str(t_output), tool_call_id=t_id, name=t_name))

            tool_iteration += 1

        # If loop reached max iterations without returning final SQL, extract or generate
        if not generated_sql:
            messages.append(HumanMessage(content="Please provide the final executable MySQL query inside a ```sql ... ``` block."))
            try:
                final_res = await tools_model.ainvoke(messages)
                final_content = final_res.content if isinstance(final_res.content, str) else str(final_res.content)
                generated_sql = extract_sql_from_text(final_content)
            except Exception:
                pass

        if not generated_sql:
            res: GeneratedSQL = await _get_sql_chain().ainvoke({
                "user_query": user_query,
                "context": context_str,
            })
            generated_sql = clean_sql(res.sql_query)

        return {
            "sql_query": generated_sql,
            "error": None,
            "retry_count": 0,
        }
    except Exception as e:
        err_msg = str(e)
        extracted = _extract_sql_from_text(err_msg)
        if extracted:
            return {
                "sql_query": extracted,
                "error": None,
                "retry_count": 0,
            }
        return {
            "sql_query": None,
            "error": f"SQL generation failed: {err_msg}",
            "retry_count": 0,
        }

