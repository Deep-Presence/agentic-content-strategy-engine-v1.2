"""JsonTopicDiscoveryDataService — filesystem-backed implementation of TopicDiscoveryDataServiceProtocol."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional


class JsonTopicDiscoveryDataService:
    """Filesystem-backed TD data service.

    Delegates to ``TopicDiscoveryStorage`` via ``asyncio.to_thread()``.
    """

    def __init__(self, artifacts_root: Path, *, backend: Optional["StorageBackend"] = None) -> None:
        from core.storage.backends import LocalStorageBackend

        self._root = artifacts_root
        self._backend = backend or LocalStorageBackend(artifacts_root)

    def _storage(self, effective_slug: str):
        from core.topic_discovery.storage import TopicDiscoveryStorage
        return TopicDiscoveryStorage(self._root, effective_slug, backend=self._backend)

    async def get_discovery_summary(self, effective_slug: str) -> Optional[dict]:
        def _read():
            storage = self._storage(effective_slug)
            manifest = storage.read_manifest()
            if not manifest.company_name:
                return None
            taxonomy = storage.get_latest_taxonomy()
            matrix = storage.get_latest_matrix()
            return {
                "slug": effective_slug,
                "company_name": manifest.company_name,
                "has_taxonomy": taxonomy is not None,
                "taxonomy_version": storage.get_latest_taxonomy_version(),
                "has_matrix": matrix is not None,
                "matrix_version": storage.get_latest_matrix_version(),
                "last_updated": manifest.last_updated,
            }
        return await asyncio.to_thread(_read)

    async def get_taxonomy(
        self,
        effective_slug: str,
        *,
        version: Optional[int] = None,
    ) -> Optional[dict]:
        def _read():
            storage = self._storage(effective_slug)
            if version is not None:
                tree = storage.read_taxonomy(version)
            else:
                tree = storage.get_latest_taxonomy()
            if tree is None:
                return None
            return tree.model_dump(mode="json") if hasattr(tree, "model_dump") else vars(tree)
        return await asyncio.to_thread(_read)

    async def get_matrix(
        self,
        effective_slug: str,
        *,
        version: Optional[int] = None,
    ) -> Optional[dict]:
        def _read():
            storage = self._storage(effective_slug)
            if version is not None:
                matrix = storage.read_matrix(version)
            else:
                matrix = storage.get_latest_matrix()
            if matrix is None:
                return None
            return matrix.model_dump(mode="json") if hasattr(matrix, "model_dump") else vars(matrix)
        return await asyncio.to_thread(_read)

    async def list_assignments(
        self,
        effective_slug: str,
        *,
        buyer_stage: Optional[str] = None,
        intent_type: Optional[str] = None,
        persona_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        def _read():
            storage = self._storage(effective_slug)
            matrix = storage.get_latest_matrix()
            if matrix is None:
                return {"items": [], "total": 0, "page": 1, "page_size": page_size}

            assignments = matrix.assignments or []

            # Filter
            if buyer_stage:
                assignments = [a for a in assignments if getattr(a, "buyer_stage", None) == buyer_stage]
            if intent_type:
                assignments = [a for a in assignments if getattr(a, "intent_type", None) == intent_type]
            if persona_id:
                assignments = [a for a in assignments if getattr(a, "persona_id", "") == persona_id]

            total = len(assignments)
            start = (page - 1) * page_size
            end = start + page_size
            page_items = assignments[start:end]

            return {
                "items": [
                    a.model_dump(mode="json") if hasattr(a, "model_dump") else vars(a)
                    for a in page_items
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
            }
        return await asyncio.to_thread(_read)

    async def get_scored_subdomains(
        self,
        effective_slug: str,
        *,
        version: Optional[int] = None,
    ) -> Optional[dict]:
        def _read():
            storage = self._storage(effective_slug)
            if version is not None:
                scored = storage.read_scoring(version)
            else:
                scored = storage.get_latest_scoring()
            if scored is None:
                return None
            return scored.model_dump(mode="json")
        return await asyncio.to_thread(_read)

    async def get_persona_affinity(
        self,
        effective_slug: str,
        *,
        persona_id: Optional[str] = None,
    ) -> Optional[dict]:
        def _read():
            storage = self._storage(effective_slug)
            index = storage.get_latest_persona_affinity()
            if index is None:
                return None
            data = index.model_dump(mode="json")
            # Optional persona_id filter: return only entries for that persona
            if persona_id and "persona_entries" in data:
                filtered = {persona_id: data["persona_entries"].get(persona_id, [])}
                data["persona_entries"] = filtered
                data["total_personas"] = 1 if filtered[persona_id] else 0
            return data
        return await asyncio.to_thread(_read)
