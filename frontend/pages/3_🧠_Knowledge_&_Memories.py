"""
Knowledge & Memories Manager Page
Browse, search, and manage ChromaDB few-shot Question-SQL pairs across 8 domain files,
inspect corporate business rules, and add new training pairs.
"""

import streamlit as st
import json
from pathlib import Path
import sys

# Ensure root, frontend, and backend directories are in sys.path
PAGES_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = PAGES_DIR.parent
ROOT_DIR = FRONTEND_DIR.parent
BACKEND_DIR = ROOT_DIR / "backend"

for p in [ROOT_DIR, FRONTEND_DIR, BACKEND_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from frontend.components import render_header
from frontend.services import load_all_sql_pairs, load_all_business_rules, add_golden_sql_pair
from frontend.config import SCHEMA_FILES_DIR as SCHEMA_DIR

st.set_page_config(
    page_title="Knowledge & Memories | ChromaDB",
    page_icon="🧠",
    layout="wide",
)

render_header(
    title="Knowledge Base & Memories Manager",
    subtitle="Manage ChromaDB few-shot SQL pairs, corporate KPI definitions, and business logic for RAG retrieval",
)

sql_pairs = load_all_sql_pairs()
rules = load_all_business_rules()

# Header Metrics
mcol1, mcol2, mcol3 = st.columns(3)
with mcol1:
    st.metric("Total Golden SQL Pairs", len(sql_pairs))
with mcol2:
    st.metric("Corporate Business Rules", len(rules))
with mcol3:
    domains_set = set(p["domain"] for p in sql_pairs)
    st.metric("Specialized Domains", len(domains_set))

st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

tab_pairs, tab_rules, tab_add = st.tabs([
    f"💡 Few-Shot SQL Pairs ({len(sql_pairs)})",
    f"📋 Business Rules ({len(rules)})",
    "➕ Add New Pair / Rule",
])

with tab_pairs:
    fcol1, fcol2 = st.columns([2, 1])
    with fcol1:
        search_query = st.text_input("🔍 Search Question, SQL, or Tables...", placeholder="e.g. revenue, gold membership, return disposition...")
    with fcol2:
        all_domains = ["All Domains"] + sorted(list(domains_set))
        selected_domain = st.selectbox("Filter by Domain", all_domains)

    filtered_pairs = sql_pairs
    if selected_domain != "All Domains":
        filtered_pairs = [p for p in filtered_pairs if p["domain"] == selected_domain]

    if search_query.strip():
        q_lower = search_query.lower()
        filtered_pairs = [
            p for p in filtered_pairs
            if q_lower in p["question"].lower()
            or q_lower in p["sql"].lower()
            or q_lower in p["tables"].lower()
        ]

    st.markdown(f"**Showing {len(filtered_pairs)} matching golden SQL pairs:**")

    for i, pair in enumerate(filtered_pairs):
        with st.expander(f"**{i+1}. {pair['question']}** ({pair['domain']})", expanded=(i < 3 and not search_query)):
            st.markdown(f"**Target Tables:** `{pair['tables']}` | **Difficulty:** `{pair['difficulty'].upper()}`")
            st.code(pair["sql"], language="sql")

with tab_rules:
    st.markdown("##### Corporate E-Commerce KPI & Metric Definitions")
    rule_search = st.text_input("🔍 Search business rules...", placeholder="e.g. revenue, completed orders, inventory threshold...")
    
    filtered_rules = rules
    if rule_search.strip():
        r_lower = rule_search.lower()
        filtered_rules = [
            r for r in filtered_rules
            if r_lower in r.get("topic", "").lower() or r_lower in r.get("rule", "").lower()
        ]

    for r in filtered_rules:
        st.markdown(
            f"""
            <div class="glass-card" style="margin-bottom: 12px; border-left: 4px solid #38bdf8;">
                <div style="font-weight: 700; color: #38bdf8; font-size: 14px; margin-bottom: 4px;">
                    📌 {r.get('topic', 'Business Rule')}
                </div>
                <div style="color: #e4e4e7; font-size: 13px; line-height: 1.5;">
                    {r.get('rule', '')}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

with tab_add:
    st.markdown("##### ➕ Contribute New Golden Training Pair")
    st.write("Add reference SQL queries to enrich the few-shot RAG retrieval pool for similar user questions.")
    
    with st.form("new_pair_form"):
        form_domain = st.selectbox(
            "Target Domain File",
            [
                "orders_and_revenue.json",
                "products_and_catalog.json",
                "customers_and_profiles.json",
                "inventory_and_logistics.json",
                "marketing_and_coupons.json",
                "engagement_and_reviews.json",
                "returns_and_refunds.json",
                "carts_and_wishlists.json",
            ]
        )
        form_question = st.text_input("Natural Language Question", placeholder="e.g. What is the total discount amount redeemed in Q1?")
        form_sql = st.text_area("Gold MySQL Query", placeholder="SELECT SUM(c.discount_amount) FROM ...", height=120)
        form_tables = st.text_input("Involved Tables (comma-separated)", placeholder="e.g. coupons, coupon_redemptions, orders")
        form_difficulty = st.selectbox("Difficulty Level", ["easy", "medium", "complex", "extreme_edge_case"], index=1)
        
        submitted = st.form_submit_button("💾 Save Pair to Knowledge Base", use_container_width=True)
        if submitted:
            if not form_question.strip() or not form_sql.strip():
                st.error("Please provide both a question and a valid SQL query.")
            else:
                ok = add_golden_sql_pair(
                    domain_file=form_domain,
                    question=form_question,
                    sql=form_sql,
                    tables=form_tables,
                    difficulty=form_difficulty,
                )
                if ok:
                    st.success(f"Successfully added golden pair to `{form_domain}`! It is now active for hybrid RAG retrieval.")
                    st.rerun()
                else:
                    st.error(f"Failed to save training pair to `{form_domain}`.")
