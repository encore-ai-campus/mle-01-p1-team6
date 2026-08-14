from __future__ import annotations

import csv
import json
from pathlib import Path


OUT = Path("output/aladin_bestsellers")
EXCLUDED = {"all_bestsellers.json", "all_community_reviews.json"}

API_FIELDS = [
    "category_name", "category_id", "rank_in_category", "itemId", "title",
    "author", "publisher", "pubDate", "isbn", "isbn13", "priceSales",
    "priceStandard", "salesPoint", "customerReviewRank", "bestSellerRank",
    "link", "cover", "description", "fetched_at",
]

DETAIL_FIELDS = [
    "itemId", "category_name", "category_id", "title", "api_isbn",
    "fullDescription", "reviewList", "fetched_at",
]

PUBLISHER_FIELDS = [
    "itemId", "category_name", "category_id", "title", "api_isbn",
    "publisherDescription", "fetched_at",
]

def rows() -> list[dict]:
    result = []
    for path in sorted(OUT.glob("*.json")):
        if path.name in EXCLUDED:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            result.extend(data)
    return result


def write_csv(path: Path, fields: list[str], data: list[dict], nested: set[str] | None = None) -> None:
    nested = nested or set()
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in data:
            out = dict(row)
            out["bestSellerRank"] = row.get("bestSellerRank", row.get("bestRank"))
            for key in nested:
                if isinstance(out.get(key), (list, dict)):
                    out[key] = json.dumps(out[key], ensure_ascii=False)
            writer.writerow(out)


all_rows = rows()
for row in all_rows:
    # The API calls this field ``bestRank``; expose the clearer alias too.
    row["bestSellerRank"] = row.get("bestRank")
(OUT / "all_bestsellers.json").write_text(
    json.dumps(all_rows, ensure_ascii=False, indent=2), encoding="utf-8"
)
write_csv(OUT / "api_books.csv", API_FIELDS, all_rows)
write_csv(OUT / "api_item_details.csv", DETAIL_FIELDS, all_rows, {"reviewList"})
write_csv(OUT / "publisher_descriptions.csv", PUBLISHER_FIELDS, all_rows)
write_csv(OUT / "api_books_all_3000.csv", API_FIELDS, all_rows)
write_csv(OUT / "api_item_details_all_3000.csv", DETAIL_FIELDS, all_rows, {"reviewList"})
write_csv(OUT / "publisher_descriptions_all_3000.csv", PUBLISHER_FIELDS, all_rows)

with (OUT / "community_reviews_all_3000.csv").open("w", newline="", encoding="utf-8-sig") as f:
    fields = [
        "itemId", "category_name", "category_id", "title", "paperId", "rating",
        "content", "author", "authorUrl", "reviewUrl", "date",
        "recommendationCount", "commentCount", "isOrderer",
    ]
    writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for product in all_rows:
        for review in product.get("communityReviews", []):
            writer.writerow({
                "itemId": product.get("itemId"),
                "category_name": product.get("category_name"),
                "category_id": product.get("category_id"),
                "title": product.get("title"),
                **review,
            })

# Keep the legacy aggregate filename in sync as well.
with (OUT / "community_reviews.csv").open("w", newline="", encoding="utf-8-sig") as f:
    fields = [
        "itemId", "category_name", "category_id", "title", "paperId", "rating",
        "content", "author", "authorUrl", "reviewUrl", "date",
        "recommendationCount", "commentCount", "isOrderer",
    ]
    writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for product in all_rows:
        for review in product.get("communityReviews", []):
            writer.writerow({
                "itemId": product.get("itemId"),
                "category_name": product.get("category_name"),
                "category_id": product.get("category_id"),
                "title": product.get("title"),
                **review,
            })

print(f"books={len(all_rows)}")
