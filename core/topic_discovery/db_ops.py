"""Async DB operations for the Topic Discovery pipeline.

Replaces ``TopicDiscoveryStorage`` (JSON filesystem) with direct Postgres
reads/writes via the TD-specific repositories.  Each function opens its own
session via ``session_factory()``, commits, and closes.

**No try/except swallowing** — errors propagate to the caller so the pipeline
fails visibly when the database is unavailable.

Design:
- Module-level async functions (no class).
- Naming: ``db_read_*``, ``db_write_*``, ``db_get_*``.
- Repos imported lazily inside function bodies (same pattern as persistence.py).
- Enum mapping: ``.value`` for Pydantic -> DB, enum class constructor for DB -> Pydantic.
"""
from __future__ import annotations

import logging
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import async_sessionmaker

from core.models.topic_discovery import (
    PersonaAffinityIndex,
    ScoredSubdomainList,
    TaxonomyTree,
    TopicAssignmentMatrix,
    TopicDiscoveryManifest,
    TopicDiscoveryStatus,
)

logger = logging.getLogger(__name__)


# ── Tree flattening (reused from persistence.py) ────────────────────────


def _flatten_taxonomy_for_db(
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

        # Persona affinity dict (Pydantic field name is "persona_affinity",
        # ORM column name is "persona_affinity_json")
        pa = getattr(node, "persona_affinity", None)

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
            "priority_score": getattr(node, "priority_score", 0.0),
            "priority_factors": getattr(node, "priority_factors", None),
            "persona_affinity_json": pa if isinstance(pa, dict) else None,
            "expansion_status": getattr(node, "expansion_status", "not_expanded"),
        })

        # Recurse into children
        children = getattr(node, "children", [])
        if children:
            flat.extend(
                _flatten_taxonomy_for_db(
                    children, taxonomy_id,
                    parent_id=node_uuid, _counter=_counter,
                )
            )
    return flat


# ── Pydantic ↔ DB enum mapping helpers ──────────────────────────────────


def _td_status_to_pydantic(db_status: Any) -> TopicDiscoveryStatus:
    """Convert DB TDStatus enum to Pydantic TopicDiscoveryStatus."""
    val = db_status.value if hasattr(db_status, "value") else str(db_status)
    return TopicDiscoveryStatus(val)


# ── 1. db_read_manifest ─────────────────────────────────────────────────


async def db_read_manifest(
    session_factory: async_sessionmaker,
    effective_slug: str,
) -> TopicDiscoveryManifest:
    """Read a TopicDiscoveryManifest from the DB.

    Builds the manifest from the DB row's columns (taxonomy_version,
    matrix_version, scoring_version, persona_affinity_version, status,
    manifest_json).  Returns a blank manifest if no row found.
    """
    from core.db.repositories.topic_discovery_repo import TopicDiscoveryRepository

    async with session_factory() as session:
        repo = TopicDiscoveryRepository(session)
        discovery = await repo.get_by_effective_slug(effective_slug)

    if discovery is None:
        logger.debug("db_read_manifest: no discovery for slug=%s, returning blank", effective_slug)
        return TopicDiscoveryManifest(slug=effective_slug, effective_slug=effective_slug)

    # Merge columns into manifest
    manifest_data: dict = discovery.manifest_json or {}
    manifest_data.update({
        "effective_slug": effective_slug,
        "taxonomy_version": discovery.taxonomy_version,
        "matrix_version": discovery.matrix_version,
        "scoring_version": discovery.scoring_version,
        "persona_affinity_version": discovery.persona_affinity_version,
        "status": _td_status_to_pydantic(discovery.status).value,
    })
    manifest = TopicDiscoveryManifest.model_validate(manifest_data)
    logger.debug(
        "db_read_manifest: loaded for slug=%s (tax_v=%d, mat_v=%d)",
        effective_slug, manifest.taxonomy_version, manifest.matrix_version,
    )
    return manifest


# ── 2. db_write_manifest ────────────────────────────────────────────────


