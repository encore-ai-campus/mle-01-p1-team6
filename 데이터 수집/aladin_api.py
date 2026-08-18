"""Functions that communicate with the Aladin Open API."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests


API_URL = "https://www.aladin.co.kr/ttb/api/ItemList.aspx"
ITEM_LOOKUP_API_URL = "https://www.aladin.co.kr/ttb/api/ItemLookUp.aspx"
API_VERSION = "20131101"
PAGE_SIZE = 50
MAX_ITEMS_PER_CATEGORY = 200


def load_categories(path: Path) -> dict[str, int]:
    """Load a ``{category_name: category_id}`` mapping from JSON."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"카테고리 파일을 찾을 수 없습니다: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"카테고리 JSON 형식이 올바르지 않습니다: {path}") from exc

    if not isinstance(data, dict) or not data:
        raise ValueError('카테고리 파일은 {"카테고리명": 카테고리ID} 형식이어야 합니다.')

    categories: dict[str, int] = {}
    for name, category_id in data.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("카테고리명은 비어 있지 않은 문자열이어야 합니다.")
        try:
            category_id = int(category_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"카테고리 ID가 정수가 아닙니다: {name}={category_id}") from exc
        if category_id < 0:
            raise ValueError(f"카테고리 ID는 0 이상이어야 합니다: {name}")
        categories[name.strip()] = category_id

    return categories


def request_json(
    session: requests.Session,
    params: dict[str, Any],
    retries: int = 3,
    timeout: int = 30,
    api_url: str = API_URL,
) -> dict[str, Any]:
    """Call a JSON endpoint with a small exponential-backoff retry policy."""
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        try:
            response = session.get(api_url, params=params, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("API 응답이 JSON 객체가 아닙니다.")
            return payload
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt == retries:
                break
            time.sleep(2**attempt)

    raise RuntimeError(f"API 호출 실패: {last_error}") from last_error


def fetch_category_bestsellers(
    session: requests.Session,
    api_key: str,
    category_name: str,
    category_id: int,
    *,
    week: tuple[int, int, int] | None = None,
    delay: float = 0.3,
) -> list[dict[str, Any]]:
    """Fetch up to 200 bestseller items for one category via ItemList.aspx."""
    collected: list[dict[str, Any]] = []

    for page in range(1, MAX_ITEMS_PER_CATEGORY // PAGE_SIZE + 1):
        params: dict[str, Any] = {
            "TTBKey": api_key,
            "QueryType": "Bestseller",
            "SearchTarget": "Book",
            "CategoryId": category_id,
            "Start": page,
            "MaxResults": PAGE_SIZE,
            "Cover": "Mid",
            "Output": "JS",
            "Version": API_VERSION,
            "outofStockfilter": 1,
        }
        if week is not None:
            params.update({"Year": week[0], "Month": week[1], "Week": week[2]})

        payload = request_json(session, params)
        items = payload.get("item", [])
        if isinstance(items, dict):
            items = [items]
        if not isinstance(items, list):
            raise ValueError(f"{category_name}: item 응답 형식이 올바르지 않습니다.")

        for item in items:
            if isinstance(item, dict):
                row = dict(item)
                row["category_name"] = category_name
                row["category_id"] = category_id
                row["rank_in_category"] = len(collected) + 1
                collected.append(row)

        if len(items) < PAGE_SIZE or len(collected) >= MAX_ITEMS_PER_CATEGORY:
            break
        time.sleep(delay)

    return collected[:MAX_ITEMS_PER_CATEGORY]


def fetch_item_details(
    session: requests.Session,
    api_key: str,
    item_id: int,
) -> dict[str, Any]:
    """Fetch item descriptions and the API-provided review list."""
    params: dict[str, Any] = {
        "TTBKey": api_key,
        "ItemIdType": "ItemId",
        "ItemId": item_id,
        "Output": "JS",
        "Version": API_VERSION,
        "OptResult": "reviewList,fulldescription",
    }
    payload = request_json(session, params, api_url=ITEM_LOOKUP_API_URL)

    item = payload.get("item", [])
    if isinstance(item, list):
        item = item[0] if item else {}
    if not isinstance(item, dict):
        return {}

    sub_info = item.get("subInfo", {})
    if not isinstance(sub_info, dict):
        sub_info = {}

    return {
        "isbn": str(item.get("isbn") or "").strip(),
        "fullDescription": item.get("fullDescription", ""),
        "reviewList": sub_info.get("reviewList", []),
    }
