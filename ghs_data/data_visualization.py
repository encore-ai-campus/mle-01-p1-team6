# 베스트셀러 고유 도서 수 기준
# 상위 작가 10명과 상위 역자 10명을 시각화한다.

import json
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


# 1. 파일 경로 설정
# 현재 실행 중인 파이썬 파일(data_visualization.py)의 위치
# 예: mle-01-p1-team6/ghs_data
base_dir = Path(__file__).resolve().parent

# JSON 파일이 있는 폴더
# 예: mle-01-p1-team6/output/aladin_bestsellers
data_dir = base_dir.parent / "output" / "aladin_bestsellers"

# 원저자와 역자가 분리된 JSON 파일
input_path = data_dir / "all_bestsellers_author_split.json"

# 집계 결과 CSV 저장 경로
author_csv_path = data_dir / "top10_authors.csv"
translator_csv_path = data_dir / "top10_translators.csv"

# 시각화 이미지 저장 경로
chart_path = data_dir / "top10_authors_translators.png"

# 입력 파일이 실제로 존재하는지 확인
if not input_path.exists():
    raise FileNotFoundError(
        f"입력 JSON 파일을 찾을 수 없습니다.\n"
        f"확인한 경로: {input_path}"
    )

print(f"입력 파일: {input_path}")



# 2. JSON 데이터 불러오기
with input_path.open("r", encoding="utf-8") as file:
    bestseller_data = json.load(file)

# JSON의 리스트 데이터를 DataFrame으로 변환
df = pd.DataFrame(bestseller_data)

print(f"전체 데이터 행 수: {len(df):,}개")
print(f"고유 도서 수: {df['itemId'].nunique():,}권")



# 3. 분석에 필요한 열 확인
required_columns = {
    "itemId",
    "original_author",
    "translator"
}

missing_columns = required_columns - set(df.columns)

if missing_columns:
    raise KeyError(
        f"필요한 열이 없습니다: {missing_columns}"
    )



# 4. 인물별 고유 도서 수를 계산하는 함수
def get_top10_people(dataframe, person_column):
    """
    저자 또는 역자별 고유 도서 수를 계산하고
    상위 10명을 반환한다.

    person_column:
        original_author 또는 translator
    """

    # 도서 식별자와 인물 이름만 선택한다.
    # 저자나 역자가 없는 null 데이터는 제외한다.
    people_data = dataframe[
        ["itemId", person_column]
    ].dropna().copy()

    # 공동 저자 또는 공동 역자는 쉼표로 연결되어 있다.
    # 예: "박용우, 김영아"
    # 이를 ["박용우", "김영아"] 형태로 분리한다.
    people_data[person_column] = (
        people_data[person_column]
        .astype(str)
        .str.split(",")
    )

    # 리스트로 분리된 인물들을 각각 별도의 행으로 만든다.
    people_data = people_data.explode(person_column)

    # 이름 앞뒤에 남아 있는 공백을 제거한다.
    people_data[person_column] = (
        people_data[person_column]
        .str.strip()
    )

    # 이름이 빈 문자열인 데이터는 제외한다.
    people_data = people_data[
        people_data[person_column] != ""
    ]

    # 같은 책에 같은 인물이 중복되어 있다면 한 번만 집계한다.
    people_data = people_data.drop_duplicates(
        subset=["itemId", person_column]
    )

    # 인물별로 서로 다른 itemId의 개수를 계산한다.
    people_count = (
        people_data
        .groupby(person_column)["itemId"]
        .nunique()
        .reset_index(name="book_count")
    )

    # 고유 도서 수가 많은 순서로 정렬한다.
    # 도서 수가 같으면 이름 순서로 정렬한다.
    people_count = people_count.sort_values(
        by=["book_count", person_column],
        ascending=[False, True]
    )

    # 상위 10명만 반환한다.
    return people_count.head(10)



# 5. 작가와 역자의 상위 10명 집계
author_top10 = get_top10_people(
    df,
    "original_author"
)

translator_top10 = get_top10_people(
    df,
    "translator"
)

# 터미널에서 집계 결과 확인
print("\n작가별 고유 도서 수 상위 10명")
print(author_top10.to_string(index=False))

print("\n역자별 고유 도서 수 상위 10명")
print(translator_top10.to_string(index=False))



# 6. 집계 결과를 CSV 파일로 저장
# utf-8-sig를 사용해서  한글이 깨지지 않고 열리게
author_top10.to_csv(
    author_csv_path,
    index=False,
    encoding="utf-8-sig"
)

translator_top10.to_csv(
    translator_csv_path,
    index=False,
    encoding="utf-8-sig"
)



# 7. 한글 폰트 설정
# Windows 기본 한글 폰트인 맑은 고딕 사용
plt.rcParams["font.family"] = "Malgun Gothic"

# 마이너스 기호가 깨지는 현상 방지
plt.rcParams["axes.unicode_minus"] = False



# 8. 그래프를 그리는 함수
def draw_top10_chart(
    ax,
    data,
    name_column,
    title,
    color
):
    """
    상위 10명 데이터를 가로 막대그래프로 그린다.
    """

    # barh 그래프에서는 마지막 데이터가 위쪽에 표시된다.
    # 1위가 위쪽에 나오도록 순서를 뒤집는다.
    plot_data = data.iloc[::-1]

    bars = ax.barh(
        plot_data[name_column],
        plot_data["book_count"],
        color=color
    )

    # 각 막대 끝에 고유 도서 수 표시
    ax.bar_label(
        bars,
        padding=3,
        fontsize=10
    )

    ax.set_title(
        title,
        fontsize=15,
        fontweight="bold"
    )

    ax.set_xlabel("고유 도서 수")
    ax.set_ylabel("")

    # 숫자를 정수 단위로 표시
    ax.xaxis.get_major_locator().set_params(integer=True)

    # 세로 방향 보조선 추가
    ax.grid(
        axis="x",
        linestyle="--",
        alpha=0.3
    )

    # 위쪽과 오른쪽 테두리 제거
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)



# 9. 작가와 역자 그래프 생성
fig, axes = plt.subplots(
    nrows=1,
    ncols=2,
    figsize=(16, 8)
)

# 왼쪽: 작가 상위 10명
draw_top10_chart(
    axes[0],
    author_top10,
    "original_author",
    "고유 도서 수 기준 작가 상위 10명",
    "#4C78A8"
)

# 오른쪽: 역자 상위 10명
draw_top10_chart(
    axes[1],
    translator_top10,
    "translator",
    "고유 도서 수 기준 역자 상위 10명",
    "#F28E2B"
)

fig.suptitle(
    "알라딘 베스트셀러 작가·역자 분석",
    fontsize=18,
    fontweight="bold"
)

plt.tight_layout(
    rect=[0, 0, 1, 0.95]
)



# 10. 그래프 저장 및 출력
fig.savefig(
    chart_path,
    dpi=300,
    bbox_inches="tight"
)

print(f"\n작가 집계 CSV 저장 완료: {author_csv_path}")
print(f"역자 집계 CSV 저장 완료: {translator_csv_path}")
print(f"그래프 이미지 저장 완료: {chart_path}")

# 그래프 창 출력
plt.show()