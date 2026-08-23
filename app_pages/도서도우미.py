from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import streamlit as st

from utils.theme import apply_library_theme


apply_library_theme()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = PROJECT_ROOT / "agent"
ASSISTANT_AVATAR = PROJECT_ROOT / "assets" / "book-assistant-avatar.png"


@st.cache_resource(show_spinner=False)
def load_agent_runner():
    """agent/book_agent.py의 RAG를 질문 시점에 한 번만 초기화합니다."""
    agent_path = str(AGENT_DIR)
    if agent_path not in sys.path:
        sys.path.insert(0, agent_path)

    from book_agent import ask_book_agent_with_results, reset_book_memory

    return ask_book_agent_with_results, reset_book_memory


def initialize_state() -> None:
    st.session_state.setdefault(
        "book_agent_messages",
        [
            {
                "role": "assistant",
                "content": (
                    "안녕하세요. 도서 도우미 AI입니다.\n\n"
                    "읽고 싶은 분위기, 주제, 작가, 가격대처럼 자연스럽게 질문해 주세요. "
                    "도서 검색 RAG를 바탕으로 추천해 드릴게요."
                ),
                "books": [],
            }
        ],
    )
    st.session_state.setdefault("book_agent_thread_id", f"book-agent-{uuid4().hex}")


def render_book_cards(books: list[dict[str, Any]]) -> None:
    if not books:
        return

    st.markdown("#### 검색된 추천 도서")
    for start in range(0, len(books), 3):
        row = books[start : start + 3]
        columns = st.columns(len(row), gap="small")
        for column, book in zip(columns, row):
            with column:
                with st.container(border=True, height="stretch"):
                    cover_url = book.get("cover_url")
                    if isinstance(cover_url, str) and cover_url.strip():
                        st.image(cover_url, width=120)

                    st.markdown(f"**{book.get('title') or '제목 정보 없음'}**")
                    if book.get("author"):
                        st.caption(str(book["author"]))

                    metadata = []
                    if book.get("price") is not None:
                        metadata.append(f"{int(book['price']):,}원")
                    if book.get("rating") is not None:
                        metadata.append(f"평점 {book['rating']}")
                    if metadata:
                        st.caption(" · ".join(metadata))

                    if book.get("description"):
                        with st.expander("검색 근거"):
                            st.write(book["description"])


def reset_chat() -> None:
    old_thread_id = st.session_state.get("book_agent_thread_id")
    try:
        _, reset_memory = load_agent_runner()
        if old_thread_id:
            reset_memory(old_thread_id)
    except Exception:
        pass

    st.session_state.book_agent_messages = [
        {
            "role": "assistant",
            "content": "대화를 초기화했습니다. 새로운 책을 찾아볼까요?",
            "books": [],
        }
    ]
    st.session_state.book_agent_thread_id = f"book-agent-{uuid4().hex}"


initialize_state()

avatar_column, header_column, action_column = st.columns([1, 5, 1], vertical_alignment="bottom")
with avatar_column:
    if ASSISTANT_AVATAR.exists():
        st.image(str(ASSISTANT_AVATAR), width=92)
with header_column:
    st.caption("🤖 AGENT RAG  /  BOOK DISCOVERY")
    st.title("🤖 도서 도우미 AI")
    st.write("자연어 질문으로 원하는 책을 찾고, 검색 결과를 근거와 함께 확인해 보세요.")
with action_column:
    if st.button("새 대화", icon=":material/restart_alt:", width="stretch"):
        reset_chat()
        st.rerun()

st.badge("agent/book_agent.py 연결", icon=":material/auto_awesome:", color="blue")
st.caption("의미 기반 검색은 ChromaDB, 조건 검색과 표지 정보는 Agent의 Supabase 도구를 사용합니다.")

suggestion = None
if len(st.session_state.book_agent_messages) == 1:
    suggestion = st.pills(
        "추천 질문",
        [
            "몰입감 있는 추리소설 3권 추천해줘",
            "10,000원 이하 자기계발서",
            "따뜻한 분위기의 소설을 찾아줘",
        ],
        label_visibility="collapsed",
    )

for message in st.session_state.book_agent_messages:
    with st.chat_message(
        message["role"],
        avatar=str(ASSISTANT_AVATAR) if message["role"] == "assistant" and ASSISTANT_AVATAR.exists() else ":material/person:",
    ):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            render_book_cards(message.get("books", []))

question = st.chat_input(
    "예: 비 오는 날 읽기 좋은 잔잔한 소설 3권 추천해줘",
    key="book_agent_chat_input",
) or suggestion

if question:
    question = str(question).strip()
    if question:
        st.session_state.book_agent_messages.append(
            {"role": "user", "content": question, "books": []}
        )
        with st.chat_message("user", avatar=":material/person:"):
            st.markdown(question)

        with st.chat_message(
            "assistant",
            avatar=str(ASSISTANT_AVATAR) if ASSISTANT_AVATAR.exists() else ":material/auto_awesome:",
        ):
            try:
                with st.spinner("도서 데이터를 검색하고 있어요..."):
                    ask_agent, _ = load_agent_runner()
                    answer, recommended_books = ask_agent(
                        question,
                        st.session_state.book_agent_thread_id,
                    )
                st.markdown(answer)
                render_book_cards(recommended_books)
            except Exception as exc:  # noqa: BLE001
                answer = (
                    "도서 추천 연결 중 문제가 발생했습니다. `.env`의 OpenAI/Supabase "
                    "설정과 ChromaDB 상태를 확인해 주세요."
                )
                recommended_books = []
                st.error(answer, icon=":material/error:")
                with st.expander("오류 상세"):
                    st.code(str(exc))

        st.session_state.book_agent_messages.append(
            {
                "role": "assistant",
                "content": answer,
                "books": recommended_books,
            }
        )
