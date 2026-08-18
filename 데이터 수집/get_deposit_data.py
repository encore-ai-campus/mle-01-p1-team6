import os
import json
import time
from pathlib import Path

import requests
import pandas as pd
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

API_KEY = os.getenv("FINLIFE_AUTH")

if not API_KEY:
    raise RuntimeError(
        ".env 파일에 FINLIFE_AUTH가 설정되어 있지 않습니다."
    )


API_URL = (
    "https://finlife.fss.or.kr/"
    "finlifeapi/depositProductsSearch.json"
)


GROUPS = {
    "020000": "은행",
    "030200": "여신전문금융",
    "030300": "저축은행",
    "050000": "보험",
    "060000": "금융투자",
}


def get_page(group_code, page_no):
    params = {
        "auth": API_KEY,
        "topFinGrpNo": group_code,
        "pageNo": page_no,
    }

    response = requests.get(
        API_URL,
        params=params,
        timeout=30,
    )
    response.raise_for_status()

    result = response.json().get("result", {})

    if result.get("err_cd") != "000":
        raise RuntimeError(
            f"API 오류 {result.get('err_cd')}: "
            f"{result.get('err_msg')}"
        )

    return result


def get_all_deposits():
    all_products = []
    all_options = []

    for group_code, group_name in GROUPS.items():
        page_no = 1

        while True:
            print(
                f"[조회 중] {group_name} "
                f"({group_code}) - {page_no}페이지"
            )

            result = get_page(group_code, page_no)

            products = result.get("baseList", [])
            options = result.get("optionList", [])

            for product in products:
                product["topFinGrpNo"] = group_code
                product["topFinGrpNm"] = group_name

            for option in options:
                option["topFinGrpNo"] = group_code
                option["topFinGrpNm"] = group_name

            all_products.extend(products)
            all_options.extend(options)

            max_page_no = int(result.get("max_page_no", 1))

            if page_no >= max_page_no:
                break

            page_no += 1
            time.sleep(0.2)

    return all_products, all_options


def save_data(products, options):
    output_dir = BASE_DIR / "output"
    output_dir.mkdir(exist_ok=True)

    with open(
        output_dir / "정기예금_전체.json",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            {
                "baseList": products,
                "optionList": options,
            },
            file,
            ensure_ascii=False,
            indent=2,
        )

    product_df = pd.json_normalize(products)
    option_df = pd.json_normalize(options)

    product_df.to_csv(
        output_dir / "정기예금_상품정보.csv",
        index=False,
        encoding="utf-8-sig",
    )

    option_df.to_csv(
        output_dir / "정기예금_금리정보.csv",
        index=False,
        encoding="utf-8-sig",
    )

    if not product_df.empty and not option_df.empty:
        merge_keys = [
            "topFinGrpNo",
            "dcls_month",
            "fin_co_no",
            "fin_prdt_cd",
        ]

        merged_df = option_df.merge(
            product_df,
            on=merge_keys,
            how="left",
            suffixes=("_금리", "_상품"),
        )

        merged_df.to_csv(
            output_dir / "정기예금_상품_금리_통합.csv",
            index=False,
            encoding="utf-8-sig",
        )


def main():
    products, options = get_all_deposits()
    save_data(products, options)

    print()
    print("조회가 완료되었습니다.")
    print(f"상품 정보: {len(products):,}개")
    print(f"금리 옵션: {len(options):,}개")
    print(f"저장 위치: {BASE_DIR / 'output'}")


if __name__ == "__main__":
    main()
