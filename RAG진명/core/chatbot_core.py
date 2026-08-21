# [제공 코드]
"""chatbot_core: '기존 챗봇 시스템' (LangChain 대화형 챗봇).

지난 단원(LangChain LCEL·Memory)에서 만든 챗봇이라고 생각하세요.
이 단원에서는 이 함수를 Streamlit 채팅 UI에 **연결**하기만 하면 됩니다.

이 모듈은 **실제 OpenAI 호출만** 합니다. 키가 없을 때 대신 도는 가짜 응답 경로는 없습니다.
키가 없으면 `stream_reply` 가 안내와 함께 `RuntimeError` 를 냅니다
(앱은 그 전에 `core.keys.require_openai_key_or_stop()` 으로 화면에 안내를 띄우고 멈춥니다).
"""

import os
import re
from pathlib import Path
from typing import Iterator
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel, Field
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from langchain.agents.structured_output import ProviderStrategy
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.prompts import ChatPromptTemplate
from typing import Literal, Optional
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from dotenv import load_dotenv
from core.keys import MISSING_KEY_MESSAGE, load_key


APP_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_DIR = APP_DIR.parent
load_dotenv(WORKSPACE_DIR / ".env")
load_key()
from core.supabase_search import fetch_cover_map, search_supabase


model = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

system_prompt="""너는 친절한 도서관 사서이다.
        반드시 검색 결과에 근거해서만 답변하라.
        도서 검색 질문에서 검색 결과가 없으면 '검색 결과를 찾지 못했습니다'라고 답하라.
        도서와 관계없는 일반 대화에는 검색 결과가 없다는 말을 하지 말고 자연스럽게 대답하라.
        사용자가 요청한 책의 개수만큼 추천하라.
예를 들어:
- 한 권, 하나, 1개 → 정확히 1권
- 두 권, 2개 → 정확히 2권
- 다섯 권, 5개 → 정확히 5권
검색 결과가 요청 개수보다 적으면 실제 검색된 책만 추천하고,
없는 책을 만들어내지 마라.책 제목, 작가, 가격을 함께 보여줘라. 그리고 추천한 이유도 같이 알려줘
사용자가 추천 개수를 말하지 않으면 검색된 책을 최대 5권 모두 추천하라.
검색 결과가 5개라면 반드시 5개를 각각 번호를 붙여 설명하라.
검색 결과가 요청 개수보다 적을 때만 실제 결과 수만큼 추천하라.
검색 결과를 임의로 제외하거나 책을 만들어내지 마라.
책과 관계없는 일반 대화는 검색 결과가 없어도 자연스럽게 대답하라."""

class Filter(BaseModel):
    query: str = Field(
        description="책의 내용이나 특징을 검색하기 위한 자연어 검색 문장"
    )
    k: int = Field(default=5, ge=1,
            description="검색할 책의 개수. 기본값은 5")
    author: str | None = Field( default=None,
        description="작가 이름. 조건이 없으면 NULL값으로 무조건 해줘")
    
    min_price: int | None = Field( default=None, ge=0,
        description="최소 가격. '10000원 이상'이면 10000,숫자가 없으면 NULL값으로 무조건 해줘")
    
    max_price: int | None = Field(default=None,ge=0,
        description="최대 가격. '20000원 이하'이면 20000,숫자가 없으면 NULL값으로 무조건 해줘")
    
    min_rating: int | None = Field(default=None,ge=1,le=10,
        description="최소 평점. '평점 7 이상'이면 7,점수가 없으면 NULL값으로 무조건 해줘")
    
    max_rating: int | None = Field(default=None,ge=1,le=10,
        description="최대 평점. '평점 8 이하'이면 8,점수가 없으면 NULL값으로 무조건 해줘")

filter_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """
        사용자의 질문에서 도서 검색 조건을 추출하라.

        개수 규칙:
        - '하나', '한 권', '1개'라고 하면 k=1
        - '두 권', '2개'라고 하면 k=2
        - 개수가 없으면 k=5

        가격, 평점, 작가도 질문에 명시된 경우에만 추출하라.
        언급되지 않은 조건은 모두 None으로 설정하라.
        """
        ),
        ("human", "{query}")
    ])

