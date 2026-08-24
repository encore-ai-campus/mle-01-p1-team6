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

CURRENT_DIR = Path(__file__).resolve().parent
BASE_DIR = CURRENT_DIR.parent
AGENT_DIR = BASE_DIR / "agent"
ENV_PATH = BASE_DIR / ".env"

if AGENT_DIR.exists() and str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from dotenv import load_dotenv

load_dotenv(ENV_PATH, override=False)
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
#   Tool이 반환한 itemId를 Supabase 원본에서 다시 조회한 뒤
#   실제 책이 만족해야 하는 조건입니다.
#
# constraint_metric=True:
#   이번에 추가한 "복합 조건 준수 정확도" 대상 문항입니다.
#   모든 반환 책이 result_conditions를 만족하고,
#   expected_result_count까지 맞아야 해당 문항이 PASS입니다.
#
# answer_match:
#   exact  -> 최종 답변 itemId와 Tool 결과가 정확히 같아야 함
#   subset -> 최종 답변 itemId가 Tool 결과의 부분집합이면 됨
#   none   -> 최종 답변 itemId 비교를 채점하지 않음
#

TEST_CASES = [
    # --------------------------------------------------------
    # 기존 평가: 카테고리 조건
    # --------------------------------------------------------
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
    # 신규 평가: 복합 조건 준수 정확도
    # --------------------------------------------------------
    # 이 문항들은 Tool 선택 자체보다,
    # 실제 반환된 책이 여러 조건을 동시에 만족하는지 확인합니다.
    {
        "case_id": "constraint_001",
        "query": "평점 8점 이상이고 2만원 이하인 책 5권 추천해줘.",
        "expected_tools": [
            {
                "name": "search_book",
                "args": {
                    "min_rating": 8,
                    "max_price": 20000,
                    "k": 5,
                },
                "strict_args": True,
                "result_conditions": {
                    "customerReviewRank": {"gte": 8},
                    "priceStandard": {"lte": 20000},
                },
            },
        ],
        # 이번 지표는 검색 결과의 조건 만족 여부가 핵심이므로
        # 최종 자연어 답변의 itemId 형식은 채점에서 제외합니다.
        "answer_match": "none",
        "constraint_metric": True,
        "expected_result_count": 5,
    },
    {
        "case_id": "constraint_002",
        "query": (
            "가격이 1만원 이상 3만원 이하이고 "
            "평점이 7점 이상인 책 3권 추천해줘."
        ),
        "expected_tools": [
            {
                "name": "search_book",
                "args": {
                    "min_price": 10000,
                    "max_price": 30000,
                    "min_rating": 7,
                    "k": 3,
                },
                "strict_args": True,
                "result_conditions": {
                    "priceStandard": {"gte": 10000, "lte": 30000},
                    "customerReviewRank": {"gte": 7},
                },
            },
        ],
        "answer_match": "none",
        "constraint_metric": True,
        "expected_result_count": 3,
    },
    {
        "case_id": "constraint_003",
        "query": "평점 6점 이상이고 2만 5천원 이하인 책 4권 추천해줘.",
        "expected_tools": [
            {
                "name": "search_book",
                "args": {
                    "min_rating": 6,
                    "max_price": 25000,
                    "k": 4,
                },
                "strict_args": True,
                "result_conditions": {
                    "customerReviewRank": {"gte": 6},
                    "priceStandard": {"lte": 25000},
                },
            },
        ],
        "answer_match": "none",
        "constraint_metric": True,
        "expected_result_count": 4,
    },
]

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
    "vector_search_descp": {"k": 3},
}


def current_turn_messages(result: dict[str, Any]) -> list[Any]:
    if not isinstance(result, dict):
        return []
    messages = result.get("messages", [])
    start_index = 0
    for index in range(len(messages) - 1, -1, -1):
        if getattr(messages[index], "type", "") == "human":
            start_index = index + 1
            break
    return messages[start_index:]


def extract_tool_calls(result: dict[str, Any]) -> list[dict[str, Any]]:
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
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            calls.append({"name": name, "args": args, "id": call_id})
    return calls


def parse_tool_rows(value: Any) -> list[dict[str, Any]]:
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


def extract_tool_results(result: dict[str, Any]) -> list[dict[str, Any]]:
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


def effective_tool_args(tool_name: str, raw_args: dict[str, Any]) -> dict[str, Any]:
    effective = dict(TOOL_DEFAULTS.get(tool_name, {}))
    effective.update(raw_args or {})
    return effective


def match_rule(actual: Any, rule: Any) -> bool:
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


