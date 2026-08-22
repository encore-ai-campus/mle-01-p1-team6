# 도서 추천 Agent

Streamlit으로 실행하는 도서 추천 챗봇입니다.

## 실행 방법

프로젝트의 `.env` 파일과 `chroma_db` 폴더가 준비되어 있어야 합니다.

```powershell
cd C:\Users\Playdata\Desktop\mle-01-p1-team6\agent
uv run streamlit run .\app.py
```

## 파일별 역할

### `app.py` — 화면 실행

Streamlit 화면을 실행합니다. 사용자의 질문을 입력받고, `book_agent.py`의 Agent를 호출합니다. 답변과 추천 도서 카드를 화면에 표시하며 대화 초기화도 담당합니다.

### `book_agent.py` — Agent 및 추천 함수

도서 추천의 핵심 로직입니다.

- `ask_book_agent_with_results`: 질문을 받아 추천 답변과 도서 목록을 반환합니다.
- `reset_book_memory`: 현재 대화의 기억을 초기화합니다.
- `vector_search_descp`: ChromaDB에서 책 설명을 의미 검색합니다.
- `search_book`: 조건에 맞는 도서를 검색합니다.
- `create_agent`: 도서 검색 도구를 사용하는 LangChain Agent를 생성합니다.

ChromaDB의 벡터 검색과 Supabase의 도서 정보를 함께 사용합니다.

### `db.py` — Supabase 연결

`.env`에서 Supabase 접속 정보를 읽고 Supabase 클라이언트를 생성합니다. `book_agent.py`가 도서 정보와 표지 URL을 조회할 때 사용합니다.

## 환경 변수

프로젝트 루트의 `.env`에 OpenAI와 Supabase 접속 정보를 설정해야 합니다. `.env` 파일은 GitHub에 올리지 않습니다.
