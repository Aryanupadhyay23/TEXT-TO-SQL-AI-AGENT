import asyncio
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_community.retrievers.bm25 import BM25Retriever
from langchain_openai import OpenAIEmbeddings

from chatbot.app.models import AgentState
from chatbot.app.schema.introspector import introspector
from chatbot.app.retrieval.entity_matcher import entity_matcher
from chatbot.app.retrieval.graph_expander import graph_expander
from chatbot.app.retrieval.query_expander import query_expander
from chatbot.config.settings import settings

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
CHROMA_DIR = str(BACKEND_DIR / "data" / "chroma")
SCHEMA_TABLES_DIR = BACKEND_DIR / "schema_files" / "schema_of_table"


# 1. Native Nomic Embeddings via LangChain OpenAIEmbeddings (768 Dim)
def get_nomic_embeddings(api_key: str | None = None) -> OpenAIEmbeddings:
    key = api_key or os.environ.get("EMBEDDING_MODEL_KEY") or os.environ.get("OPENAI_API_KEY") or "nomic-unconfigured"
    chunk_size = int(os.getenv("EMBEDDING_CHUNK_SIZE", "10"))
    timeout = float(os.getenv("EMBEDDING_TIMEOUT", "15.0"))
    return OpenAIEmbeddings(
        model=os.getenv("EMBEDDING_MODEL_NAME", "nomic-embed-text-v1.5"),
        base_url=os.getenv("EMBEDDING_BASE_URL", "https://nomicapi.duckdns.org/v1"),
        api_key=key,
        chunk_size=chunk_size,
        request_timeout=timeout,
        check_embedding_ctx_length=False,
    )


nomic_embeddings = get_nomic_embeddings()
default_embeddings = nomic_embeddings

# 27 Deployed Relational Tables in ecommerce_db
VALID_ECOMMERCE_TABLES = {
    "users", "customer_profiles", "user_addresses",
    "products", "product_variants", "product_images", "categories", "brands",
    "inventory_items", "stock_movements", "warehouses", "shipments",
    "orders", "order_items", "order_status_history", "payments", "refunds",
    "coupons", "coupon_redemptions",
    "shopping_carts", "cart_items", "wishlists", "wishlist_items",
    "product_reviews", "review_helpful_votes", "return_requests", "return_items"
}

# Domain keyword to actual database table mapping
TABLE_SYNONYMS: Dict[str, List[str]] = {
    "customer": ["users", "customer_profiles"],
    "customers": ["users", "customer_profiles"],
    "user": ["users", "customer_profiles"],
    "users": ["users", "customer_profiles"],
    "profile": ["customer_profiles"],
    "address": ["user_addresses"],
    "addresses": ["user_addresses"],
    "product": ["products", "product_variants"],
    "products": ["products", "product_variants"],
    "variant": ["product_variants"],
    "variants": ["product_variants"],
    "category": ["categories", "products"],
    "categories": ["categories", "products"],
    "brand": ["brands", "products"],
    "brands": ["brands", "products"],
    "order": ["orders", "order_items"],
    "orders": ["orders", "order_items"],
    "revenue": ["orders", "order_items", "payments"],
    "sale": ["orders", "order_items"],
    "sales": ["orders", "order_items"],
    "payment": ["payments", "orders"],
    "payments": ["payments", "orders"],
    "coupon": ["coupons", "coupon_redemptions"],
    "coupons": ["coupons", "coupon_redemptions"],
    "discount": ["coupons", "orders"],
    "discounts": ["coupons", "orders"],
    "cart": ["shopping_carts", "cart_items"],
    "carts": ["shopping_carts", "cart_items"],
    "wishlist": ["wishlists", "wishlist_items"],
    "wishlists": ["wishlists", "wishlist_items"],
    "review": ["product_reviews"],
    "reviews": ["product_reviews"],
    "rating": ["product_reviews", "products"],
    "ratings": ["product_reviews", "products"],
    "shipment": ["shipments", "orders"],
    "shipments": ["shipments", "orders"],
    "carrier": ["shipments"],
    "inventory": ["inventory_items", "warehouses"],
    "stock": ["inventory_items", "stock_movements"],
    "warehouse": ["warehouses", "inventory_items"],
    "warehouses": ["warehouses", "inventory_items"],
    "return": ["return_requests", "return_items"],
    "returns": ["return_requests", "return_items"],
    "refund": ["refunds", "return_requests"],
    "refunds": ["refunds", "return_requests"],
}


