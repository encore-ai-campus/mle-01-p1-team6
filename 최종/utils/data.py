from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _find_books_file() -> Path:
    candidates = []
    for path in PROJECT_ROOT.rglob("books.csv"):
        try:
            columns = pd.read_csv(path, nrows=0).columns
        except (OSError, pd.errors.ParserError):
            continue
        if {"title", "category_name", "priceStandard"}.issubset(columns):
            candidates.append(path)
    if not candidates:
        raise FileNotFoundError("books.csv를 찾을 수 없습니다.")
    return min(candidates, key=lambda path: len(path.parts))


@st.cache_data(ttl="15m", max_entries=4)
def load_books() -> pd.DataFrame:
    books = pd.read_csv(_find_books_file())
    books = books.drop(columns=[column for column in books.columns if column.startswith("Unnamed:")], errors="ignore")

    text_columns = ["title", "author", "publisher", "category_name", "description"]
    for column in text_columns:
        if column not in books:
            books[column] = ""
        books[column] = books[column].fillna("").astype(str).str.strip()

    numeric_columns = [
        "rank_in_category",
        "priceSales",
        "priceStandard",
        "salesPoint",
        "customerReviewRank",
    ]
    for column in numeric_columns:
        if column not in books:
            books[column] = 0
        books[column] = pd.to_numeric(books[column], errors="coerce").fillna(0)

    if "itemId" not in books:
        books["itemId"] = books.index
    books["itemId"] = books["itemId"].astype(str)
    return books


def filter_books(
    books: pd.DataFrame,
    categories: list[str] | None = None,
    price_range: tuple[float, float] | None = None,
    rating_range: tuple[float, float] | None = None,
) -> pd.DataFrame:
    result = books
    if categories:
        result = result[result["category_name"].isin(categories)]
    if price_range:
        result = result[result["priceStandard"].between(*price_range)]
    if rating_range:
        result = result[result["customerReviewRank"].between(*rating_range)]
    return result.copy()


def format_price(value: object) -> str:
    try:
        return f"{float(value):,.0f}원"
    except (TypeError, ValueError):
        return "가격 정보 없음"


def format_rating(value: object) -> str:
    try:
        return f"{float(value):.1f}점"
    except (TypeError, ValueError):
        return "평점 정보 없음"


def safe_cover(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if value.startswith(("http://", "https://")) else None
