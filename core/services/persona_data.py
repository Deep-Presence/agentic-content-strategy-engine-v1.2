"""PersonaDataServiceProtocol — async interface for Audience Persona data reads."""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class PersonaDataServiceProtocol(Protocol):
    """Async interface for Audience Persona data endpoints.

    Two implementations:
    - ``JsonPersonaDataService``: filesystem-backed via ``asyncio.to_thread()``
    - ``DbPersonaDataService``: Postgres metadata + filesystem content (Phase F)
    """

    async def list_personas(self, effective_slug: str) -> list[dict]: ...

    async def get_persona(
        self,
        effective_slug: str,
        persona_id: str,
        *,
        version: Optional[int] = None,
    ) -> Optional[dict]: ...

    async def get_summary(self, effective_slug: str) -> dict: ...

    async def check_staleness(
        self,
        effective_slug: str,
        *,
        kb_synthesis_version: Optional[int] = None,
    ) -> dict: ...