filter_chain = filter_prompt | model.with_structured_output(Filter)
def filterd(query):
    """질문으로 메타데이터 필터 추출 질문에 조건이 없다 싶으면 무조건 뽑지마. 그리고 마음대로 무작위로 조건을 넣지마

    Args:
        query (_type_): 질문
    """
    print("FILTER INPUT:", repr(query))
    filters = extract_filters(query)
    print("FILTER OUTPUT:", filters)
    data = filters.model_dump(exclude_none=True)
    equal_fields = ["author"]
    range_fields = {
        "min_price": ("priceStandard", "$gte"),
        "max_price": ("priceStandard", "$lte"),
        "min_rating": ("customerReviewRank", "$gte"),
        "max_rating": ("customerReviewRank", "$lte"),
    }

    conditions = []
    for key, value in data.items():
        if key in equal_fields:
            conditions.append({
                key: {
                    "$eq": value
                }
            })
        elif key in range_fields:
            field, operator = range_fields[key]
            conditions.append({
                field: {
                    operator: value
                }
            })
    if not conditions:
        return {}, filters.k
    if len(conditions) == 1:
        return conditions[0], filters.k
    return {"$and": conditions}, filters.k


def extract_filters(query):
    return filter_chain.invoke({
        "query": query
    })



store = Chroma(persist_directory=str(WORKSPACE_DIR / "chroma_db"),
                    collection_name='book',
                    embedding_function=HuggingFaceEmbeddings(
    model_name="SamilPwC-AXNode-GenAI/PwC-Embedding_expr",
    encode_kwargs={"normalize_embeddings": True}))

#책 추천시 카테고리만 다른 동일 도서면 하나만 사용하기 위한 함수들
def _book_key(doc):
    """카테고리만 다른 동일 도서를 같은 책으로 판단한다."""
    metadata = doc.metadata
    item_id = (
        metadata.get("itemId")
        or metadata.get("item_id")
        or metadata.get("ItemId")
    )
    if item_id not in (None, ""):
        return ("item", str(item_id))

    values = [
        metadata.get("title"),
        metadata.get("author"),
        metadata.get("priceStandard", metadata.get("price_standard")),
        metadata.get(
            "customerReviewRank",
            metadata.get("customer_review_rank"),
        ),
    ]
    if any(value not in (None, "") for value in values):
        normalized = tuple(
            re.sub(r"[\W_]+", "", str(value)).casefold()
            for value in values
        )
        return ("book", normalized)

    return ("document", id(doc))


def _deduplicate_books(docs, limit):
    unique_docs = []
    seen = set()

    for doc in docs:
        key = _book_key(doc)
        if key in seen:
            continue
        seen.add(key)
        unique_docs.append(doc)
        if len(unique_docs) == limit:
            break

    return unique_docs


def search_chroma(query):
    """책이나 문서의 내용에 대한 질문을 검색한다.
    의미 기반 검색이나 문서 근거가 필요한 질문에 사용한다.
    단순한 수치 계산, 집계, 정렬, 조건 조회는 관계형 DB 도구를 사용한다.
    근거 문서를 찾지 못했다면 못찾았다고 말한다. 조건은 
    Args:
        query (질문): _description_
    """
    print("SEARCH QUERY:", repr(query))
    where, k = filterd(query)

    print("where:", where)

    candidate_k = max(k * 3, k)

    docs_without_filter = store.similarity_search(query, k=candidate_k)
    print("필터 없는 결과:", len(docs_without_filter))

    search_kwargs = {"k": candidate_k}

    if where:
        search_kwargs["filter"] = where

    retriever = store.as_retriever(
        search_kwargs=search_kwargs
    )

    candidates = retriever.invoke(query)
    docs = _deduplicate_books(candidates, k)
    print("중복 제거 후 결과:", len(docs))

    return docs

