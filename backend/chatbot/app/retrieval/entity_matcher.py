import re
import json
from pathlib import Path
from typing import List, Dict, Any
try:
    from rapidfuzz import fuzz, process
except ImportError:
    import difflib
    class _FuzzFallback:
        @staticmethod
        def ratio(s1: str, s2: str) -> float:
            return difflib.SequenceMatcher(None, s1, s2).ratio() * 100
    class _ProcessFallback:
        @staticmethod
        def extractOne(query: str, choices: list, scorer=None, score_cutoff: float = 0):
            best = None
            best_score = score_cutoff
            for c in choices:
                score = difflib.SequenceMatcher(None, query, c).ratio() * 100
                if score >= best_score:
                    best = (c, score)
                    best_score = score
            return best
    fuzz = _FuzzFallback()
    process = _ProcessFallback()

CATALOG_DIR = Path(__file__).resolve().parent.parent.parent / "schema_files" / "literal_entity_matcher"


class EntityMatcher:
    """Matches words or phrases in a user query against known DB enums, statuses, and categorical literals."""

    def __init__(self, catalog_dir: Path = CATALOG_DIR):
        self.catalog_dir = catalog_dir
        self.entities = self._load_catalog()

    def _load_catalog(self) -> List[Dict[str, Any]]:
        """Loads entity definitions from backend/schema_files/literal_entity_matcher/."""
        entities = []
        if not self.catalog_dir.exists():
            return entities

        for json_file in sorted(self.catalog_dir.glob("*.json")):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    items = data.get("entities", []) if isinstance(data, dict) else data
                    if isinstance(items, list):
                        entities.extend(items)
            except Exception:
                continue

        return entities

    def match_entities(self, query: str, threshold: int = 90) -> List[Dict[str, Any]]:
        """
        Scans a query against aliases of known database categorical values.
        Returns matched entity metadata and SQL condition hints.
        """
        if not self.entities or not query:
            return []

        query_lower = query.lower()
        matched = []
        seen_conditions = set()

        # Generate single words and 2-3 word n-gram phrases
        words = query_lower.split()
        phrases = list(words)
        for i in range(len(words) - 1):
            phrases.append(f"{words[i]} {words[i+1]}")
        for i in range(len(words) - 2):
            phrases.append(f"{words[i]} {words[i+1]} {words[i+2]}")

        for entity in self.entities:
            aliases = [a.lower() for a in entity.get("aliases", [])]
            sql_cond = entity.get("sql_condition", "")
            if not sql_cond:
                continue

            # 1. Exact match with word boundary
            exact_hit = any(bool(re.search(rf"\b{re.escape(a)}\b", query_lower)) for a in aliases)
            if exact_hit:
                if sql_cond not in seen_conditions:
                    seen_conditions.add(sql_cond)
                    matched.append({
                        "category": entity.get("category"),
                        "matched_term": entity.get("literal_value"),
                        "table": entity.get("table"),
                        "column": entity.get("column"),
                        "sql_condition": sql_cond,
                        "score": 100,
                    })
                continue

            # 2. Fuzzy match across candidate phrases (skip very short aliases, which over-match)
            fuzzy_aliases = [a for a in aliases if len(a) >= 4]
            for phrase in phrases:
                if len(phrase) < 4:
                    continue
                best_match = process.extractOne(phrase, fuzzy_aliases, scorer=fuzz.ratio, score_cutoff=threshold)
                if best_match:
                    if sql_cond not in seen_conditions:
                        seen_conditions.add(sql_cond)
                        matched.append({
                            "category": entity.get("category"),
                            "matched_term": entity.get("literal_value"),
                            "table": entity.get("table"),
                            "column": entity.get("column"),
                            "sql_condition": sql_cond,
                            "score": round(best_match[1], 1),
                        })
                    break

        return matched

    def format_hints_for_prompt(self, matches: List[Dict[str, Any]]) -> str:
        """Formats matched entities into clear prompt hints for SQL generation."""
        if not matches:
            return ""
        lines = ["Database Value Mappings & Literal Hints:"]
        for m in matches:
            lines.append(f"- Matched '{m['matched_term']}': use `{m['sql_condition']}` on table `{m['table']}`")
        return "\n".join(lines)


# Singleton instance
entity_matcher = EntityMatcher()
