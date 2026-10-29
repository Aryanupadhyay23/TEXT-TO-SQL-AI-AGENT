"""
Schema and Knowledge Files Service
Loads and updates table definitions, foreign keys, golden SQL pairs, and business rules.
"""

import json
import glob
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from frontend.config.constants import SCHEMA_FILES_DIR


def load_all_tables_metadata() -> Dict[str, Any]:
    """Loads all 27 table schema JSON files from schema_files/schema_of_table/."""
    tables_dir = SCHEMA_FILES_DIR / "schema_of_table"
    schema_map = {}
    if tables_dir.exists():
        for jf in glob.glob(str(tables_dir / "*.json")):
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    t_name = data.get("table_name")
                    if t_name:
                        schema_map[t_name] = data
            except Exception:
                pass
    return schema_map


def load_all_sql_pairs() -> List[Dict[str, Any]]:
    """Loads all golden SQL training pairs from schema_files/sql_pairs/*.json."""
    pairs = []
    pairs_dir = SCHEMA_FILES_DIR / "sql_pairs"
    if pairs_dir.exists():
        for jf in glob.glob(str(pairs_dir / "*.json")):
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    domain = data.get("domain", Path(jf).stem.replace("_", " ").title())
                    for p in data.get("sql_pairs", []):
                        pairs.append({
                            "question": p.get("question", ""),
                            "sql": p.get("sql", ""),
                            "tables": p.get("tables", ""),
                            "domain": domain,
                            "difficulty": p.get("difficulty", "medium"),
                            "source_file": Path(jf).name,
                        })
            except Exception:
                pass
    return pairs


def load_all_business_rules() -> List[Dict[str, str]]:
    """Loads corporate business rules, normalizing both supported JSON layouts."""
    rules_file = SCHEMA_FILES_DIR / "business_text" / "ecommerce_business_rules.json"
    if not rules_file.exists():
        return []
    try:
        with open(rules_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []

    raw_rules = data.get("business_rules") or data.get("rules") or []
    rules = []
    for entry in raw_rules:
        if not isinstance(entry, dict):
            continue
        content = entry.get("content") or entry.get("rule") or ""
        if not content:
            continue
        tables = entry.get("associated_tables") or entry.get("tables") or ""
        if isinstance(tables, list):
            tables = ", ".join(str(t) for t in tables)
        rules.append({
            "topic": entry.get("title") or entry.get("topic") or "Business Rule",
            "rule": content,
            "domain": entry.get("domain", ""),
            "tables": tables,
        })
    return rules


def _index_sql_pair(question: str, sql: str, tables: str, difficulty: str) -> Tuple[bool, Optional[str]]:
    """Adds a golden pair to the Chroma SQL-pair collection and drops the stale BM25 cache."""
    try:
        import uuid

        from chatbot.app.retrieval.retriever import (
            default_embeddings,
            invalidate_bm25_cache,
            sql_vectorstore,
        )

        doc_text = question.strip()
        embeddings = default_embeddings.embed_documents([doc_text])
        sql_vectorstore._collection.add(
            ids=[uuid.uuid4().hex],
            documents=[doc_text],
            embeddings=embeddings,
            metadatas=[{
                "sql": sql.strip(),
                "tables": tables.strip(),
                "difficulty": difficulty,
                "source": "streamlit_ui",
            }],
        )
        invalidate_bm25_cache("question_sql_pairs")
        return True, None
    except Exception as e:
        return False, str(e)


def add_golden_sql_pair(
    domain_file: str, question: str, sql: str, tables: str, difficulty: str = "medium"
) -> Tuple[bool, str]:
    """Appends a golden pair to its domain file and indexes it for hybrid RAG retrieval."""
    target_file = SCHEMA_FILES_DIR / "sql_pairs" / domain_file
    if not target_file.exists():
        return False, f"Domain file '{domain_file}' not found."

    with open(target_file, "r+", encoding="utf-8") as f:
        data = json.load(f)
        data.setdefault("sql_pairs", []).append({
            "question": question.strip(),
            "sql": sql.strip(),
            "tables": tables.strip(),
            "difficulty": difficulty,
        })
        f.seek(0)
        json.dump(data, f, indent=2)
        f.truncate()

    indexed, index_error = _index_sql_pair(question, sql, tables, difficulty)
    if indexed:
        return True, "Pair saved and indexed for hybrid RAG retrieval."
    return True, f"Pair saved to disk, but the vector index was not updated: {index_error}"
