# [제공 코드]
"""core: 이 단원에서 '기존 시스템'으로 제공되는 백엔드 모듈 모음.

지난 단원(RAG·LangChain·에이전트)에서 이미 만든 것으로 간주하는 코드입니다.
이 단원의 목표는 이 코드를 **다시 만드는 것이 아니라 Streamlit UI에 연결**하는 것이므로,
여기 있는 함수를 import 해서 그대로 사용하세요.

- chatbot_core : LangChain 대화형 챗봇 (스트리밍 지원: 실제 OpenAI 호출만)
- rag_core     : LangChain RAG (검색 기반 답변 + 출처: 실제 OpenAI 호출만)
- keys         : .streamlit/secrets.toml 로드 + OpenAI 키 확인 게이트 (키 없으면 안내 후 정지)
- data_loader  : 대시보드용 데이터 로더 (캐싱)
- fonts        : matplotlib 한글 폰트 설정
"""
