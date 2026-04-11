"""DB persistence hooks for each gap analysis pipeline step.

After each step writes its JSON artifact to disk, the pipeline optionally
calls the corresponding ``persist_sN()`` function here to write the same
data into Postgres tables so that ``DbGapDataService`` (and friends)
serve real data to the dashboard API.

Design principles:
- **Filesystem-first, DB-additive**: JSON is always written first; DB is extra.
- **Graceful degradation**: Every function catches all exceptions — DB errors
  NEVER crash the pipeline.
- **Per-step transaction isolation**: Each function opens its own session,
  commits, and closes.  A failure in s4 does not affect s5.
- **Idempotent re-persist**: Deletes stale rows for the same ``run_id``
  before inserting, so retries are safe.
"""
from __future__ import annotations

import hashlib
import logging
import math
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

# ── Helpers ─────────────────────────────────────────────────────────────


def _safe_float(val: Any) -> float:
    """Convert to float, returning 0.0 for NaN/Inf/None."""
    if val is None:
        return 0.0
    try:
        f = float(val)
        return 0.0 if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return 0.0


def _classify(interpretation: str) -> Any:
    """Map interpretation string to GapClassification enum."""
    from core.db.enums import GapClassification

    try:
        return GapClassification(interpretation)
    except ValueError:
        legacy_map = {
            "large_gap": GapClassification.significant_gap,
            "moderate_gap": GapClassification.gap_to_close,
            "small_gap": GapClassification.roughly_equal,
            "no_gap": GapClassification.company_wins,
            "already_cited": GapClassification.company_wins,
        }
        return legacy_map.get(interpretation, GapClassification.no_data)


def _map_engine(engine_str: str) -> Any:
    """Map engine string to SearchEngine enum, or None."""
    from core.db.enums import SearchEngine

    try:
        return SearchEngine(engine_str.lower())
    except ValueError:
        return None