async def db_write_manifest(
    session_factory: async_sessionmaker,
    discovery_id: _uuid.UUID,
    manifest: TopicDiscoveryManifest,
) -> None:
    """Update the TopicDiscoveryModel with manifest data."""
    from core.db.enums import TDStatus
    from core.db.repositories.topic_discovery_repo import TopicDiscoveryRepository

    async with session_factory() as session:
        repo = TopicDiscoveryRepository(session)
        discovery = await repo.get_by_id(discovery_id)
        if discovery is None:
            raise ValueError(f"db_write_manifest: discovery {discovery_id} not found")

        discovery.manifest_json = manifest.model_dump(mode="json")
        discovery.status = TDStatus(manifest.status.value)
        discovery.updated_at = datetime.now(timezone.utc)

        await repo.update_versions(
            discovery_id,
            taxonomy_version=manifest.taxonomy_version,
            matrix_version=manifest.matrix_version,
            scoring_version=manifest.scoring_version,
            persona_affinity_version=manifest.persona_affinity_version,
        )
        await session.commit()

    logger.info(
        "db_write_manifest: discovery %s updated (status=%s)",
        discovery_id, manifest.status.value,
    )


# ── 3. db_write_source_results ──────────────────────────────────────────


async def db_write_source_results(
    session_factory: async_sessionmaker,
    discovery_id: _uuid.UUID,
    source_results: List[Any],
    version: int,
) -> None:
    """Persist SourceResultModel rows for S1 source collection.

    Deletes existing results for this discovery (idempotent), then bulk inserts.
    """
    from core.db.models.topic_discovery import SourceResultModel
    from core.db.repositories.topic_discovery_repo import SourceResultRepository

    async with session_factory() as session:
        repo = SourceResultRepository(session)

        # Idempotent: delete existing results
        await repo.delete_by_discovery(discovery_id)

        models = []
        for sr in source_results:
            # Serialize candidates to JSON
            candidates_json = None
            if sr.candidates:
                candidates_json = [
                    c.model_dump(mode="json") if hasattr(c, "model_dump")
                    else vars(c)
                    for c in sr.candidates
                ]

            models.append(SourceResultModel(
                discovery_id=discovery_id,
                source=sr.source.value if hasattr(sr.source, "value") else str(sr.source),
                version=version,
                total_candidates=len(sr.candidates),
                total_rounds=getattr(sr, "total_rounds", 0),
                singletons=getattr(sr, "singletons", 0),
                doubletons=getattr(sr, "doubletons", 0),
                chao1_estimate=getattr(sr, "chao1_estimate", None),
                source_sample_coverage=getattr(sr, "source_sample_coverage", None),
                execution_time_s=getattr(sr, "execution_time_s", None),
                error=getattr(sr, "error", None),
                candidates_json=candidates_json,
            ))

        if models:
            await repo.bulk_create(models)
        await session.commit()

    logger.info(
        "db_write_source_results: %d sources stored for discovery %s (v%d)",
        len(models), discovery_id, version,
    )


# ── 4. db_write_coverage ────────────────────────────────────────────────


async def db_write_coverage(
    session_factory: async_sessionmaker,
    taxonomy_db_id: _uuid.UUID,
    coverage: Any,
) -> None:
    """Update taxonomy_trees.capture_recapture_est JSONB with coverage data."""
    from core.db.repositories.topic_discovery_repo import TaxonomyTreeRepository

    async with session_factory() as session:
        tax_repo = TaxonomyTreeRepository(session)
        taxonomy = await tax_repo.get_by_id(taxonomy_db_id)
        if taxonomy is None:
            raise ValueError(f"db_write_coverage: taxonomy {taxonomy_db_id} not found")

        taxonomy.capture_recapture_est = coverage.model_dump(mode="json")
        await session.flush()
        await session.commit()

    logger.info(
        "db_write_coverage: updated taxonomy %s with coverage data",
        taxonomy_db_id,
    )


# ── 5. db_write_taxonomy ────────────────────────────────────────────────


