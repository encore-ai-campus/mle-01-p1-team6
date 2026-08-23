# [제공 코드]
"""keys : OpenAI API 키 확인 게이트.

이 단원의 챗봇·RAG 앱은 **실제 OpenAI 호출만** 합니다. 가짜 응답으로 대신 도는 우회로는 없습니다.
키가 없으면 화면에 안내를 띄우고 그 자리에서 멈춥니다(`st.error` + `st.stop`).

키는 Streamlit 표준 방식인 **`.streamlit/secrets.toml`** 에 둡니다.

    .streamlit/secrets.toml
    OPENAI_API_KEY = "sk-..."

앱에서 쓰는 법 : LLM/RAG 를 호출하기 전에 한 줄

    from core.keys import require_openai_key_or_stop
    require_openai_key_or_stop()

`st.set_page_config` 를 쓰는 앱이라면 **그 다음에** 호출하세요
(Streamlit 은 set_page_config 보다 먼저 다른 요소를 그리면 오류를 냅니다).
"""

import os
import tomllib
from pathlib import Path

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

def _find_secrets() -> Path | None:
    """`.streamlit/secrets.toml` 을 이 파일 위쪽으로 올라가며 찾습니다.

    core/ 가 단원 폴더에 있을 때도, 배포용으로 앱 폴더 안에 복사돼 있을 때도
    같은 코드가 동작하도록 **가장 가까운 것부터** 찾습니다.
    """
    for folder in Path(__file__).resolve().parents:
        candidate = folder / ".streamlit" / "secrets.toml"
        if candidate.exists():
            return candidate
    return None

MISSING_KEY_MESSAGE = (
    "이 앱은 실제 OpenAI 호출이 필요합니다. OPENAI_API_KEY 를 찾지 못했습니다.\n\n"
    "1) 이 단원 폴더에서  cp .streamlit/secrets.toml.example .streamlit/secrets.toml\n"
    "2) 그 파일을 열어 본인 키를 채우세요 (https://platform.openai.com/api-keys)\n"
    "3) 앱을 다시 실행하세요 (uv run streamlit run ...)"
)


def _from_st_secrets() -> str | None:
    """`st.secrets` 에서 키를 읽습니다.

    secrets 파일이 아예 없으면 `st.secrets` 는 **키 조회 시점에 예외**를 냅니다
    (`"KEY" in st.secrets` 같은 확인조차 예외를 냅니다). 그래서 감싸서 처리합니다.
    """
    try:
        return st.secrets["OPENAI_API_KEY"]
    except (StreamlitSecretNotFoundError, KeyError):
        return None


def _from_unit_folder() -> str | None:
    """단원 폴더의 `.streamlit/secrets.toml` 을 절대경로로 직접 읽습니다.

    `st.secrets` 는 **앱을 실행한 폴더(현재 작업 디렉터리)** 기준으로 파일을 찾습니다.
    이 자료는 단원 폴더에서 실행할 수도, 실습자료 루트에서 실행할 수도 있어
    (`uv run streamlit run day23_.../교안_01_기초UI/01_시작하기.py`) 후자에서는 못 찾습니다.
    어느 폴더에서 실행하든 같게 동작하도록 둔 보완 경로입니다.
    """
    path = _find_secrets()
    if path is None:
        return None
    with path.open("rb") as f:
        return tomllib.load(f).get("OPENAI_API_KEY")


def load_key() -> None:
    """키를 찾아 환경변수에 넣습니다.

    LangChain(`ChatOpenAI`·`OpenAIEmbeddings`)은 `OPENAI_API_KEY` **환경변수**를 읽으므로,
    secrets 에서 읽은 값을 환경변수로 옮겨 줘야 그대로 동작합니다.
    이미 설정된 환경변수는 덮어쓰지 않습니다(터미널에서 준 값이 우선).
    """
    if os.getenv("OPENAI_API_KEY"):
        return
    key = _from_st_secrets() or _from_unit_folder()
    if key:
        os.environ["OPENAI_API_KEY"] = key


def has_openai_key() -> bool:
    """OpenAI 키가 준비됐는지 알려줍니다."""
    load_key()
    return bool(os.getenv("OPENAI_API_KEY"))


def require_openai_key_or_stop() -> None:
    """키가 없으면 안내를 띄우고 앱을 멈춥니다. 가짜 응답으로 대신 돌지 않습니다."""
    if not has_openai_key():
        st.error(MISSING_KEY_MESSAGE)
        st.stop()