def _hash_text(text: str) -> str:
    """SHA-256 hex digest of a text string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ── Guard ───────────────────────────────────────────────────────────────


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


# ── persist_s1: Semantic Units ──────────────────────────────────────────


async def persist_s1(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    slug: str,
    semantic_units: list,
) -> None:
    """Persist s1 outputs — no-op for embeddings (VectorStoreClient writes during S1).

    Embedding storage is now handled by VectorStoreClient.upsert_embeddings()
    called directly from s1_embed_assets. This function is retained as a hook
    for any future non-embedding persistence needs.
    """
    logger.info("persist_s1: embeddings handled by VectorStoreClient for %s (%d units)", slug, len(semantic_units))


# ── persist_s2: Generated Queries ───────────────────────────────────────


async def persist_s2(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    slug: str,
    queries: list,
) -> None:
    """Persist s2 outputs → run_queries table."""
    if not _should_persist(session_factory, run_id, company_id):
        return
    assert session_factory is not None and run_id is not None
    try:
        from core.db.models.gap_analysis import RunQueryModel
        from core.db.repositories.gap_analysis_repo import GapAnalysisRepository

        async with session_factory() as session:
            # Idempotent
            await session.execute(
                delete(RunQueryModel).where(RunQueryModel.run_id == run_id)
            )

            repo = GapAnalysisRepository(session)
            items: list[dict[str, object]] = []
            for q in queries:
                source_ids = getattr(q, "source_topic_ids", None) or []
                items.append({
                    "id": _uuid.uuid4(),
                    "run_id": run_id,
                    "query_id": q.query_id,
                    "cluster_id": getattr(q, "cluster_id", None),
                    "cluster_name": q.cluster_name,
                    "query_text": q.query_text,
                    "buyer_stage": getattr(q, "buyer_stage", None),
                    "persona_tag": getattr(q, "persona_tag", None),
                    "source_topic_ids": source_ids if source_ids else None,
                })
            if items:
                await repo.bulk_insert_run_queries(items)
            await session.commit()
        logger.info("persist_s2: %d queries stored for %s", len(items), slug)
    except Exception:
        logger.warning("persist_s2 failed for %s, continuing without DB", slug, exc_info=True)


# ── persist_s3: Platform Results + Citations ────────────────────────────


async def persist_s3(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    slug: str,
    platform_results: list,
    queries: list,
) -> None:
    """Persist s3 outputs → run_citations + platform_result_cache.

    Handles composite FK constraint: ensures RunQueryModel rows exist
    before inserting RunCitationModel rows (backfills from queries if
    step 2 was skipped).
    """
    if not _should_persist(session_factory, run_id, company_id):
        return
    assert session_factory is not None and run_id is not None
    try:
        from core.db.models.gap_analysis import RunCitationModel, RunQueryModel
        from core.db.repositories.gap_analysis_repo import GapAnalysisRepository

        async with session_factory() as session:
            # Idempotent: clear citations for this run
            await session.execute(
                delete(RunCitationModel).where(RunCitationModel.run_id == run_id)
            )

            # Ensure run_queries exist (may have been skipped in s2)
            existing_count = (await session.execute(
                select(func.count()).select_from(RunQueryModel)
                .where(RunQueryModel.run_id == run_id)
            )).scalar_one()

            repo = GapAnalysisRepository(session)
            if existing_count == 0 and queries:
                query_rows: list[dict[str, object]] = []
                for q in queries:
                    query_rows.append({
                        "id": _uuid.uuid4(),
                        "run_id": run_id,
                        "query_id": q.query_id,
                        "cluster_id": getattr(q, "cluster_id", None),
                        "cluster_name": q.cluster_name,
                        "query_text": q.query_text,
                        "buyer_stage": getattr(q, "buyer_stage", None),
                        "persona_tag": getattr(q, "persona_tag", None),
                    })
                await repo.bulk_insert_run_queries(query_rows)

            # Build citation rows from platform results
            citation_rows: list[dict[str, object]] = []
            for pr in platform_results:
                engine = _map_engine(pr.engine)
                if engine is None:
                    continue
                for i, cit in enumerate(pr.citations):
                    citation_rows.append({
                        "id": _uuid.uuid4(),
                        "run_id": run_id,
                        "query_id": pr.query_id,
                        "cluster_name": getattr(pr, "cluster_name", None),
                        "engine": engine,
                        "url": str(cit.url),
                        "domain": getattr(cit, "source", None) or getattr(cit, "domain", None),
                        "title": getattr(cit, "title", None),
                        "snippet": getattr(cit, "snippet", None),
                        "citation_rank": getattr(cit, "rank", i + 1),
                        "is_company_citation": getattr(cit, "is_company_citation", False),
                    })
            if citation_rows:
                await repo.bulk_insert_run_citations(citation_rows)

            await session.commit()
        logger.info(
            "persist_s3: %d citations stored for %s", len(citation_rows), slug
        )
    except Exception:
        logger.warning("persist_s3 failed for %s, continuing without DB", slug, exc_info=True)


# ── persist_s4: Enriched Citations → URL cache + structural signals ─────


async def persist_s4(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    slug: str,
    enriched: list,
) -> None:
    """Persist s4 outputs → url_enrichment_cache + url_structural_signals.

    Uses ON CONFLICT upserts for the cache tables (shared across runs).
    """
    if not _should_persist(session_factory, run_id, company_id):
        return
    assert session_factory is not None
    try:
        from core.db.repositories.cache_repo import CacheRepository

        async with session_factory() as session:
            repo = CacheRepository(session)
            enrichment_rows: list[dict[str, object]] = []
            signal_rows: list[dict[str, object]] = []

            for cit in enriched:
                url_str = str(cit.url)
                url_hash = _hash_text(url_str)
                # Deterministic UUID from url_hash so reruns produce the same id.
                # Prevents FK mismatch: upsert on url_hash keeps original id,
                # and signal rows always reference a valid enrichment_id.
                enrichment_id = _uuid.uuid5(_uuid.NAMESPACE_URL, url_hash)

                enrichment_rows.append({
                    "id": enrichment_id,
                    "url_hash": url_hash,
                    "url": url_str,
                    "final_url": url_str,
                    "domain": getattr(cit, "domain", None),
                    "title": getattr(cit, "title", None),
                    "authority_type": (
                        cit.structural_signals.authority_type
                        if cit.structural_signals else None
                    ),
                    "content_type": (
                        cit.structural_signals.content_type
                        if cit.structural_signals else None
                    ),
                    "published_at": getattr(cit, "published_at", None),
                    "modified_at": getattr(cit, "modified_at", None),
                    "paragraph_count": len(cit.paragraphs) if cit.paragraphs else 0,
                    "http_status": 200,
                    "scraped_at": datetime.now(tz=timezone.utc),
                })

                if cit.structural_signals:
                    ss = cit.structural_signals
                    signal_rows.append({
                        "url_enrichment_id": enrichment_id,
                        "word_count": ss.word_count,
                        "paragraph_count": ss.paragraph_count,
                        "header_count": ss.header_count,
                        "list_item_count": ss.list_item_count,
                        "stat_count": ss.stat_count,
                        "citation_count": ss.citation_count,
                        "has_headers": ss.has_headers,
                        "has_lists": ss.has_lists,
                        "has_numbers": ss.has_numbers,
                        "main_content_word_count": ss.main_content_word_count,
                        "sentence_count": ss.sentence_count,
                        "avg_paragraph_length": _safe_float(ss.avg_paragraph_length),
                        "median_paragraph_length": _safe_float(ss.median_paragraph_length),
                        "max_paragraph_word_count": ss.max_paragraph_word_count,
                        "avg_sentence_length": _safe_float(ss.avg_sentence_length),
                        "avg_sentence_count_per_paragraph": _safe_float(ss.avg_sentence_count_per_paragraph),
                        "reading_level": _safe_float(ss.reading_level),
                        "self_contained_ratio": _safe_float(ss.self_contained_ratio),
                        "h1_count": ss.h1_count,
                        "h2_count": ss.h2_count,
                        "h3_count": ss.h3_count,
                        "h4_count": ss.h4_count,
                        "ordered_list_count": ss.ordered_list_count,
                        "unordered_list_count": ss.unordered_list_count,
                        "table_count": ss.table_count,
                        "definition_list_count": ss.definition_list_count,
                        "blockquote_count": ss.blockquote_count,
                        "code_block_count": ss.code_block_count,
                        "list_block_count": ss.list_block_count,
                        "bullets_per_list_block": _safe_float(ss.bullets_per_list_block),
                        "min_bullets_per_list": ss.min_bullets_per_list,
                        "has_faq_section": ss.has_faq_section,
                        "has_definition_opening": ss.has_definition_opening,
                        "has_key_takeaways": ss.has_key_takeaways,
                        "has_toc": ss.has_toc,
                        "has_comparison_table": ss.has_comparison_table,
                        "has_step_by_step": ss.has_step_by_step,
                        "has_research_refs": ss.has_research_refs,
                        "has_expert_quotes": ss.has_expert_quotes,
                        "data_point_count": ss.data_point_count,
                        "citation_density": _safe_float(ss.citation_density),
                        "named_entity_density": _safe_float(ss.named_entity_density),
                    })

            if enrichment_rows:
                await repo.bulk_upsert_url_enrichments(enrichment_rows)
            if signal_rows:
                await repo.bulk_insert_structural_signals(signal_rows)

            await session.commit()
        logger.info(
            "persist_s4: %d enrichments, %d signals stored for %s",
            len(enrichment_rows), len(signal_rows), slug,
        )
    except Exception:
        logger.warning("persist_s4 failed for %s, continuing without DB", slug, exc_info=True)


# ── persist_s5: Query + Paragraph Embeddings ────────────────────────────


async def persist_s5(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    slug: str,
    queries: list,
    enriched: list,
) -> None:
    """Persist s5 outputs → query_embeddings table.

    Citation paragraph embeddings are handled by VectorStoreClient during S5.
    Query embeddings still need persist_s5 because QueryEmbeddingModel requires
    run_id (FK to pipeline_runs), which is only available in the pipeline context.
    """
    if not _should_persist(session_factory, run_id, company_id):
        return
    assert session_factory is not None and run_id is not None
    try:
        from core.db.models.embeddings import QueryEmbeddingModel
        from core.db.repositories.embedding_repo import EmbeddingRepository

        async with session_factory() as session:
            # Idempotent: clear previous rows for this run
            await session.execute(
                delete(QueryEmbeddingModel).where(QueryEmbeddingModel.run_id == run_id)
            )

            repo = EmbeddingRepository(session)
            q_items: list[dict[str, object]] = []
            for q in queries:
                if not q.embedding or len(q.embedding) != 1536:
                    continue
                q_items.append({
                    "id": _uuid.uuid4(),
                    "run_id": run_id,
                    "query_id": q.query_id,
                    "query_text": q.query_text,
                    "embedding": q.embedding,
                })
            if q_items:
                await repo.bulk_store_embeddings(QueryEmbeddingModel, q_items)

            await session.commit()
        logger.info("persist_s5: %d query embeddings stored for %s", len(q_items), slug)
    except Exception:
        logger.warning("persist_s5 failed for %s, continuing without DB", slug, exc_info=True)


# ── persist_s6: Analysis Results ────────────────────────────────────────


async def persist_s6(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    slug: str,
    analysis: Any,
) -> None:
    """Persist s6 outputs → query_gaps, exemplars, cluster_specs, spa, centroids."""
    if not _should_persist(session_factory, run_id, company_id):
        return
    assert session_factory is not None and run_id is not None
    try:
        from core.db.models.gap_analysis import (
            CentroidResultModel,
            ClusterProximityStatsModel,
            ClusterSpecModel,
            QueryExemplarModel,
            QueryGapModel,
            SpaResultModel,
        )
        from core.db.repositories.gap_analysis_repo import GapAnalysisRepository

        async with session_factory() as session:
            # Idempotent: clear all s6-owned tables for this run.
            # QueryExemplarModel has no run_id column — it's linked via
            # query_gap_id FK with ondelete="CASCADE", so deleting
            # QueryGapModel rows automatically cascades to exemplars.
            for model_cls in (
                QueryGapModel,
                ClusterSpecModel,
                SpaResultModel,
                CentroidResultModel,
                ClusterProximityStatsModel,
            ):
                await session.execute(
                    delete(model_cls).where(model_cls.run_id == run_id)  # type: ignore[attr-defined]
                )

            repo = GapAnalysisRepository(session)

            # ── Query Gaps + Exemplars ─────────────────────────────
            gap_rows: list[dict[str, object]] = []
            exemplar_rows: list[dict[str, object]] = []

            for gap in analysis.gaps:
                gap_id = _uuid.uuid4()
                # Build content_brief JSONB from exemplars
                exemplars = getattr(gap, "top_cited_exemplars", [])
                content_brief: Optional[Dict[str, Any]] = None
                if gap.content_brief:
                    content_brief = gap.content_brief.model_dump(mode="json") if hasattr(gap.content_brief, "model_dump") else gap.content_brief

                source_ids = getattr(gap, "source_topic_ids", None) or []
                # Serialize best_company_structural_signals to dict if present
                _bcs_raw = getattr(gap, "best_company_structural_signals", None)
                bcs_dict: Optional[Dict[str, Any]] = None
                if _bcs_raw is not None:
                    if hasattr(_bcs_raw, "model_dump"):
                        bcs_dict = _bcs_raw.model_dump(mode="json")
                    elif isinstance(_bcs_raw, dict):
                        bcs_dict = _bcs_raw

                gap_rows.append({
                    "id": gap_id,
                    "run_id": run_id,
                    "query_id": gap.query_id,
                    "cluster_id": getattr(gap, "cluster_id", None),
                    "cluster_name": gap.cluster_name or "",
                    "query_text": gap.query_text,
                    "best_company_similarity": _safe_float(gap.best_company_similarity),
                    "best_company_unit_id": getattr(gap, "best_company_unit", None),
                    "best_company_unit_text": getattr(gap, "best_company_unit_text", None),
                    "best_company_url": getattr(gap, "best_company_url", None),
                    "best_company_structural_signals": bcs_dict,
                    "company_cited": getattr(gap, "company_cited", False),
                    "avg_citation_similarity": _safe_float(gap.avg_citation_similarity),
                    "gap": _safe_float(gap.gap),
                    "classification": _classify(gap.interpretation or "no_data"),
                    "content_brief": content_brief,
                    "source_topic_ids": source_ids if source_ids else None,
                })

                for rank, ex in enumerate(exemplars[:5], start=1):
                    # Deterministic url_enrichment_id — matches persist_s4
                    # UUID derivation.  S4 always runs before S6 in the
                    # pipeline, so the url_enrichment_cache row exists.
                    # If S4 was skipped, persist_s6's try/except catches
                    # the IntegrityError and the pipeline continues.
                    ex_url_str = str(ex.url)
                    ex_url_hash = _hash_text(ex_url_str)
                    ex_enrichment_id = _uuid.uuid5(
                        _uuid.NAMESPACE_URL, ex_url_hash,
                    )
                    exemplar_rows.append({
                        "id": _uuid.uuid4(),
                        "query_gap_id": gap_id,
                        "url_enrichment_id": ex_enrichment_id,
                        "url": ex_url_str,
                        "domain": getattr(ex, "domain", None),
                        "similarity": _safe_float(ex.similarity),
                        "snippet": getattr(ex, "snippet", None),
                        "authority_type": getattr(ex, "authority_type", None),
                        "rank": rank,
                    })

            if gap_rows:
                await repo.bulk_insert_query_gaps(gap_rows)
            if exemplar_rows:
                await repo.bulk_insert_query_exemplars(exemplar_rows)

            # ── Cluster Specs ──────────────────────────────────────
            spec_rows: list[dict[str, object]] = []
            for spec in analysis.cluster_specs:
                wc_range = getattr(spec, "word_count_range", [0, 0])
                wc_min = int(wc_range[0]) if isinstance(wc_range, (list, tuple)) and len(wc_range) >= 1 else 0
                wc_max = int(wc_range[1]) if isinstance(wc_range, (list, tuple)) and len(wc_range) >= 2 else 0
                structural_rates = getattr(spec, "structural_rates", {}) or {}

                spec_rows.append({
                    "id": _uuid.uuid4(),
                    "run_id": run_id,
                    "cluster_id": getattr(spec, "cluster_id", None),
                    "cluster_name": spec.cluster_name,
                    "query_count": int(_safe_float(getattr(spec, "query_count", 0))),
                    "total_citations_analyzed": int(_safe_float(getattr(spec, "total_citations_analyzed", 0))),
                    "word_count_min": wc_min,
                    "word_count_max": wc_max,
                    "avg_word_count": _safe_float(getattr(spec, "avg_word_count", (wc_min + wc_max) / 2 if wc_min or wc_max else 0)),
                    "avg_paragraph_word_count": _safe_float(getattr(spec, "avg_paragraph_word_count", 0)),
                    "avg_sentence_count_per_paragraph": _safe_float(getattr(spec, "avg_sentence_count_per_paragraph", 0)),
                    "min_similarity_threshold": _safe_float(getattr(spec, "min_similarity_threshold", None)),
                    "min_bullets_per_list": int(_safe_float(getattr(spec, "min_bullets_per_list", 0))),
                    # Rate columns — map from Pydantic fields (NOT structural_rates dict)
                    "faq_rate": _safe_float(getattr(spec, "faq_rate", 0)),
                    "table_rate": _safe_float(getattr(spec, "table_rate", 0)),
                    "definition_rate": _safe_float(getattr(spec, "definition_rate", 0)),
                    "code_block_rate": _safe_float(getattr(spec, "code_block_rate", 0)),
                    "key_takeaways_rate": _safe_float(getattr(spec, "key_takeaways_rate", 0)),
                    "dominant_content_type": getattr(spec, "dominant_content_type", None),
                    "dominant_authority_type": getattr(spec, "dominant_authority_type", None),
                    "required_elements": getattr(spec, "required_elements", None) or None,
                    "structural_rates": structural_rates or None,
                    "exemplar_themes": getattr(spec, "exemplar_themes", None) or None,
                })
            if spec_rows:
                await repo.bulk_insert_cluster_specs(spec_rows)

            # ── SPA Results ────────────────────────────────────────
            spa_rows: list[dict[str, object]] = []
            for spa in analysis.spa_results:
                spa_rows.append({
                    "id": _uuid.uuid4(),
                    "run_id": run_id,
                    "cluster_id": getattr(spa, "cluster_id", None),
                    "cluster_name": spa.cluster_name or "all",
                    "t_stat": _safe_float(spa.t_stat),
                    "p_value": _safe_float(spa.p_value),
                    "effect": getattr(spa, "effect", ""),
                    "mean_citation_similarity": _safe_float(spa.mean_citation_similarity),
                    "mean_company_similarity": _safe_float(spa.mean_company_similarity),
                })
            if spa_rows:
                await repo.bulk_insert_spa_results(spa_rows)

            # ── Centroid Results ────────────────────────────────────
            centroid_rows: list[dict[str, object]] = []
            for c in analysis.centroids:
                centroid_rows.append({
                    "id": _uuid.uuid4(),
                    "run_id": run_id,
                    "cluster_name": c.cluster_name or "",
                    "distance": _safe_float(c.distance),
                })
            if centroid_rows:
                await repo.bulk_insert_centroid_results(centroid_rows)

            # ── Cluster Proximity Stats ────────────────────────────
            prox_rows: list[dict[str, object]] = []
            prox_stats_raw = getattr(analysis, "proximity_stats", None) or {}
            if isinstance(prox_stats_raw, dict):
                # Per-cluster rows
                per_cluster = prox_stats_raw.get("per_cluster", {})
                for cname, stats in per_cluster.items():
                    if isinstance(stats, dict):
                        prox_rows.append({
                            "id": _uuid.uuid4(),
                            "run_id": run_id,
                            "cluster_name": cname,
                            "cluster_id": None,
                            "citation_mean": _safe_float(stats.get("mean")),
                            "citation_std": _safe_float(stats.get("std")),
                            "citation_min": _safe_float(stats.get("min")),
                            "citation_max": _safe_float(stats.get("max")),
                            "citation_median": 0.0,
                            "company_mean": 0.0,
                            "company_median": 0.0,
                            "count": int(stats.get("count", 0)),
                        })
                # Global row with run-level aggregates
                prox_rows.append({
                    "id": _uuid.uuid4(),
                    "run_id": run_id,
                    "cluster_name": "__global__",
                    "cluster_id": None,
                    "citation_mean": _safe_float(prox_stats_raw.get("citation_similarity_mean")),
                    "citation_std": 0.0,
                    "citation_min": 0.0,
                    "citation_max": 0.0,
                    "citation_median": _safe_float(prox_stats_raw.get("citation_similarity_median")),
                    "company_mean": _safe_float(prox_stats_raw.get("company_similarity_mean")),
                    "company_median": _safe_float(prox_stats_raw.get("company_similarity_median")),
                    "count": 0,
                })
            if prox_rows:
                await repo.bulk_insert_cluster_proximity_stats(prox_rows)

            await session.commit()

        logger.info(
            "persist_s6: %d gaps, %d exemplars, %d specs, %d spa, %d centroids, %d prox for %s",
            len(gap_rows), len(exemplar_rows), len(spec_rows),
            len(spa_rows), len(centroid_rows), len(prox_rows), slug,
        )
    except Exception:
        logger.warning("persist_s6 failed for %s, continuing without DB", slug, exc_info=True)


# ── persist_s7: No-op (visualizations stay on filesystem) ──────────────


async def persist_s7(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    slug: str,
    visualization_paths: Any,
) -> None:
    """No DB writes for s7 — visualizations are HTML files on disk."""
    pass


# ── persist_s8: Update PipelineRunModel summary ────────────────────────


async def persist_s8(
    session_factory: Optional[async_sessionmaker],
    run_id: Optional[_uuid.UUID],
    company_id: Optional[_uuid.UUID],
    slug: str,
    report: Any,
    analysis: Any,
) -> None:
    """Update the PipelineRunModel with final summary metrics."""
    if not _should_persist(session_factory, run_id, company_id):
        return
    assert session_factory is not None and run_id is not None
    try:
        from core.db.enums import PipelineStatus
        from core.db.models.pipelines import PipelineRunModel

        async with session_factory() as session:
            run = await session.get(PipelineRunModel, run_id)
            if run is None:
                logger.warning("persist_s8: PipelineRunModel %s not found", run_id)
                return

            # Build summary from analysis decision_metrics
            decision_metrics = getattr(analysis, "decision_metrics", {}) or {}
            spa_results = getattr(analysis, "spa_results", []) or []
            summary: Dict[str, Any] = {
                "total_queries": int(_safe_float(decision_metrics.get("total_queries"))),
                "total_citations": int(_safe_float(decision_metrics.get("total_citations"))),
                "avg_gap": _safe_float(decision_metrics.get("avg_gap")),
            }
            if spa_results:
                first_spa = spa_results[0]
                summary["spa_score"] = _safe_float(
                    first_spa.t_stat if hasattr(first_spa, "t_stat") else getattr(first_spa, "t_stat", None)
                )

            run.summary = summary
            run.status = PipelineStatus.completed
            run.completed_at = datetime.now(tz=timezone.utc)
            run.stages_executed = [
                "s1_embed_assets", "s2_generate_queries", "s3_search_platforms",
                "s4_enrich_citations", "s5_embed_content", "s6_analyze",
                "s7_visualize", "s8_generate_report",
            ]

            await session.commit()
        logger.info("persist_s8: run summary updated for %s", slug)
    except Exception:
        logger.warning("persist_s8 failed for %s, continuing without DB", slug, exc_info=True)
