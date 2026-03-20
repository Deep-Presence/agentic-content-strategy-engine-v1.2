"""JsonVSGDataService — filesystem-backed implementation of VSGDataServiceProtocol."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional


class JsonVSGDataService:
    """Filesystem-backed VSG data service.

    Delegates to ``VoiceStyleGuideStorage`` via ``asyncio.to_thread()``.
    """

    def __init__(self, artifacts_root: Path, *, backend: Optional["StorageBackend"] = None) -> None:
        from core.storage.backends import LocalStorageBackend

        self._root = artifacts_root
        self._backend = backend or LocalStorageBackend(artifacts_root)

    def _storage(self, effective_slug: str):
        from core.research.voice_style_guide.storage import VoiceStyleGuideStorage
        return VoiceStyleGuideStorage(self._root, effective_slug, backend=self._backend)

    async def get_summary(self, effective_slug: str) -> dict:
        def _read():
            storage = self._storage(effective_slug)
            manifest = storage.read_manifest()
            guide = storage.get_latest_guide()
            return {
                "slug": effective_slug,
                "company_name": manifest.company_name,
                "has_guide": guide is not None,
                "guide_word_count": len(guide.split()) if guide else 0,
                "authors_count": len(storage.list_author_ids()),
                "active_authors": len(storage.list_active_author_ids()),
                "last_full_run": manifest.last_full_run.isoformat() if manifest.last_full_run else None,
            }
        return await asyncio.to_thread(_read)

    async def get_guide(
        self,
        effective_slug: str,
        *,
        version: Optional[int] = None,
    ) -> Optional[dict]:
        def _read():
            storage = self._storage(effective_slug)
            guide_md = storage.get_latest_guide()
            if guide_md is None:
                return None
            manifest = storage.read_manifest()
            return {
                "content_md": guide_md,
                "version": manifest.guide.current_version,
                "word_count": len(guide_md.split()),
                "last_updated": manifest.guide.last_updated.isoformat() if manifest.guide.last_updated else None,
                "source_authors": manifest.guide.source_authors,
            }
        return await asyncio.to_thread(_read)

    async def list_authors(self, effective_slug: str) -> list[dict]:
        def _read():
            storage = self._storage(effective_slug)
            manifest = storage.read_manifest()
            result = []
            for aid in storage.list_author_ids():
                meta = (manifest.authors or {}).get(aid)
                has_research = storage.get_latest_author_research(aid) is not None
                result.append({
                    "author_id": aid,
                    "name": meta.name if meta else aid,
                    "status": meta.status if meta else "unknown",
                    "has_research": has_research,
                })
            return result
        return await asyncio.to_thread(_read)

    async def get_author_research(
        self,
        effective_slug: str,
        author_id: str,
        *,
        version: Optional[int] = None,
    ) -> Optional[dict]:
        def _read():
            storage = self._storage(effective_slug)
            if version is not None:
                content = storage.read_author_research(author_id, version)
            else:
                content = storage.get_latest_author_research(author_id)
            if content is None:
                return None
            return {
                "author_id": author_id,
                "content_md": content,
                "word_count": len(content.split()),
            }
        return await asyncio.to_thread(_read)
