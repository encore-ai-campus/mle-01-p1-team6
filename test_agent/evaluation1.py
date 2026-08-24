# test_agent/evaluation.py
from __future__ import annotations

import ast
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from uuid import uuid4


# ============================================================
# 0. 프로젝트 경로
# ============================================================
#
# mle-01-p1-team6/
# ├─ .env
# ├─ agent/
# │  ├─ book_agent.py
# │  ├─ db.py
# │  └─ ...
# └─ test_agent/
#    └─ evaluation.py
#

CURRENT_DIR = Path(__file__).resolve().parent

# 실제 프로젝트에서는 evaluation.py가 test_agent/ 안에 있으므로
# 한 단계 위가 프로젝트 루트입니다.
BASE_DIR = CURRENT_DIR.parent
AGENT_DIR = BASE_DIR / "agent"
ENV_PATH = BASE_DIR / ".env"

# /mnt/data에서 문법 검사용으로 열었을 때와 실제 프로젝트에서 실행할 때를
# 모두 고려해, agent 폴더가 실제로 존재하는 경우에만 경로를 추가합니다.
if AGENT_DIR.exists() and str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


# ============================================================
# 1. .env 로드 후 기존 Agent import
# ============================================================

from dotenv import load_dotenv

load_dotenv(ENV_PATH, override=False)

# 실제 프로젝트의 기존 Agent와 동일한 Supabase client를 그대로 사용합니다.
# 별도의 Agent나 별도의 Supabase 연결을 만들지 않습니다.
from book_agent import run_agent, supabase


TABLE_NAME = "books"


# ============================================================
# 2. 평가셋
# ============================================================
#
# expected_tools:
#   어떤 도구를 어떤 인자로 호출해야 하는지 평가합니다.
#
# result_conditions:
#   해당 도구가 반환한 itemId를 Supabase 원본에서 다시 조회한 뒤
#   만족해야 하는 조건입니다.
#
# answer_match:
#   exact  -> 최종 답변의 itemId가 Tool 결과와 정확히 같아야 함
#   subset -> 최종 답변의 itemId가 Tool 결과의 부분집합이면 됨
#   none   -> 최종 답변 itemId 비교를 하지 않음
#

TEST_CASES = [
    {
        "case_id": "category_001",
        "query": (
            "역사책 중에서 추천해줘. "
            "해당 책의 itemId를 명기해줘."
        ),
        "expected_tools": [
            {
                "name": "search_book",
                "args": {
                    "category_name": "역사",
                    "k": 3,
                },
                "strict_args": True,
                "result_conditions": {
                    "category_name": "역사",
                },
            },
        ],
        "answer_match": "exact",
    },

    # --------------------------------------------------------
    # 추가 예시 1: 가격 조건
    # --------------------------------------------------------
    # {
    #     "case_id": "price_001",
    #     "query": "2만원 이하인 책을 3권 추천하고 itemId도 알려줘.",
    #     "expected_tools": [
    #         {
    #             "name": "search_book",
    #             "args": {
    #                 "max_price": 20000,
    #                 "k": 3,
    #             },
    #             "strict_args": True,
    #             "result_conditions": {
    #                 "priceStandard": {"lte": 20000},
    #             },
    #         },
    #     ],
    #     "answer_match": "exact",
    # },

    # --------------------------------------------------------
    # 추가 예시 2: 작가 조건
    # --------------------------------------------------------
    # {
    #     "case_id": "author_001",
    #     "query": "유시민 작가의 책을 3권 추천하고 itemId도 알려줘.",
    #     "expected_tools": [
    #         {
    #             "name": "search_book",
    #             "args": {
    #                 "author": "유시민",
    #                 "k": 3,
    #             },
    #             "strict_args": True,
    #             "result_conditions": {
    #                 "author": {"contains": "유시민"},
    #             },
    #         },
    #     ],
    #     "answer_match": "exact",
    # },

    # --------------------------------------------------------
    # 추가 예시 3: 의미 검색
    # --------------------------------------------------------
    # 의미 검색의 query는 LLM이 자연스럽게 재작성할 수 있으므로
    # 문자열 전체 일치 대신 nonempty 조건만 검사합니다.
    # {
    #     "case_id": "vector_001",
    #     "query": "마음이 지칠 때 읽기 좋은 따뜻한 책 3권과 itemId를 알려줘.",
    #     "expected_tools": [
    #         {
    #             "name": "vector_search_descp",
    #             "args": {
    #                 "query": {"nonempty": True},
    #                 "k": 3,
    #             },
    #             "strict_args": True,
    #             "result_conditions": {},
    #         },
    #     ],
    #     "answer_match": "exact",
    # },
]


