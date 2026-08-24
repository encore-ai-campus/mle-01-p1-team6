from pathlib import Path
import sys

import pandas as pd
import pytest

TEST_DIR = Path(__file__).resolve().parent
if str(TEST_DIR) not in sys.path:
    sys.path.insert(0, str(TEST_DIR))

from evaluation import (
    calculate_answer_grounding,
    calculate_comprehensive_score,
    calculate_count_fulfillment,
    calculate_metrics,
    extract_agent_observation,
    unique_ranked_rows,
)


def test_calculate_metrics_uses_rank_of_first_relevant_item():
    metrics = calculate_metrics([101, 102, 103, 104], {102, 104, 999}, k=4)

    assert metrics["hit_at_k"] == 1.0
    assert metrics["precision_at_k"] == 2 / 4
    assert metrics["recall_at_k"] == 2 / 3
    assert metrics["mrr_at_k"] == 1 / 2


def test_unique_ranked_rows_keeps_first_item_id_order():
    rows = [
        {"itemId": 11, "title": "A"},
        {"itemId": 12, "title": "B"},
        {"itemId": 11, "title": "A duplicate"},
        {"itemId": None, "title": "missing"},
    ]

    result = unique_ranked_rows(rows)

    assert [str(row["itemId"]) for row in result] == ["11", "12"]
    assert result[0]["title"] == "A"


def test_extract_agent_observation_ignores_previous_turn_tool_messages():
    result = {
        "messages": [
            {"type": "human", "content": "old"},
            {"type": "tool", "name": "search_book", "content": "[{'itemId': 1, 'title': 'OLD'}]"},
            {"type": "ai", "content": "old answer"},
            {"type": "human", "content": "new"},
            {"type": "tool", "name": "vector_search_descp", "content": "[{'itemId': 2, 'title': 'NEW'}]"},
            {"type": "ai", "content": "new answer"},
        ]
    }

    observation = extract_agent_observation(result)

    assert observation["ranked_item_ids"] == ["2"]
    assert observation["used_tools"] == ["vector_search_descp"]
    assert observation["ranked_rows"][0]["title"] == "NEW"
    assert observation["tool_call_count"] == 1


def test_answer_grounding_measures_retrieved_titles_used_in_answer():
    rows = [
        {"itemId": 1, "title": "코스모스"},
        {"itemId": 2, "title": "우주 산책"},
    ]

    score = calculate_answer_grounding(
        "첫 번째 추천은 코스모스입니다.",
        rows,
        k=2,
    )

    assert score == 0.5


def test_count_fulfillment_caps_score_at_one():
    assert calculate_count_fulfillment([1, 2], k=4) == 0.5
    assert calculate_count_fulfillment([1, 2, 3, 4, 5], k=4) == 1.0


def test_comprehensive_score_gives_retrieval_the_largest_weight():
    score = calculate_comprehensive_score(
        retrieval_score=0.5,
        tool_match=1.0,
        count_fulfillment=1.0,
        answer_grounding=1.0,
    )

    # 검색 품질 60%, 도구 선택 20%, 개수 충족 10%, 답변 반영 10%.
    assert score == pytest.approx(0.7)


def test_dataset_is_balanced_for_structured_and_semantic_cases():
    df = pd.read_csv(TEST_DIR / "evaluation_dataset.csv")

    assert len(df) == 20
    assert (df["search_type"] == "structured").sum() == 12
    assert (df["search_type"] == "semantic").sum() == 8
    assert df["query_id"].is_unique
    assert df["gold_item_ids"].astype(str).str.len().gt(0).all()


def test_runtime_preflight_explains_missing_rfc3987(tmp_path, monkeypatch):
    import evaluation

    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    (agent_dir / "book_agent.py").write_text("def run_agent(*args, **kwargs): pass\n", encoding="utf-8")
    (tmp_path / "chroma_db").mkdir()

    real_find_spec = evaluation.importlib.util.find_spec

    def fake_find_spec(name, *args, **kwargs):
        if name == "rfc3987":
            return None
        return real_find_spec(name, *args, **kwargs)

    monkeypatch.setattr(evaluation.importlib.util, "find_spec", fake_find_spec)

    issues = evaluation.runtime_preflight(tmp_path)

    assert any("rfc3987" in issue for issue in issues)
    assert any("uv add rfc3987" in issue for issue in issues)


def test_direct_chroma_case_calculates_same_k_metrics():
    import evaluation

    row = pd.Series(
        {
            "query_id": "M99",
            "search_type": "semantic",
            "query": "우주 책",
            "k": 3,
            "expected_tool": "vector_search_descp",
            "gold_item_ids": "2|3|9",
        }
    )

    def fake_search(query, k):
        assert query == "우주 책"
        assert k == 3
        return [
            {"itemId": 1, "title": "A"},
            {"itemId": 2, "title": "B"},
            {"itemId": 3, "title": "C"},
        ]

    result = evaluation.evaluate_direct_chroma_case(row, fake_search)

    assert result["predicted_item_ids"] == "1|2|3"
    assert result["hit_at_k"] == 1.0
    assert result["precision_at_k"] == pytest.approx(2 / 3)
    assert result["recall_at_k"] == pytest.approx(2 / 3)
    assert result["mrr_at_k"] == pytest.approx(1 / 2)