def search_books(query):
    """이 함수는 Chroma에서 책을 의미 검색한 뒤, 검색된 책의 표지만 Supabase에서 추가로 가져오는 함수입니다.."""
    docs = search_chroma(query)
    if not docs:
        return docs

    item_ids = [doc.metadata.get("itemId")for doc in docs]

    try:
        cover_map = fetch_cover_map(item_ids)
    except RuntimeError as exc:
        print(f"표지 조회를 건너뜁니다: {exc}")
        return docs

    for doc in docs:
        item_id = (
            doc.metadata.get("itemId"))
        cover = cover_map.get(str(item_id))
        if cover:
            doc.metadata["cover"] = cover

    return docs



def is_live() -> bool:
    """실제 OpenAI 연동이 가능한 상태인지(키가 설정됐는지) 알려줍니다.

    UI 가 '키 없음'을 감지해 안내를 띄울 때 씁니다. 답변 경로를 바꾸는 스위치가 아닙니다.
    """
    load_key()
    return bool(os.getenv("OPENAI_API_KEY"))

def format_docs(docs):
    if not docs:
        return "검색 결과가 없습니다."

    return "\n\n".join(
        f"""
        책 내용:
        {doc.page_content}

        책 메타데이터:
        {doc.metadata}
        """
        for doc in docs
    )

def retrieve(inputs):
    """검색 결과와 사용자 질문을 LangChain프롬프트에 넣을 형태로 형태로 정리하는 함수
    """
    docs = inputs.get("docs")
    is_book_query = inputs.get("is_book_query", True)

    if docs is None:
        docs = search_books(inputs["query"]) if is_book_query else []

    if is_book_query:
        context = format_docs(docs)
    else:
        context = "이 질문은 도서 검색이 아닌 일반 대화입니다. 검색 결과를 언급하지 마세요."

    return {
        "history": inputs.get("history", []),
        "query": inputs["query"],
        "context": context,
        "result_count": len(docs),
    }


def build_chain():
    """프롬프트 · 모델 · 출력 파서를 이어 붙인 체인을 만들어 돌려줍니다.

    만드는 데 시간이 드는 준비물이라 **매 메시지마다 새로 만들 필요가 없습니다**.
    이 함수는 캐싱하지 않습니다. 캐싱은 이 함수를 부르는 쪽이 정합니다
    (Streamlit 앱이라면 `@st.cache_resource`, 일반 스크립트라면 변수에 담아 두기).

    Raises:
        RuntimeError: OPENAI_API_KEY 가 없을 때.
    """
    if not is_live():
        raise RuntimeError(MISSING_KEY_MESSAGE)

    
    prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                MessagesPlaceholder("history"),
                (
        "human",
        """
        질문:
        {query}

        검색 결과 개수:
        {result_count}

        검색 결과:
        {context}
        """
    ),
            ]
        )
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
    search=RunnableLambda(retrieve)
    return search | prompt | model | StrOutputParser()
    

def stream_reply(
    message: str,
    history: list[dict] | None = None,
    chain=None,
    docs=None,
    is_book_query=True,
) -> Iterator[str]:
    """사용자 메시지에 대한 답변을 토큰(문자열 조각) 단위로 스트리밍합니다.

    Args:
        message: 이번 사용자 입력.
        history: 이전 대화 [{"role": "user"/"assistant", "content": ...}, ...].
        chain: 미리 만들어 둔 체인. 주지 않으면 이 호출에서 새로 만듭니다.
            같은 체인을 계속 쓰려면 앱에서 한 번 만들어 넘기세요.
    Yields:
        답변 텍스트 조각. `st.write_stream()` 에 그대로 넘길 수 있습니다.
    Raises:
        RuntimeError: OPENAI_API_KEY 가 없을 때(가짜 응답으로 대신 돌지 않습니다).
    """
    chain = chain or build_chain()

    past = [
        (m["role"], m["content"])
        for m in (history or [])
    ]

    for token in chain.stream({
        "history": past,
        "query": message,
        "docs": docs,
        "is_book_query": is_book_query,
    }):
        yield token


def reply(message: str, history: list[dict] | None = None) -> str:
    """스트리밍이 필요 없을 때 쓰는 전체 답변 문자열 버전."""
    return "".join(stream_reply(message, history))