async def db_write_taxonomy(
    session_factory: async_sessionmaker,
    discovery_id: _uuid.UUID,
    taxonomy: TaxonomyTree,
    version: int,
) -> Tuple[_uuid.UUID, int]:
    """Persist TaxonomyTreeModel + SubdomainNodeModel rows.

    Steps:
    1. Upsert TaxonomyTreeModel with tree_json
    2. Delete existing subdomain nodes for this taxonomy (idempotent)
    3. Flatten taxonomy tree into flat list
    4. Bulk insert SubdomainNodeModel rows
    5. Update TopicDiscoveryModel.taxonomy_version

    Returns (taxonomy_db_id, version_written).
    """
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
            capture_recapture_est=(
                taxonomy.capture_recapture_est
                if isinstance(taxonomy.capture_recapture_est, dict)
                else {}
            ),
            status=TDStatus.approved,
        )
        taxonomy_id = tax_model.id

        # 2. Delete old nodes (idempotent)
        await node_repo.delete_by_taxonomy(taxonomy_id)

        # 3. Flatten tree
        flat_nodes = _flatten_taxonomy_for_db(taxonomy.root_nodes, taxonomy_id)

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
        "db_write_taxonomy: v%d stored for discovery %s (%d nodes)",
        version, discovery_id, len(flat_nodes),
    )
    return taxonomy_id, version


# ── 6. db_read_taxonomy ─────────────────────────────────────────────────


async def db_read_taxonomy(
    session_factory: async_sessionmaker,
    effective_slug: str,
    version: Optional[int] = None,
) -> Optional[TaxonomyTree]:
    """Read a TaxonomyTree from the DB.

    If version is None, returns the latest (highest version).
    Returns None if no taxonomy exists.
    """
    from core.db.repositories.topic_discovery_repo import (
        TaxonomyTreeRepository,
        TopicDiscoveryRepository,
    )

    async with session_factory() as session:
        disc_repo = TopicDiscoveryRepository(session)
        discovery = await disc_repo.get_by_effective_slug(effective_slug)
        if discovery is None:
            return None

        tax_repo = TaxonomyTreeRepository(session)
        tax_model = await tax_repo.get_by_discovery(discovery.id, version=version)

    if tax_model is None or tax_model.tree_json is None:
        return None

    return TaxonomyTree.model_validate(tax_model.tree_json)


# ── 7. db_write_scoring ─────────────────────────────────────────────────


async def db_write_scoring(
    session_factory: async_sessionmaker,
    discovery_id: _uuid.UUID,
    scored_subdomains: ScoredSubdomainList,
) -> int:
    """Store scored subdomains in topic_discoveries.scoring_json JSONB.

    Also updates per-node priority_score, priority_factors, persona_affinity_json
    on subdomain_nodes for the latest taxonomy version.

    Returns the scoring version.
    """
    from core.db.repositories.topic_discovery_repo import (
        SubdomainNodeRepository,
        TaxonomyTreeRepository,
        TopicDiscoveryRepository,
    )

    scoring_json = scored_subdomains.model_dump(mode="json")
    scoring_version = scored_subdomains.version

    async with session_factory() as session:
        disc_repo = TopicDiscoveryRepository(session)
        discovery = await disc_repo.get_by_id(discovery_id)
        if discovery is None:
            raise ValueError(f"db_write_scoring: discovery {discovery_id} not found")

        # Store bulk scoring JSON on discovery row
        discovery.scoring_json = scoring_json
        await session.flush()

        # Update per-node scoring columns on subdomain_nodes
        tax_repo = TaxonomyTreeRepository(session)
        tax_model = await tax_repo.get_by_discovery(discovery_id)
        if tax_model is not None:
            node_repo = SubdomainNodeRepository(session)
            nodes = await node_repo.get_by_taxonomy(tax_model.id)

            # Build a lookup from subdomain_id -> score entry
            score_lookup: Dict[str, Any] = {}
            for score in scored_subdomains.scores:
                score_lookup[score.subdomain_id] = score

            for node in nodes:
                node_id_str = str(node.id)
                if node_id_str in score_lookup:
                    s = score_lookup[node_id_str]
                    node.priority_score = s.composite_score
                    node.priority_factors = (
                        s.signal_scores if isinstance(s.signal_scores, dict) else {}
                    )
                    node.persona_affinity_json = (
                        s.persona_affinity if isinstance(s.persona_affinity, dict) else {}
                    )
            await session.flush()

        # Update version counter
        await disc_repo.update_versions(
            discovery_id, scoring_version=scoring_version,
        )
        await session.commit()

    logger.info(
        "db_write_scoring: v%d stored for discovery %s (%d scores)",
        scoring_version, discovery_id, len(scored_subdomains.scores),
    )
    return scoring_version


