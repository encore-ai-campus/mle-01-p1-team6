#필요한 라이브러리와 도구 호출
import os
from datetime import date
from langchain_core.tools import tool
from typing import Literal
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from supabase import create_client, Client

# 환경 설정
load_dotenv("../../.env")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY")

# Supabase 연결
supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

#기본 슈퍼베이스에 존재하는 열 명시
BookColumn = Literal["category_name","rank_in_category","itemId","title","author","publisher","pubDate","priceSales","priceStandard","salesPoint","customerReviewRank","link","cover","description","row_id"]

#정렬에 사용할 열 제한
OrderColumn = Literal["rank_in_category","pubDate","priceSales","priceStandard","salesPoint","customerReviewRank"]

#sql 질문 위한 스키마
class BookSearchInput(BaseModel):
    # 반환할 컬럼
    select_list: list[BookColumn] = Field(
        default=[
            "title",
            "author",
            "publisher",
            "pubDate",
            "priceSales",
            "customerReviewRank",
            "description",
        ],
        min_length=1,
        description=(
            "검색 결과에서 가져올 컬럼 목록. "
            "books 테이블에 존재하는 허용된 컬럼만 선택 가능"
        ),
    )

    # 카테고리
    category_name: str | None = Field(
        default=None,
        description=(
            "책 카테고리. 정확히 일치하는 카테고리만 조회. "
            "조건이 없으면 None"
        ),
    )

    # 카테고리 순위
    # 정확한 값 OR 범위
    rank_in_category: int | None = Field(
        default=None,
        ge=1,
        description=(
            "카테고리 순위가 정확히 이 값인 책 조회. "
            "예: 10위 → 10"
        ),
    )

    min_rank_in_category: int | None = Field(
        default=None,
        ge=1,
        description=(
            "조회할 카테고리 순위의 최소값. "
            "예: 1~10위 → 1"
        ),
    )

    max_rank_in_category: int | None = Field(
        default=None,
        ge=1,
        description=(
            "조회할 카테고리 순위의 최대값. "
            "예: 1~10위 → 10"
        ),
    )

    # 문자열 검색
    # 부분 포함 검색
    title: str | None = Field(
        default=None,
        description=(
            "책 제목에 포함되어야 하는 문자열. "
            "조건이 없으면 None"
        ),
    )

    author: str | None = Field(
        default=None,
        description=(
            "저자명에 포함되어야 하는 문자열. "
            "조건이 없으면 None"
        ),
    )

    publisher: str | None = Field(
        default=None,
        description=(
            "출판사명에 포함되어야 하는 문자열. "
            "조건이 없으면 None"
        ),
    )

    # 출간일 범위
    start_pub_date: date | None = Field(
        default=None,
        description=(
            "출간일 검색 시작 날짜. "
            "예: 2025-01-01 이후"
        ),
    )

    end_pub_date: date | None = Field(
        default=None,
        description=(
            "출간일 검색 종료 날짜. "
            "예: 2025-12-31 이전"
        ),
    )

    # 판매가 priceSales
    # 정확한 가격 OR 가격 범위
    price_sales: int | None = Field(
        default=None,
        ge=0,
        description=(
            "판매가가 정확히 이 가격인 책 조회. "
            "범위 검색과 동시에 사용하지 않음"
        ),
    )

    min_price_sales: int | None = Field(
        default=None,
        ge=0,
        description="최소 판매가",
    )

    max_price_sales: int | None = Field(
        default=None,
        ge=0,
        description="최대 판매가",
    )

    # 정가 priceStandard
    # 정확한 가격 OR 가격 범위
    price_standard: int | None = Field(
        default=None,
        ge=0,
        description=(
            "정가가 정확히 이 가격인 책 조회. "
            "범위 검색과 동시에 사용하지 않음"
        ),
    )

    min_price_standard: int | None = Field(
        default=None,
        ge=0,
        description="최소 정가",
    )

    max_price_standard: int | None = Field(
        default=None,
        ge=0,
        description="최대 정가",
    )

    # 판매지수
    min_sales_point: int | None = Field(
        default=None,
        ge=0,
        description="최소 판매지수",
    )

    max_sales_point: int | None = Field(
        default=None,
        ge=0,
        description="최대 판매지수",
    )

    # 고객 평점
    # int 사용
    # 정확한 평점 OR 평점 범위
    review_rank: int | None = Field(
        default=None,
        ge=0,
        description=(
            "고객 평점이 정확히 이 값인 책 조회. "
            "예: 9"
        ),
    )

    min_review_rank: int | None = Field(
        default=None,
        ge=0,
        description=(
            "최소 고객 평점. "
            "예: 평점 8 이상 → 8"
        ),
    )

    max_review_rank: int | None = Field(
        default=None,
        ge=0,
        description=(
            "최대 고객 평점. "
            "예: 평점 9 이하 → 9"
        ),
    )

    # 책 설명
    # 복잡한 조건이 아니라 특정 단어 포함 여부만 검색
    description_keyword: str | None = Field(
        default=None,
        description=(
            "책 description에 포함되어야 할 특정 단어 또는 짧은 문구. "
            "예: '인공지능', '성장', '경제'. "
            "복잡한 자연어 의미 검색 용도가 아님"
        ),
    )

    # 정렬
    order_by: OrderColumn | None = Field(
        default=None,
        description=(
            "정렬 기준 컬럼. "
            "조건이 없으면 별도 정렬하지 않음"
        ),
    )

    order_desc: bool = Field(
        default=False,
        description=(
            "True이면 내림차순, False이면 오름차순"
        ),
    )

    # 조회 개수
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="최대 조회 개수. 1~100",
    )