# ============================================================
# 3. 실제 Agent 도구의 기본값
# ============================================================
# book_agent.py의 SearchBookInput / VectorSearchInput 기본값과 맞춥니다.
# AIMessage.tool_calls에는 기본값이 생략될 수 있으므로
# "실제로 함수에 적용되는 값"을 계산하기 위해 사용합니다.

TOOL_DEFAULTS: dict[str, dict[str, Any]] = {
    "search_book": {
        "category_name": None,
        "author": None,
        "min_price": None,
        "max_price": None,
        "min_rating": None,
        "max_rating": None,
        "k": 3,
    },
    "vector_search_descp": {
        "k": 3,
    },
}


# ============================================================
# 4. 현재 질문에서 생성된 메시지만 가져오기
# ============================================================

def current_turn_messages(result: dict[str, Any]) -> list[Any]:
    """
    Agent에 memory가 있으므로 result 안에 이전 대화가 남아 있을 수 있습니다.
    가장 최근 HumanMessage 뒤의 메시지만 이번 평가 대상으로 사용합니다.
    """

    if not isinstance(result, dict):
        return []

    messages = result.get("messages", [])
    start_index = 0

    for index in range(len(messages) - 1, -1, -1):
        if getattr(messages[index], "type", "") == "human":
            start_index = index + 1
            break

    return messages[start_index:]


# ============================================================
# 5. AIMessage의 Tool Call 추출
# ============================================================

def extract_tool_calls(result: dict[str, Any]) -> list[dict[str, Any]]:
    """
    현재 질문에서 AI가 실제로 어떤 Tool을 어떤 args로 호출했는지 추출합니다.
    """

    calls: list[dict[str, Any]] = []

    for message in current_turn_messages(result):
        raw_calls = getattr(message, "tool_calls", None) or []

        for call in raw_calls:
            if isinstance(call, dict):
                name = call.get("name")
                args = call.get("args") or {}
                call_id = call.get("id")
            else:
                name = getattr(call, "name", None)
                args = getattr(call, "args", {}) or {}
                call_id = getattr(call, "id", None)

            # 혹시 args가 문자열로 들어오는 버전도 처리
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}

            calls.append(
                {
                    "name": name,
                    "args": args,
                    "id": call_id,
                }
            )

    return calls


# ============================================================
# 6. ToolMessage 반환값을 책 행 목록으로 변환
# ============================================================

def parse_tool_rows(value: Any) -> list[dict[str, Any]]:
    """
    ToolMessage.content가 list / dict / JSON 문자열 / Python 문자열 중
    어떤 형태이든 itemId를 가진 책 행을 찾아냅니다.

    book_agent.extract_book_rows()와 달리 cover_url 유무로 걸러내지 않습니다.
    평가에서는 실제 검색 결과 전체가 필요하기 때문입니다.
    """

    if value is None:
        return []

    if isinstance(value, list):
        rows: list[dict[str, Any]] = []
        for item in value:
            rows.extend(parse_tool_rows(item))
        return rows

    if isinstance(value, dict):
        if "itemId" in value:
            return [value]

        rows: list[dict[str, Any]] = []
        for nested in value.values():
            rows.extend(parse_tool_rows(nested))
        return rows

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []

        for parser in (json.loads, ast.literal_eval):
            try:
                parsed = parser(text)
            except (ValueError, SyntaxError, TypeError, json.JSONDecodeError):
                continue

            return parse_tool_rows(parsed)

    return []


# ============================================================
# 7. ToolMessage 추출
# ============================================================

def extract_tool_results(result: dict[str, Any]) -> list[dict[str, Any]]:
    """
    현재 질문에서 실행된 ToolMessage와 반환 책 목록을 가져옵니다.
    tool_call_id를 보존하여 AIMessage.tool_calls와 연결할 수 있게 합니다.
    """

    tool_results: list[dict[str, Any]] = []

    for message in current_turn_messages(result):
        if getattr(message, "type", "") != "tool":
            continue

        tool_results.append(
            {
                "name": getattr(message, "name", None),
                "tool_call_id": getattr(message, "tool_call_id", None),
                "rows": parse_tool_rows(getattr(message, "content", None)),
            }
        )

    return tool_results


# ============================================================
# 8. 실제 적용되는 Tool args 계산
# ============================================================

