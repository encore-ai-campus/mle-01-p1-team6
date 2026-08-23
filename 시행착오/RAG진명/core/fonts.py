# [제공 코드]
"""matplotlib 한글 폰트 설정: 운영체제별.

대시보드에서 seaborn/matplotlib 그래프의 한글 라벨이 깨지지 않게 합니다.
그래프를 그리기 전에 한 번 `apply_korean_font()`를 호출하세요.
"""

import platform

import matplotlib.pyplot as plt


def apply_korean_font() -> None:
    """운영체제에 맞는 한글 폰트를 matplotlib 전역에 적용합니다."""
    system = platform.system()
    if system == "Windows":
        plt.rc("font", family="Malgun Gothic")
    elif system == "Darwin":  # macOS
        plt.rc("font", family="AppleGothic")
    else:  # Linux
        plt.rc("font", family="NanumGothic")
    # 음수 부호(-)가 네모로 깨지는 것을 방지
    plt.rc("axes", unicode_minus=False)
