"""KBDataServiceProtocol — async interface for Knowledge Base data reads."""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class KBDataServiceProtocol(Protocol):
    """Async interface for Knowledge Base data endpoints.

    Two implementations:
    - ``JsonKBDataService``: filesystem-backed via ``asyncio.to_thread()``
    - ``DbKBDataService``: Postgres metadata + filesystem content (Phase F)
    """

    async def get_summary(self, effective_slug: str) -> dict: ...

    async def get_doc(
        self,
        effective_slug: str,
        doc_type: str,
        *,
        version: Optional[int] = None,
    ) -> Optional[dict]: ...

    async def get_synthesis(
        self,
        effective_slug: str,
        *,
        version: Optional[int] = None,
    ) -> Optional[dict]: ...

    async def get_health(
        self,
        effective_slug: str,
        *,
        threshold_override: Optional[int] = None,
    ) -> dict: ...

    async def get_staleness_report(self, effective_slug: str) -> dict: ...
