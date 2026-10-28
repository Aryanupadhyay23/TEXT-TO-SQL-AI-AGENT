"""
Centralized CSS Stylesheet & Glassmorphic Dark Theme.
"""

import streamlit as st


def apply_theme():
    """Injects high-end obsidian dark theme with glassmorphic cards and typography."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

        html, body, [class*="css"] {
            font-family: 'Plus Jakarta Sans', sans-serif;
        }

        code, pre, [class*="stCode"] {
            font-family: 'JetBrains Mono', monospace !important;
        }

        /* Top header brand container */
        .brand-header {
            background: linear-gradient(135deg, rgba(24, 24, 27, 0.85) 0%, rgba(9, 9, 11, 0.95) 100%);
            border: 1px solid rgba(63, 63, 70, 0.4);
            border-radius: 16px;
            padding: 20px 24px;
            margin-bottom: 24px;
            box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .brand-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 12px;
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.35);
            border-radius: 9999px;
            color: #34d399;
            font-size: 12px;
            font-weight: 600;
        }

        .brand-db-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 12px;
            background: rgba(56, 189, 248, 0.1);
            border: 1px solid rgba(56, 189, 248, 0.3);
            border-radius: 8px;
            color: #38bdf8;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
        }

        /* Glassmorphic Cards */
        .glass-card {
            background: rgba(24, 24, 27, 0.65);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(63, 63, 70, 0.4);
            border-radius: 14px;
            padding: 18px 20px;
            margin-bottom: 16px;
            transition: all 0.2s ease-in-out;
        }

        .glass-card:hover {
            border-color: rgba(161, 161, 170, 0.4);
            box-shadow: 0 8px 24px -8px rgba(0, 0, 0, 0.4);
        }

        /* Pipeline Step Card */
        .step-card {
            background: rgba(18, 18, 21, 0.8);
            border: 1px solid rgba(63, 63, 70, 0.5);
            border-left: 4px solid #8b5cf6;
            border-radius: 10px;
            padding: 12px 16px;
            margin: 8px 0;
            font-size: 13px;
        }

        .step-card.success {
            border-left-color: #10b981;
        }

        .step-card.error {
            border-left-color: #ef4444;
        }

        .step-title {
            font-weight: 700;
            color: #f4f4f5;
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 4px;
        }

        .step-desc {
            color: #a1a1aa;
            font-size: 12px;
            line-height: 1.4;
        }

        /* Metric Box */
        .metric-label {
            font-size: 12px;
            color: #a1a1aa;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 4px;
        }

        .metric-value {
            font-size: 24px;
            font-weight: 800;
            color: #fafafa;
        }

        /* Custom scrollbars */
        ::-webkit-scrollbar {
            width: 6px;
            height: 6px;
        }
        ::-webkit-scrollbar-track {
            background: rgba(9, 9, 11, 0.5);
        }
        ::-webkit-scrollbar-thumb {
            background: rgba(63, 63, 70, 0.6);
            border-radius: 3px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
