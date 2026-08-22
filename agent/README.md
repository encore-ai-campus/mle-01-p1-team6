# 도서 추천 Agent

Streamlit으로 실행하는 도서 추천 챗봇입니다.

## 실행 방법

프로젝트의 `.env` 파일과 `chroma_db` 폴더가 준비되어 있어야 합니다.

```powershell
cd C:\Users\Playdata\Desktop\mle-01-p1-team6\agent
uv run streamlit run .\app.py
```

## 함수 설명

### app.py

#### `normalize_question`
사용자가 입력한 질문의 앞뒤 공백을 제거합니다.

#### `has_cover_url`
도서 표지 URL이 실제로 존재하는지 확인합니다.

#### `initial_messages`
챗봇을 처음 실행했을 때 표시할 기본 안내 메시지를 반환합니다.

#### `_load_agent_runner`
`book_agent.py`의 도서 추천 함수를 불러옵니다. 한 번 불러온 Agent는 다시 불러오지 않고 재사용합니다.

#### `run_agent_query`
사용자의 질문과 대화 ID를 Agent에 전달하고 추천 답변과 도서 목록을 받습니다.

#### `_reset_agent_memory`
현재 대화의 기억을 초기화합니다.

#### `chunk_books`
추천 도서 목록을 한 줄에 표시할 개수만큼 나눕니다.

#### `render_book_cards`
추천 도서의 표지, 제목, 저자, 가격, 평점을 화면에 카드 형태로 표시합니다.

#### `render_messages`
이전 대화 내용을 Streamlit 채팅 화면에 표시합니다.

#### `main`
Streamlit 앱을 실행하는 메인 함수입니다. 질문 입력, 답변 출력, 대화 초기화 등을 처리합니다.


### book_agent.py

#### `get_memory_config`
대화 ID를 기준으로 Agent가 이전 대화를 기억할 수 있도록 설정 정보를 만듭니다.

#### `reset_book_memory`
특정 대화 ID에 저장된 대화 기억을 삭제합니다.

#### `make_book_row`
ChromaDB와 Supabase에서 가져온 도서 정보를 하나의 일정한 형식으로 변환합니다.

#### `get_cover_map`
도서 ID를 기준으로 Supabase에서 책 표지 URL을 조회합니다.

#### `vector_search_descp`
ChromaDB에서 책 설명의 의미를 검색해 질문과 관련된 도서를 찾습니다.

#### `search_book`
작가, 가격, 평점, 제목 등의 조건을 기준으로 Supabase에서 도서를 검색합니다.

#### `run_agent`
사용자의 질문을 LangChain Agent에 전달하고 Agent의 답변을 생성합니다.

#### `_parse_book_rows`
Agent 검색 결과에 포함된 도서 정보를 파싱해 리스트 형태로 변환합니다.

#### `extract_book_rows`
Agent 실행 결과에서 추천 도서 정보만 추출합니다.

#### `ask_book_agent_with_results`
외부에서 사용하는 도서 추천 함수입니다. 사용자의 질문을 처리한 뒤 추천 답변과 도서 목록을 반환합니다.

#### `create_agent`
LangChain에서 제공하는 Agent 생성 함수입니다. 등록된 도서 검색 도구를 사용해 질문에 답변하도록 Agent를 구성합니다.


### db.py

#### `get_settings`
`.env` 파일에서 `SUPABASE_URL`과 `SUPABASE_PUBLISHABLE_KEY`를 읽어옵니다.

#### `create_supabase_client`
Supabase 접속 정보를 이용해 데이터베이스 클라이언트를 생성합니다.


### `db.py` — Supabase 연결

`.env`에서 Supabase 접속 정보를 읽고 Supabase 클라이언트를 생성합니다. `book_agent.py`가 도서 정보와 표지 URL을 조회할 때 사용합니다.

## 환경 변수

프로젝트 루트의 `.env`에 OpenAI와 Supabase 접속 정보를 설정해야 합니다. `.env` 파일은 GitHub에 올리지 않습니다.
