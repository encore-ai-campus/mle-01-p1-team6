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
vector_db_path = (BASE_DIR / "../vector_db").resolve()

#기본 chromadb불러오기
client = chromadb.PersistentClient(
    path=str(vector_db_path)
)

collection = client.get_collection(
    name="description_embeddings"
)

# 유사도 검색 도구
@tool
def vector_search_descp(query: str):
    """책소개의 벡터 유사도 검색을 통해 기본 필터링 진행.
    필요한 메타데이터들을 반환합니다.

    Args:
        query (_str_): 일반적인 유사도 검색을 위한 문장을 넣습니다.
    """

    query_embedding = model.encode([query])

    results = collection.query(
        query_embeddings=query_embedding.tolist(),
        n_results=5
    )

    #데이터 반환
    return(results['metadatas'][0])