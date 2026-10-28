"""
Reusable Metric Dashboard Cards Component.
"""

import streamlit as st


def render_overview_metrics(tables_count: int = 27, pairs_count: int = 56, rules_count: int = 6, tools_count: int = 2):
    """Renders 4 glassmorphic metric cards across the top of the dashboard."""
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            """
            <div class="glass-card">
                <div class="metric-label">Target Database</div>
                <div class="metric-value" style="color: #38bdf8;">ecommerce_db</div>
                <div style="font-size: 12px; color: #71717a; margin-top: 4px;">Live Aiven MySQL 8.0+</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f"""
            <div class="glass-card">
                <div class="metric-label">Relational Tables</div>
                <div class="metric-value" style="color: #34d399;">{tables_count}</div>
                <div style="font-size: 12px; color: #71717a; margin-top: 4px;">Across 7 E-Commerce Domains</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            f"""
            <div class="glass-card">
                <div class="metric-label">Golden SQL Pairs</div>
                <div class="metric-value" style="color: #a78bfa;">{pairs_count}</div>
                <div style="font-size: 12px; color: #71717a; margin-top: 4px;">Few-Shot ChromaDB Store</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col4:
        st.markdown(
            f"""
            <div class="glass-card">
                <div class="metric-label">Autonomous Tools</div>
                <div class="metric-value" style="color: #fbbf24;">{tools_count} Bound</div>
                <div style="font-size: 12px; color: #71717a; margin-top: 4px;">run_sql & search_knowledge</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
