#필요한 라이브러리와 도구 호출
from pathlib import Path
from langchain_core.tools import tool
import chromadb
from sentence_transformers import SentenceTransformer
from pydantic import BaseModel, Field
model = SentenceTransformer(
    "SamilPwC-AXNode-GenAI/PwC-Embedding_expr"
)

#경로 설정
BASE_DIR = Path(__file__).resolve().parent
chroma_db_path = (BASE_DIR / "../../chroma_db").resolve()

#기본 chromadb불러오기
client = chromadb.PersistentClient(
    path=str(chroma_db_path)
)

collection = client.get_collection(
    name="book"
)

#기본 입력 틀 제작 : ai의 메타데이터 필터링 용이 목적
class VectorSearchInput(BaseModel):
    query: str = Field(
        description="책의 내용이나 특징을 검색하기 위한 자연어 검색 문장"
    )
    k: int = Field(default=5, ge=1,
        description="검색할 책의 개수. 기본값은 5")
    
    category_name: str | None = Field( default=None,
        description="책 카테고리. 조건이 없으면 None")
    
    author: str | None = Field( default=None,
        description="작가 이름. 조건이 없으면 None")
    
    min_price: int | None = Field( default=None, ge=0,
        description="최소 가격. '10000원 이상'이면 10000")
    
    max_price: int | None = Field(default=None,ge=0,
        description="최대 가격. '20000원 이하'이면 20000")
    
    min_rating: float | None = Field(default=None,ge=1,le=10,
        description="최소 평점. '평점 7 이상'이면 7")
    
    max_rating: float | None = Field(default=None,ge=1,le=10,
        description="최대 평점. '평점 8 이하'이면 8")


# 유사도 검색 도구
@tool(args_schema=VectorSearchInput)
def vector_search_descp(
    query: str,
    k: int = 5,
    category_name: str | None = None,
    author: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    min_rating: float | None = None,
    max_rating: float | None = None
):
    """책 소개를 기반으로 메타데이터 필터링과 벡터 유사도 검색을 수행합니다."""

    # 질문 임베딩
    query_embedding = model.encode(
        [query],
        normalize_embeddings=True
    ).tolist()

    # 메타데이터 필터 생성
    filters = []

    if category_name:
        filters.append({
            "category_name": category_name
        })

    if author:
        filters.append({
            "author": author
        })

    if min_price is not None:
        filters.append({
            "priceStandard": {"$gte": min_price}
        })

    if max_price is not None:
        filters.append({
            "priceStandard": {"$lte": max_price}
        })

    if min_rating is not None:
        filters.append({
            "customerReviewRank": {"$gte": min_rating}
        })

    if max_rating is not None:
        filters.append({
            "customerReviewRank": {"$lte": max_rating}
        })

    # 필터 개수에 따라 where 생성
    if len(filters) == 0:   #필터 비면 조건 없음
        where = None

    elif len(filters) == 1: #하나면 [{열:조건}]
        where = filters[0]

    else:                   #여러개면 [{ }, { },...]
        where = {"$and": filters}
        #이 경우 코드 예시
        # where = {
        #     "$and": [
        #         {"category_name": "과학"},
        #         {"priceStandard": {"$lte": 20000}}
        #           ]
        #       }       

    # 필터 + 벡터 유사도 검색(topK)
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=k,
        where=where
    )

    #벡터 제외 메타데이터만 생성
    return results["metadatas"][0]