# 2. Vectorstore Accessors
def get_schema_vectorstore() -> Chroma:
    return Chroma(
        collection_name="schema_tables",
        persist_directory=CHROMA_DIR,
        embedding_function=nomic_embeddings,
    )


def get_sql_vectorstore() -> Chroma:
    return Chroma(
        collection_name="question_sql_pairs",
        persist_directory=CHROMA_DIR,
        embedding_function=nomic_embeddings,
    )


def get_knowledge_vectorstore() -> Chroma:
    return Chroma(
        collection_name="business_knowledge",
        persist_directory=CHROMA_DIR,
        embedding_function=nomic_embeddings,
    )


schema_vectorstore = get_schema_vectorstore()
sql_vectorstore = get_sql_vectorstore()
knowledge_vectorstore = get_knowledge_vectorstore()



# 3. Hybrid Search with Reciprocal Rank Fusion (RRF: Semantic vs BM25 Keyword)
# In-memory BM25 index cache to avoid reading all Chroma documents & rebuilding BM25 tokenizers on every query
_bm25_cache: Dict[str, BM25Retriever] = {}


def invalidate_bm25_cache(collection_name: Optional[str] = None):
    """Invalidates the in-memory BM25 index cache when documents are added, updated, or deleted."""
    if collection_name:
        _bm25_cache.pop(collection_name, None)
    else:
        _bm25_cache.clear()


