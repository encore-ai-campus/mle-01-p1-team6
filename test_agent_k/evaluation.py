"""도서 추천 Agent 종합 K 평가.

프로젝트 루트에서 실행:
    uv run test_agent_k/evaluation.py

일부 문항만 빠르게 확인:
    uv run test_agent_k/evaluation.py --limit 3

평가 축
- 검색 품질: Hit@K, Precision@K, Recall@K, MRR@K
- 라우팅: 질문에 맞는 Tool을 선택했는지
- 응답 구성: 요청한 K개를 채웠는지, 검색된 제목을 답변에 반영했는지
- 안정성: 오류율, 문항별 실행 시간

실제 Agent의 run_agent()를 호출하므로 structured 문항은 Supabase search_book,
semantic 문항은 ChromaDB vector_search_descp까지 포함한 end-to-end 평가가 된다.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import math
import sys
from pathlib import Path
from time import perf_counter
from typing import Any, Callable
from uuid import uuid4

import pandas as pd


TEST_AGENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TEST_AGENT_DIR.parent
DEFAULT_DATASET = TEST_AGENT_DIR / "evaluation_dataset.csv"
DEFAULT_OUTPUT = TEST_AGENT_DIR / "evaluation_results.csv"
DEFAULT_SUMMARY_OUTPUT = TEST_AGENT_DIR / "evaluation_summary.json"
DEFAULT_CHROMA_OUTPUT = TEST_AGENT_DIR / "chroma_baseline_results.csv"


def normalize_item_id(value: Any) -> str | None:
    """itemId를 비교하기 쉬운 문자열로 통일한다."""
    if value is None:
        return None

    if isinstance(value, float):
        if math.isnan(value):
            return None
        if value.is_integer():
            return str(int(value))

    text = str(value).strip()
    if not text or text.lower() in {"none", "nan"}:
        return None

    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]

    return text


def parse_book_rows(value: Any) -> list[dict[str, Any]]:
    """ToolMessage의 list/dict/문자열 형태를 책 dict 리스트로 변환한다."""
    if value is None:
        return []

    if isinstance(value, list):
        rows: list[dict[str, Any]] = []
        for item in value:
            rows.extend(parse_book_rows(item))
        return rows

    if isinstance(value, dict):
        if "itemId" in value:
            return [value]

        rows: list[dict[str, Any]] = []
        for key in ("rows", "text", "content"):
            if key in value:
                rows.extend(parse_book_rows(value[key]))
        return rows

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []

        # LangChain ToolMessage는 JSON 또는 파이썬 리스트 문자열로 올 수 있다.
        for parser in (json.loads, ast.literal_eval):
            try:
                parsed = parser(text)
            except (ValueError, SyntaxError, TypeError, json.JSONDecodeError):
                continue
            return parse_book_rows(parsed)

    return []


def unique_ranked_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """검색 순서를 유지하면서 같은 itemId의 중복 결과만 제거한다."""
    result: list[dict[str, Any]] = []
    seen: set[str] = set()

    for row in rows:
        item_id = normalize_item_id(row.get("itemId"))
        if item_id is None or item_id in seen:
            continue
        seen.add(item_id)
        result.append(row)

    return result


def _message_attr(message: Any, key: str, default: Any = None) -> Any:
    """LangChain Message 객체와 dict 메시지를 같은 방법으로 읽는다."""
    if isinstance(message, dict):
        return message.get(key, default)
    return getattr(message, key, default)


def extract_agent_observation(result: dict[str, Any]) -> dict[str, Any]:
    """이번 질문에서 실제 Tool 호출과 검색 결과를 추출한다."""
    if not isinstance(result, dict):
        return {
            "ranked_rows": [],
            "ranked_item_ids": [],
            "used_tools": [],
            "tool_call_count": 0,
        }

    messages = result.get("messages", [])

    # checkpointer 때문에 이전 대화의 ToolMessage도 result에 남을 수 있다.
    # 가장 최근 HumanMessage 이후만 보면 현재 평가 문항만 분리할 수 있다.
    start_index = 0
    for index in range(len(messages) - 1, -1, -1):
        if _message_attr(messages[index], "type", "") == "human":
            start_index = index + 1
            break

    rows: list[dict[str, Any]] = []
    used_tools: list[str] = []
    tool_call_count = 0

    for message in messages[start_index:]:
        if _message_attr(message, "type", "") != "tool":
            continue

        tool_call_count += 1
        tool_name = str(_message_attr(message, "name", "") or "").strip()
        if tool_name:
            used_tools.append(tool_name)

        rows.extend(parse_book_rows(_message_attr(message, "content", None)))

    ranked_rows = unique_ranked_rows(rows)
    ranked_item_ids = [
        item_id
        for item_id in (normalize_item_id(row.get("itemId")) for row in ranked_rows)
        if item_id is not None
    ]

    return {
        "ranked_rows": ranked_rows,
        "ranked_item_ids": ranked_item_ids,
        "used_tools": list(dict.fromkeys(used_tools)),
        "tool_call_count": tool_call_count,
    }


def parse_gold_item_ids(value: Any) -> set[str]:
    """평가셋의 id1|id2 형식을 정답 itemId 집합으로 바꾼다."""
    gold: set[str] = set()
    for raw in str(value).split("|"):
        item_id = normalize_item_id(raw)
        if item_id is not None:
            gold.add(item_id)
    return gold


def calculate_metrics(
    ranked_item_ids: list[Any],
    gold_item_ids: set[Any],
    k: int,
) -> dict[str, float]:
    """표준 검색 지표 Hit@K, Precision@K, Recall@K, MRR@K를 계산한다."""
    if k < 1:
        raise ValueError("k는 1 이상이어야 합니다.")

    ranked = [
        item_id
        for item_id in (normalize_item_id(value) for value in ranked_item_ids)
        if item_id is not None
    ]
    gold = {
        item_id
        for item_id in (normalize_item_id(value) for value in gold_item_ids)
        if item_id is not None
    }
    top_k = ranked[:k]
    relevant_count = sum(item_id in gold for item_id in top_k)

    hit_at_k = 1.0 if relevant_count > 0 else 0.0
    precision_at_k = relevant_count / k
    recall_at_k = relevant_count / len(gold) if gold else 0.0

    mrr_at_k = 0.0
    for rank, item_id in enumerate(top_k, start=1):
        if item_id in gold:
            mrr_at_k = 1.0 / rank
            break

    return {
        "hit_at_k": hit_at_k,
        "precision_at_k": precision_at_k,
        "recall_at_k": recall_at_k,
        "mrr_at_k": mrr_at_k,
    }


def calculate_count_fulfillment(ranked_item_ids: list[Any], k: int) -> float:
    """사용자가 요청한 K권을 실제 검색 결과가 얼마나 채웠는지 계산한다."""
    if k < 1:
        raise ValueError("k는 1 이상이어야 합니다.")
    return min(len(ranked_item_ids), k) / k


def calculate_answer_grounding(
    answer: str,
    ranked_rows: list[dict[str, Any]],
    k: int,
) -> float:
    """Top-K 검색 결과의 제목이 최종 답변에 얼마나 반영됐는지 계산한다.

    이 값은 '환각률' 자체가 아니라 검색 결과 활용도를 보는 보조 지표다.
    """
    top_rows = ranked_rows[:k]
    titles = [
        str(row.get("title", "")).strip()
        for row in top_rows
        if str(row.get("title", "")).strip()
    ]

    if not titles:
        return 0.0

    answer_text = str(answer or "").casefold()
    mentioned = sum(title.casefold() in answer_text for title in titles)
    return mentioned / len(titles)


def calculate_comprehensive_score(
    *,
    retrieval_score: float,
    tool_match: float,
    count_fulfillment: float,
    answer_grounding: float,
) -> float:
    """에이전트 상태를 한눈에 보는 참고용 종합점수다.

    검색 성능이 핵심이므로 K 검색지표 평균에 가장 큰 60% 가중치를 둔다.
    표준 IR 지표가 아니므로 최종 판단은 개별 지표와 함께 해야 한다.
    """
    return (
        0.60 * retrieval_score
        + 0.20 * tool_match
        + 0.10 * count_fulfillment
        + 0.10 * answer_grounding
    )


def runtime_preflight(
    project_root: Path = PROJECT_ROOT,
    mode: str = "both",
) -> list[str]:
    """실행 전에 경로와 현재 환경에서 알려진 Chroma 의존성 문제를 확인한다."""
    issues: list[str] = []

    agent_file = project_root / "agent" / "book_agent.py"
    chroma_db = project_root / "chroma_db"

    if mode in {"agent", "both"} and not agent_file.exists():
        issues.append(f"Agent 파일 없음: {agent_file}")
    if mode in {"chroma", "both", "agent"} and not chroma_db.exists():
        issues.append(f"ChromaDB 폴더 없음: {chroma_db}")

    # 현재 사용자 환경에서는 rfc3987이 없을 때 jsonschema가 느린 fallback parser를
    # 불러오며 chromadb import가 멈췄다. 미리 잡아서 긴 traceback 대신 해결 명령을 보여준다.
    if importlib.util.find_spec("rfc3987") is None:
        issues.append(
            "ChromaDB import 안정화용 rfc3987 패키지가 없습니다. "
            "프로젝트 루트에서 `uv add rfc3987`을 한 번 실행하세요."
        )

    return issues


def load_run_agent() -> Callable[..., tuple[str, dict[str, Any]]]:
    """실제 agent/book_agent.py의 run_agent()를 지연 로드한다."""
    agent_dir = PROJECT_ROOT / "agent"
    agent_file = agent_dir / "book_agent.py"

    if not agent_file.exists():
        raise FileNotFoundError(f"Agent 파일을 찾을 수 없습니다: {agent_file}")

    # book_agent.py의 `from db import ...`가 같은 agent/db.py를 찾도록 한다.
    if str(agent_dir) not in sys.path:
        sys.path.insert(0, str(agent_dir))

    spec = importlib.util.spec_from_file_location(
        "book_agent_for_evaluation",
        agent_file,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Agent 모듈을 불러올 수 없습니다: {agent_file}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    run_agent = getattr(module, "run_agent", None)
    if not callable(run_agent):
        raise AttributeError(f"{agent_file}에서 run_agent()를 찾을 수 없습니다.")

    return run_agent



def load_direct_chroma_search() -> Callable[[str, int], list[dict[str, Any]]]:
    """Agent의 vector_search_descp와 같은 방식으로 ChromaDB만 직접 조회한다.

    표지 URL은 K 평가에 필요하지 않으므로 Supabase 조회는 생략한다.
    이 기준선은 LLM의 도구 선택/질문 재작성 영향을 제외한 순수 벡터 검색 성능이다.
    """
    import chromadb
    from langchain_huggingface import HuggingFaceEmbeddings

    chroma_db_path = PROJECT_ROOT / "chroma_db"
    embeddings = HuggingFaceEmbeddings(
        model_name="SamilPwC-AXNode-GenAI/PwC-Embedding_expr",
        encode_kwargs={"normalize_embeddings": True},
    )
    client = chromadb.PersistentClient(path=str(chroma_db_path))
    collection = client.get_collection(name="book")

    def search(query: str, k: int) -> list[dict[str, Any]]:
        query_embedding = embeddings.embed_query(query)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )

        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        rows: list[dict[str, Any]] = []
        for chroma_id, document, metadata, distance in zip(
            ids,
            documents,
            metadatas,
            distances,
        ):
            metadata = metadata or {}
            rows.append(
                {
                    **metadata,
                    "chroma_id": chroma_id,
                    "description": document,
                    "distance": distance,
                }
            )
        return rows

    return search


def evaluate_direct_chroma_case(
    row: pd.Series,
    search: Callable[[str, int], list[dict[str, Any]]],
) -> dict[str, Any]:
    """의미검색 문항을 Agent 없이 ChromaDB에 직접 넣어 기준 성능을 계산한다."""
    query_id = str(row["query_id"])
    query = str(row["query"])
    k = int(row["k"])
    gold = parse_gold_item_ids(row["gold_item_ids"])
    started = perf_counter()

    try:
        ranked_rows = unique_ranked_rows(search(query, k))
        latency_sec = perf_counter() - started
        ranked_ids = [
            item_id
            for item_id in (normalize_item_id(book.get("itemId")) for book in ranked_rows)
            if item_id is not None
        ]
        metrics = calculate_metrics(ranked_ids, gold, k)
        retrieval_score = sum(metrics.values()) / len(metrics)

        return {
            "query_id": query_id,
            "search_type": "semantic",
            "query": query,
            "k": k,
            "gold_item_ids": "|".join(sorted(gold)),
            "predicted_item_ids": "|".join(ranked_ids[:k]),
            "predicted_titles": _titles_for_output(ranked_rows, k),
            **metrics,
            "retrieval_score": retrieval_score,
            "latency_sec": latency_sec,
            "status": "ok",
            "error": "",
        }
    except Exception as exc:
        return {
            "query_id": query_id,
            "search_type": "semantic",
            "query": query,
            "k": k,
            "gold_item_ids": "|".join(sorted(gold)),
            "predicted_item_ids": "",
            "predicted_titles": "",
            "hit_at_k": 0.0,
            "precision_at_k": 0.0,
            "recall_at_k": 0.0,
            "mrr_at_k": 0.0,
            "retrieval_score": 0.0,
            "latency_sec": perf_counter() - started,
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
        }

def _titles_for_output(ranked_rows: list[dict[str, Any]], k: int) -> str:
    titles = [
        str(row.get("title", "")).strip()
        for row in ranked_rows[:k]
        if str(row.get("title", "")).strip()
    ]
    return " | ".join(titles)


def evaluate_case(
    row: pd.Series,
    run_agent: Callable[..., tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    """문항 하나를 실제 Agent에 넣고 검색/라우팅/답변 지표를 계산한다."""
    query_id = str(row["query_id"])
    query = str(row["query"])
    search_type = str(row["search_type"])
    k = int(row["k"])
    expected_tool = str(row["expected_tool"])
    gold = parse_gold_item_ids(row["gold_item_ids"])

    # 평가 문항끼리 대화 기억이 섞이지 않도록 매번 별도 thread_id를 사용한다.
    thread_id = f"eval-{query_id}-{uuid4().hex[:8]}"
    started = perf_counter()

    try:
        answer, result = run_agent(query, thread_id=thread_id)
        latency_sec = perf_counter() - started

        observation = extract_agent_observation(result)
        ranked_ids = observation["ranked_item_ids"]
        ranked_rows = observation["ranked_rows"]
        used_tools = observation["used_tools"]

        metrics = calculate_metrics(ranked_ids, gold, k)
        retrieval_score = sum(metrics.values()) / len(metrics)
        tool_match = float(expected_tool in used_tools)
        count_fulfillment = calculate_count_fulfillment(ranked_ids, k)
        answer_grounding = calculate_answer_grounding(answer, ranked_rows, k)
        comprehensive_score = calculate_comprehensive_score(
            retrieval_score=retrieval_score,
            tool_match=tool_match,
            count_fulfillment=count_fulfillment,
            answer_grounding=answer_grounding,
        )

        return {
            "query_id": query_id,
            "search_type": search_type,
            "query": query,
            "k": k,
            "expected_tool": expected_tool,
            "used_tools": "|".join(used_tools),
            "tool_call_count": observation["tool_call_count"],
            "tool_match": tool_match,
            "gold_item_ids": "|".join(sorted(gold)),
            "predicted_item_ids": "|".join(ranked_ids[:k]),
            "predicted_titles": _titles_for_output(ranked_rows, k),
            **metrics,
            "retrieval_score": retrieval_score,
            "count_fulfillment": count_fulfillment,
            "answer_grounding": answer_grounding,
            "comprehensive_score": comprehensive_score,
            "latency_sec": latency_sec,
            "status": "ok",
            "error": "",
            "answer": str(answer),
        }

    except Exception as exc:
        latency_sec = perf_counter() - started
        return {
            "query_id": query_id,
            "search_type": search_type,
            "query": query,
            "k": k,
            "expected_tool": expected_tool,
            "used_tools": "",
            "tool_call_count": 0,
            "tool_match": 0.0,
            "gold_item_ids": "|".join(sorted(gold)),
            "predicted_item_ids": "",
            "predicted_titles": "",
            "hit_at_k": 0.0,
            "precision_at_k": 0.0,
            "recall_at_k": 0.0,
            "mrr_at_k": 0.0,
            "retrieval_score": 0.0,
            "count_fulfillment": 0.0,
            "answer_grounding": 0.0,
            "comprehensive_score": 0.0,
            "latency_sec": latency_sec,
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "answer": "",
        }


def print_case_result(index: int, total: int, result: dict[str, Any]) -> None:
    """문항별 결과를 사람이 바로 읽을 수 있게 출력한다."""
    print("\n" + "=" * 82)
    print(f"[{index}/{total}] {result['query_id']} | {result['search_type']} | K={result['k']}")
    print(f"질문          : {result['query']}")
    print(f"예상/사용 도구: {result['expected_tool']} / {result['used_tools'] or '-'}")
    print(f"Gold IDs      : {result['gold_item_ids']}")
    print(f"Pred IDs      : {result['predicted_item_ids'] or '-'}")
    if result["predicted_titles"]:
        print(f"검색 제목      : {result['predicted_titles']}")
    print(
        "K 지표         : "
        f"Hit={result['hit_at_k']:.3f} | "
        f"P={result['precision_at_k']:.3f} | "
        f"R={result['recall_at_k']:.3f} | "
        f"MRR={result['mrr_at_k']:.3f}"
    )
    print(
        "Agent 보조지표 : "
        f"Tool={result['tool_match']:.3f} | "
        f"K충족={result['count_fulfillment']:.3f} | "
        f"답변반영={result['answer_grounding']:.3f} | "
        f"종합={result['comprehensive_score']:.3f} | "
        f"{result['latency_sec']:.2f}s"
    )
    if result["status"] == "error":
        print(f"오류          : {result['error']}")


def _mean_dict(df: pd.DataFrame) -> dict[str, float]:
    columns = [
        "hit_at_k",
        "precision_at_k",
        "recall_at_k",
        "mrr_at_k",
        "retrieval_score",
        "tool_match",
        "count_fulfillment",
        "answer_grounding",
        "comprehensive_score",
        "latency_sec",
    ]
    return {column: float(df[column].mean()) for column in columns}


def build_summary(results_df: pd.DataFrame) -> dict[str, Any]:
    """CSV와 별도로 저장할 전체/검색유형별 요약 정보를 만든다."""
    summary: dict[str, Any] = {
        "total_cases": int(len(results_df)),
        "success_cases": int((results_df["status"] == "ok").sum()),
        "error_cases": int((results_df["status"] == "error").sum()),
        "success_rate": float((results_df["status"] == "ok").mean()),
        "overall": _mean_dict(results_df),
        "by_search_type": {},
    }

    for search_type, group in results_df.groupby("search_type"):
        summary["by_search_type"][str(search_type)] = _mean_dict(group)

    return summary


def print_summary(results_df: pd.DataFrame) -> dict[str, Any]:
    """전체 Agent 평가를 한 화면에 요약한다."""
    summary = build_summary(results_df)
    overall = summary["overall"]

    print("\n" + "#" * 82)
    print("도서 추천 Agent 종합 평가 요약")
    print("#" * 82)
    print(
        f"문항 {summary['total_cases']}개 | 성공 {summary['success_cases']}개 | "
        f"오류 {summary['error_cases']}개 | 성공률 {summary['success_rate']:.3f}"
    )
    print("\n[검색 K 지표]")
    print(f"Hit@K       : {overall['hit_at_k']:.4f}")
    print(f"Precision@K : {overall['precision_at_k']:.4f}")
    print(f"Recall@K    : {overall['recall_at_k']:.4f}")
    print(f"MRR@K       : {overall['mrr_at_k']:.4f}")
    print(f"검색 종합    : {overall['retrieval_score']:.4f}")

    print("\n[Agent 동작 지표]")
    print(f"도구 선택 정확도 : {overall['tool_match']:.4f}")
    print(f"요청 K개 충족률  : {overall['count_fulfillment']:.4f}")
    print(f"검색결과 답변반영 : {overall['answer_grounding']:.4f}")
    print(f"참고 종합점수    : {overall['comprehensive_score']:.4f}")
    print(f"평균 실행시간     : {overall['latency_sec']:.2f}s")

    print("\n[검색 유형별]")
    for search_type, values in summary["by_search_type"].items():
        print(
            f"{search_type:10s} | "
            f"Hit {values['hit_at_k']:.3f} | "
            f"P {values['precision_at_k']:.3f} | "
            f"R {values['recall_at_k']:.3f} | "
            f"MRR {values['mrr_at_k']:.3f} | "
            f"Tool {values['tool_match']:.3f} | "
            f"종합 {values['comprehensive_score']:.3f}"
        )

    return summary



def print_chroma_summary(results_df: pd.DataFrame) -> dict[str, Any]:
    """Agent를 거치지 않은 직접 Chroma 의미검색 성능을 요약한다."""
    metrics = [
        "hit_at_k",
        "precision_at_k",
        "recall_at_k",
        "mrr_at_k",
        "retrieval_score",
        "latency_sec",
    ]
    means = {name: float(results_df[name].mean()) for name in metrics}
    summary = {
        "total_cases": int(len(results_df)),
        "error_cases": int((results_df["status"] == "error").sum()),
        "overall": means,
    }

    print("\n" + "#" * 82)
    print("직접 ChromaDB 의미검색 기준선")
    print("#" * 82)
    print(f"문항 수       : {summary['total_cases']}")
    print(f"오류 문항 수  : {summary['error_cases']}")
    print(f"Hit@K         : {means['hit_at_k']:.4f}")
    print(f"Precision@K   : {means['precision_at_k']:.4f}")
    print(f"Recall@K      : {means['recall_at_k']:.4f}")
    print(f"MRR@K         : {means['mrr_at_k']:.4f}")
    print(f"검색 종합      : {means['retrieval_score']:.4f}")
    print(f"평균 검색시간  : {means['latency_sec']:.2f}s")
    return summary

def load_dataset(path: Path) -> pd.DataFrame:
    """평가셋을 읽고 실행 전에 기본 형식을 검증한다."""
    if not path.exists():
        raise FileNotFoundError(f"평가셋을 찾을 수 없습니다: {path}")

    df = pd.read_csv(path)
    required_columns = {
        "query_id",
        "search_type",
        "query",
        "k",
        "expected_tool",
        "gold_item_ids",
    }
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"평가셋 필수 컬럼이 없습니다: {sorted(missing)}")
    if df["query_id"].duplicated().any():
        raise ValueError("query_id는 중복될 수 없습니다.")
    if (df["k"] < 1).any():
        raise ValueError("모든 k는 1 이상이어야 합니다.")

    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="도서 추천 Agent 종합 K 평가")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--chroma-output", type=Path, default=DEFAULT_CHROMA_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument(
        "--mode",
        choices=("both", "agent", "chroma"),
        default="both",
        help="both=Agent 전체+직접 Chroma 기준선, agent=Agent만, chroma=Chroma만",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Agent 평가에서 앞에서부터 N개 문항만 실행",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="환경 사전 점검을 건너뜀(문제 원인 확인용)",
    )
    args = parser.parse_args()

    dataset = load_dataset(args.dataset)
    agent_dataset = dataset
    if args.limit is not None:
        if args.limit < 1:
            raise ValueError("--limit은 1 이상이어야 합니다.")
        agent_dataset = dataset.head(args.limit)

    if not args.skip_preflight:
        issues = runtime_preflight(PROJECT_ROOT, mode=args.mode)
        if issues:
            print("=" * 82)
            print("평가 실행 전 환경 점검에서 해결할 항목이 발견되었습니다.")
            print("=" * 82)
            for issue in issues:
                print(f"- {issue}")
            print("\n위 항목을 해결한 뒤 같은 명령을 다시 실행하세요.")
            raise SystemExit(2)

    combined_summary: dict[str, Any] = {"mode": args.mode}

    if args.mode in {"agent", "both"}:
        run_agent = load_run_agent()

        print("=" * 82)
        print("도서 추천 Agent 종합 K 평가 시작")
        print("=" * 82)
        print(f"프로젝트 루트 : {PROJECT_ROOT}")
        print(f"Agent 파일    : {PROJECT_ROOT / 'agent' / 'book_agent.py'}")
        print("Supabase      : agent/book_agent.py의 search_book 사용")
        print(f"ChromaDB      : {PROJECT_ROOT / 'chroma_db'} / collection='book'")
        print(f"평가셋        : {args.dataset}")
        print(f"Agent 문항 수 : {len(agent_dataset)}")

        agent_results: list[dict[str, Any]] = []
        for index, (_, row) in enumerate(agent_dataset.iterrows(), start=1):
            result = evaluate_case(row, run_agent)
            agent_results.append(result)
            print_case_result(index, len(agent_dataset), result)

        agent_df = pd.DataFrame(agent_results)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        agent_df.to_csv(args.output, index=False, encoding="utf-8-sig")
        combined_summary["agent"] = print_summary(agent_df)
        print(f"\nAgent 상세 결과 CSV: {args.output}")

    if args.mode in {"chroma", "both"}:
        semantic_dataset = dataset[dataset["search_type"] == "semantic"].copy()
        direct_search = load_direct_chroma_search()

        print("\n" + "=" * 82)
        print("직접 ChromaDB 의미검색 K 평가 시작")
        print("=" * 82)
        print(f"ChromaDB      : {PROJECT_ROOT / 'chroma_db'} / collection='book'")
        print(f"임베딩 모델    : SamilPwC-AXNode-GenAI/PwC-Embedding_expr")
        print(f"의미검색 문항 수: {len(semantic_dataset)}")

        chroma_results: list[dict[str, Any]] = []
        for index, (_, row) in enumerate(semantic_dataset.iterrows(), start=1):
            result = evaluate_direct_chroma_case(row, direct_search)
            chroma_results.append(result)
            print("\n" + "-" * 82)
            print(f"[{index}/{len(semantic_dataset)}] {result['query_id']} | K={result['k']}")
            print(f"질문     : {result['query']}")
            print(f"Gold IDs : {result['gold_item_ids']}")
            print(f"Pred IDs : {result['predicted_item_ids'] or '-'}")
            print(
                f"Hit={result['hit_at_k']:.3f} | "
                f"P={result['precision_at_k']:.3f} | "
                f"R={result['recall_at_k']:.3f} | "
                f"MRR={result['mrr_at_k']:.3f}"
            )
            if result["status"] == "error":
                print(f"오류     : {result['error']}")

        chroma_df = pd.DataFrame(chroma_results)
        args.chroma_output.parent.mkdir(parents=True, exist_ok=True)
        chroma_df.to_csv(args.chroma_output, index=False, encoding="utf-8-sig")
        combined_summary["chroma_baseline"] = print_chroma_summary(chroma_df)
        print(f"\nChroma 상세 결과 CSV: {args.chroma_output}")

        # both 모드에서는 Agent 의미검색과 직접 Chroma 기준선의 차이도 남긴다.
        if args.mode == "both" and "agent" in combined_summary:
            agent_semantic = agent_df[agent_df["search_type"] == "semantic"]
            if not agent_semantic.empty:
                agent_semantic_score = float(agent_semantic["retrieval_score"].mean())
                chroma_score = float(chroma_df["retrieval_score"].mean())
                combined_summary["semantic_gap"] = {
                    "agent_retrieval_score": agent_semantic_score,
                    "direct_chroma_retrieval_score": chroma_score,
                    "agent_minus_chroma": agent_semantic_score - chroma_score,
                }
                print("\n[Agent 의미검색 vs 직접 Chroma]")
                print(f"Agent 의미검색 : {agent_semantic_score:.4f}")
                print(f"직접 Chroma    : {chroma_score:.4f}")
                print(f"차이           : {agent_semantic_score - chroma_score:+.4f}")

    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.write_text(
        json.dumps(combined_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n통합 요약 JSON: {args.summary_output}")


if __name__ == "__main__":
    main()
