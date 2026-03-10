"""BrandDataServiceProtocol — async interface for brand/research data retrieval."""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from api.schemas.brand_data import (
    ResearchArtifactsResponse,
    RunHistoryResponse,
)


@runtime_checkable
class BrandDataServiceProtocol(Protocol):
    """Async interface for brand data endpoints.

    Two implementations:
    - ``JsonBrandDataService``: wraps filesystem + TaskStore functions
    - ``DbBrandDataService``: SQL queries against Postgres (Phase 3, Step 3)
    """

    async def get_research_artifacts(
        self, slug: str,
    ) -> ResearchArtifactsResponse: ...

    async def get_run_history(
        self,
        slug: str,
        *,
        pipeline: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> RunHistoryResponse: ...
