"""DB persistence hooks for the Topic Discovery pipeline.

After each pipeline stage writes artifacts to the filesystem, the pipeline
optionally calls the corresponding ``persist_*()`` function here to write
metadata into Postgres via the TD-specific repositories.

Design principles (mirrors ``core/research/persistence.py``):
- **Filesystem-first, DB-additive**: JSON always written first.
- **Graceful degradation**: Every function catches all exceptions — DB errors
  NEVER crash the pipeline.
- **Per-step transaction isolation**: Each function opens its own session,
  commits, and closes.
- **FK-safe ordering**: insert discovery → taxonomy → nodes → assignments.
"""
from __future__ import annotations

import logging
import uuid as _uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

logger = logging.getLogger(__name__)


# ── Guard ────────────────────────────────────────────────────────────────


def _should_persist(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
) -> bool:
    """Return True if DB persistence is configured."""
    return (
        session_factory is not None
        and run_id is not None
        and company_id is not None
    )


# ── Tree flattening ─────────────────────────────────────────────────────


def _flatten_taxonomy_tree(
    root_nodes: list,
    taxonomy_id: _uuid.UUID,
    *,
    parent_id: _uuid.UUID | None = None,
    _counter: list | None = None,
) -> List[Dict[str, Any]]:
    """Recursively flatten SubdomainNode tree into a flat list of dicts.

    Preserves existing Pydantic UUIDs (SubdomainNode.id parsed as UUID).
    Returns parent-before-child ordering (FK constraint safe).

    Each dict maps to SubdomainNodeModel fields.
    """
    if _counter is None:
        _counter = [0]

    flat: List[Dict[str, Any]] = []
    for node in root_nodes:
        # Preserve existing Pydantic UUID
        try:
            node_uuid = _uuid.UUID(node.id)
        except (ValueError, AttributeError):
            node_uuid = _uuid.uuid4()

        sort_idx = _counter[0]
        _counter[0] += 1

        flat.append({
            "id": node_uuid,
            "taxonomy_id": taxonomy_id,
            "parent_id": parent_id,
            "name": node.name,
            "description": getattr(node, "description", ""),
            "depth": getattr(node, "depth", 0),
            "source_provenance": getattr(node, "source_provenance", None),
            "confidence": getattr(node, "confidence", 0.0),
            "is_manually_added": getattr(node, "is_manually_added", False),
            "sort_order": sort_idx,
            "metadata_json": getattr(node, "metadata", None),
        })

        # Recurse into children
        children = getattr(node, "children", [])
        if children:
            flat.extend(
                _flatten_taxonomy_tree(
                    children, taxonomy_id,
                    parent_id=node_uuid, _counter=_counter,
                )
            )
    return flat


# ── Discovery hook ───────────────────────────────────────────────────────


async def persist_td_discovery(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    effective_slug: str,
    domain_name: str,
    *,
    product_id: _uuid.UUID | None = None,
    pipeline_run_id: _uuid.UUID | None = None,
) -> _uuid.UUID | None:
    """Create/update TopicDiscoveryModel at pipeline start.

    Returns the discovery_id (UUID) for subsequent hooks, or None if
    persistence is skipped or fails.
    """
    if not _should_persist(session_factory, run_id, company_id):
        return None
    assert session_factory is not None and run_id is not None and company_id is not None
    try:
        from core.db.enums import TDStatus
        from core.db.repositories.topic_discovery_repo import TopicDiscoveryRepository

        async with session_factory() as session:
            repo = TopicDiscoveryRepository(session)
            discovery = await repo.upsert_discovery(
                company_id=company_id,
                effective_slug=effective_slug,
                pipeline_run_id=pipeline_run_id or run_id,
                product_id=product_id,
                domain_name=domain_name,
                status=TDStatus.draft,
            )
            await session.commit()

        logger.info(
            "persist_td_discovery: %s stored for %s (id=%s)",
            effective_slug, effective_slug, discovery.id,
        )
        return discovery.id
    except Exception:
        logger.warning(
            "persist_td_discovery failed for %s, continuing without DB",
            effective_slug, exc_info=True,
        )
        return None


# ── Taxonomy hook ────────────────────────────────────────────────────────


