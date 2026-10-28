"""
Reusable Header Component for Streamlit Pages.
"""

import streamlit as st
from frontend.styles.theme import apply_theme


def render_header(title: str, subtitle: str):
    """Renders the top branding header on each page."""
    apply_theme()
    st.markdown(
        f"""
        <div class="brand-header">
            <div>
                <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 4px;">
                    <h2 style="margin: 0; color: #ffffff; font-weight: 800; font-size: 22px;">{title}</h2>
                    <span class="brand-pill">● Online</span>
                </div>
                <div style="color: #a1a1aa; font-size: 13px;">{subtitle}</div>
            </div>
            <div style="display: flex; align-items: center; gap: 10px;">
                <span class="brand-db-badge">🗄️ ecommerce_db</span>
                <span style="font-size: 11px; color: #71717a; background: rgba(39, 39, 42, 0.6); padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(63, 63, 70, 0.4);">Aiven MySQL</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
