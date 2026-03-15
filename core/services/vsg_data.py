"""VSGDataServiceProtocol — async interface for Voice Style Guide data reads."""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class VSGDataServiceProtocol(Protocol):
    """Async interface for Voice Style Guide data endpoints.

    Two implementations:
    - ``JsonVSGDataService``: filesystem-backed via ``asyncio.to_thread()``
    - ``DbVSGDataService``: Postgres metadata + filesystem content (Phase F)
    """

    async def get_summary(self, effective_slug: str) -> dict: ...

    async def get_guide(
        self,
        effective_slug: str,
        *,
        version: Optional[int] = None,
    ) -> Optional[dict]: ...

    async def list_authors(self, effective_slug: str) -> list[dict]: ...

    async def get_author_research(
        self,
        effective_slug: str,
        author_id: str,
        *,
        version: Optional[int] = None,
    ) -> Optional[dict]: ...
