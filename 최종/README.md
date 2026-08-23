# 도서 도우미 AI - 배포용

도서 분석 대시보드, Agent RAG 도서 도우미, 도서 검색을 포함한 Streamlit 앱입니다.

## 로컬 실행

```powershell
cd 최종
uv run streamlit run streamlit_app.py
```

## Streamlit Community Cloud 배포

1. 저장소의 `최종/streamlit_app.py`를 앱 파일로 선택합니다.
2. 의존성 파일은 `최종/requirements.txt`를 사용합니다.
3. 앱 설정의 Secrets에 다음 값을 등록합니다.

```toml
OPENAI_API_KEY = "..."
SUPABASE_URL = "..."
SUPABASE_PUBLISHABLE_KEY = "..."
```

`.env`와 `secrets.toml`은 배포 폴더에 넣지 않습니다.

배포 폴더 이름은 한글 `최종`으로 유지하면서, 도서도우미 AI의 ChromaDB는 실행 시 ASCII 임시 경로에서 읽도록 처리되어 HNSW 경로 오류를 피합니다.
