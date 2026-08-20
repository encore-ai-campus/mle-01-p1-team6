import os
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import seaborn as sns
import streamlit as st



st.title('분석 대시보드')

books=pd.read_csv('./도서 데이터/api_books.csv')
books=books.drop(columns=['pubDate','isbn','isbn13','bestSellerRank','link','fetched_at'])

with st.sidebar:
    st.header("필터")
    category = st.multiselect(
        "카테고리", books["category_name"].unique(), default=list(books["category_name"].unique())
    )
filtered = books[books["category_name"].isin(category)]
st.caption("▼ 왼쪽 사이드바에서 종을 고르면 아래 표가 바뀝니다")
st.write("선택된 카테고리 수:", len(filtered))

standard = filtered.groupby("category_name")["priceStandard"].mean().reset_index()
# color 에 범주 열을 주면 종마다 색이 갈리고 범례가 생긴다(범례를 눌러 켜고 끌 수 있다)
fig = px.bar(standard, x="category_name", y="priceStandard", color="category_name", title="카테고리별 평균 가격(원)")
st.plotly_chart(fig, width="stretch")












