"""DbKBDataService — Postgres-backed implementation of KBDataServiceProtocol.

Uses KB-specific repositories for metadata queries. Content reads
delegate to filesystem via storage_key. Complex operations (health,
staleness) delegate to JsonKBDataService.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from core.db.repositories.kb_repo import (
    KBDocumentRepository,
    KBRunRepository,
    KBSynthesisRepository,
)
from core.db.repositories.pipeline_repo import PipelineRepository


class DbKBDataService:
    """Postgres-backed KB data service.

    Hybrid: metadata from DB via dedicated repos, content from filesystem.
    """

    def __init__(
        self,
        kb_run_repo: KBRunRepository,
        kb_doc_repo: KBDocumentRepository,
        kb_synth_repo: KBSynthesisRepository,
        pipeline_repo: PipelineRepository,
        artifacts_root: Path,
        *,
        backend: Optional["StorageBackend"] = None,
    ) -> None:
        from core.storage.backends import LocalStorageBackend

        self._kb_run_repo = kb_run_repo
        self._kb_doc_repo = kb_doc_repo
        self._kb_synth_repo = kb_synth_repo
        self._pipeline_repo = pipeline_repo
        self._artifacts_root = artifacts_root
        self._backend = backend or LocalStorageBackend(artifacts_root)

    def _read_file(self, storage_key: str) -> Optional[str]:
        """Read artifact content via storage backend."""
        return self._backend.read(storage_key)

    async def get_summary(self, effective_slug: str) -> dict:
        from core.db.enums import PipelineType

        kb_run = await self._kb_run_repo.get_by_effective_slug(effective_slug)
        if kb_run is None:
            return {
                "slug": effective_slug,
                "company_name": "",
                "docs": {},
                "synthesis_version": 0,
                "last_full_refresh": None,
            }

        documents = await self._kb_doc_repo.list_by_run(kb_run.id)
        synthesis = await self._kb_synth_repo.get_by_run(kb_run.id)
        run = await self._pipeline_repo.get_latest_completed(
            effective_slug, PipelineType.knowledge_base,
        )

        # Group by doc_type, keep latest version per doc_type
        docs: dict[str, dict] = {}
        for d in documents:
            if d.doc_type not in docs or d.version > docs[d.doc_type].get("version", 0):
                docs[d.doc_type] = {
                    "version": d.version,
                    "word_count": d.word_count,
                    "status": d.status or "draft",
                    "has_content": True,
                    "updated_at": d.created_at.isoformat() if d.created_at else None,
                }

        return {
            "slug": effective_slug,
            "company_name": "",
            "docs": docs,
            "synthesis_version": synthesis.version if synthesis else 0,
            "last_full_refresh": run.completed_at.isoformat() if run and run.completed_at else None,
        }

    async def get_doc(
        self,
        effective_slug: str,
        doc_type: str,
        *,
        version: Optional[int] = None,
    ) -> Optional[dict]:
        kb_run = await self._kb_run_repo.get_by_effective_slug(effective_slug)
        if kb_run is None:
            return None

        target = await self._kb_doc_repo.get_by_run_and_type(
            kb_run.id, doc_type, version=version,
        )
        if target is None:
            return None

        content_md = await asyncio.to_thread(self._read_file, target.storage_key)
        return {
            "doc_type": doc_type,
            "version": target.version,
            "content_md": content_md or "",
            "word_count": target.word_count,
            "sha256": target.content_hash,
        }

    async def get_synthesis(
        self,
        effective_slug: str,
        *,
        version: Optional[int] = None,
    ) -> Optional[dict]:
        kb_run = await self._kb_run_repo.get_by_effective_slug(effective_slug)
        if kb_run is None:
            return None

        synthesis = await self._kb_synth_repo.get_by_run(
            kb_run.id, version=version,
        )
        if synthesis is None:
            return None

        content_md = await asyncio.to_thread(self._read_file, synthesis.storage_key)
        return {
            "version": synthesis.version,
            "content_md": content_md or "",
            "word_count": synthesis.word_count,
            "sha256": synthesis.content_hash,
        }

    async def get_health(
        self,
        effective_slug: str,
        *,
        threshold_override: Optional[int] = None,
    ) -> dict:
        # Delegate to filesystem — staleness DAG is filesystem-only
        from core.services.json_kb_data import JsonKBDataService
        json_svc = JsonKBDataService(self._artifacts_root, backend=self._backend)
        return await json_svc.get_health(
            effective_slug, threshold_override=threshold_override,
        )

    async def get_staleness_report(self, effective_slug: str) -> dict:
        from core.services.json_kb_data import JsonKBDataService
        json_svc = JsonKBDataService(self._artifacts_root, backend=self._backend)
        return await json_svc.get_staleness_report(effective_slug)
