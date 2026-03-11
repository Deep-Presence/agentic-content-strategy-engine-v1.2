"""DbTopicDiscoveryDataService — Postgres-backed implementation of TopicDiscoveryDataServiceProtocol.

Uses TD-specific repositories for metadata queries.  Content reads
(taxonomy tree JSON, matrix JSON) delegate to filesystem via
JsonTopicDiscoveryDataService.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.db.repositories.topic_discovery_repo import (
    TopicAssignmentRepository,
    TopicDiscoveryRepository,
    TaxonomyTreeRepository,
)


class DbTopicDiscoveryDataService:
    """Postgres-backed TD data service.

    Metadata queries from DB via repos.  Content (taxonomy tree JSON,
    matrix JSON) read from filesystem via storage path.
    """

    def __init__(
        self,
        td_repo: TopicDiscoveryRepository,
        taxonomy_repo: TaxonomyTreeRepository,
        assignment_repo: TopicAssignmentRepository,
        artifacts_root: Path,
        *,
        backend: Optional["StorageBackend"] = None,
    ) -> None:
        from core.storage.backends import LocalStorageBackend

        self._td_repo = td_repo
        self._taxonomy_repo = taxonomy_repo
        self._assignment_repo = assignment_repo
        self._artifacts_root = artifacts_root
        self._backend = backend or LocalStorageBackend(artifacts_root)

    async def get_discovery_summary(self, effective_slug: str) -> Optional[dict]:
        row = await self._td_repo.get_by_effective_slug(effective_slug)
        if row is None:
            return None

        return {
            "slug": effective_slug,
            "company_name": "",
            "has_taxonomy": (row.taxonomy_version or 0) > 0,
            "taxonomy_version": row.taxonomy_version or 0,
            "has_matrix": (row.matrix_version or 0) > 0,
            "matrix_version": row.matrix_version or 0,
            "last_updated": row.updated_at.isoformat() if row.updated_at else None,
        }

    async def get_taxonomy(
        self,
        effective_slug: str,
        *,
        version: Optional[int] = None,
    ) -> Optional[dict]:
        # Delegate to filesystem — taxonomy trees are large JSON blobs
        from core.services.json_topic_discovery_data import JsonTopicDiscoveryDataService

        json_svc = JsonTopicDiscoveryDataService(self._artifacts_root, backend=self._backend)
        return await json_svc.get_taxonomy(effective_slug, version=version)

    async def get_matrix(
        self,
        effective_slug: str,
        *,
        version: Optional[int] = None,
    ) -> Optional[dict]:
        from core.services.json_topic_discovery_data import JsonTopicDiscoveryDataService

        json_svc = JsonTopicDiscoveryDataService(self._artifacts_root, backend=self._backend)
        return await json_svc.get_matrix(effective_slug, version=version)

    async def list_assignments(
        self,
        effective_slug: str,
        *,
        buyer_stage: Optional[str] = None,
        intent_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        # Find discovery for slug
        discovery = await self._td_repo.get_by_effective_slug(effective_slug)
        if discovery is None:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}

        # Map string filters to DB enums
        bs_enum = None
        it_enum = None
        if buyer_stage:
            from core.db.enums import BuyerStage
            try:
                bs_enum = BuyerStage(buyer_stage)
            except ValueError:
                pass
        if intent_type:
            from core.db.enums import IntentType
            try:
                it_enum = IntentType(intent_type)
            except ValueError:
                pass

        items, total = await self._assignment_repo.list_paginated(
            discovery.id,
            buyer_stage=bs_enum,
            intent_type=it_enum,
            page=page,
            page_size=page_size,
        )

        return {
            "items": [
                {
                    "topic_text": r.topic_text,
                    "buyer_stage": r.buyer_stage.value if r.buyer_stage else None,
                    "intent_type": r.intent_type.value if r.intent_type else None,
                    "audience_segment": r.audience_segment,
                    "relevance": r.relevance.value if r.relevance else None,
                    "priority_score": r.priority_score,
                    "status": r.status.value if r.status else None,
                }
                for r in items
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
