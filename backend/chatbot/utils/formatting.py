"""Formatting utilities for markdown tables, schema representation, and rules."""

from typing import List, Dict, Any, Optional


def format_markdown_table(columns: List[str], rows: List[Dict[str, Any]], max_rows: int = 10) -> str:
    """Formats SQL result rows into a clean, scannable markdown table."""
    if not columns or not rows:
        return "Query executed successfully. Result: 0 rows returned."

    display_rows = rows[:max_rows]
    headers = " | ".join(str(c) for c in columns)
    separator = " | ".join("---" for _ in columns)
    lines = [f"| {headers} |", f"| {separator} |"]

    for row in display_rows:
        row_vals = []
        for c in columns:
            val = row.get(c)
            val_str = str(val).replace("\n", " ").replace("|", "\\|") if val is not None else "NULL"
            if len(val_str) > 40:
                val_str = val_str[:37] + "..."
            row_vals.append(val_str)
        lines.append(f"| {' | '.join(row_vals)} |")

    total = len(rows)
    if total > max_rows:
        lines.append(f"\n*(Showing first {max_rows} of {total} rows)*")
    else:
        lines.append(f"\n*(Total rows returned: {total})*")

    return "\n".join(lines)


def format_examples(examples: List[Dict[str, Any]]) -> str:
    """Formats few-shot question-SQL pairs for LLM prompt context."""
    if not examples:
        return "No specific few-shot examples available."
    return "\n\n".join(
        f"Example {i}:\n  Question: {ex.get('question', '')}\n  SQL: {ex.get('sql', '')}"
        for i, ex in enumerate(examples, 1)
    )


def format_rules(rules: List[str]) -> str:
    """Formats business knowledge rules into bullet points."""
    if not rules:
        return "No specific business rules retrieved."
    return "\n".join(f"- {r}" for r in rules)


def format_value_hints(hints: List[Dict[str, Any]]) -> str:
    """Formats extracted database literal values and conditions."""
    if not hints:
        return ""
    lines = []
    seen = set()
    for h in hints:
        cond = h.get("sql_condition")
        if cond and cond not in seen:
            seen.add(cond)
            tbl = h.get("table", "")
            term = h.get("matched_term", "")
            lines.append(f"- Matched value for '{term}': condition `{cond}` (table: `{tbl}`)")
    return "\n".join(lines)


def format_schema(schema: Dict[str, Any]) -> str:
    """Formats database schema (tables, DDL, columns, and foreign key join paths) into clear text."""
    if not schema or not schema.get("tables"):
        return ""

    lines = []
    tables = schema.get("tables", {})
    for tbl_name, tbl_info in tables.items():
        ddl = tbl_info.get("ddl")
        if ddl:
            lines.append(f"--- Table: {tbl_name} ---\n{ddl.strip()}\n")
        else:
            cols = tbl_info.get("columns", [])
            col_desc = ", ".join(f"{c['name']} ({c.get('type', c.get('data_type', 'TEXT'))})" for c in cols if isinstance(c, dict))
            lines.append(f"Table `{tbl_name}`: columns [{col_desc}]")

    relationships = schema.get("relationships", [])
    if relationships:
        lines.append("\nAvailable Relational JOIN Paths:")
        for r in relationships:
            if isinstance(r, str):
                lines.append(f"  - {r}")
            elif isinstance(r, dict):
                cond = r.get("join_condition")
                if cond:
                    lines.append(f"  - {cond}")
                else:
                    lines.append(f"  - `{r.get('from_table')}`.`{r.get('from_column')}` -> `{r.get('to_table')}`.`{r.get('to_column')}`")

    return "\n".join(lines)
