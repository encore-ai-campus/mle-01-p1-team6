"""베스트셀러 리뷰·평점·판매지수와 순위의 관계를 분석한다.

분석 단위는 목적에 따라 다르게 사용한다.

1. 리뷰 분석
   같은 책이 여러 카테고리에 중복 등장할 수 있으므로 itemId당 한 행으로 만든다.
   여러 순위 중 숫자가 가장 작은 값, 즉 가장 좋은 순위를 대표 순위로 사용한다.

2. 판매지수 분석
   베스트셀러 순위는 카테고리 안에서 결정되므로
   itemId와 category_name의 조합을 하나의 관측값으로 사용한다.

주의: 이 분석은 변수 사이의 관련성을 확인하는 분석이다.
판매지수나 리뷰가 순위의 원인이라는 인과관계까지 증명하지는 않는다.
"""

import json
import platform
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd



# 1. 파일 경로 설정
# 이 파이썬 파일은 프로젝트의 ghs_data 폴더에 있다고 가정
# __file__을 사용하면 PowerShell의 현재 위치와 관계없이 같은 경로를 찾을 수 있음
base_dir = Path(__file__).resolve().parent

input_path = (
    base_dir.parent
    / "output"
    / "aladin_bestsellers"
    / "all_bestsellers_author_split.json"
)

# 분석 결과는 입력 JSON과 같은 폴더에 저장
output_dir = input_path.parent
review_summary_path = output_dir / "review_rank_summary.csv"
sales_summary_path = output_dir / "sales_rank_summary.csv"
breakpoint_result_path = output_dir / "sales_breakpoint_candidates.csv"
review_chart_path = output_dir / "review_rank_relationship.png"
sales_chart_path = output_dir / "sales_rank_breakpoint.png"


# Windows에서 그래프의 한글이 깨지지 않도록 맑은 고딕을 사용한다.
if platform.system() == "Windows":
    plt.rcParams["font.family"] = "Malgun Gothic"

plt.rcParams["axes.unicode_minus"] = False



# 2. JSON 데이터 불러오기
def load_data(path):
    """JSON을 불러와 DataFrame으로 변환한다."""

    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {path}")

    # JSON의 최상위 구조는 책 정보가 들어 있는 리스트다.
    # 각 책의 communityReviews에는 해당 책의 리뷰 목록이 중첩되어 있다.
    with path.open("r", encoding="utf-8") as file:
        bestseller_data = json.load(file)

    # 리스트 안의 책 하나가 DataFrame의 한 행이 된다.
    # communityReviews는 이 단계에서는 펼치지 않고 리스트 상태를 유지한다.
    df = pd.DataFrame(bestseller_data)

    required_columns = {
        "itemId",
        "title",
        "category_name",
        "bestRank",
        "salesPoint",
        "communityReviews",
    }
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise KeyError(f"필요한 열이 없습니다: {sorted(missing_columns)}")

    return df



# 3. 리뷰 관련 파생변수 생성
def count_reviews(review_list):
    """책 한 권에 포함된 리뷰 개수를 계산한다."""

    if not isinstance(review_list, list):
        return 0

    return len(review_list)


def calculate_average_rating(review_list):
    """책 한 권의 리뷰 평균 평점을 계산한다."""

    if not isinstance(review_list, list) or not review_list:
        return np.nan

    ratings = [
        review.get("rating")
        for review in review_list
        if review.get("rating") is not None
    ]

    if not ratings:
        return np.nan

    return sum(ratings) / len(ratings)


def calculate_recommendation_count(review_list):
    """책 한 권의 리뷰 추천 수 합계를 계산한다."""

    if not isinstance(review_list, list):
        return 0

    return sum(
        (review.get("recommendationCount", 0) or 0)
        for review in review_list
    )


def add_review_columns(df):
    """
    communityReviews에서 리뷰 개수, 평균 평점,
    추천 수 합계를 계산한다.
    """

    # 원본 DataFrame을 직접 변경하지 않도록 복사본을 사용한다.
    df = df.copy()

    # apply()는 communityReviews 열을 책 한 권씩 순회한다.
    # 즉 아래 결과는 전체 리뷰 통계가 아니라 각 책의 리뷰 통계다.
    df["review_count"] = df["communityReviews"].apply(count_reviews)
    df["average_rating"] = df["communityReviews"].apply(
        calculate_average_rating
    )
    df["recommendation_count"] = df["communityReviews"].apply(
        calculate_recommendation_count
    )

    return df