# 4. Supabase 검색 조건 적용 함수
def apply_book_filters(query, params: BookSearchInput):
    # 카테고리
    if params.category_name is not None:

        query = query.eq(
            "category_name",
            params.category_name,
        )

    # 카테고리 순위
    # 정확한 값 OR 범위
    if params.rank_in_category is not None:

        query = query.eq(
            "rank_in_category",
            params.rank_in_category,
        )

    else:
        if params.min_rank_in_category is not None:
            query = query.gte(
                "rank_in_category",
                params.min_rank_in_category,
            )

        if params.max_rank_in_category is not None:
            query = query.lte(
                "rank_in_category",
                params.max_rank_in_category,
            )

    # 제목 / 저자 / 출판사
    # 부분 포함 검색
    if params.title is not None:
        query = query.ilike(
            "title",
            f"%{params.title}%",
        )

    if params.author is not None:
        query = query.ilike(
            "author",
            f"%{params.author}%",
        )

    if params.publisher is not None:
        query = query.ilike(
            "publisher",
            f"%{params.publisher}%",
        )

    # 출간일
    if params.start_pub_date is not None:

        query = query.gte(
            "pubDate",
            params.start_pub_date.isoformat(),
        )

    if params.end_pub_date is not None:

        query = query.lte(
            "pubDate",
            params.end_pub_date.isoformat(),
        )

    # 판매가
    if params.price_sales is not None:

        query = query.eq(
            "priceSales",
            params.price_sales,
        )

    else:
        if params.min_price_sales is not None:

            query = query.gte(
                "priceSales",
                params.min_price_sales,
            )

        if params.max_price_sales is not None:
            query = query.lte(
                "priceSales",
                params.max_price_sales,
            )

    # 정가
    if params.price_standard is not None:

        query = query.eq(
            "priceStandard",
            params.price_standard,
        )

    else:

        if params.min_price_standard is not None:

            query = query.gte(
                "priceStandard",
                params.min_price_standard,
            )

        if params.max_price_standard is not None:

            query = query.lte(
                "priceStandard",
                params.max_price_standard,
            )

    # 판매지수
    if params.min_sales_point is not None:
        query = query.gte(
            "salesPoint",
            params.min_sales_point,
        )


    if params.max_sales_point is not None:
        query = query.lte(
            "salesPoint",
            params.max_sales_point,
        )

    # 고객 평점
    # 정확한 값 OR 범위
    if params.review_rank is not None:
        query = query.eq(
            "customerReviewRank",
            params.review_rank,
        )

    else:

        if params.min_review_rank is not None:
            query = query.gte(
                "customerReviewRank",
                params.min_review_rank,
            )

        if params.max_review_rank is not None:
            query = query.lte(
                "customerReviewRank",
                params.max_review_rank,
            )


    # 책 소개 키워드
    # 특정 단어가 포함되는지만 검사
    if params.description_keyword is not None:

        query = query.ilike(
            "description",
            f"%{params.description_keyword}%",
        )

    # 정렬
    if params.order_by is not None:

        query = query.order(
            params.order_by,
            desc=params.order_desc,
        )

    # 최대 조회 개수
    query = query.limit(params.limit)

    return query


# 5. LangChain 조회 도구
@tool(args_schema=BookSearchInput)
def search_books(**kwargs):
    """
    Supabase books 테이블에서 책 정보를 조회합니다.

    카테고리, 순위, 제목, 저자, 출판사, 출간일,
    가격, 판매지수, 고객 평점, description 키워드를
    조건으로 사용할 수 있습니다.

    입력되지 않은 조건은 검색에 사용하지 않습니다.
    여러 조건이 입력되면 모든 조건을 만족하는 책을 조회합니다.
    """
    # Pydantic 스키마로 최종 입력 검증
    params = BookSearchInput(**kwargs)

    select_columns = ",".join(
        params.select_list
    )

    query = (
        supabase
        .table("books")
        .select(select_columns)
    )

    query = apply_book_filters(
        query,
        params,
    )

    response = query.execute()

    return response.data