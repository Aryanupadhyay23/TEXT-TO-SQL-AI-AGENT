"""Knowledge and Few-Shot SQL Retrieval Tool (search_knowledge_and_examples)."""

import asyncio
import glob
import json
from pathlib import Path
from typing import List, Dict, Optional

from langchain_core.tools import tool

from chatbot.app.retrieval.knowledge_files import load_business_rules
from chatbot.app.retrieval.retriever import (
    async_hybrid_search,
    knowledge_vectorstore,
    sql_vectorstore,
)

SCHEMA_FILES_DIR = Path(__file__).resolve().parent.parent / "schema_files"

# Lazy-loaded cache for JSON-based fallback retrieval
_cached_rules: Optional[List[Dict[str, str]]] = None
_cached_pairs: Optional[List[Dict[str, str]]] = None


def _load_local_knowledge():
    """Loads business rules and golden SQL pairs from local schema_files/ as fallback."""
    global _cached_rules, _cached_pairs
    if _cached_rules is None:
        rule_file = SCHEMA_FILES_DIR / "business_text" / "ecommerce_business_rules.json"
        _cached_rules = load_business_rules(rule_file)

    if _cached_pairs is None:
        _cached_pairs = []
        for jf in glob.glob(str(SCHEMA_FILES_DIR / "sql_pairs" / "*.json")):
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for pair in data.get("sql_pairs", []):
                    _cached_pairs.append({
                        "question": pair.get("question", ""),
                        "sql": pair.get("sql", ""),
                        "tables": pair.get("tables", ""),
                        "domain": data.get("domain", ""),
                    })
            except Exception:
                pass


def _match_locally(clean_q: str) -> List[str]:
    """Keyword-overlap search across the local JSON knowledge files."""
    _load_local_knowledge()
    sections: List[str] = []
    q_tokens = set(clean_q.lower().split())

    # Match local rules
    matched_rules = []
    for r in (_cached_rules or []):
        text = f"{r.get('topic', '')} {r.get('rule', '')}".lower()
        overlap = sum(1 for t in q_tokens if t in text)
        if overlap > 0:
            matched_rules.append((overlap, r))
    matched_rules.sort(key=lambda x: x[0], reverse=True)
    if matched_rules:
        rule_lines = [f"- [{r.get('topic')}]: {r.get('rule')}" for _, r in matched_rules[:3]]
        sections.append("### Business Rules:\n" + "\n".join(rule_lines))

    # Match local SQL pairs
    matched_pairs = []
    for p in (_cached_pairs or []):
        text = f"{p.get('question', '')} {p.get('tables', '')} {p.get('domain', '')}".lower()
        overlap = sum(1 for t in q_tokens if t in text)
        if overlap > 0:
            matched_pairs.append((overlap, p))
    matched_pairs.sort(key=lambda x: x[0], reverse=True)
    if matched_pairs:
        pair_lines = [f"Question: {p.get('question')}\nSQL: {p.get('sql')}" for _, p in matched_pairs[:2]]
        sections.append("### Reference SQL Pairs:\n" + "\n\n".join(pair_lines))

    return sections


@tool
async def search_knowledge_and_examples(query: str) -> str:
    """Searches the knowledge base for business rules, KPI/metric definitions,
    and reference Question-SQL pairs for complex query patterns.
    Input: Search terms or question topic (e.g. 'how is revenue calculated', 'returns and refunds', 'customer LTV').
    Output: Relevant business rules and matching golden SQL examples.
    """
    clean_q = query.strip()
    if not clean_q:
        return "Please provide a search topic or question."

    sections = []

    # 1. Try vectorstore hybrid retrieval first (runs off the event loop)
    try:
        rules_docs, sql_docs = await asyncio.gather(
            async_hybrid_search(knowledge_vectorstore, clean_q, k=3),
            async_hybrid_search(sql_vectorstore, clean_q, k=2),
        )
        if rules_docs:
            rule_texts = [
                f"- [{d.metadata.get('topic') or d.page_content}] {d.metadata.get('rule') or d.page_content}"
                for d in rules_docs
            ]
            sections.append("### Business Rules:\n" + "\n".join(rule_texts))

        if sql_docs:
            sql_texts = [
                f"Question: {d.page_content}\nSQL: {d.metadata.get('sql', '')}"
                for d in sql_docs
            ]
            sections.append("### Reference SQL Pairs:\n" + "\n\n".join(sql_texts))
    except Exception:
        pass

    # 2. Local Fallback search across JSON files if vectorstore yielded few/no results
    if not sections:
        sections = await asyncio.to_thread(_match_locally, clean_q)

    if not sections:
        return f"No specific business rules or SQL examples found matching '{clean_q}'."

    return "\n\n".join(sections)