# 4. 리뷰 분석용 책 단위 데이터 생성
def make_book_level_data(df):
    """
    itemId별로 한 행만 남긴다.

    동일 도서가 여러 카테고리에 있으면 가장 좋은 순위,
    즉 가장 작은 bestRank를 사용한다.
    """

    # 같은 itemId가 여러 카테고리에서 발견되더라도 리뷰 목록은 같은 책의 정보다.
    # 따라서 리뷰 관련 값은 first로 하나만 가져오고,
    # 순위는 그 책이 기록한 순위 중 가장 좋은 값인 min을 사용한다.
    book_df = (
        df.groupby("itemId", as_index=False)
        .agg(
            title=("title", "first"),
            bestRank=("bestRank", "min"),
            review_count=("review_count", "first"),
            average_rating=("average_rating", "first"),
            recommendation_count=("recommendation_count", "first"),
            salesPoint=("salesPoint", "first"),
        )
    )

    return book_df



# 5. 리뷰 수·평점과 순위 관계 분석
def calculate_spearman_correlation(df, first_column, second_column):
    """두 열의 스피어만 상관계수를 안전하게 계산한다."""

    # 결측치가 있는 행은 두 변수의 상관계수 계산에서 제외한다.
    valid_data = df[[first_column, second_column]].dropna()

    if (
        len(valid_data) < 2
        or valid_data[first_column].nunique() < 2
        or valid_data[second_column].nunique() < 2
    ):
        return np.nan

    # 판매·리뷰 데이터는 극단값이 많고 정규분포를 따르지 않을 수 있다.
    # 따라서 실제 값보다 순서 관계를 이용하는 스피어만 상관계수를 사용한다.
    # bestRank는 숫자가 작을수록 좋은 순위이므로 음수 상관계수는
    # 두 번째 변수가 클수록 더 좋은 순위에 위치하는 경향을 의미한다.
    return valid_data[first_column].corr(
        valid_data[second_column],
        method="spearman",
    )


def analyze_review_relationship(book_df):
    """리뷰 수·평점·추천 수와 순위의 관계를 분석한다."""

    book_df = book_df.copy()

    review_corr = calculate_spearman_correlation(
        book_df,
        "bestRank",
        "review_count",
    )
    rating_corr = calculate_spearman_correlation(
        book_df,
        "bestRank",
        "average_rating",
    )
    recommendation_corr = calculate_spearman_correlation(
        book_df,
        "bestRank",
        "recommendation_count",
    )

    print(f"리뷰 수와 순위 상관계수: {review_corr:.3f}")
    print(f"평균 평점과 순위 상관계수: {rating_corr:.3f}")
    print(f"추천 수와 순위 상관계수: {recommendation_corr:.3f}")

    rank_bins = [0, 10, 20, 30, 50, 100, 150, 200]
    rank_labels = [
        "1~10위",
        "11~20위",
        "21~30위",
        "31~50위",
        "51~100위",
        "101~150위",
        "151~200위",
    ]

    # 책을 1~10위, 11~20위 등의 구간으로 나누면
    # 개별 산점도보다 구간별 대표값을 비교하기 쉽다.
    book_df["rank_group"] = pd.cut(
        book_df["bestRank"],
        bins=rank_bins,
        labels=rank_labels,
        include_lowest=True,
    )

    # 리뷰 수는 일부 책에 매우 많이 몰려 있으므로 평균보다 중앙값을 사용한다.
    review_summary = (
        book_df.groupby("rank_group", observed=True)
        .agg(
            book_count=("itemId", "nunique"),
            median_review_count=("review_count", "median"),
            median_average_rating=("average_rating", "median"),
            median_recommendation_count=(
                "recommendation_count",
                "median",
            ),
        )
        .reset_index()
    )

    print("\n순위 구간별 리뷰 통계")
    print(review_summary.to_string(index=False))

    return book_df, review_summary



