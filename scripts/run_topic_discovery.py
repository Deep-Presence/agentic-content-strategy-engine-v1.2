#!/usr/bin/env python3
"""Run Topic Discovery pipelines — Pipeline A (Discovery) or Pipeline B (Expansion).

Pipeline A (discover): Multi-source subdomain generation → dedup → hierarchy → HITL-1 → scoring
Pipeline B (expand):   Load taxonomy → expand selected subdomains → HITL-2 → matrix

Usage::

    cd content-strategy-engine

    # ── Pipeline A: Discovery ──

    # Full discovery (interactive HITL):
    python scripts/run_topic_discovery.py discover --company-name "Ramp" --domain ramp.com

    # With product scope:
    python scripts/run_topic_discovery.py discover --company-name "Ramp" --domain ramp.com \
        --product-slug equity --product-name "Ramp Equity"

    # Auto-approve taxonomy checkpoint:
    python scripts/run_topic_discovery.py discover --company-name "Ramp" --domain ramp.com --auto-approve

    # With seed URLs + persona filter:
    python scripts/run_topic_discovery.py discover --company-name "Ramp" --domain ramp.com \
        --seed-url https://ramp.com/blog --seed-url https://ramp.com/resources \
        --persona david

    # ── Pipeline B: Expansion ──

    # Expand top 10 subdomains (default):
    python scripts/run_topic_discovery.py expand --company-name "Ramp" --slug ramp

    # Expand specific subdomains by ID:
    python scripts/run_topic_discovery.py expand --company-name "Ramp" --slug ramp \
        --ids sd-abc123,sd-def456

    # Expand top 5 with auto-approve:
    python scripts/run_topic_discovery.py expand --company-name "Ramp" --slug ramp \
        --top-n 5 --auto-approve

    # With persona filter:
    python scripts/run_topic_discovery.py expand --company-name "Ramp" --slug ramp \
        --persona david --top-n 5

    # Use a specific taxonomy version:
    python scripts/run_topic_discovery.py expand --company-name "Ramp" --slug ramp \
        --taxonomy-version 2
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.config.settings import settings
from core.models.topic_discovery import (
    TopicDiscoveryInput,
    TopicDiscoveryOutput,
    TopicExpansionInput,
    TopicExpansionOutput,
)
from core.topic_discovery.pipeline import (
    run_topic_discovery_pipeline,
    run_topic_expansion_pipeline,
)

from core.shared_tools.structured_logging import configure_logging

configure_logging()
logger = logging.getLogger("run_td")


# ── Argument parsing ─────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Topic Discovery Pipeline A (discover) or Pipeline B (expand).",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable DEBUG logging",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── discover (Pipeline A) ──
    pa = sub.add_parser(
        "discover",
        help="Pipeline A: multi-source discovery → taxonomy → scoring",
    )
    pa.add_argument("--company-name", required=True, help="Company name")
    pa.add_argument("--domain", default=None, help="Company domain")
    pa.add_argument("--company-slug", default=None, help="Override company slug")
    pa.add_argument("--product-slug", default=None, help="Product slug (for product-level scope)")
    pa.add_argument("--product-name", default=None, help="Product name")
    pa.add_argument("--seed-url", action="append", default=[], help="Seed URL (repeatable)")
    pa.add_argument("--language", default="en", help="Language code (default: en)")
    pa.add_argument("--region", default=None, help="Region code")
    pa.add_argument(
        "--auto-approve",
        action="store_true",
        help="Auto-approve HITL-1 taxonomy checkpoint",
    )
    pa.add_argument(
        "--dedup-threshold",
        type=float,
        default=0.85,
        help="Deduplication cosine-similarity threshold (default: 0.85)",
    )
    pa.add_argument(
        "--top-n-expand",
        type=int,
        default=10,
        help="Number of top subdomains to auto-expand (default: 10)",
    )
    pa.add_argument(
        "--max-rounds",
        type=int,
        default=None,
        help="Max brainstorm rounds per source (default: from settings, currently 4)",
    )
    pa.add_argument("--persona", default=None, help="Persona ID to filter by")
    pa.add_argument("--artifacts-root", default="artifacts", help="Artifacts root (default: artifacts)")

    # ── expand (Pipeline B) ──
    pb = sub.add_parser(
        "expand",
        help="Pipeline B: expand selected subdomains into topic matrix",
    )
    pb.add_argument("--company-name", required=True, help="Company name")
    pb.add_argument(
        "--slug",
        required=True,
        help="Effective slug from Pipeline A (e.g. 'ramp' or 'ramp__equity')",
    )
    pb.add_argument("--domain", default=None, help="Company domain")
    pb.add_argument("--company-slug", default=None, help="Override company slug")
    pb.add_argument("--product-slug", default=None, help="Product slug")
    pb.add_argument("--product-name", default=None, help="Product name")
    pb.add_argument(
        "--ids",
        default=None,
        help="Comma-separated subdomain IDs to expand (overrides --top-n)",
    )
    pb.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Expand top N scored subdomains (default: 10, ignored if --ids set)",
    )
    pb.add_argument("--persona", default=None, help="Persona ID to filter by")
    pb.add_argument(
        "--taxonomy-version",
        type=int,
        default=None,
        help="Use a specific taxonomy version (default: latest)",
    )
    pb.add_argument(
        "--auto-approve",
        action="store_true",
        help="Auto-approve HITL-2 matrix checkpoint",
    )
    pb.add_argument("--language", default="en", help="Language code (default: en)")
    pb.add_argument("--region", default=None, help="Region code")
    pb.add_argument("--artifacts-root", default="artifacts", help="Artifacts root (default: artifacts)")

    return parser


# ── Pipeline A: Discovery ────────────────────────────────────────────


async def _run_discover(args: argparse.Namespace) -> int:
    inp = TopicDiscoveryInput(
        company_name=args.company_name,
        domain=args.domain,
        company_slug=args.company_slug,
        product_slug=args.product_slug,
        product_name=args.product_name,
        seed_urls=args.seed_url or [],
        language=args.language,
        region=args.region,
        auto_approve_checkpoints=[1] if args.auto_approve else [],
        dedup_threshold=args.dedup_threshold,
        top_n_expand=args.top_n_expand,
        persona_filter=args.persona,
        max_expansion_rounds=args.max_rounds or settings.topic_discovery_max_expansion_rounds,
    )

    print(f"\n{'=' * 60}")
    print(f"  Topic Discovery — Pipeline A (Discovery)")
    print(f"  Company:  {args.company_name}")
    if args.domain:
        print(f"  Domain:   {args.domain}")
    if args.product_slug:
        print(f"  Product:  {args.product_name or args.product_slug}")
    if args.persona:
        print(f"  Persona:  {args.persona}")
    print(f"  Rounds:   {inp.max_expansion_rounds}")
    print(f"  HITL:     {'auto-approve' if args.auto_approve else 'interactive'}")
    print(f"{'=' * 60}\n")

    t0 = time.time()
    result: TopicDiscoveryOutput = await run_topic_discovery_pipeline(
        inp,
        artifacts_root=Path(args.artifacts_root),
    )
    elapsed = time.time() - t0

    print(f"\n{'=' * 60}")
    print(f"  PIPELINE A — RESULTS")
    print(f"{'=' * 60}")
    print(f"  Slug:              {result.slug}")
    print(f"  Effective slug:    {result.effective_slug}")
    print(f"  Status:            {result.status}")
    if result.taxonomy:
        print(f"  Taxonomy:          v{result.taxonomy.version} — {result.taxonomy.total_subdomains} subdomains")
    if result.coverage:
        print(f"  Coverage estimate: {result.coverage.median_estimate:.0f} (Chao1 median)")
    if result.scored_subdomains:
        print(f"  Scored subdomains: {result.scored_subdomains.total_scored}")
        print(f"  Top 5:")
        for sc in result.scored_subdomains.scores[:5]:
            print(f"    #{sc.rank}  {sc.composite_score:.4f}  {sc.subdomain_name}")
    if result.persona_affinity:
        print(f"  Persona affinity:  {result.persona_affinity.total_personas} personas × {result.persona_affinity.total_subdomains} subdomains")
    print(f"  Time:              {elapsed:.1f}s")
    print()

    # ── Persist results to filesystem (CLI-only) ──
    _persist_discovery_output(result, Path(args.artifacts_root))

    return 0


# ── CLI-only filesystem persistence ─────────────────────────────────


def _persist_discovery_output(
    result: TopicDiscoveryOutput, artifacts_root: Path
) -> None:
    """Write Pipeline A results to artifacts/ so CLI runs are never lost.

    This is a CLI-only convenience — the pipeline itself is db_only.
    Uses TopicDiscoveryStorage for consistent file layout.
    """
    from core.topic_discovery.storage import TopicDiscoveryStorage

    slug = result.effective_slug or result.slug
    if not slug:
        logger.warning("No slug on output — skipping filesystem persist")
        return

    storage = TopicDiscoveryStorage(artifacts_root, slug)
    written: list[str] = []

    if result.manifest:
        storage.write_manifest(result.manifest)
        written.append("_manifest.json")

    if result.taxonomy:
        ver = result.taxonomy_version or result.taxonomy.version or 1
        storage.write_taxonomy(result.taxonomy, version=ver)
        written.append(f"taxonomy/v{ver}.json")

    if result.coverage:
        storage.write_coverage(result.coverage, version=1)
        written.append("raw/coverage_v1.json")

    if result.scored_subdomains:
        ver = (result.manifest.scoring_version if result.manifest else 0) or 1
        storage.write_scoring(result.scored_subdomains, version=ver)
        written.append(f"scoring/v{ver}.json")

    if result.persona_affinity:
        ver = (result.manifest.persona_affinity_version if result.manifest else 0) or 1
        storage.write_persona_affinity(result.persona_affinity, version=ver)
        written.append(f"persona_affinity/v{ver}.json")

    if result.matrix:
        ver = result.matrix_version or 1
        storage.write_matrix(result.matrix, version=ver)
        written.append(f"matrix/v{ver}.json")

    if written:
        print(f"\n  📁 Saved {len(written)} artifacts to {storage.base_dir}/")
        for f in written:
            print(f"     {f}")
    else:
        logger.warning("No data on output — nothing written to filesystem")


def _persist_expansion_output(
    result: "TopicExpansionOutput", artifacts_root: Path
) -> None:
    """Write Pipeline B results to artifacts/ so CLI runs are never lost."""
    from core.topic_discovery.storage import TopicDiscoveryStorage

    slug = result.effective_slug or result.slug
    if not slug:
        logger.warning("No slug on output — skipping filesystem persist")
        return

    storage = TopicDiscoveryStorage(artifacts_root, slug)
    written: list[str] = []

    if result.matrix:
        ver = result.matrix_version or 1
        storage.write_matrix(result.matrix, version=ver)
        written.append(f"matrix/v{ver}.json")

        # Update manifest with new matrix version
        manifest = storage.read_manifest()
        manifest.matrix_version = ver
        storage.write_manifest(manifest)
        written.append("_manifest.json (updated)")

    if written:
        print(f"\n  📁 Saved {len(written)} artifacts to {storage.base_dir}/")
        for f in written:
            print(f"     {f}")
    else:
        logger.warning("No data on output — nothing written to filesystem")


# ── Pipeline B: Expansion ────────────────────────────────────────────


async def _run_expand(args: argparse.Namespace) -> int:
    subdomain_ids = args.ids.split(",") if args.ids else []

    # If no explicit IDs, resolve --top-n from scored subdomains in artifacts
    if not subdomain_ids:
        from core.topic_discovery.storage import TopicDiscoveryStorage

        storage = TopicDiscoveryStorage(Path(args.artifacts_root), args.slug)
        manifest = storage.read_manifest()
        scoring_ver = manifest.scoring_version
        if not scoring_ver:
            # Try latest
            scoring_ver = storage.get_latest_scoring_version()
        if not scoring_ver:
            print("ERROR: No scoring artifacts found. Run Pipeline A first.")
            return 1
        scored = storage.read_scoring(scoring_ver)
        if not scored or not scored.scores:
            print("ERROR: Scoring artifacts are empty. Run Pipeline A first.")
            return 1
        subdomain_ids = [sc.subdomain_id for sc in scored.scores[: args.top_n]]
        print(f"  Resolved top {args.top_n} subdomain IDs from scoring v{scoring_ver}:")
        for sc in scored.scores[: args.top_n]:
            print(f"    {sc.subdomain_id}  {sc.composite_score:.4f}  {sc.subdomain_name}")

    inp = TopicExpansionInput(
        company_name=args.company_name,
        domain=args.domain,
        company_slug=args.company_slug,
        product_slug=args.product_slug,
        product_name=args.product_name,
        effective_slug=args.slug,
        subdomain_ids=subdomain_ids,
        persona_filter=args.persona,
        taxonomy_version=args.taxonomy_version,
        auto_approve_checkpoints=[2] if args.auto_approve else [],
        language=args.language,
        region=args.region,
    )

    print(f"\n{'=' * 60}")
    print(f"  Topic Discovery — Pipeline B (Expansion)")
    print(f"  Company:        {args.company_name}")
    print(f"  Effective slug: {args.slug}")
    print(f"  Subdomains:     {len(subdomain_ids)} IDs")
    if args.persona:
        print(f"  Persona:        {args.persona}")
    if args.taxonomy_version:
        print(f"  Taxonomy ver:   v{args.taxonomy_version}")
    print(f"  HITL:           {'auto-approve' if args.auto_approve else 'interactive'}")
    print(f"{'=' * 60}\n")

    t0 = time.time()
    result: TopicExpansionOutput = await run_topic_expansion_pipeline(
        inp,
        artifacts_root=Path(args.artifacts_root),
    )
    elapsed = time.time() - t0

    print(f"\n{'=' * 60}")
    print(f"  PIPELINE B — RESULTS")
    print(f"{'=' * 60}")
    print(f"  Slug:               {result.slug}")
    print(f"  Effective slug:     {result.effective_slug}")
    print(f"  Status:             {result.status}")
    print(f"  Matrix version:     v{result.matrix_version}")
    print(f"  Subdomains expanded: {result.subdomains_expanded}")
    print(f"  Subdomains failed:   {result.subdomains_failed}")
    print(f"  Total assignments:   {result.total_assignments}")
    if result.matrix:
        print(f"  Buyer stage dist:   {result.matrix.buyer_stage_distribution}")
        print(f"  Intent dist:        {result.matrix.intent_distribution}")
    print(f"  Time:               {elapsed:.1f}s")
    print()

    # ── Persist results to filesystem (CLI-only) ──
    _persist_expansion_output(result, Path(args.artifacts_root))

    return 0


# ── Entry point ──────────────────────────────────────────────────────


async def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.command == "discover":
        return await _run_discover(args)
    elif args.command == "expand":
        return await _run_expand(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))