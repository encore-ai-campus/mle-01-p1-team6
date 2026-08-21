"""알라딘 책 추천 에이전트 Streamlit 앱.

실행:
    streamlit run app.py
"""

import os

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

st.set_page_config(
    page_title="책갈피 AI · 도서 추천",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)


SYSTEM_PROMPT = """당신은 알라딘 도서 데이터를 바탕으로 책을 추천하는 친절한 한국어 큐레이터입니다.
사용자의 취향, 읽는 목적, 난이도, 분량, 장르를 파악해 구체적인 책을 추천하세요.
각 추천에는 책 제목과 저자, 추천 이유를 포함하고, 정보가 확실하지 않으면 추측하지 말고
확인할 수 없는 정보라고 밝혀 주세요. 답변은 읽기 쉬운 한국어로 작성하세요."""


def get_api_key() -> str:
    """환경변수 또는 Streamlit secrets에서 API 키를 읽습니다."""
    try:
        secret_key = st.secrets.get("OPENAI_API_KEY", "")
    except (FileNotFoundError, KeyError):
        secret_key = ""
    return str(secret_key or os.getenv("OPENAI_API_KEY", "")).strip()


def init_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]


def ask_agent(prompt: str, model: str, api_key: str) -> str:
    client = OpenAI(api_key=api_key, max_retries=8)
    response = client.chat.completions.create(
        model=model,
        messages=st.session_state.messages,
        temperature=0.2,
    )
    return response.choices[0].message.content or "추천 결과를 받지 못했습니다."


def reset_chat() -> None:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]


init_state()
api_key = get_api_key()

st.markdown(
    """
    <style>
    .hero { padding: 1.5rem 0 .75rem; }
    .hero h1 { letter-spacing: -.04em; margin-bottom: .25rem; }
    .hero p { color: #667085; font-size: 1.05rem; }
    [data-testid="stSidebar"] { border-right: 1px solid #eaecf0; }
    </style>
    <div class="hero">
      <h1>📚 책갈피 AI</h1>
      <p>당신의 다음 책을 함께 고르는 개인 맞춤형 도서 큐레이터</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.subheader("추천 설정")
    model = st.selectbox("사용할 모델", ["gpt-4o-mini", "gpt-4o"], index=0)
    st.caption("대화가 길어질수록 앞선 대화의 맥락을 함께 참고합니다.")
    if st.button("새 대화 시작", use_container_width=True):
        reset_chat()
        st.rerun()
    st.divider()
    if api_key:
        st.success("OpenAI API 연결 준비 완료")
    else:
        st.warning("OPENAI_API_KEY가 없습니다.")
        st.caption("프로젝트의 .env 파일에 OPENAI_API_KEY를 설정해 주세요.")
    st.divider()
    st.caption("예시 질문")
    examples = [
        "퇴근 후 가볍게 읽을 소설 추천해줘",
        "AI 입문자가 읽기 좋은 책 3권",
        "여행의 설렘을 느낄 수 있는 에세이",
    ]
    for example in examples:
        if st.button(example, use_container_width=True):
            st.session_state.pending_prompt = example
            st.rerun()

for message in st.session_state.messages:
    if message["role"] != "system":
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

pending_prompt = st.session_state.pop("pending_prompt", None)
prompt = st.chat_input("어떤 책을 찾고 있나요?") or pending_prompt

if prompt:
    if not api_key:
        st.error("OpenAI API 키가 설정되지 않았습니다. 사이드바 안내를 확인해 주세요.")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("취향에 맞는 책을 고르는 중..."):
                try:
                    answer = ask_agent(prompt, model, api_key)
                    st.markdown(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                except Exception as exc:
                    st.error(f"응답을 가져오지 못했습니다: {exc}")
                    st.session_state.messages.pop()