# 6. 리뷰 관계 시각화
def draw_review_chart(book_df, output_path=None, show=True):
    """리뷰 수·평점과 순위 관계를 산점도로 표시한다."""

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # 리뷰 수는 0개부터 1,000개 이상까지 편차가 크다.
    # log(리뷰 수 + 1)을 사용하면 큰 값을 압축하면서 리뷰 0개도 표시할 수 있다.
    axes[0].scatter(
        book_df["bestRank"],
        np.log1p(book_df["review_count"]),
        alpha=0.4,
        s=22,
        color="#4C78A8",
    )
    axes[0].set_title("리뷰 수와 베스트셀러 순위")
    axes[0].set_xlabel("베스트셀러 순위")
    axes[0].set_ylabel("log(리뷰 수 + 1)")
    axes[0].grid(linestyle="--", alpha=0.3)

    rating_data = book_df.dropna(subset=["average_rating"])
    axes[1].scatter(
        rating_data["bestRank"],
        rating_data["average_rating"],
        alpha=0.4,
        s=22,
        color="#F28E2B",
    )
    axes[1].set_title("평균 평점과 베스트셀러 순위")
    axes[1].set_xlabel("베스트셀러 순위")
    axes[1].set_ylabel("평균 평점")
    axes[1].grid(linestyle="--", alpha=0.3)

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Glyph .* missing from font")
        fig.tight_layout()

        if output_path is not None:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(output_path, dpi=300, bbox_inches="tight")

    if show:
        plt.show()

    plt.close(fig)


# ============================================================
# 7. 판매지수 분석용 데이터 준비
# ============================================================

def prepare_sales_data(df):
    """
    itemId와 category_name의 조합을 하나의 순위 관측값으로 사용한다.
    """

    # 판매지수 분석에 필요한 네 개 열만 선택한다.
    sales_df = df[
        ["itemId", "category_name", "bestRank", "salesPoint"]
    ].copy()

    sales_df["bestRank"] = pd.to_numeric(
        sales_df["bestRank"],
        errors="coerce",
    )
    sales_df["salesPoint"] = pd.to_numeric(
        sales_df["salesPoint"],
        errors="coerce",
    )

    sales_df = sales_df.dropna(
        subset=["itemId", "category_name", "bestRank", "salesPoint"]
    )
    sales_df = sales_df[
        sales_df["bestRank"].between(1, 200)
        & (sales_df["salesPoint"] >= 0)
    ]
    # itemId만으로 중복 제거하면 서로 다른 카테고리 순위를 잃게 된다.
    # 따라서 동일 책·동일 카테고리 조합만 중복으로 판단한다.
    sales_df = sales_df.drop_duplicates(
        subset=["itemId", "category_name"]
    ).reset_index(drop=True)

    # 판매지수는 극단적으로 큰 값이 존재하므로 로그 변환한다.
    # log1p(x)는 log(x + 1)이며 판매지수가 0인 데이터도 계산할 수 있다.
    sales_df["log_sales_point"] = np.log1p(sales_df["salesPoint"])

    return sales_df



# 8. 순위 구간별 판매지수 계산
def summarize_sales_by_rank(sales_df):
    """순위 구간별 판매지수 요약 통계를 계산한다."""

    sales_df = sales_df.copy()

    rank_bins = [0, 10, 20, 30, 50, 75, 100, 125, 150, 175, 200]
    rank_labels = [
        "1~10위",
        "11~20위",
        "21~30위",
        "31~50위",
        "51~75위",
        "76~100위",
        "101~125위",
        "126~150위",
        "151~175위",
        "176~200위",
    ]

    sales_df["rank_group"] = pd.cut(
        sales_df["bestRank"],
        bins=rank_bins,
        labels=rank_labels,
        include_lowest=True,
    )

    # 중앙값과 함께 1·3사분위수를 계산하면
    # 순위 구간별 판매지수의 중심과 흩어진 정도를 확인할 수 있다.
    sales_summary = (
        sales_df.groupby("rank_group", observed=True)
        .agg(
            observation_count=("itemId", "size"),
            median_sales_point=("salesPoint", "median"),
            mean_log_sales_point=("log_sales_point", "mean"),
            first_quartile=("salesPoint", lambda values: values.quantile(0.25)),
            third_quartile=("salesPoint", lambda values: values.quantile(0.75)),
        )
        .reset_index()
    )

    print("\n순위 구간별 판매지수")
    print(sales_summary.to_string(index=False))

    return sales_df, sales_summary



