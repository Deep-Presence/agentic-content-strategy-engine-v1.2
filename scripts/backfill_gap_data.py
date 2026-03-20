#!/usr/bin/env python3
"""Backfill gap analysis artifacts from filesystem JSON into Postgres tables.

Reads existing JSON artifacts from artifacts/gap_analysis/{slug}/ directories
and inserts them into the database tables used by DbGapDataService.

Tables populated:
- pipeline_runs       (one run per slug with status=completed)
- query_gaps          (from analysis.json gaps array)
- cluster_specs       (from analysis.json cluster_specs array)
- spa_results         (from analysis.json spa_results array)
- centroid_results    (from analysis.json centroids array — without embeddings)
- run_citations       (from enriched_citations.json — core fields only)

Usage:
    # Backfill all slugs
    python scripts/backfill_gap_data.py

    # Backfill specific slug
    python scripts/backfill_gap_data.py --slug ramp

    # Dry-run mode (parse and validate, don't write)
    python scripts/backfill_gap_data.py --dry-run

Requires DATABASE_URL environment variable.
Idempotent: uses effective_slug + pipeline_type uniqueness to skip existing runs.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import settings
from core.db.engine import get_engine, get_session_factory
from core.db.enums import (
    GapClassification,
    PipelineStatus,
    PipelineType,
    SearchEngine,
)
from core.db.models.gap_analysis import (
    CentroidResultModel,
    ClusterSpecModel,
    QueryGapModel,
    RunCitationModel,
    RunQueryModel,
    SpaResultModel,
)
from core.db.models.pipelines import PipelineRunModel

from core.shared_tools.structured_logging import configure_logging

configure_logging()
logger = logging.getLogger("backfill")

ARTIFACTS_ROOT = PROJECT_ROOT / "artifacts"
GAP_DIR = ARTIFACTS_ROOT / "gap_analysis"

# ── Helpers ──────────────────────────────────────────────────────────


def _safe_float(val: Any) -> float:
    """Convert to float, returning 0.0 for NaN/Inf/None."""
    if val is None:
        return 0.0
    try:
        f = float(val)
        return 0.0 if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return 0.0


def _load_json(path: Path) -> Optional[Any]:
    """Load a JSON file, returning None on failure."""
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load %s: %s", path, exc)
        return None


def _classify(interpretation: str) -> GapClassification:
    """Map interpretation string to GapClassification enum."""
    try:
        return GapClassification(interpretation)
    except ValueError:
        # Legacy values → new mapping
        legacy_map = {
            "large_gap": GapClassification.significant_gap,
            "moderate_gap": GapClassification.gap_to_close,
            "small_gap": GapClassification.roughly_equal,
            "no_gap": GapClassification.company_wins,
            "already_cited": GapClassification.company_wins,
        }
        return legacy_map.get(interpretation, GapClassification.no_data)


def _map_engine(engine_str: str) -> Optional[SearchEngine]:
    """Map engine string to SearchEngine enum."""
    try:
        return SearchEngine(engine_str.lower())
    except ValueError:
        return None


# ── Backfill Logic ───────────────────────────────────────────────────


async def _backfill_slug(
    session: AsyncSession,
    slug: str,
    *,
    dry_run: bool = False,
) -> Dict[str, int]:
    """Backfill a single slug's gap analysis data into the DB.

    Returns dict of {table: rows_inserted} counts.
    """
    slug_dir = GAP_DIR / slug
    analysis = _load_json(slug_dir / "analysis.json")
    if analysis is None:
        logger.warning("No analysis.json for slug '%s', skipping", slug)
        return {}

    counts: Dict[str, int] = {
        "pipeline_runs": 0,
        "run_queries": 0,
        "query_gaps": 0,
        "cluster_specs": 0,
        "spa_results": 0,
        "centroid_results": 0,
        "run_citations": 0,
    }

    # ── Check if run already exists ──────────────────────────────
    existing = await session.execute(
        select(PipelineRunModel).where(
            PipelineRunModel.effective_slug == slug,
            PipelineRunModel.pipeline_type == PipelineType.gap_analysis,
            PipelineRunModel.status == PipelineStatus.completed,
        ).limit(1)
    )
    if existing.scalars().first() is not None:
        logger.info("Run already exists for slug '%s', skipping", slug)
        return counts

    if dry_run:
        logger.info("[DRY-RUN] Would insert data for slug '%s'", slug)
        # Count what would be inserted
        gaps = analysis.get("gaps", [])
        counts["query_gaps"] = len(gaps)
        counts["cluster_specs"] = len(analysis.get("cluster_specs", []))
        counts["spa_results"] = len(analysis.get("spa_results", []))
        counts["centroid_results"] = len(analysis.get("centroids", []))

        queries = _load_json(slug_dir / "queries.json")
        counts["run_queries"] = len(queries) if isinstance(queries, list) else 0

        citations = _load_json(slug_dir / "enriched_citations.json")
        counts["run_citations"] = len(citations) if isinstance(citations, list) else 0
        counts["pipeline_runs"] = 1
        return counts

    # ── Create pipeline run ──────────────────────────────────────
    now = datetime.now(tz=timezone.utc)
    decision_metrics = analysis.get("decision_metrics", {})
    spa_results_raw = analysis.get("spa_results", [])

    # Build summary JSONB
    summary: Dict[str, Any] = {
        "total_queries": int(_safe_float(decision_metrics.get("total_queries"))),
        "total_citations": int(_safe_float(decision_metrics.get("total_citations"))),
        "avg_gap": _safe_float(decision_metrics.get("avg_gap")),
    }
    if spa_results_raw:
        first_spa = spa_results_raw[0]
        summary["spa_score"] = _safe_float(first_spa.get("t_stat"))

    run_id = uuid.uuid4()
    run = PipelineRunModel(
        id=run_id,
        company_id=uuid.uuid4(),  # placeholder — no company in filesystem mode
        effective_slug=slug,
        pipeline_type=PipelineType.gap_analysis,
        status=PipelineStatus.completed,
        summary=summary,
        stages_executed=[
            "s1_embed_assets", "s2_generate_queries", "s3_search_platforms",
            "s4_enrich_citations", "s5_embed_content", "s6_analyze",
            "s7_visualize", "s8_generate_report",
        ],
        started_at=now,
        completed_at=now,
    )
    session.add(run)
    counts["pipeline_runs"] = 1

    # ── Query Gaps ───────────────────────────────────────────────
    gaps_raw: List[Dict[str, Any]] = analysis.get("gaps", [])
    for gap in gaps_raw:
        query_id = gap.get("query_id", "")

        # Build content_brief from top_cited_exemplars
        exemplars = gap.get("top_cited_exemplars", [])
        content_brief: Optional[Dict[str, Any]] = None
        if exemplars:
            content_brief = {
                "exemplars": [
                    {
                        "url": e.get("url", ""),
                        "domain": e.get("domain", ""),
                        "snippet": e.get("snippet", ""),
                        "similarity": _safe_float(e.get("similarity")),
                    }
                    for e in exemplars[:5]
                ],
            }

        gap_model = QueryGapModel(
            id=uuid.uuid4(),
            run_id=run_id,
            query_id=query_id,
            cluster_id=gap.get("cluster_id", ""),
            cluster_name=gap.get("cluster_name", ""),
            query_text=gap.get("query_text", ""),
            best_company_similarity=_safe_float(gap.get("best_company_similarity")),
            avg_citation_similarity=_safe_float(gap.get("avg_citation_similarity")),
            gap=_safe_float(gap.get("gap")),
            classification=_classify(gap.get("interpretation", "no_data")),
            content_brief=content_brief,
        )
        session.add(gap_model)
        counts["query_gaps"] += 1

    # ── Cluster Specs ────────────────────────────────────────────
    specs_raw: List[Dict[str, Any]] = analysis.get("cluster_specs", [])
    for spec in specs_raw:
        wc_range = spec.get("word_count_range", [0, 0])
        wc_min = int(wc_range[0]) if isinstance(wc_range, (list, tuple)) and len(wc_range) >= 1 else 0
        wc_max = int(wc_range[1]) if isinstance(wc_range, (list, tuple)) and len(wc_range) >= 2 else 0

        structural_rates = spec.get("structural_rates", {})

        spec_model = ClusterSpecModel(
            id=uuid.uuid4(),
            run_id=run_id,
            cluster_id=spec.get("cluster_id", ""),
            cluster_name=spec.get("cluster_name", ""),
            query_count=int(_safe_float(spec.get("query_count"))),
            total_citations_analyzed=int(_safe_float(spec.get("total_citations_analyzed"))),
            word_count_min=wc_min,
            word_count_max=wc_max,
            avg_word_count=_safe_float(spec.get("avg_word_count", 0)),
            avg_paragraph_word_count=_safe_float(spec.get("avg_paragraph_word_count", 0)),
            avg_sentence_count_per_paragraph=_safe_float(spec.get("avg_sentence_count_per_paragraph", 0)),
            min_bullets_per_list=int(_safe_float(spec.get("min_bullets_per_list", 0))),
            min_similarity_threshold=_safe_float(spec.get("min_similarity_threshold")),
            structural_rates=structural_rates,
            faq_rate=_safe_float(spec.get("faq_rate", 0)),
            table_rate=_safe_float(spec.get("table_rate", 0)),
            definition_rate=_safe_float(spec.get("definition_rate", 0)),
            code_block_rate=_safe_float(spec.get("code_block_rate", 0)),
            key_takeaways_rate=_safe_float(spec.get("key_takeaways_rate", 0)),
            dominant_content_type=spec.get("dominant_content_type"),
            dominant_authority_type=spec.get("dominant_authority_type"),
            required_elements=spec.get("required_elements"),
            exemplar_themes=spec.get("exemplar_themes"),
        )
        session.add(spec_model)
        counts["cluster_specs"] += 1

    # ── SPA Results ──────────────────────────────────────────────
    for spa in spa_results_raw:
        spa_model = SpaResultModel(
            id=uuid.uuid4(),
            run_id=run_id,
            cluster_id=spa.get("cluster_id"),
            cluster_name=spa.get("cluster_name", "all"),
            t_stat=_safe_float(spa.get("t_stat")),
            p_value=_safe_float(spa.get("p_value")),
            effect=spa.get("effect", ""),
            mean_citation_similarity=_safe_float(spa.get("mean_citation_similarity")),
            mean_company_similarity=_safe_float(spa.get("mean_company_similarity")),
        )
        session.add(spa_model)
        counts["spa_results"] += 1

    # ── Centroid Results ─────────────────────────────────────────
    centroids_raw: List[Dict[str, Any]] = analysis.get("centroids", [])
    for centroid in centroids_raw:
        centroid_model = CentroidResultModel(
            id=uuid.uuid4(),
            run_id=run_id,
            cluster_name=centroid.get("cluster_name", ""),
            distance=_safe_float(centroid.get("distance")),
        )
        session.add(centroid_model)
        counts["centroid_results"] += 1

    # ── Run Queries (must precede citations due to composite FK) ──
    queries_raw = _load_json(slug_dir / "queries.json")
    if isinstance(queries_raw, list):
        for q in queries_raw:
            query_model = RunQueryModel(
                id=uuid.uuid4(),
                run_id=run_id,
                query_id=q.get("query_id", ""),
                cluster_id=q.get("cluster_id"),
                cluster_name=q.get("cluster_name", ""),
                query_text=q.get("query_text", ""),
                buyer_stage=q.get("buyer_stage"),
                persona_tag=q.get("persona_tag"),
            )
            session.add(query_model)
            counts["run_queries"] += 1
        await session.flush()  # ensure run_queries rows exist before citations

    # ── Run Citations ────────────────────────────────────────────
    citations_raw = _load_json(slug_dir / "enriched_citations.json")
    if isinstance(citations_raw, list):
        for cit in citations_raw:
            engine = _map_engine(cit.get("engine", ""))
            if engine is None:
                continue

            citation_model = RunCitationModel(
                id=uuid.uuid4(),
                run_id=run_id,
                query_id=cit.get("query_id", ""),
                cluster_name=cit.get("cluster_name", ""),
                engine=engine,
                url=cit.get("url", ""),
                domain=cit.get("domain", ""),
            )
            session.add(citation_model)
            counts["run_citations"] += 1

    await session.flush()
    return counts


async def backfill(
    slugs: Optional[List[str]] = None,
    *,
    dry_run: bool = False,
) -> None:
    """Run the backfill for specified slugs (or all found)."""
    if not settings.database_url:
        logger.error("DATABASE_URL not set. Cannot backfill.")
        sys.exit(1)

    # Discover slugs
    if slugs:
        slug_list = slugs
    else:
        if not GAP_DIR.is_dir():
            logger.error("Gap analysis artifacts dir not found: %s", GAP_DIR)
            sys.exit(1)
        slug_list = sorted(
            d.name for d in GAP_DIR.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        )

    logger.info(
        "Backfilling %d slug(s): %s%s",
        len(slug_list),
        ", ".join(slug_list),
        " [DRY-RUN]" if dry_run else "",
    )

    # Ensure engine is initialized
    get_engine()

    total_counts: Dict[str, int] = {}

    session_factory = get_session_factory()
    async with session_factory() as session:
        for slug in slug_list:
            try:
                counts = await _backfill_slug(session, slug, dry_run=dry_run)
                for k, v in counts.items():
                    total_counts[k] = total_counts.get(k, 0) + v
                if counts:
                    logger.info(
                        "  %s: %s",
                        slug,
                        " | ".join(f"{k}={v}" for k, v in counts.items() if v > 0),
                    )
            except Exception:
                logger.exception("Failed to backfill slug '%s'", slug)
                await session.rollback()
                continue

        if not dry_run:
            await session.commit()
            logger.info("Committed all changes.")

    logger.info(
        "Backfill complete. Totals: %s",
        " | ".join(f"{k}={v}" for k, v in total_counts.items() if v > 0) or "(nothing inserted)",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill gap analysis artifacts from JSON to Postgres",
    )
    parser.add_argument(
        "--slug", type=str, default=None,
        help="Specific slug to backfill (default: all found)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Parse and validate without writing to DB",
    )
    args = parser.parse_args()

    slugs = [args.slug] if args.slug else None
    asyncio.run(backfill(slugs, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
