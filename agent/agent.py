from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage,AIMessage
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

#환경 설정 가져오기
load_dotenv((BASE_DIR / "../.env").resolve())

#도구 위치에서 불러오기
from tools.vector_search import vector_search_descp #유사도 검색
from tools.sql_reader import search_books #sql 실행

GPTmodel = ChatOpenAI(model="gpt-4o-mini", temperature=0)

#도구 목록 : 유사도 검색, sql 실행
book_tools = [vector_search_descp,search_books]

#에이전트 입력 프롬프트
agent_prompt="""
    당신은 책 검색 및 추천 에이전트입니다.

    사용자의 요청에 따라 적절한 검색 도구를 선택하세요.

    - 카테고리, 가격, 평점, 순위, 제목, 저자, 출판사, 출간일 등
    명확한 조건이 있으면 search_books 도구를 사용하세요.

    - 책의 내용, 분위기, 주제, 특징처럼 의미 기반 검색이 필요하면
    vector_search_descp 도구를 사용하세요.

    - 조건 검색과 의미 검색이 모두 필요한 요청이면
    필요한 도구를 함께 사용하세요.

    반드시 검색 도구가 반환한 정보만 근거로 답변하세요.
    검색 결과에 없는 책이나 정보는 임의로 생성하지 마세요.

    책을 추천할 때는 제목, 저자와 함께
    검색 결과에 포함된 출처 정보(itemId 또는 link 등)를 표시하세요.

    조건에 맞는 책을 찾지 못한 경우
    임의로 추천하지 말고 조건에 맞는 결과가 없다고 답변하세요."""


#에이전트 제작
book_agent = create_agent(
    model=GPTmodel,
    tools=book_tools,
    system_prompt=agent_prompt
)

# #에이전트 기억 저장소 생성
# agent_memory = []


# #반복 내부에서 기억 구현(이 부분은 streamlit방법으로 바꿔야 됨)
# while True:
#     #입력 받기
#     user_input_prompt = input("책 챗봇입니다. 무엇을 도와드릴까요?(종료는 0): ")

#     if user_input_prompt=='0' :
#         print('종료되었습니다.')

#         #현재까지의 기록 보기
#         print(agent_memory)
#         break

#     #현재 사용자 질문을 기존 대화에 추가
#     agent_memory.append(
#         HumanMessage(content=user_input_prompt)
#     )

#     #에이전트에 묻기(+메모리)
#     result = book_agent.invoke({
#         "messages": agent_memory
#     })

#     #답변
#     agent_result = result["messages"][-1].content

#     #ai의 답변만 출력
#     print(agent_result)

#     #전체 대화 저장
#     agent_memory = result["messages"]

def run_cli():

    #에이전트 단기 기억
    agent_memory = []
    while True:
        #입력 받기
        user_input_prompt = input(
            "책 챗봇입니다. 무엇을 도와드릴까요?(종료는 0): "
        )

        if user_input_prompt == "0":
            print("종료되었습니다.")
            break

        #현재 사용자 메시지
        user_message = HumanMessage(
            content=user_input_prompt
        )

        #답을 받아오기
        result = book_agent.invoke({
            "messages": agent_memory + [
                user_message
            ]
        })

        #최종 AI 답변
        agent_result = result["messages"][-1].content

        #사용자 질문 대답 기억
        agent_memory = result["messages"]

        #ai의 답변만 출력
        print(agent_result)


#챗봇 사용을 위해
if __name__ == "__main__":
    run_cli()