from __future__ import annotations

import os

import streamlit as st

from utils.theme import apply_library_theme


st.set_page_config(
    page_title="도서 도우미 AI",
    page_icon=":material/auto_stories:",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_library_theme()


# Streamlit Cloud Secrets를 하위 페이지와 라이브러리가 읽을 수 있는
# 환경변수로 연결합니다. 이미 설정된 환경변수는 우선 유지합니다.
for _key in ("OPENAI_API_KEY", "SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY"):
    try:
        if not os.getenv(_key) and _key in st.secrets:
            _value = str(st.secrets[_key]).strip()
            if _value:
                os.environ[_key] = _value
    except Exception:
        # Secrets가 없는 로컬 실행에서도 일반 페이지는 열 수 있어야 합니다.
        pass

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
                "대시보드.py",
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
