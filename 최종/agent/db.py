import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent


def get_settings():
    # .env가 agent 폴더가 아니라 프로젝트 상위 폴더에 있어도 찾습니다.
    env_candidates = (
        BASE_DIR / ".env",
        PROJECT_ROOT / ".env",
        Path.cwd() / ".env",
    )
    for env_path in env_candidates:
        if env_path.exists():
            load_dotenv(env_path, override=True)
            break

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_PUBLISHABLE_KEY")

    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL 또는 SUPABASE_PUBLISHABLE_KEY가 없습니다. "
            ".env 파일을 확인하세요."
        )

    return url, key


def create_supabase_client():
    url, key = get_settings()
    return create_client(url, key)
