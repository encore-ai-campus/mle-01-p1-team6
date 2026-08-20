#필요한 라이브러리와 도구 호출
from pathlib import Path
from langchain_core.tools import tool
import chromadb
from sentence_transformers import SentenceTransformer
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

# 유사도 검색 도구
@tool
def vector_search_descp(
    query: str,
    category_name: str | None = None,
    author: str | None = None,
    priceStandard: int | None = None,
    customerReviewRank: int | None = None
):
    """책 소개 기반 벡터 유사도 검색.

    Args:
        query: 유사도 검색 문장
        category_name: 책 카테고리( 다음 중에서 하나를 입력: "건강/취미","경제경영","과학","사회과학","소설/시/희곡","어린이","에세이","여행","역사","예술/대중문화","요리/살림","인문학","자기계발","청소년","컴퓨터/모바일")
        author: 작가 이름
        priceStandard: 최대 가격
        customerReviewRank: 최소 평점(1~10)
    """

    # 질문 임베딩
    query_embedding = model.encode(
        [query],
        normalize_embeddings=True
    ).tolist()

    # 메타데이터 필터 생성
    filters = []

    if category_name:
        filters.append({"category_name": category_name})

    if author:
        filters.append({"author": author})

    if priceStandard is not None:
        filters.append({
            "priceStandard": {"$lte": priceStandard}
        })

    if customerReviewRank is not None:
        filters.append({
            "customerReviewRank": {"$gte": customerReviewRank}
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

    # 필터 + 벡터 유사도 검색(top5)
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=5,
        where=where
    )

    #벡터 제외 메타데이터만 생성
    return results["metadatas"][0]