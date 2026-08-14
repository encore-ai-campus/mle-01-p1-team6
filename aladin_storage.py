"""Output helpers for collected Aladin data."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any


CSV_FIELDS = [
    "category_name", "category_id", "rank_in_category", "itemId", "title",
    "author", "publisher", "pubDate", "isbn", "isbn13", "priceSales",
    "priceStandard", "salesPoint", "customerReviewRank", "bestSellerRank",
    "link", "cover", "description", "fullDescription", "publisherDescription",
    "reviewList", "communityReviews",
]

# Keep each data source in its own CSV.  The legacy combined writer above is
# retained for compatibility with callers that still import it.
API_BOOK_FIELDS = [
    "category_name", "category_id", "rank_in_category", "itemId", "title",
    "author", "publisher", "pubDate", "isbn", "isbn13", "priceSales",
    "priceStandard", "salesPoint", "customerReviewRank", "bestSellerRank",
    "link", "cover", "description", "fetched_at",
]

API_DETAIL_FIELDS = [
    "itemId", "category_name", "category_id", "title", "api_isbn",
    "fullDescription", "reviewList", "fetched_at",
]

PUBLISHER_DESCRIPTION_FIELDS = [
    "itemId", "category_name", "category_id", "title", "api_isbn",
    "publisherDescription", "fetched_at",
]

COMMUNITY_REVIEW_CSV_FIELDS = [
    "itemId", "category_name", "category_id", "title", "paperId", "rating",
    "content", "author", "authorUrl", "reviewUrl", "date",
    "recommendationCount", "commentCount", "isOrderer",
]


def safe_filename(value: str) -> str:
    value = re.sub(r"[^0-9A-Za-z가-힣_-]+", "_", value).strip("._")
    return value or "category"


def write_json(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            csv_row = dict(row)
            for field in ("reviewList", "communityReviews"):
                if isinstance(csv_row.get(field), (dict, list)):
                    csv_row[field] = json.dumps(csv_row[field], ensure_ascii=False)
            writer.writerow(csv_row)


def _write_source_csv(
    path: Path,
    rows: list[dict[str, Any]],
    fieldnames: list[str],
    nested_fields: tuple[str, ...] = (),
) -> None:
    """Write one source-specific CSV while preserving nested API values."""
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            csv_row = dict(row)
            for field in nested_fields:
                if isinstance(csv_row.get(field), (dict, list)):
                    csv_row[field] = json.dumps(csv_row[field], ensure_ascii=False)
            writer.writerow(csv_row)


def write_api_books_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    _write_source_csv(path, rows, API_BOOK_FIELDS)


def write_api_details_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    _write_source_csv(path, rows, API_DETAIL_FIELDS, ("reviewList",))


def write_publisher_descriptions_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    _write_source_csv(path, rows, PUBLISHER_DESCRIPTION_FIELDS)


def write_community_reviews_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(
            file, fieldnames=COMMUNITY_REVIEW_CSV_FIELDS, extrasaction="ignore"
        )
        writer.writeheader()
        for product in rows:
            for review in product.get("communityReviews", []):
                writer.writerow({
                    "itemId": product.get("itemId"),
                    "category_name": product.get("category_name"),
                    "category_id": product.get("category_id"),
                    "title": product.get("title"),
                    **review,
                })
