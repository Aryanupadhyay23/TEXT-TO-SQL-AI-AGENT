"""
Schema and Knowledge Files Service
Loads and updates table definitions, foreign keys, golden SQL pairs, and business rules.
"""

import json
import glob
from pathlib import Path
from typing import Dict, Any, List, Optional
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
    """Loads all corporate business rules and KPI formulas."""
    rules_file = SCHEMA_FILES_DIR / "business_text" / "ecommerce_business_rules.json"
    if rules_file.exists():
        try:
            with open(rules_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("rules", [])
        except Exception:
            return []
    return []


def add_golden_sql_pair(domain_file: str, question: str, sql: str, tables: str, difficulty: str = "medium") -> bool:
    """Appends a new golden training pair to the specified domain file."""
    target_file = SCHEMA_FILES_DIR / "sql_pairs" / domain_file
    if not target_file.exists():
        return False
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
    return True
