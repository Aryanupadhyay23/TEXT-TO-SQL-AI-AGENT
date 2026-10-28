"""
Chatbot Execution Routes

Endpoints for executing the Agentic Text-to-SQL system:
- /api/chat/message & /api/chat/stream (POST): SSE streaming endpoint for real-time progress and tokens
- /api/chat/stream (GET): Browser EventSource SSE streaming endpoint
- /api/chat/poll (POST): Synchronous polling endpoint
- /api/chat (POST): Direct programmatic agent execution
"""

import asyncio
import json
import logging
import uuid
from typing import List, Dict, Any, AsyncGenerator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from auth.deps import get_current_user
from chatbot.app.agent.orchestrator import agent_graph
from chatbot.app.models import AgentState, ChatRequest, ChatResponse
from chatbot.config.settings import settings
from chatbot.schemas import (
    ChatMessageRequest,
    _format_chunk,
)

logger = logging.getLogger(__name__)

router = APIRouter()


async def stream_agent_execution(
    user_query: str,
    conv_id: str,
    req_id: str,
) -> AsyncGenerator[str, None]:
    """
    Executes the Text-to-SQL agent workflow and streams Server-Sent Events (SSE)
    in real time including status cards, SQL queries, tabular results, and token-by-token answer.
    """
    config = {"configurable": {"thread_id": conv_id}}
    initial_input = {"user_input": user_query}

    emitted_sql = False
    emitted_table = False
    emitted_answer = False
    emitted_error = False
    last_error = None
    active_sql = None

    try:
        async for node_update in agent_graph.astream(
            initial_input,
            config=config,
            stream_mode="updates",
        ):
            for node_name, values in node_update.items():
                if not isinstance(values, dict):
                    continue

                # =======================================================
                # Detailed Workflow Execution Step Cards (All Users)
                # =======================================================
                # 1. Query Understanding
                if node_name == "query_understanding":
                    intent = values.get("intent", "database_query")
                    p_query = values.get("processed_query") or user_query
                    card_data = {
                        "type": "status_card",
                        "id": f"step-1-understanding-{req_id}",
                        "title": "1. Query Understanding & Classification",
                        "status": "success",
                        "description": f"Classified intent as '{intent}'",
                        "metadata": {
                            "Intent": intent,
                            "Processed Query": p_query,
                            "Is Follow-Up": str(values.get("is_follow_up", False)),
                        },
                    }
                    yield f"data: {json.dumps(_format_chunk('status_card', card_data, conv_id, req_id), default=str)}\n\n"

                # 2. Query Expansion
                elif node_name == "query_expansion":
                    variations = values.get("query_variations", [])
                    card_data = {
                        "type": "status_card",
                        "id": f"step-2-expansion-{req_id}",
                        "title": "2. Query Expansion (Multi-Query)",
                        "status": "success",
                        "description": f"Generated {len(variations)} search variations for multi-index retrieval",
                        "metadata": {
                            f"Variation {i+1}": v for i, v in enumerate(variations)
                        },
                    }
                    yield f"data: {json.dumps(_format_chunk('status_card', card_data, conv_id, req_id), default=str)}\n\n"

                # 3. Retriever
                elif node_name == "retriever":
                    tables = values.get("retrieved_tables", [])
                    examples = values.get("retrieved_examples", [])
                    rules = values.get("retrieved_rules", [])
                    hints = values.get("value_hints", [])
                    card_data = {
                        "type": "status_card",
                        "id": f"step-3-retriever-{req_id}",
                        "title": "3. Multi-Index Hybrid Retrieval (RRF)",
                        "status": "success",
                        "description": f"Retrieved {len(tables)} tables ({', '.join(tables) if tables else 'None'}), {len(examples)} SQL pairs, {len(rules)} business rules",
                        "metadata": {
                            "Target Tables": ", ".join(tables) if tables else "None",
                            "Few-Shot SQL Pairs": f"{len(examples)} examples pooled",
                            "Business Rules": f"{len(rules)} rules matched",
                            "Literal Entity Hints": f"{len(hints)} conditions matched",
                        },
                    }
                    yield f"data: {json.dumps(_format_chunk('status_card', card_data, conv_id, req_id), default=str)}\n\n"

                    # Detailed Retrieved Memories Card
                    memories_payload = {
                        "type": "retrieved_memory",
                        "id": f"step-3b-memories-{req_id}",
                        "title": "Retrieved ChromaDB Memories (All Types)",
                        "status": "success",
                        "description": f"Loaded {len(examples)} SQL Pair(s), {len(rules)} Business Rule(s), {len(tables)} Schema Table(s), {len(hints)} Entity Hint(s)",
                        "memories": {
                            "sql_pairs": examples,
                            "business_rules": rules,
                            "schema_tables": tables,
                            "entity_hints": hints,
                        },
                    }
                    yield f"data: {json.dumps(_format_chunk('retrieved_memory', memories_payload, conv_id, req_id), default=str)}\n\n"

                # 4. Autonomous SQL Generation Card & SQL block
                elif node_name == "sql_generation":
                    sql_query = values.get("sql_query")
                    gen_err = values.get("error")
                    if sql_query:
                        active_sql = sql_query
                        emitted_sql = True
                        card_data = {
                            "type": "status_card",
                            "id": f"step-4-sql-gen-{req_id}",
                            "title": "4. Autonomous SQL Generation (Fast-Path / Tool Exploration)",
                            "status": "success",
                            "description": values.get("sql_explanation") or "Synthesized verified SQL statement based on retrieved schema and autonomous tool exploration",
                            "metadata": {
                                "Target Dialect": "MySQL 8.0+",
                                "Query Length": f"{len(sql_query)} characters",
                                "Generated Query": sql_query,
                            },
                        }
                        yield f"data: {json.dumps(_format_chunk('status_card', card_data, conv_id, req_id), default=str)}\n\n"
                        chunk = _format_chunk("sql", sql_query, conv_id, req_id)
                        yield f"data: {json.dumps(chunk, default=str)}\n\n"
                    elif gen_err:
                        card_data = {
                            "type": "status_card",
                            "id": f"step-4-sql-gen-{req_id}",
                            "title": "4. Autonomous SQL Generation",
                            "status": "error",
                            "description": f"Query generation syntax/LLM issue: {gen_err}",
                            "metadata": {
                                "Status": "Failed",
                                "Error": str(gen_err),
                            },
                        }
                        yield f"data: {json.dumps(_format_chunk('status_card', card_data, conv_id, req_id), default=str)}\n\n"

                # 5. SQL Execution Card
                elif node_name == "sql_execution":
                    exec_time = values.get("execution_time", 0.0)
                    exec_err = values.get("error")
                    rows = values.get("sql_results") or []
                    query_to_display = active_sql or "N/A"
                    card_data = {
                        "type": "status_card",
                        "id": f"step-5-sql-exec-{req_id}",
                        "title": "5. Safe SQL Execution & Guardrails",
                        "status": "error" if exec_err else "success",
                        "description": (
                            f"Query executed successfully in {exec_time}s returning {len(rows)} row(s)"
                            if not exec_err
                            else f"Execution error: {exec_err}"
                        ),
                        "metadata": {
                            "Execution Time": f"{exec_time}s",
                            "Rows Returned": len(rows),
                            "Status": "Error" if exec_err else "Success",
                            "Executed Query": query_to_display,
                        },
                    }
                    yield f"data: {json.dumps(_format_chunk('status_card', card_data, conv_id, req_id), default=str)}\n\n"

                # SQL Repair Cycle (if error corrected)
                elif node_name == "sql_repair":
                    retry_c = values.get("retry_count", 1)
                    repaired_sql = values.get("sql_query")
                    repair_err = values.get("error")

                    if repaired_sql:
                        active_sql = repaired_sql
                        emitted_sql = True
                        card_data = {
                            "type": "status_card",
                            "id": f"step-5b-repair-{retry_c}-{req_id}",
                            "title": f"SQL Self-Correction Cycle (Attempt {retry_c})",
                            "status": "success",
                            "description": f"Successfully corrected SQL query for execution retry #{retry_c}",
                            "metadata": {
                                "Attempt": retry_c,
                                "Status": "Corrected",
                                "Corrected Query": repaired_sql,
                            },
                        }
                        yield f"data: {json.dumps(_format_chunk('status_card', card_data, conv_id, req_id), default=str)}\n\n"
                        chunk = _format_chunk("sql", repaired_sql, conv_id, req_id)
                        yield f"data: {json.dumps(chunk, default=str)}\n\n"
                    else:
                        card_data = {
                            "type": "status_card",
                            "id": f"step-5b-repair-{retry_c}-{req_id}",
                            "title": f"SQL Self-Correction Cycle (Attempt {retry_c})",
                            "status": "error",
                            "description": f"Repair cycle failed: {repair_err or 'Unable to rectify SQL syntax'}",
                            "metadata": {
                                "Attempt": retry_c,
                                "Status": "Failed",
                                "Error": str(repair_err),
                            },
                        }
                        yield f"data: {json.dumps(_format_chunk('status_card', card_data, conv_id, req_id), default=str)}\n\n"

                # 6. Answer Generation Card
                elif node_name == "answer_generation":
                    ans = values.get("final_answer") or values.get("direct_response") or "Synthesized executive natural language answer from query results"
                    card_data = {
                        "type": "status_card",
                        "id": f"step-6-answer-{req_id}",
                        "title": "6. Natural Language Answer Synthesis",
                        "status": "success",
                        "description": str(ans)[:300] + ("..." if len(str(ans)) > 300 else ""),
                        "metadata": {
                            "Status": "Completed",
                            "Final Answer": str(ans),
                        },
                    }
                    yield f"data: {json.dumps(_format_chunk('status_card', card_data, conv_id, req_id), default=str)}\n\n"

                # =======================================================
                # Returned SQL Result Table (All Users)
                # =======================================================
                sql_results = values.get("sql_results")
                if sql_results is not None and not emitted_table:
                    emitted_table = True
                    chunk = _format_chunk("table", sql_results, conv_id, req_id)
                    yield f"data: {json.dumps(chunk, default=str)}\n\n"

                # Safeguard: Ensure active SQL block is emitted
                if active_sql and not emitted_sql:
                    emitted_sql = True
                    chunk = _format_chunk("sql", active_sql, conv_id, req_id)
                    yield f"data: {json.dumps(chunk, default=str)}\n\n"

                # =======================================================
                # Final Answer Token-by-Token Streaming
                # =======================================================
                final_answer = values.get("final_answer") or values.get("direct_response")
                if final_answer and not emitted_answer:
                    emitted_answer = True
                    words = final_answer.split(" ")
                    for i, word in enumerate(words):
                        token = word + (" " if i < len(words) - 1 else "")
                        chunk = _format_chunk("text", token, conv_id, req_id)
                        yield f"data: {json.dumps(chunk, default=str)}\n\n"
                        await asyncio.sleep(0.012)

                # Error state during execution
                error = values.get("error")
                if error:
                    last_error = error
                    retry = values.get("retry_count", 0)
                    max_retries = values.get("max_retries", getattr(settings, "MAX_SQL_RETRIES", 6))
                    if retry is not None and retry >= max_retries:
                        emitted_error = True
                        chunk = _format_chunk("error", error, conv_id, req_id)
                        yield f"data: {json.dumps(chunk, default=str)}\n\n"

        if not emitted_answer:
            if last_error and not emitted_error:
                chunk = _format_chunk("error", last_error, conv_id, req_id)
                yield f"data: {json.dumps(chunk, default=str)}\n\n"

            fallback_msg = (
                f"Unable to retrieve records: {last_error}"
                if last_error
                else "I was unable to retrieve an answer for your request. Please try rephrasing your question."
            )
            words = fallback_msg.split(" ")
            for i, word in enumerate(words):
                token = word + (" " if i < len(words) - 1 else "")
                chunk = _format_chunk("text", token, conv_id, req_id)
                yield f"data: {json.dumps(chunk, default=str)}\n\n"
                await asyncio.sleep(0.012)

        yield f"data: [DONE] {conv_id}\n\n"

    except Exception as e:
        logger.exception("Chat stream execution failed: %s", e)
        err_chunk = _format_chunk("error", str(e), conv_id, req_id)
        yield f"data: {json.dumps(err_chunk, default=str)}\n\n"
        yield f"data: [DONE] {conv_id}\n\n"


