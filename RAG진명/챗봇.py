import os
import sys
from pathlib import Path

import streamlit as st


os.environ.setdefault("ARROW_DEFAULT_MEMORY_POOL", "system")

st.set_page_config(
    page_title="책담 | AI 도서관 사서",
    page_icon=":material/local_library:",
    layout="centered",
    initial_sidebar_state="expanded",
)


PROJECT_ROOT = next(
    (path for path in Path(__file__).resolve().parents if (path / "core").is_dir()),
    Path(__file__).resolve().parent,
)
sys.path.insert(0, str(PROJECT_ROOT))

from core import chatbot_core
from core.keys import require_openai_key_or_stop


require_openai_key_or_stop()


@st.cache_resource
def get_chain():
    """앱이 실행되는 동안 재사용할 LangChain 체인을 만든다."""
    return chatbot_core.build_chain()


chain = get_chain()


def is_book_search_request(text):
    book_keywords = [
        "책", "도서", "소설", "에세이", "작가", "독서", "읽을"
    ]
    request_keywords = [
        "추천", "검색", "찾아줘", "찾아", "골라줘", "소개"
    ]

    return (
        any(keyword in text for keyword in book_keywords)
        and any(keyword in text for keyword in request_keywords)
    )


def clear_chat():
    st.session_state.messages = []


if "messages" not in st.session_state:
    st.session_state.messages = []


with st.sidebar:
    st.markdown(":material/local_library: **책담**")
    st.caption("당신의 다음 책을 함께 찾는 AI 사서")
    st.space("small")

    if st.button(
        "새 대화",
        icon=":material/add:",
        type="primary",
        width="stretch",
        on_click=clear_chat,
    ):
        st.rerun()

    st.space("medium")
    st.markdown("#### 책담 사용법")
    st.caption("책 추천, 작가 검색, 가격·평점 조건을 편하게 말해보세요.")
    st.caption("예: 1만원 이하의 잔잔한 소설 한 권 추천해줘")
    st.space("medium")
    st.badge("AI 사서 온라인", icon=":material/check_circle:", color="green")


with st.container(horizontal=True, horizontal_alignment="distribute"):
    st.markdown(":material/local_library:")
    st.caption("오늘의 서가")

st.title("책과 대화하는 시간")
st.caption("취향을 말해주면, 책담이 어울리는 책을 찾아드릴게요.")


for message in st.session_state.messages:
    avatar = (
        ":material/person:"
        if message["role"] == "user"
        else ":material/auto_awesome:"
    )
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])


prompt = None

if not st.session_state.messages:
    with st.container(border=True):
        st.markdown("### 조용한 서가에서, 어떤 책을 찾고 있나요?")
        st.caption(
            "분위기, 장르, 작가, 가격, 평점처럼 떠오르는 단서만 말해도 괜찮아요."
        )

    st.caption("이렇게 시작해보세요")
    with st.container(horizontal=True):
        quick_prompts = [
            "잔잔한 느낌의 책 추천해줘",
            "영화 관련 책 하나 추천해줘",
            "1만원 이하 책 3권 추천해줘",
        ]
        for index, quick_prompt in enumerate(quick_prompts):
            if st.button(
                quick_prompt,
                key=f"quick_prompt_{index}",
                icon=":material/auto_stories:",
            ):
                prompt = quick_prompt


typed_prompt = st.chat_input(
    "책, 작가, 분위기를 자유롭게 입력해보세요",
    key="book_chat_input",
    submit_mode="disable",
)
if typed_prompt:
    prompt = typed_prompt


if prompt:
    st.session_state.messages.append({
        "role": "user",
        "content": prompt,
    })

    with st.chat_message("user", avatar=":material/person:"):
        st.markdown(prompt)

    is_book_query = is_book_search_request(prompt)
    docs = chatbot_core.search_books(prompt) if is_book_query else []

    with st.chat_message("assistant", avatar=":material/auto_awesome:"):
        answer = st.write_stream(
            chatbot_core.stream_reply(
                prompt,
                st.session_state.messages[:-1],
                chain=chain,
                docs=docs,
                is_book_query=is_book_query,
            )
        )

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
    })
