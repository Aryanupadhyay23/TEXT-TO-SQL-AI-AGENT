"""API Request and Response Pydantic Schemas."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Schema for incoming chat query requests."""

    query: str = Field(..., description="User question or statement")
    thread_id: Optional[str] = Field(
        default="default",
        description="Session or thread ID for conversational memory persistence",
    )
    history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Optional client-provided history override",
    )


class ChatResponse(BaseModel):
    """Schema for outgoing chat query responses."""

    query: str
    thread_id: Optional[str] = "default"
    intent: Optional[str] = None
    is_follow_up: bool = False
    processed_query: Optional[str] = None
    final_answer: str
    sql_query: Optional[str] = None
    sql_results: Optional[List[Dict[str, Any]]] = None
    is_context_sufficient: bool = False
    retrieved_examples: List[Dict[str, Any]] = []
    retrieved_rules: List[str] = []
    retrieved_tables: List[str] = []
    value_hints: List[Dict[str, Any]] = []
    schema_context: Dict[str, Any] = {}
    error: Optional[str] = None
    retry_count: int = 0
    query_variations: List[str] = []
    search_queries: List[str] = []
