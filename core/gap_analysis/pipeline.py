from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import async_sessionmaker

from core.gap_analysis.steps.s1_embed_assets import embed_company_assets
from core.models.gap_analysis import PlatformResult
from core.research.audience_persona.storage import PersonaStorage
from core.shared_tools.structured_logging import scoped_bind
from core.shared_tools.vector_store import (
    async_collection_exists,
    async_get_all_embeddings,
)

from core.config.settings import settings as _settings
from core.shared_tools.tracing import (
    create_session,
    create_span,
    create_trace,
    end_span,
    flush as flush_traces,
    update_trace_output,
)

logger = logging.getLogger(__name__)


def _ga_dbg(msg: str) -> None:
    """Emit a microscopic debug log when GA_DEBUG=true."""
    if _settings.gap_analysis_debug:
        logger.info("[ga-debug] %s", msg)


# ── Self-citation helpers ──────────────────────────────────────────


def _normalize_domain(domain: str) -> str:
    """Strip 'www.' prefix and lowercase a domain for comparison."""
    return domain.lower().removeprefix("www.")


def _flag_company_citations(
    results: List[PlatformResult],
    company_domain: Optional[str],
) -> None:
    """In-place: set is_company_citation=True for citations matching company domain."""
    if not company_domain:
        return
    norm_company = _normalize_domain(company_domain)
    for result in results:
        for citation in result.citations:
            citation_netloc = urlparse(str(citation.url)).netloc
            norm_citation = _normalize_domain(citation_netloc)
            if norm_citation == norm_company or norm_citation.endswith(
                f".{norm_company}"
            ):
                citation.is_company_citation = True


def _build_company_citation_map(
    results: List[PlatformResult],
) -> Dict[str, List[str]]:
    """Build query_id → [engine1, engine2, ...] map from flagged citations.

    Must be called BEFORE s4 dedup, since dedup collapses multi-engine info.
    """
    citation_map: Dict[str, List[str]] = defaultdict(list)
    for result in results:
        for citation in result.citations:
            if citation.is_company_citation:
                if result.engine not in citation_map[result.query_id]:
                    citation_map[result.query_id].append(result.engine)
    return dict(citation_map)

# ── CLI progress helpers ────────────────────────────────────────────

_STEP_NAMES: dict[int, str] = {
    1: "Embed Company Assets",
    2: "Generate Queries",
    3: "Search Platforms",
    4: "Enrich Citations",
    5: "Embed Content",
    6: "Analyze Gaps",
    7: "Generate Visualizations",
    8: "Generate Report",
}


def _fmt_duration(seconds: float) -> str:
    if seconds >= 60:
        m, s = divmod(seconds, 60)
        return f"{int(m)}m {s:.1f}s"
    return f"{seconds:.1f}s"


def _cli_header(slug: str, skip_steps: list[int]) -> None:
    w = sys.stdout.write
    w("\n")
    w("─" * 52 + "\n")
    w(f"  Gap Analysis Pipeline — {slug}\n")
    if skip_steps:
        w(f"  Skipping: {', '.join(str(s) for s in sorted(skip_steps))}\n")
    w("─" * 52 + "\n\n")
    sys.stdout.flush()


def _cli_step(step: int, elapsed: float, skipped: bool = False) -> None:
    name = _STEP_NAMES.get(step, f"Step {step}")
    tag = " (cached)" if skipped else ""
    dots = "." * (36 - len(name))
    sys.stdout.write(f"  [{step}/8] {name} {dots} {_fmt_duration(elapsed):>8s}{tag}\n")
    sys.stdout.flush()


def _cli_footer(total: float, skipped_count: int) -> None:
    run_count = 8 - skipped_count
    parts = [f"{run_count} executed"]
    if skipped_count:
        parts.append(f"{skipped_count} cached")
    w = sys.stdout.write
    w("\n" + "─" * 52 + "\n")
    w(f"  Done — {_fmt_duration(total)} total ({', '.join(parts)})\n")
    w("─" * 52 + "\n\n")
    sys.stdout.flush()

