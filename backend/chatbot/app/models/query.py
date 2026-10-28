"""Query Analysis and Multi-Query Expansion Pydantic Models."""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class QueryAnalysis(BaseModel):
    """Structured schema for query intent classification and understanding."""

    intent: Literal["greeting", "answer_from_memory", "database_query", "out_of_scope"] = Field(
        description="Category: 'greeting', 'answer_from_memory', 'database_query', or 'out_of_scope'."
    )
    direct_response: Optional[str] = Field(
        default=None,
        description="Direct answer if intent is 'greeting', 'answer_from_memory', or 'out_of_scope'. Null for 'database_query'.",
    )
    is_follow_up: bool = Field(
        default=False,
        description="True if the question refers to or depends on previous questions or results.",
    )
    processed_query: str = Field(
        description="Clean standalone query. If follow-up, rewritten with previous context included. If sufficient, passed as-is.",
    )


class QueryVariations(BaseModel):
    """Structured schema for multi-query search variations with filler words removed."""

    variations: List[str] = Field(
        default_factory=list,
        description="List of exactly 3 distinct search variations with conversational filler removed.",
    )
