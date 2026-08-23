"""세 번째 도서 검색 페이지의 Streamlit 진입점입니다."""

from pathlib import Path
import runpy


runpy.run_path(
    str(Path(__file__).resolve().parent / "app_pages" / "search.py"),
    run_name="__book_search_page__",
)