from core.gap_analysis.steps.s2_generate_queries import (
    generate_queries,
    generate_queries_from_topics,
)
from core.gap_analysis.steps.s8_generate_report import aggregate_per_topic
from core.gap_analysis.steps.s3_search_platforms import (
    save_platform_results,
    search_platforms,
)
from core.gap_analysis.steps.s4_enrich_citations import (
    enrich_citations,
    save_enriched_citations,
)
from core.gap_analysis.steps.s5_embed_content import embed_all, save_embeddings
from core.gap_analysis.steps.s6_analyze import compute_gap_analysis
from core.gap_analysis.steps.s7_visualize import generate_visualizations
from core.gap_analysis.steps.s8_generate_report import generate_gap_report, save_report
from core.gap_analysis.persistence import (
    persist_s1,
    persist_s2,
    persist_s3,
    persist_s4,
    persist_s5,
    persist_s6,
    persist_s7,
    persist_s8,
)
from core.models.gap_analysis import (
    AnalysisResult,
    CompanyPageAnalysis,
    EnrichedCitation,
    GapAnalysisInput,
    GapReport,
    GeneratedQuery,
    PlatformResult,
    SemanticUnit,
)
from core.models.topic_discovery import TopicAssignment

_PROJECT_ROOT = Path(__file__).resolve().parents[2]  # content-strategy-engine/


def _company_slug(input_data: GapAnalysisInput) -> str:
    return input_data.company_slug or re.sub(
        r"[^a-z0-9]+", "-", input_data.company_name.lower()
    ).strip("-")


def _artifact_dir(company_slug: str) -> Path:
    path = _PROJECT_ROOT / "artifacts" / "gap_analysis" / company_slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def _resolve_persona_paths(input_data: "GapAnalysisInput", slug: str) -> None:
    """Auto-discover persona paths from audience_persona artifacts when none provided.

    Mutates ``input_data.persona_paths`` in place. Explicit paths take priority.
    """
    if input_data.persona_paths:
        logger.info("Using %d explicit persona path(s)", len(input_data.persona_paths))
        return

    storage = PersonaStorage(artifacts_root=_PROJECT_ROOT / "artifacts", slug=slug)
    paths = storage.list_persona_paths()
    if paths:
        input_data.persona_paths = paths
        logger.info(
            "Auto-discovered %d persona(s) from artifacts/audience_personas/%s/",
            len(paths),
            slug,
        )
    else:
        logger.info("No audience persona artifacts found for slug '%s'", slug)


