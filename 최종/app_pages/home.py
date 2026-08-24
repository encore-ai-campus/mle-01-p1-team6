from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from utils.data import load_books, safe_cover
from utils.theme import apply_library_theme


apply_library_theme()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEARCH_PAGE = "검색.py" if (PROJECT_ROOT / "대시보드.py").exists() else "app_pages/search.py"


def html_block(markup: str) -> None:
    st.html(markup)


books = load_books()
total_books = books["itemId"].nunique()
category_count = books["category_name"].replace("", pd.NA).nunique()
author_count = books["author"].replace("", pd.NA).nunique()
avg_rating = books.loc[books["customerReviewRank"] > 0, "customerReviewRank"].mean()
avg_rating = float(avg_rating) if pd.notna(avg_rating) else 0.0

html_block(
    """
    <div class="library-topbar">
      <div class="library-brand">
        <div class="library-mark">⌘</div>
        <div>
          <div class="library-brand-name">PageTurn</div>
          <div class="library-brand-sub">library intelligence</div>
        </div>
      </div>
      <div class="library-nav"><span>Overview</span><span>How it works</span><span>About the data</span></div>
    </div>
    """
)

hero_left, hero_right = st.columns([1.12, 0.88], gap="large", vertical_alignment="center")
with hero_left:
    html_block(
        """
        <div class="hero-shell">
          <div class="hero-eyebrow">A quieter way to find your next book</div>
          <div class="hero-title">읽고 싶은 마음을<br/><em>발견하는 순간</em>까지.</div>
          <div class="hero-copy">도서 데이터, 취향 신호, 그리고 AI의 언어 이해를 한곳에 모았습니다. 수많은 책 사이에서 지금의 나에게 맞는 한 권을 더 빠르고 깊이 있게 만나는 지식 탐색 공간입니다.</div>
          <div class="hero-tags"><span class="hero-tag">✦ semantic search</span><span class="hero-tag">✦ grounded answers</span><span class="hero-tag">✦ catalog analytics</span></div>
        </div>
        """
    )
    st.space("small")
    with st.container(horizontal=True, gap="small"):
        st.page_link(SEARCH_PAGE, label="도서 탐색 시작", icon=":material/search:", width="content")
        st.page_link("app_pages/도서도우미.py", label="AI 도우미 열기", icon=":material/auto_awesome:", width="content")

with hero_right:
    html_block(
        """
        <div class="hero-visual">
          <div class="hero-visual-panel">
            <div class="visual-label"><span>오늘의 탐색 온도</span><span>LIVE</span></div>
            <div class="visual-value">A room for curious minds</div>
            <div class="visual-bars"><i style="height:42%"></i><i style="height:58%"></i><i style="height:48%"></i><i style="height:76%"></i><i style="height:66%"></i><i style="height:92%"></i><i style="height:78%"></i><i style="height:100%"></i></div>
          </div>
        </div>
        """
    )

st.space("medium")
with st.container(horizontal=True, gap="small"):
    st.metric("큐레이션 카탈로그", f"{total_books:,}", "+12.4%", border=True, chart_data=[42, 49, 56, 65, 73, 82, 94], chart_type="line")
    st.metric("분류된 주제", f"{category_count:,}", "넓은 스펙트럼", border=True)
    st.metric("발견 가능한 저자", f"{author_count:,}", "다양한 목소리", border=True)
    st.metric("평균 독자 신뢰도", f"{avg_rating:.1f}/10", "상위 신호 기반", border=True, chart_data=[7.2, 7.4, 7.5, 7.7, 7.8, 8.0, 8.1], chart_type="line")

html_block(
    """
    <div class="section-heading"><div class="section-kicker">Built for better discovery</div><div class="section-title">도서관의 깊이와 제품의 속도를 함께</div></div>
    """
)
feature_columns = st.columns(3, gap="small")
features = [
    ("⌕", "의미를 읽는 검색", "제목이나 키워드가 정확히 일치하지 않아도, 질문의 의도와 문맥을 이해해 관련 도서를 찾아냅니다."),
    ("✦", "근거가 보이는 AI", "검색된 도서 정보에 기반해 답변합니다. 추천 이유와 참고한 책을 함께 보여주어 탐색의 맥락을 잃지 않습니다."),
    ("⌁", "카탈로그 인사이트", "카테고리·저자·출판사·가격 신호를 시각화해 어떤 책들이 사랑받고 있는지 한눈에 파악합니다."),
]
for column, (icon, title, description) in zip(feature_columns, features):
    with column:
        html_block(f'<div class="feature-card"><div class="feature-icon">{icon}</div><h3>{title}</h3><p>{description}</p></div>')