# ── 8. db_read_scoring ──────────────────────────────────────────────────


async def db_read_scoring(
    session_factory: async_sessionmaker,
    effective_slug: str,
) -> Optional[ScoredSubdomainList]:
    """Read scoring_json from topic_discoveries and deserialize."""
    from core.db.repositories.topic_discovery_repo import TopicDiscoveryRepository

    async with session_factory() as session:
        repo = TopicDiscoveryRepository(session)
        discovery = await repo.get_by_effective_slug(effective_slug)

    if discovery is None or discovery.scoring_json is None:
        return None

    return ScoredSubdomainList.model_validate(discovery.scoring_json)


# ── 9. db_write_persona_affinity ────────────────────────────────────────


async def db_write_persona_affinity(
    session_factory: async_sessionmaker,
    discovery_id: _uuid.UUID,
    affinity_index: PersonaAffinityIndex,
    version: int,
) -> int:
    """Persist PersonaAffinityIndex to both JSONB and td_persona_affinity rows.

    Steps:
    1. Store full index as persona_affinity_index_json on discovery row
    2. Delete existing affinity rows for this discovery + version
    3. Flatten persona_entries into PersonaAffinityModel rows
    4. Bulk insert
    5. Update persona_affinity_version

    Returns version.
    """
    from core.db.models.topic_discovery import PersonaAffinityModel
    from core.db.repositories.topic_discovery_repo import (
        PersonaAffinityRepository,
        TopicDiscoveryRepository,
    )

    index_json = affinity_index.model_dump(mode="json")

    async with session_factory() as session:
        disc_repo = TopicDiscoveryRepository(session)
        discovery = await disc_repo.get_by_id(discovery_id)
        if discovery is None:
            raise ValueError(
                f"db_write_persona_affinity: discovery {discovery_id} not found"
            )

        # 1. Store bulk JSONB
        discovery.persona_affinity_index_json = index_json
        await session.flush()

        # 2. Delete existing rows (idempotent)
        pa_repo = PersonaAffinityRepository(session)
        await pa_repo.delete_by_discovery(discovery_id, version=version)

        # 3+4. Flatten and bulk insert
        models = []
        persona_entries = affinity_index.persona_entries or {}
        persona_meta = getattr(affinity_index, "persona_metadata", {}) or {}
        for persona_id, entries in persona_entries.items():
            meta = persona_meta.get(persona_id, {})
            p_name = meta.get("persona_name") or None
            p_role = meta.get("career_role") or None
            for entry in entries:
                # Resolve subdomain UUID for FK linkage
                subdomain_node_uuid = None
                raw_sub_id = getattr(entry, "subdomain_id", None)
                if raw_sub_id:
                    try:
                        subdomain_node_uuid = _uuid.UUID(raw_sub_id)
                    except (ValueError, AttributeError):
                        pass

                pain_points_val = getattr(entry, "pain_points", None)

                models.append(PersonaAffinityModel(
                    discovery_id=discovery_id,
                    subdomain_node_id=subdomain_node_uuid,
                    persona_id=persona_id,
                    persona_name=p_name,
                    career_role=p_role,
                    subdomain_id_str=raw_sub_id,
                    subdomain_name=getattr(entry, "subdomain_name", None),
                    affinity_score=getattr(entry, "affinity_score", 0.0),
                    provenance=getattr(entry, "provenance", None),
                    pain_points=(
                        pain_points_val if isinstance(pain_points_val, list) else None
                    ),
                    version=version,
                ))

        if models:
            await pa_repo.bulk_create(models)

        # 5. Update version
        await disc_repo.update_versions(
            discovery_id, persona_affinity_version=version,
        )
        await session.commit()

    logger.info(
        "db_write_persona_affinity: %d entries stored for discovery %s (v%d)",
        len(models), discovery_id, version,
    )
    return version


# ── 10. db_read_persona_affinity ────────────────────────────────────────


async def db_read_persona_affinity(
    session_factory: async_sessionmaker,
    effective_slug: str,
) -> Optional[PersonaAffinityIndex]:
    """Read persona_affinity_index_json from topic_discoveries and deserialize."""
    from core.db.repositories.topic_discovery_repo import TopicDiscoveryRepository

    async with session_factory() as session:
        repo = TopicDiscoveryRepository(session)
        discovery = await repo.get_by_effective_slug(effective_slug)

    if discovery is None or discovery.persona_affinity_index_json is None:
        return None

    return PersonaAffinityIndex.model_validate(discovery.persona_affinity_index_json)


