"""CPS (Citation Signal Predictor) standalone scoring endpoint."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from api.auth.dependencies import require_auth
from api.schemas.cps import CPSScoreRequest, CPSScoreResponse

try:
    from core.cps_model.scorer import get_cps_scorer
except Exception:  # pragma: no cover
    def get_cps_scorer():  # type: ignore[misc]
        return None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/cps", tags=["cps"])


@router.post(
    "/score",
    response_model=CPSScoreResponse,
    dependencies=[Depends(require_auth)],
)
async def score_content(body: CPSScoreRequest) -> CPSScoreResponse:
    """Score markdown content for citation probability across AI engines.

    Returns a CPS score (0.0-1.0) for each engine and query combination.
    Requires torch + model checkpoint to be available on the server.
    """
    scorer = get_cps_scorer()
    if scorer is None:
        raise HTTPException(
            status_code=503,
            detail="CPS scoring unavailable — model or dependencies not loaded.",
        )

    try:
        result = await scorer.score_async(
            query_texts=body.target_queries,
            content_markdown=body.content_markdown,
            content_url=body.content_url,
        )
    except Exception:
        logger.exception("CPS scoring failed")
        raise HTTPException(
            status_code=500,
            detail="CPS scoring failed — see server logs for details.",
        )

    return CPSScoreResponse(**result)
