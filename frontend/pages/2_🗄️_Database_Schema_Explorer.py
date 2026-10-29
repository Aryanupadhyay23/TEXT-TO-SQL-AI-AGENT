"""
Database Schema Explorer Page
Interactive exploration of all 27 tables in ecommerce_db grouped by business domain,
with column definitions, foreign keys, and live Aiven MySQL table record previews.
"""

import streamlit as st
import pandas as pd
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
from frontend.services import load_all_tables_metadata, fetch_live_table_preview
from frontend.config import TABLE_DOMAINS

st.set_page_config(
    page_title="Database Schema Explorer | ecommerce_db",
    page_icon="🗄️",
    layout="wide",
)

render_header(
    title="Database Schema Explorer",
    subtitle="Inspect all 27 tables, column definitions, data types, foreign keys, and live records from ecommerce_db",
)

tables_meta = load_all_tables_metadata()

# Domain Filter & Search Controls
st.markdown("### 🗂️ Browse Tables by Business Domain")

domain_options = ["All Domains (27 Tables)"] + list(TABLE_DOMAINS.keys())
selected_domain = st.selectbox("Select Business Domain", domain_options)

search_col, count_col = st.columns([3, 1])
with search_col:
    table_search = st.text_input("🔍 Search tables by name...", placeholder="e.g. orders, inventory, products...")

# Filter tables
if selected_domain == "All Domains (27 Tables)":
    candidate_tables = sorted(list(tables_meta.keys()))
else:
    candidate_tables = TABLE_DOMAINS.get(selected_domain, [])

if table_search.strip():
    candidate_tables = [t for t in candidate_tables if table_search.lower() in t.lower()]

with count_col:
    st.metric("Matching Tables", len(candidate_tables))

if not candidate_tables:
    st.warning("No tables matched your search criteria.")
    st.stop()

# Layout: Left column table selector, Right column table details & live preview
left_col, right_col = st.columns([1, 2.5])

with left_col:
    st.markdown("##### 📋 Table Directory")
    selected_table_name = st.radio(
        "Choose a table to inspect:",
        candidate_tables,
        label_visibility="collapsed",
    )

with right_col:
    table_info = tables_meta.get(selected_table_name, {})
    
    st.markdown(
        f"""
        <div class="glass-card" style="margin-bottom: 14px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h3 style="margin: 0; color: #38bdf8; font-family: 'JetBrains Mono', monospace;">
                    📊 {selected_table_name}
                </h3>
                <span class="brand-pill">Target Table</span>
            </div>
            <p style="color: #a1a1aa; font-size: 13px; margin-top: 6px;">
                {table_info.get('description', 'Core relational entity in ecommerce_db.')}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_schema, tab_records, tab_fks = st.tabs(["📐 Column Schema", "👁️ Live Records Preview", "🔗 Foreign Keys & Joins"])

    with tab_schema:
        columns_data = table_info.get("columns", [])
        if columns_data:
            # Build DataFrame
            rows = []
            for col in columns_data:
                rows.append({
                    "Column Name": col.get("name"),
                    "Type": col.get("column_type") or col.get("data_type", ""),
                    "Nullable": "YES" if col.get("nullable") else "NO",
                    "Key": "PK" if col.get("primary_key") else "",
                    "Default": str(col.get("default", "")),
                    "Extra": col.get("extra", ""),
                })
            df_cols = pd.DataFrame(rows)
            st.dataframe(df_cols, use_container_width=True, hide_index=True)
        else:
            st.info("Schema definition details loading or unavailable.")

    with tab_records:
        rcol1, rcol2 = st.columns([2, 1])
        with rcol1:
            st.markdown(f"Previewing live rows directly from Aiven MySQL (`{selected_table_name}`)")
        with rcol2:
            row_limit = st.selectbox("Row Limit", [10, 25, 50, 100], index=1)

        with st.spinner(f"Querying live database for {selected_table_name}..."):
            df_records, err = fetch_live_table_preview(selected_table_name, limit=row_limit)

        if err:
            st.error(f"Error fetching live table records: {err}")
        elif df_records is not None and not df_records.empty:
            st.dataframe(df_records, use_container_width=True)
            csv_data = df_records.to_csv(index=False).encode("utf-8")
            st.download_button(
                label=f"📥 Download {selected_table_name} preview as CSV",
                data=csv_data,
                file_name=f"{selected_table_name}_preview.csv",
                mime="text/csv",
            )
        else:
            st.info(f"No records found in table `{selected_table_name}`.")

    with tab_fks:
        fks = table_info.get("foreign_keys", [])
        if fks:
            fk_rows = []
            for fk in fks:
                fk_rows.append({
                    "Constraint": fk.get("constraint_name", "N/A"),
                    "Column": fk.get("column") or fk.get("column_name", "N/A"),
                    "Referenced Table": fk.get("referenced_table") or fk.get("referenced_table_name", "N/A"),
                    "Referenced Column": fk.get("referenced_column") or fk.get("referenced_column_name", "N/A"),
                })
            st.dataframe(pd.DataFrame(fk_rows), use_container_width=True, hide_index=True)
        else:
            st.info(f"Table `{selected_table_name}` has no explicit foreign key dependencies.")
