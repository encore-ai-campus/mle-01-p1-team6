import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client


def get_settings():
    workspace_dir = Path(__file__).resolve().parents[2]
    load_dotenv(workspace_dir / ".env", override=True)

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
