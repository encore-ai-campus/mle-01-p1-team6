from __future__ import annotations

import pandas as pd
import streamlit as st
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from utils.data import format_price, format_rating, load_books, safe_cover
from utils.theme import apply_library_theme


apply_library_theme()


@st.cache_resource
def build_recommender(books: pd.DataFrame):
    text = (
        books["title"]
        + " "
        + books["author"]
        + " "
        + books["category_name"]
        + " "
        + books["description"].str.slice(0, 2000)
    )
    vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(2, 5), min_df=1, max_features=50000)
    matrix = vectorizer.fit_transform(text)
    return vectorizer, matrix


books = load_books()
categories = ["전체"] + sorted(value for value in books["category_name"].unique() if value)
max_price = max(books["priceStandard"].max(), 1)

st.title("취향 기반 도서 추천")
st.caption("원하는 분위기나 주제를 적으면 책 소개와 메타데이터를 바탕으로 가까운 책을 찾습니다.")

with st.form("recommend_form", border=True):
    preference = st.text_area(
        "어떤 책을 찾고 있나요?",
        placeholder="예: 몰입감 있는 추리소설, 따뜻한 위로가 되는 에세이, 실무에 바로 쓰는 데이터 분석 책",
        height=100,
    )
    first, second, third = st.columns(3)
    with first:
        category = st.selectbox("카테고리", categories)
    with second:
        price_limit = st.slider("최대 가격", 0.0, float(max_price), float(max_price), step=1000.0, format="%d원")
    with third:
        count = st.selectbox("추천 개수", [3, 5, 8, 10], index=1)
    submitted = st.form_submit_button("추천 받기", type="primary", icon=":material/auto_awesome:")

if submitted:
    candidates = books[books["priceStandard"].le(price_limit)]
    if category != "전체":
        candidates = candidates[candidates["category_name"].eq(category)]

    if candidates.empty:
        st.warning("조건에 맞는 책이 없습니다. 가격이나 카테고리를 넓혀 보세요.")
        st.stop()

    if preference.strip():
        vectorizer, matrix = build_recommender(books)
        query_vector = vectorizer.transform([preference])
        scores = cosine_similarity(query_vector, matrix).ravel()
        candidates = candidates.assign(_score=scores[candidates.index]).sort_values(
            ["_score", "customerReviewRank", "salesPoint"], ascending=False
        )
    else:
        candidates = candidates.sort_values(["customerReviewRank", "salesPoint"], ascending=False)

    recommendations = candidates.head(count)
    st.subheader("추천 결과")
    st.caption("소개·제목·저자·카테고리의 텍스트 유사도와 평점/판매지수를 함께 반영했습니다.")

    for row_start in range(0, len(recommendations), 3):
        row = recommendations.iloc[row_start : row_start + 3]
        columns = st.columns(len(row))
        for column, (_, book) in zip(columns, row.iterrows()):
            with column:
                with st.container(border=True):
                    cover_url = safe_cover(book.get("cover"))
                    if cover_url:
                        st.image(cover_url, width=150)
                    st.markdown(f"**{book['title']}**")
                    st.caption(book["author"] or "저자 정보 없음")
                    st.write(f"{format_price(book['priceStandard'])} · {format_rating(book['customerReviewRank'])}")
                    if book["category_name"]:
                        st.caption(book["category_name"])
                    if isinstance(book.get("link"), str) and book["link"].startswith("http"):
                        st.link_button("상세 보기", book["link"], icon=":material/open_in_new:")