# ── 11. db_write_matrix ─────────────────────────────────────────────────


async def db_write_matrix(
    session_factory: async_sessionmaker,
    discovery_id: _uuid.UUID,
    matrix: TopicAssignmentMatrix,
    version: int,
) -> int:
    """Persist TopicAssignmentModel rows for the dimensionality matrix.

    Steps:
    1. Auto-increment version if version=0
    2. Delete existing assignments for this discovery + version (idempotent)
    3. Map Pydantic enums -> DB enums and bulk insert
    4. Update topic_discoveries.matrix_version

    Returns the version written.
    """
    from core.db.enums import (
        AudienceSegmentType as DBAudienceSegmentType,
        BuyerStage as DBBuyerStage,
        IntentType as DBIntentType,
        RelevanceCell as DBRelevanceCell,
        TopicAssignmentStatus as DBTopicAssignmentStatus,
    )
    from core.db.models.topic_discovery import TopicAssignmentModel
    from core.db.repositories.topic_discovery_repo import (
        TopicAssignmentRepository,
        TopicDiscoveryRepository,
    )

    async with session_factory() as session:
        disc_repo = TopicDiscoveryRepository(session)

        # 1. Auto-increment if version=0
        if version == 0:
            discovery = await disc_repo.get_by_id(discovery_id)
            if discovery is None:
                raise ValueError(
                    f"db_write_matrix: discovery {discovery_id} not found"
                )
            version = (discovery.matrix_version or 0) + 1

        assign_repo = TopicAssignmentRepository(session)

        # 2. Delete old assignments (idempotent)
        await assign_repo.delete_by_discovery(
            discovery_id, matrix_version=version,
        )

        # 3. Map and bulk insert
        models = []
        for a in matrix.assignments:
            try:
                a_uuid = _uuid.UUID(a.id)
            except (ValueError, AttributeError):
                a_uuid = _uuid.uuid4()

            # Resolve subdomain_node_id FK from Pydantic subdomain_id
            subdomain_node_uuid = None
            raw_subdomain_id = getattr(a, "subdomain_id", None)
            if raw_subdomain_id:
                try:
                    subdomain_node_uuid = _uuid.UUID(raw_subdomain_id)
                except (ValueError, AttributeError):
                    pass

            models.append(TopicAssignmentModel(
                id=a_uuid,
                discovery_id=discovery_id,
                matrix_version=version,
                subdomain_node_id=subdomain_node_uuid,
                topic_text=a.topic_text,
                buyer_stage=DBBuyerStage(a.buyer_stage.value),
                intent_type=DBIntentType(a.intent_type.value),
                audience_segment=a.audience_segment,
                audience_segment_type=DBAudienceSegmentType(
                    a.audience_segment_type.value
                ),
                relevance=DBRelevanceCell(a.relevance.value),
                priority_score=a.priority_score,
                priority_factors=(
                    a.priority_factors
                    if isinstance(a.priority_factors, dict) else {}
                ),
                status=DBTopicAssignmentStatus(a.status.value),
                is_manually_added=getattr(a, "is_manually_added", False),
                metadata_json=(
                    getattr(a, "metadata", None)
                    if isinstance(getattr(a, "metadata", None), dict) else {}
                ),
                persona_id=getattr(a, "persona_id", None),
                persona_name=getattr(a, "persona_name", None),
                subdomain_id_text=raw_subdomain_id,
                subdomain_name=getattr(a, "subdomain_name", None),
            ))

        if models:
            await assign_repo.bulk_create(models)

        # 4. Update discovery version
        await disc_repo.update_versions(
            discovery_id, matrix_version=version,
        )
        await session.commit()

    logger.info(
        "db_write_matrix: v%d stored for discovery %s (%d assignments)",
        version, discovery_id, len(models),
    )
    return version


# ── 12. db_read_latest_matrix ───────────────────────────────────────────


