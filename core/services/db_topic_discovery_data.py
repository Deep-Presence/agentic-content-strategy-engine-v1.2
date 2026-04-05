"""DbTopicDiscoveryDataService — Postgres-backed implementation of TopicDiscoveryDataServiceProtocol.

Uses TD-specific repositories for all queries.  No JSON filesystem fallback.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Optional

from core.db.repositories.topic_discovery_repo import (
    PersonaAffinityRepository,
    SourceResultRepository,
    SubdomainNodeRepository,
    TopicAssignmentRepository,
    TopicDiscoveryRepository,
    TaxonomyTreeRepository,
)


class DbTopicDiscoveryDataService:
    """Postgres-backed TD data service.

    Metadata + content queries from DB via repos.
    Returns None when DB data is missing (no filesystem fallback).
    """

    def __init__(
        self,
        td_repo: TopicDiscoveryRepository,
        taxonomy_repo: TaxonomyTreeRepository,
        assignment_repo: TopicAssignmentRepository,
        *,
        node_repo: Optional[SubdomainNodeRepository] = None,
        source_result_repo: Optional[SourceResultRepository] = None,
        persona_affinity_repo: Optional[PersonaAffinityRepository] = None,
    ) -> None:
        self._td_repo = td_repo
        self._taxonomy_repo = taxonomy_repo
        self._assignment_repo = assignment_repo
        self._node_repo = node_repo
        self._source_result_repo = source_result_repo
        self._persona_affinity_repo = persona_affinity_repo

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
            "scoring_version": row.scoring_version or 0,
            "persona_affinity_version": row.persona_affinity_version or 0,
            "status": row.status.value if row.status else None,
            "last_updated": row.updated_at.isoformat() if row.updated_at else None,
        }

    async def get_taxonomy(
        self,
        effective_slug: str,
        *,
        version: Optional[int] = None,
    ) -> Optional[dict]:
        discovery = await self._td_repo.get_by_effective_slug(effective_slug)
        if discovery is None:
            return None

        tax = await self._taxonomy_repo.get_by_discovery(
            discovery.id, version=version,
        )
        if tax is not None and tax.tree_json is not None:
            return tax.tree_json

        return None

    async def get_matrix(
        self,
        effective_slug: str,
        *,
        version: Optional[int] = None,
    ) -> Optional[dict]:
        discovery = await self._td_repo.get_by_effective_slug(effective_slug)
        if discovery is None:
            return None

        items = await self._assignment_repo.get_by_discovery(
            discovery.id, matrix_version=version,
        )
        if not items:
            return None

        assignments = []
        for r in items:
            assignments.append({
                "id": str(r.id),
                "subdomain_id": r.subdomain_id_text or "",
                "subdomain_name": r.subdomain_name or "",
                "topic_text": r.topic_text,
                "buyer_stage": r.buyer_stage.value if r.buyer_stage else "tofu",
                "intent_type": r.intent_type.value if r.intent_type else "informational",
                "audience_segment": r.audience_segment,
                "audience_segment_type": r.audience_segment_type.value if r.audience_segment_type else "individual_persona",
                "relevance": r.relevance.value if r.relevance else "relevant",
                "priority_score": r.priority_score or 0.0,
                "priority_factors": r.priority_factors or {},
                "status": r.status.value if r.status else "not_started",
                "is_manually_added": r.is_manually_added,
                "metadata": r.metadata_json or {},
                "persona_id": r.persona_id,
                "persona_name": r.persona_name,
            })

        return {
            "version": version or discovery.matrix_version or 1,
            "status": "approved",
            "assignments": assignments,
            "total_assignments": len(assignments),
        }

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
    ) -> dict:
        discovery = await self._td_repo.get_by_effective_slug(effective_slug)
        if discovery is None:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}

        # Map string filters to DB enums
        bs_enum = None
        it_enum = None
        status_enum = None
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
        if status:
            from core.db.enums import TopicAssignmentStatus
            try:
                status_enum = TopicAssignmentStatus(status)
            except ValueError:
                pass

        items, total = await self._assignment_repo.list_paginated(
            discovery.id,
            buyer_stage=bs_enum,
            intent_type=it_enum,
            persona_id=persona_id,
            status=status_enum,
            page=page,
            page_size=page_size,
        )

        result_items = [
            {
                "id": str(r.id),
                "topic_text": r.topic_text,
                "buyer_stage": r.buyer_stage.value if r.buyer_stage else None,
                "intent_type": r.intent_type.value if r.intent_type else None,
                "audience_segment": r.audience_segment,
                "relevance": r.relevance.value if r.relevance else None,
                "priority_score": r.priority_score,
                "status": r.status.value if r.status else None,
                "persona_id": r.persona_id,
                "persona_name": r.persona_name,
                "subdomain_id": r.subdomain_id_text,
                "subdomain_name": r.subdomain_name,
                "is_manually_added": r.is_manually_added,
                "metadata": r.metadata_json or {},
            }
            for r in items
        ]

        return {
            "items": result_items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def update_assignment_status(
        self,
        effective_slug: str,
        assignment_id: str,
        status: str,
    ) -> Optional[dict]:
        discovery = await self._td_repo.get_by_effective_slug(effective_slug)
        if discovery is None:
            return None

        from core.db.enums import TopicAssignmentStatus
        try:
            status_enum = TopicAssignmentStatus(status)
        except ValueError:
            return None

        updated = await self._assignment_repo.update_assignment_status(
            assignment_id, status_enum,
        )
        if updated is None:
            return None

        return {
            "id": str(updated.id),
            "status": updated.status.value if updated.status else status,
            "topic_text": updated.topic_text,
        }

    async def create_assignment(
        self,
        effective_slug: str,
        assignment_data: dict,
    ) -> dict:
        discovery = await self._td_repo.get_by_effective_slug(effective_slug)
        if discovery is None:
            raise ValueError("No discovery found for this slug.")

        from core.db.models.topic_discovery import TopicAssignmentModel
        from core.db.enums import BuyerStage, IntentType, TopicAssignmentStatus

        import uuid as _uuid

        model = TopicAssignmentModel(
            id=_uuid.uuid4(),
            discovery_id=discovery.id,
            matrix_version=discovery.matrix_version or 1,
            topic_text=assignment_data.get("topic_text", ""),
            subdomain_id_text=assignment_data.get("subdomain_id", ""),
            subdomain_name=assignment_data.get("subdomain_name", ""),
            buyer_stage=BuyerStage(assignment_data.get("buyer_stage", "tofu")),
            intent_type=IntentType(assignment_data.get("intent_type", "informational")),
            persona_id=assignment_data.get("persona_id", ""),
            persona_name=assignment_data.get("persona_name", ""),
            priority_score=assignment_data.get("priority_score", 0.5),
            status=TopicAssignmentStatus.not_started,
            is_manually_added=True,
        )

        created = await self._assignment_repo.bulk_create([model])
        row = created[0]

        return {
            "id": str(row.id),
            "topic_text": row.topic_text,
            "buyer_stage": row.buyer_stage.value if row.buyer_stage else "tofu",
            "intent_type": row.intent_type.value if row.intent_type else "informational",
            "persona_id": row.persona_id,
            "persona_name": row.persona_name,
            "priority_score": row.priority_score,
            "status": row.status.value if row.status else "not_started",
            "is_manually_added": True,
            "subdomain_id": row.subdomain_id_text or "",
            "subdomain_name": row.subdomain_name or "",
        }

    async def get_scored_subdomains(
        self,
        effective_slug: str,
        *,
        version: Optional[int] = None,
    ) -> Optional[dict]:
        if self._node_repo is None:
            return None

        discovery = await self._td_repo.get_by_effective_slug(effective_slug)
        if discovery is None:
            return None

        tax = await self._taxonomy_repo.get_by_discovery(
            discovery.id, version=version,
        )
        if tax is None:
            return None

        nodes = await self._node_repo.get_by_taxonomy(tax.id)
        if not nodes:
            return None

        # Check if any node has scoring data
        has_scoring = any(n.priority_score is not None for n in nodes)
        if not has_scoring:
            return None

        scores = []
        for rank, n in enumerate(
            sorted(nodes, key=lambda x: x.priority_score or 0.0, reverse=True),
            start=1,
        ):
            scores.append({
                "subdomain_id": str(n.id),
                "subdomain_name": n.name,
                "composite_score": n.priority_score or 0.0,
                "signal_scores": (n.priority_factors or {}),
                "signal_weights": {},
                "signals_available": list((n.priority_factors or {}).keys()),
                "rank": rank,
                "persona_affinity": n.persona_affinity_json or {},
                "metadata": n.metadata_json or {},
            })

        return {
            "version": discovery.scoring_version or 1,
            "scores": scores,
            "total_scored": len(scores),
            "signals_used": [],
            "weights_config": {},
        }

    async def get_persona_affinity(
        self,
        effective_slug: str,
        *,
        persona_id: Optional[str] = None,
    ) -> Optional[dict]:
        if self._persona_affinity_repo is None:
            return None

        discovery = await self._td_repo.get_by_effective_slug(effective_slug)
        if discovery is None:
            return None

        if persona_id:
            rows = await self._persona_affinity_repo.get_by_persona(
                discovery.id, persona_id,
            )
        else:
            rows = await self._persona_affinity_repo.get_by_discovery(
                discovery.id,
            )

        if not rows:
            return None

        # Group by persona_id and collect metadata
        persona_entries: dict = defaultdict(list)
        persona_metadata: dict = {}
        for r in rows:
            persona_entries[r.persona_id].append({
                "subdomain_id": r.subdomain_id_str or str(r.subdomain_node_id or ""),
                "subdomain_name": r.subdomain_name or "",
                "affinity_score": r.affinity_score,
                "provenance": r.provenance,
                "pain_points": r.pain_points or [],
            })
            # First occurrence per persona_id populates metadata
            if r.persona_id not in persona_metadata:
                persona_metadata[r.persona_id] = {
                    "persona_name": r.persona_name or "",
                    "career_role": getattr(r, "career_role", "") or "",
                }

        return {
            "version": discovery.persona_affinity_version or 1,
            "persona_entries": dict(persona_entries),
            "persona_metadata": persona_metadata,
            "total_personas": len(persona_entries),
            "total_subdomains": len({
                e["subdomain_id"]
                for entries in persona_entries.values()
                for e in entries
            }),
        }

    # ── Tree CRUD operations ──────────────────────────────────────────

    async def update_node(
        self,
        effective_slug: str,
        node_id: str,
        **kwargs,
    ) -> Optional[dict]:
        """Update a single taxonomy node's attributes."""
        import uuid as _uuid

        if self._node_repo is None:
            return None

        try:
            nid = _uuid.UUID(node_id)
        except ValueError:
            return None

        result = await self._node_repo.update_node(nid, **kwargs)
        if result is None:
            return None

        return {
            "id": str(result.id),
            "name": result.name,
            "description": result.description or "",
            "parent_id": str(result.parent_id) if result.parent_id else None,
            "depth": result.depth,
            "expansion_status": result.expansion_status or "not_expanded",
        }

    async def delete_node(
        self,
        effective_slug: str,
        node_id: str,
        *,
        reparent_children: bool = True,
    ) -> bool:
        """Delete a single taxonomy node. Reparents children by default."""
        import uuid as _uuid

        if self._node_repo is None:
            return False

        try:
            nid = _uuid.UUID(node_id)
        except ValueError:
            return False

        return await self._node_repo.delete_single_node(
            nid, reparent_children=reparent_children,
        )

    async def create_node(
        self,
        effective_slug: str,
        *,
        name: str,
        description: str = "",
        parent_id: Optional[str] = None,
    ) -> Optional[dict]:
        """Add a new manually-added taxonomy node."""
        import uuid as _uuid
        from core.db.models.topic_discovery import SubdomainNodeModel

        if self._node_repo is None:
            return None

        # Resolve taxonomy_id
        discovery = await self._td_repo.get_by_effective_slug(effective_slug)
        if discovery is None:
            return None

        taxonomy = await self._taxonomy_repo.get_by_discovery(discovery.id)
        if taxonomy is None:
            return None

        parent_uuid = None
        depth = 0
        if parent_id:
            try:
                parent_uuid = _uuid.UUID(parent_id)
                parent_node = await self._node_repo.get_by_id(parent_uuid)
                if parent_node:
                    depth = parent_node.depth + 1
            except ValueError:
                pass

        node = SubdomainNodeModel(
            taxonomy_id=taxonomy.id,
            parent_id=parent_uuid,
            name=name,
            description=description,
            depth=depth,
            is_manually_added=True,
            expansion_status="not_expanded",
        )
        self._node_repo._session.add(node)
        await self._node_repo._session.flush()

        return {
            "id": str(node.id),
            "name": node.name,
            "description": node.description or "",
            "parent_id": str(node.parent_id) if node.parent_id else None,
            "depth": node.depth,
            "expansion_status": "not_expanded",
        }
