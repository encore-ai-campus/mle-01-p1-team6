from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import requests

from aladin_bestsellers import fetch_item_details


SOURCE_PATH = Path("output/all.csv")
OUTPUT_PATH = Path("output/all_filled.csv")


def is_blank(series: pd.Series) -> pd.Series:
    return series.isna() | (series.astype(str).str.strip() == "")


def main() -> int:
    api_key = os.getenv("BOOK_API_KEY")
    if not api_key:
        raise SystemExit("BOOK_API_KEY 환경변수가 없습니다.")

    df = pd.read_csv(SOURCE_PATH)
    missing_mask = is_blank(df["fullDescription"])
    missing_count = int(missing_mask.sum())

    if missing_count == 0:
        df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
        print(f"No missing fullDescription values. Wrote {OUTPUT_PATH}")
        return 0

    session = requests.Session()
    session.headers.update({"User-Agent": "aladin-bestseller-backfill/1.0"})

    detail_cache: dict[int, dict[str, str]] = {}
    filled_from_api = 0
    filled_from_description = 0

    for idx in df.index[missing_mask]:
        item_id_raw = df.at[idx, "itemId"]
        try:
            item_id = int(item_id_raw)
        except (TypeError, ValueError):
            item_id = 0

        replacement = ""
        if item_id > 0:
            if item_id not in detail_cache:
                try:
                    detail_cache[item_id] = fetch_item_details(session, api_key, item_id)
                except Exception:
                    detail_cache[item_id] = {}

            details = detail_cache.get(item_id, {})
            replacement = (
                str(details.get("fullDescription", "")).strip()
                or str(details.get("publisherDescription", "")).strip()
            )
            if replacement:
                filled_from_api += 1

        if not replacement:
            description = df.at[idx, "description"]
            if pd.notna(description) and str(description).strip():
                replacement = str(description).strip()
                filled_from_description += 1

        if replacement:
            df.at[idx, "fullDescription"] = replacement

    remaining_missing = int(is_blank(df["fullDescription"]).sum())
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    print(f"source: {SOURCE_PATH}")
    print(f"missing before: {missing_count}")
    print(f"filled from api: {filled_from_api}")
    print(f"filled from description: {filled_from_description}")
    print(f"still missing: {remaining_missing}")
    print(f"wrote: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
