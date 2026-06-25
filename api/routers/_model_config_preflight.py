"""Shared API helpers for workspace BYOK model-config preflight."""
from __future__ import annotations

from collections.abc import Sequence

from fastapi import HTTPException

from core.model_config.service import ModelConfigService


async def preflight_model_config_or_409(
    model_config_service: ModelConfigService,
    workspace_id: str,
    agent_keys: Sequence[str],
    *,
    message: str,
) -> None:
    """Raise a consistent 409 response when workspace BYOK setup is incomplete."""
    required_agent_keys = list(dict.fromkeys(agent_keys))
    result = await model_config_service.preflight(workspace_id, required_agent_keys)
    if result.ok:
        return

    detail = result.model_dump(mode="json")
    detail.update(
        {
            "code": "byok_model_config_required",
            "reason": "model_config_required",
            "message": message,
            "required_agent_keys": required_agent_keys,
        }
    )
    raise HTTPException(status_code=409, detail=detail)
