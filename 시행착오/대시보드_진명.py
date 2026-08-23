"""Streamlit navigation에서 매번 새로 실행되는 대시보드 진입점입니다."""

from pathlib import Path
import runpy


runpy.run_path(
    str(Path(__file__).resolve().parent / "app_pages" / "dashboard.py"),
    run_name="__dashboard_page__",
)
