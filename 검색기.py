import pandas as pd
import streamlit as st

df = pd.read_csv("./도서 데이터/api_books.csv")

st.title("📚 도서 검색기")





# 검색창
keyword = st.text_input("책 제목 또는 저자를 검색하세요")
sort_col, category_col = st.columns(2)
sort_option = sort_col.selectbox(
    "정렬",
    [
        "가나다순",
        "카테고리별 랭크순",
        "카테고리별 가나다순",
        "가격순 오름차순",
        "가격순 내림차순",
        "평점순"
    ]
)

filtered = category_col.selectbox('카테고리', ['전체', '건강/취미', '경제경영', '과학', '사회과학', '소설/시/희곡', '어린이', '에세이', '여행', '역사',
    '예술/대중문화', '요리/살림', '인문학', '자기계발', '청소년', '컴퓨터/모바일'])





# 1. 검색
if filtered == "전체":
    # 전체를 선택하면 모든 행을 통과시키는 조건을 만든다.
    category_mask = pd.Series(True, index=df.index)
else:
    category_mask = df["category_name"] == filtered

if keyword.strip():
    keyword_mask = (
        df["title"].str.contains(keyword, case=False, na=False)
        | df["author"].str.contains(keyword, case=False, na=False)
    )
    result = df[category_mask & keyword_mask]
else:
    result = df[category_mask]

# 2. 정렬
if sort_option == "가나다순":
    result = result.sort_values("title")
elif sort_option == "카테고리별 랭크순":
    result = result.sort_values(["category_name", "rank_in_category"])
elif sort_option == "카테고리별 가나다순":
    result = result.sort_values(["category_name", "title"])
elif sort_option == "가격순 오름차순":
    result = result.sort_values("priceStandard")
elif sort_option == "가격순 내림차순":
    result = result.sort_values("priceStandard",ascending=False)
elif sort_option == "평점순":
    result = result.sort_values("customerReviewRank", ascending=False)

# 페이지 설정
page_size = 20
total_books = len(result)
total_pages = max(1, (total_books + page_size - 1) // page_size)

# 검색어나 정렬 방식이 바뀌면 1페이지로 이동
view_key = (keyword, filtered, sort_option)
if st.session_state.get("last_view_key") != view_key:
    st.session_state.page = 1
    st.session_state.last_view_key = view_key

st.session_state.page = min(st.session_state.get("page", 1), total_pages)

page_labels = [f"{page}페이지" for page in range(1, total_pages + 1)]
selected_page = st.selectbox(
    "페이지",
    page_labels,
    index=st.session_state.page - 1,
)
st.session_state.page = page_labels.index(selected_page) + 1

st.write(f"검색 결과 {total_books}권 · {st.session_state.page}/{total_pages}페이지")

# 현재 페이지에 해당하는 책만 출력
start = (st.session_state.page - 1) * page_size
visible_books = result.iloc[start:start + page_size]


for _, book in visible_books.iterrows():

    col1, col2 = st.columns([1, 5])

    with col1:
        st.image(book["cover"], width=120)

    with col2:
        st.subheader(book["title"])
        st.write(f'저자: {book["author"]}')
        st.write(f'가격: {book["priceStandard"]:,}원')
        st.write(f'카테고리: {book["category_name"]}')
        st.write(f'{book['category_name']}: {book["rank_in_category"]}위')

    st.divider()


# 페이지 이동 버튼
if total_pages > 1:
    previous_col, next_col = st.columns(2)

    with previous_col:
        if st.button("이전 페이지", disabled=st.session_state.page == 1):
            st.session_state.page -= 1
            st.rerun()

    with next_col:
        if st.button("다음 페이지", disabled=st.session_state.page == total_pages):
            st.session_state.page += 1
            st.rerun()