# 9. 순위별 판매지수 중앙값 계산
def calculate_rank_median(sales_df):
    """각 순위의 로그 판매지수 중앙값을 계산한다."""

    # 현재 데이터는 15개 카테고리의 1~200위 자료다.
    # 예를 들어 1위 판매지수 중앙값은 각 카테고리 1위들의 중앙값이다.
    # 카테고리별 판매지수 차이와 극단값의 영향을 줄이기 위해 중앙값을 사용한다.
    rank_median = (
        sales_df.groupby("bestRank", as_index=False)["log_sales_point"]
        .median()
        .rename(
            columns={
                "log_sales_point": "median_log_sales_point",
            }
        )
        .sort_values("bestRank")
        .reset_index(drop=True)
    )

    return rank_median



# 10. 판매지수 변화점 찾기
def find_sales_breakpoint(rank_median):
    """
    연속 구간 회귀를 사용하여 판매지수 감소 기울기가
    달라지는 순위를 찾는다.
    """

    # x는 순위, y는 해당 순위의 로그 판매지수 중앙값이다.
    x = rank_median["bestRank"].to_numpy(dtype=float)
    y = rank_median["median_log_sales_point"].to_numpy(dtype=float)

    if len(x) < 4:
        raise ValueError("변화점을 계산하기 위한 순위 데이터가 부족합니다.")

    # 너무 앞쪽인 1~9위는 한쪽 구간의 자료가 부족하므로 제외한다.
    # 이번 질문은 상위권에서 관계가 약해지는 지점을 찾는 것이므로
    # 10위부터 최대 100위까지만 변화점 후보로 확인한다.
    max_candidate = min(100, int(x.max()))
    candidate_ranks = range(10, max_candidate + 1)
    result_list = []

    for candidate in candidate_ranks:
        # 하나의 직선을 candidate 지점에서 꺾는 연속 구간 회귀다.
        #
        # 1                 : 절편
        # x                 : 변화점 이전의 순위 기울기
        # max(0, x-candidate): 변화점 이후에 추가되는 기울기
        #
        # 이 구조를 사용하면 변화점에서 두 회귀선이 끊기지 않고 이어진다.
        design_matrix = np.column_stack(
            [
                np.ones_like(x),
                x,
                np.maximum(0, x - candidate),
            ]
        )

        # 최소제곱법으로 관측값과 회귀선의 차이가 가장 작아지는 계수를 구한다.
        coefficients = np.linalg.lstsq(
            design_matrix,
            y,
            rcond=None,
        )[0]
        predicted = design_matrix @ coefficients
        # 후보별 제곱오차합(SSE)을 계산한다.
        # SSE가 작을수록 해당 후보에서 선을 꺾었을 때 데이터를 잘 설명한다.
        total_error = float(np.square(y - predicted).sum())

        # 로그 판매지수의 기울기이므로 음수 값은
        # 순위 숫자가 커질수록 판매지수가 감소한다는 뜻이다.
        slope_before = float(coefficients[1])
        slope_after = float(coefficients[1] + coefficients[2])

        result_list.append(
            {
                "candidate_rank": candidate,
                "total_error": total_error,
                "slope_before": slope_before,
                "slope_after": slope_after,
            }
        )

    if not result_list:
        raise ValueError("10위 이후의 변화점 후보를 만들 수 없습니다.")

    # 모든 후보 중 오차가 가장 작은 순위를 최종 변화점으로 선택한다.
    best_result = min(
        result_list,
        key=lambda result: result["total_error"],
    )
    breakpoint = best_result["candidate_rank"]

    return breakpoint, result_list