html_block(
    """
    <div class="section-heading"><div class="section-kicker">Under the cover</div><div class="section-title">한 권의 발견이 만들어지는 흐름</div></div>
    <div class="architecture">
      <div class="arch-step"><div class="arch-index">01 / INPUT</div><h4>도서 데이터</h4><p>카탈로그, 설명, 리뷰, 판매 신호를 하나의 탐색 가능한 문맥으로 모읍니다.</p></div>
      <div class="arch-arrow">→</div>
      <div class="arch-step"><div class="arch-index">02 / PROCESS</div><h4>정제 & 임베딩</h4><p>텍스트를 정규화하고 의미 벡터로 변환해 책과 질문 사이의 거리를 계산합니다.</p></div>
      <div class="arch-arrow">→</div>
      <div class="arch-step"><div class="arch-index">03 / RETRIEVE</div><h4>스마트 검색</h4><p>키워드와 의미 검색을 함께 사용해 더 정확하고 풍부한 후보를 고릅니다.</p></div>
      <div class="arch-arrow">→</div>
      <div class="arch-step"><div class="arch-index">04 / ANSWER</div><h4>AI 큐레이션</h4><p>검색 근거를 바탕으로 지금의 취향에 맞는 설명과 다음 책을 제안합니다.</p></div>
    </div>
    """
)

html_block(
    """
    <div class="section-heading"><div class="section-kicker">A glimpse inside</div><div class="section-title">실제 서비스처럼 미리 탐색해보세요</div></div>
    """
)
demo_left, demo_right = st.columns([1.05, 0.95], gap="small")
with demo_left:
    with st.container(border=True):
        html_block('<div class="demo-head"><span class="demo-title">카탈로그 탐색</span><span class="online-dot">index ready</span></div>')
        preview_query = st.text_input("찾고 싶은 책", placeholder="예: 다정함과 회복에 관한 에세이", label_visibility="collapsed", key="home_preview_query")
        filtered = books
        if preview_query.strip():
            mask = filtered[["title", "author", "description"]].apply(lambda column: column.str.contains(preview_query.strip(), case=False, na=False, regex=False)).any(axis=1)
            filtered = filtered[mask]
        preview = filtered.sort_values("salesPoint", ascending=False).head(3)
        if preview.empty:
            st.caption("아직 정확히 맞는 책을 찾지 못했어요. AI 도우미에서 문장으로 물어보세요.")
        else:
            for _, book in preview.iterrows():
                with st.container(horizontal=True, gap="small"):
                    cover_url = safe_cover(book.get("cover"))
                    if cover_url:
                        st.image(cover_url, width=42)
                    with st.container():
                        st.markdown(f"**{book['title']}**")
                        st.caption(f"{book['author'] or '저자 정보 없음'}  ·  {book['category_name'] or '기타'}")

with demo_right:
    with st.container(border=True):
        html_block('<div class="demo-head"><span class="demo-title">AI 도우미 미리보기</span><span class="online-dot">grounded</span></div>')
        st.chat_message("user", avatar=":material/person:").write("요즘 마음을 돌보는 데 도움이 될 책이 있을까요?")
        with st.chat_message("assistant", avatar=":material/auto_awesome:"):
            html_block('<div class="answer-card"><div class="answer-meta">PageTurn AI · 0.8s</div><div class="answer-text">지금의 질문에는 회복과 자기 이해를 천천히 따라가는 에세이가 잘 어울려요. 검색된 문맥을 바탕으로 부담 없이 읽기 좋은 책부터 골라볼게요.</div></div>')
            st.caption("추천 근거 3개 · 도서 설명과 독자 신호를 함께 참고")

html_block(
    """
    <div class="footer-cta"><h2>다음 페이지를 여는 가장 좋은 방법</h2><p>데이터를 둘러보거나, 지금 떠오른 질문을 AI에게 바로 건네보세요.</p></div>
    <div style="display:flex;gap:.5rem;flex-wrap:wrap;margin-top:1rem"><span class="tech-pill">Streamlit</span><span class="tech-pill">ChromaDB</span><span class="tech-pill">RAG</span><span class="tech-pill">Supabase</span><span class="tech-pill">Altair</span></div>
    """
)