def effective_tool_args(
    tool_name: str,
    raw_args: dict[str, Any],
) -> dict[str, Any]:
    """
    Tool call에 k가 생략돼도 실제 함수에서는 기본값 k=3이 적용됩니다.
    그 실제 적용값 기준으로 평가합니다.
    """

    effective = dict(TOOL_DEFAULTS.get(tool_name, {}))
    effective.update(raw_args or {})
    return effective


# ============================================================
# 9. 공통 조건 비교
# ============================================================

def match_rule(actual: Any, rule: Any) -> bool:
    """
    rule이 일반 값이면 정확 일치합니다.

    dict이면 다음 연산자를 사용할 수 있습니다.
      {"eq": 값}
      {"ne": 값}
      {"gte": 값}
      {"lte": 값}
      {"contains": 문자열}
      {"one_of": [값1, 값2]}
      {"nonempty": True}
    """

    if not isinstance(rule, dict):
        return actual == rule

    if "nonempty" in rule:
        want_nonempty = bool(rule["nonempty"])
        is_nonempty = actual is not None and str(actual).strip() != ""
        if is_nonempty != want_nonempty:
            return False

    if "eq" in rule and actual != rule["eq"]:
        return False

    if "ne" in rule and actual == rule["ne"]:
        return False

    if "gte" in rule:
        if actual is None or actual < rule["gte"]:
            return False

    if "lte" in rule:
        if actual is None or actual > rule["lte"]:
            return False

    if "contains" in rule:
        if actual is None or str(rule["contains"]) not in str(actual):
            return False

    if "one_of" in rule and actual not in rule["one_of"]:
        return False

    return True


# ============================================================
# 10. Tool args 평가
# ============================================================

def evaluate_tool_args(
    actual_call: dict[str, Any],
    expected_spec: dict[str, Any],
) -> tuple[bool, list[dict[str, Any]], list[str]]:
    """
    기대한 인자와 실제 Tool call 인자를 비교합니다.

    strict_args=True이면 질문에 없던 의미 있는 필터를 Agent가 임의로 추가한 것도
    실패로 처리합니다. 단, None이나 원래 기본값과 같은 값은 문제로 보지 않습니다.
    """

    tool_name = expected_spec["name"]
    raw_args = actual_call.get("args") or {}
    effective_args = effective_tool_args(tool_name, raw_args)
    expected_args = expected_spec.get("args", {})

    checks: list[dict[str, Any]] = []

    for key, rule in expected_args.items():
        actual_value = effective_args.get(key)
        passed = match_rule(actual_value, rule)

        checks.append(
            {
                "key": key,
                "expected": rule,
                "actual": actual_value,
                "source": "전달값" if key in raw_args else "기본값",
                "passed": passed,
            }
        )

    unexpected: list[str] = []

    if expected_spec.get("strict_args", True):
        defaults = TOOL_DEFAULTS.get(tool_name, {})
        missing = object()

        for key, value in raw_args.items():
            if key in expected_args:
                continue

            # None은 의미 있는 추가 필터가 아님
            if value is None:
                continue

            default_value = defaults.get(key, missing)

            # 명시했더라도 원래 기본값과 같다면 허용
            if default_value is not missing and value == default_value:
                continue

            unexpected.append(f"{key}={value!r}")

    passed = all(check["passed"] for check in checks) and not unexpected
    return passed, checks, unexpected


# ============================================================
# 11. 기대 Tool spec과 실제 Tool call 연결
# ============================================================

def match_expected_tool_calls(
    expected_specs: list[dict[str, Any]],
    actual_calls: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any] | None]]:
    """
    같은 Tool을 여러 번 호출하는 경우까지 고려해 기대 spec과 실제 call을 매칭합니다.
    가능한 경우 args까지 통과하는 call을 우선 선택합니다.
    """

    used: set[int] = set()
    matches: list[tuple[dict[str, Any], dict[str, Any] | None]] = []

    for spec in expected_specs:
        candidates = [
            (index, call)
            for index, call in enumerate(actual_calls)
            if index not in used and call.get("name") == spec.get("name")
        ]

        selected: tuple[int, dict[str, Any]] | None = None

        # 이름이 같은 후보 중 args까지 맞는 call을 우선 선택
        for candidate in candidates:
            args_passed, _, _ = evaluate_tool_args(candidate[1], spec)
            if args_passed:
                selected = candidate
                break

        if selected is None and candidates:
            selected = candidates[0]

        if selected is None:
            matches.append((spec, None))
        else:
            used.add(selected[0])
            matches.append((spec, selected[1]))

    return matches


