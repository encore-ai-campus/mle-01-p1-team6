from __future__ import annotations

import sys
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

import streamlit as st

from utils.theme import apply_library_theme


apply_library_theme()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = PROJECT_ROOT / "agent"
ASSISTANT_AVATAR = PROJECT_ROOT / "assets" / "book-assistant-avatar.png"


def load_deployment_secrets() -> None:
    """Streamlit Cloud secrets를 Agent가 읽는 환경변수로 연결합니다."""
    for key in ("OPENAI_API_KEY", "SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY"):
        try:
            if key in st.secrets:
                value = str(st.secrets[key]).strip()
                if value:
                    os.environ[key] = value
        except Exception:
            # 로컬에서 secrets.toml이 없어도 대시보드와 검색은 사용할 수 있습니다.
            continue


@st.cache_resource(show_spinner=False)
def prepare_chroma_db(source_path: str) -> str:
    """한글 프로젝트 경로를 피하도록 ChromaDB를 ASCII 임시 경로에 준비합니다."""
    source = Path(source_path)
    runtime_path = Path(tempfile.gettempdir()) / "book_agent_chroma_db"
    runtime_path.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, runtime_path, dirs_exist_ok=True)
    return str(runtime_path)


@st.cache_resource(show_spinner=False)
def load_agent_runner():
    """agent/book_agent.py의 RAG를 질문 시점에 한 번만 초기화합니다."""
    load_deployment_secrets()
    os.environ["CHROMA_DB_PATH"] = prepare_chroma_db(str(PROJECT_ROOT / "chroma_db"))
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

    st.html('<div class="section-row"><div><h2>검색된 추천 도서</h2><p>답변의 근거가 된 책을 함께 확인해 보세요.</p></div><span class="book-pill">GROUNDED</span></div>')
    for start in range(0, len(books), 3):
        row = books[start : start + 3]
        columns = st.columns(len(row), gap="small", vertical_alignment="top")
        for rank, (column, book) in enumerate(zip(columns, row), start=start + 1):
            with column:
                with st.container(border=True, height="stretch", gap="small"):
                    cover_url = book.get("cover_url")
                    if isinstance(cover_url, str) and cover_url.strip():
                        with st.container(horizontal_alignment="center", gap="small"):
                            st.image(cover_url, width=145)

                    st.badge(f"추천 {rank}위", icon=":material/auto_awesome:", color="orange")
                    st.html(
                        f'<div class="book-card-title">{book.get("title") or "제목 정보 없음"}</div>'
                        f'<div class="book-card-meta">{book.get("author") or "저자 정보 없음"}</div>'
                    )
                    if book.get("author"):
                        st.caption(str(book["author"]))

                    metadata = []
                    if book.get("price") is not None:
                        metadata.append(f"{int(book['price']):,}원")
                    if book.get("rating") is not None:
                        metadata.append(f"평점 {book['rating']}")
                    if book.get("category_name"):
                        metadata.append(str(book["category_name"]))
                    if metadata:
                        st.caption(" · ".join(metadata))

                    with st.expander("왜 추천했나요?", icon=":material/lightbulb:"):
                        evidence = []
                        if book.get("category_name"):
                            evidence.append(f"{book['category_name']} 카테고리 조건")
                        if book.get("author"):
                            evidence.append(f"저자: {book['author']}")
                        if book.get("rating") is not None:
                            evidence.append(f"평점: {book['rating']}")

                        if evidence:
                            st.write(" · ".join(evidence))
                        st.caption("사용자의 질문과 검색 결과를 바탕으로 선택된 도서입니다.")

                        if book.get("description"):
                            st.caption("검색된 책 소개")
                            description = str(book["description"])
                            st.write(description[:500] + ("…" if len(description) > 500 else ""))


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

header_column, action_column = st.columns([5, 1], vertical_alignment="center")
with header_column:
    st.html(
        """
        <div class="assistant-hero">
          <div class="assistant-hero-inner">
            <div>
              <div class="assistant-label">Agent RAG / book discovery</div>
              <div class="assistant-title">책을 고르는 대화를 시작해 보세요.</div>
              <p class="assistant-copy">자연어 질문으로 원하는 책을 찾고, 검색 결과를 근거와 함께 확인할 수 있습니다.</p>
              <div class="status-line">도서 인덱스와 추천 에이전트 연결됨</div>
            </div>
          </div>
        </div>
        """
    )
with action_column:
    if st.button("새 대화", icon=":material/restart_alt:", width="stretch"):
        reset_chat()
        st.rerun()

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
