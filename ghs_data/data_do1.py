# 원저자와 번역자를 분리하되 기존 데이터는 유지한다.

import json
import re
from pathlib import Path

base_dir = Path(__file__).resolve().parent

input_path = (
    base_dir.parent
    / "output"
    / "aladin_bestsellers"
    / "all_bestsellers.json"
)

output_path = (
    base_dir.parent
    / "output"
    / "aladin_bestsellers"
    / "all_bestsellers_author_split.json"
)

# 역할이 표시된 이름 추출
role_pattern = re.compile(
    r"(?:^|,\s*)([^()]+?)\s*\((지은이|옮긴이)\)"
)


def split_author(author_text):
    """author 문자열에서 지은이와 옮긴이를 분리한다."""

    if not isinstance(author_text, str) or not author_text.strip():
        return None, None

    original_authors = []
    translators = []

    for name, role in role_pattern.findall(author_text):
        name = name.strip().strip(",").strip()

        if role == "지은이":
            original_authors.append(name)

        elif role == "옮긴이":
            translators.append(name)

    original_author = ", ".join(original_authors) or None
    translator = ", ".join(translators) or None

    return original_author, translator


# JSON 불러오기
with input_path.open("r", encoding="utf-8") as file:
    author_step1 = json.load(file)


# 기존 데이터는 유지하면서 새로운 필드 추가
processed_data = []

for row in author_step1:
    new_row = row.copy()

    original_author, translator = split_author(
        row.get("author")
    )

    new_row["original_author"] = original_author
    new_row["translator"] = translator

    processed_data.append(new_row)


# 결과 확인
print(f"전체 데이터 개수: {len(processed_data)}")

if processed_data:
    print(processed_data[0])


# 새로운 JSON 파일로 저장
with output_path.open("w", encoding="utf-8") as file:
    json.dump(
        processed_data,
        file,
        ensure_ascii=False,
        indent=2
    )

print(f"저장 완료: {output_path}")