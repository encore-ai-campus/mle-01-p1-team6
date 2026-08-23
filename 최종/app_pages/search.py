from __future__ import annotations

import math

import streamlit as st

from utils.data import format_price, format_rating, load_books, safe_cover
from utils.theme import apply_library_theme


apply_library_theme()


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

st.title("🔎 도서 검색")
st.caption("제목, 저자, 출판사, 책 소개를 한 번에 검색할 수 있습니다.")

with st.form("book_search_form", border=True):
    query = st.text_input("검색어", placeholder="예: 추리, 김영하, 자기계발")
    first, second, third = st.columns(3)
    with first:
        category = st.selectbox("카테고리", categories)
    with second:
        sort_option = st.selectbox("정렬", list(sort_options))
    with third:
        page_size = st.selectbox("페이지당 표시", [10, 20, 40], index=1)
    submitted = st.form_submit_button("검색", type="primary", icon=":material/search:")

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

header_left, header_right = st.columns([3, 1])
header_left.write(f"검색 결과 **{total:,}권**")
with header_right:
    page = st.selectbox(
        "페이지",
        range(1, total_pages + 1),
        index=st.session_state.search_page - 1,
        key="search_page_select",
        format_func=lambda value: f"{value} / {total_pages}",
        label_visibility="collapsed",
    )
    st.session_state.search_page = page

if not total:
    st.info("검색 결과가 없습니다. 다른 검색어나 카테고리를 선택해 보세요.")
    st.stop()

start = (st.session_state.search_page - 1) * page_size
for _, book in result.iloc[start : start + page_size].iterrows():
    with st.container(border=True):
        cover, detail = st.columns([1, 5])
        with cover:
            cover_url = safe_cover(book.get("cover"))
            if cover_url:
                st.image(cover_url, width=110)
            else:
                st.markdown(":material/menu_book:")
        with detail:
            st.subheader(book["title"] or "제목 정보 없음")
            st.caption(f"{book['author'] or '저자 정보 없음'} · {book['publisher'] or '출판사 정보 없음'}")
            st.write(f"{format_price(book['priceStandard'])} · 평점 {format_rating(book['customerReviewRank'])} · {book['category_name']}")
            description = book["description"].replace("\n", " ").strip()
            if description:
                st.write(description[:180] + ("…" if len(description) > 180 else ""))
            if isinstance(book.get("link"), str) and book["link"].startswith("http"):
                st.link_button("알라딘에서 보기", book["link"], icon=":material/open_in_new:")
