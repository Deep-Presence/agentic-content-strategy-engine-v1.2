"""DbVSGDataService — Postgres-backed implementation of VSGDataServiceProtocol.

Uses VSG-specific repositories for metadata queries. Content reads
delegate to filesystem via storage_key.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from core.db.repositories.pipeline_repo import PipelineRepository
from core.db.repositories.vsg_repo import (
    VSGAuthorRepository,
    VSGGuideRepository,
    VSGRunRepository,
)


class DbVSGDataService:
    """Postgres-backed VSG data service.

    Hybrid: metadata from DB via dedicated repos, content from filesystem.
    """

    def __init__(
        self,
        vsg_run_repo: VSGRunRepository,
        vsg_author_repo: VSGAuthorRepository,
        vsg_guide_repo: VSGGuideRepository,
        pipeline_repo: PipelineRepository,
        artifacts_root: Path,
        *,
        backend: Optional["StorageBackend"] = None,
    ) -> None:
        from core.storage.backends import LocalStorageBackend

        self._vsg_run_repo = vsg_run_repo
        self._vsg_author_repo = vsg_author_repo
        self._vsg_guide_repo = vsg_guide_repo
        self._pipeline_repo = pipeline_repo
        self._artifacts_root = artifacts_root
        self._backend = backend or LocalStorageBackend(artifacts_root)

    def _read_file(self, storage_key: str) -> Optional[str]:
        """Read artifact content via storage backend."""
        return self._backend.read(storage_key)

    async def get_summary(self, effective_slug: str) -> dict:
        from core.db.enums import PipelineType

        vsg_run = await self._vsg_run_repo.get_by_effective_slug(effective_slug)

        authors_count = 0
        has_guide = False
        guide_word_count = 0
        if vsg_run is not None:
            authors = await self._vsg_author_repo.list_by_run(vsg_run.id)
            # Deduplicate by author_id
            seen_authors: set[str] = set()
            for a in authors:
                seen_authors.add(a.author_id)
            authors_count = len(seen_authors)

            guide = await self._vsg_guide_repo.get_by_run(vsg_run.id)
            if guide is not None:
                has_guide = True
                guide_word_count = guide.word_count

        run = await self._pipeline_repo.get_latest_completed(
            effective_slug, PipelineType.voice_style_guide,
        )

        return {
            "slug": effective_slug,
            "company_name": "",
            "has_guide": has_guide,
            "guide_word_count": guide_word_count,
            "authors_count": authors_count,
            "active_authors": authors_count,
            "last_full_run": run.completed_at.isoformat() if run and run.completed_at else None,
        }

    async def get_guide(
        self,
        effective_slug: str,
        *,
        version: Optional[int] = None,
    ) -> Optional[dict]:
        vsg_run = await self._vsg_run_repo.get_by_effective_slug(effective_slug)
        if vsg_run is None:
            return None

        guide = await self._vsg_guide_repo.get_by_run(
            vsg_run.id, version=version,
        )
        if guide is None:
            return None

        content_md = await asyncio.to_thread(self._read_file, guide.storage_key)
        if content_md is None:
            return None

        return {
            "content_md": content_md,
            "version": guide.version,
            "word_count": guide.word_count,
            "last_updated": guide.created_at.isoformat() if guide.created_at else None,
            "source_authors": guide.source_authors or [],
        }

    async def list_authors(self, effective_slug: str) -> list[dict]:
        vsg_run = await self._vsg_run_repo.get_by_effective_slug(effective_slug)
        if vsg_run is None:
            return []

        authors = await self._vsg_author_repo.list_by_run(vsg_run.id)

        # Group by author_id, keep latest version
        best: dict[str, object] = {}
        for a in authors:
            if a.author_id not in best or a.version > best[a.author_id].version:
                best[a.author_id] = a

        return [
            {
                "author_id": aid,
                "name": a.name,
                "status": a.status or "unknown",
                "has_research": True,
            }
            for aid, a in best.items()
        ]

    async def get_author_research(
        self,
        effective_slug: str,
        author_id: str,
        *,
        version: Optional[int] = None,
    ) -> Optional[dict]:
        vsg_run = await self._vsg_run_repo.get_by_effective_slug(effective_slug)
        if vsg_run is None:
            return None

        target = await self._vsg_author_repo.get_by_run_and_author_id(
            vsg_run.id, author_id, version=version,
        )
        if target is None:
            return None

        content_md = await asyncio.to_thread(self._read_file, target.storage_key)
        if content_md is None:
            return None

        return {
            "author_id": author_id,
            "content_md": content_md,
            "word_count": target.word_count,
        }
