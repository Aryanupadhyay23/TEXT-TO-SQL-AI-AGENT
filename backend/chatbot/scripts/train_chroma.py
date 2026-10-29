"""Seed or incrementally sync the ChromaDB RAG collections from schema_files/.

Usage:
    python chatbot/scripts/train_chroma.py          # incremental sync
    python chatbot/scripts/train_chroma.py --force  # rebuild every collection
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

SCHEMA_FILES_DIR = BACKEND_DIR / "chatbot" / "schema_files"


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _schema_docs() -> List[Dict]:
    docs = []
    for path in sorted((SCHEMA_FILES_DIR / "schema_of_table").glob("*.json")):
        card = _load_json(path)
        if not isinstance(card, dict):
            continue
        name = card.get("table_name") or path.stem
        cols = [c.get("name") for c in card.get("columns", []) if c.get("name")]
        text = f"Table: {name}\nDescription: {card.get('description', '')}\nColumns: {', '.join(cols)}"
        docs.append({
            "id": f"table::{name}",
            "text": text,
            "metadata": {
                "table_name": name,
                "domain": card.get("domain", ""),
                "checksum": _checksum(text),
            },
        })
    return docs


def _sql_pair_docs() -> List[Dict]:
    docs = []
    for path in sorted((SCHEMA_FILES_DIR / "sql_pairs").glob("*.json")):
        data = _load_json(path)
        if not isinstance(data, dict):
            continue
        domain = data.get("domain") or path.stem.replace("_", " ").title()
        for idx, pair in enumerate(data.get("sql_pairs", [])):
            question = (pair.get("question") or "").strip()
            sql = (pair.get("sql") or "").strip()
            if not question or not sql:
                continue
            docs.append({
                "id": f"pair::{path.stem}::{idx}",
                "text": question,
                "metadata": {
                    "sql": sql,
                    "tables": pair.get("tables", ""),
                    "difficulty": pair.get("difficulty", "medium"),
                    "domain": domain,
                    "checksum": _checksum(question + "\n" + sql),
                },
            })
    return docs


def _rule_docs() -> List[Dict]:
    data = _load_json(SCHEMA_FILES_DIR / "business_text" / "ecommerce_business_rules.json")
    if not isinstance(data, dict):
        return []
    raw_rules = data.get("business_rules") or data.get("rules") or []
    docs = []
    for idx, entry in enumerate(raw_rules):
        if not isinstance(entry, dict):
            continue
        content = (entry.get("content") or entry.get("rule") or "").strip()
        if not content:
            continue
        topic = (entry.get("title") or entry.get("topic") or "Business Rule").strip()
        tables = entry.get("associated_tables") or entry.get("tables") or ""
        if isinstance(tables, list):
            tables = ", ".join(str(t) for t in tables)
        text = f"{topic}: {content}"
        docs.append({
            "id": f"rule::{idx}",
            "text": text,
            "metadata": {
                "topic": topic,
                "rule": content,
                "tables": tables,
                "domain": entry.get("domain", ""),
                "checksum": _checksum(text),
            },
        })
    return docs


def _sync(store, docs: List[Dict], force: bool, label: str) -> int:
    collection = store._collection
    existing = collection.get()
    existing_ids = existing.get("ids") or []

    if force and existing_ids:
        collection.delete(ids=existing_ids)
        existing_ids = []

    desired_ids = {d["id"] for d in docs}
    stale_ids = [i for i in existing_ids if i not in desired_ids]
    if stale_ids:
        collection.delete(ids=stale_ids)

    existing_meta = {}
    lookup_ids = [d["id"] for d in docs]
    if lookup_ids and not force:
        found = collection.get(ids=lookup_ids)
        for doc_id, meta in zip(found.get("ids") or [], found.get("metadatas") or []):
            existing_meta[doc_id] = meta or {}

    to_write = []
    for doc in docs:
        previous = existing_meta.get(doc["id"])
        if force or previous is None or previous.get("checksum") != doc["metadata"]["checksum"]:
            to_write.append(doc)

    if to_write:
        from chatbot.app.retrieval.retriever import default_embeddings

        texts = [d["text"] for d in to_write]
        embeddings = default_embeddings.embed_documents(texts)
        collection.upsert(
            ids=[d["id"] for d in to_write],
            embeddings=embeddings,
            documents=texts,
            metadatas=[d["metadata"] for d in to_write],
        )

    from chatbot.app.retrieval.retriever import invalidate_bm25_cache

    invalidate_bm25_cache(label)
    print(f"{label}: {len(docs)} source docs, {len(to_write)} written, {len(stale_ids)} removed")
    return len(to_write)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync ChromaDB collections from schema_files/")
    parser.add_argument("--force", action="store_true", help="Delete existing collection contents first")
    args = parser.parse_args()

    from chatbot.app.retrieval.retriever import (
        get_knowledge_vectorstore,
        get_schema_vectorstore,
        get_sql_vectorstore,
    )

    written = 0
    written += _sync(get_schema_vectorstore(), _schema_docs(), args.force, "schema_tables")
    written += _sync(get_sql_vectorstore(), _sql_pair_docs(), args.force, "question_sql_pairs")
    written += _sync(get_knowledge_vectorstore(), _rule_docs(), args.force, "business_knowledge")
    print(f"ChromaDB sync complete ({written} documents written).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
