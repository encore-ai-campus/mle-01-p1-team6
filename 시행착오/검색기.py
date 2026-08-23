"""기존 실행 경로와의 호환을 위한 도서 검색 바로가기입니다."""

from utils.theme import apply_library_theme

apply_library_theme()

from app_pages.search import *  # noqa: F401,F403
