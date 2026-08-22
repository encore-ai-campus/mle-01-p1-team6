# Streamlit 화면입니다. Agent 로직은 book_agent홍기표.py에 두고,
# 이 파일은 입력·대화 기억·책 카드 표시만 담당합니다.
from __future__ import annotations

from functools import lru_cache
from typing import Any
from uuid import uuid4

try:
    import streamlit as st
except (ModuleNotFoundError, PermissionError):  # 테스트 환경에서 UI 의존성이 없어도 헬퍼는 검증 가능
    st = None


def normalize_question(question: str) -> str:
    return question.strip()


def has_cover_url(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def initial_messages() -> list[dict[str, Any]]:
    return [{"role": "assistant", "content": "원하는 책을 자연어로 말씀해 주세요."}]


@lru_cache(maxsize=1)
def _load_agent_runner():
    # Agent 모듈은 첫 질문 때 한 번만 불러와 초기화 비용을 줄입니다.
    from book_agent홍기표 import ask_book_agent_with_results

    return ask_book_agent_with_results


def run_agent_query(question: str, thread_id: str, runner=None):
    """현재 Streamlit 대화 ID를 사용해 기억형 Agent를 호출한다."""

    if runner is None:
        runner = _load_agent_runner()
    return runner(question, thread_id)


def _reset_agent_memory(thread_id: str) -> None:
    # 화면의 대화 초기화 버튼과 Agent의 기억을 함께 초기화합니다.
    from book_agent홍기표 import reset_book_memory

    reset_book_memory(thread_id)


def chunk_books(books: list[dict[str, Any]], size: int = 3) -> list[list[dict[str, Any]]]:
    # 책 카드를 한 줄에 최대 3개씩 배치합니다.
    return [books[start:start + size] for start in range(0, len(books), size)]


def render_book_cards(books: list[dict[str, Any]]) -> None:
    # Agent가 검색한 책을 표지·제목·저자·가격·평점 카드로 표시합니다.
    if st is None or not books:
        return

    for row_books in chunk_books(books):
        columns = st.columns(len(row_books))
        for column, book in zip(columns, row_books):
            with column:
                if has_cover_url(book.get("cover_url")):
                    st.image(book["cover_url"], use_container_width=True)
                st.markdown(f"**{book.get('title') or '제목 없음'}**")
                if book.get("author"):
                    st.caption(f"저자: {book['author']}")
                if book.get("price") is not None:
                    st.caption(f"가격: {book['price']}")
                if book.get("rating") is not None:
                    st.caption(f"평점: {book['rating']}")


def render_messages(messages: list[dict[str, Any]]) -> None:
    # 세션에 저장된 이전 대화와 책 카드를 다시 그립니다.
    if st is None:
        return

    for message in messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            # if message["role"] == "assistant":
            #     render_book_cards(message.get("books", []))


def main() -> None:
    # Streamlit 앱의 시작점입니다.
    if st is None:
        raise RuntimeError("Streamlit이 설치되어 있지 않습니다. `uv sync` 후 다시 실행하세요.")

    st.set_page_config(page_title="도서 추천 에이전트", page_icon="📚")
    st.title("📚 도서 추천 에이전트")
    st.caption("내용, 분위기, 작가, 가격, 평점 등의 조건을 자연어로 입력해 보세요.")

    if "messages" not in st.session_state:
        st.session_state.messages = initial_messages()
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = f"streamlit-{uuid4().hex}"

    with st.sidebar:
        st.subheader("대화 관리")
        if st.button("대화 초기화", use_container_width=True):
            try:
                _reset_agent_memory(st.session_state.thread_id)
            except Exception as exc:
                st.warning(f"서버 대화 기억을 초기화하지 못했습니다: {exc}")
            st.session_state.messages = initial_messages()
            st.session_state.thread_id = f"streamlit-{uuid4().hex}"
            st.rerun()

    render_messages(st.session_state.messages)

    question = st.chat_input("예: 잔잔하고 따뜻한 소설 3권 추천해줘")
    if question is None:
        return

    question = normalize_question(question)
    if not question:
        st.warning("질문을 입력해 주세요.")
        return

    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("책을 찾고 있습니다..."):
            try:
                answer, books = run_agent_query(
                    question,
                    st.session_state.thread_id,
                )
            except Exception as exc:
                answer = f"도서 추천 중 오류가 발생했습니다: {exc}"
                books = []
                st.error(answer)
            else:
                st.markdown(answer)
                # render_book_cards(books)

    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "books": books}
    )


if __name__ == "__main__":
    main()
