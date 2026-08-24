# 도서 추천 Agent의 핵심 로직입니다.
# app홍기표.py는 이 파일의 ask_book_agent_with_results와
# reset_book_memory를 호출하므로 두 함수는 반드시 유지해야 합니다.
from pathlib import Path
from contextvars import ContextVar
import ast
import json
import os

import chromadb
from dotenv import load_dotenv

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from pydantic import BaseModel, Field

from db import create_supabase_client


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

ENV_PATH = PROJECT_ROOT / ".env"
CHROMA_DB_PATH = Path(
    os.getenv("CHROMA_DB_PATH", str(PROJECT_ROOT / "chroma_db"))
)

load_dotenv(ENV_PATH, override=False)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

if not OPENAI_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY가 없습니다. "
        ".env 파일을 확인하세요."
    )


GPTmodel = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    api_key=OPENAI_API_KEY,
)


embeddings = HuggingFaceEmbeddings(
    model_name="SamilPwC-AXNode-GenAI/PwC-Embedding_expr",
    encode_kwargs={
        "normalize_embeddings": True
    },
)


supabase = create_supabase_client()


chroma_client = chromadb.PersistentClient(
    path=str(CHROMA_DB_PATH)
)

book_collection = chroma_client.get_collection(
    name="book"
)


# 대화 기억
memory = InMemorySaver()


# thread_id별로 이미 추천한 책의 itemId를 저장합니다.
thread_recommended_ids: dict[str, set[str]] = {}


# 현재 질문에서 제외할 책 ID를 검색 함수와 공유합니다.
current_excluded_ids = ContextVar(
    "current_excluded_ids",
    default=set(),
)


def get_memory_config(thread_id: str):
    """대화 ID를 기준으로 Agent 기억 설정을 만듭니다."""
    return {
        "configurable": {
            "thread_id": thread_id
        }
    }


def reset_book_memory(thread_id: str):
    """대화 기억과 이전 추천 책 목록을 초기화합니다."""
    memory.delete_thread(thread_id)
    thread_recommended_ids.pop(thread_id, None)


def make_book_row(
    data: dict,
    *,
    cover_url=None,
    description=None,
    distance=None,
    chroma_id=None,
):
    """Supabase와 ChromaDB 결과를 동일한 도서 형식으로 변환합니다."""

    data = data or {}

    row = {
        "itemId": data.get("itemId"),
        "title": data.get("title"),
        "author": data.get("author"),
        "publisher": data.get("publisher"),
        "category_name": data.get("category_name"),
        "price": data.get("priceStandard"),
        "rating": data.get("customerReviewRank"),
        "pubDate": data.get("pubDate"),
        "cover_url": cover_url,
    }

    if data.get("description"):
        row["description"] = data["description"]

    if chroma_id is not None:
        row["chroma_id"] = chroma_id

    if description is not None:
        row["description"] = description

    if distance is not None:
        row["distance"] = distance

    return row


def get_cover_map(item_ids):
    """도서 ID 목록을 기준으로 Supabase에서 표지 URL을 가져옵니다."""

    if not item_ids:
        return {}

    unique_item_ids = list(dict.fromkeys(item_ids))

    response = (
        supabase
        .table("books")
        .select("itemId, cover")
        .in_("itemId", unique_item_ids)
        .execute()
    )

    return {
        str(book["itemId"]): book.get("cover")
        for book in response.data
        if book.get("itemId") is not None
    }


class VectorSearchInput(BaseModel):
    """의미 기반 검색 입력 형식입니다."""

    query: str = Field(
        description=(
            "책의 내용, 분위기, 주제, 특징, 취향 등을 "
            "표현한 자연어 검색 문장"
        )
    )

    k: int = Field(
        default=3,
        ge=1,
        le=20,
        description="사용자가 요청한 추천 책 개수"
    )


class SearchBookInput(BaseModel):
    """조건 검색 입력 형식입니다."""

    category_name: str | None = Field(
        default=None,
        description="책 카테고리"
    )

    author: str | None = Field(
        default=None,
        description="저자 이름"
    )

    min_price: int | None = Field(
        default=None,
        ge=0,
        description="최소 가격"
    )

    max_price: int | None = Field(
        default=None,
        ge=0,
        description="최대 가격"
    )

    min_rating: int | None = Field(
        default=None,
        ge=1,
        le=10,
        description="최소 평점"
    )

    max_rating: int | None = Field(
        default=None,
        ge=1,
        le=10,
        description="최대 평점"
    )

    k: int = Field(
        default=3,
        ge=1,
        le=20,
        description="사용자가 요청한 추천 책 개수"
    )


