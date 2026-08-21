import os

from langchain_core.documents import Document

from 내작업.db import create_supabase_client


def _get_supabase():
    """Supabase는 실제 조회가 필요할 때만 연결한다."""
    return create_supabase_client()


def search_supabase(filters):
    """메타데이터 조건으로 책 행을 조회한다.

    추천의 의미 검색에는 사용하지 않고, 명시적인 조건 조회가 필요할 때만
    사용하는 함수다.
    """
    supabase = _get_supabase()
    query = supabase.table("books").select("*")

    if filters.author is not None:
        query = query.ilike("author", f"%{filters.author.strip()}%")

    if filters.min_price is not None:
        query = query.gte("price_standard", filters.min_price)

    if filters.max_price is not None:
        query = query.lte("price_standard", filters.max_price)

    if filters.min_rating is not None:
        query = query.gte("customer_review_rank", filters.min_rating)

    if filters.max_rating is not None:
        query = query.lte("customer_review_rank", filters.max_rating)

    rows = query.limit(getattr(filters, "k", 5)).execute().data

    return [
        Document(
            page_content=row.get("description") or "",
            metadata=row,
        )
        for row in rows
    ]


def fetch_cover_map(item_ids):
    """itemId 목록으로 Supabase에서 표지 URL을 조회한다.

    프로젝트의 테이블이 camelCase(itemId) 또는 snake_case(item_id)로
    만들어졌을 수 있어 두 이름을 순서대로 지원한다.
    """
    values = [value for value in item_ids if value not in (None, "")]
    if not values:
        return {}

    supabase = _get_supabase()
    last_error = None

    for id_column in ("itemId", "item_id"):
        for cover_column in ("cover", "cover_url"):
            try:
                rows = (
                    supabase.table("books")
                    .select(f"{id_column},{cover_column}")
                    .in_(id_column, values)
                    .execute()
                    .data
                )
                return {
                    str(row.get(id_column)): row.get(cover_column)
                    for row in rows
                    if row.get(id_column) is not None
                    and row.get(cover_column)
                }
            except Exception as exc:  # noqa: BLE001 - 컬럼명 호환용 재시도
                last_error = exc

    raise RuntimeError(
        "Supabase books 테이블의 itemId/item_id 또는 cover/cover_url 컬럼을 "
        "확인하세요."
    ) from last_error