# ============================================================
# 12. 특정 Tool call에 대응하는 ToolMessage rows
# ============================================================

def rows_for_call(
    call: dict[str, Any],
    tool_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    call_id = call.get("id")
    tool_name = call.get("name")

    matched: list[dict[str, Any]] = []

    if call_id:
        matched = [
            result
            for result in tool_results
            if result.get("tool_call_id") == call_id
        ]

    # tool_call_id가 없는 환경에 대한 fallback
    if not matched:
        matched = [
            result
            for result in tool_results
            if result.get("name") == tool_name
        ]

    rows: list[dict[str, Any]] = []
    for result in matched:
        rows.extend(result.get("rows", []))

    return rows


# ============================================================
# 13. itemId 정규화
# ============================================================

def normalize_item_id(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def unique_item_ids(rows: list[dict[str, Any]]) -> list[int]:
    result: list[int] = []
    seen: set[int] = set()

    for row in rows:
        item_id = normalize_item_id(row.get("itemId"))
        if item_id is None or item_id in seen:
            continue
        seen.add(item_id)
        result.append(item_id)

    return result


# ============================================================
# 14. Supabase 원본 조회
# ============================================================

def fetch_original_books(item_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    """
    Tool이 반환한 itemId를 Supabase books 원본에서 다시 조회합니다.
    itemId는 PostgreSQL int8이므로 Python int로 전달합니다.

    같은 itemId가 여러 카테고리 행에 중복되어 있을 수 있으므로
    한 행으로 덮어쓰지 않고 itemId별 원본 행 전체를 보존합니다.
    """

    if not item_ids:
        return {}

    normalized = list(dict.fromkeys(int(item_id) for item_id in item_ids))

    response = (
        supabase
        .table(TABLE_NAME)
        .select("*")
        .in_("itemId", normalized)
        .execute()
    )

    grouped: dict[int, list[dict[str, Any]]] = {}

    for book in (response.data or []):
        item_id = normalize_item_id(book.get("itemId"))
        if item_id is None:
            continue

        grouped.setdefault(item_id, []).append(book)

    return grouped


def find_matching_original_book(
    originals: list[dict[str, Any]],
    conditions: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[str]]:
    """
    같은 itemId의 Supabase 원본 행들 중에서 result_conditions를
    모두 만족하는 행 하나를 찾습니다.

    예를 들어 같은 itemId가 ['소설', '역사'] 두 카테고리에 존재하고
    기대 조건이 category_name='역사'라면 PASS가 됩니다.
    """

    for original in originals:
        condition_errors: list[str] = []

        for field, rule in conditions.items():
            actual_value = original.get(field)
            if not match_rule(actual_value, rule):
                condition_errors.append(
                    f"{field}: 기대={rule!r}, 실제={actual_value!r}"
                )

        if not condition_errors:
            return original, []

    errors: list[str] = []
    for field, rule in conditions.items():
        actual_values = list(
            dict.fromkeys(original.get(field) for original in originals)
        )
        errors.append(
            f"{field}: 기대={rule!r}, 실제 후보={actual_values!r}"
        )

    return None, errors


# ============================================================
# 15. 최종 답변에서 itemId 추출
# ============================================================
# 최종 답변 충실도를 보기 위한 용도입니다.
# Tool 결과 자체의 정답 판정은 이 정규식에 의존하지 않습니다.

ITEM_ID_PATTERN = re.compile(
    r"\*{0,2}\s*itemId\s*\*{0,2}\s*[:：]\s*`?(\d+)`?",
    flags=re.IGNORECASE,
)


def extract_answer_item_ids(answer: Any) -> list[int]:
    if isinstance(answer, str):
        text = answer
    else:
        content = getattr(answer, "content", answer)
        text = str(content)

    result: list[int] = []
    seen: set[int] = set()

    for raw in ITEM_ID_PATTERN.findall(text):
        item_id = int(raw)
        if item_id in seen:
            continue
        seen.add(item_id)
        result.append(item_id)

    return result


# ============================================================
# 16. 최종 답변 vs Tool 검색 결과 비교
# ============================================================

def evaluate_answer_ids(
    answer: Any,
    tool_item_ids: list[int],
    mode: str,
) -> tuple[bool, list[int], list[int], list[int]]:
    """
    반환값:
      passed
      answer_ids
      unexpected_ids  -> Tool에 없는데 최종 답변에 등장
      missing_ids     -> Tool에는 있는데 최종 답변에서 누락
    """

    answer_ids = extract_answer_item_ids(answer)

    tool_set = set(tool_item_ids)
    answer_set = set(answer_ids)

    unexpected = sorted(answer_set - tool_set)
    missing = sorted(tool_set - answer_set)

    if mode == "none":
        passed = True
    elif mode == "subset":
        passed = bool(answer_ids) and not unexpected
    else:  # exact
        passed = bool(answer_ids) and not unexpected and not missing

    return passed, answer_ids, unexpected, missing


# ============================================================
# 17. 한 평가 케이스 실행
# ============================================================

def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    print()
    print("=" * 78)
    print(f"CASE : {case['case_id']}")
    print(f"질문 : {case['query']}")
    print("=" * 78)

    # 평가 케이스 간 단기기억 오염을 막기 위해 매번 새로운 thread_id 사용
    thread_id = f"eval-{case['case_id']}-{uuid4().hex}"

    answer, result = run_agent(
        case["query"],
        thread_id=thread_id,
    )

    actual_calls = extract_tool_calls(result)
    tool_results = extract_tool_results(result)
    expected_specs = case.get("expected_tools", [])

    # --------------------------------------------------------
    # 1) 도구 선택 평가
    # --------------------------------------------------------

    expected_names = [spec["name"] for spec in expected_specs]
    actual_names = [call.get("name") for call in actual_calls]

    tool_selection_pass = Counter(actual_names) == Counter(expected_names)

    print()
    print("[1. 도구 선택]")
    print(f"기대 : {expected_names}")
    print(f"실제 : {actual_names}")
    print(f"결과 : {'PASS' if tool_selection_pass else 'FAIL'}")

    # --------------------------------------------------------
    # 2) 도구 입력 평가
    # --------------------------------------------------------

    print()
    print("[2. 도구 입력]")

    matched_calls = match_expected_tool_calls(expected_specs, actual_calls)
    tool_args_pass = True

    for spec, call in matched_calls:
        print()
        print(f"- 기대 도구: {spec['name']}")

        if call is None:
            print("  실제 호출: 없음")
            print("  결과     : FAIL")
            tool_args_pass = False
            continue

        print(f"  실제 호출: {call.get('name')}")
        print(f"  raw args : {call.get('args')}")

        args_passed, checks, unexpected = evaluate_tool_args(call, spec)

        for check in checks:
            print(
                f"  {check['key']}: "
                f"기대={check['expected']!r}, "
                f"실제={check['actual']!r} "
                f"({check['source']}) "
                f"-> {'PASS' if check['passed'] else 'FAIL'}"
            )

        if unexpected:
            print(f"  불필요한 추가 인자: {unexpected}")

        print(f"  도구 인자 결과: {'PASS' if args_passed else 'FAIL'}")
        tool_args_pass = tool_args_pass and args_passed

    # --------------------------------------------------------
    # 3) Tool 검색 결과 + Supabase 원본 평가
    # --------------------------------------------------------

    print()
    print("[3. Tool 검색 결과 / Supabase 원본 검증]")

    tool_result_pass = True
    evaluated_tool_rows: list[dict[str, Any]] = []

    for spec, call in matched_calls:
        if call is None:
            tool_result_pass = False
            continue

        rows = rows_for_call(call, tool_results)
        evaluated_tool_rows.extend(rows)

        print()
        print(f"- {call.get('name')} 반환 책 수: {len(rows)}")

        if not rows:
            print("  ToolMessage에서 책 결과를 찾지 못함 -> FAIL")
            tool_result_pass = False
            continue

        item_ids = unique_item_ids(rows)
        originals = fetch_original_books(item_ids)
        conditions = spec.get("result_conditions", {})

        for index, row in enumerate(rows, start=1):
            item_id = normalize_item_id(row.get("itemId"))

            if item_id is None:
                print(f"  {index}. itemId 없음/형식 오류 -> FAIL")
                tool_result_pass = False
                continue

            original_candidates = originals.get(item_id, [])

            if not original_candidates:
                print(f"  {index}. itemId={item_id} | Supabase 원본 없음 -> FAIL")
                tool_result_pass = False
                continue

            original, condition_errors = find_matching_original_book(
                original_candidates,
                conditions,
            )

            row_passed = original is not None
            tool_result_pass = tool_result_pass and row_passed

            display_original = original or original_candidates[0]
            categories = list(
                dict.fromkeys(
                    candidate.get("category_name")
                    for candidate in original_candidates
                )
            )

            print(
                f"  {index}. {'PASS' if row_passed else 'FAIL'} | "
                f"itemId={item_id} | "
                f"제목={display_original.get('title')} | "
                f"categories={categories}"
            )

            for error in condition_errors:
                print(f"     불일치: {error}")

    # 실제 호출된 모든 ToolMessage의 itemId를 최종 답변 비교 기준으로 사용
    all_tool_rows: list[dict[str, Any]] = []
    for tool_result in tool_results:
        all_tool_rows.extend(tool_result.get("rows", []))

    all_tool_item_ids = unique_item_ids(all_tool_rows)

    # --------------------------------------------------------
    # 4) 최종 답변 충실도 평가
    # --------------------------------------------------------

    print()
    print("[4. 최종 답변 vs Tool 결과]")

    answer_match = case.get("answer_match", "exact")

    (
        answer_pass,
        answer_item_ids,
        unexpected_ids,
        missing_ids,
    ) = evaluate_answer_ids(
        answer,
        all_tool_item_ids,
        answer_match,
    )

    print(f"Tool itemId : {all_tool_item_ids}")
    print(f"답변 itemId : {answer_item_ids}")

    if unexpected_ids:
        print(f"Tool에 없는데 답변에 추가됨 : {unexpected_ids}")

    if missing_ids:
        print(f"Tool에는 있는데 답변에서 누락 : {missing_ids}")

    print(f"결과 : {'PASS' if answer_pass else 'FAIL'}")

    # --------------------------------------------------------
    # 최종 답변 출력
    # --------------------------------------------------------

    print()
    print("[Agent 최종 답변]")
    print("-" * 78)
    print(answer)

    # --------------------------------------------------------
    # 케이스 종합
    # --------------------------------------------------------

    case_pass = all(
        [
            tool_selection_pass,
            tool_args_pass,
            tool_result_pass,
            answer_pass,
        ]
    )

    print()
    print("-" * 78)
    print(f"도구 선택       : {'PASS' if tool_selection_pass else 'FAIL'}")
    print(f"도구 입력       : {'PASS' if tool_args_pass else 'FAIL'}")
    print(f"검색 결과       : {'PASS' if tool_result_pass else 'FAIL'}")
    print(f"최종 답변 충실도: {'PASS' if answer_pass else 'FAIL'}")
    print(f"CASE 최종       : {'PASS' if case_pass else 'FAIL'}")

    return {
        "case_id": case["case_id"],
        "tool_selection": tool_selection_pass,
        "tool_args": tool_args_pass,
        "tool_results": tool_result_pass,
        "answer_fidelity": answer_pass,
        "case_pass": case_pass,
    }


# ============================================================
# 18. 전체 평가 실행
# ============================================================

def rate(count: int, total: int) -> str:
    if total == 0:
        return "0.00%"
    return f"{count / total:.2%}"


def main() -> None:
    print()
    print("=" * 78)
    print("도서 추천 Agent 평가 시작")
    print("=" * 78)
    print(f"프로젝트 루트 : {BASE_DIR}")
    print(f"Agent 폴더    : {AGENT_DIR}")
    print(f"평가 문항 수  : {len(TEST_CASES)}")

    results: list[dict[str, Any]] = []

    for case in TEST_CASES:
        try:
            results.append(evaluate_case(case))
        except Exception as error:
            print()
            print("!" * 78)
            print(f"[ERROR] {case['case_id']} 실행 중 오류")
            print(f"{type(error).__name__}: {error}")
            print("!" * 78)

            results.append(
                {
                    "case_id": case["case_id"],
                    "tool_selection": False,
                    "tool_args": False,
                    "tool_results": False,
                    "answer_fidelity": False,
                    "case_pass": False,
                }
            )

    total = len(results)

    metrics = {
        "도구 선택": sum(r["tool_selection"] for r in results),
        "도구 입력": sum(r["tool_args"] for r in results),
        "검색 결과": sum(r["tool_results"] for r in results),
        "최종 답변 충실도": sum(r["answer_fidelity"] for r in results),
        "전체 케이스": sum(r["case_pass"] for r in results),
    }

    print()
    print("=" * 78)
    print("전체 평가 결과")
    print("=" * 78)

    for label, passed in metrics.items():
        print(
            f"{label:<16} "
            f": {passed}/{total} "
            f"({rate(passed, total)})"
        )


if __name__ == "__main__":
    main()
