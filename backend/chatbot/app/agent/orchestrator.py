import asyncio
import logging
import os
from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from chatbot.app.models import AgentState
from chatbot.app.llm.reasoning import query_understanding_node
from chatbot.app.retrieval.query_expander import query_expansion_node
from chatbot.app.retrieval.retriever import retriever_node
from chatbot.app.sql.generator import sql_generation_node
from chatbot.app.sql.executor import sql_execution_node
from chatbot.app.sql.repair import sql_repair_node
from chatbot.app.llm.answer_generator import answer_generation_node


# Conditional Routing Functions
def route_query_understanding(state: AgentState) -> Literal["query_expansion", "answer_generation"]:
    """Routes query based on classified intent."""
    if state.intent == "database_query":
        return "query_expansion"
    # For greetings, answers directly from conversation memory, or out_of_scope
    return "answer_generation"


def route_execution(state: AgentState) -> Literal["answer_generation", "sql_repair"]:
    """Routes to repair loop if SQL execution failed, or to answer generation if successful/exhausted."""
    if state.error is None:
        return "answer_generation"

    # Self-correction loop: retry up to max_retries
    if state.retry_count < state.max_retries:
        return "sql_repair"

    # Retries exhausted: summarize findings or explain error gracefully
    return "answer_generation"


# Graph Assembly
def create_agent_graph(checkpointer=None):
    """
    Builds and compiles the complete multi-step Text-to-SQL agent workflow:
    Phase 1: Deterministic Warm-Start RAG (Query Understanding -> Query Expansion -> Hybrid Retriever)
    Phase 2: Autonomous SQL Agent (sql_generation with Dual Bound Tools: run_sql & search_knowledge_and_examples)
    Phase 3: Execution & Synthesis (sql_execution -> answer_generation -> END)
    """
    workflow = StateGraph(AgentState)

    # 1. Register Active Nodes
    workflow.add_node("query_understanding", query_understanding_node)
    workflow.add_node("query_expansion", query_expansion_node)
    workflow.add_node("retriever", retriever_node)
    workflow.add_node("sql_generation", sql_generation_node)
    workflow.add_node("sql_execution", sql_execution_node)
    workflow.add_node("sql_repair", sql_repair_node)
    workflow.add_node("answer_generation", answer_generation_node)

    # 2. Add Edges & Conditional Branches
    workflow.add_edge(START, "query_understanding")

    workflow.add_conditional_edges(
        "query_understanding",
        route_query_understanding,
        {
            "query_expansion": "query_expansion",
            "answer_generation": "answer_generation",
        },
    )

    # Multi-Query expansion node feeds directly into retriever
    workflow.add_edge("query_expansion", "retriever")

    # Warm Context Bundle connects directly to Autonomous SQL Agent
    workflow.add_edge("retriever", "sql_generation")

    # SQL Agent output feeds into safe SQL execution
    workflow.add_edge("sql_generation", "sql_execution")

    workflow.add_conditional_edges(
        "sql_execution",
        route_execution,
        {
            "answer_generation": "answer_generation",
            "sql_repair": "sql_repair",
        },
    )

    # Repair loops back to execution for re-validation and retry
    workflow.add_edge("sql_repair", "sql_execution")

    workflow.add_edge("answer_generation", END)

    # 3. Compile with State Checkpointer
    return workflow.compile(checkpointer=checkpointer)


logger = logging.getLogger(__name__)


def get_checkpointer() -> MemorySaver:
    """
    Initializes native LangGraph MemorySaver for conversational state management.
    """
    return MemorySaver()


# Global compiled graph instance backed by native LangGraph MemorySaver
checkpointer_instance = get_checkpointer()
agent_graph = create_agent_graph(checkpointer=checkpointer_instance)


