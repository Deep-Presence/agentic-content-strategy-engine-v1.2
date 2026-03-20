"""Health and readiness endpoints."""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Request

from core.config.settings import settings

router = APIRouter(tags=["health"])

_REQUIRED_KEYS = [
    "openai_api_key",
    "anthropic_api_key",
    "perplexity_api_key",
]


@router.get("/health")
async def health(request: Request) -> Dict[str, Any]:
    db_healthy = getattr(request.app.state, "db_healthy", False)
    pgvector = getattr(request.app.state, "pgvector_available", False)
    return {
        "status": "ok",
        "database": "connected" if db_healthy else "unavailable",
        "pgvector": "available" if pgvector else "unavailable",
    }


@router.get("/readiness")
async def readiness() -> Dict[str, Any]:
    missing: List[str] = []
    for key in _REQUIRED_KEYS:
        if not getattr(settings, key, None):
            missing.append(key)
    return {"ready": len(missing) == 0, "missing_keys": missing}
