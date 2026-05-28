"""API-specific configuration loaded from environment variables."""
from __future__ import annotations

from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings


class ApiSettings(BaseSettings):
    """Settings specific to the FastAPI layer.

    All values can be overridden via environment variables prefixed with ``API_``.
    Example: ``API_CORS_ORIGINS='["https://app.example.com"]'``
    """

    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:3001"],
        description="Allowed CORS origins (JSON list)",
    )
    api_prefix: str = Field(
        default="/api/v1",
        description="URL prefix for all API routes",
    )
    max_concurrent_pipelines: int = Field(
        default=3,
        description="Max pipeline runs allowed in parallel",
    )
    max_concurrent_content_engine_per_company: int = Field(
        default=15,
        description="Max content-engine runs allowed in parallel per company",
    )

    model_config = {"env_prefix": "API_"}


api_settings = ApiSettings()
