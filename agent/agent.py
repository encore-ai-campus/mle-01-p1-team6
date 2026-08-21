from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv((BASE_DIR / "../.env").resolve())

#도구 위치에서 불러오기
from tools.vector_search import vector_search_descp

#환경 설정 가져오기
load_dotenv("../.env")

GPTmodel = ChatOpenAI(model="gpt-4o-mini", temperature=0)

book_tools = [vector_search_descp]

book_agent = create_agent(
    model=GPTmodel,
    tools=book_tools,
    system_prompt="""
    당신은 책 추천 에이전트입니다.

    반드시 검색 도구가 반환한 정보만 근거로 답변하세요.
    책을 추천할 때 각 책마다 출처를 함께 표시하세요.
    검색 도구가 반환하지 않은 정보나 출처는 임의로 생성하지 마세요."""
)


###테스트 코드입니다.
test_prompt = input("원하는 책을 고르시오")

#답을 받아오기
result = book_agent.invoke({
    "messages": [{
            "role": "user",
            "content": test_prompt
        }]
})

agent_result = result["messages"][-1].content
#+ 히스토리(단기기억)

###테스트 코드 실제로 에이전트가 모델을 호출했는지 확인
# for message in result["messages"]:
#     print(type(message).__name__)
#     print(message)
#     print("-" * 50)

#ai의 답변만 출력
print(agent_result)