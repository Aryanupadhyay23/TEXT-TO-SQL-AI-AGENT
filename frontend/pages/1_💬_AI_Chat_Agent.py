"""
AI Chat & SQL Agent Page
Interactive conversational Text-to-SQL interface with real-time execution steps,
SQL code blocks, interactive data tables, and suggestion chips.
"""

import streamlit as st
import asyncio
import uuid
import pandas as pd
from pathlib import Path
import sys

# Ensure WindowsSelectorEventLoopPolicy is active for Windows socket SSL duplexing
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

# Ensure root, frontend, and backend directories are in sys.path
PAGES_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = PAGES_DIR.parent
ROOT_DIR = FRONTEND_DIR.parent
BACKEND_DIR = ROOT_DIR / "backend"

for p in [ROOT_DIR, FRONTEND_DIR, BACKEND_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import importlib
import frontend.services.agent_service as agent_service_module
importlib.reload(agent_service_module)
stream_agent_workflow = agent_service_module.stream_agent_workflow

from frontend.components import render_header, render_step_card
from frontend.config import SAMPLE_QUERIES

st.set_page_config(
    page_title="AI Chat Agent | E-Commerce Text-to-SQL",
    page_icon="💬",
    layout="wide",
)

render_header(
    title="AI Chat & SQL Agent",
    subtitle="Ask natural language questions and watch the autonomous agent reason, inspect schema, and generate verified MySQL",
)

# Sidebar conversation management
if "thread_id" not in st.session_state:
    st.session_state.thread_id = f"thread_{uuid.uuid4().hex[:8]}"

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.markdown("### 💬 Session Controls")
    if st.button("➕ New Conversation", use_container_width=True):
        st.session_state.thread_id = f"thread_{uuid.uuid4().hex[:8]}"
        st.session_state.messages = []
        st.rerun()

    st.markdown(f"**Thread ID:** `{st.session_state.thread_id}`")
    st.markdown(f"**Total Turns:** `{len(st.session_state.messages) // 2}`")
    
    show_pipeline_steps = st.checkbox("Show Detailed Workflow Cards", value=True)
    st.markdown("---")
    st.markdown("### 💡 Recommended Questions")
    for s in SAMPLE_QUERIES:
        if st.button(f"👉 {s}", key=f"sug_{s}", use_container_width=True):
            st.session_state.preset_query = s
            st.rerun()

# Check for preset query from sidebar
preset_query = st.session_state.pop("preset_query", None)

# Render Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="👤" if msg["role"] == "user" else "🤖"):
        if msg["role"] == "user":
            st.write(msg["content"])
        else:
            # Render workflow pipeline steps if enabled
            if show_pipeline_steps and msg.get("steps"):
                with st.expander("🔍 **Agent Execution Pipeline**", expanded=False):
                    for step in msg["steps"]:
                        st.markdown(
                            f"""
                            <div class="step-card {step.get('status', 'success')}">
                                <div class="step-title">{step.get('title')}</div>
                                <div class="step-desc">{step.get('description')}</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
            
            # Render SQL query if generated
            if msg.get("sql"):
                st.markdown("##### 📝 Generated MySQL Query")
                st.code(msg["sql"], language="sql")

            # Render retrieved SQL pairs if available
            if msg.get("examples"):
                with st.expander(f"🧠 **Retrieved Reference SQL Pairs ({len(msg['examples'])})**", expanded=False):
                    for ex in msg["examples"]:
                        st.caption(f"💡 **Sample Query:** {ex.get('question')}")
                        st.code(ex.get("sql"), language="sql")

            # Render SQL results table if available
            if msg.get("table") is not None and not msg["table"].empty:
                st.markdown(f"##### 📊 Query Results ({len(msg['table'])} rows)")
                st.dataframe(msg["table"], use_container_width=True)
                csv = msg["table"].to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📥 Download Results as CSV",
                    data=csv,
                    file_name="query_results.csv",
                    mime="text/csv",
                    key=f"dl_{msg.get('id', uuid.uuid4())}",
                )

            # Render natural language answer
            st.markdown(msg["content"])


# Input handling
user_input = st.chat_input("Ask a question about store orders, products, inventory, revenue, or customers...")
active_query = preset_query or user_input

if active_query:
    # 1. Add user message
    st.session_state.messages.append({"role": "user", "content": active_query})
    with st.chat_message("user", avatar="👤"):
        st.write(active_query)

    # 2. Assistant execution with live streaming steps
    with st.chat_message("assistant", avatar="🤖"):
        status_placeholder = st.empty()
        pipeline_container = st.container()
        sql_placeholder = st.empty()
        table_placeholder = st.empty()
        answer_placeholder = st.empty()

        steps_log = []
        generated_sql = None
        sql_results = None
        final_answer = None

        with status_placeholder.status("🤖 Agent is analyzing query & database schema...", expanded=True) as status_box:
            async def execute_query_flow(query: str, thread_id: str):
                steps = []
                gen_sql = None
                results_df = None
                ans_text = None
                retrieved_examples = []
                retrieved_rules = []

                async for node_name, values in stream_agent_workflow(query, thread_id):
                    if node_name == "query_understanding":
                        intent = values.get("intent", "database_query")
                        desc = f"Classified intent as **'{intent}'** (Processed: *{values.get('processed_query')}*)"
                        steps.append({
                            "title": "1. Query Understanding & Classification",
                            "description": desc,
                            "status": "success",
                        })
                        status_box.write(f"✅ **1. Query Understanding:** {intent}")

                    elif node_name == "query_expansion":
                        vars_list = values.get("query_variations", [])
                        desc = f"Synthesized {len(vars_list)} high-density query variations for multi-index retrieval"
                        steps.append({
                            "title": "2. Multi-Query Expansion",
                            "description": desc,
                            "status": "success",
                        })
                        status_box.write(f"✅ **2. Query Expansion:** Generated {len(vars_list)} search variations")

                    elif node_name == "retriever":
                        tables = values.get("retrieved_tables", [])
                        examples = values.get("retrieved_examples", [])
                        rules = values.get("retrieved_rules", [])
                        retrieved_examples = examples
                        retrieved_rules = rules
                        desc = f"Retrieved {len(tables)} tables ({', '.join(tables) if tables else 'None'}), {len(examples)} SQL pairs, {len(rules)} business rules"
                        steps.append({
                            "title": "3. Multi-Index Hybrid Retrieval (RRF)",
                            "description": desc,
                            "status": "success",
                        })
                        status_box.write(f"✅ **3. Hybrid Retrieval:** Loaded {len(tables)} table(s) [{', '.join(tables)}], {len(examples)} golden SQL pair(s), {len(rules)} business rule(s)")

                    elif node_name == "sql_generation":
                        gen_sql = values.get("sql_query")
                        gen_err = values.get("error")
                        if gen_sql:
                            desc = "Synthesized verified MySQL query with explicit column projections"
                            steps.append({
                                "title": "4. Autonomous SQL Generation",
                                "description": desc,
                                "status": "success",
                            })
                            status_box.write("✅ **4. SQL Generation:** Complete")
                            sql_placeholder.markdown("##### 📝 Generated MySQL Query")
                            sql_placeholder.code(gen_sql, language="sql")
                        else:
                            steps.append({
                                "title": "4. Autonomous SQL Generation",
                                "description": f"Failed: {gen_err}",
                                "status": "error",
                            })

                    elif node_name == "sql_execution":
                        rows = values.get("sql_results") or []
                        exec_err = values.get("error")
                        if rows is not None and not exec_err:
                            results_df = pd.DataFrame(rows)
                            desc = f"Executed read-only query on live Aiven MySQL. Returned {len(rows)} row(s)."
                            steps.append({
                                "title": "5. Safe SQL Execution",
                                "description": desc,
                                "status": "success",
                            })
                            status_box.write(f"✅ **5. SQL Execution:** Returned {len(rows)} record(s)")
                            if not results_df.empty:
                                table_placeholder.markdown(f"##### 📊 Query Results ({len(rows)} rows)")
                                table_placeholder.dataframe(results_df, use_container_width=True)
                        else:
                            steps.append({
                                "title": "5. Safe SQL Execution",
                                "description": f"Error: {exec_err}",
                                "status": "error",
                            })

                    elif node_name == "sql_repair":
                        retry_c = values.get("retry_count", 1)
                        repaired = values.get("sql_query")
                        steps.append({
                            "title": f"SQL Self-Correction Cycle #{retry_c}",
                            "description": f"Auto-repaired SQL: {repaired}",
                            "status": "success",
                        })
                        status_box.write(f"🔄 **SQL Repair:** Rectified error on attempt #{retry_c}")

                    elif node_name == "answer_generation":
                        ans_text = values.get("final_answer") or values.get("direct_response") or "Query executed successfully."
                        steps.append({
                            "title": "6. Natural Language Answer Synthesis",
                            "description": "Synthesized executive business answer without technical database jargon",
                            "status": "success",
                        })
                        status_box.write("✅ **6. Executive Answer Synthesized**")

                return steps, gen_sql, results_df, ans_text, retrieved_examples, retrieved_rules

            # Execute workflow
            steps_log, generated_sql, sql_results, final_answer, retrieved_examples, retrieved_rules = asyncio.run(
                execute_query_flow(active_query, st.session_state.thread_id)
            )
            status_box.update(label="✨ Analysis complete!", state="complete", expanded=False)

        # Render retrieved SQL pairs expander if any were retrieved
        if retrieved_examples:
            with st.expander(f"🧠 **Retrieved Reference SQL Pairs ({len(retrieved_examples)})**", expanded=False):
                for ex in retrieved_examples:
                    st.caption(f"💡 **Sample Query:** {ex.get('question')}")
                    st.code(ex.get("sql"), language="sql")

        # Render final synthesized answer
        answer_text = final_answer or "I was unable to retrieve a response for this query."
        answer_placeholder.markdown(answer_text)

        # Save assistant message to session state
        st.session_state.messages.append({
            "id": uuid.uuid4().hex,
            "role": "assistant",
            "content": answer_text,
            "sql": generated_sql,
            "table": sql_results,
            "steps": steps_log,
            "examples": retrieved_examples,
        })
