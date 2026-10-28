"""
Agent Architecture Page
Interactive workflow diagram, technical specifications, and phase-by-phase
breakdown of the Text-to-SQL autonomous agent with bound tools.
"""

import streamlit as st
import streamlit.components.v1 as components
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
from frontend.config import SYSTEM_SPECIFICATIONS

st.set_page_config(
    page_title="Agent Architecture | E-Commerce Text-to-SQL",
    page_icon="🏛️",
    layout="wide",
)

render_header(
    title="Agent Architecture & Pipeline",
    subtitle="Interactive execution flowchart, dual-mode autonomous tool binding, and system specifications",
)

st.markdown("### 🗺️ End-to-End System Flowchart")

# Render Mermaid diagram via HTML component
mermaid_code = """
flowchart TD
    classDef startNode fill:#0f172a,stroke:#38bdf8,stroke-width:2px,color:#f8fafc;
    classDef ragNode fill:#1e1b4b,stroke:#818cf8,stroke-width:2px,color:#e0e7ff;
    classDef toolNode fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#ecfdf5;
    classDef agentNode fill:#4a044e,stroke:#f472b6,stroke-width:2px,color:#fdf2f8;
    classDef execNode fill:#451a03,stroke:#f59e0b,stroke-width:2px,color:#fffbeb;
    classDef finishNode fill:#0369a1,stroke:#7dd3fc,stroke-width:2.5px,color:#ffffff;

    User(["👤 User Natural Language Input"]):::startNode --> QU["1. Query Understanding & Intent Gate"]:::ragNode
    
    QU -->|"Greeting / Memory / Out of Scope"| DirectAns["💬 Direct Response"]:::finishNode
    QU -->|"database_query"| QE["2. Multi-Query Expansion (3 Variations)"]:::ragNode
    
    subgraph Phase1 ["Phase 1: Deterministic Warm-Start RAG"]
        QE --> HybridRAG["3. Multi-Index Hybrid Search<br/>• BM25 + Semantic Search (RRF)<br/>• Tables, Rules, Few-Shots"]:::ragNode
        HybridRAG --> EntityMatcher["Literal Entity Matcher &<br/>Foreign Key Join Graph"]:::ragNode
        EntityMatcher --> ContextBundle["📦 Warm Context Bundle"]:::ragNode
    end

    subgraph Phase2 ["Phase 2: Autonomous SQL Agent & Bound Tools"]
        ContextBundle --> ToolAgent{"4. Autonomous SQL Agent<br/>(ReAct Tool Loop)"}:::agentNode
        ToolAgent -.->|"Needs Schema / Probe Values"| Tool1["🛠️ run_sql(sql)<br/>SHOW, DESCRIBE, SELECT DISTINCT"]:::toolNode
        ToolAgent -.->|"Needs Rules / Formulas"| Tool2["📚 search_knowledge_and_examples(query)"]:::toolNode
        Tool1 -.->|"Tool Output"| ToolAgent
        Tool2 -.->|"Tool Output"| ToolAgent
        ToolAgent -->|"Fast-Path or Post-Exploration"| FinalSQL["Synthesized MySQL Query"]:::agentNode
    end

    subgraph Phase3 ["Phase 3: Execution, Self-Healing & Synthesis"]
        FinalSQL --> Validator["5. AST Read-Only Validation<br/>(Block mutating statements, auto LIMIT)"]:::execNode
        Validator --> DB[("🗄️ Aiven MySQL 8.0+<br/>ecommerce_db (27 Tables)")]:::execNode
        DB -->|"MySQL Error"| Repair["🔄 SQL Self-Correction Node<br/>(Retry loop up to max_retries)"]:::execNode
        Repair --> Validator
        DB -->|"Query Rows"| AnsGen["6. Executive Answer Synthesizer<br/>(Zero Technical/SQL Jargon)"]:::finishNode
    end

    AnsGen --> SSEOutput(["✨ Real-Time SSE Stream & Table Output"]):::finishNode
"""