# 11. 판매지수 변화점 시각화
def draw_sales_breakpoint_chart(
    rank_median,
    breakpoint,
    output_path=None,
    show=True,
):
    """순위별 로그 판매지수 중앙값과 변화점을 표시한다."""

    x = rank_median["bestRank"].to_numpy(dtype=float)
    y = rank_median["median_log_sales_point"].to_numpy(dtype=float)

    # 최종 변화점으로 다시 구간 회귀선을 계산해 원자료와 함께 표시한다.
    design_matrix = np.column_stack(
        [
            np.ones_like(x),
            x,
            np.maximum(0, x - breakpoint),
        ]
    )
    coefficients = np.linalg.lstsq(
        design_matrix,
        y,
        rcond=None,
    )[0]
    fitted_values = design_matrix @ coefficients

    fig, ax = plt.subplots(figsize=(12, 6))

    ax.plot(
        x,
        y,
        color="#4C78A8",
        alpha=0.65,
        label="순위별 판매지수 중앙값",
    )
    ax.plot(
        x,
        fitted_values,
        color="#F28E2B",
        linewidth=2.5,
        label="구간 회귀선",
    )
    ax.axvline(
        x=breakpoint,
        color="#E15759",
        linestyle="--",
        linewidth=2,
        label=f"추정 변화점: {breakpoint}위",
    )

    ax.set_title("베스트셀러 순위에 따른 판매지수 변화")
    ax.set_xlabel("베스트셀러 순위")
    ax.set_ylabel("로그 판매지수 중앙값")
    ax.grid(linestyle="--", alpha=0.3)
    ax.legend()

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Glyph .* missing from font")
        fig.tight_layout()

        if output_path is not None:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(output_path, dpi=300, bbox_inches="tight")

    if show:
        plt.show()

    plt.close(fig)



# 12. 전체 분석 실행
def main():
    # 1단계: 원본 JSON을 불러온다.
    df = load_data(input_path)
    print(f"전체 관측값: {len(df):,}개")

    # 2단계: 중첩된 리뷰 목록에서 책별 리뷰 파생변수를 만든다.
    df = add_review_columns(df)

    # 3단계: 리뷰 분석에서는 itemId당 한 행으로 정리한다.
    book_df = make_book_level_data(df)
    print(f"고유 도서 수: {len(book_df):,}권")

    # 4단계: 리뷰·평점·추천 수와 순위의 관계를 계산하고 저장한다.
    book_df, review_summary = analyze_review_relationship(book_df)
    review_summary.to_csv(
        review_summary_path,
        index=False,
        encoding="utf-8-sig",
    )
    draw_review_chart(
        book_df,
        output_path=review_chart_path,
    )

    # 5단계: 판매지수 분석에서는 책·카테고리 조합을 유지한다.
    sales_df = prepare_sales_data(df)
    sales_df, sales_summary = summarize_sales_by_rank(sales_df)
    sales_summary.to_csv(
        sales_summary_path,
        index=False,
        encoding="utf-8-sig",
    )

    # 6단계: 순위별 로그 판매지수 중앙값을 계산한다.
    rank_median = calculate_rank_median(sales_df)

    # 7단계: 회귀선의 기울기가 가장 크게 달라지는 변화점을 찾는다.
    breakpoint, result_list = find_sales_breakpoint(rank_median)

    breakpoint_df = pd.DataFrame(result_list)
    breakpoint_df.to_csv(
        breakpoint_result_path,
        index=False,
        encoding="utf-8-sig",
    )

    best_result = breakpoint_df.loc[
        breakpoint_df["candidate_rank"] == breakpoint
    ].iloc[0]

    print(f"\n추정된 판매지수 변화점: {breakpoint}위")
    print(f"변화점 이전 기울기: {best_result['slope_before']:.4f}")
    print(f"변화점 이후 기울기: {best_result['slope_after']:.4f}")

    draw_sales_breakpoint_chart(
        rank_median,
        breakpoint,
        output_path=sales_chart_path,
    )

    print("\n저장 완료")
    print(f"- 리뷰 요약: {review_summary_path}")
    print(f"- 판매지수 요약: {sales_summary_path}")
    print(f"- 변화점 후보: {breakpoint_result_path}")
    print(f"- 리뷰 그래프: {review_chart_path}")
    print(f"- 판매지수 그래프: {sales_chart_path}")


if __name__ == "__main__":
    main()
