"""Build and query a book recommendation vector store.

Usage:
    python rag_pipeline.py build
    python rag_pipeline.py query "추리 소설을 좋아하고 2만원 이하"
"""
from __future__ import annotations

import argparse
import ast
import html
import json
import re
from pathlib import Path

import pandas as pd

DATA = Path("output/aladin_bestsellers")
DB = DATA / "chroma_db"
MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
CHUNK_SIZE = 200


def clean(value: object) -> str:
    text = "" if value is None else html.unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def reviews_for(item_id: str, reviews: pd.DataFrame) -> str:
    rows = reviews[reviews.itemId.astype(str) == str(item_id)]
    return " ".join(clean(x) for x in rows.get("content", []) if clean(x))


def chunks(text: str, size: int = CHUNK_SIZE) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)] or [""]


def build() -> None:
    import chromadb
    from sentence_transformers import SentenceTransformer
    books = pd.read_csv(DATA / "api_books.csv", dtype={"itemId": str})
    details = pd.read_csv(DATA / "api_item_details.csv", dtype={"itemId": str})
    publisher = pd.read_csv(DATA / "publisher_descriptions.csv", dtype={"itemId": str})
    reviews = pd.read_csv(DATA / "community_reviews.csv", dtype={"itemId": str})

    for frame in (details, publisher):
        frame.drop_duplicates("itemId", inplace=True)
    books = books.drop_duplicates("itemId").copy()
    books["priceSales"] = pd.to_numeric(books["priceSales"], errors="coerce").fillna(0)
    details = details.set_index("itemId")
    publisher = publisher.set_index("itemId")

    documents, ids, metadatas = [], [], []
    for _, book in books.iterrows():
        item_id = str(book.itemId)
        detail = details.loc[item_id] if item_id in details.index else {}
        pub = publisher.loc[item_id] if item_id in publisher.index else {}
        text = "\n".join(filter(None, [
            clean(book.get("title")), clean(book.get("author")),
            clean(book.get("description")), clean(detail.get("fullDescription", "")),
            clean(pub.get("publisherDescription", "")), reviews_for(item_id, reviews),
        ]))
        meta = {"itemId": item_id, "title": clean(book.get("title")),
                "genre": clean(book.get("category_name")),
                "price": float(book.priceSales), "author": clean(book.get("author")),
                "link": clean(book.get("link"))}
        for n, chunk in enumerate(chunks(text)):
            documents.append(chunk); ids.append(f"{item_id}-{n}"); metadatas.append(meta)

    model = SentenceTransformer(MODEL)
    client = chromadb.PersistentClient(path=str(DB))
    collection = client.get_or_create_collection("aladin_books", metadata={"hnsw:space": "cosine"})
    if ids:
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas,
                          embeddings=model.encode(documents, normalize_embeddings=True).tolist())
    print(json.dumps({"books": len(books), "chunks": len(ids), "db": str(DB)}, ensure_ascii=False))


def query(question: str, genre: str | None, max_price: float | None, n: int) -> None:
    import chromadb
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL)
    collection = chromadb.PersistentClient(path=str(DB)).get_collection("aladin_books")
    where = None
    conditions = []
    if genre: conditions.append({"genre": {"$eq": genre}})
    if max_price is not None: conditions.append({"price": {"$lte": max_price}})
    if conditions: where = conditions[0] if len(conditions) == 1 else {"$and": conditions}
    result = collection.query(query_embeddings=[model.encode(question, normalize_embeddings=True).tolist()],
                              n_results=n, where=where)
    seen = set()
    for meta, distance in zip(result["metadatas"][0], result["distances"][0]):
        if meta["itemId"] not in seen:
            seen.add(meta["itemId"])
            print(f"{meta['title']} | {meta['genre']} | {int(meta['price']):,}원 | score={1-distance:.3f}\n{meta['link']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build")
    q = sub.add_parser("query"); q.add_argument("question"); q.add_argument("--genre"); q.add_argument("--max-price", type=float); q.add_argument("-n", type=int, default=5)
    args = parser.parse_args()
    build() if args.command == "build" else query(args.question, args.genre, args.max_price, args.n)
