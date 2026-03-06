"""CPS (Citation Signal Predictor) scoring request/response schemas."""
from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field, field_validator


class CPSScoreRequest(BaseModel):
    """Request body for standalone CPS scoring."""

    content_markdown: str = Field(
        ...,
        min_length=50,
        description="Markdown content to score (min 50 chars).",
    )
    target_queries: List[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="1-10 search queries to score against.",
    )
    content_url: str = Field(
        default="https://example.com",
        description="URL for authority feature extraction.",
    )

    @field_validator("target_queries")
    @classmethod
    def queries_non_empty(cls, v: List[str]) -> List[str]:
        for q in v:
            if not q.strip():
                raise ValueError("Each query must be non-empty")
        return v


class CPSScoreResponse(BaseModel):
    """Response from CPS scoring endpoint."""

    cps_score: float
    per_engine: Dict[str, float]
    per_query: List[Dict[str, Any]]
    model_version: str
    feature_config: str
    target_weight: float
