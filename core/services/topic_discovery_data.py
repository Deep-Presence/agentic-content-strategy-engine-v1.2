"""TopicDiscoveryDataServiceProtocol — async interface for Topic Discovery data reads."""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class TopicDiscoveryDataServiceProtocol(Protocol):
    """Async interface for Topic Discovery data endpoints.

    Two implementations:
    - ``JsonTopicDiscoveryDataService``: filesystem-backed via ``asyncio.to_thread()``
    - ``DbTopicDiscoveryDataService``: Postgres-backed (Phase F)
    """

    async def get_discovery_summary(self, effective_slug: str) -> Optional[dict]: ...

    async def get_taxonomy(
        self,
        effective_slug: str,
        *,
        version: Optional[int] = None,
    ) -> Optional[dict]: ...

    async def get_matrix(
        self,
        effective_slug: str,
        *,
        version: Optional[int] = None,
    ) -> Optional[dict]: ...

    async def list_assignments(
        self,
        effective_slug: str,
        *,
        buyer_stage: Optional[str] = None,
        intent_type: Optional[str] = None,
        persona_id: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict: ...

    async def get_scored_subdomains(
        self,
        effective_slug: str,
        *,
        version: Optional[int] = None,
    ) -> Optional[dict]: ...

    async def get_persona_affinity(
        self,
        effective_slug: str,
        *,
        persona_id: Optional[str] = None,
    ) -> Optional[dict]: ...

    async def update_assignment_status(
        self,
        effective_slug: str,
        assignment_id: str,
        status: str,
    ) -> Optional[dict]: ...

    async def create_assignment(
        self,
        effective_slug: str,
        assignment_data: dict,
    ) -> dict: ...
