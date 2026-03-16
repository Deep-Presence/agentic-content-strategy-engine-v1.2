#!/usr/bin/env python3
"""Re-run Topic Discovery Phase 2.5 (scoring + persona affinity) and optionally
Phase 3 (expansion) from existing artifacts — skips S1/S2/HITL-1.

Usage::

    cd content-strategy-engine

    # Re-score only (no LLM calls):
    python scripts/run_td_rescore.py --slug carta

    # Re-score + expand top 5 subdomains (1 LLM call each):
    python scripts/run_td_rescore.py --slug carta --expand --top-n 5

    # Re-score + expand specific subdomains:
    python scripts/run_td_rescore.py --slug carta --expand --ids id1,id2,id3

    # With persona filter:
    python scripts/run_td_rescore.py --slug carta --expand --top-n 5 --persona david
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.config.settings import settings
from core.content_engine.llm_client import configure_litellm_callbacks
from core.models.topic_discovery import (
    BuyerStage,
    IntentType,
    PersonaAffinityIndex,
    ScoredSubdomainList,
    SourceResult,
    TaxonomyTree,
    TDSource,
    TopicAssignment,
    TopicAssignmentMatrix,
    TopicDiscoveryStatus,
)
from core.research.utils import load_persona_profiles, read_company_context
from core.storage.backends import LocalStorageBackend
from core.topic_discovery.agents import run_subdomain_expansion
from core.topic_discovery.pipeline import (
    _backfill_scores_into_taxonomy,
    _build_persona_name_to_id,
    _build_persona_summaries,
    _compute_distributions,
    _flatten_subdomain_nodes,
    _load_persona_entries,
)
from core.topic_discovery.scoring import (
    compute_persona_affinity_index,
    compute_subdomain_scores,
    compute_topic_priority,
)
from core.topic_discovery.storage import TopicDiscoveryStorage

from core.shared_tools.structured_logging import configure_logging

configure_logging()
logger = logging.getLogger("td_rescore")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Re-run TD scoring + optional expansion from existing artifacts",
    )
    p.add_argument(
        "--slug",
        required=True,
        help="Effective slug (e.g. 'carta' or 'carta__equity')",
    )
    p.add_argument(
        "--company-slug",
        default=None,
        help="Company slug for persona fallback (defaults to slug before '__')",
    )
    p.add_argument(
        "--artifacts-root",
        default="artifacts",
        help="Artifacts root directory (default: artifacts)",
    )
    p.add_argument(
        "--expand",
        action="store_true",
        help="Also run S3 expansion after scoring",
    )
    p.add_argument(
        "--top-n",
        type=int,
        default=5,
        help="Number of top-scored subdomains to expand (default: 5)",
    )
    p.add_argument(
        "--ids",
        default=None,
        help="Comma-separated subdomain IDs to expand (overrides --top-n)",
    )
    p.add_argument(
        "--persona",
        default=None,
        help="Persona ID to filter by (e.g. 'david')",
    )
    return p.parse_args()


async def main() -> None:
    args = _parse_args()
    slug = args.slug
    company_slug = args.company_slug or slug.split("__")[0]
    root = Path(args.artifacts_root)
    storage = TopicDiscoveryStorage(root, slug)
    backend = LocalStorageBackend(root)

    configure_litellm_callbacks()

    t0 = time.time()

    # ── Load existing taxonomy ──
    manifest = storage.read_manifest()
    tax_version = manifest.taxonomy_version or 1
    taxonomy = storage.read_taxonomy(tax_version)
    if taxonomy is None:
        # Try latest
        latest = storage.get_latest_taxonomy_version()
        if latest:
            taxonomy = storage.read_taxonomy(latest)
            tax_version = latest
    if taxonomy is None:
        logger.error("No taxonomy found at %s", storage.base_dir / "taxonomy")
        sys.exit(1)
    logger.info("Loaded taxonomy v%d (%d subdomains)", tax_version, taxonomy.total_subdomains)

    # ── Load persona entries ──
    persona_entries = _load_persona_entries(backend, slug, company_slug)
    persona_name_to_id = _build_persona_name_to_id(persona_entries)
    logger.info("Loaded %d persona entries: %s", len(persona_entries), persona_entries)

    # ── Load persona markdown for affinity scoring ──
    persona_mds = load_persona_profiles(backend, slug, company_slug)
    persona_mds_by_id: Dict[str, str] = {}
    for (pid, pname), md in zip(persona_entries, persona_mds):
        persona_mds_by_id[pid] = md

    # ── Load source_b results to build persona map ──
    source_b_persona_map: Dict[str, List[str]] = {}
    try:
        sr_b = storage.read_source_result(TDSource.source_b)
        if sr_b:
            for cand in sr_b.candidates:
                if cand.persona_ids:
                    key = cand.name.lower().strip()
                    existing = source_b_persona_map.get(key, [])
                    merged = list(dict.fromkeys(existing + list(cand.persona_ids)))
                    source_b_persona_map[key] = merged
            logger.info(
                "Source B: %d candidates, %d with persona_ids",
                len(sr_b.candidates),
                sum(1 for c in sr_b.candidates if c.persona_ids),
            )
        else:
            logger.warning("No source_b results found — persona affinity will use embeddings only")
    except Exception:
        logger.warning("Could not load source_b results", exc_info=True)

    logger.info("source_b_persona_map: %d entries", len(source_b_persona_map))

    # ══════════════════════════════════════════════════════════════════
    # Phase 2.5: Algorithmic Scoring (zero LLM calls)
    # ══════════════════════════════════════════════════════════════════
    logger.info("═" * 60)
    logger.info("Phase 2.5: Computing subdomain scores...")
    scored_subdomains = await compute_subdomain_scores(taxonomy=taxonomy)
    scoring_version = storage.write_scoring(scored_subdomains)
    logger.info("Scoring v%d: %d subdomains scored", scoring_version, scored_subdomains.total_scored)

    # Top 10 preview
    for sc in scored_subdomains.scores[:10]:
        logger.info(
            "  #%d  %.4f  %s  signals=%s",
            sc.rank, sc.composite_score, sc.subdomain_name, sc.signal_scores,
        )

    # ── Persona affinity ──
    logger.info("Computing persona affinity index...")
    persona_affinity = await compute_persona_affinity_index(
        taxonomy=taxonomy,
        subdomain_embeddings={},
        persona_mds_by_id=persona_mds_by_id,
        persona_embeddings={},
        source_b_persona_map=source_b_persona_map,
    )
    affinity_version = storage.write_persona_affinity(persona_affinity)
    logger.info(
        "Persona affinity v%d: %d personas × %d subdomains",
        affinity_version,
        persona_affinity.total_personas,
        persona_affinity.total_subdomains,
    )

    # Show non-zero affinities
    for pid, entries in persona_affinity.persona_entries.items():
        non_zero = [e for e in entries if e.affinity_score > 0]
        logger.info("  persona=%s: %d/%d non-zero affinities", pid, len(non_zero), len(entries))
        for e in non_zero[:5]:
            logger.info(
                "    %.3f  %s  (%s)", e.affinity_score, e.subdomain_name, e.provenance,
            )

    # ── Backfill into taxonomy ──
    _backfill_scores_into_taxonomy(
        taxonomy.root_nodes, scored_subdomains, persona_affinity,
    )
    storage.write_taxonomy(taxonomy, taxonomy.version)
    logger.info("Backfilled scores into taxonomy v%d", taxonomy.version)

    # ── Update manifest ──
    manifest.scoring_version = scoring_version
    manifest.persona_affinity_version = affinity_version
    storage.write_manifest(manifest)

    elapsed_scoring = time.time() - t0
    logger.info("Phase 2.5 complete in %.1fs", elapsed_scoring)

    if not args.expand:
        logger.info("Done (scoring only). Use --expand to also run S3 expansion.")
        return

    # ══════════════════════════════════════════════════════════════════
    # Phase 3 (S3): On-Demand Expansion
    # ══════════════════════════════════════════════════════════════════
    logger.info("═" * 60)
    logger.info("Phase 3: Subdomain expansion...")

    # Load company context for expansion prompt
    company_md = read_company_context(backend, slug, company_slug) or ""
    if not company_md.strip():
        logger.error("No company context found — cannot run expansion")
        sys.exit(1)
    company_md = company_md[:60_000]

    # Determine subdomains to expand
    all_tuples = _flatten_subdomain_nodes(taxonomy.root_nodes)

    if args.ids:
        selected_ids = set(args.ids.split(","))
        selected_tuples = [
            (sid, sname, sdesc) for sid, sname, sdesc in all_tuples if sid in selected_ids
        ]
        if not selected_tuples:
            logger.error("No matching subdomain IDs found for: %s", args.ids)
            sys.exit(1)
    else:
        # Select top-N by score
        top_ids = {sc.subdomain_id for sc in scored_subdomains.scores[:args.top_n]}
        selected_tuples = [
            (sid, sname, sdesc) for sid, sname, sdesc in all_tuples if sid in top_ids
        ]

    # Apply persona filter if set
    persona_filter = args.persona or ""
    if persona_filter and persona_filter in persona_affinity.persona_entries:
        persona_sds = {
            e.subdomain_id
            for e in persona_affinity.persona_entries[persona_filter]
            if e.affinity_score > 0.3
        }
        before = len(selected_tuples)
        selected_tuples = [t for t in selected_tuples if t[0] in persona_sds]
        logger.info(
            "Persona filter '%s': %d → %d subdomains",
            persona_filter, before, len(selected_tuples),
        )

    logger.info("Expanding %d subdomains...", len(selected_tuples))
    for sid, sname, _ in selected_tuples:
        logger.info("  - %s (%s)", sname, sid)

    # Build dimensions
    buyer_stages = [s.value for s in BuyerStage]
    intent_types = [t.value for t in IntentType]
    audience_segments: List[Tuple[str, str]] = persona_entries or [("general", "General")]

    # Optional persona context
    expansion_persona_ctx: Optional[str] = None
    if persona_filter and persona_filter in persona_mds_by_id:
        expansion_persona_ctx = persona_mds_by_id[persona_filter][:500]

    # Expand concurrently
    all_assignments: List[TopicAssignment] = []
    semaphore = asyncio.Semaphore(settings.topic_discovery_max_concurrent_sources)

    async def _expand(sd_id: str, sd_name: str, sd_desc: str) -> List[TopicAssignment]:
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
            )
        for a in assignments:
            a.subdomain_id = sd_id
        return assignments

    tasks = [_expand(sid, sname, sdesc) for sid, sname, sdesc in selected_tuples]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for i, res in enumerate(results):
        if isinstance(res, Exception):
            logger.error(
                "Expansion FAILED for '%s': %s(%s)",
                selected_tuples[i][1], type(res).__name__, res,
            )
        else:
            all_assignments.extend(res)
            logger.info(
                "Expanded '%s': %d assignments",
                selected_tuples[i][1], len(res),
            )

    # Compute topic priority scores
    score_lookup = {sc.subdomain_id: sc for sc in scored_subdomains.scores}
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

    # Build and persist matrix
    distributions = _compute_distributions(all_assignments)
    matrix = TopicAssignmentMatrix(
        version=1,
        status=TopicDiscoveryStatus.draft,
        assignments=all_assignments,
        total_assignments=len(all_assignments),
        total_relevant_cells=len(all_assignments),
        total_irrelevant_cells=0,
        buyer_stage_distribution=distributions["buyer_stage"],
        intent_distribution=distributions["intent"],
        audience_distribution=distributions["audience"],
    )
    mat_version = storage.write_matrix(matrix)

    elapsed_total = time.time() - t0
    logger.info("═" * 60)
    logger.info("Phase 3 complete.")
    logger.info("  Subdomains expanded: %d", len(selected_tuples))
    logger.info("  Total assignments: %d", len(all_assignments))
    logger.info("  Matrix version: v%d", mat_version)
    logger.info("  Total time: %.1fs", elapsed_total)

    # Update manifest
    manifest.matrix_version = mat_version
    storage.write_manifest(manifest)
    logger.info("Manifest updated. Done.")


if __name__ == "__main__":
    asyncio.run(main())
