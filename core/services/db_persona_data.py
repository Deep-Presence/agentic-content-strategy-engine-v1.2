"""DbPersonaDataService — Postgres-backed implementation of PersonaDataServiceProtocol.

Uses AP-specific repositories for metadata queries. Content reads
delegate to filesystem via storage_key.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from core.db.repositories.persona_repo import (
    PersonaProfileRepository,
    PersonaRunRepository,
)
from core.db.repositories.pipeline_repo import PipelineRepository


class DbPersonaDataService:
    """Postgres-backed persona data service.

    Hybrid: metadata from DB via dedicated repos, content from filesystem.
    """

    def __init__(
        self,
        persona_run_repo: PersonaRunRepository,
        persona_profile_repo: PersonaProfileRepository,
        pipeline_repo: PipelineRepository,
        artifacts_root: Path,
        *,
        backend: Optional["StorageBackend"] = None,
    ) -> None:
        from core.storage.backends import LocalStorageBackend

        self._persona_run_repo = persona_run_repo
        self._persona_profile_repo = persona_profile_repo
        self._pipeline_repo = pipeline_repo
        self._artifacts_root = artifacts_root
        self._backend = backend or LocalStorageBackend(artifacts_root)

    def _read_file(self, storage_key: str) -> Optional[str]:
        """Read artifact content via storage backend."""
        return self._backend.read(storage_key)

    async def list_personas(self, effective_slug: str) -> list[dict]:
        persona_run = await self._persona_run_repo.get_by_effective_slug(effective_slug)
        if persona_run is None:
            return []

        profiles = await self._persona_profile_repo.list_by_run(persona_run.id)

        # Group by persona_id, keep latest version
        best: dict[str, object] = {}
        for p in profiles:
            if p.persona_id not in best or p.version > best[p.persona_id].version:
                best[p.persona_id] = p

        result = []
        for pid, p in best.items():
            result.append({
                "persona_id": pid,
                "persona_name": p.persona_name,
                "tagline": p.tagline or "",
                "kind": p.kind or "secondary",
                "status": p.status or "unknown",
                "current_version": p.version,
                "last_updated": p.created_at.isoformat() if p.created_at else None,
                "created_by": p.created_by or "agent",
                "word_count": p.word_count,
                "has_content": True,
            })
        return result

    async def get_persona(
        self,
        effective_slug: str,
        persona_id: str,
        *,
        version: Optional[int] = None,
    ) -> Optional[dict]:
        persona_run = await self._persona_run_repo.get_by_effective_slug(effective_slug)
        if persona_run is None:
            return None

        target = await self._persona_profile_repo.get_by_run_and_persona_id(
            persona_run.id, persona_id, version=version,
        )
        if target is None:
            return None

        content_md = await asyncio.to_thread(self._read_file, target.storage_key)
        return {
            "persona_id": persona_id,
            "version": target.version,
            "content_md": content_md or "",
            "word_count": target.word_count,
            "sha256": target.content_hash,
        }

    async def get_summary(self, effective_slug: str) -> dict:
        from core.db.enums import PipelineType

        persona_run = await self._persona_run_repo.get_by_effective_slug(effective_slug)

        total = 0
        active = 0
        if persona_run is not None:
            profiles = await self._persona_profile_repo.list_by_run(persona_run.id)
            # Deduplicate by persona_id
            seen: dict[str, object] = {}
            for p in profiles:
                if p.persona_id not in seen or p.version > seen[p.persona_id].version:
                    seen[p.persona_id] = p
            total = len(seen)
            active = sum(
                1 for p in seen.values()
                if (p.status or "unknown") in ("draft", "fresh")
            )

        run = await self._pipeline_repo.get_latest_completed(
            effective_slug, PipelineType.audience_persona,
        )

        return {
            "slug": effective_slug,
            "company_name": "",
            "total_personas": total,
            "active_personas": active,
            "last_full_run": run.completed_at.isoformat() if run and run.completed_at else None,
            "kb_synthesis_version": persona_run.kb_synthesis_version if persona_run else None,
        }

    async def check_staleness(
        self,
        effective_slug: str,
        *,
        kb_synthesis_version: Optional[int] = None,
    ) -> dict:
        # Delegate to filesystem — staleness logic lives in PersonaStorage
        from core.services.json_persona_data import JsonPersonaDataService
        json_svc = JsonPersonaDataService(self._artifacts_root, backend=self._backend)
        return await json_svc.check_staleness(
            effective_slug, kb_synthesis_version=kb_synthesis_version,
        )
