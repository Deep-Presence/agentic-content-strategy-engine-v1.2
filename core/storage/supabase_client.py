from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from supabase import Client

from core.config.settings import settings


@lru_cache(maxsize=1)
def get_supabase_client() -> "Client":
    from supabase import create_client

    url = settings.effective_supabase_url
    key = settings.effective_supabase_key
    if not url or not key:
        raise RuntimeError(
            "Supabase env not set. Need SUPABASE_URL and one of SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY."
        )
    return create_client(url, key)