async def persist_td_taxonomy(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    discovery_id: Optional[_uuid.UUID],
    taxonomy: Any,
    version: int,
) -> _uuid.UUID | None:
    """Persist TaxonomyTreeModel + SubdomainNodeModel rows AFTER HITL-1 approval.

    Steps:
    1. Upsert TaxonomyTreeModel with tree_json
    2. Delete existing subdomain nodes for this taxonomy (idempotent)
    3. Flatten taxonomy tree into flat list
    4. Bulk insert SubdomainNodeModel rows
    5. Update TopicDiscoveryModel.taxonomy_version

    Returns taxonomy_id for assignment hooks, or None.
    """
    if not _should_persist(session_factory, run_id, company_id):
        return None
    if discovery_id is None:
        return None
    assert session_factory is not None and run_id is not None and company_id is not None
    try:
        from core.db.enums import TDStatus
        from core.db.models.topic_discovery import SubdomainNodeModel
        from core.db.repositories.topic_discovery_repo import (
            SubdomainNodeRepository,
            TaxonomyTreeRepository,
            TopicDiscoveryRepository,
        )

        tree_json = taxonomy.model_dump(mode="json")

        async with session_factory() as session:
            tax_repo = TaxonomyTreeRepository(session)
            node_repo = SubdomainNodeRepository(session)
            disc_repo = TopicDiscoveryRepository(session)

            # 1. Upsert taxonomy
            tax_model = await tax_repo.upsert_taxonomy(
                discovery_id=discovery_id,
                version=version,
                tree_json=tree_json,
                total_subdomains=taxonomy.total_subdomains,
                max_depth=taxonomy.max_depth,
                coverage_score=taxonomy.coverage_score,
                chao1_estimate=taxonomy.chao1_estimate,
                capture_recapture_est=taxonomy.capture_recapture_est
                if isinstance(taxonomy.capture_recapture_est, dict)
                else {},
                status=TDStatus.approved,
            )
            taxonomy_id = tax_model.id

            # 2. Delete old nodes (idempotent)
            await node_repo.delete_by_taxonomy(taxonomy_id)

            # 3. Flatten tree
            flat_nodes = _flatten_taxonomy_tree(
                taxonomy.root_nodes, taxonomy_id,
            )

            # 4. Bulk insert nodes
            if flat_nodes:
                node_models = [
                    SubdomainNodeModel(**node_dict) for node_dict in flat_nodes
                ]
                await node_repo.bulk_create(node_models)

            # 5. Update discovery version
            await disc_repo.update_versions(
                discovery_id, taxonomy_version=version,
            )

            await session.commit()

        logger.info(
            "persist_td_taxonomy: v%d stored for discovery %s (%d nodes)",
            version, discovery_id, len(flat_nodes),
        )
        return taxonomy_id
    except Exception:
        logger.warning(
            "persist_td_taxonomy failed for discovery %s, continuing without DB",
            discovery_id, exc_info=True,
        )
        return None


# ── Assignment hook ──────────────────────────────────────────────────────


