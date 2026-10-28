"""
Chatbot Memory Management Routes

ChromaDB CRUD endpoints for golden few-shot SQL examples, business knowledge,
and schema definitions (Admin Only):
- GET /api/chat/memories: List memories
- POST /api/chat/memories: Add memory
- PUT /api/chat/memories/{id}: Update memory
- DELETE /api/chat/memories/{id}: Delete memory
- POST /api/chat/memories/reset: Reset collection memories
"""

import asyncio
import logging
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from auth.deps import get_current_user
from chatbot.app.retrieval.retriever import (
    default_embeddings,
    knowledge_vectorstore,
    schema_vectorstore,
    sql_vectorstore,
    invalidate_bm25_cache,
)
from chatbot.schemas import (
    CreateMemoryRequest,
    UpdateMemoryRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_collection_map():
    """Maps collection key names to Chroma collection instances and display metadata."""
    return {
        "question_sql_pairs": {
            "store": sql_vectorstore,
            "category": "SQL Pair",
            "tool_name": "run_sql",
        },
        "business_knowledge": {
            "store": knowledge_vectorstore,
            "category": "Business Rule",
            "tool_name": "business_rule",
        },
        "schema_tables": {
            "store": schema_vectorstore,
            "category": "Schema Table",
            "tool_name": "schema_table",
        },
    }


@router.get("/memories")
async def list_memories(
    collection: str = "all",
    current_user: dict = Depends(get_current_user),
):
    """
    List memories stored in ChromaDB across all components:
    - question_sql_pairs (Golden Few-Shot SQL)
    - business_knowledge (Business Rules & KPIs)
    - schema_tables (Schema table definitions)
    """

    col_map = _get_collection_map()
    targets = col_map.keys() if collection == "all" else [collection]
    all_memories = []

    try:
        for c_key in targets:
            if c_key not in col_map:
                continue
            entry = col_map[c_key]
            store = entry["store"]
            col = store._collection
            res = await asyncio.to_thread(col.get)

            ids = res.get("ids") or []
            docs = res.get("documents") or []
            metas = res.get("metadatas") or []

            for memory_id, doc, meta in zip(ids, docs, metas):
                meta = meta or {}
                if c_key == "question_sql_pairs":
                    question = doc or meta.get("question", "")
                    sql = meta.get("sql", "")
                    content = ""
                    tables = meta.get("tables", "")
                elif c_key == "business_knowledge":
                    question = meta.get("title") or doc or ""
                    sql = ""
                    content = meta.get("rule") or doc or ""
                    tables = meta.get("tables", "")
                else:  # schema_tables
                    question = meta.get("table_name") or doc or ""
                    sql = ""
                    content = doc or ""
                    tables = meta.get("columns", "")

                all_memories.append({
                    "id": memory_id,
                    "collection": c_key,
                    "category": entry["category"],
                    "question": question,
                    "sql": sql,
                    "content": content,
                    "tables": tables,
                    "tool_name": entry["tool_name"],
                    "timestamp": meta.get("created_at") or meta.get("timestamp") or "",
                })

        all_memories.sort(key=lambda m: m["timestamp"] or "", reverse=True)
        return {"total": len(all_memories), "memories": all_memories}
    except Exception as e:
        logger.exception("Failed to fetch memories from ChromaDB: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch memories: {str(e)}"
        )


@router.post("/memories")
async def create_memory(
    body: CreateMemoryRequest,
    current_user: dict = Depends(get_current_user),
):
    """Add a new memory item to ChromaDB under the specified component collection."""

    col_map = _get_collection_map()
    target_key = body.collection if body.collection in col_map else "question_sql_pairs"
    entry = col_map[target_key]
    col = entry["store"]._collection

    memory_id = uuid.uuid4().hex
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    try:
        if target_key == "question_sql_pairs":
            doc_text = body.question.strip()
            meta = {
                "sql": (body.sql or "").strip(),
                "tables": (body.tables or "").strip(),
                "source": "admin_ui",
                "created_at": now_str,
            }
        elif target_key == "business_knowledge":
            doc_text = body.question.strip()
            meta = {
                "title": body.question.strip(),
                "rule": (body.content or "").strip(),
                "tables": (body.tables or "").strip(),
                "source": "admin_ui",
                "created_at": now_str,
            }
        else:  # schema_tables
            doc_text = f"Table: {body.question.strip()}\n{body.content or ''}"
            meta = {
                "table_name": body.question.strip(),
                "domain": "Admin Custom",
                "columns": (body.tables or "").strip(),
                "source": "admin_ui",
                "created_at": now_str,
            }

        embeddings = await asyncio.to_thread(default_embeddings.embed_documents, [doc_text])
        await asyncio.to_thread(
            col.add,
            ids=[memory_id],
            documents=[doc_text],
            embeddings=embeddings,
            metadatas=[meta],
        )
        invalidate_bm25_cache(target_key)

        return {
            "status": "success",
            "memory": {
                "id": memory_id,
                "collection": target_key,
                "category": entry["category"],
                "question": body.question.strip(),
                "sql": (body.sql or "").strip(),
                "content": (body.content or "").strip(),
                "tables": (body.tables or "").strip(),
                "tool_name": entry["tool_name"],
                "timestamp": now_str,
            },
        }
    except Exception as e:
        logger.exception("Failed to add memory to ChromaDB: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create memory: {str(e)}"
        )


@router.put("/memories/{memory_id}")
async def update_memory(
    memory_id: str,
    body: UpdateMemoryRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update a memory item in ChromaDB across any component."""

    col_map = _get_collection_map()
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    target_key = None
    target_col = None
    existing = None

    if body.collection and body.collection in col_map:
        check_col = col_map[body.collection]["store"]._collection
        res = await asyncio.to_thread(check_col.get, ids=[memory_id])
        if res.get("ids"):
            target_key = body.collection
            target_col = check_col
            existing = res

    if not target_col:
        for c_key, c_info in col_map.items():
            check_col = c_info["store"]._collection
            res = await asyncio.to_thread(check_col.get, ids=[memory_id])
            if res.get("ids"):
                target_key = c_key
                target_col = check_col
                existing = res
                break

    if not target_col or not existing or not existing.get("ids"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found in any collection"
        )

    try:
        meta = existing["metadatas"][0] if existing.get("metadatas") else {}
        meta["updated_at"] = now_str

        if target_key == "question_sql_pairs":
            doc_text = body.question.strip()
            if body.sql is not None:
                meta["sql"] = body.sql.strip()
            if body.tables is not None:
                meta["tables"] = body.tables.strip()
        elif target_key == "business_knowledge":
            doc_text = body.question.strip()
            meta["title"] = body.question.strip()
            if body.content is not None:
                meta["rule"] = body.content.strip()
            if body.tables is not None:
                meta["tables"] = body.tables.strip()
        else:  # schema_tables
            doc_text = f"Table: {body.question.strip()}\n{body.content or ''}"
            meta["table_name"] = body.question.strip()
            if body.tables is not None:
                meta["columns"] = body.tables.strip()

        embeddings = await asyncio.to_thread(default_embeddings.embed_documents, [doc_text])
        await asyncio.to_thread(
            target_col.update,
            ids=[memory_id],
            documents=[doc_text],
            embeddings=embeddings,
            metadatas=[meta],
        )
        invalidate_bm25_cache(target_key)

        return {
            "status": "success",
            "memory": {
                "id": memory_id,
                "collection": target_key,
                "category": col_map[target_key]["category"],
                "question": body.question.strip(),
                "sql": meta.get("sql", ""),
                "content": meta.get("rule", "") or body.content or "",
                "tables": meta.get("tables", "") or meta.get("columns", ""),
                "tool_name": col_map[target_key]["tool_name"],
                "timestamp": meta.get("created_at") or now_str,
            },
        }
    except Exception as e:
        logger.exception("Failed to update memory %s: %s", memory_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update memory: {str(e)}"
        )


@router.delete("/memories/{memory_id}")
async def delete_memory(
    memory_id: str,
    collection: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Delete a memory item by ID from ChromaDB across any component."""

    col_map = _get_collection_map()
    deleted = False

    try:
        targets = [collection] if collection and collection in col_map else col_map.keys()
        for c_key in targets:
            col = col_map[c_key]["store"]._collection
            res = await asyncio.to_thread(col.get, ids=[memory_id])
            if res.get("ids"):
                await asyncio.to_thread(col.delete, ids=[memory_id])
                invalidate_bm25_cache(c_key)
                deleted = True
                break

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Memory not found"
            )

        return {"status": "success", "id": memory_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to delete memory %s: %s", memory_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete memory: {str(e)}"
        )


@router.post("/memories/reset")
async def reset_all_memories(
    collection: str = "all",
    current_user: dict = Depends(get_current_user),
):
    """Clear memories from ChromaDB for a specific collection or all collections."""

    col_map = _get_collection_map()
    targets = col_map.keys() if collection == "all" else [collection]
    total_deleted = 0

    try:
        for c_key in targets:
            if c_key in col_map:
                col = col_map[c_key]["store"]._collection
                res = await asyncio.to_thread(col.get)
                ids = res.get("ids") or []
                if ids:
                    await asyncio.to_thread(col.delete, ids=ids)
                    invalidate_bm25_cache(c_key)
                    total_deleted += len(ids)

        return {"status": "success", "deleted_count": total_deleted}
    except Exception as e:
        logger.exception("Failed to reset memories: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset memories: {str(e)}"
        )
