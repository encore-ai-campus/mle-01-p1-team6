from pathlib import Path

import chromadb
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from db import create_supabase_client


# =========================================================
# 1. Path / ENV
# =========================================================
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

ENV_PATH = PROJECT_ROOT / ".env"
CHROMA_DB_PATH = PROJECT_ROOT / "chroma_db"

load_dotenv(ENV_PATH, override=True)


# =========================================================
# 2. Model / DB
# =========================================================

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
)


embeddings = HuggingFaceEmbeddings(
    model_name="SamilPwC-AXNode-GenAI/PwC-Embedding_expr",
    encode_kwargs={
        "normalize_embeddings": True
    },
)


# Supabase
supabase = create_supabase_client()


# ChromaDB
chroma_client = chromadb.PersistentClient(
    path=str(CHROMA_DB_PATH)
)


book_collection = chroma_client.get_collection(
    name="book"
)


# =========================================================
# 3. Tool Input Schema
# =========================================================


# ---------------------------------------------------------
# ChromaDB 의미 검색
# ---------------------------------------------------------

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
            "'3개 추천', '3권 추천'이면 3. "
            "개수를 말하지 않으면 3"
        )
    )


# ---------------------------------------------------------
# Supabase 조건 검색
# ---------------------------------------------------------

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
            "'3개 추천', '3권 추천'이면 3. "
            "개수를 말하지 않으면 3"
        )
    )


# =========================================================
# 4. ChromaDB 의미 검색 Tool
# =========================================================

@tool(args_schema=VectorSearchInput)
def vector_search_descp(
    query: str,
    k: int = 3,
):
    """
    책의 내용, 분위기, 주제, 특징, 취향처럼
    의미 기반 검색이 필요한 경우 사용한다.
    """

    # -----------------------------------------------------
    # 1. 질문 임베딩
    # -----------------------------------------------------

    query_embedding = embeddings.embed_query(query)


    # -----------------------------------------------------
    # 2. ChromaDB 검색
    # -----------------------------------------------------

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


    # -----------------------------------------------------
    # 3. Chroma 결과에서 itemId 가져오기
    # -----------------------------------------------------

    item_ids = []

    for metadata in metadatas:

        item_id = metadata.get("itemId")

        if item_id is not None:
            item_ids.append(item_id)


    # -----------------------------------------------------
    # 4. itemId를 이용해서 Supabase에서 cover 가져오기
    # -----------------------------------------------------

    cover_map = {}

    if item_ids:

        response = (
            supabase
            .table("books")
            .select(
                "itemId, cover"
            )
            .in_(
                "itemId",
                item_ids
            )
            .execute()
        )


        for book in response.data:

            item_id = book.get("itemId")

            if item_id is not None:

                # 타입 차이(int/string) 방지
                cover_map[str(item_id)] = book.get("cover")


    # -----------------------------------------------------
    # 5. Chroma 결과 + Supabase cover 합치기
    # -----------------------------------------------------

    rows = []

    for book_id, document, metadata, distance in zip(
        ids,
        documents,
        metadatas,
        distances,
    ):

        item_id = metadata.get("itemId")

        rows.append(
            {
                "chroma_id": book_id,

                "itemId": item_id,

                "title": metadata.get("title"),

                "author": metadata.get("author"),

                "publisher": metadata.get("publisher"),

                "category_name": metadata.get(
                    "category_name"
                ),

                "price": metadata.get(
                    "priceStandard"
                ),

                "rating": metadata.get(
                    "customerReviewRank"
                ),

                "pubDate": metadata.get(
                    "pubDate"
                ),

                "description": document,

                "distance": distance,

                # ★ Supabase에서 가져온 실제 이미지 URL
                "cover_url": (
                    cover_map.get(str(item_id))
                    if item_id is not None
                    else None
                ),
            }
        )

    return rows


