# [제공 코드]
"""대시보드용 데이터 로더: `@st.cache_data`로 캐싱.

CSV를 매 재실행마다 다시 읽으면 느리므로, 캐시 데코레이터로 한 번만 읽습니다.
`data/` 폴더의 CSV를 스크립트 위치 기준 상대 경로로 읽어 어디서 실행하든 동작합니다.
"""

from pathlib import Path

import pandas as pd
import streamlit as st

# 이 파일(core/) 기준으로 프로젝트 루트의 data/ 를 가리킵니다.
DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@st.cache_data
def load_csv(name: str) -> pd.DataFrame:
    """data/ 폴더의 CSV 하나를 DataFrame으로 읽습니다. (예: load_csv('titanic'))"""
    return pd.read_csv(DATA_DIR / f"{name}.csv")


@st.cache_data
def load_penguins() -> pd.DataFrame:
    """펭귄 데이터(종·서식지·부리/날개 치수·체중): 교안 대시보드 예제용."""
    return pd.read_csv(DATA_DIR / "penguins.csv")


@st.cache_data
def load_titanic() -> pd.DataFrame:
    """타이타닉 탑승객 데이터(생존·객실등급·성별·나이·요금): 과제 LV1용."""
    return pd.read_csv(DATA_DIR / "titanic.csv")


@st.cache_data
def load_taxis() -> pd.DataFrame:
    """뉴욕 택시 운행 데이터(거리·요금·팁·결제수단·지역): 과제 LV2용."""
    return pd.read_csv(DATA_DIR / "taxis.csv")


@st.cache_data
def load_diamonds() -> pd.DataFrame:
    """다이아몬드 데이터(캐럿·컷·색상·투명도·가격): 과제 LV3용."""
    return pd.read_csv(DATA_DIR / "diamonds.csv")
