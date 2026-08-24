from __future__ import annotations

import html
import math

import streamlit as st

from utils.data import format_price, format_rating, load_books, safe_cover
from utils.theme import apply_library_theme


apply_library_theme()


def html_block(markup: str) -> None:
    st.html(markup)


books = load_books()
categories = ["전체"] + sorted(value for value in books["category_name"].unique() if value)
sort_options = {
    "관련도순": None,
    "가나다순": ["title"],
    "가격 낮은순": ["priceStandard"],
    "가격 높은순": ["priceStandard"],
    "평점 높은순": ["customerReviewRank"],
    "판매지수 높은순": ["salesPoint"],
}

html_block(
    """
    <div class="page-header">
      <div class="page-eyebrow">Book discovery / semantic index</div>
      <div class="page-title">찾고 싶은 책을, <em>더 정확하게.</em></div>
      <p class="page-subtitle">제목과 키워드뿐 아니라 저자, 출판사, 책 소개까지 함께 살펴봅니다. 검색어가 짧아도 지금 필요한 책에 가까운 결과부터 보여드릴게요.</p>
    </div>
    """
)

with st.form("book_search_form", border=True):
    st.markdown("**카탈로그 검색**")
    query = st.text_input("검색어", placeholder="예: 추리, 김영하, 자기계발", label_visibility="collapsed")
    first, second, third, action = st.columns([1.15, 1.15, 1.15, .55], vertical_alignment="bottom")
    with first:
        category = st.selectbox("카테고리", categories)
    with second:
        sort_option = st.selectbox("정렬", list(sort_options))
    with third:
        page_size = st.selectbox("페이지당 표시", [10, 20, 40], index=1)
    with action:
        submitted = st.form_submit_button("검색", type="primary", icon=":material/search:", width="stretch")

if submitted or "search_query" not in st.session_state:
    st.session_state.search_query = query
    st.session_state.search_category = category
    st.session_state.search_sort = sort_option
    st.session_state.search_page_size = page_size
    st.session_state.search_page = 1

query = st.session_state.get("search_query", "")
category = st.session_state.get("search_category", "전체")
sort_option = st.session_state.get("search_sort", "관련도순")
page_size = st.session_state.get("search_page_size", 20)

result = books
if category != "전체":
    result = result[result["category_name"].eq(category)]

if query.strip():
    query_mask = result[["title", "author", "publisher", "description"]].apply(
        lambda column: column.str.contains(query.strip(), case=False, na=False, regex=False)
    ).any(axis=1)
    result = result[query_mask]

sort_columns = sort_options[sort_option]
if sort_columns:
    result = result.sort_values(sort_columns, ascending=sort_option in {"가나다순", "가격 낮은순"})
elif query.strip():
    result = result.assign(
        _match=result["title"].str.contains(query.strip(), case=False, na=False, regex=False).astype(int)
        + result["author"].str.contains(query.strip(), case=False, na=False, regex=False).astype(int)
    ).sort_values(["_match", "salesPoint"], ascending=False).drop(columns="_match")
else:
    result = result.sort_values("salesPoint", ascending=False)

result = result.reset_index(drop=True)
total = len(result)
total_pages = max(1, math.ceil(total / page_size))
st.session_state.search_page = min(st.session_state.get("search_page", 1), total_pages)

page_left, page_right = st.columns([3, 1], vertical_alignment="center")
with page_left:
    query_label = f"‘{html.escape(query)}’ 검색 결과" if query.strip() else "추천 도서 카탈로그"
    html_block(f'<div class="result-summary"><strong>{query_label}</strong><span>{total:,}권 · 페이지 {st.session_state.search_page} / {total_pages}</span></div>')
with page_right:
    page = st.selectbox(
        "페이지",
        range(1, total_pages + 1),
        index=st.session_state.search_page - 1,
        key="search_page_select",
        format_func=lambda value: f"페이지 {value} / {total_pages}",
        label_visibility="collapsed",
    )
    st.session_state.search_page = page

if not total:
    html_block('<div class="empty-state"><strong>아직 맞는 책을 찾지 못했어요.</strong><br/>검색어를 조금 넓히거나 다른 카테고리를 선택해 보세요.</div>')
    st.stop()

start = (st.session_state.search_page - 1) * page_size
for _, book in result.iloc[start : start + page_size].iterrows():
    title = html.escape(str(book["title"] or "제목 정보 없음"))
    author = html.escape(str(book["author"] or "저자 정보 없음"))
    publisher = html.escape(str(book["publisher"] or "출판사 정보 없음"))
    category_label = html.escape(str(book["category_name"] or "기타"))
    description = str(book["description"] or "").replace("\n", " ").strip()
    with st.container(border=True):
        cover, detail = st.columns([1, 5], vertical_alignment="top")
        with cover:
            cover_url = safe_cover(book.get("cover"))
            if cover_url:
                st.image(cover_url, width=118)
            else:
                st.markdown(":material/menu_book:")
        with detail:
            html_block(
                f'<div class="book-result-title">{title}</div>'
                f'<div class="book-result-meta">{author} · {publisher}</div>'
                f'<div style="margin-top:.55rem"><span class="book-pill">{category_label}</span></div>'
            )
            st.caption(f"{format_price(book['priceStandard'])} · 평점 {format_rating(book['customerReviewRank'])} · 판매지수 {book['salesPoint']:,.0f}")
            if description:
                short_description = html.escape(description[:220] + ("…" if len(description) > 220 else ""))
                html_block(f'<div class="book-result-description">{short_description}</div>')
            if isinstance(book.get("link"), str) and book["link"].startswith("http"):
                st.link_button("상세 페이지 열기", book["link"], icon=":material/open_in_new:")


