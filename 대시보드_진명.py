import os
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import seaborn as sns
import streamlit as st
import base64
from pathlib import Path

st.markdown("""
<style>
/* 전체 배경: 책 종이색 + 분석 그래프 격자 */
.stApp {
    background-color: #f7f4ee;
    background-image:
        linear-gradient(rgba(37,  60, 90, 0.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(37, 60, 90, 0.04) 1px, transparent 1px);
    background-size: 32px 32px;
}

/* 메인 콘텐츠 카드 */
.block-container {
    max-width: 1200px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}

/* 사이드바 */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #eef6ff, #dcecff);
    border-right: 1px solid #c5d9ee;
}

[data-testid="stSidebar"] * {
    color: black;
}

/* 제목 */
h1 {
    color: #182b40;
    font-weight: 800;
    letter-spacing: -1px;
}

/* 지표 카드 */
[data-testid="stMetric"] {
    background: rgba(255, 255, 255, 0.85);
    border: 1px solid rgba(24, 43, 64, 0.1);
    border-radius: 14px;
    padding: 16px;
    box-shadow: 0 4px 14px rgba(24, 43, 64, 0.08);
}

/* 탭 */
button[data-baseweb="tab"] {
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

bg_path = Path(__file__).parent / "배경이미지" / "대시보드배경.png"

@st.cache_data
def load_background(path):
    return base64.b64encode(Path(path).read_bytes()).decode()
bg_base64 = load_background(str(bg_path))

st.markdown(
    f"""
    <style>
    .stApp {{
        background:
            linear-gradient(
                rgba(239, 246, 255, 0.72),
                rgba(239, 246, 255, 0.72)
            ),
            url("data:image/png;base64,{bg_base64}");

        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}

    .block-container {{
        padding-top: 2rem;
    }}
    </style>
    """,
    unsafe_allow_html=True
)

st.title("📚 분석 대시보드")


@st.cache_data
def load_books():
    return pd.read_csv('./정제데이터/books.csv')

books = load_books()

with st.sidebar:
    st.header("필터")

    categories = sorted(books["category_name"].dropna().unique().tolist())

    all_category = st.toggle("전체 카테고리",value=True)
    if all_category:
        category = categories
    else:
        category = st.pills(
            "카테고리 선택",
            options=categories,
            selection_mode="multi",
            default=None,
            width="stretch"
        )
    price = st.slider('가격대',0,300000,(0,300000))
    min_price, max_price= price
filtered = books[(books["category_name"].isin(category)) & (books["priceStandard"].between(min_price, max_price))]

c1,c2,c3,c4=st.columns(4)
c1.metric('도서수',f"{filtered['itemId'].nunique()}권")
c2.metric('작가수',f"{filtered['author'].nunique()}명")
c3.metric('출판사수',f"{filtered['publisher'].nunique()}")
c4.metric('평균 평점',f"{round(filtered['customerReviewRank'].mean(),1)}점")



k=st.selectbox('TOP-k', options=range(3, 16),index=7)
tab1, tab2, tab3 = st.tabs(["카테고리별 가격 평균-중앙값", "도서 많은 작가 Top k", "도서 많은 출판사 TOP k"])
with tab1:
    summary = (
    filtered.groupby("category_name")["priceStandard"]
    .agg(mean="mean", median="median")
    .reset_index()
    .melt(
        id_vars="category_name",
        var_name="stat",
        value_name="priceStandard"
    )
)

    st.plotly_chart(px.bar(
        summary,
        x="category_name",
        y="priceStandard",
        color="stat",
        barmode="group",
        labels={
            "category_name": "카테고리",
            "priceStandard": "가격",
            "stat": "통계값"
        },
        title="카테고리별 평균·중앙 가격"
    ))




with tab2:  
    count=filtered['author'].value_counts()[:k].reset_index()
    count = count.iloc[::-1]
    count['author']=count['author'].replace('김진우, 박종우, 장용익, 이인섭, 맹형규, 정재일, 한지우, 유태용','김진우 외 7명')
    st.plotly_chart(px.bar(count,x='count',y='author'))

with tab3:  
    count=filtered['publisher'].value_counts()[:k].reset_index()
    count = count.iloc[::-1]
    st.plotly_chart(px.bar(count,x='count',y='publisher'))







