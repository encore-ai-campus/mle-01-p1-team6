from pathlib import Path
import ast
import json

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
CHROMA_DB_PATH = PROJECT_ROOT / "chroma_db"

load_dotenv(ENV_PATH, override=True)


GPTmodel = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
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


memory = InMemorySaver()


def get_memory_config(thread_id: str):
    return {
        "configurable": {
            "thread_id": thread_id
        }
    }


def reset_book_memory(thread_id: str):
    """해당 대화방의 단기기억 삭제"""
    memory.delete_thread(thread_id)



def make_book_row(
    data: dict,
    *,
    cover_url=None,
    description=None,
    distance=None,
    chroma_id=None,
):
    """
    Supabase / ChromaDB 검색 결과를
    Agent가 사용하기 좋은 동일한 형태로 바꾼다.
    """

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


    # Chroma 검색에서만 필요한 값
    if chroma_id is not None:
        row["chroma_id"] = chroma_id

    if description is not None:
        row["description"] = description

    if distance is not None:
        row["distance"] = distance


    return row


def get_cover_map(item_ids):
    """
    itemId 목록을 받아서
    Supabase에서 실제 cover URL을 가져온다.
    """

    if not item_ids:
        return {}


    # 중복 itemId 제거
    unique_item_ids = list(
        dict.fromkeys(item_ids)
    )


    response = (
        supabase
        .table("books")
        .select("itemId, cover")
        .in_(
            "itemId",
            unique_item_ids
        )
        .execute()
    )


    return {
        str(book["itemId"]): book.get("cover")
        for book in response.data
        if book.get("itemId") is not None
    }


class VectorSearchInput(BaseModel):

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
        description=(
            "사용자가 요청한 추천 책 개수. "
            "개수를 말하지 않으면 3"
        )
    )


class SearchBookInput(BaseModel):

    category_name: str | None = Field(
        default=None,
        description="책 카테고리"
    )

    author: str | None = Field(
        default=None,
        description="작가 이름"
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
        description=(
            "사용자가 요청한 추천 책 개수. "
            "개수를 말하지 않으면 3"
        )
    )



@tool(args_schema=VectorSearchInput)
def vector_search_descp(
    query: str,
    k: int = 3,
):
    """
    내용, 분위기, 주제, 특징, 취향처럼
    의미 기반 검색이 필요한 경우 사용한다.
    """

    # 질문 임베딩
    query_embedding = embeddings.embed_query(
        query
    )


    # 벡터 검색
    results = book_collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
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


    # Chroma 결과에서 itemId 추출
    item_ids = [
        metadata.get("itemId")
        for metadata in metadatas
        if metadata.get("itemId") is not None
    ]


    # Supabase에서 cover URL 가져오기
    cover_map = get_cover_map(
        item_ids
    )


    rows = []


    for book_id, document, metadata, distance in zip(
        ids,
        documents,
        metadatas,
        distances,
    ):

        item_id = metadata.get("itemId")


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
    가격, 평점, 작가, 카테고리처럼
    정확한 조건으로 검색할 때 사용한다.
    """

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
            "cover"
        )
    )


    if category_name is not None:
        request = request.eq(
            "category_name",
            category_name
        )


    if author is not None:
        request = request.eq(
            "author",
            author
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


    response = (
        request
        .limit(k)
        .execute()
    )


    return [
        make_book_row(
            book,
            cover_url=book.get("cover"),
        )
        for book in response.data
    ]


tools = [
    search_book,
    vector_search_descp,
]


SYSTEM_PROMPT = """
너는 사용자의 취향과 조건에 맞는 책을 추천하는
도서 추천 에이전트다.

[대화 기억]
- 이전 대화를 참고해서 후속 질문을 이해한다.
- "그중에서", "그 책", "그 작가" 같은 표현은
  이전 대화의 내용을 참고한다.

[도구 선택]
- 가격, 평점, 작가, 카테고리 → search_book
- 내용, 분위기, 주제, 특징, 취향 → vector_search_descp
- 두 조건이 섞여 있으면 필요한 도구를 사용한다.

[추천 개수]
- 사용자가 개수를 말하면 그 숫자를 k로 사용한다.
- 개수를 말하지 않으면 k=3이다.

[검색 결과]
- 반드시 도구에서 검색된 책만 추천한다.
- 검색되지 않은 책이나 정보를 만들지 않는다.
- 같은 itemId는 같은 책이다.
- 같은 책을 중복 추천하지 않는다.

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
- cover_url
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
    """
    모든 Agent 실행은 이 함수 하나를 통해 처리한다.
    """

    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": question,
                }
            ]
        },

        config=get_memory_config(
            thread_id
        ),
    )


    answer = result[
        "messages"
    ][-1].content


    if not isinstance(
        answer,
        str
    ):
        answer = str(answer)


    return answer, result


def ask_book_agent(
    question: str,
    thread_id: str = "cli-session",
) -> str:

    answer, _ = run_agent(
        question,
        thread_id,
    )

    return answer


def _parse_book_rows(value):
    """
    ToolMessage 내부의 list / dict / 문자열을
    책 정보 리스트로 변환한다.
    """

    if value is None:
        return []


    # list
    if isinstance(value, list):

        rows = []

        for item in value:
            rows.extend(
                _parse_book_rows(item)
            )

        return rows


    if isinstance(value, dict):

        # 실제 책 한 권
        if "cover_url" in value:
            return [value]


        rows = []

        # ToolMessage content block 처리
        for key in (
            "rows",
            "text",
            "content",
        ):

            if key in value:

                rows.extend(
                    _parse_book_rows(
                        value[key]
                    )
                )


        return rows


    # 문자열
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
                json.JSONDecodeError,
            ):
                continue


            return _parse_book_rows(
                parsed
            )


    return []


def extract_book_rows(result):
    """
    현재 질문에서 Tool이 검색한 책만 가져온다.

    단기기억 때문에 이전 ToolMessage들도 result에 들어갈 수 있으므로
    가장 최근 HumanMessage 이후의 ToolMessage만 확인한다.
    """

    if not isinstance(
        result,
        dict
    ):
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

    current_messages = messages[
        start_index:
    ]


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

            cover_url = row.get(
                "cover_url"
            )


            # Streamlit 카드에는
            # 실제 cover가 있는 책만 사용
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
    return

    answer:
        LLM 최종 답변

    books:
        Streamlit 카드에서 사용할 실제 검색 결과
    """

    answer, result = run_agent(
        question,
        thread_id,
    )


    books = extract_book_rows(
        result
    )


    return answer, books

def main():

    print(
        "ChromaDB:",
        CHROMA_DB_PATH
    )


    print(
        "저장된 책 수:",
        book_collection.count()
    )


    print(
        "\n도서 추천 에이전트입니다."
        "\n종료: 종료"
        "\n대화 초기화: 새대화\n"
    )


    thread_id = "cli-session"


    while True:

        question = input(
            "질문> "
        ).strip()


        if question.lower() in {
            "종료",
            "exit",
            "quit",
        }:
            break


        if question == "새대화":

            reset_book_memory(
                thread_id
            )

            print(
                "\n대화 기억을 초기화했습니다.\n"
            )

            continue


        if not question:
            continue


        try:

            answer = ask_book_agent(
                question,
                thread_id,
            )

            print(
                f"\n{answer}\n"
            )


        except Exception as exc:

            print(
                f"\n오류: {exc}\n"
            )
if __name__ == "__main__":
    main()
