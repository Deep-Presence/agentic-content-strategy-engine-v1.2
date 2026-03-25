"""Shared gap context extraction for content brief sidebar enrichment.

Used by both JsonContentDataService and DbContentDataService to enrich
content briefs with gap analysis data (why we picked this, success
indicators, exemplars) from StorageBackend-based analysis.json.

Reads gap_analysis artifacts via StorageBackend regardless of whether
the brief itself came from DB or JSON.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from api.schemas.content_data import GapContextSummary
from core.storage.backends.base import StorageBackend

logger = logging.getLogger(__name__)

# ── Caching ──────────────────────────────────────────────────────────

_GAP_CACHE: Dict[str, Tuple[float, Any]] = {}
_GAP_CACHE_TTL_S = 300  # 5 minutes
_GAP_CACHE_LOCK = threading.Lock()

# Cache LocalStorageBackend instances by root path to avoid per-call instantiation
_LOCAL_BACKEND_CACHE: Dict[str, "StorageBackend"] = {}
_LOCAL_BACKEND_CACHE_MAX = 20


def _resolve_storage(storage_or_root: Union[StorageBackend, Path]) -> StorageBackend:
    """Resolve a StorageBackend or Path to a StorageBackend instance.

    Caches LocalStorageBackend instances per root path to avoid repeated
    instantiation on every call.  The Path branch is deprecated — all
    production callers now inject StorageBackend directly (Phase 7).
    """
    if isinstance(storage_or_root, Path):
        logger.warning(
            "load_analysis_json called with Path instead of StorageBackend — "
            "this fallback is deprecated and will be removed",
        )
        cache_key = str(storage_or_root)
        cached = _LOCAL_BACKEND_CACHE.get(cache_key)
        if cached is not None:
            return cached
        from core.storage.backends.local import LocalStorageBackend
        backend: StorageBackend = LocalStorageBackend(storage_or_root)
        if len(_LOCAL_BACKEND_CACHE) >= _LOCAL_BACKEND_CACHE_MAX:
            oldest_key = next(iter(_LOCAL_BACKEND_CACHE))
            del _LOCAL_BACKEND_CACHE[oldest_key]
        _LOCAL_BACKEND_CACHE[cache_key] = backend
        return backend
    return storage_or_root


def load_analysis_json(
    storage_or_root: Union[StorageBackend, Path], slug: str,
) -> Optional[Dict[str, Any]]:
    """Load and cache analysis.json for a company slug.

    Accepts StorageBackend (preferred) or Path (backward compat for Phase 2
    callers in content_data_service / db_content_data).
    Uses TTL-based cache invalidation.
    """
    storage = _resolve_storage(storage_or_root)

    cache_key = f"gap_analysis/{slug}/analysis.json"
    now = time.monotonic()
    cached = _GAP_CACHE.get(cache_key)
    if cached is not None and (now - cached[0]) < _GAP_CACHE_TTL_S:
        return cached[1]

    content = storage.read(f"gap_analysis/{slug}/analysis.json")
    if content is None:
        return None

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse gap_analysis/%s/analysis.json: %s", slug, exc)
        return None

    with _GAP_CACHE_LOCK:
        _GAP_CACHE[cache_key] = (now, data)
    return data


# ── Extraction ───────────────────────────────────────────────────────


def _build_why_picked(
    gap_score: float,
    classification: str,
    company_sim: float,
    citation_sim: float,
    company_cited: bool,
    exemplars_raw: List[Dict[str, Any]],
    cluster_spec: Dict[str, Any],
    cluster_name: str,
) -> List[str]:
    """Build human-readable 'Why We Picked This' reasons from gap data."""
    why: List[str] = []
    if gap_score >= 0.15:
        why.append(
            f"Significant citation gap detected (score: {gap_score:.4f}) — "
            f"AI engines cite competitors but not your content for this query."
        )
    if exemplars_raw:
        top_domains = list({e.get("domain", "") for e in exemplars_raw[:3] if e.get("domain")})
        if top_domains:
            why.append(
                f"Top cited sources: {', '.join(top_domains)}. "
                f"Content matching their structure has high citation probability."
            )
    if cluster_spec:
        wc = cluster_spec.get("word_count_range", [0, 0])
        if isinstance(wc, list) and len(wc) >= 2 and wc[1] > 0:
            why.append(
                f"Cluster '{cluster_name}' requires "
                f"{wc[0]}-{wc[1]} word content for citation eligibility."
            )
    if company_cited:
        why.append("Your company is already cited for related queries — this strengthens your position.")
    elif company_sim < citation_sim:
        why.append(
            f"Your best page similarity ({company_sim:.4f}) is below "
            f"the citation threshold ({citation_sim:.4f})."
        )
    return why


def _build_indicators(
    gap_score: float,
    classification: str,
    company_sim: float,
    citation_sim: float,
    exemplar_count: int,
) -> List[Dict[str, str]]:
    """Build Key Success Indicators from gap metrics."""
    indicators: List[Dict[str, str]] = []
    if gap_score > 0:
        indicators.append({"label": "Gap Score", "value": f"{gap_score:.4f}", "sub": classification.replace("_", " ")})
    if company_sim > 0:
        indicators.append({"label": "Your Similarity", "value": f"{company_sim:.4f}", "sub": "vs citation avg"})
    if citation_sim > 0:
        indicators.append({"label": "Citation Avg", "value": f"{citation_sim:.4f}", "sub": "benchmark to beat"})
    if exemplar_count > 0:
        indicators.append({"label": "Exemplars", "value": str(exemplar_count), "sub": "top cited pages analyzed"})
    return indicators


def _build_exemplars(exemplars_raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build exemplar list for display."""
    return [
        {
            "url": e.get("url", ""),
            "domain": e.get("domain", ""),
            "similarity": round(float(e.get("similarity", 0) or 0), 4),
            "word_count": int(
                (e.get("structural_signals") or {}).get("word_count", 0)
                or e.get("word_count", 0)
                or 0
            ),
            "authority_type": e.get("authority_type", ""),
        }
        for e in exemplars_raw[:5]
    ]