# 1. Real-Time Streaming SSE Endpoints

@router.post("/message")
@router.post("/stream")
async def chat_message_stream(
    body: ChatMessageRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Executes the Text-to-SQL agent workflow and streams Server-Sent Events (SSE)
    in real time with status cards, SQL statements, data tables, and token-by-token answer.
    """
    conv_id = body.conversation_id or uuid.uuid4().hex
    req_id = uuid.uuid4().hex
    user_query = body.message.strip()

    if not user_query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty."
        )

    return StreamingResponse(
        stream_agent_execution(user_query, conv_id, req_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


chat_stream_post = chat_message_stream


@router.get("/stream")
async def chat_stream_get(
    message: str = Query(..., description="User query or message"),
    conversation_id: Optional[str] = Query(None, description="Optional conversation session ID"),
    current_user: dict = Depends(get_current_user),
):
    """
    Dedicated GET streaming endpoint (/api/chat/stream?message=...) compatible
    with standard browser EventSource listeners.
    """
    user_query = message.strip()
    if not user_query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query parameter 'message' cannot be empty."
        )

    conv_id = conversation_id or uuid.uuid4().hex
    req_id = uuid.uuid4().hex

    return StreamingResponse(
        stream_agent_execution(user_query, conv_id, req_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# 2. Synchronous Polling Endpoint

@router.post("/poll")
async def chat_message_poll(
    body: ChatMessageRequest,
    current_user: dict = Depends(get_current_user),
):
    """Executes agent workflow and returns all generated chunks synchronously."""
    conv_id = body.conversation_id or uuid.uuid4().hex
    req_id = uuid.uuid4().hex
    user_query = body.message.strip()

    if not user_query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty."
        )

    try:
        config = {"configurable": {"thread_id": conv_id}}
        initial_state = AgentState(user_input=user_query)
        result = await agent_graph.ainvoke(initial_state, config=config)

        chunks: List[Dict[str, Any]] = []

        # 1. Retrieved Memory (All Users)
        if result.get("retrieved_examples") or result.get("retrieved_rules") or result.get("retrieved_tables") or result.get("value_hints"):
            mem_data = {
                "type": "retrieved_memory",
                "id": f"memories-{req_id}",
                "title": "Retrieved ChromaDB Memories (All Types)",
                "status": "success",
                "description": f"Retrieved {len(result.get('retrieved_examples') or [])} SQL pair(s), {len(result.get('retrieved_rules') or [])} business rule(s), {len(result.get('retrieved_tables') or [])} schema table(s)",
                "memories": {
                    "sql_pairs": result.get("retrieved_examples") or [],
                    "business_rules": result.get("retrieved_rules") or [],
                    "schema_tables": result.get("retrieved_tables") or [],
                    "entity_hints": result.get("value_hints") or [],
                },
            }
            chunks.append(_format_chunk("retrieved_memory", mem_data, conv_id, req_id))

        # 2. SQL Query (All Users)
        if result.get("sql_query"):
            chunks.append(_format_chunk("sql", result["sql_query"], conv_id, req_id))

        # 3. SQL Results Table (All Users)
        if result.get("sql_results") is not None:
            chunks.append(_format_chunk("table", result["sql_results"], conv_id, req_id))

        # 4. Final LLM Answer (Both Admin and User)
        answer = result.get("final_answer") or result.get("direct_response") or "No answer could be generated."
        chunks.append(_format_chunk("text", answer, conv_id, req_id))

        if result.get("error"):
            chunks.append(_format_chunk("error", result["error"], conv_id, req_id))

        return {
            "chunks": chunks,
            "conversation_id": conv_id,
            "request_id": req_id,
            "total_chunks": len(chunks),
        }

    except Exception as e:
        logger.exception("Chat poll failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent workflow error: {str(e)}"
        )


# 3. Direct Programmatic Execution Endpoint

@router.post("/", response_model=ChatResponse)
async def chat_direct(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
) -> ChatResponse:
    """Executes the full agentic Text-to-SQL pipeline and returns structured metadata."""
    try:
        thread_id = request.thread_id or uuid.uuid4().hex
        config = {"configurable": {"thread_id": thread_id}}

        initial_input = {"user_input": request.query}
        if request.history:
            initial_input["history"] = request.history

        result = await agent_graph.ainvoke(initial_input, config=config)

        return ChatResponse(
            query=request.query,
            thread_id=thread_id,
            intent=result.get("intent"),
            is_follow_up=result.get("is_follow_up", False),
            processed_query=result.get("processed_query"),
            final_answer=result.get("final_answer") or "No answer could be generated.",
            sql_query=result.get("sql_query"),
            sql_results=result.get("sql_results"),
            is_context_sufficient=result.get("is_context_sufficient", False),
            retrieved_examples=result.get("retrieved_examples", []),
            retrieved_rules=result.get("retrieved_rules", []),
            retrieved_tables=result.get("retrieved_tables", []),
            value_hints=result.get("value_hints", []),
            schema_context=result.get("schema_context", {}),
            error=result.get("error"),
            retry_count=result.get("retry_count", 0),
            query_variations=result.get("query_variations", []),
            search_queries=result.get("search_queries", []),
        )
    except Exception as e:
        logger.exception("Direct agent query failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent workflow error: {str(e)}"
        )


# ==============================================================================
# Local SQLite Conversation Memory Management Endpoints
# ==============================================================================

@router.get("/conversations/{conversation_id}")
async def get_conversation_memory(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Retrieves full conversation turns and state memory stored in local SQLite checkpointer."""
    config = {"configurable": {"thread_id": conversation_id}}
    try:
        state = await agent_graph.aget_state(config)
        values = state.values if state else {}
        history = values.get("history", [])
        return {
            "conversation_id": conversation_id,
            "turns_count": len(history),
            "history": history,
            "latest_intent": values.get("intent"),
            "latest_sql": values.get("sql_query"),
            "latest_answer": values.get("final_answer"),
        }
    except Exception as e:
        logger.exception("Failed to retrieve conversation memory from SQLite: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch conversation memory: {str(e)}",
        )


@router.delete("/conversations/{conversation_id}")
async def delete_conversation_memory(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Deletes conversation memory and checkpointer thread state from local SQLite."""
    try:
        checkpointer = getattr(agent_graph, "checkpointer", None)
        if hasattr(checkpointer, "adelete_thread"):
            await checkpointer.adelete_thread(conversation_id)
        elif hasattr(checkpointer, "delete_thread"):
            checkpointer.delete_thread(conversation_id)

        return {
            "status": "success",
            "conversation_id": conversation_id,
            "message": "Conversation memory cleared from local SQLite database.",
        }
    except Exception as e:
        logger.exception("Failed to delete conversation memory: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear conversation memory: {str(e)}",
        )