async def persist_td_assignments(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    discovery_id: Optional[_uuid.UUID],
    matrix: Any,
    version: int,
    *,
    taxonomy_id: _uuid.UUID | None = None,
) -> None:
    """Persist TopicAssignmentModel rows AFTER HITL-2 approval.

    Steps:
    1. Delete existing assignments for this discovery + version (idempotent)
    2. Map Pydantic enums → DB enums via .value
    3. Bulk insert TopicAssignmentModel rows
    4. Update TopicDiscoveryModel.matrix_version and status
    """
    if not _should_persist(session_factory, run_id, company_id):
        return
    if discovery_id is None:
        return
    assert session_factory is not None and run_id is not None and company_id is not None
    try:
        from core.db.enums import (
            AudienceSegmentType as DBAudienceSegmentType,
            BuyerStage as DBBuyerStage,
            IntentType as DBIntentType,
            RelevanceCell as DBRelevanceCell,
            TDStatus,
            TopicAssignmentStatus as DBTopicAssignmentStatus,
        )
        from core.db.models.topic_discovery import TopicAssignmentModel
        from core.db.repositories.topic_discovery_repo import (
            TopicAssignmentRepository,
            TopicDiscoveryRepository,
        )

        async with session_factory() as session:
            assign_repo = TopicAssignmentRepository(session)
            disc_repo = TopicDiscoveryRepository(session)

            # 1. Delete old assignments (idempotent)
            await assign_repo.delete_by_discovery(
                discovery_id, matrix_version=version,
            )

            # 2+3. Map and bulk insert
            models = []
            for a in matrix.assignments:
                try:
                    a_uuid = _uuid.UUID(a.id)
                except (ValueError, AttributeError):
                    a_uuid = _uuid.uuid4()

                models.append(TopicAssignmentModel(
                    id=a_uuid,
                    discovery_id=discovery_id,
                    matrix_version=version,
                    subdomain_node_id=None,  # FK link is best-effort
                    topic_text=a.topic_text,
                    buyer_stage=DBBuyerStage(a.buyer_stage.value),
                    intent_type=DBIntentType(a.intent_type.value),
                    audience_segment=a.audience_segment,
                    audience_segment_type=DBAudienceSegmentType(
                        a.audience_segment_type.value
                    ),
                    relevance=DBRelevanceCell(a.relevance.value),
                    priority_score=a.priority_score,
                    priority_factors=a.priority_factors
                    if isinstance(a.priority_factors, dict) else {},
                    status=DBTopicAssignmentStatus(a.status.value),
                    is_manually_added=getattr(a, "is_manually_added", False),
                    metadata_json=getattr(a, "metadata", None)
                    if isinstance(getattr(a, "metadata", None), dict) else {},
                ))

            if models:
                await assign_repo.bulk_create(models)

            # 4. Update discovery version + status
            await disc_repo.update_versions(
                discovery_id, matrix_version=version,
            )

            await session.commit()

        logger.info(
            "persist_td_assignments: v%d stored for discovery %s (%d assignments)",
            version, discovery_id, len(models),
        )
    except Exception:
        logger.warning(
            "persist_td_assignments failed for discovery %s, continuing without DB",
            discovery_id, exc_info=True,
        )


# ── Assignment status batch hook ──────────────────────────────────────────


async def persist_td_assignment_status_batch(
    session_factory: Optional[async_sessionmaker],
    assignment_ids: List[str],
    status: str,
) -> None:
    """Bulk-update TopicAssignmentModel.status for a list of assignment IDs.

    Used by the TD→Content orchestrator to transition assignments through
    not_started → in_gap_analysis → content_produced.
    """
    if session_factory is None or not assignment_ids:
        return
    try:
        from core.db.enums import TopicAssignmentStatus as DBTopicAssignmentStatus
        from core.db.repositories.topic_discovery_repo import TopicAssignmentRepository

        db_status = DBTopicAssignmentStatus(status)
        async with session_factory() as session:
            repo = TopicAssignmentRepository(session)
            for aid in assignment_ids:
                try:
                    a_uuid = _uuid.UUID(aid)
                except (ValueError, AttributeError):
                    continue
                await repo.update_assignment_status(a_uuid, db_status)
            await session.commit()
        logger.info(
            "persist_td_assignment_status_batch: %d assignments → %s",
            len(assignment_ids), status,
        )
    except Exception:
        logger.warning(
            "persist_td_assignment_status_batch failed for %d assignments",
            len(assignment_ids), exc_info=True,
        )


# ── Status update hook ───────────────────────────────────────────────────


async def persist_td_status_update(
    session_factory: Optional[async_sessionmaker],
    discovery_id: Optional[_uuid.UUID],
    status: str,
) -> None:
    """Update TopicDiscoveryModel.status on transitions."""
    if session_factory is None or discovery_id is None:
        return
    try:
        from core.db.enums import TDStatus
        from core.db.repositories.topic_discovery_repo import TopicDiscoveryRepository

        td_status = TDStatus(status)
        async with session_factory() as session:
            repo = TopicDiscoveryRepository(session)
            await repo.update_status(discovery_id, td_status)
            await session.commit()
        logger.info(
            "persist_td_status_update: discovery %s → %s",
            discovery_id, status,
        )
    except Exception:
        logger.warning(
            "persist_td_status_update failed for discovery %s",
            discovery_id, exc_info=True,
        )