def evaluate_tool_args(
    actual_call: dict[str, Any],
    expected_spec: dict[str, Any],
) -> tuple[bool, list[dict[str, Any]], list[str]]:
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
            if value is None:
                continue
            default_value = defaults.get(key, missing)
            if default_value is not missing and value == default_value:
                continue
            unexpected.append(f"{key}={value!r}")
    passed = all(check["passed"] for check in checks) and not unexpected
    return passed, checks, unexpected


def match_expected_tool_calls(
    expected_specs: list[dict[str, Any]],
    actual_calls: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any] | None]]:
    used: set[int] = set()
    matches: list[tuple[dict[str, Any], dict[str, Any] | None]] = []
    for spec in expected_specs:
        candidates = [
            (index, call)
            for index, call in enumerate(actual_calls)
            if index not in used and call.get("name") == spec.get("name")
        ]
        selected: tuple[int, dict[str, Any]] | None = None
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
    if not matched:
        matched = [
            result for result in tool_results if result.get("name") == tool_name
        ]
    rows: list[dict[str, Any]] = []
    for result in matched:
        rows.extend(result.get("rows", []))
    return rows


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


def fetch_original_books(item_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    if not item_ids:
        return {}
    normalized = list(dict.fromkeys(int(item_id) for item_id in item_ids))
    response = (
        supabase.table(TABLE_NAME).select("*").in_("itemId", normalized).execute()
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

        # 해당 필드 자체는 조건을 만족하는 후보가 있다면
        # "불일치"라고 잘못 표시하지 않습니다.
        if any(match_rule(value, rule) for value in actual_values):
            continue

        errors.append(
            f"{field}: 기대={rule!r}, 실제 후보={actual_values!r}"
        )

    # 각 필드는 개별적으로 맞지만 같은 한 행에서 모든 조건을
    # 동시에 만족하지 못한 특수한 중복 데이터 상황입니다.
    if not errors:
        errors.append("모든 조건을 동시에 만족하는 원본 행이 없음")

    return None, errors


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


def evaluate_answer_ids(
    answer: Any,
    tool_item_ids: list[int],
    mode: str,
) -> tuple[bool, list[int], list[int], list[int]]:
    answer_ids = extract_answer_item_ids(answer)
    tool_set = set(tool_item_ids)
    answer_set = set(answer_ids)
    unexpected = sorted(answer_set - tool_set)
    missing = sorted(tool_set - answer_set)
    if mode == "none":
        passed = True
    elif mode == "subset":
        passed = bool(answer_ids) and not unexpected
    else:
        passed = bool(answer_ids) and not unexpected and not missing
    return passed, answer_ids, unexpected, missing


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    print()
    print("=" * 78)
    print(f"CASE : {case['case_id']}")
    print(f"질문 : {case['query']}")
    print("=" * 78)

    # 평가 케이스마다 새 thread_id를 사용해 이전 대화 기억이 섞이지 않게 합니다.
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

    # 신규 지표용 누적값입니다.
    constraint_enabled = bool(case.get("constraint_metric", False))
    constraint_total_books = 0
    constraint_passed_books = 0

    for spec, call in matched_calls:
        if call is None:
            tool_result_pass = False
            continue

        rows = rows_for_call(call, tool_results)

        print()
        print(f"- {call.get('name')} 반환 책 수: {len(rows)}")

        if constraint_enabled:
            constraint_total_books += len(rows)

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

            # 같은 itemId가 여러 카테고리에 중복되어 있더라도
            # 원본 후보 중 하나가 모든 조건을 만족하면 해당 책은 PASS입니다.
            original, condition_errors = find_matching_original_book(
                original_candidates,
                conditions,
            )

            row_passed = original is not None
            tool_result_pass = tool_result_pass and row_passed

            if constraint_enabled and row_passed:
                constraint_passed_books += 1

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
                f"가격={display_original.get('priceStandard')} | "
                f"평점={display_original.get('customerReviewRank')} | "
                f"categories={categories}"
            )

            for error in condition_errors:
                print(f"     불일치: {error}")

    # --------------------------------------------------------
    # 4) 신규 지표: 복합 조건 준수 정확도
    # --------------------------------------------------------
    constraint_satisfaction: bool | None = None
    constraint_count_pass: bool | None = None

    if constraint_enabled:
        expected_count = case.get("expected_result_count")

        if expected_count is None:
            constraint_count_pass = True
        else:
            constraint_count_pass = constraint_total_books == expected_count

        all_books_satisfy = (
            constraint_total_books > 0
            and constraint_passed_books == constraint_total_books
        )

        constraint_satisfaction = all_books_satisfy and constraint_count_pass

        print()
        print("[4. 복합 조건 준수]")
        print(
            f"조건 만족 도서 : "
            f"{constraint_passed_books}/{constraint_total_books}"
        )
        if expected_count is not None:
            print(
                f"요청 개수      : 기대={expected_count}, "
                f"실제={constraint_total_books} "
                f"-> {'PASS' if constraint_count_pass else 'FAIL'}"
            )
        print(
            "결과           : "
            f"{'PASS' if constraint_satisfaction else 'FAIL'}"
        )

    # --------------------------------------------------------
    # 5) 최종 답변 vs Tool 결과
    # --------------------------------------------------------
    all_tool_rows: list[dict[str, Any]] = []
    for tool_result in tool_results:
        all_tool_rows.extend(tool_result.get("rows", []))

    all_tool_item_ids = unique_item_ids(all_tool_rows)
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

    print()
    print("[5. 최종 답변 vs Tool 결과]")
    print(f"비교 모드    : {answer_match}")
    print(f"Tool itemId : {all_tool_item_ids}")
    print(f"답변 itemId : {answer_item_ids}")

    if answer_match != "none":
        if unexpected_ids:
            print(f"Tool에 없는데 답변에 추가됨 : {unexpected_ids}")
        if missing_ids:
            print(f"Tool에는 있는데 답변에서 누락 : {missing_ids}")
    else:
        print("이번 문항은 최종 답변 itemId 비교를 채점하지 않음")

    print(f"결과 : {'PASS' if answer_pass else 'FAIL'}")

    print()
    print("[Agent 최종 답변]")
    print("-" * 78)
    print(answer)

    # 신규 복합 조건 케이스는 새 지표까지 통과해야 CASE PASS입니다.
    case_checks = [
        tool_selection_pass,
        tool_args_pass,
        tool_result_pass,
        answer_pass,
    ]
    if constraint_enabled:
        case_checks.append(bool(constraint_satisfaction))

    case_pass = all(case_checks)

    print()
    print("-" * 78)
    print(f"도구 선택       : {'PASS' if tool_selection_pass else 'FAIL'}")
    print(f"도구 입력       : {'PASS' if tool_args_pass else 'FAIL'}")
    print(f"검색 결과       : {'PASS' if tool_result_pass else 'FAIL'}")
    if constraint_enabled:
        print(
            "복합 조건 준수  : "
            f"{'PASS' if constraint_satisfaction else 'FAIL'}"
        )
    print(f"최종 답변 충실도: {'PASS' if answer_pass else 'FAIL'}")
    print(f"CASE 최종       : {'PASS' if case_pass else 'FAIL'}")

    return {
        "case_id": case["case_id"],
        "tool_selection": tool_selection_pass,
        "tool_args": tool_args_pass,
        "tool_results": tool_result_pass,
        "answer_fidelity": answer_pass,
        "constraint_satisfaction": constraint_satisfaction,
        "constraint_passed_books": constraint_passed_books,
        "constraint_total_books": constraint_total_books,
        "constraint_count_pass": constraint_count_pass,
        "case_pass": case_pass,
    }


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
            print(f"[ERROR] {case['case_id']}: {type(error).__name__}: {error}")
            results.append(
                {
                    "case_id": case["case_id"],
                    "tool_selection": False,
                    "tool_args": False,
                    "tool_results": False,
                    "answer_fidelity": False,
                    "constraint_satisfaction": (
                        False if case.get("constraint_metric") else None
                    ),
                    "constraint_passed_books": 0,
                    "constraint_total_books": 0,
                    "constraint_count_pass": (
                        False if case.get("constraint_metric") else None
                    ),
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

    constraint_results = [
        result
        for result in results
        if result.get("constraint_satisfaction") is not None
    ]
    constraint_total = len(constraint_results)
    constraint_passed = sum(
        bool(result["constraint_satisfaction"])
        for result in constraint_results
    )

    print()
    print("=" * 78)
    print("전체 평가 결과")
    print("=" * 78)
    for label, passed in metrics.items():
        print(f"{label:<16} : {passed}/{total} ({rate(passed, total)})")

    print("-" * 78)
    print(
        f"{'복합 조건 준수 정확도':<16} "
        f": {constraint_passed}/{constraint_total} "
        f"({rate(constraint_passed, constraint_total)})"
    )
    print(
        "  계산 기준: 반환된 모든 책이 가격/평점 조건을 만족하고 "
        "요청한 권수까지 맞으면 해당 문항 1점"
    )


if __name__ == "__main__":
    main()
