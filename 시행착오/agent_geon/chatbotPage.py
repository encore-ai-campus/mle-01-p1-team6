import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage

from agent import book_agent


# 페이지 기본 설정
st.set_page_config(
    page_title="책 추천 챗봇",
    page_icon="📚",
    layout="centered",
)

st.title("📚 책 추천 챗봇")
st.caption("조건 검색과 책 소개 기반 의미 검색을 이용해 책을 찾아드립니다.")


# 대화 화면용 히스토리
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# 에이전트에 전달할 단기 기억
# 사용자 질문 + 최종 AI 답변만 저장
if "agent_memory" not in st.session_state:
    st.session_state.agent_memory = []


# 대화 초기화
if st.sidebar.button("대화 초기화"):
    st.session_state.chat_history = []
    st.session_state.agent_memory = []
    st.rerun()


# 이전 대화 출력
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# 사용자 입력
user_input_prompt = st.chat_input(
    "원하는 책이나 조건을 입력하세요."
)


if user_input_prompt:

    # 사용자 메시지 화면 출력
    with st.chat_message("user"):
        st.markdown(user_input_prompt)

    # 화면 표시용 히스토리에 사용자 질문 저장
    st.session_state.chat_history.append({
        "role": "user",
        "content": user_input_prompt,
    })

    # LangChain 메시지 생성
    user_message = HumanMessage(
        content=user_input_prompt
    )

    # 에이전트 호출
    with st.chat_message("assistant"):
        with st.spinner("책을 검색하고 있습니다..."):
            try:
                result = book_agent.invoke({
                    "messages": (
                        st.session_state.agent_memory
                        + [user_message]
                    )
                })

                # 최종 AI 답변만 추출
                agent_result = result["messages"][-1].content

            except Exception as e:
                agent_result = f"검색 중 오류가 발생했습니다: {e}"

        st.markdown(agent_result)


    # 정상 답변인 경우 대화 기억에 저장
    if not agent_result.startswith("검색 중 오류가 발생했습니다:"):
        st.session_state.agent_memory.append(
            user_message
        )

        st.session_state.agent_memory.append(
            AIMessage(content=agent_result)
        )


    # 화면 표시용 히스토리에 AI 답변 저장
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": agent_result,
    })