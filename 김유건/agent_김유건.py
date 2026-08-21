# [제공 코드] OpenAI 클라이언트 준비 — 이 셀을 먼저 실행하세요.
# .env 파일에 OPENAI_API_KEY 를 넣어 두면 아래 한 줄이 그것을 읽어 연결합니다.
#   참고: https://developers.openai.com/api/docs/guides/text
import os

from dotenv import load_dotenv
from openai import OpenAI
from pathlib import Path
from langchain_core.tools import tool
import chromadb
from sentence_transformers import SentenceTransformer
from pydantic import BaseModel, Field
model = SentenceTransformer(
    "SamilPwC-AXNode-GenAI/PwC-Embedding_expr"
)

# .env 로드
load_dotenv()

# 환경 변수에서 가져오거나, 로드 실패 시 직접 입력한 키 사용
api_key = os.getenv("OPENAI_API_KEY") or "your-actual-api-key-here"

client = OpenAI(api_key=api_key, max_retries=8)
print('연결 준비 완료 —', '키 확인됨' if os.getenv('OPENAI_API_KEY') else '키가 없습니다(.env 를 확인하세요)')

messages = [{'role': 'system', 'content': '너는 알라딘의 베스트셀러를 추천하는 친절한 말투의 도우미야.'}]

while True:
    user_input = input("사용자: ")
    if user_input.lower() in ['end', 'exit', '종료']:
        break
    messages.append({'role': 'user', 'content': user_input})
    resp = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=messages,
        temperature=0,
        )
    bot_reply = resp.choices[0].message.content
    print(f"{bot_reply}\n")

    # 사용자 질문 추가
    messages.append({'role': 'assistant', 'content': bot_reply})