def _get_or_create_bm25(vectorstore: Chroma, k: int) -> Optional[BM25Retriever]:
    """Retrieves or lazily constructs and caches a BM25 retriever for a Chroma vectorstore."""
    col_name = getattr(vectorstore, "_collection_name", None) or getattr(vectorstore, "collection_name", "default")
    if col_name in _bm25_cache:
        retriever = _bm25_cache[col_name]
        retriever.k = k
        return retriever

    try:
        data = vectorstore.get()
        texts = data.get("documents", [])
        metas = data.get("metadatas", [])
        all_docs = [Document(page_content=t, metadata=m or {}) for t, m in zip(texts, metas) if t]
        
        # Fallback to local schema_files if vectorstore was uninitialized or empty
        if not all_docs:
            if col_name == "schema_tables":
                for p in SCHEMA_TABLES_DIR.glob("*.json"):
                    try:
                        with open(p, "r", encoding="utf-8") as f:
                            card = json.load(f)
                        t_name = card.get("table_name", p.stem)
                        desc = card.get("description", "")
                        cols = [c.get("name") for c in card.get("columns", [])]
                        all_docs.append(Document(
                            page_content=f"Table: {t_name}\nDescription: {desc}\nColumns: {', '.join(cols)}",
                            metadata={"table_name": t_name}
                        ))
                    except Exception:
                        pass
            elif col_name == "question_sql_pairs":
                pairs_dir = BACKEND_DIR / "schema_files" / "sql_pairs"
                for jf in pairs_dir.glob("*.json"):
                    try:
                        with open(jf, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        for pair in data.get("sql_pairs", []):
                            all_docs.append(Document(
                                page_content=pair.get("question", ""),
                                metadata={"sql": pair.get("sql", ""), "tables": pair.get("tables", "")}
                            ))
                    except Exception:
                        pass
            elif col_name == "business_knowledge":
                rf = BACKEND_DIR / "schema_files" / "business_text" / "ecommerce_business_rules.json"
                if rf.exists():
                    try:
                        with open(rf, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        for r in data.get("rules", []):
                            all_docs.append(Document(
                                page_content=r.get("rule", ""),
                                metadata={"rule": r.get("rule", ""), "topic": r.get("topic", "")}
                            ))
                    except Exception:
                        pass

        if not all_docs:
            return None
        retriever = BM25Retriever.from_documents(all_docs, k=k)
        _bm25_cache[col_name] = retriever
        return retriever
    except Exception:
        return None


def hybrid_search(
    vectorstore: Chroma,
    query: str,
    k: int = 5,
    c: Optional[int] = None,
    semantic_weight: Optional[float] = None,
    bm25_weight: Optional[float] = None,
) -> List[Document]:
    """
    Combines Chroma semantic search with BM25 keyword search using Reciprocal Rank Fusion.
    Weights and constant 'c' are dynamically configured via settings / .env.
    Uses cached BM25 retriever to eliminate document re-fetching overhead.
    """
    if c is None:
        c = settings.RETRIEVAL_RRF_C
    if semantic_weight is None:
        semantic_weight = settings.RETRIEVAL_SEMANTIC_WEIGHT
    if bm25_weight is None:
        bm25_weight = settings.RETRIEVAL_BM25_WEIGHT

    if not query or not query.strip():
        return []

    # Semantic vector search
    try:
        semantic_docs = vectorstore.similarity_search(query, k=k)
    except Exception:
        semantic_docs = []

    # Cached BM25 keyword search
    bm25 = _get_or_create_bm25(vectorstore, k=k)
    if not bm25:
        return semantic_docs[:k]

    try:
        keyword_docs = bm25.invoke(query)
    except Exception:
        return semantic_docs[:k]

    # Score fusion: Semantic + BM25 RRF
    rrf_scores: Dict[str, Dict[str, Any]] = {}
    for rank, doc in enumerate(semantic_docs):
        key = doc.page_content
        if key not in rrf_scores:
            rrf_scores[key] = {"doc": doc, "score": 0.0}
        rrf_scores[key]["score"] += semantic_weight / (c + rank + 1)

    for rank, doc in enumerate(keyword_docs):
        key = doc.page_content
        if key not in rrf_scores:
            rrf_scores[key] = {"doc": doc, "score": 0.0}
        rrf_scores[key]["score"] += bm25_weight / (c + rank + 1)

    sorted_items = sorted(rrf_scores.values(), key=lambda x: x["score"], reverse=True)
    return [item["doc"] for item in sorted_items[:k]]


async def async_hybrid_search(
    vectorstore: Chroma,
    query: str,
    k: int = 5,
    c: Optional[int] = None,
    semantic_weight: Optional[float] = None,
    bm25_weight: Optional[float] = None,
) -> List[Document]:
    """Asynchronously executes hybrid_search in a thread pool to prevent blocking the asyncio event loop."""
    return await asyncio.to_thread(
        hybrid_search,
        vectorstore=vectorstore,
        query=query,
        k=k,
        c=c,
        semantic_weight=semantic_weight,
        bm25_weight=bm25_weight,
    )



# 4. Ingestion Helpers
def add_question_sql_example(question: str, sql: str, tables: Optional[List[str]] = None, created_at: Optional[str] = None):
    doc = Document(
        page_content=question.strip(),
        metadata={
            "sql": sql.strip(),
            "tables": ",".join(tables) if tables else "",
            "created_at": created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    )
    sql_vectorstore.add_documents([doc])
    invalidate_bm25_cache("question_sql_pairs")


def add_business_knowledge_rule(rule: str, topic: str = "", created_at: Optional[str] = None):
    doc = Document(
        page_content=topic.strip() if topic else rule.strip(),
        metadata={
            "rule": rule.strip(),
            "topic": topic.strip(),
            "created_at": created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    )
    knowledge_vectorstore.add_documents([doc])
    invalidate_bm25_cache("business_knowledge")


def add_schema_card(table_name: str, card_content: str, metadata: Optional[Dict[str, Any]] = None):
    meta = metadata or {}
    meta["table_name"] = table_name
    doc = Document(page_content=card_content, metadata=meta)
    schema_vectorstore.add_documents([doc])
    invalidate_bm25_cache("schema_tables")


def _load_schema_card(table_name: str) -> Optional[Dict[str, Any]]:
    card_path = SCHEMA_TABLES_DIR / f"{table_name}.json"
    if card_path.exists():
        try:
            with open(card_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


# 5. LangGraph Retriever Node with Multi-Query Pooling & Top-5 Deduplication
async def retriever_node(state: AgentState) -> Dict[str, Any]:
    """
    Executes Multi-Query Retrieval across all stores with strict Top-5 deduplication:
    1. Multi-Query Expansion: original query + 3 generated variations (4 search vectors).
    2. Literal Grounding: RapidFuzz scan across all query variations, deduplicated by condition.
    3. Hybrid Table Retrieval: pools candidate tables across all queries -> expands to Top 5 unique tables.
    4. Relational Join Graph: NetworkX closure providing foreign key conditions for selected tables.
    5. Few-Shot SQL Retrieval: pools across all queries -> keeps Top 5 unique SQL pairs.
    6. Business Knowledge Retrieval: pools across all queries -> keeps Top 5 unique business rules.
    """
    raw_query = state.processed_query or state.user_input

    # Step 1: Ensure search_queries pool is available (original + 3 variations)
    if state.search_queries:
        search_queries = state.search_queries
    else:
        variations = await query_expander.expand(raw_query)
        seen_q = set()
        search_queries = []
        for q in [raw_query] + variations:
            q_clean = q.strip()
            if q_clean and q_clean.lower() not in seen_q:
                seen_q.add(q_clean.lower())
                search_queries.append(q_clean)

    # Step 2: Multi-Query Literal Entity Grounding (RapidFuzz across all queries)
    value_hints = []
    seen_conditions = set()
    for q in search_queries:
        for hint in entity_matcher.match_entities(q):
            cond = hint.get("sql_condition")
            if cond and cond not in seen_conditions:
                seen_conditions.add(cond)
                value_hints.append(hint)

    hint_tables = [h["table"] for h in value_hints if h.get("table")]

    # Step 3: Multi-Query Schema Table Retrieval (Pooled & Deduplicated)
    candidate_tables = []
    seen_tables = set()

    # Prepend hint tables first (filtering through permissions)
    for ht in hint_tables:
        if ht not in seen_tables and introspector.is_allowed(ht):
            seen_tables.add(ht)
            candidate_tables.append(ht)

    # Configurable limits from settings / .env (defaults to 5)
    top_k_tables = settings.RETRIEVAL_TOP_K_TABLES
    top_k_sql = settings.RETRIEVAL_TOP_K_SQL_PAIRS
    top_k_rules = settings.RETRIEVAL_TOP_K_RULES

    # Step 3, 4, 5: Run Multi-Query searches across all stores concurrently via asyncio.gather!
    table_tasks = [async_hybrid_search(schema_vectorstore, q, k=top_k_tables) for q in search_queries]
    sql_tasks = [async_hybrid_search(sql_vectorstore, q, k=top_k_sql) for q in search_queries]
    rule_tasks = [async_hybrid_search(knowledge_vectorstore, q, k=top_k_rules) for q in search_queries]

    all_table_results, all_sql_results, all_rule_results = await asyncio.gather(
        asyncio.gather(*table_tasks),
        asyncio.gather(*sql_tasks),
        asyncio.gather(*rule_tasks),
    )

    # Process retrieved tables (strictly filter for valid tables in ecommerce_db)
    for table_docs in all_table_results:
        for d in table_docs:
            tbl = d.metadata.get("table_name")
            if tbl and tbl in VALID_ECOMMERCE_TABLES and tbl not in seen_tables and introspector.is_allowed(tbl):
                seen_tables.add(tbl)
                candidate_tables.append(tbl)

    # Keyword / Synonym Matching Fallback (ensures exact table resolution even if vector search is sparse)
    if not candidate_tables:
        combined_text = " ".join(search_queries).lower()
        for kw, mapped_tbls in TABLE_SYNONYMS.items():
            # Match whole word
            if f" {kw} " in f" {combined_text} ":
                for mt in mapped_tbls:
                    if mt not in seen_tables and introspector.is_allowed(mt):
                        seen_tables.add(mt)
                        candidate_tables.append(mt)

    # Core eCommerce Fallback: default to orders, products, users (guarantees valid tables)
    if not candidate_tables:
        default_candidates = ["orders", "products", "users"]
        candidate_tables = [t for t in default_candidates if introspector.is_allowed(t)]

    # Expand candidate tables via NetworkX relational bridge graph (Capped at top_k_tables unique tables)
    connected_tables = [
        t for t in graph_expander.expand_tables(candidate_tables, max_tables=top_k_tables)
        if introspector.is_allowed(t) and t in VALID_ECOMMERCE_TABLES
    ]
    join_paths = graph_expander.get_join_paths(connected_tables)

    # Build Pruned Schema Context (strictly filtered for allowed tables and columns)
    pruned_tables = {}
    for tbl in connected_tables:
        if not introspector.is_allowed(tbl):
            continue

        card = _load_schema_card(tbl)
        if card:
            raw_columns = card.get("columns", [])
            filtered_cols = [c for c in raw_columns if introspector.is_allowed(tbl, c.get("name"))]
            has_blocked_col = len(filtered_cols) < len(raw_columns)

            pruned_tables[tbl] = {
                "columns": filtered_cols,
                "foreign_keys": card.get("foreign_keys", []),
                # If table had blocked columns omitted, drop raw DDL to avoid leaking blocked column definitions
                "ddl": "" if has_blocked_col else card.get("ddl_statement", ""),
                "domain": card.get("domain", ""),
                "description": card.get("description", ""),
            }
        else:
            full_schema = await introspector.aget_schema()
            tbl_info = full_schema.get("tables", {}).get(tbl, {})
            raw_columns = tbl_info.get("columns", [])
            filtered_cols = [c for c in raw_columns if introspector.is_allowed(tbl, c.get("name"))]
            pruned_tables[tbl] = {
                "columns": filtered_cols,
                "foreign_keys": tbl_info.get("foreign_keys", []),
            }

    schema_context = {
        "tables": pruned_tables,
        "relationships": join_paths,
        "connected_tables": connected_tables,
    }

    # Step 4: Multi-Query Few-Shot SQL Retrieval (RRF Multi-Query Pooling)
    example_scores = {}
    example_map = {}
    for sql_docs in all_sql_results:
        for rank, d in enumerate(sql_docs):
            sql_str = d.metadata.get("sql", "").strip()
            q_text = d.page_content.strip()
            dedup_key = f"{q_text}::{sql_str}"
            if not sql_str:
                continue
            # Multi-query RRF score pooling
            score = 1.0 / (60.0 + rank)
            example_scores[dedup_key] = example_scores.get(dedup_key, 0.0) + score
            if dedup_key not in example_map:
                example_map[dedup_key] = {
                    "question": q_text,
                    "sql": sql_str,
                    "tables": [t for t in d.metadata.get("tables", "").split(",") if t],
                    "created_at": d.metadata.get("created_at"),
                }

    sorted_example_keys = sorted(example_scores.keys(), key=lambda k: example_scores[k], reverse=True)
    examples = [example_map[k] for k in sorted_example_keys[:top_k_sql]]

    # Step 5: Multi-Query Business Rules Retrieval (RRF Multi-Query Pooling)
    rule_scores = {}
    rule_map = {}
    for knowledge_docs in all_rule_results:
        for rank, d in enumerate(knowledge_docs):
            title = d.page_content.strip()
            rule_body = (d.metadata.get("rule") or d.metadata.get("content") or "").strip()
            b_rule = d.metadata.get("business_rule")
            if b_rule and b_rule not in rule_body:
                rule_body = f"{rule_body} [Rule: {b_rule}]".strip()
            rule_text = f"[{title}] {rule_body}" if rule_body else title
            if not rule_text:
                continue
            score = 1.0 / (60.0 + rank)
            rule_scores[rule_text] = rule_scores.get(rule_text, 0.0) + score
            rule_map[rule_text] = rule_text

    sorted_rule_keys = sorted(rule_scores.keys(), key=lambda k: rule_scores[k], reverse=True)
    rules = [rule_map[k] for k in sorted_rule_keys[:top_k_rules]]

    return {
        "retrieved_examples": examples,
        "retrieved_rules": rules,
        "schema_context": schema_context,
        "retrieved_tables": connected_tables,
        "value_hints": value_hints,
        "search_queries": search_queries,
    }




