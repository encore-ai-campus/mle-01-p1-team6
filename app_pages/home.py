from __future__ import annotations

import streamlit as st

from utils.theme import apply_library_theme


apply_library_theme()


with st.container(border=True):
    st.caption("📚 LIBRARY INTELLIGENCE  /  BOOK DISCOVERY")
    st.title("도서관을 더 똑똑하게 이용하는 방법")
    st.write(
        "도서 데이터 분석부터 AI 맞춤 추천, 상세 도서 검색까지 한곳에서 이용할 수 있는 "
        "스마트 도서관 서비스입니다."
    )


st.write("")
st.subheader("무엇을 할 수 있나요?")

feature_columns = st.columns(3, gap="small")
features = [
    (
        "📊",
        "도서 분석 대시보드",
        "전체 도서 수, 작가·출판사 순위, 가격 분포와 인기 도서를 한눈에 확인합니다.",
    ),
    (
        "🤖",
        "도서 도우미 AI",
        "읽고 싶은 분위기나 조건을 자연어로 질문하면 어울리는 책을 추천받습니다.",
    ),
    (
        "🔎",
        "도서 검색",
        "제목, 작가, 출판사, 책 소개를 검색하고 알라딘에서 자세한 정보를 확인합니다.",
    ),
]

for column, (icon, title, description) in zip(feature_columns, features):
    with column:
        with st.container(border=True, height="stretch"):
            st.markdown(f"### {icon} {title}")
            st.write(description)


st.write("")
with st.container(border=True):
    st.markdown("### 이용 순서")
    steps = st.columns(3, gap="medium")
    for step, (number, title, description) in zip(
        steps,
        [
            ("01", "둘러보기", "대시보드에서 현재 도서 카탈로그의 흐름을 확인합니다."),
            ("02", "질문하기", "도서 도우미 AI에게 취향과 상황을 편하게 이야기합니다."),
            ("03", "찾아보기", "검색 결과를 비교하고 마음에 드는 책의 상세 페이지로 이동합니다."),
        ],
    ):
        with step:
            st.markdown(f"**{number}  {title}**")
            st.caption(description)


st.info(
    "왼쪽 사이드바에서 원하는 서비스를 선택해 시작해 보세요. "
    "처음이라면 대시보드에서 인기 도서를 둘러본 뒤 AI에게 추천을 요청해 보세요.",
    icon=":material/lightbulb:",
)
