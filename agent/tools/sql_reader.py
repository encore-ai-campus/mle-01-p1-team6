#필요한 라이브러리와 도구 호출
from pathlib import Path
from langchain_core.tools import tool
import chromadb
from sentence_transformers import SentenceTransformer

from langchain.agents import create_agent

sql_agent = create_agent(model, [run_select], system_prompt=schema_prompt)


def called_tools(res):
    """에이전트 궤적에서 (도구 이름, 인자) 목록을 뽑는다 -- 무엇을 불렀는지 확인용."""
    return [(c['name'], c['args']) for m in res['messages']
            if getattr(m, 'tool_calls', None) for c in m.tool_calls]


def showsql(res):
    """에이전트가 만든 SQL 과 최종 답을 함께 보여 준다."""
    # 궤적에는 모델이 도구를 부른 기록이 남아 있습니다 -- 거기서 sql 인자를 꺼냅니다.
    for , args in called_tools(res):
        print('만든 SQL:', args['sql'])
        print('답      :', res['messages'][-1].text)


print('Text-to-SQL 에이전트 준비 완료')




sql_chain = 