def extract_gap_context(
    brief: Dict[str, Any],
    analysis_json: Optional[Dict[str, Any]],
    gap_query_id: Optional[str] = None,
) -> Optional[GapContextSummary]:
    """Extract gap analysis context for a brief's sidebar display.

    Sources (in priority order):
    1. Blueprint's embedded gap_context (pipeline-generated briefs)
    2. Direct query_id lookup in analysis.json (when gap_query_id provided)
    3. Title match in analysis.json gaps (add_brief briefs)

    Args:
        brief: Blueprint dict with at least 'title' and 'target_cluster'.
        analysis_json: Loaded analysis.json dict, or None.
        gap_query_id: Optional direct query_id for tier-1 lookup.
    """
    # Source 1: Blueprint's embedded gap_context (WorkerQueryContext serialized)
    gap_ctx = brief.get("gap_context")
    if gap_ctx and isinstance(gap_ctx, dict):
        qg = gap_ctx.get("query_gap", {})
        exemplars_raw = gap_ctx.get("exemplars", [])
        cluster_spec = gap_ctx.get("cluster_spec", {})

        gap_score = float(qg.get("gap", 0) or 0)
        classification = qg.get("interpretation", "")
        company_sim = float(qg.get("best_company_similarity", 0) or 0)
        citation_sim = float(qg.get("avg_citation_similarity", 0) or 0)
        company_cited = bool(qg.get("company_cited"))

        return GapContextSummary(
            gap_score=gap_score,
            classification=classification,
            company_similarity=company_sim,
            citation_similarity=citation_sim,
            company_cited=company_cited,
            company_best_url=qg.get("best_company_url", ""),
            why_picked=_build_why_picked(
                gap_score, classification, company_sim, citation_sim,
                company_cited, exemplars_raw, cluster_spec,
                brief.get("target_cluster", ""),
            ),
            success_indicators=_build_indicators(
                gap_score, classification, company_sim, citation_sim, len(exemplars_raw),
            ),
            exemplars=_build_exemplars(exemplars_raw),
        )

    # Source 2 & 3: Lookup in analysis.json by query_id or title
    if analysis_json:
        gaps_raw = analysis_json.get("gaps", [])
        matched_gap: Optional[Dict[str, Any]] = None

        # Tier 1: Direct query_id lookup
        if gap_query_id:
            matched_gap = next(
                (g for g in gaps_raw if g.get("query_id") == gap_query_id),
                None,
            )

        # Tier 2: Title match fallback
        if not matched_gap:
            title_norm = (brief.get("title", "") or "").strip().lower()
            if title_norm:
                matched_gap = next(
                    (g for g in gaps_raw
                     if (g.get("query_text", "") or "").strip().lower() == title_norm),
                    None,
                )

        if matched_gap:
            gap_score = float(matched_gap.get("gap", 0) or 0)
            classification = matched_gap.get("interpretation", "")
            company_sim = float(matched_gap.get("best_company_similarity", 0) or 0)
            citation_sim = float(matched_gap.get("avg_citation_similarity", 0) or 0)
            company_cited = bool(matched_gap.get("company_cited"))
            exemplars_raw = matched_gap.get("top_cited_exemplars", [])

            # Look up cluster spec for richer context
            cluster_name = matched_gap.get("cluster_name") or brief.get("target_cluster", "")
            cluster_spec: Dict[str, Any] = {}
            for s in analysis_json.get("cluster_specs", []):
                if (s.get("cluster_name") or "").strip().lower() == (cluster_name or "").strip().lower():
                    cluster_spec = s
                    break

            return GapContextSummary(
                gap_score=gap_score,
                classification=classification,
                company_similarity=company_sim,
                citation_similarity=citation_sim,
                company_cited=company_cited,
                company_best_url=matched_gap.get("best_company_url", ""),
                why_picked=_build_why_picked(
                    gap_score, classification, company_sim, citation_sim,
                    company_cited, exemplars_raw, cluster_spec, cluster_name,
                ),
                success_indicators=_build_indicators(
                    gap_score, classification, company_sim, citation_sim, len(exemplars_raw),
                ),
                exemplars=_build_exemplars(exemplars_raw),
            )

    return None