@tool(args_schema=VectorSearchInput)
def vector_search_descp(
    query: str,
    k: int = 3,
):
    """
    책의 내용, 분위기, 주제, 특징 등을 기준으로
    ChromaDB 의미 검색을 수행합니다.
    """

    excluded_ids = current_excluded_ids.get()

    # 이전 책을 제외하기 위해 k보다 많이 검색합니다.
    collection_count = book_collection.count()

    if collection_count == 0:
        return []

    candidate_k = min(
        k + len(excluded_ids),
        collection_count
    )

    query_embedding = embeddings.embed_query(query)

    results = book_collection.query(
        query_embeddings=[query_embedding],
        n_results=candidate_k,
        include=[
            "documents",
            "metadatas",
            "distances",
        ],
    )

    ids = results["ids"][0]
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    item_ids = [
        metadata.get("itemId")
        for metadata in metadatas
        if metadata.get("itemId") is not None
    ]

    cover_map = get_cover_map(item_ids)

    rows = []

    for book_id, document, metadata, distance in zip(
        ids,
        documents,
        metadatas,
        distances,
    ):
        item_id = metadata.get("itemId")

        # 이전에 추천한 책은 제외합니다.
        if item_id is not None:
            if str(item_id) in excluded_ids:
                continue

        row = make_book_row(
            metadata,
            cover_url=(
                cover_map.get(str(item_id))
                if item_id is not None
                else None
            ),
            description=document,
            distance=distance,
            chroma_id=book_id,
        )

        rows.append(row)

        if len(rows) >= k:
            break

    # 이번 검색에서 사용한 책도 중복 방지를 위해 저장합니다.
    for row in rows:
        item_id = row.get("itemId")

        if item_id is not None:
            excluded_ids.add(str(item_id))

    return rows


@tool(args_schema=SearchBookInput)
def search_book(
    category_name: str | None = None,
    author: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    min_rating: int | None = None,
    max_rating: int | None = None,
    k: int = 3,
):
    """
    가격, 평점, 작가(저자), 카테고리 등
    정확한 조건으로 Supabase에서 책을 검색합니다.
    """

    excluded_ids = current_excluded_ids.get()

    request = (
        supabase
        .table("books")
        .select(
            "itemId, "
            "title, "
            "author, "
            "publisher, "
            "category_name, "
            "priceStandard, "
            "customerReviewRank, "
            "pubDate, "
            "cover, "
            "description"
        )
    )

    if category_name is not None:
        request = request.eq(
            "category_name",
            category_name
        )

    if author and author.strip():
        request = request.ilike(
            "author",
            f"%{author.strip()}%"
        )

    if min_price is not None:
        request = request.gte(
            "priceStandard",
            min_price
        )

    if max_price is not None:
        request = request.lte(
            "priceStandard",
            max_price
        )

    if min_rating is not None:
        request = request.gte(
            "customerReviewRank",
            min_rating
        )

    if max_rating is not None:
        request = request.lte(
            "customerReviewRank",
            max_rating
        )

    # 이전 책이 있을 수 있으므로 더 많이 검색합니다.
    response = (
        request
        .limit(k + len(excluded_ids))
        .execute()
    )

    rows = []

    for book in response.data:
        item_id = book.get("itemId")

        # 이전에 추천한 책은 제외합니다.
        if item_id is not None:
            if str(item_id) in excluded_ids:
                continue

        rows.append(
            make_book_row(
                book,
                cover_url=book.get("cover"),
            )
        )

        if len(rows) >= k:
            break

    # 이번 검색 결과도 추천 목록에 저장합니다.
    for row in rows:
        item_id = row.get("itemId")

        if item_id is not None:
            excluded_ids.add(str(item_id))

    return rows


tools = [
    search_book,
    vector_search_descp,
]


