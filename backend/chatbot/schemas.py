import time
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    """Payload for frontend chat interaction."""
    message: str = Field(..., description="User message or query")
    conversation_id: Optional[str] = Field(None, description="Active session or thread conversation ID")


class CreateMemoryRequest(BaseModel):
    """Payload for adding a new memory to ChromaDB across all components."""
    collection: str = Field(
        default="question_sql_pairs",
        description="Target collection: question_sql_pairs, business_knowledge, or schema_tables",
    )
    question: str = Field(..., description="Training question, rule title, or table name")
    sql: Optional[str] = Field(None, description="Executable SQL query (for SQL pairs)")
    content: Optional[str] = Field(None, description="Rule description, explanation, or schema DDL")
    tables: Optional[str] = Field(None, description="Comma-separated associated tables")


class UpdateMemoryRequest(BaseModel):
    """Payload for updating a ChromaDB memory."""
    collection: Optional[str] = Field(
        default=None,
        description="Optional collection name if known",
    )
    question: str = Field(..., description="Training question, rule title, or table name")
    sql: Optional[str] = Field(None, description="Executable SQL query")
    content: Optional[str] = Field(None, description="Rule description, explanation, or schema DDL")
    tables: Optional[str] = Field(None, description="Comma-separated associated tables")


from chatbot.utils.json_helpers import format_sse_chunk as _format_chunk