html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <script>
        mermaid.initialize({{
            startOnLoad: true,
            theme: 'dark',
            themeVariables: {{
                fontFamily: 'Plus Jakarta Sans, sans-serif',
                darkMode: true,
                background: '#09090b',
                primaryColor: '#8b5cf6',
                edgeColor: '#64748b'
            }}
        }});
    </script>
    <style>
        body {{
            background: #09090b;
            margin: 0;
            padding: 10px;
            display: flex;
            justify-content: center;
        }}
    </style>
</head>
<body>
    <div class="mermaid">
        {mermaid_code}
    </div>
</body>
</html>
"""

components.html(html_content, height=640, scrolling=True)

st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

# Phase Details Cards
st.markdown("### ⚙️ Deep-Dive Architecture Phases")

pcol1, pcol2 = st.columns(2)

with pcol1:
    st.markdown(
        """
        <div class="glass-card" style="border-left: 4px solid #8b5cf6;">
            <h4 style="margin: 0 0 8px 0; color: #a78bfa;">Phase 1: Deterministic Warm-Start RAG</h4>
            <p style="color: #a1a1aa; font-size: 13px; line-height: 1.5;">
                • <b>Query Understanding:</b> History-aware sliding window resolves follow-up queries while preserving active filters.<br/>
                • <b>Multi-Query Expander:</b> Generates 3 keyword-dense variations to maximize recall across sparse and dense indices.<br/>
                • <b>Hybrid RRF Retrieval:</b> Concurrently queries table definitions, business rules, and few-shot pairs via Reciprocal Rank Fusion.<br/>
                • <b>Graph Expansion:</b> Traverses foreign-key relationships to find the optimal join paths across the 27 tables.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="glass-card" style="border-left: 4px solid #f59e0b;">
            <h4 style="margin: 0 0 8px 0; color: #fbbf24;">Phase 3: AST Guardrails & Safe Execution</h4>
            <p style="color: #a1a1aa; font-size: 13px; line-height: 1.5;">
                • <b>Read-Only Enforcement:</b> Blocks INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, or administrative statements.<br/>
                • <b>Safe Probing:</b> Explicitly allows SHOW, DESCRIBE, and EXPLAIN for schema introspection.<br/>
                • <b>Automated LIMIT Guard:</b> Injects LIMIT 20 if unbounded SELECT is detected to prevent memory exhaustion.<br/>
                • <b>Connection Pool:</b> Asynchronous MySQL connection pooling for high throughput.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with pcol2:
    st.markdown(
        """
        <div class="glass-card" style="border-left: 4px solid #10b981;">
            <h4 style="margin: 0 0 8px 0; color: #34d399;">Phase 2: Autonomous Tool Binding (ReAct)</h4>
            <p style="color: #a1a1aa; font-size: 13px; line-height: 1.5;">
                • <b>run_sql(sql):</b> Live read-only execution tool allowing the agent to run DESCRIBE, inspect distinct enum values, or dry-run candidates.<br/>
                • <b>search_knowledge_and_examples(query):</b> Searches business rules, KPI formulas, and few-shot golden pairs.<br/>
                • <b>Fast-Path vs. Exploration:</b> Directly outputs final SQL when warm context is sufficient; autonomously calls tools when schema is ambiguous.<br/>
                • <b>Synthesis Node:</b> Automatically merges tool discovery outputs into the final query.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="glass-card" style="border-left: 4px solid #38bdf8;">
            <h4 style="margin: 0 0 8px 0; color: #38bdf8;">Phase 4 & 5: Self-Correction & Synthesis</h4>
            <p style="color: #a1a1aa; font-size: 13px; line-height: 1.5;">
                • <b>Self-Correction Loop:</b> If a MySQL error occurs during execution, the error diagnosis and schema context loop back into sql_repair up to 3 times.<br/>
                • <b>Zero-Jargon Business Synthesis:</b> Never exposes raw table names, column keys, or SQL errors to end-users.<br/>
                • <b>Rich Output:</b> Delivers clean Markdown tables with currency formatting ($) and capitalized headers.<br/>
                • <b>Checkpointer Persistence:</b> Multi-turn state saved to LangGraph Checkpointer.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Technical Specifications Table
st.markdown("### 📋 Technical Specifications")
st.table(SYSTEM_SPECIFICATIONS)