SYSTEM_PROMPT = """
너는 사용자의 취향과 조건에 맞는 책을 추천하는
도서 추천 에이전트다.

[대화 기억]
- 이전 대화를 참고해서 후속 질문을 이해한다.
- "그중에서", "그 책", "그 작가(저자)" 같은 표현은
  이전 대화의 내용을 참고한다.

[도구 선택]
- 가격, 평점, 작가(저자), 카테고리 → search_book
- 내용, 분위기, 주제, 특징, 취향 → vector_search_descp
- 두 조건이 섞여 있으면 필요한 도구를 사용한다.
- 작가(저자)의 권수를 물어 볼 시 ->search_book 

[추천 개수]
- 사용자가 개수를 말하면 그 숫자를 k로 사용한다.
- 개수를 말하지 않으면 k=3이다.

[중복 방지]
- 반드시 검색 도구에서 반환된 책만 추천한다.
- 같은 itemId는 같은 책이다.
- 이전에 추천한 책은 다시 추천하지 않는다.
- 사용자가 "다른 책", "새로운 책"을 요청하면
  이전 추천 책을 제외한 검색 결과만 사용한다.

[표지 이미지]
- cover_url은 도구의 값을 그대로 사용한다.
- URL을 임의로 만들거나 수정하지 않는다.
- cover_url이 없으면 만들어내지 않는다.

[최종 답변]
가능한 경우 다음 정보를 보여준다.

- 책 제목
- 저자
- 가격
- 평점
- 추천 이유
"""


agent = create_agent(
    model=GPTmodel,
    tools=tools,
    system_prompt=SYSTEM_PROMPT,
    checkpointer=memory,
)


def run_agent(
    question: str,
    thread_id: str = "cli-session",
):
    """질문을 LangChain Agent에 전달하고 답변을 생성합니다."""

    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": question,
                }
            ]
        },
        config=get_memory_config(thread_id),
    )

    answer = result["messages"][-1].content

    if not isinstance(answer, str):
        answer = str(answer)

    return answer, result


def _parse_book_rows(value):
    """검색 결과를 도서 정보 리스트로 변환합니다."""

    if value is None:
        return []

    if isinstance(value, list):
        rows = []

        for item in value:
            rows.extend(
                _parse_book_rows(item)
            )

        return rows

    if isinstance(value, dict):
        if "cover_url" in value:
            return [value]

        rows = []

        for key in (
            "rows",
            "text",
            "content",
        ):
            if key in value:
                rows.extend(
                    _parse_book_rows(value[key])
                )

        return rows

    if isinstance(value, str):
        text = value.strip()

        if not text:
            return []

        for parser in (
            json.loads,
            ast.literal_eval,
        ):
            try:
                parsed = parser(text)
            except (
                ValueError,
                SyntaxError,
                TypeError,
            ):
                continue

            return _parse_book_rows(parsed)

    return []


def extract_book_rows(result):
    """
    현재 질문에서 검색된 책만 추출합니다.
    이전 대화의 ToolMessage는 제외합니다.
    """

    if not isinstance(result, dict):
        return []

    messages = result.get(
        "messages",
        []
    )

    start_index = 0

    for index in range(
        len(messages) - 1,
        -1,
        -1,
    ):
        if getattr(
            messages[index],
            "type",
            ""
        ) == "human":
            start_index = index + 1
            break

    current_messages = messages[start_index:]

    rows = []
    seen = set()

    for message in current_messages:
        if getattr(
            message,
            "type",
            ""
        ) != "tool":
            continue

        tool_rows = _parse_book_rows(
            getattr(
                message,
                "content",
                None
            )
        )

        for row in tool_rows:
            cover_url = row.get("cover_url")

            # 표지가 없는 책은 화면 카드에서 제외합니다.
            if not isinstance(
                cover_url,
                str
            ):
                continue

            if not cover_url.strip():
                continue

            identity = (
                row.get("itemId")
                or row.get("title")
                or cover_url
            )

            if identity in seen:
                continue

            seen.add(identity)
            rows.append(row)

    return rows


def ask_book_agent_with_results(
    question: str,
    thread_id: str,
):
    """
    질문을 처리하고 답변과 추천 도서 목록을 반환합니다.

    같은 thread_id에서 이전에 추천한 책은
    다음 질문의 검색 결과에서 제외합니다.
    """

    excluded_ids = thread_recommended_ids.setdefault(
        thread_id,
        set(),
    )

    token = current_excluded_ids.set(
        excluded_ids
    )

    try:
        answer, result = run_agent(
            question,
            thread_id,
        )

        books = extract_book_rows(result)

        # 화면에 표시된 책도 추천 목록에 저장합니다.
        for book in books:
            item_id = book.get("itemId")

            if item_id is not None:
                excluded_ids.add(str(item_id))

        return answer, books

    finally:
        current_excluded_ids.reset(token)