# =========================================================
# 5. Supabase 정확 조건 검색 Tool
# =========================================================

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
    정확한 조건으로 책을 검색할 때 사용한다.

    cover_url은 Supabase books 테이블의
    cover 값을 그대로 사용한다.
    """

    # -----------------------------------------------------
    # 1. 기본 Query
    # -----------------------------------------------------

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


    # -----------------------------------------------------
    # 2. 조건 적용
    # -----------------------------------------------------

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
    # -----------------------------------------------------
    # 3. 사용자가 원하는 개수만큼 검색
    # -----------------------------------------------------

    response = (
        request
        .limit(k)
        .execute()
    )

    # -----------------------------------------------------
    # 4. Agent에게 전달할 데이터 형태 정리
    # -----------------------------------------------------

    rows = []

    for book in response.data:

        rows.append(
            {
                "itemId": book.get(
                    "itemId"
                ),

                "title": book.get(
                    "title"
                ),

                "author": book.get(
                    "author"
                ),

                "publisher": book.get(
                    "publisher"
                ),

                "category_name": book.get(
                    "category_name"
                ),

                "price": book.get(
                    "priceStandard"
                ),

                "rating": book.get(
                    "customerReviewRank"
                ),

                "pubDate": book.get(
                    "pubDate"
                ),
                "cover_url": book.get(
                    "cover"
                ),
            }
        )

    return rows
# =========================================================
# 6. Agent
# =========================================================
tools = [
    search_book,
    vector_search_descp,
]
agent = create_agent(
    model=llm,

    tools=tools,

    system_prompt="""
너는 사용자의 취향과 조건에 맞는 책을 추천하는
도서 추천 에이전트다.
[도구 선택 규칙]
1. 가격, 평점, 작가, 카테고리처럼
   정확한 조건이 필요한 경우
   search_book을 사용한다.
2. 책의 내용, 분위기, 주제, 특징, 취향처럼
   의미 기반 검색이 필요한 경우
   vector_search_descp를 사용한다.
3. 의미 조건과 정확한 조건이 같이 포함되면
   필요한 도구를 사용해서 검색한다.
[추천 개수 규칙]
4. 사용자가 추천할 책 개수를 말하면
   반드시 그 숫자를 k로 전달한다.
5. 사용자가 추천 개수를 말하지 않으면
   기본값으로 k=3을 사용한다.
6. 최종 답변의 추천 개수도
   사용자가 요청한 개수를 따른다.
[검색 결과 규칙]
7. 반드시 도구에서 실제 검색된 책만 추천한다.
8. 검색되지 않은 책이나 정보를
   임의로 만들어내지 않는다.
9. 같은 책을 중복해서 추천하지 않는다.
10. itemId가 같으면 같은 책으로 판단한다.
[표지 이미지 규칙]
11. 표지 이미지 URL은 반드시
    도구가 반환한 cover_url 값을 그대로 사용한다.
12. cover_url을 직접 만들거나 추측하지 않는다.
13. cover_url 문자열의 일부를 수정하거나
    다른 URL로 변경하지 않는다.
14. cover_url이 None이거나 빈 문자열이면
    이미지 URL을 임의로 만들어내지 않는다.
[최종 답변 규칙]
15. 가능한 경우 다음 정보를 보여준다.
- 책 제목
- 저자
- 가격
- 평점
- 추천 이유
- cover_url
16. 추천 이유는 사용자의 질문과
    검색 결과를 바탕으로 간단하게 설명한다.
""",
)
# =========================================================
# 7. Agent 호출
# =========================================================
def ask_book_agent(
    question: str
) -> str:

    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": question,
                }
            ]
        }
    )
    return result[
        "messages"
    ][-1].content
# =========================================================
# 8. CLI
# =========================================================
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
        "\n종료하려면 '종료'를 입력하세요.\n"
    )


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


        if not question:
            continue


        try:

            answer = ask_book_agent(
                question
            )

            print(
                f"\n{answer}\n"
            )


        except Exception as exc:

            print(
                f"\n오류: {exc}\n"
            )
# =========================================================
# 9. 실행
# =========================================================

if __name__ == "__main__":
    main()