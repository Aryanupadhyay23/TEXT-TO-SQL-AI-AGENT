"""Chatbot API Unified Router Package.

Combines modular sub-routers:
- chat: /api/chat/message, /api/chat/stream, /api/chat/poll, /api/chat
- memories: /api/chat/memories (few-shots, rules, schema table inspection)
- schema: /api/chat/schema (live table schema introspection)
"""

from fastapi import APIRouter

from chatbot.routes.chat import (
    router as chat_router,
    chat_message_stream,
    chat_stream_post,
    chat_stream_get,
    chat_message_poll,
    chat_direct,
    stream_agent_execution,
)
from chatbot.routes.memories import (
    router as memories_router,
    list_memories,
    create_memory,
    update_memory,
    delete_memory,
    reset_all_memories,
)
from chatbot.routes.schema import (
    router as schema_router,
)

router = APIRouter(prefix="/api/chat", tags=["Chatbot"])

# Include modular sub-routers
router.include_router(chat_router)
router.include_router(memories_router)
router.include_router(schema_router)

__all__ = [
    "router",
    "chat_router",
    "memories_router",
    "schema_router",
    "chat_message_stream",
    "chat_stream_post",
    "chat_stream_get",
    "chat_message_poll",
    "chat_direct",
    "stream_agent_execution",
    "list_memories",
    "create_memory",
    "update_memory",
    "delete_memory",
    "reset_all_memories",
]
