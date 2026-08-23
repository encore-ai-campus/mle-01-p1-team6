from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKGROUND_PATH = PROJECT_ROOT / "assets" / "library-background.png"


def _background_data_uri() -> str:
    encoded = base64.b64encode(BACKGROUND_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def apply_library_theme() -> None:
    background = _background_data_uri()
    st.html(
        f"""
        <style>
        :root {{
            --library-ink: #13253a;
            --library-cream: #f8f3eb;
            --library-amber: #e3a85f;
            --library-sidebar: rgba(255, 251, 245, 0.92);
            --library-sidebar-ink: #24364b;
            --library-sidebar-muted: #687386;
        }}

        html,
        body,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        [data-testid="stAppViewContainer"] > .main,
        [data-testid="stAppViewContainer"] > section.main {{
            background: transparent !important;
        }}

        [data-testid="stAppViewContainer"] {{
            position: relative;
            z-index: 1;
        }}

        .stApp {{
            position: relative;
            isolation: isolate;
            min-height: 100vh;
            background: transparent !important;
        }}

        .stApp::before {{
            content: "";
            position: fixed;
            inset: 0;
            z-index: 0;
            pointer-events: none;
            background-image:
                linear-gradient(110deg, rgba(250, 246, 238, 0.68), rgba(252, 249, 244, 0.52) 48%, rgba(247, 241, 231, 0.66)),
                url("{background}");
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            background-color: #f7f1e8;
        }}

        [data-testid="stHeader"] {{
            background: transparent !important;
        }}

        [data-testid="stBottom"],
        [data-testid="stBottomBlockContainer"] {{
            background: transparent !important;
        }}

        [data-testid="stChatInput"] {{
            background: rgba(248, 245, 239, 0.96) !important;
            border: 1px solid rgba(201, 132, 56, 0.42) !important;
            border-radius: 16px !important;
            box-shadow: 0 10px 26px rgba(92, 62, 28, 0.14) !important;
        }}

        [data-testid="stSidebar"] {{
            background:
                linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(247, 237, 222, 0.94)),
                var(--library-sidebar) !important;
            backdrop-filter: blur(18px);
            border-right: 1px solid rgba(181, 132, 70, 0.24);
            box-shadow: 10px 0 34px rgba(92, 62, 28, 0.10);
        }}

        [data-testid="stSidebar"] * {{
            color: var(--library-sidebar-ink);
        }}

        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {{
            color: #8b5e2f;
            letter-spacing: -0.02em;
        }}

        [data-testid="stSidebarNav"] {{
            padding-top: 0.45rem;
        }}

        [data-testid="stSidebarNav"] span {{
            font-weight: 650;
        }}

        [data-testid="stSidebarNav"] a {{
            border-radius: 14px;
            margin: 0.2rem 0.35rem;
            padding: 0.62rem 0.72rem;
            transition: background 160ms ease, transform 160ms ease;
        }}

        [data-testid="stSidebarNav"] a:hover {{
            background: rgba(227, 168, 95, 0.14);
            transform: translateX(2px);
        }}

        [data-testid="stSidebarNav"] a[aria-current="page"] {{
            background: linear-gradient(90deg, rgba(227, 168, 95, 0.30), rgba(255, 255, 255, 0.58));
            box-shadow: inset 3px 0 0 #c98438, 0 6px 18px rgba(127, 82, 31, 0.08);
            color: #704519;
        }}

        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{
            color: var(--library-sidebar-muted);
        }}

        .block-container {{
            max-width: 1440px;
            padding-top: 3.2rem;
            padding-bottom: 4rem;
        }}

        [data-testid="stAppViewContainer"] .main h1,
        [data-testid="stAppViewContainer"] .main h2,
        [data-testid="stAppViewContainer"] .main h3 {{
            color: var(--library-ink);
            letter-spacing: -0.035em;
        }}

        [data-testid="stAppViewContainer"] .main p,
        [data-testid="stAppViewContainer"] .main label {{
            color: #334155;
        }}

        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background: rgba(248, 245, 239, 0.93);
            border: 1px solid rgba(255, 255, 255, 0.72);
            border-radius: 20px;
            box-shadow: 0 18px 50px rgba(0, 0, 0, 0.18);
        }}

        div[data-testid="stVerticalBlockBorderWrapper"] h1,
        div[data-testid="stVerticalBlockBorderWrapper"] h2,
        div[data-testid="stVerticalBlockBorderWrapper"] h3,
        div[data-testid="stVerticalBlockBorderWrapper"] p,
        div[data-testid="stVerticalBlockBorderWrapper"] label {{
            color: var(--library-ink);
        }}

        [data-testid="stMetric"] {{
            background: rgba(248, 245, 239, 0.94);
            border: 1px solid rgba(227, 168, 95, 0.42);
            border-radius: 18px;
            box-shadow: 0 12px 32px rgba(0, 0, 0, 0.16);
        }}

        [data-testid="stMetricLabel"],
        [data-testid="stMetricValue"] {{
            color: var(--library-ink) !important;
        }}

        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        textarea {{
            border-radius: 12px;
        }}

        button[kind="primary"] {{
            background: var(--library-amber);
            border-color: var(--library-amber);
            color: var(--library-ink);
            font-weight: 750;
        }}

        button[data-baseweb="tab"] {{
            color: var(--library-ink);
        }}
        </style>
        """,
    )
