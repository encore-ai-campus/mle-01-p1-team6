"""Collect Aladin category bestsellers and enrich them with crawled data.

The actual integrations live in separate modules:

* :mod:`aladin_api` - Aladin Open API calls
* :mod:`aladin_description` - publisher-description crawler
* :mod:`aladin_reviews` - community-review crawler/parser
* :mod:`aladin_storage` - JSON/CSV output helpers
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from aladin_api import (
    fetch_category_bestsellers,
    fetch_item_details as fetch_item_details_api,
    load_categories,
)
from aladin_description import fetch_publisher_description
from aladin_reviews import fetch_community_reviews
from aladin_storage import (
    safe_filename,
    write_api_books_csv,
    write_api_details_csv,
    write_community_reviews_csv,
    write_publisher_descriptions_csv,
    write_json,
)


load_dotenv(Path(__file__).with_name(".env"))


def fetch_item_details(
    session: requests.Session,
    api_key: str,
    item_id: int,
) -> dict[str, Any]:
    """Backward-compatible combined detail helper.

    New code should call ``aladin_api.fetch_item_details`` and
    ``aladin_description.fetch_publisher_description`` separately.
    """
    details = fetch_item_details_api(session, api_key, item_id)
    publisher_description = fetch_publisher_description(
        session,
        item_id,
        str(details.get("isbn", "")),
    )
    return {
        "fullDescription": details.get("fullDescription", ""),
        "publisherDescription": publisher_description,
        "reviewList": details.get("reviewList", []),
    }


def parse_week(value: str | None) -> tuple[int, int, int] | None:
    if value is None:
        return None
    parts = value.split("-")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError("--week은 YYYY-M-W 형식이어야 합니다. 예: 2026-8-1")
    year, month, week = map(int, parts)
    if year < 1 or not 1 <= month <= 12 or not 1 <= week <= 5:
        raise ValueError("--week 값이 올바르지 않습니다. 예: 2026-8-1")
    return year, month, week


def collect_category(
    session: requests.Session,
    api_key: str,
    category_name: str,
    category_id: int,
    *,
    week: tuple[int, int, int] | None,
    delay: float,
    skip_community_reviews: bool,
    detail_cache: dict[int, dict[str, Any]],
    publisher_description_cache: dict[int, str],
    community_review_cache: dict[int, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Fetch and enrich one category using the separated integrations."""
    rows = fetch_category_bestsellers(
        session,
        api_key,
        category_name,
        category_id,
        week=week,
        delay=delay,
    )

    for row in rows:
        try:
            item_id = int(row["itemId"])
        except (KeyError, TypeError, ValueError):
            item_id = 0

        # 1) Open API: item fullDescription and API reviewList.
        if item_id and item_id not in detail_cache:
            try:
                detail_cache[item_id] = fetch_item_details_api(session, api_key, item_id)
            except Exception as exc:
                print(
                    f"상세 API 조회 실패: {category_name}, ItemId={item_id}: {exc}",
                    file=sys.stderr,
                )
                detail_cache[item_id] = {}
            time.sleep(delay)
        details = detail_cache.get(item_id, {})
        row["api_isbn"] = str(details.get("isbn", ""))

        # 2) Crawler: publisher's book introduction.
        if item_id and item_id not in publisher_description_cache:
            try:
                publisher_description_cache[item_id] = fetch_publisher_description(
                    session,
                    item_id,
                    str(details.get("isbn", "")),
                )
            except Exception as exc:
                print(
                    f"책소개 크롤링 실패: {category_name}, ItemId={item_id}: {exc}",
                    file=sys.stderr,
                )
                publisher_description_cache[item_id] = ""
        publisher_description = publisher_description_cache.get(item_id, "")
        row["publisherDescription"] = publisher_description
        row["fullDescription"] = (
            details.get("fullDescription", "") or publisher_description
        )
        row["reviewList"] = details.get("reviewList", [])

        # 3) Crawler: all community reviews.
        if skip_community_reviews:
            row["communityReviews"] = []
        elif item_id and item_id not in community_review_cache:
            try:
                community_review_cache[item_id] = fetch_community_reviews(
                    session,
                    item_id,
                    page_size=100,
                    delay=delay,
                )
                print(
                    f"커뮤니티 리뷰 수집: ItemId={item_id}, "
                    f"{len(community_review_cache[item_id])}건"
                )
            except Exception as exc:
                print(
                    f"커뮤니티 리뷰 조회 실패: {category_name}, ItemId={item_id}: {exc}",
                    file=sys.stderr,
                )
                community_review_cache[item_id] = []
        row["communityReviews"] = community_review_cache.get(item_id, [])

    return rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description="알라딘 카테고리별 베스트셀러를 최대 200권씩 수집합니다."
    )
    parser.add_argument(
        "--categories",
        type=Path,
        default=Path("categories.json"),
        help="{카테고리명: 카테고리ID} 형식의 JSON 파일",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/aladin_bestsellers"),
        help="결과 저장 폴더",
    )
    parser.add_argument(
        "--merge-existing",
        action="store_true",
        help="기존 all_bestsellers.json에서 선택하지 않은 카테고리를 보존합니다.",
    )
    parser.add_argument(
        "--week",
        help="과거 주간 조회 시 사용. YYYY-M-W 형식, 생략하면 현재 주간입니다.",
    )
    parser.add_argument("--delay", type=float, default=0.3, help="페이지 사이 대기 시간(초)")
    parser.add_argument(
        "--skip-community-reviews",
        action="store_true",
        help="커뮤니티 리뷰 크롤링을 건너뜁니다.",
    )
    args = parser.parse_args()

    api_key = os.getenv("BOOK_API_KEY")
    if not api_key:
        print("환경변수 BOOK_API_KEY가 설정되어 있지 않습니다.", file=sys.stderr)
        return 1

    try:
        categories = load_categories(args.categories)
        selected_week = parse_week(args.week)
    except (FileNotFoundError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": "aladin-bestseller-collector/1.0"})
    all_rows: list[dict[str, Any]] = []
    detail_cache: dict[int, dict[str, Any]] = {}
    publisher_description_cache: dict[int, str] = {}
    community_review_cache: dict[int, list[dict[str, Any]]] = {}
    fetched_at = datetime.now().astimezone().isoformat(timespec="seconds")

    for category_name, category_id in categories.items():
        print(f"수집 중: {category_name} (CategoryId={category_id})")
        try:
            rows = collect_category(
                session,
                api_key,
                category_name,
                category_id,
                week=selected_week,
                delay=args.delay,
                skip_community_reviews=args.skip_community_reviews,
                detail_cache=detail_cache,
                publisher_description_cache=publisher_description_cache,
                community_review_cache=community_review_cache,
            )
        except Exception as exc:
            print(f"실패: {category_name}: {exc}", file=sys.stderr)
            return 1

        for row in rows:
            row["fetched_at"] = fetched_at
        all_rows.extend(rows)
        write_json(args.output_dir / f"{safe_filename(category_name)}.json", rows)
        print(f"  -> {len(rows)}권 저장")

    if args.merge_existing:
        existing_path = args.output_dir / "all_bestsellers.json"
        try:
            existing_rows = json.loads(existing_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            existing_rows = []
        except json.JSONDecodeError as exc:
            print(f"기존 결과 병합 실패: {existing_path}: {exc}", file=sys.stderr)
            return 1

        if not isinstance(existing_rows, list):
            print(f"기존 결과 병합 실패: 목록 형식이 아닙니다: {existing_path}", file=sys.stderr)
            return 1

        selected_category_ids = {int(category_id) for category_id in categories.values()}
        selected_category_names = set(categories)
        preserved_rows = [
            row for row in existing_rows
            if not (
                isinstance(row, dict)
                and (
                    row.get("category_name") in selected_category_names
                    or row.get("category_id") in selected_category_ids
                )
            )
        ]
        all_rows = preserved_rows + all_rows

    write_json(args.output_dir / "all_bestsellers.json", all_rows)
    write_api_books_csv(args.output_dir / "api_books.csv", all_rows)
    write_api_details_csv(args.output_dir / "api_item_details.csv", all_rows)
    write_publisher_descriptions_csv(
        args.output_dir / "publisher_descriptions.csv", all_rows
    )
    write_json(
        args.output_dir / "all_community_reviews.json",
        [review for row in all_rows for review in row.get("communityReviews", [])],
    )
    write_community_reviews_csv(args.output_dir / "community_reviews.csv", all_rows)
    print(f"완료: 총 {len(all_rows)}권")
    print(f"저장 위치: {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