def _load_json_list(path: Path, model_cls):
    if not path.exists():
        raise RuntimeError(f"Missing artifact: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return [model_cls(**item) for item in data]


async def run_gap_analysis(
    input_data: GapAnalysisInput,
    skip_steps: Optional[List[int]] = None,
    *,
    session_factory: Optional[async_sessionmaker] = None,
    run_id: Optional[uuid.UUID] = None,
    company_id: Optional[uuid.UUID] = None,
    trace_parent: Optional[object] = None,
) -> GapReport:
    skip_steps = skip_steps or []
    slug = _company_slug(input_data)
    artifact_dir = _artifact_dir(slug)
    pipeline_start = time.monotonic()
    skipped_count = len([s for s in range(1, 9) if s in skip_steps])

    # ── LangSmith tracing: create root trace or child span ────────────
    session_id = create_session(slug)
    if trace_parent is not None:
        trace = create_span(trace_parent, f"gap-analysis/{slug}", input_data={
            "company_slug": slug,
            "platforms": input_data.platforms,
            "max_queries": input_data.max_queries,
            "skip_steps": skip_steps,
        })
    else:
        trace = create_trace(
            session_id,
            f"gap-analysis/{slug}",
            input_data={
                "company_slug": slug,
                "platforms": input_data.platforms,
                "max_queries": input_data.max_queries,
                "skip_steps": skip_steps,
            },
            project_name=_settings.gap_analysis_langsmith_project,
        )

    # Fast/demo mode: cap queries and use only fastest engines
    if input_data.fast_mode:
        input_data.max_queries = min(input_data.max_queries or 30, 30)
        if not input_data.platforms or len(input_data.platforms) > 2:
            input_data.platforms = ["openai", "perplexity"]
        logger.info(
            "Fast mode enabled: max_queries=%d, platforms=%s",
            input_data.max_queries,
            input_data.platforms,
        )

    _cli_header(slug, skip_steps)

    # Auto-resolve persona paths before query generation (depends on neither S1 nor S2)
    _resolve_persona_paths(input_data, slug)

    # ── Branch A: S1 (crawl + embed company assets) ─────────────────
    # ── Branch B: S2 → S3 → S4 → S5 (query → search → enrich → embed)
    # Both branches run in parallel. S6 is the merge point.

    async def _run_s1() -> tuple[List[SemanticUnit], float]:
        s1_span = create_span(trace, "ga-s1-embed-assets", input_data={"skip": 1 in skip_steps})
        try:
            with scoped_bind(step_name="s1_embed_company_assets"):
                t = time.monotonic()
                _ga_dbg(f"S1 started: embed_company_assets (skip={1 in skip_steps})")
                logger.info("Step 1 started: embed_company_assets")
                if 1 in skip_steps:
                    units = _load_json_list(
                        artifact_dir / "company_embeddings.json", SemanticUnit
                    )
                    if not any(u.embedding for u in units):
                        if await async_collection_exists(slug):
                            embedding_map = await async_get_all_embeddings(slug)
                            hydrated = 0
                            for unit in units:
                                if unit.unit_id in embedding_map:
                                    unit.embedding = embedding_map[unit.unit_id]
                                    hydrated += 1
                            logger.info(
                                "Hydrated %d/%d unit embeddings from pgvector.",
                                hydrated, len(units),
                            )
                        else:
                            logger.warning(
                                "No pgvector collection found for '%s' and JSON has no embeddings. "
                                "S6/S7 may produce degraded results.", slug,
                            )
                    _ga_dbg(f"S1 loaded {len(units)} cached units")
                else:
                    units = await embed_company_assets(input_data)
                    _ga_dbg(f"S1 produced {len(units)} units")
                elapsed = time.monotonic() - t
                _ga_dbg(f"S1 DONE in {elapsed:.1f}s ({len(units)} units)")
                logger.info("Step 1 completed: embed_company_assets (%.1fs)", elapsed)
                await persist_s1(session_factory, run_id, company_id, slug, units)
                _cli_step(1, elapsed, skipped=1 in skip_steps)
                end_span(s1_span, output={"unit_count": len(units), "elapsed_s": round(elapsed, 1)})
                return units, elapsed
        except BaseException as exc:
            end_span(s1_span, error=str(exc))
            raise

    async def _run_s2_to_s5() -> tuple:
        """Run the query → search → enrich → embed chain (no S1 dependency)."""

        # ── S2: generate queries ──
        _ga_dbg(f"S2 started: generate_queries (skip={2 in skip_steps})")
        s2_span = create_span(trace, "ga-s2-generate-queries", input_data={"skip": 2 in skip_steps})
        try:
            with scoped_bind(step_name="s2_generate_queries"):
                s2_start = time.monotonic()
                logger.info("Step 2 started: generate_queries")
                if 2 in skip_steps:
                    queries = _load_json_list(artifact_dir / "queries.json", GeneratedQuery)
                else:
                    queries = await generate_queries(input_data, trace_span=s2_span)
                    (artifact_dir / "queries.json").write_text(
                        json.dumps([q.model_dump(mode="json") for q in queries], indent=2, default=str),
                        encoding="utf-8",
                    )
                s2_elapsed = time.monotonic() - s2_start
                _ga_dbg(f"S2 DONE in {s2_elapsed:.1f}s ({len(queries)} queries)")
                logger.info("Step 2 completed: generate_queries (%.1fs)", s2_elapsed)
                await persist_s2(session_factory, run_id, company_id, slug, queries)
                _cli_step(2, s2_elapsed, skipped=2 in skip_steps)
                end_span(s2_span, output={"query_count": len(queries), "elapsed_s": round(s2_elapsed, 1)})
        except BaseException as exc:
            end_span(s2_span, error=str(exc))
            raise

        # ── S3: search platforms ──
        _ga_dbg("S3 starting: search_platforms")
        s3_span = create_span(trace, "ga-s3-search-platforms", input_data={
            "skip": 3 in skip_steps,
            "query_count": len(queries),
            "platforms": input_data.platforms,
        })
        try:
            with scoped_bind(step_name="s3_search_platforms"):
                s3_start = time.monotonic()
                logger.info("Step 3 started: search_platforms")
                if 3 in skip_steps:
                    platform_results: List[PlatformResult] = []
                    for name in input_data.platforms:
                        path = artifact_dir / "platform_results" / f"{name}_results.jsonl"
                        if not path.exists():
                            continue
                        items = [
                            PlatformResult(**json.loads(line))
                            for line in path.read_text(encoding="utf-8").splitlines()
                            if line.strip()
                        ]
                        platform_results.extend(items)
                else:
                    platform_results = await search_platforms(queries, input_data.platforms, trace_span=s3_span)
                    save_platform_results(platform_results, artifact_dir / "platform_results")
                logger.info("Step 3 completed: search_platforms (%.1fs)", time.monotonic() - s3_start)

                _flag_company_citations(platform_results, input_data.domain)
                company_citation_map = _build_company_citation_map(platform_results)
                if company_citation_map:
                    logger.info(
                        "Self-citation detection: company cited for %d queries across platforms",
                        len(company_citation_map),
                    )

                s3_elapsed = time.monotonic() - s3_start
                await persist_s3(session_factory, run_id, company_id, slug, platform_results, queries)
                _cli_step(3, s3_elapsed, skipped=3 in skip_steps)
                end_span(s3_span, output={
                    "result_count": len(platform_results),
                    "citation_count": sum(len(r.citations) for r in platform_results),
                    "elapsed_s": round(s3_elapsed, 1),
                })
        except BaseException as exc:
            end_span(s3_span, error=str(exc))
            raise

        # ── S4: enrich citations ──
        _ga_dbg("S4 starting: enrich_citations")
        s4_span = create_span(trace, "ga-s4-enrich-citations", input_data={"skip": 4 in skip_steps})
        try:
            with scoped_bind(step_name="s4_enrich_citations"):
                s4_start = time.monotonic()
                logger.info("Step 4 started: enrich_citations")
                if 4 in skip_steps:
                    enriched = _load_json_list(
                        artifact_dir / "enriched_citations.json", EnrichedCitation
                    )
                else:
                    query_lookup = {q.query_id: q for q in queries}
                    enriched = await enrich_citations(platform_results, query_lookup=query_lookup)
                    save_enriched_citations(enriched, artifact_dir / "enriched_citations.json")
                s4_elapsed = time.monotonic() - s4_start
                logger.info("Step 4 completed: enrich_citations (%.1fs)", s4_elapsed)
                await persist_s4(session_factory, run_id, company_id, slug, enriched)
                _cli_step(4, s4_elapsed, skipped=4 in skip_steps)
                end_span(s4_span, output={"enriched_count": len(enriched), "elapsed_s": round(s4_elapsed, 1)})
        except BaseException as exc:
            end_span(s4_span, error=str(exc))
            raise

        # ── S5: embed content ──
        _ga_dbg("S5 starting: embed_content")
        s5_span = create_span(trace, "ga-s5-embed-content", input_data={"skip": 5 in skip_steps})
        try:
            with scoped_bind(step_name="s5_embed_content"):
                s5_start = time.monotonic()
                logger.info("Step 5 started: embed_content")
                if 5 in skip_steps:
                    queries = _load_json_list(
                        artifact_dir / "embeddings" / "queries_with_embeddings.json",
                        GeneratedQuery,
                    )
                    enriched = _load_json_list(
                        artifact_dir / "embeddings" / "citations_with_embeddings.json",
                        EnrichedCitation,
                    )
                else:
                    queries, enriched = await embed_all(queries, enriched, company_slug=slug)
                    save_embeddings(queries, enriched, artifact_dir / "embeddings")
                s5_elapsed = time.monotonic() - s5_start
                logger.info("Step 5 completed: embed_content (%.1fs)", s5_elapsed)
                await persist_s5(session_factory, run_id, company_id, slug, queries, enriched)
                _cli_step(5, s5_elapsed, skipped=5 in skip_steps)
                end_span(s5_span, output={
                    "query_count": len(queries),
                    "enriched_count": len(enriched),
                    "elapsed_s": round(s5_elapsed, 1),
                })
        except BaseException as exc:
            end_span(s5_span, error=str(exc))
            raise

        return queries, enriched, company_citation_map

    # ── Run both branches in parallel, merge at S6 ──────────────────
    try:
        _ga_dbg("Starting parallel branches: S1 || S2→S3→S4→S5")
        (company_units, s1_elapsed), (queries, enriched, company_citation_map) = (
            await asyncio.gather(_run_s1(), _run_s2_to_s5())
        )
        _ga_dbg(
            f"Both branches complete — S1: {len(company_units)} units in {s1_elapsed:.1f}s, "
            f"S2→S5: {len(queries)} queries, {len(enriched)} enriched"
        )

        # Load company page analysis (produced by S1 alongside embeddings)
        page_analysis_path = artifact_dir / "company_page_analysis.json"
        page_analysis_lookup: Dict[str, CompanyPageAnalysis] = {}
        if page_analysis_path.exists():
            try:
                raw = json.loads(page_analysis_path.read_text(encoding="utf-8"))
                for item in raw:
                    pa = CompanyPageAnalysis(**item)
                    page_analysis_lookup[pa.url] = pa
                logger.info(
                    "Loaded company page analysis: %d pages", len(page_analysis_lookup)
                )
            except Exception:
                logger.warning("Failed to load company_page_analysis.json, skipping")

        # Step 6: analyze
        _ga_dbg("S6 starting: compute_gap_analysis")
        s6_span = create_span(trace, "ga-s6-analyze", input_data={"skip": 6 in skip_steps})
        try:
            with scoped_bind(step_name="s6_compute_gap_analysis"):
                step_start = time.monotonic()
                logger.info("Step 6 started: compute_gap_analysis")
                if 6 in skip_steps:
                    analysis = AnalysisResult(
                        **json.loads((artifact_dir / "analysis.json").read_text(encoding="utf-8"))
                    )
                else:
                    analysis = compute_gap_analysis(
                        queries,
                        company_units,
                        enriched,
                        company_citation_map=company_citation_map,
                        page_analysis_lookup=page_analysis_lookup or None,
                    )
                    (artifact_dir / "analysis.json").write_text(
                        json.dumps(analysis.model_dump(mode="json"), indent=2, default=str), encoding="utf-8"
                    )
                s6_elapsed = time.monotonic() - step_start
                logger.info("Step 6 completed: compute_gap_analysis (%.1fs)", s6_elapsed)
                await persist_s6(session_factory, run_id, company_id, slug, analysis)
                _cli_step(6, s6_elapsed, skipped=6 in skip_steps)
                end_span(s6_span, output={
                    "gap_count": len(analysis.gaps),
                    "cluster_count": len(analysis.cluster_specs),
                    "elapsed_s": round(s6_elapsed, 1),
                })
        except BaseException as exc:
            end_span(s6_span, error=str(exc))
            raise

        # Step 7: visualize
        _ga_dbg("S7 starting: generate_visualizations")
        s7_span = create_span(trace, "ga-s7-visualize", input_data={"skip": 7 in skip_steps})
        try:
            with scoped_bind(step_name="s7_generate_visualizations"):
                step_start = time.monotonic()
                logger.info("Step 7 started: generate_visualizations")
                if 7 in skip_steps:
                    visualization_paths = json.loads(
                        (artifact_dir / "visualizations" / "visualization_paths.json").read_text(
                            encoding="utf-8"
                        )
                    )
                else:
                    visualization_paths = generate_visualizations(
                        queries, enriched, company_units, analysis, artifact_dir / "visualizations"
                    )
                    (artifact_dir / "visualizations" / "visualization_paths.json").write_text(
                        json.dumps(visualization_paths, indent=2), encoding="utf-8"
                    )
                s7_elapsed = time.monotonic() - step_start
                logger.info("Step 7 completed: generate_visualizations (%.1fs)", s7_elapsed)
                await persist_s7(session_factory, run_id, company_id, slug, visualization_paths)
                _cli_step(7, s7_elapsed, skipped=7 in skip_steps)
                end_span(s7_span, output={
                    "viz_count": len(visualization_paths) if isinstance(visualization_paths, dict) else 0,
                    "elapsed_s": round(s7_elapsed, 1),
                })
        except BaseException as exc:
            end_span(s7_span, error=str(exc))
            raise

        # Step 8: report
        _ga_dbg("S8 starting: generate_gap_report")
        s8_span = create_span(trace, "ga-s8-report", input_data={"skip": 8 in skip_steps})
        try:
            with scoped_bind(step_name="s8_generate_gap_report"):
                step_start = time.monotonic()
                logger.info("Step 8 started: generate_gap_report")
                if 8 in skip_steps:
                    report = GapReport(
                        report_md=(artifact_dir / "gap_report.md").read_text(encoding="utf-8"),
                        report_json=json.loads(
                            (artifact_dir / "gap_report.json").read_text(encoding="utf-8")
                        ),
                        generation_spec_md=(artifact_dir / "generation_spec.md").read_text(
                            encoding="utf-8"
                        ),
                        generation_spec_json=json.loads(
                            (artifact_dir / "generation_spec.json").read_text(encoding="utf-8")
                        ),
                        visualization_paths=list(visualization_paths.values())
                        if isinstance(visualization_paths, dict)
                        else visualization_paths,
                    )
                else:
                    report = await generate_gap_report(analysis, queries, enriched, trace_span=s8_span)
                    report.visualization_paths = list(visualization_paths.values())
                    save_report(report, artifact_dir, analysis=analysis)
                s8_elapsed = time.monotonic() - step_start
                logger.info("Step 8 completed: generate_gap_report (%.1fs)", s8_elapsed)
                await persist_s8(session_factory, run_id, company_id, slug, report, analysis)
                _cli_step(8, s8_elapsed, skipped=8 in skip_steps)
                end_span(s8_span, output={"elapsed_s": round(s8_elapsed, 1)})
        except BaseException as exc:
            end_span(s8_span, error=str(exc))
            raise

        total = time.monotonic() - pipeline_start
        logger.info("Pipeline completed: all steps finished (%.1fs total)", total)
        _cli_footer(total, skipped_count)
        update_trace_output(trace, output={
            "total_queries": len(queries),
            "total_enriched": len(enriched),
            "total_gaps": len(analysis.gaps),
            "total_time_s": round(total, 1),
            "status": "completed",
        })
        return report
    except BaseException as exc:
        total = time.monotonic() - pipeline_start
        logger.error("Pipeline FAILED after %.1fs: %s", total, exc)
        end_span(trace, error=str(exc))
        raise
    finally:
        flush_traces()


# ── Topic-Scoped Gap Analysis (TD Integration) ──────────────────────


async def run_topic_scoped_gap_analysis(
    topics: List[TopicAssignment],
    base_input: GapAnalysisInput,
    *,
    existing_ga_slug: Optional[str] = None,
    skip_visualizations: bool = True,
    session_factory: Optional[async_sessionmaker] = None,
    run_id: Optional[uuid.UUID] = None,
    company_id: Optional[uuid.UUID] = None,
) -> tuple[GapReport, Dict[str, List[str]]]:
    """Run a topic-scoped gap analysis for TD-approved TopicAssignments.

    Reuses S1 embeddings from an existing GA run (if available), uses
    topic-scoped S2, runs S3-S6 identically (fewer queries = faster),
    skips S7 by default, runs S8 with per-topic aggregation.

    Storage path: artifacts/gap_analysis/{slug}/topic_scoped/{run_id}/

    Returns:
        Tuple of (GapReport, topic_query_map) where topic_query_map
        maps topic_assignment_id → [query_ids].
    """
    slug = _company_slug(base_input)
    scoped_run_id = run_id or uuid.uuid4()
    scoped_dir = _PROJECT_ROOT / "artifacts" / "gap_analysis" / slug / "topic_scoped" / str(scoped_run_id)
    scoped_dir.mkdir(parents=True, exist_ok=True)
    pipeline_start = time.monotonic()

    logger.info(
        "Topic-scoped GA: %d topics, slug=%s, run_id=%s",
        len(topics), slug, scoped_run_id,
    )

    # Auto-resolve persona paths
    _resolve_persona_paths(base_input, slug)

    # ── S1: Reuse cached company embeddings ──
    with scoped_bind(step_name="s1_embed_company_assets"):
        s1_start = time.monotonic()
        cache_slug = existing_ga_slug or slug
        cache_dir = _PROJECT_ROOT / "artifacts" / "gap_analysis" / cache_slug
        embeddings_path = cache_dir / "company_embeddings.json"

        if embeddings_path.exists():
            company_units = _load_json_list(embeddings_path, SemanticUnit)
            # Hydrate from pgvector if needed
            if not any(u.embedding for u in company_units):
                if await async_collection_exists(cache_slug):
                    embedding_map = await async_get_all_embeddings(cache_slug)
                    for unit in company_units:
                        if unit.unit_id in embedding_map:
                            unit.embedding = embedding_map[unit.unit_id]
            logger.info("S1: reused %d cached embeddings from '%s'", len(company_units), cache_slug)
        else:
            company_units = await embed_company_assets(base_input)
            logger.info("S1: computed %d embeddings (no cache)", len(company_units))

        # Load page analysis (if available)
        page_analysis_lookup: Dict[str, CompanyPageAnalysis] = {}
        page_analysis_path = cache_dir / "company_page_analysis.json"
        if page_analysis_path.exists():
            try:
                raw = json.loads(page_analysis_path.read_text(encoding="utf-8"))
                for item in raw:
                    pa = CompanyPageAnalysis(**item)
                    page_analysis_lookup[pa.url] = pa
            except Exception:
                pass
        s1_elapsed = time.monotonic() - s1_start
        logger.info("S1 completed (%.1fs)", s1_elapsed)

    # ── S2: Topic-scoped query generation ──
    with scoped_bind(step_name="s2_generate_queries"):
        s2_start = time.monotonic()
        queries = await generate_queries_from_topics(
            topics=topics,
            company_context_path=base_input.company_context_path,
            persona_paths=base_input.persona_paths,
            company_name=base_input.company_name,
            company_domain=base_input.domain,
            product_name=base_input.product_name,
            product_slug=base_input.product_slug,
            product_description=base_input.product_description,
        )
        (scoped_dir / "queries.json").write_text(
            json.dumps([q.model_dump(mode="json") for q in queries], indent=2, default=str),
            encoding="utf-8",
        )
        s2_elapsed = time.monotonic() - s2_start
        logger.info("S2 completed: %d queries (%.1fs)", len(queries), s2_elapsed)

        if not queries:
            logger.warning("Topic-scoped S2 produced 0 queries. Returning empty report.")
            empty_report = GapReport()
            return empty_report, {}

    # ── S3: Search platforms ──
    with scoped_bind(step_name="s3_search_platforms"):
        s3_start = time.monotonic()
        platform_results = await search_platforms(queries, base_input.platforms)
        results_dir = scoped_dir / "platform_results"
        save_platform_results(platform_results, results_dir)

        _flag_company_citations(platform_results, base_input.domain)
        company_citation_map = _build_company_citation_map(platform_results)
        s3_elapsed = time.monotonic() - s3_start
        logger.info("S3 completed: %d results (%.1fs)", len(platform_results), s3_elapsed)

    # ── S4: Enrich citations ──
    with scoped_bind(step_name="s4_enrich_citations"):
        s4_start = time.monotonic()
        query_lookup = {q.query_id: q for q in queries}
        enriched = await enrich_citations(platform_results, query_lookup=query_lookup)
        save_enriched_citations(enriched, scoped_dir / "enriched_citations.json")
        s4_elapsed = time.monotonic() - s4_start
        logger.info("S4 completed: %d enriched (%.1fs)", len(enriched), s4_elapsed)

    # ── S5: Embed content ──
    with scoped_bind(step_name="s5_embed_content"):
        s5_start = time.monotonic()
        queries, enriched = await embed_all(queries, enriched, company_slug=slug)
        save_embeddings(queries, enriched, scoped_dir / "embeddings")
        s5_elapsed = time.monotonic() - s5_start
        logger.info("S5 completed (%.1fs)", s5_elapsed)

    # ── S6: Analyze gaps ──
    with scoped_bind(step_name="s6_compute_gap_analysis"):
        s6_start = time.monotonic()
        analysis = compute_gap_analysis(
            queries,
            company_units,
            enriched,
            company_citation_map=company_citation_map,
            page_analysis_lookup=page_analysis_lookup or None,
        )
        (scoped_dir / "analysis.json").write_text(
            json.dumps(analysis.model_dump(mode="json"), indent=2, default=str),
            encoding="utf-8",
        )
        s6_elapsed = time.monotonic() - s6_start
        logger.info("S6 completed (%.1fs)", s6_elapsed)

    # ── S7: Skip visualizations by default ──
    with scoped_bind(step_name="s7_generate_visualizations"):
        if not skip_visualizations:
            generate_visualizations(
                queries, enriched, company_units, analysis, scoped_dir / "visualizations"
            )

    # ── S8: Report + per-topic aggregation ──
    with scoped_bind(step_name="s8_generate_gap_report"):
        s8_start = time.monotonic()
        report = await generate_gap_report(analysis, queries, enriched)
        save_report(report, scoped_dir, analysis=analysis)

        # Per-topic aggregation (sets analysis.topic_query_map as side effect)
        topic_metrics = aggregate_per_topic(analysis, queries)
        topic_query_map = analysis.topic_query_map

        # Re-save analysis.json with topic_query_map populated
        (scoped_dir / "analysis.json").write_text(
            json.dumps(analysis.model_dump(mode="json"), indent=2, default=str),
            encoding="utf-8",
        )
        # Save per-topic metrics separately
        (scoped_dir / "topic_metrics.json").write_text(
            json.dumps(topic_metrics, indent=2, default=str),
            encoding="utf-8",
        )
        s8_elapsed = time.monotonic() - s8_start
        logger.info("S8 completed (%.1fs)", s8_elapsed)

    total = time.monotonic() - pipeline_start
    logger.info(
        "Topic-scoped GA completed: %d queries, %d gaps, %.1fs total",
        len(queries), len(analysis.gaps), total,
    )

    return report, topic_query_map
