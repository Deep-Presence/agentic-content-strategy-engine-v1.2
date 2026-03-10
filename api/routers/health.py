"""Health and readiness endpoints."""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter

from core.config.settings import settings

router = APIRouter(tags=["health"])

_REQUIRED_KEYS = [
    "openai_api_key",
    "anthropic_api_key",
    "perplexity_api_key",
]


@router.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@router.get("/readiness")
async def readiness() -> Dict[str, Any]:
    missing: List[str] = []
    for key in _REQUIRED_KEYS:
        if not getattr(settings, key, None):
            missing.append(key)
    return {"ready": len(missing) == 0, "missing_keys": missing}
