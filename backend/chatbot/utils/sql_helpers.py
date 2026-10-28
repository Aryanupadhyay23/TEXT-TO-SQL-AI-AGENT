"""SQL string cleaning, normalization, and extraction utilities."""

import re
from typing import Optional


def clean_sql(query: str) -> str:
    """Removes any markdown fences, backticks, or extraneous formatting and normalizes Unicode operators in raw SQL."""
    if not query:
        return ""
    cleaned = query.strip()
    cleaned = re.sub(r"^```(?:sql)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    # Normalize Unicode comparison and mathematical operators
    cleaned = cleaned.replace("≠", "!=")
    cleaned = cleaned.replace("≤", "<=")
    cleaned = cleaned.replace("≥", ">=")
    cleaned = cleaned.replace("×", "*")
    cleaned = cleaned.replace("÷", "/")

    # Normalize typographical quotes and backticks
    cleaned = cleaned.replace("‘", "'").replace("’", "'")
    cleaned = cleaned.replace("“", '"').replace("”", '"')

    # Normalize non-breaking spaces and fancy dashes
    cleaned = cleaned.replace("\u00a0", " ")
    cleaned = cleaned.replace("–", "-").replace("—", "-")

    return cleaned.strip()


def extract_sql_from_text(text: str) -> Optional[str]:
    """Robustly extracts an executable SQL query from model outputs, raw text, or LangChain parsing errors."""
    if not text:
        return None

    # 1. Backtick code fences: ```sql ... ``` or ``` ... ```
    fence_matches = re.findall(r"```(?:sql)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    for block in fence_matches:
        trimmed = block.strip()
        if re.search(r"\b(?:SELECT|SHOW|DESCRIBE|EXPLAIN)\b", trimmed, re.IGNORECASE):
            return clean_sql(trimmed)

    # 2. JSON escaped: "sql_query": "SELECT ..."
    m = re.search(r'["\']sql_query["\']\s*:\s*["\']((?:SELECT|SHOW|DESCRIBE|EXPLAIN)[\s\S]+?)["\']', text, re.IGNORECASE)
    if m:
        return clean_sql(m.group(1).replace(r"\"", '"').replace(r"\n", "\n"))

    # 3. Raw SELECT/SHOW statement up to semicolon, newline troubleshooting info, or end of text
    m = re.search(r"((?:SELECT|SHOW|DESCRIBE|EXPLAIN)\s+[\s\S]+?)(?:;|\n\s*For troubleshooting|$)", text, re.IGNORECASE)
    if m:
        return clean_sql(m.group(1))

    return None
