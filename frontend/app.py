"""
AI Database Assistant - Multipage Streamlit Application
Home Dashboard & System Overview
"""

import streamlit as st
import asyncio
from pathlib import Path
import sys

# Ensure WindowsSelectorEventLoopPolicy is active for Windows socket SSL duplexing
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

# Ensure root, frontend, and backend directories are in sys.path
FRONTEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = FRONTEND_DIR.parent
BACKEND_DIR = ROOT_DIR / "backend"

for p in [ROOT_DIR, FRONTEND_DIR, BACKEND_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from frontend.components import render_header, render_overview_metrics
from frontend.services import (
    load_all_tables_metadata,
    load_all_sql_pairs,
    load_all_business_rules,
)
from frontend.config import SAMPLE_QUERIES

st.set_page_config(
    page_title="AI Database Assistant | E-Commerce Text-to-SQL",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_header(
    title="AI Database Assistant",
    subtitle="Autonomous Text-to-SQL Agent with Hybrid Warm-Start RAG & Bound Exploration Tools",
)

# Metric Overview Cards via Component
tables_meta = load_all_tables_metadata()
sql_pairs = load_all_sql_pairs()
rules = load_all_business_rules()

render_overview_metrics(
    tables_count=len(tables_meta) or 27,
    pairs_count=len(sql_pairs) or 56,
    rules_count=len(rules) or 6,
    tools_count=2,
)

st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

# Navigation Cards Section
st.markdown("### 🚀 Application Modules")

mcol1, mcol2 = st.columns(2)

with mcol1:
    st.markdown(
        """
        <div class="glass-card" style="min-height: 190px;">
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
                <span style="font-size: 24px;">💬</span>
                <h3 style="margin: 0; color: #ffffff; font-size: 18px;">AI Chat & SQL Agent</h3>
            </div>
            <p style="color: #a1a1aa; font-size: 13px; line-height: 1.5;">
                Ask natural language questions about customers, revenue, orders, inventory, returns, or marketing. 
                Watch the step-by-step agent workflow execute in real time with interactive SQL code and result tables.
            </p>
            <div style="margin-top: 12px;">
                <span style="font-size: 12px; color: #38bdf8; background: rgba(56, 189, 248, 0.1); padding: 4px 10px; border-radius: 6px;">👉 Open <b>1_💬_AI_Chat_Agent</b> in sidebar</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="glass-card" style="min-height: 190px;">
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
                <span style="font-size: 24px;">🧠</span>
                <h3 style="margin: 0; color: #ffffff; font-size: 18px;">Knowledge & Memories</h3>
            </div>
            <p style="color: #a1a1aa; font-size: 13px; line-height: 1.5;">
                Inspect and search through 56+ golden Question-SQL pairs across 8 modular domain files and corporate business rules. Add new few-shot pairs dynamically.
            </p>
            <div style="margin-top: 12px;">
                <span style="font-size: 12px; color: #a78bfa; background: rgba(167, 139, 250, 0.1); padding: 4px 10px; border-radius: 6px;">👉 Open <b>3_🧠_Knowledge_&_Memories</b> in sidebar</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with mcol2:
    st.markdown(
        """
        <div class="glass-card" style="min-height: 190px;">
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
                <span style="font-size: 24px;">🗄️</span>
                <h3 style="margin: 0; color: #ffffff; font-size: 18px;">Database Schema Explorer</h3>
            </div>
            <p style="color: #a1a1aa; font-size: 13px; line-height: 1.5;">
                Explore all 27 tables organized by business domain. Inspect column types, primary keys, foreign key relationships, and preview live sample records from the Aiven MySQL database.
            </p>
            <div style="margin-top: 12px;">
                <span style="font-size: 12px; color: #34d399; background: rgba(16, 185, 129, 0.1); padding: 4px 10px; border-radius: 6px;">👉 Open <b>2_🗄️_Database_Schema_Explorer</b> in sidebar</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="glass-card" style="min-height: 190px;">
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
                <span style="font-size: 24px;">🏛️</span>
                <h3 style="margin: 0; color: #ffffff; font-size: 18px;">Agent Architecture</h3>
            </div>
            <p style="color: #a1a1aa; font-size: 13px; line-height: 1.5;">
                Inspect the complete dual-mode workflow: Warm-Start RAG $\\rightarrow$ Autonomous ReAct Tool Exploration $\\rightarrow$ AST Read-Only Execution $\\rightarrow$ Self-Correction Repair Loop.
            </p>
            <div style="margin-top: 12px;">
                <span style="font-size: 12px; color: #fbbf24; background: rgba(251, 191, 36, 0.1); padding: 4px 10px; border-radius: 6px;">👉 Open <b>4_🏛️_Agent_Architecture</b> in sidebar</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

# Sample Query Playground via Constants
st.markdown("### 💡 Sample Questions to Try in the Chat Agent")

sc1, sc2, sc3 = st.columns(3)
for i, q in enumerate(SAMPLE_QUERIES):
    col = [sc1, sc2, sc3][i % 3]
    with col:
        st.info(f"🔍 **\"{q}\"**")

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ System Status")
st.sidebar.success("Database: **Connected** (ecommerce_db)")
st.sidebar.info("Model: **ChatOllama (gemma4)**")
st.sidebar.caption("Dual Bound Tools: `run_sql` & `search_knowledge_and_examples`")
