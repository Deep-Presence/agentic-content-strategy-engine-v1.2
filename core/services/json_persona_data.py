"""JsonPersonaDataService — filesystem-backed implementation of PersonaDataServiceProtocol."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional


class JsonPersonaDataService:
    """Filesystem-backed persona data service.

    Delegates to ``PersonaStorage`` via ``asyncio.to_thread()``.
    """

    def __init__(self, artifacts_root: Path, *, backend: Optional["StorageBackend"] = None) -> None:
        from core.storage.backends import LocalStorageBackend

        self._root = artifacts_root
        self._backend = backend or LocalStorageBackend(artifacts_root)

    def _storage(self, effective_slug: str):
        from core.research.audience_persona.storage import PersonaStorage
        return PersonaStorage(self._root, effective_slug, backend=self._backend)

    async def list_personas(self, effective_slug: str) -> list[dict]:
        def _read():
            storage = self._storage(effective_slug)
            manifest = storage.read_manifest()
            result = []
            for pid in storage.list_persona_ids():
                meta = (manifest.personas or {}).get(pid)
                latest = storage.get_latest_version(pid)
                result.append({
                    "persona_id": pid,
                    "persona_name": meta.persona_name if meta else pid,
                    "tagline": meta.tagline if meta else "",
                    "kind": meta.kind if meta else "secondary",
                    "status": meta.status if meta else "unknown",
                    "current_version": meta.current_version if meta else 0,
                    "last_updated": meta.last_updated.isoformat() if meta and meta.last_updated else None,
                    "created_by": meta.created_by if meta else "agent",
                    "word_count": latest.get("word_count", 0) if latest else 0,
                    "has_content": latest is not None,
                })
            return result
        return await asyncio.to_thread(_read)

    async def get_persona(
        self,
        effective_slug: str,
        persona_id: str,
        *,
        version: Optional[int] = None,
    ) -> Optional[dict]:
        def _read():
            storage = self._storage(effective_slug)
            if version is not None:
                doc = storage.read_version(persona_id, version)
            else:
                doc = storage.get_latest_version(persona_id)
            if doc is None:
                return None
            return {
                "persona_id": persona_id,
                "version": doc.get("version", 1),
                "content_md": doc.get("content_md", ""),
                "word_count": doc.get("word_count", 0),
                "sha256": doc.get("sha256"),
            }
        return await asyncio.to_thread(_read)

    async def get_summary(self, effective_slug: str) -> dict:
        def _read():
            storage = self._storage(effective_slug)
            manifest = storage.read_manifest()
            total = len(storage.list_persona_ids())
            active = len(storage.list_active_persona_ids())
            return {
                "slug": effective_slug,
                "company_name": manifest.company_name,
                "total_personas": total,
                "active_personas": active,
                "last_full_run": manifest.last_full_run.isoformat() if manifest.last_full_run else None,
                "kb_synthesis_version": manifest.kb_synthesis_version,
            }
        return await asyncio.to_thread(_read)

    async def check_staleness(
        self,
        effective_slug: str,
        *,
        kb_synthesis_version: Optional[int] = None,
    ) -> dict:
        def _read():
            storage = self._storage(effective_slug)
            stale_personas = []
            for pid in storage.list_active_persona_ids():
                if storage.check_staleness(pid):
                    stale_personas.append(pid)
            kb_stale = False
            if kb_synthesis_version is not None:
                kb_stale = storage.check_kb_staleness(kb_synthesis_version)
            return {
                "slug": effective_slug,
                "stale_personas": stale_personas,
                "kb_stale": kb_stale,
                "total_active": len(storage.list_active_persona_ids()),
            }
        return await asyncio.to_thread(_read)
