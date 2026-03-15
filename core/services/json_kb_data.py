"""JsonKBDataService — filesystem-backed implementation of KBDataServiceProtocol."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional


class JsonKBDataService:
    """Filesystem-backed KB data service.

    Delegates to ``KBStorage`` via ``asyncio.to_thread()``.
    """

    def __init__(self, artifacts_root: Path, *, backend: Optional["StorageBackend"] = None) -> None:
        from core.storage.backends import LocalStorageBackend

        self._root = artifacts_root
        self._backend = backend or LocalStorageBackend(artifacts_root)

    def _storage(self, effective_slug: str):
        from core.research.knowledge_base.storage import KBStorage
        return KBStorage(self._root, effective_slug, backend=self._backend)

    async def get_summary(self, effective_slug: str) -> dict:
        def _read():
            storage = self._storage(effective_slug)
            manifest = storage.read_manifest()
            docs = {}
            for dt_val, doc_meta in (manifest.documents or {}).items():
                latest = storage.get_latest_version(
                    _doc_type_from_str(dt_val)
                )
                docs[dt_val] = {
                    "version": doc_meta.current_version if doc_meta else 0,
                    "word_count": latest.word_count if latest else 0,
                    "has_content": latest is not None and bool(latest.content_md),
                    "updated_at": doc_meta.last_updated.isoformat() if doc_meta and doc_meta.last_updated else None,
                }
            return {
                "slug": effective_slug,
                "company_name": manifest.company_name,
                "docs": docs,
                "synthesis_version": manifest.synthesis_version,
                "last_full_refresh": manifest.last_full_refresh.isoformat() if manifest.last_full_refresh else None,
            }
        return await asyncio.to_thread(_read)

    async def get_doc(
        self,
        effective_slug: str,
        doc_type: str,
        *,
        version: Optional[int] = None,
    ) -> Optional[dict]:
        def _read():
            storage = self._storage(effective_slug)
            dt = _doc_type_from_str(doc_type)
            if version is not None:
                doc = storage.read_version(dt, version)
            else:
                doc = storage.get_latest_version(dt)
            if doc is None:
                return None
            return {
                "doc_type": doc_type,
                "version": doc.version,
                "content_md": doc.content_md,
                "word_count": doc.word_count,
                "sha256": doc.sha256,
            }
        return await asyncio.to_thread(_read)

    async def get_synthesis(
        self,
        effective_slug: str,
        *,
        version: Optional[int] = None,
    ) -> Optional[dict]:
        def _read():
            storage = self._storage(effective_slug)
            doc = storage.read_synthesis(version=version)
            if doc is None:
                return None
            return {
                "version": doc.version,
                "content_md": doc.content_md,
                "word_count": doc.word_count,
                "sha256": doc.sha256,
            }
        return await asyncio.to_thread(_read)

    async def get_health(
        self,
        effective_slug: str,
        *,
        threshold_override: Optional[int] = None,
    ) -> dict:
        def _read():
            storage = self._storage(effective_slug)
            report = storage.get_staleness_report(
                threshold_override=threshold_override,
            )
            return report.model_dump(mode="json") if hasattr(report, "model_dump") else vars(report)
        return await asyncio.to_thread(_read)

    async def get_staleness_report(self, effective_slug: str) -> dict:
        return await self.get_health(effective_slug)


def _doc_type_from_str(val: str):
    """Convert string to KBDocType enum."""
    from core.models.knowledge_base import KBDocType
    return KBDocType(val)
