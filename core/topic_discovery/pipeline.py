"""Topic Discovery pipeline orchestrators — Pipeline A (Discovery) + Pipeline B (Expansion).

Pipeline A (run_topic_discovery_pipeline):
  Phase 0: Preflight (load company context + persona profiles, validate prereqs)
  Phase 1 (S1): Multi-Source Subdomain Generation (A+B+C parallel, then D sequential)
  Phase 2 (S2): Exhaustiveness Evaluation & Merge (dedup → coverage metrics → hierarchy)
  ── HITL-1: Taxonomy approval (approve/modify/retry, max 2 retries) ──
  Phase 2.5: Algorithmic Subdomain Scoring (zero LLM calls) + Persona Affinity
  → Ends with status=discovery_complete. No expansion.

Pipeline B (run_topic_expansion_pipeline):
  Preflight: Load taxonomy + scores + personas from Pipeline A artifacts
  Phase 3 (S3): On-Demand Expansion (1 LLM call per selected subdomain)
  ── HITL-2: Matrix approval (approve/modify) ──
  Finalize: Update manifest, emit completed
  → Re-entrant: can be called multiple times with different subdomains.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from core.config.settings import settings
from core.content_engine.llm_client import configure_openrouter
from core.models.topic_discovery import (
    BuyerStage,
    CaptureRecaptureResult,
    IntentType,
    PersonaAffinityIndex,
    RelevanceCell,
    ScoredSubdomainList,
    SourceResult,
    SubdomainNode,
    TaxonomyTree,
    TDSource,
    TopicAssignment,
    TopicAssignmentMatrix,
    TopicDiscoveryInput,
    TopicDiscoveryManifest,
    TopicDiscoveryOutput,
    TopicDiscoveryStatus,
    TopicExpansionInput,
    TopicExpansionOutput,
)
from core.research.audience_persona.storage import PersonaStorage
from core.research.utils import load_persona_profiles, read_company_context
from core.shared_tools.tracing import (
    create_session,
    create_span,
    create_trace,
    end_span,
    flush,
    log_score,
    set_current_span,
)
from core.topic_discovery.agents import (
    compute_all_coverage_metrics,
    deduplicate_subdomains_with_clusters,
    run_hierarchy_construction,
    run_relevance_filtering,
    run_source_a_company_brainstorm,
    run_source_b_persona_brainstorm,
    run_source_c_deep_research,
    run_source_d_adversarial,
    run_subdomain_expansion,
    run_topic_generation,
    run_unified_hierarchy_and_scoring,
)
from core.topic_discovery.graph import (
    build_td_matrix_review_graph,
    build_td_subdomain_selection_graph,
    build_td_taxonomy_review_graph,
    run_td_hitl_checkpoint,
)
from core.topic_discovery.scoring import (
    apply_source_confidence_adjustment,
    build_persona_affinity_index_from_taxonomy,
    build_scored_subdomain_list_from_taxonomy,
    compute_persona_affinity_index,
    compute_source_confidence_scores,
    compute_subdomain_scores,
    compute_topic_priority,
)
from core.topic_discovery.storage import TopicDiscoveryStorage

logger = logging.getLogger(__name__)

_MAX_COMPANY_CONTEXT_CHARS = 60_000
_MAX_TAXONOMY_RETRIES = 2


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


_TDInput = Union[TopicDiscoveryInput, TopicExpansionInput]


def _resolve_slug(input_data: _TDInput) -> str:
    """Derive company slug from input."""
    if input_data.company_slug:
        return input_data.company_slug
    slug = input_data.company_name.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug).strip("-")
    return slug


def _resolve_effective_slug(input_data: _TDInput) -> str:
    """Derive effective slug (company__product if product_slug is set)."""
    slug = _resolve_slug(input_data)
    if input_data.product_slug:
        return f"{slug}__{input_data.product_slug}"
    return slug


def _emit(
    event_bus: Optional[Any],
    task_id: Optional[str],
    event_type: str,
    data: Dict[str, Any],
) -> None:
    """Null-safe SSE event publish."""
    if event_bus and task_id:
        event_bus.publish(task_id, event_type, data)


def _update_task(
    task_store: Optional[Any],
    task_id: Optional[str],
    **kwargs: Any,
) -> None:
    """Null-safe task_store update."""
    if task_store and task_id:
        task_store.update_task(task_id, **kwargs)


def _build_persona_summaries(persona_mds: List[str], max_chars: int = 30_000) -> str:
    """Build a concatenated summary of all persona profiles."""
    if not persona_mds:
        return ""
    parts = []
    for i, md in enumerate(persona_mds, 1):
        parts.append(f"### Persona {i}\n\n{md[:10_000]}")
    result = "\n\n---\n\n".join(parts)
    return result[:max_chars]


def _flatten_subdomain_names(nodes: List[SubdomainNode]) -> List[str]:
    """Recursively flatten subdomain tree into a list of names."""
    names: List[str] = []
    for node in nodes:
        if node.name:
            names.append(node.name)
        names.extend(_flatten_subdomain_names(node.children))
    return names


def _flatten_subdomain_nodes(
    nodes: List[SubdomainNode],
) -> List[Tuple[str, str, str]]:
    """Recursively flatten subdomain tree into (id, name, description) tuples."""
    result: List[Tuple[str, str, str]] = []
    for node in nodes:
        if node.name:
            result.append((node.id, node.name, node.description))
        result.extend(_flatten_subdomain_nodes(node.children))
    return result


def _backfill_scores_into_taxonomy(
    root_nodes: List[SubdomainNode],
    scored_subdomains: ScoredSubdomainList,
    persona_affinity: PersonaAffinityIndex,
) -> None:
    """Backfill priority_score and persona_affinity from scoring artifacts
    into the taxonomy SubdomainNode tree (mutates in-place)."""
    # Build lookup maps
    score_by_id = {s.subdomain_id: s for s in scored_subdomains.scores}
    # Build persona_affinity per subdomain: {subdomain_id: {persona_id: score}}
    affinity_by_sd: Dict[str, Dict[str, float]] = {}
    for pid, entries in persona_affinity.persona_entries.items():
        for entry in entries:
            if entry.affinity_score > 0:
                affinity_by_sd.setdefault(entry.subdomain_id, {})[pid] = entry.affinity_score

    def _walk(nodes: List[SubdomainNode]) -> None:
        for node in nodes:
            sc = score_by_id.get(node.id)
            if sc:
                node.priority_score = sc.composite_score
                node.priority_factors = dict(sc.signal_scores)
            aff = affinity_by_sd.get(node.id)
            if aff:
                node.persona_affinity = aff
            _walk(node.children)

    _walk(root_nodes)


def _load_persona_entries(
    backend: Any,
    effective_slug: str,
    company_slug: Optional[str] = None,
) -> List[Tuple[str, str]]:
    """Load (persona_id, persona_name) tuples from persona manifest.

    Falls back from effective_slug to company_slug.
    Returns list of tuples for active (fresh/stale) personas.
    """
    from core.research.audience_persona.storage import PersonaStorage

    for check_slug in filter(None, [effective_slug, company_slug]):
        # artifacts_root is only used for base_dir property; backend handles all I/O.
        ps = PersonaStorage(Path("artifacts"), check_slug, backend=backend)
        manifest = ps.read_manifest()
        if manifest.personas:
            break
    else:
        return []

    entries: List[Tuple[str, str]] = []
    for pid, entry in manifest.personas.items():
        if entry.status in ("fresh", "stale"):
            entries.append((pid, entry.persona_name or pid))
    return entries


def _build_persona_name_to_id(
    entries: List[Tuple[str, str]],
) -> Dict[str, str]:
    """Build persona_name → persona_id mapping from entries."""
    return {name: pid for pid, name in entries}


def _compute_distributions(
    assignments: List[TopicAssignment],
) -> Dict[str, Dict[str, int]]:
    """Compute distribution counts for buyer_stage, intent, and audience."""
    buyer_dist = Counter(a.buyer_stage.value for a in assignments)
    intent_dist = Counter(a.intent_type.value for a in assignments)
    audience_dist = Counter(a.audience_segment for a in assignments if a.audience_segment)
    return {
        "buyer_stage": dict(buyer_dist),
        "intent": dict(intent_dist),
        "audience": dict(audience_dist),
    }


# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------


async def run_topic_discovery_pipeline(
    input_data: TopicDiscoveryInput,
    *,
    task_id: Optional[str] = None,
    task_store: Optional[Any] = None,
    event_bus: Optional[Any] = None,
    artifacts_root: Optional[Path] = None,
    session_factory: Optional[Any] = None,
    run_id: Optional[Any] = None,
    company_id: Optional[Any] = None,
    langsmith_project: Optional[str] = None,
) -> TopicDiscoveryOutput:
    """Run the Topic Discovery pipeline (Pipeline A: Discovery).

    Produces a scored, prioritized taxonomy with persona affinity.
    Does NOT expand subdomains — use run_topic_expansion_pipeline() for that.
    """
    start_time = time.time()
    root = artifacts_root or Path("artifacts")
    slug = _resolve_slug(input_data)
    company_slug = slug
    effective_slug = _resolve_effective_slug(input_data)
    storage = TopicDiscoveryStorage(root, effective_slug)
    auto_approve_cps = set(input_data.auto_approve_checkpoints)
    max_rounds = input_data.max_expansion_rounds or settings.topic_discovery_max_expansion_rounds
    dedup_threshold = input_data.dedup_threshold or settings.topic_discovery_dedup_threshold
    timeout_s = settings.topic_discovery_source_timeout_s

    # Configure LiteLLM callbacks for LangSmith tracing
    configure_openrouter()

    # Tracing
    session_id = create_session(slug)
    _ls_project = langsmith_project or settings.topic_discovery_langsmith_project
    trace_span = create_trace(session_id, f"td-pipeline/{slug}", input_data={
        "company": input_data.company_name, "domain": input_data.domain,
    }, tags=["topic-discovery", "pipeline-a"], project_name=_ls_project)

    # SSE: pipeline start
    _emit(event_bus, task_id, "pipeline_start", {"pipeline": "topic_discovery"})
    _update_task(task_store, task_id, current_step="preflight")

    try:
        # =============================================================
        # Phase 0: Preflight — Load Context + Personas
        # =============================================================
        preflight_span = create_span(trace_span, "td-preflight")
        _emit(event_bus, task_id, "td_phase_start", {"phase": 0, "stage": "preflight"})

        # Load company context
        from core.storage import get_storage_backend

        _backend = get_storage_backend(root)
        company_md = read_company_context(_backend, effective_slug, company_slug) or ""

        if not company_md.strip():
            raise RuntimeError(
                f"Company context not found or empty at company_context/{effective_slug}.md "
                f"(also checked {company_slug}.md). Run the Knowledge Base pipeline first."
            )

        company_md = company_md[:_MAX_COMPANY_CONTEXT_CHARS]

        # Load persona profiles
        persona_mds = load_persona_profiles(_backend, effective_slug, company_slug)
        if not persona_mds:
            raise RuntimeError(
                f"No active persona profiles found for slug={effective_slug}. "
                f"Run the Audience Persona pipeline first."
            )

        persona_summaries = _build_persona_summaries(persona_mds)
        domain = input_data.domain or f"{company_slug}.com"

        # Load competitor landscape from KB (best-effort, not required)
        competitor_landscape = ""
        try:
            from core.models.knowledge_base import KBDocType
            from core.research.knowledge_base.storage import KBStorage

            _kb_storage = KBStorage(root, effective_slug, backend=_backend)
            _competitor_doc = _kb_storage.get_latest_version(
                KBDocType.COMPETITOR_REGISTRY,
            )
            if _competitor_doc:
                competitor_landscape = _competitor_doc.content_md or ""
        except Exception:
            logger.debug(
                "Could not load competitor landscape from KB for %s",
                effective_slug,
            )

        # Build persona_name_to_id early so Source B can resolve persona links
        persona_entries = _load_persona_entries(
            _backend, effective_slug, company_slug
        )
        persona_name_to_id = _build_persona_name_to_id(persona_entries)

        _emit(event_bus, task_id, "td_phase_complete", {"phase": 0})
        end_span(preflight_span, output={
            "personas_loaded": len(persona_mds),
            "has_company_context": bool(company_md),
        })

        # ── DB: Create/update TopicDiscoveryModel ──
        discovery_id = None
        taxonomy_db_id = None
        try:
            from core.topic_discovery.persistence import persist_td_discovery

            discovery_id = await persist_td_discovery(
                session_factory, run_id, company_id,
                effective_slug, domain,
                pipeline_run_id=run_id,
            )
        except Exception:
            logger.warning("TD persist_td_discovery failed, continuing", exc_info=True)

        # =============================================================
        # Phase 1 (S1): Multi-Source Subdomain Generation
        # =============================================================
        taxonomy_retry_count = 0
        user_feedback = ""

        while True:
            s1_span = create_span(trace_span, "td-s1-sources", input_data={
                "retry": taxonomy_retry_count,
            })
            _emit(event_bus, task_id, "td_phase_start", {
                "phase": 1, "stage": "s1_multi_source",
                "retry": taxonomy_retry_count,
            })
            _update_task(task_store, task_id, current_step="phase_1_multi_source")

            # Run sources A, B, C in parallel
            _revision = user_feedback or None
            source_a_task = run_source_a_company_brainstorm(
                company_md, max_rounds=max_rounds, timeout_s=timeout_s,
                revision_note=_revision, parent_span=s1_span,
                company_slug=company_slug,
            )
            source_b_task = run_source_b_persona_brainstorm(
                persona_summaries, company_md, max_rounds=max_rounds, timeout_s=timeout_s,
                revision_note=_revision,
                persona_name_to_id=persona_name_to_id,
                parent_span=s1_span,
                company_slug=company_slug,
            )

            # Source C: deep research competitive content landscape
            source_c_task = run_source_c_deep_research(
                company_md, competitor_landscape, domain,
                timeout_s=settings.topic_discovery_source_c_timeout_s,
                revision_note=_revision, parent_span=s1_span,
                company_slug=company_slug,
            )

            results_abc = await asyncio.gather(
                source_a_task, source_b_task, source_c_task,
                return_exceptions=True,
            )

            source_results: List[SourceResult] = []
            for i, res in enumerate(results_abc):
                source_name = ["source_a", "source_b", "source_c"][i]
                if isinstance(res, Exception):
                    logger.warning("Source %s failed (exception): %s", source_name, res)
                    source_results.append(SourceResult(
                        source=TDSource(source_name),
                        error=str(res),
                    ))
                else:
                    source_results.append(res)
                    if res.error:
                        logger.warning("Source %s returned error: %s", source_name, res.error)

                sr = source_results[-1]
                _emit(event_bus, task_id, "td_source_complete", {
                    "source": source_name,
                    "candidate_count": len(sr.candidates),
                    "has_error": sr.error is not None,
                    "error": sr.error,
                })

            # Source D: adversarial (sequential, uses existing subdomains)
            existing_names: List[str] = []
            for sr in source_results:
                existing_names.extend(c.name for c in sr.candidates if c.name)

            source_d_result = await run_source_d_adversarial(
                company_md, existing_names, max_rounds=max_rounds, timeout_s=timeout_s,
                revision_note=_revision, parent_span=s1_span,
                company_slug=company_slug,
            )
            source_results.append(source_d_result)
            if source_d_result.error:
                logger.warning("Source source_d returned error: %s", source_d_result.error)
            _emit(event_bus, task_id, "td_source_complete", {
                "source": "source_d",
                "candidate_count": len(source_d_result.candidates),
                "has_error": source_d_result.error is not None,
                "error": source_d_result.error,
            })

            # Write raw source results to storage
            for sr in source_results:
                await asyncio.to_thread(storage.write_source_result, sr.source, sr)

            # ── DB: Persist source results ──
            try:
                from core.topic_discovery.persistence import persist_td_source_results

                await persist_td_source_results(
                    session_factory, run_id, company_id,
                    discovery_id, source_results,
                )
            except Exception:
                logger.warning("TD persist_td_source_results failed, continuing", exc_info=True)

            _emit(event_bus, task_id, "td_phase_complete", {"phase": 1})
            end_span(s1_span, output={
                "sources_completed": len(source_results),
                "total_candidates": sum(len(sr.candidates) for sr in source_results),
            })

            # =============================================================
            # Phase 2 (S2): Exhaustiveness Evaluation & Merge
            # =============================================================
            s2_span = create_span(trace_span, "td-s2-merge")
            _emit(event_bus, task_id, "td_phase_start", {
                "phase": 2, "stage": "s2_merge",
            })
            _update_task(task_store, task_id, current_step="phase_2_merge")

            # Collect all candidates
            all_candidates = []
            for sr in source_results:
                all_candidates.extend(sr.candidates)

            if not all_candidates:
                # Surface individual source errors for debugging
                source_errors = [
                    f"{sr.source.value}: {sr.error}"
                    for sr in source_results
                    if sr.error
                ]
                err_detail = "; ".join(source_errors) if source_errors else "no errors captured"
                raise RuntimeError(
                    f"All sources returned 0 candidates. Source errors: [{err_detail}]"
                )

            # Deduplicate via embeddings (with cluster metadata for coverage)
            dedup_result = await deduplicate_subdomains_with_clusters(
                all_candidates, threshold=dedup_threshold, parent_span=s2_span,
            )
            deduped = dedup_result.kept
            logger.info(
                "TD/%s: dedup %d → %d candidates",
                effective_slug, len(all_candidates), len(deduped),
            )

            # Coverage metrics (cluster-based overlap + semantic frequency)
            coverage = compute_all_coverage_metrics(
                source_results, dedup_result=dedup_result,
            )
            await asyncio.to_thread(storage.write_coverage, coverage)

            # Log coverage metrics
            coverage_span = create_span(s2_span, "td-s2-coverage")
            log_score(coverage_span, "aggregate_coverage", coverage.aggregate_sample_coverage)
            log_score(coverage_span, "chao1_lower_bound", coverage.chao1_lower_bound)
            end_span(coverage_span, output={
                "aggregate_coverage": coverage.aggregate_sample_coverage,
            })

            # Unified S2: hierarchy + priority scoring + persona affinity
            deduped_names = [c.name for c in deduped if c.name]
            persona_profiles_for_s2: List[Tuple[str, str]] = []
            for (pid, _pname), md in zip(persona_entries, persona_mds):
                persona_profiles_for_s2.append((pid, md))
            taxonomy = await run_unified_hierarchy_and_scoring(
                subdomains=deduped_names,
                company_domain=domain,
                company_context=company_md,
                persona_profiles=persona_profiles_for_s2,
                timeout_s=600.0,
                parent_span=s2_span,
                company_slug=company_slug,
            )

            # Enrich taxonomy with coverage data
            taxonomy.coverage_score = coverage.aggregate_sample_coverage
            taxonomy.chao1_estimate = coverage.chao1_lower_bound
            taxonomy.capture_recapture_est = coverage.model_dump(mode="json")

            # Write taxonomy
            tax_version = await asyncio.to_thread(storage.write_taxonomy, taxonomy)

            _emit(event_bus, task_id, "td_phase_complete", {
                "phase": 2,
                "total_subdomains": taxonomy.total_subdomains,
                "coverage_score": coverage.aggregate_sample_coverage,
            })
            end_span(s2_span, output={"total_subdomains": taxonomy.total_subdomains})

            # =============================================================
            # HITL-1: Taxonomy Approval
            # =============================================================
            hitl1_span = create_span(trace_span, "td-hitl-1", input_data={
                "auto_approve": 1 in auto_approve_cps,
            })
            set_current_span(hitl1_span)
            _emit(event_bus, task_id, "td_phase_start", {
                "phase": "hitl_1", "stage": "taxonomy_review",
            })
            _update_task(task_store, task_id, current_step="hitl_1_taxonomy_review")

            taxonomy_review_graph = build_td_taxonomy_review_graph()
            hitl1_state = {
                "taxonomy": taxonomy.model_dump(mode="json"),
                "coverage_metrics": coverage.model_dump(mode="json"),
                "checkpoint": 1,
                "auto_approve": 1 in auto_approve_cps,
            }

            hitl1_result = await run_td_hitl_checkpoint(
                taxonomy_review_graph, hitl1_state,
                thread_id=f"td-hitl-1-{slug}-{uuid.uuid4().hex[:8]}",
                task_store=task_store, event_bus=event_bus, task_id=task_id,
                stage_name="td_taxonomy_review",
                parent_span=hitl1_span,
            )

            decision = hitl1_result.get("batch_decision", "approve")
            log_score(hitl1_span, "decision", decision)
            end_span(hitl1_span, output={
                "decision": decision, "retry_count": taxonomy_retry_count,
            })

            if decision == "retry":
                taxonomy_retry_count += 1
                user_feedback = hitl1_result.get("user_feedback", "")
                if taxonomy_retry_count >= _MAX_TAXONOMY_RETRIES:
                    logger.warning(
                        "TD/%s: max taxonomy retries (%d) reached, approving as-is",
                        effective_slug, _MAX_TAXONOMY_RETRIES,
                    )
                    # H3: Explicitly approve the last-generated taxonomy
                    taxonomy.status = TopicDiscoveryStatus.approved
                    tax_version = await asyncio.to_thread(
                        storage.write_taxonomy, taxonomy,
                    )
                    break
                logger.info(
                    "TD/%s: taxonomy retry %d/%d (feedback: %s)",
                    effective_slug, taxonomy_retry_count, _MAX_TAXONOMY_RETRIES,
                    user_feedback[:100],
                )
                continue  # loop back to S1
            else:
                # approve or modify → use approved_taxonomy
                approved_tax_raw = hitl1_result.get("approved_taxonomy", {})
                if approved_tax_raw:
                    taxonomy = TaxonomyTree.model_validate(approved_tax_raw)
                    taxonomy.status = TopicDiscoveryStatus.approved
                    tax_version = await asyncio.to_thread(
                        storage.write_taxonomy, taxonomy,
                    )
                break

        _emit(event_bus, task_id, "td_phase_complete", {
            "phase": "hitl_1", "decision": decision,
        })

        # ── DB: Persist approved taxonomy ──
        try:
            from core.topic_discovery.persistence import persist_td_taxonomy

            taxonomy_db_id = await persist_td_taxonomy(
                session_factory, run_id, company_id,
                discovery_id, taxonomy, tax_version,
            )
        except Exception:
            logger.warning("TD persist_td_taxonomy failed, continuing", exc_info=True)

        # =============================================================
        # Phase 2.5: Post-Processing — Source Confidence Blend (trial)
        # =============================================================
        # LLM scores (priority_factors + persona_affinity) are already on
        # taxonomy nodes from the unified S2 call.  We only add a lightweight
        # source_confidence adjustment and produce the ScoredSubdomainList +
        # PersonaAffinityIndex artifacts for Pipeline B compatibility.
        scoring_span = create_span(trace_span, "td-scoring")
        _emit(event_bus, task_id, "td_phase_start", {
            "phase": "2.5", "stage": "score_blending",
        })
        _update_task(task_store, task_id, current_step="phase_2_5_blending")

        # Compute source_confidence per node (lightweight, no embeddings)
        source_scores = compute_source_confidence_scores(taxonomy)

        # Blend LLM composite with source_confidence
        apply_source_confidence_adjustment(taxonomy, source_scores)
        logger.info(
            "TD/%s: blended LLM scores with source_confidence for %d nodes",
            effective_slug, len(source_scores),
        )

        # Build ScoredSubdomainList from taxonomy (Pipeline B compatibility)
        scored_subdomains = build_scored_subdomain_list_from_taxonomy(taxonomy)
        scoring_version = await asyncio.to_thread(
            storage.write_scoring, scored_subdomains
        )

        # Build PersonaAffinityIndex from taxonomy (Pipeline B compatibility)
        persona_affinity = build_persona_affinity_index_from_taxonomy(taxonomy)
        affinity_version = await asyncio.to_thread(
            storage.write_persona_affinity, persona_affinity
        )

        # Re-persist taxonomy with blended priority_score
        await asyncio.to_thread(
            storage.write_taxonomy, taxonomy, taxonomy.version
        )

        # ── DB: Re-persist taxonomy with scoring data on nodes ──
        try:
            from core.topic_discovery.persistence import persist_td_taxonomy as _re_persist_tax

            await _re_persist_tax(
                session_factory, run_id, company_id,
                discovery_id, taxonomy, tax_version,
            )
        except Exception:
            logger.warning("TD re-persist_td_taxonomy (post-scoring) failed, continuing", exc_info=True)

        # ── DB: Persist persona affinity index ──
        try:
            from core.topic_discovery.persistence import persist_td_persona_affinity

            await persist_td_persona_affinity(
                session_factory, run_id, company_id,
                discovery_id, persona_affinity, affinity_version,
            )
        except Exception:
            logger.warning("TD persist_td_persona_affinity failed, continuing", exc_info=True)

        # ── DB: Persist scoring + affinity version metadata ──
        try:
            from core.topic_discovery.persistence import persist_td_scoring_metadata

            await persist_td_scoring_metadata(
                session_factory, discovery_id,
                scoring_version, affinity_version,
            )
        except Exception:
            logger.warning("TD persist_td_scoring_metadata failed, continuing", exc_info=True)

        _emit(event_bus, task_id, "td_phase_complete", {
            "phase": "2.5",
            "total_scored": scored_subdomains.total_scored,
            "total_personas": persona_affinity.total_personas,
        })
        end_span(scoring_span, output={
            "total_scored": scored_subdomains.total_scored,
        })

        # =============================================================
        # Finalize: Discovery Complete
        # =============================================================
        finalize_span = create_span(trace_span, "td-finalize")
        _emit(event_bus, task_id, "td_phase_start", {"phase": "finalize", "stage": "discovery_finalize"})
        _update_task(task_store, task_id, current_step="finalize_discovery")

        manifest = await asyncio.to_thread(storage.read_manifest)
        manifest.slug = company_slug
        manifest.effective_slug = effective_slug
        manifest.company_name = input_data.company_name
        manifest.domain_name = domain
        manifest.status = TopicDiscoveryStatus.discovery_complete
        manifest.taxonomy_version = tax_version
        manifest.matrix_version = 0
        manifest.scoring_version = scoring_version
        manifest.persona_affinity_version = affinity_version
        manifest.last_updated = datetime.now(timezone.utc).isoformat()
        manifest.discovery_completed_at = datetime.now(timezone.utc).isoformat()
        manifest.source_results_written = [sr.source.value for sr in source_results]
        await asyncio.to_thread(storage.write_manifest, manifest)

        # ── DB Persistence (fire-and-forget) ──
        try:
            from core.topic_discovery.persistence import persist_td_status_update

            await persist_td_status_update(session_factory, discovery_id, "discovery_complete")
        except Exception:
            logger.warning("TD persist_td_status_update failed, continuing", exc_info=True)

        # ── DB: Persist manifest metadata ──
        try:
            if session_factory is not None and discovery_id is not None:
                from core.db.repositories.topic_discovery_repo import TopicDiscoveryRepository

                async with session_factory() as _msess:
                    _mrepo = TopicDiscoveryRepository(_msess)
                    await _mrepo.update(discovery_id, manifest_json={
                        "source_results_written": manifest.source_results_written,
                        "expanded_subdomain_ids": getattr(manifest, "expanded_subdomain_ids", []),
                        "last_expansion_task_id": getattr(manifest, "last_expansion_task_id", None),
                    })
                    await _msess.commit()
        except Exception:
            logger.warning("TD manifest_json DB persist failed, continuing", exc_info=True)

        try:
            from core.research.persistence import persist_pipeline_run_complete

            await persist_pipeline_run_complete(
                session_factory, run_id,
                {
                    "taxonomy_version": tax_version,
                    "total_subdomains": taxonomy.total_subdomains,
                },
            )
        except Exception:
            logger.warning("TD DB persistence failed, continuing", exc_info=True)

        output = TopicDiscoveryOutput(
            slug=company_slug,
            effective_slug=effective_slug,
            company_name=input_data.company_name,
            taxonomy=taxonomy,
            matrix=None,
            coverage=coverage,
            scored_subdomains=scored_subdomains,
            persona_affinity=persona_affinity,
            manifest=manifest,
            taxonomy_version=tax_version,
            matrix_version=0,
            total_execution_time_s=time.time() - start_time,
            status=TopicDiscoveryStatus.discovery_complete,
        )

        _emit(event_bus, task_id, "completed", {"pipeline": "topic_discovery"})
        _emit(event_bus, task_id, "td_phase_complete", {"phase": "finalize"})
        end_span(finalize_span, output={"taxonomy_version": tax_version})
        end_span(trace_span, output={
            "total_subdomains": taxonomy.total_subdomains,
            "coverage_score": coverage.aggregate_sample_coverage,
        })
        flush()
        return output

    except Exception as exc:
        logger.exception("TD pipeline failed for %s: %s", slug, exc)
        _emit(event_bus, task_id, "failed", {"error": str(exc)})
        end_span(trace_span, error=str(exc))
        flush()
        raise


# ---------------------------------------------------------------------------
# Pipeline B: Topic Expansion
# ---------------------------------------------------------------------------


def _update_expansion_status(
    root_nodes: List[SubdomainNode],
    expanded_ids: set,
    failed_ids: set,
) -> None:
    """Walk taxonomy tree and set expansion_status for expanded/failed nodes."""
    for node in root_nodes:
        if node.id in expanded_ids:
            node.expansion_status = "expanded"
        elif node.id in failed_ids:
            node.expansion_status = "failed"
        _update_expansion_status(node.children, expanded_ids, failed_ids)


async def run_topic_expansion_pipeline(
    input_data: TopicExpansionInput,
    *,
    task_id: Optional[str] = None,
    task_store: Optional[Any] = None,
    event_bus: Optional[Any] = None,
    artifacts_root: Optional[Path] = None,
    session_factory: Optional[Any] = None,
    run_id: Optional[Any] = None,
    company_id: Optional[Any] = None,
    langsmith_project: Optional[str] = None,
) -> TopicExpansionOutput:
    """Run the Topic Expansion pipeline (Pipeline B).

    Expands selected subdomains into a buyer_stage x intent_type matrix.
    Requires Pipeline A (discovery) to have completed first.
    Re-entrant: can be called multiple times with different subdomains.
    """
    start_time = time.time()
    root = artifacts_root or Path("artifacts")
    slug = _resolve_slug(input_data)
    company_slug = slug
    effective_slug = input_data.effective_slug or _resolve_effective_slug(input_data)

    _emit(event_bus, task_id, "pipeline_start", {
        "pipeline": "topic_expansion",
        "company_slug": company_slug,
        "effective_slug": effective_slug,
    })

    configure_openrouter()
    session_id = create_session(f"td-expansion-{effective_slug}")
    _ls_project = langsmith_project or settings.topic_discovery_langsmith_project
    trace_span = create_trace(
        session_id,
        f"td-expansion/{effective_slug}",
        input_data={"effective_slug": effective_slug, "subdomain_ids": input_data.subdomain_ids},
        tags=["topic-discovery", "expansion"],
        project_name=_ls_project,
    )

    try:
        # =============================================================
        # Preflight: Load Pipeline A artifacts
        # =============================================================
        exp_preflight_span = create_span(trace_span, "td-exp-preflight")
        _emit(event_bus, task_id, "td_phase_start", {"phase": "preflight", "stage": "expansion_preflight"})
        _update_task(task_store, task_id, current_step="expansion_preflight")

        storage = TopicDiscoveryStorage(root, effective_slug)
        manifest = await asyncio.to_thread(storage.read_manifest)

        if manifest.taxonomy_version == 0 or manifest.scoring_version == 0:
            raise RuntimeError(
                f"Topic Discovery has not completed for '{effective_slug}'. "
                "Run the discovery pipeline first."
            )

        # Load taxonomy
        tax_version = input_data.taxonomy_version or manifest.taxonomy_version
        taxonomy = await asyncio.to_thread(storage.read_taxonomy, tax_version)
        if taxonomy is None:
            raise RuntimeError(f"Taxonomy v{tax_version} not found for '{effective_slug}'.")

        # Load scored subdomains + persona affinity
        scored_subdomains = await asyncio.to_thread(
            storage.read_scoring, manifest.scoring_version,
        )
        persona_affinity = await asyncio.to_thread(
            storage.read_persona_affinity, manifest.persona_affinity_version,
        )

        # Load company context + persona profiles (needed for expansion prompts)
        domain = input_data.domain or f"{company_slug}.com"
        from core.storage import get_storage_backend
        backend = get_storage_backend(root)

        company_md = await asyncio.to_thread(
            read_company_context, backend, effective_slug, company_slug,
        )
        if not company_md:
            company_md = ""
        company_md = company_md[:_MAX_COMPANY_CONTEXT_CHARS]

        persona_mds = await asyncio.to_thread(
            load_persona_profiles, backend, effective_slug, company_slug,
        )

        # Build persona_mds_by_id for expansion context
        persona_entries = _load_persona_entries(backend, effective_slug, company_slug)
        persona_mds_by_id: Dict[str, str] = {}
        if persona_entries and persona_mds:
            for idx, (pid, _pname) in enumerate(persona_entries):
                if idx < len(persona_mds):
                    persona_mds_by_id[pid] = persona_mds[idx]

        # Validate subdomain selection
        if not input_data.subdomain_ids:
            raise ValueError("subdomain_ids must be non-empty for topic expansion.")

        all_subdomain_tuples = _flatten_subdomain_nodes(taxonomy.root_nodes)
        valid_ids = {sid for sid, _, _ in all_subdomain_tuples}
        unknown_ids = set(input_data.subdomain_ids) - valid_ids
        if unknown_ids:
            logger.warning(
                "TD-Expansion/%s: unknown subdomain IDs will be skipped: %s",
                effective_slug, unknown_ids,
            )

        selected_subdomain_ids = [
            sid for sid in input_data.subdomain_ids if sid in valid_ids
        ]
        if not selected_subdomain_ids:
            raise ValueError("No valid subdomain IDs provided for expansion.")

        _emit(event_bus, task_id, "td_phase_complete", {
            "phase": "preflight",
            "subdomains_selected": len(selected_subdomain_ids),
        })
        end_span(exp_preflight_span, output={
            "subdomains_selected": len(selected_subdomain_ids),
        })

        # =============================================================
        # Phase 3 (S3): On-Demand Expansion
        # =============================================================
        s3_span = create_span(trace_span, "td-s3-expansion", input_data={
            "subdomains": len(selected_subdomain_ids),
        })
        _emit(event_bus, task_id, "td_phase_start", {
            "phase": 3, "stage": "s3_expansion",
        })
        _update_task(task_store, task_id, current_step="phase_3_expansion")

        auto_approve_cps = set(input_data.auto_approve_checkpoints or [])

        buyer_stages = [s.value for s in BuyerStage]
        intent_types = [t.value for t in IntentType]
        audience_segments: List[Tuple[str, str]] = persona_entries or [("general", "General")]

        # Filter to selected subdomains
        selected_set = set(selected_subdomain_ids)
        selected_tuples = [
            (sid, sname, sdesc)
            for sid, sname, sdesc in all_subdomain_tuples
            if sid in selected_set
        ]

        max_expand = settings.topic_discovery_max_subdomains_to_expand
        if len(selected_tuples) > max_expand:
            logger.warning(
                "TD-Expansion/%s: selected %d subdomains, capping at %d",
                effective_slug, len(selected_tuples), max_expand,
            )
            selected_tuples = selected_tuples[:max_expand]

        # Optional persona context for focused expansion
        persona_filter = input_data.persona_filter or ""
        expansion_persona_ctx: Optional[str] = None
        if persona_filter and persona_filter in persona_mds_by_id:
            expansion_persona_ctx = persona_mds_by_id[persona_filter][:500]

        # Expand each selected subdomain
        all_assignments: List[TopicAssignment] = []
        semaphore = asyncio.Semaphore(settings.topic_discovery_max_concurrent_sources)
        expanded_ids: set = set()
        failed_ids: set = set()

        async def _expand_subdomain(
            sd_id: str, sd_name: str, sd_desc: str,
        ) -> List[TopicAssignment]:
            async with semaphore:
                assignments = await run_subdomain_expansion(
                    subdomain_name=sd_name,
                    subdomain_description=sd_desc,
                    buyer_stages=buyer_stages,
                    intent_types=intent_types,
                    audience_segments=audience_segments,
                    company_context=company_md,
                    persona_context=expansion_persona_ctx,
                    timeout_s=settings.topic_discovery_expansion_timeout_s,
                    parent_span=s3_span,
                    company_slug=company_slug,
                )
            for a in assignments:
                a.subdomain_id = sd_id
            return assignments

        expansion_tasks = [
            _expand_subdomain(sid, sname, sdesc)
            for sid, sname, sdesc in selected_tuples
        ]
        expansion_results = await asyncio.gather(
            *expansion_tasks, return_exceptions=True,
        )

        for i, res in enumerate(expansion_results):
            sd_id = selected_tuples[i][0]
            if isinstance(res, Exception):
                logger.warning(
                    "TD-Expansion/%s: expansion failed for '%s': %s(%s)",
                    effective_slug, selected_tuples[i][1],
                    type(res).__name__, res,
                )
                failed_ids.add(sd_id)
            else:
                all_assignments.extend(res)
                expanded_ids.add(sd_id)

        # Compute topic priority scores
        score_lookup: Dict[str, Any] = {}
        if scored_subdomains:
            for sc in scored_subdomains.scores:
                score_lookup[sc.subdomain_id] = sc

        for assignment in all_assignments:
            sd_score = score_lookup.get(assignment.subdomain_id)
            if sd_score:
                priority, factors = compute_topic_priority(
                    assignment.buyer_stage.value,
                    assignment.intent_type.value,
                    sd_score.composite_score,
                )
                assignment.priority_score = priority
                assignment.priority_factors = factors

        # ── Merge with previous matrix (re-entrant accumulation) ──
        # Keep assignments from subdomains NOT touched in this run;
        # only successful expansions replace previous assignments.
        previous_matrix = await asyncio.to_thread(storage.get_latest_matrix)
        if previous_matrix and previous_matrix.assignments:
            previous_kept = [
                a for a in previous_matrix.assignments
                if a.subdomain_id not in expanded_ids
            ]
            all_assignments = previous_kept + all_assignments

        # Build matrix
        distributions = _compute_distributions(all_assignments)
        matrix = TopicAssignmentMatrix(
            status=TopicDiscoveryStatus.draft,
            assignments=all_assignments,
            total_assignments=len(all_assignments),
            total_relevant_cells=len(all_assignments),
            total_irrelevant_cells=0,
            buyer_stage_distribution=distributions["buyer_stage"],
            intent_distribution=distributions["intent"],
            audience_distribution=distributions["audience"],
        )

        mat_version = await asyncio.to_thread(storage.write_matrix, matrix)

        # Update expansion_status on taxonomy nodes
        _update_expansion_status(taxonomy.root_nodes, expanded_ids, failed_ids)
        await asyncio.to_thread(storage.write_taxonomy, taxonomy, taxonomy.version)

        _emit(event_bus, task_id, "td_phase_complete", {
            "phase": 3,
            "total_assignments": len(all_assignments),
            "subdomains_expanded": len(expanded_ids),
            "subdomains_failed": len(failed_ids),
        })
        log_score(s3_span, "total_expanded", float(len(expanded_ids)))
        log_score(s3_span, "total_assignments", float(len(all_assignments)))
        end_span(s3_span, output={
            "expanded": len(expanded_ids), "assignments": len(all_assignments),
        })

        # =============================================================
        # HITL-2: Matrix Approval
        # =============================================================
        hitl2_span = create_span(trace_span, "td-hitl-2", input_data={
            "auto_approve": 2 in auto_approve_cps,
        })
        set_current_span(hitl2_span)
        _emit(event_bus, task_id, "td_phase_start", {
            "phase": "hitl_2", "stage": "matrix_review",
        })
        _update_task(task_store, task_id, current_step="hitl_2_matrix_review")

        matrix_review_graph = build_td_matrix_review_graph()
        hitl2_state = {
            "matrix": matrix.model_dump(mode="json"),
            "checkpoint": 2,
            "auto_approve": 2 in auto_approve_cps,
        }

        hitl2_result = await run_td_hitl_checkpoint(
            matrix_review_graph, hitl2_state,
            thread_id=f"td-hitl-2-{slug}-{uuid.uuid4().hex[:8]}",
            task_store=task_store, event_bus=event_bus, task_id=task_id,
            stage_name="td_matrix_review",
            parent_span=hitl2_span,
        )

        mat_decision = hitl2_result.get("batch_decision", "approve")
        log_score(hitl2_span, "decision", mat_decision)
        end_span(hitl2_span, output={"decision": mat_decision})
        approved_mat_raw = hitl2_result.get("approved_matrix", {})
        if approved_mat_raw:
            matrix = TopicAssignmentMatrix.model_validate(approved_mat_raw)
            matrix.status = TopicDiscoveryStatus.approved
            mat_version = await asyncio.to_thread(storage.write_matrix, matrix)

        _emit(event_bus, task_id, "td_phase_complete", {
            "phase": "hitl_2", "decision": mat_decision,
        })

        # ── DB: Persist approved assignments ──
        discovery_id: Optional[Any] = None
        taxonomy_db_id: Optional[Any] = None
        try:
            from core.topic_discovery.persistence import (
                persist_td_assignments,
                persist_td_discovery,
            )

            discovery_id = await persist_td_discovery(
                session_factory, run_id, company_id,
                effective_slug, domain,
            )
            await persist_td_assignments(
                session_factory, run_id, company_id,
                discovery_id, matrix, mat_version,
                taxonomy_id=taxonomy_db_id,
            )
        except Exception:
            logger.warning("TD-Expansion persist failed, continuing", exc_info=True)

        # =============================================================
        # Finalize
        # =============================================================
        exp_finalize_span = create_span(trace_span, "td-exp-finalize")
        _emit(event_bus, task_id, "td_phase_start", {"phase": "finalize", "stage": "expansion_finalize"})
        _update_task(task_store, task_id, current_step="finalize_expansion")

        manifest = await asyncio.to_thread(storage.read_manifest)
        manifest.status = TopicDiscoveryStatus.approved
        manifest.matrix_version = mat_version
        manifest.last_updated = datetime.now(timezone.utc).isoformat()
        manifest.last_expansion_task_id = task_id or ""
        # Accumulate expanded IDs (re-entrant)
        existing_expanded = set(manifest.expanded_subdomain_ids)
        existing_expanded.update(expanded_ids)
        manifest.expanded_subdomain_ids = sorted(existing_expanded)
        await asyncio.to_thread(storage.write_manifest, manifest)

        try:
            from core.topic_discovery.persistence import persist_td_status_update

            await persist_td_status_update(session_factory, discovery_id, "approved")
        except Exception:
            logger.warning("TD-Expansion persist_td_status_update failed", exc_info=True)

        output = TopicExpansionOutput(
            slug=company_slug,
            effective_slug=effective_slug,
            matrix=matrix,
            matrix_version=mat_version,
            subdomains_expanded=len(expanded_ids),
            subdomains_failed=len(failed_ids),
            total_assignments=len(all_assignments),
            total_execution_time_s=time.time() - start_time,
            status=TopicDiscoveryStatus.approved,
        )

        _emit(event_bus, task_id, "completed", {"pipeline": "topic_expansion"})
        _emit(event_bus, task_id, "td_phase_complete", {"phase": "finalize"})
        end_span(exp_finalize_span, output={"matrix_version": mat_version})
        end_span(trace_span, output={
            "subdomains_expanded": len(expanded_ids),
            "total_assignments": len(all_assignments),
        })
        flush()
        return output

    except Exception as exc:
        logger.exception("TD-Expansion pipeline failed for %s: %s", effective_slug, exc)
        _emit(event_bus, task_id, "failed", {"error": str(exc)})
        end_span(trace_span, error=str(exc))
        flush()
        raise
