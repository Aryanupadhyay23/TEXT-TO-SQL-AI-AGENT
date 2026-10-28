"""SQL Generation and Schema Sufficiency Pydantic Models."""

from typing import List, Optional
from pydantic import BaseModel, Field


class GeneratedSQL(BaseModel):
    """Structured Pydantic model for generated SQL output."""

    sql_query: str = Field(
        description="The raw, valid executable MySQL SELECT query without markdown fences."
    )
    explanation: Optional[str] = Field(
        default=None,
        description="Brief explanation of the tables, joins, and calculations used.",
    )


class ContextAssessment(BaseModel):
    """Structured evaluation of retrieved context and query disambiguation."""

    status: str = Field(
        default="sufficient",
        description=(
            "One of: 'sufficient', 'needs_targeted_retrieval', 'ambiguous', 'out_of_scope'.\n"
            "- 'sufficient': context has all required tables, columns, and rules to generate accurate SQL.\n"
            "- 'needs_targeted_retrieval': specific missing concepts, tables, or terms need to be re-queried from Chroma/knowledge.\n"
            "- 'ambiguous': user request has multiple conflicting interpretations or missing critical parameter choices; must ask human back.\n"
            "- 'out_of_scope': requested information is fundamentally outside the e-commerce database domain (e.g. employee salaries, server metrics, external weather)."
        ),
    )
    reasoning: str = Field(
        default="",
        description="Clear explanation of the assessment decision.",
    )
    missing_search_queries: List[str] = Field(
        default_factory=list,
        description="Targeted specific search queries for ChromaDB/BM25 to fetch the missing concepts/tables/rules.",
    )
    clarification_question: Optional[str] = Field(
        default=None,
        description="Polite, clarifying question asking the user to choose between the ambiguous options.",
    )
    clarification_options: List[str] = Field(
        default_factory=list,
        description="Specific option pills/choices for the user (e.g. ['By Sales Revenue', 'By Review Ratings', 'By Units Sold']).",
    )
    out_of_scope_message: Optional[str] = Field(
        default=None,
        description="Polite, honest explanation of why this information is not available in our database.",
    )


class SufficiencyEvaluation(BaseModel):
    """Structured schema for determining if retrieved schema context is sufficient (backwards-compatible wrapper)."""

    is_sufficient: bool = Field(
        description="True if retrieved examples/rules/schema are enough to construct SQL."
    )
    reasoning: str = Field(
        default="",
        description="Reasoning explaining whether the schema is sufficient or what is missing.",
    )
    missing_tables: List[str] = Field(
        default_factory=list,
        description="List of table names that are missing and need to be retrieved.",
    )
    missing_terms: List[str] = Field(
        default_factory=list,
        description="List of specific business concepts or keywords that were not found in context.",
    )