async def db_read_latest_matrix(
    session_factory: async_sessionmaker,
    effective_slug: str,
) -> Optional[TopicAssignmentMatrix]:
    """Read the latest TopicAssignmentMatrix from the DB.

    Queries topic_discoveries for discovery_id and matrix_version,
    then fetches all assignments at that version and maps DB enums
    back to Pydantic enums.
    """
    from core.models.topic_discovery import (
        AudienceSegmentType as PydanticAudienceSegmentType,
        BuyerStage as PydanticBuyerStage,
        IntentType as PydanticIntentType,
        RelevanceCell as PydanticRelevanceCell,
        TopicAssignment,
        TopicAssignmentStatus as PydanticTopicAssignmentStatus,
    )
    from core.db.repositories.topic_discovery_repo import (
        TopicAssignmentRepository,
        TopicDiscoveryRepository,
    )

    async with session_factory() as session:
        disc_repo = TopicDiscoveryRepository(session)
        discovery = await disc_repo.get_by_effective_slug(effective_slug)
        if discovery is None:
            return None

        matrix_version = discovery.matrix_version
        if matrix_version == 0:
            return None

        assign_repo = TopicAssignmentRepository(session)
        rows = await assign_repo.get_by_discovery(
            discovery.id, matrix_version=matrix_version,
        )

    if not rows:
        return None

    # Map DB rows -> Pydantic TopicAssignment models
    assignments: List[TopicAssignment] = []
    buyer_stage_dist: Dict[str, int] = {}
    intent_dist: Dict[str, int] = {}
    audience_dist: Dict[str, int] = {}
    total_relevant = 0
    total_irrelevant = 0

    for row in rows:
        # DB enum -> Pydantic enum via .value
        bs = PydanticBuyerStage(row.buyer_stage.value)
        it = PydanticIntentType(row.intent_type.value)
        ast = PydanticAudienceSegmentType(row.audience_segment_type.value)
        rel = PydanticRelevanceCell(row.relevance.value)
        status = PydanticTopicAssignmentStatus(row.status.value)

        assignments.append(TopicAssignment(
            id=str(row.id),
            subdomain_id=row.subdomain_id_text or "",
            subdomain_name=row.subdomain_name or "",
            topic_text=row.topic_text,
            buyer_stage=bs,
            intent_type=it,
            audience_segment=row.audience_segment or "",
            audience_segment_type=ast,
            relevance=rel,
            priority_score=row.priority_score or 0.0,
            priority_factors=row.priority_factors or {},
            status=status,
            is_manually_added=row.is_manually_added,
            metadata=row.metadata_json or {},
            persona_id=row.persona_id or "",
            persona_name=row.persona_name or "",
        ))

        # Aggregate statistics
        bs_key = bs.value
        buyer_stage_dist[bs_key] = buyer_stage_dist.get(bs_key, 0) + 1
        it_key = it.value
        intent_dist[it_key] = intent_dist.get(it_key, 0) + 1
        aud_key = row.audience_segment or "unknown"
        audience_dist[aud_key] = audience_dist.get(aud_key, 0) + 1
        if rel == PydanticRelevanceCell.relevant:
            total_relevant += 1
        elif rel == PydanticRelevanceCell.irrelevant:
            total_irrelevant += 1

    matrix = TopicAssignmentMatrix(
        version=matrix_version,
        assignments=assignments,
        total_assignments=len(assignments),
        total_relevant_cells=total_relevant,
        total_irrelevant_cells=total_irrelevant,
        buyer_stage_distribution=buyer_stage_dist,
        intent_distribution=intent_dist,
        audience_distribution=audience_dist,
    )

    logger.debug(
        "db_read_latest_matrix: slug=%s v%d (%d assignments)",
        effective_slug, matrix_version, len(assignments),
    )
    return matrix


# ── 13. db_get_discovery_id ─────────────────────────────────────────────


async def db_get_discovery_id(
    session_factory: async_sessionmaker,
    effective_slug: str,
) -> Optional[_uuid.UUID]:
    """Return the discovery UUID for an effective_slug, or None."""
    from core.db.repositories.topic_discovery_repo import TopicDiscoveryRepository

    async with session_factory() as session:
        repo = TopicDiscoveryRepository(session)
        discovery = await repo.get_by_effective_slug(effective_slug)

    if discovery is None:
        return None
    return discovery.id
