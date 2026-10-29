"""Loaders for the JSON knowledge files used by RAG retrieval and seeding."""

import json
from pathlib import Path
from typing import Any, Dict, List


def normalize_business_rules(raw_rules: Any) -> List[Dict[str, str]]:
    """Normalizes rule entries from either supported JSON schema into topic/rule pairs."""
    rules: List[Dict[str, str]] = []
    if not isinstance(raw_rules, list):
        return rules
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


def load_business_rules(path: Path) -> List[Dict[str, str]]:
    """Loads and normalizes the business rules JSON file, tolerating both key layouts."""
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    return normalize_business_rules(data.get("business_rules") or data.get("rules"))
