from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

import os
import sys

# 현재 파일(dashboard.py)의 상위 폴더(프로젝트 루트)를 파이썬 모듈 검색 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.data import format_price, format_rating, load_books, safe_cover
from utils.theme import apply_library_theme


apply_library_theme()


def format_count(value: float | int) -> str:
    return f"{int(value):,}"


def build_chart(chart: alt.Chart) -> alt.Chart:
    return (
        chart.properties(height=320)
        .configure_view(stroke=None)
        .configure_axis(
            labelColor="#64748B",
            titleColor="#0F172A",
            gridColor="#E2E8F0",
            domainColor="#E2E8F0",
            tickColor="#E2E8F0",
            labelFont="Noto Sans KR",
            titleFont="Noto Sans KR",
        )
        .configure_legend(
            labelColor="#64748B",
            titleColor="#0F172A",
            labelFont="Noto Sans KR",
            titleFont="Noto Sans KR",
        )
    )


def render_sidebar(books: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    categories = sorted(books["category_name"].dropna().unique().tolist())
    max_price = int(books["priceStandard"].max()) if not books.empty else 300_000
    max_price = max(max_price, 1)

    with st.sidebar:
        st.markdown("### :material/tune: 탐색 설정")
        st.caption("분석 화면에 적용됩니다.")

        all_category = st.toggle("모든 카테고리", value=True, key="all_category")
        if all_category:
            selected_categories = categories
        else:
            selected_categories = st.pills(
                "카테고리",
                options=categories,
                selection_mode="multi",
                default=categories[:1] if categories else None,
                width="stretch",
                key="selected_categories",
            ) or []

        price_range = st.slider(
            "가격대",
            min_value=0,
            max_value=max_price,
            value=(0, max_price),
            step=1_000,
            format="%d원",
            key="price_range",
        )
        min_rating = st.slider(
            "최소 평점",
            min_value=0.0,
            max_value=10.0,
            value=0.0,
            step=0.5,
            format="%.1f점",
            key="min_rating",
        )
        top_k = st.select_slider(
            "차트에 표시할 순위",
            options=list(range(3, 16)),
            value=8,
            key="top_k",
        )

        st.space("medium")
        st.badge("분석 데이터 준비됨", icon=":material/database:", color="blue")
        st.caption(f"총 {format_count(len(books))}개 도서 데이터")

    filtered = books[
        books["category_name"].isin(selected_categories)
        & books["priceStandard"].between(price_range[0], price_range[1])
        & (books["customerReviewRank"].fillna(0) >= min_rating)
    ].copy()
    return filtered, top_k


def render_header() -> None:
    with st.container(border=True):
        st.caption("LIBRARY INTELLIGENCE  /  CATALOG ANALYTICS")
        st.title("📊 도서 분석 대시보드")
        st.write("카탈로그 데이터를 한눈에 살펴보고 독서 트렌드를 발견해 보세요.")


def render_kpis(filtered: pd.DataFrame) -> None:
    if filtered.empty:
        values = [("도서", "0권"), ("작가", "0명"), ("출판사", "0곳"), ("평균 평점", "—")]
    else:
        values = [
            ("도서", f"{filtered['itemId'].nunique():,}권"),
            ("작가", f"{filtered['author'].nunique():,}명"),
            ("출판사", f"{filtered['publisher'].nunique():,}곳"),
            ("평균 평점", f"{filtered['customerReviewRank'].mean():.1f}점"),
        ]

    columns = st.columns(4, gap="small")
    for column, (label, value) in zip(columns, values):
        with column:
            st.metric(label, value, border=True)


def render_analysis_tabs(filtered: pd.DataFrame, top_k: int) -> None:
    price_summary = (
        filtered.groupby("category_name", as_index=False)["priceStandard"]
        .agg(평균="mean", 중앙값="median")
        .melt("category_name", var_name="통계", value_name="가격")
    )
    price_chart = build_chart(
        alt.Chart(price_summary)
        .mark_bar(size=18, cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("category_name:N", title="카테고리", sort="-y", axis=alt.Axis(labelAngle=-35)),
            y=alt.Y("가격:Q", title="가격 (원)", axis=alt.Axis(format=",")),
            xOffset=alt.XOffset("통계:N"),
            color=alt.Color(
                "통계:N",
                title=None,
                scale=alt.Scale(domain=["평균", "중앙값"], range=["#2563EB", "#0EA5E9"]),
            ),
            tooltip=[
                alt.Tooltip("category_name:N", title="카테고리"),
                alt.Tooltip("통계:N", title="구분"),
                alt.Tooltip("가격:Q", title="가격", format=",.0f"),
            ],
        )
    )

    author_counts = (
        filtered[filtered["author"].ne("")]["author"]
        .value_counts()
        .head(top_k)
        .sort_values()
        .rename_axis("작가")
        .reset_index(name="도서 수")
    )
    publisher_counts = (
        filtered[filtered["publisher"].ne("")]["publisher"]
        .value_counts()
        .head(top_k)
        .sort_values()
        .rename_axis("출판사")
        .reset_index(name="도서 수")
    )

    tab_price, tab_author, tab_publisher = st.tabs(
        [
            ":material/payments: 카테고리별 가격",
            ":material/person: 인기 작가",
            ":material/business: 주요 출판사",
        ]
    )
    with tab_price:
        with st.container(border=True):
            st.markdown("**카테고리별 평균·중앙값 가격**")
            st.caption("평균과 중앙값의 차이로 카테고리별 가격 분포를 비교합니다.")
            st.altair_chart(price_chart)

    with tab_author:
        with st.container(border=True):
            st.markdown(f"**도서가 많은 작가 Top {top_k}**")
            author_chart = build_chart(
                alt.Chart(author_counts)
                .mark_bar(cornerRadiusEnd=4)
                .encode(
                    x=alt.X("도서 수:Q", title="도서 수"),
                    y=alt.Y("작가:N", title=None, sort=None),
                    color=alt.Color(
                        "작가:N",
                        title="작가",
                        legend=None,
                        scale=alt.Scale(scheme="tableau20"),
                    ),
                    tooltip=[alt.Tooltip("작가:N"), alt.Tooltip("도서 수:Q")],
                )
            )
            st.altair_chart(author_chart)

    with tab_publisher:
        with st.container(border=True):
            st.markdown(f"**도서가 많은 출판사 Top {top_k}**")
            publisher_chart = build_chart(
                alt.Chart(publisher_counts)
                .mark_bar(cornerRadiusEnd=4)
                .encode(
                    x=alt.X("도서 수:Q", title="도서 수"),
                    y=alt.Y("출판사:N", title=None, sort=None),
                    color=alt.Color(
                        "출판사:N",
                        title="출판사",
                        legend=None,
                        scale=alt.Scale(scheme="set3"),
                    ),
                    tooltip=[alt.Tooltip("출판사:N"), alt.Tooltip("도서 수:Q")],
                )
            )
            st.altair_chart(publisher_chart)


def render_popular_books(filtered: pd.DataFrame) -> None:
    st.subheader("인기 도서")
    st.caption("판매지수와 평점을 기준으로 현재 필터에서 가장 주목받는 책입니다.")

    popular = filtered.sort_values(
        ["salesPoint", "customerReviewRank"], ascending=False
    ).head(6)

    if popular.empty:
        st.info("현재 필터에 맞는 인기 도서가 없습니다.", icon=":material/info:")
        return

    for row_start in range(0, len(popular), 3):
        row = popular.iloc[row_start : row_start + 3]
        columns = st.columns(len(row), gap="small")
        for column, (_, book) in zip(columns, row.iterrows()):
            with column:
                with st.container(border=True):
                    cover_url = safe_cover(book.get("cover"))
                    if cover_url:
                        st.image(cover_url, width=150)
                    else:
                        st.markdown(":material/menu_book:")
                    st.markdown(f"**{book['title'] or '제목 정보 없음'}**")
                    st.caption(book["author"] or "저자 정보 없음")
                    st.write(
                        f"{format_price(book['priceStandard'])} · "
                        f"평점 {format_rating(book['customerReviewRank'])}"
                    )
                    st.caption(f"판매지수 {book['salesPoint']:,.0f} · {book['category_name']}")
                    if isinstance(book.get("link"), str) and book["link"].startswith("http"):
                        st.link_button(
                            "알라딘에서 보기",
                            book["link"],
                            icon=":material/open_in_new:",
                        )


books = load_books()
filtered, top_k = render_sidebar(books)
render_header()

st.subheader("한눈에 보는 도서 카탈로그")
st.caption(f"현재 필터에 맞는 {format_count(len(filtered))}개 행을 기준으로 집계했습니다.")
render_kpis(filtered)

if filtered.empty:
    st.info(
        "조건에 맞는 도서가 없습니다. 사이드바에서 가격대나 최소 평점을 조금 넓혀 보세요.",
        icon=":material/info:",
    )
    st.stop()

render_analysis_tabs(filtered, top_k)
render_popular_books(filtered)
