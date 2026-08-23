from __future__ import annotations

import streamlit as st

from utils.theme import apply_library_theme


st.set_page_config(
    page_title="도서 도우미 AI",
    page_icon=":material/auto_stories:",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_library_theme()

page = st.navigation(
    {
        "메인": [
            st.Page(
                "app_pages/home.py",
                title="🏠 홈",
                icon=":material/home:",
            ),
        ],
        "도서 서비스": [
            st.Page(
                "대시보드_진명.py",
                title="📊 도서 분석 대시보드",
                icon=":material/analytics:",
            ),
            st.Page(
                "app_pages/도서도우미.py",
                title="🤖 도서 도우미 AI",
                icon=":material/auto_awesome:",
            ),
            st.Page(
                "검색.py",
                title="🔎 도서 검색",
                icon=":material/search:",
            ),
        ]
    },
    position="sidebar",
)

page.run()
