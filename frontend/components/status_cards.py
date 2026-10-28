"""
Execution Pipeline Status Cards Component.
"""

import streamlit as st


def render_step_card(title: str, description: str, status: str = "success"):
    """Renders a single step card in the execution pipeline."""
    st.markdown(
        f"""
        <div class="step-card {status}">
            <div class="step-title">{title}</div>
            <div class="step-desc">{description}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
