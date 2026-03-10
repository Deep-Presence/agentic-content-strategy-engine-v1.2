"""Topic Discovery pipeline orchestrator — S1→S2→HITL1→S3→HITL2.

Execution flow:
  Phase 0: Preflight (load company context + persona profiles, validate prereqs)
  Phase 1 (S1): Multi-Source Subdomain Generation (A+B+C parallel, then D sequential)
  Phase 2 (S2): Exhaustiveness Evaluation & Merge (dedup → coverage metrics → hierarchy)
  ── HITL-1: Taxonomy approval (approve/modify/retry, max 2 retries) ──
  Phase 3 (S3): Dimensionality Expansion (relevance filter → topic generation)
  ── HITL-2: Matrix approval (approve/modify) ──
  Phase 4: Finalize (update manifest, emit completed)
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
from typing import Any, Dict, List, Optional

from core.config.settings import settings
from core.content_engine.llm_client import configure_litellm_callbacks
from core.models.topic_discovery import (
    BuyerStage,
    CaptureRecaptureResult,
    IntentType,
    RelevanceCell,
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
)
from core.research.audience_persona.storage import PersonaStorage
from core.shared_tools.tracing import (
    create_session,
    create_trace,
    end_span,
    flush,
)
from core.topic_discovery.agents import (
    compute_all_coverage_metrics,
    deduplicate_subdomains,
    run_hierarchy_construction,
    run_relevance_filtering,
    run_source_a_company_brainstorm,
    run_source_b_persona_brainstorm,
    run_source_c_competitor_sitemaps,
    run_source_d_adversarial,
    run_topic_generation,
)
from core.topic_discovery.graph import (
    build_td_matrix_review_graph,
    build_td_taxonomy_review_graph,
    run_td_hitl_checkpoint,
)
from core.topic_discovery.storage import TopicDiscoveryStorage

logger = logging.getLogger(__name__)

_MAX_COMPANY_CONTEXT_CHARS = 60_000
_MAX_TAXONOMY_RETRIES = 2


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _resolve_slug(input_data: TopicDiscoveryInput) -> str:
    """Derive company slug from input."""
    if input_data.company_slug:
        return input_data.company_slug
    slug = input_data.company_name.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug).strip("-")
    return slug


def _resolve_effective_slug(input_data: TopicDiscoveryInput) -> str:
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


async def _load_persona_profiles(
    artifacts_root: Path,
    effective_slug: str,
    company_slug: str,
) -> List[str]:
    """Load active persona profiles from PersonaStorage.

    Returns list of markdown strings (one per persona).
    Follows effective_slug → company_slug fallback.
    """
    for check_slug in (effective_slug, company_slug):
        persona_storage = PersonaStorage(artifacts_root, check_slug)
        manifest = persona_storage.read_manifest()
        if manifest.personas:
            break
    else:
        return []

    persona_mds: List[str] = []
    for pid, entry in manifest.personas.items():
        if entry.status not in ("fresh", "stale"):
            continue
        version_data = persona_storage.get_latest_version(pid)
        if version_data and version_data.get("content_md"):
            persona_mds.append(version_data["content_md"])

    return persona_mds


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
) -> TopicDiscoveryOutput:
    """Run the Topic Discovery pipeline.

    Coordinates a 5-stage pipeline (S1→S2→HITL1→S3→HITL2)
    producing an exhaustive taxonomy of content opportunities.
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
    configure_litellm_callbacks()

    # Tracing
    session_id = create_session(slug)
    trace_span = create_trace(session_id, f"td-pipeline/{slug}", input_data={
        "company": input_data.company_name, "domain": input_data.domain,
    })

    # SSE: pipeline start
    _emit(event_bus, task_id, "pipeline_start", {"pipeline": "topic_discovery"})
    _update_task(task_store, task_id, current_step="preflight")

    try:
        # =============================================================
        # Phase 0: Preflight — Load Context + Personas
        # =============================================================
        _emit(event_bus, task_id, "td_phase_start", {"phase": 0, "stage": "preflight"})

        # Load company context
        company_md = ""
        for check_slug in (effective_slug, company_slug):
            ctx_path = root / "company_context" / f"{check_slug}.md"
            if ctx_path.exists():
                company_md = await asyncio.to_thread(ctx_path.read_text, encoding="utf-8")
                break

        if not company_md.strip():
            raise RuntimeError(
                f"Company context not found or empty at company_context/{effective_slug}.md "
                f"(also checked {company_slug}.md). Run the Knowledge Base pipeline first."
            )

        company_md = company_md[:_MAX_COMPANY_CONTEXT_CHARS]

        # Load persona profiles
        persona_mds = await _load_persona_profiles(root, effective_slug, company_slug)
        if not persona_mds:
            raise RuntimeError(
                f"No active persona profiles found for slug={effective_slug}. "
                f"Run the Audience Persona pipeline first."
            )

        persona_summaries = _build_persona_summaries(persona_mds)
        domain = input_data.domain or f"{company_slug}.com"

        _emit(event_bus, task_id, "td_phase_complete", {"phase": 0})

        # =============================================================
        # Phase 1 (S1): Multi-Source Subdomain Generation
        # =============================================================
        taxonomy_retry_count = 0
        user_feedback = ""

        while True:
            _emit(event_bus, task_id, "td_phase_start", {
                "phase": 1, "stage": "s1_multi_source",
                "retry": taxonomy_retry_count,
            })
            _update_task(task_store, task_id, current_step="phase_1_multi_source")

            # Run sources A, B, C in parallel
            _revision = user_feedback or None
            source_a_task = run_source_a_company_brainstorm(
                company_md, max_rounds=max_rounds, timeout_s=timeout_s,
                revision_note=_revision,
            )
            source_b_task = run_source_b_persona_brainstorm(
                persona_summaries, company_md, max_rounds=max_rounds, timeout_s=timeout_s,
                revision_note=_revision,
            )

            # Source C: competitor sitemaps (placeholder data for now)
            sitemap_data = ""  # TODO: fetch sitemaps from seed_urls
            source_c_task = run_source_c_competitor_sitemaps(
                sitemap_data, domain, timeout_s=timeout_s,
                revision_note=_revision,
            )

            results_abc = await asyncio.gather(
                source_a_task, source_b_task, source_c_task,
                return_exceptions=True,
            )

            source_results: List[SourceResult] = []
            for i, res in enumerate(results_abc):
                source_name = ["source_a", "source_b", "source_c"][i]
                if isinstance(res, Exception):
                    logger.warning("Source %s failed: %s", source_name, res)
                    source_results.append(SourceResult(
                        source=TDSource(source_name),
                        error=str(res),
                    ))
                else:
                    source_results.append(res)
                _emit(event_bus, task_id, "td_source_complete", {
                    "source": source_name,
                    "candidate_count": len(res.candidates) if not isinstance(res, Exception) else 0,
                    "has_error": isinstance(res, Exception) or (hasattr(res, "error") and res.error is not None),
                })

            # Source D: adversarial (sequential, uses existing subdomains)
            existing_names: List[str] = []
            for sr in source_results:
                existing_names.extend(c.name for c in sr.candidates if c.name)

            source_d_result = await run_source_d_adversarial(
                company_md, existing_names, max_rounds=max_rounds, timeout_s=timeout_s,
                revision_note=_revision,
            )
            source_results.append(source_d_result)
            _emit(event_bus, task_id, "td_source_complete", {
                "source": "source_d",
                "candidate_count": len(source_d_result.candidates),
                "has_error": source_d_result.error is not None,
            })

            # Write raw source results to storage
            for sr in source_results:
                await asyncio.to_thread(storage.write_source_result, sr.source, sr)

            _emit(event_bus, task_id, "td_phase_complete", {"phase": 1})

            # =============================================================
            # Phase 2 (S2): Exhaustiveness Evaluation & Merge
            # =============================================================
            _emit(event_bus, task_id, "td_phase_start", {
                "phase": 2, "stage": "s2_merge",
            })
            _update_task(task_store, task_id, current_step="phase_2_merge")

            # Collect all candidates
            all_candidates = []
            for sr in source_results:
                all_candidates.extend(sr.candidates)

            if not all_candidates:
                raise RuntimeError(
                    "All 4 sources returned 0 candidates. Check LLM availability."
                )

            # Deduplicate via embeddings
            deduped = await deduplicate_subdomains(
                all_candidates, threshold=dedup_threshold,
            )
            logger.info(
                "TD/%s: dedup %d → %d candidates",
                effective_slug, len(all_candidates), len(deduped),
            )

            # Coverage metrics
            coverage = compute_all_coverage_metrics(source_results)
            await asyncio.to_thread(storage.write_coverage, coverage)

            # Hierarchy construction
            deduped_names = [c.name for c in deduped if c.name]
            taxonomy = await run_hierarchy_construction(deduped_names, domain)

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

            # =============================================================
            # HITL-1: Taxonomy Approval
            # =============================================================
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
            )

            decision = hitl1_result.get("batch_decision", "approve")

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

        # =============================================================
        # Phase 3 (S3): Dimensionality Expansion
        # =============================================================
        _emit(event_bus, task_id, "td_phase_start", {
            "phase": 3, "stage": "s3_expansion",
        })
        _update_task(task_store, task_id, current_step="phase_3_expansion")

        # Define dimensions
        buyer_stages = [s.value for s in BuyerStage]
        intent_types = [t.value for t in IntentType]

        # Extract audience segments from personas
        audience_segments = [f"Persona {i+1}" for i in range(len(persona_mds))]
        if not audience_segments:
            audience_segments = ["General"]

        # Flatten subdomain names from taxonomy
        subdomain_names = _flatten_subdomain_names(taxonomy.root_nodes)

        all_assignments: List[TopicAssignment] = []
        total_relevant = 0
        total_irrelevant = 0

        # Process each subdomain
        semaphore = asyncio.Semaphore(settings.topic_discovery_max_concurrent_sources)

        async def _process_subdomain(
            subdomain: str,
        ) -> tuple:
            """Return (assignments, relevant_count, irrelevant_count) for one subdomain."""
            assignments: List[TopicAssignment] = []
            sd_relevant = 0
            sd_irrelevant = 0

            # Build dimension combinations for this subdomain
            dimensions = []
            for bs in buyer_stages:
                for it in intent_types:
                    for seg in audience_segments:
                        dimensions.append({
                            "buyer_stage": bs,
                            "intent_type": it,
                            "audience_segment": seg,
                        })

            # Step 1: Relevance filtering
            async with semaphore:
                classifications = await run_relevance_filtering(
                    subdomain, dimensions, company_md, timeout_s=timeout_s,
                )

            # Build relevance lookup
            relevance_map: Dict[str, str] = {}
            for cls in classifications:
                if isinstance(cls, dict):
                    key = f"{cls.get('buyer_stage', '')}|{cls.get('intent_type', '')}|{cls.get('audience_segment', '')}"
                    relevance_map[key] = cls.get("relevance", "relevant")

            # Step 2: Generate topics for relevant cells
            for dim in dimensions:
                key = f"{dim['buyer_stage']}|{dim['intent_type']}|{dim['audience_segment']}"
                relevance = relevance_map.get(key, "relevant")

                if relevance == "irrelevant":
                    sd_irrelevant += 1
                    continue

                sd_relevant += 1

                async with semaphore:
                    topics = await run_topic_generation(
                        subdomain,
                        dim["buyer_stage"],
                        dim["intent_type"],
                        dim["audience_segment"],
                        company_md,
                        timeout_s=timeout_s,
                    )
                assignments.extend(topics)

            return assignments, sd_relevant, sd_irrelevant

        # Run subdomain processing with concurrency
        subdomain_tasks = [_process_subdomain(sd) for sd in subdomain_names]
        subdomain_results = await asyncio.gather(*subdomain_tasks, return_exceptions=True)

        for i, res in enumerate(subdomain_results):
            if isinstance(res, Exception):
                logger.warning(
                    "TD/%s: topic generation failed for '%s': %s",
                    effective_slug, subdomain_names[i], res,
                )
            else:
                sd_assignments, sd_relevant, sd_irrelevant = res
                all_assignments.extend(sd_assignments)
                total_relevant += sd_relevant
                total_irrelevant += sd_irrelevant

        # Build matrix
        distributions = _compute_distributions(all_assignments)
        matrix = TopicAssignmentMatrix(
            version=1,
            status=TopicDiscoveryStatus.draft,
            assignments=all_assignments,
            total_assignments=len(all_assignments),
            total_relevant_cells=total_relevant,
            total_irrelevant_cells=total_irrelevant,
            buyer_stage_distribution=distributions["buyer_stage"],
            intent_distribution=distributions["intent"],
            audience_distribution=distributions["audience"],
        )

        mat_version = await asyncio.to_thread(storage.write_matrix, matrix)

        _emit(event_bus, task_id, "td_phase_complete", {
            "phase": 3,
            "total_assignments": len(all_assignments),
            "total_relevant": total_relevant,
            "total_irrelevant": total_irrelevant,
        })

        # =============================================================
        # HITL-2: Matrix Approval
        # =============================================================
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
        )

        mat_decision = hitl2_result.get("batch_decision", "approve")
        approved_mat_raw = hitl2_result.get("approved_matrix", {})
        if approved_mat_raw:
            matrix = TopicAssignmentMatrix.model_validate(approved_mat_raw)
            matrix.status = TopicDiscoveryStatus.approved
            mat_version = await asyncio.to_thread(storage.write_matrix, matrix)

        _emit(event_bus, task_id, "td_phase_complete", {
            "phase": "hitl_2", "decision": mat_decision,
        })

        # =============================================================
        # Phase 4: Finalize
        # =============================================================
        _emit(event_bus, task_id, "td_phase_start", {"phase": 4, "stage": "finalize"})
        _update_task(task_store, task_id, current_step="phase_4_finalize")

        # Update manifest
        manifest = await asyncio.to_thread(storage.read_manifest)
        manifest.slug = company_slug
        manifest.effective_slug = effective_slug
        manifest.company_name = input_data.company_name
        manifest.domain_name = domain
        manifest.status = TopicDiscoveryStatus.approved
        manifest.taxonomy_version = tax_version
        manifest.matrix_version = mat_version
        manifest.last_updated = datetime.now(timezone.utc).isoformat()
        manifest.source_results_written = [sr.source.value for sr in source_results]
        await asyncio.to_thread(storage.write_manifest, manifest)

        output = TopicDiscoveryOutput(
            slug=company_slug,
            effective_slug=effective_slug,
            company_name=input_data.company_name,
            taxonomy=taxonomy,
            matrix=matrix,
            coverage=coverage,
            manifest=manifest,
            taxonomy_version=tax_version,
            matrix_version=mat_version,
            total_execution_time_s=time.time() - start_time,
            status=TopicDiscoveryStatus.approved,
        )

        _emit(event_bus, task_id, "completed", {"pipeline": "topic_discovery"})
        _emit(event_bus, task_id, "td_phase_complete", {"phase": 4})
        end_span(trace_span, output={
            "total_subdomains": taxonomy.total_subdomains,
            "total_assignments": len(all_assignments),
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
