"""Service layer for gap analysis data endpoints.

Reads pre-computed pipeline artifacts from disk, reshapes them to match
the frontend TypeScript types, and caches parsed JSON for performance.
"""
from __future__ import annotations

import json
import logging
import math
import re
import threading
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import HTTPException
from pydantic import ValidationError

from api.schemas.content_data import (
    EmbeddingPoint,
    EmbeddingProjectionResponse,
)
from api.schemas.gap_data import (
    ClusterListResponse,
    ClusterPatternRow,
    ClusterPerformanceRow,
    ClusterSpecResponse,
    GapClassificationCounts,
    GapSummaryResponse,
    HeatmapCluster,
    HeatmapQuery,
    HeatmapResponse,
    PlatformListResponse,
    PlatformSummaryResponse,
    ProximityStats,
    QueryContentBrief,
    QueryExemplar,
    QueryListResponse,
    QueryRow,
    SignalAverageRow,
    SignalAveragesResponse,
    SignalCorrelationRow,
    SPAScore,
)

logger = logging.getLogger(__name__)

# ── Caching ──────────────────────────────────────────────────────────

_CACHE: Dict[Tuple[str, str], Tuple[int, Any]] = {}
_CACHE_MAX_ENTRIES = 10
_CACHE_LOCK = threading.Lock()  # C6: protects compound check-evict-insert


def _load_json_cached(
    artifacts_root: Path, slug: str, filename: str
) -> Optional[Any]:
    """Load and parse a JSON file with mtime-based cache invalidation."""
    file_path = artifacts_root / "gap_analysis" / slug / filename

    # CX-9: guard stat() — eliminates TOCTOU between is_file() and stat()
    try:
        mtime_ns = file_path.stat().st_mtime_ns
    except (FileNotFoundError, OSError):
        return None

    cache_key = (slug, filename)

    cached = _CACHE.get(cache_key)
    if cached is not None and cached[0] == mtime_ns:
        return cached[1]

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to parse %s: %s", file_path, exc)
        return None

    # C6: lock protects the compound check-evict-insert against concurrent writes
    with _CACHE_LOCK:
        if len(_CACHE) >= _CACHE_MAX_ENTRIES and cache_key not in _CACHE:
            oldest_key = next(iter(_CACHE))
            del _CACHE[oldest_key]
        _CACHE[cache_key] = (mtime_ns, data)
    return data


# ── Slug validation ──────────────────────────────────────────────────

# Accepts bare company slugs ("ramp") and effective product slugs ("ramp__card")
_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*(__[a-z0-9][a-z0-9-]*)?$")


def _validate_slug_dir(artifacts_root: Path, slug: str) -> Path:
    """Validate slug format and return the gap_analysis/{slug}/ directory.

    Raises HTTPException 400 for invalid slug format, 404 if directory missing.
    """
    if not _SLUG_PATTERN.match(slug):
        raise HTTPException(status_code=400, detail="Invalid slug format")
    slug_dir = artifacts_root / "gap_analysis" / slug
    if not slug_dir.is_dir():
        raise HTTPException(
            status_code=404,
            detail=f"No gap analysis data found for '{slug}'",
        )
    return slug_dir


# ── File loading with fallback ───────────────────────────────────────


def _load_analysis_data(artifacts_root: Path, slug: str) -> Dict[str, Any]:
    """Load gap analysis data with fallback chain.

    1. gap_analysis_complete.json (has analysis + report + cluster_specs)
    2. analysis.json (raw AnalysisResult)
    """
    complete = _load_json_cached(artifacts_root, slug, "gap_analysis_complete.json")
    if complete is not None:
        return complete

    analysis = _load_json_cached(artifacts_root, slug, "analysis.json")
    if analysis is not None:
        # Wrap in the same shape as gap_analysis_complete.json
        return {"analysis": analysis, "report": {}, "cluster_specs": analysis.get("cluster_specs", [])}

    return {"analysis": {}, "report": {}, "cluster_specs": []}


def _load_report_data(artifacts_root: Path, slug: str) -> Dict[str, Any]:
    """Load report data (executive summary, recommendations, etc.)."""
    report = _load_json_cached(artifacts_root, slug, "gap_report.json")
    if report is not None:
        return report

    # Fall back to gap_analysis_complete.json report section
    complete = _load_json_cached(artifacts_root, slug, "gap_analysis_complete.json")
    if complete is not None:
        return complete.get("report", {})

    return {}


def _load_enriched(artifacts_root: Path, slug: str) -> List[Dict[str, Any]]:
    """Load enriched_citations.json (may be large ~20MB, cached)."""
    data = _load_json_cached(artifacts_root, slug, "enriched_citations.json")
    return data if isinstance(data, list) else []


# ── Engine name mapping ──────────────────────────────────────────────

_ENGINE_DISPLAY: Dict[str, str] = {
    "openai": "ChatGPT",
    "claude": "Claude",
    "perplexity": "Perplexity",
    "gemini": "Gemini",
}

_ENGINE_KEYS: Dict[str, str] = {
    "openai": "chatgpt",
    "claude": "claude",
    "perplexity": "perplexity",
    "gemini": "gemini",
}


def _map_engine_display(engine: Optional[str]) -> str:
    """Map backend engine name to frontend display name."""
    if engine is None:
        return "Unknown"
    return _ENGINE_DISPLAY.get(engine, engine.title())


def _map_engine_key(engine: Optional[str]) -> str:
    """Map backend engine name to lowercase frontend key."""
    if engine is None:
        return "unknown"
    return _ENGINE_KEYS.get(engine, engine.lower())


# ── Helper functions ─────────────────────────────────────────────────


def _build_platform_index(
    enriched: List[Dict[str, Any]],
) -> Dict[str, Dict[str, int]]:
    """Build query_id -> {engine_key -> count} index."""
    index: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for cit in enriched:
        qid = cit.get("query_id")
        engine = cit.get("engine")
        if qid and engine:
            key = _map_engine_key(engine)
            index[qid][key] += 1
    return dict(index)


_PATTERN_FLAGS = [
    ("has_faq_section", "FAQ"),
    ("has_key_takeaways", "Key Takeaways"),
    ("has_step_by_step", "Step-by-Step"),
    ("has_tables", "Tables"),
    ("has_definition_opening", "Definition Opening"),
    ("has_research_refs", "Research References"),
    ("has_expert_quotes", "Expert Quotes"),
]


def _extract_patterns(content_brief: Optional[Dict[str, Any]]) -> List[str]:
    """Extract content pattern names from boolean flags >= 0.5."""
    if content_brief is None:
        return []
    seen: set[str] = set()
    patterns: List[str] = []
    for flag, label in _PATTERN_FLAGS:
        val = content_brief.get(flag, 0)
        if isinstance(val, (int, float)) and val >= 0.5 and label not in seen:
            patterns.append(label)
            seen.add(label)
    return patterns


def _tuple_to_range(
    val: Any, default_min: Any = 0, default_max: Any = 0,
) -> Dict[str, Any]:
    """Convert a list/tuple [min, max] to {min, max} dict."""
    if isinstance(val, (list, tuple)) and len(val) >= 2:
        return {"min": val[0], "max": val[1]}
    return {"min": default_min, "max": default_max}


# ── Signal definition table ──────────────────────────────────────────

_SIGNAL_DEFS: List[Dict[str, str]] = [
    # Text Composition
    {"field": "word_count", "name": "Word Count", "category": "Text Composition", "unit": "words"},
    {"field": "sentence_count", "name": "Sentence Count", "category": "Text Composition", "unit": "count"},
    {"field": "paragraph_count", "name": "Paragraph Count", "category": "Text Composition", "unit": "count"},
    {"field": "avg_paragraph_length", "name": "Avg Paragraph Length", "category": "Text Composition", "unit": "words"},
    {"field": "reading_level", "name": "Reading Level", "category": "Text Composition", "unit": "grade level"},
    {"field": "self_contained_ratio", "name": "Self-Contained Ratio", "category": "Text Composition", "unit": "%"},
    # Structural Elements
    {"field": "h1_count", "name": "H1 Count", "category": "Structural Elements", "unit": "count"},
    {"field": "h2_count", "name": "H2 Count", "category": "Structural Elements", "unit": "count"},
    {"field": "h3_count", "name": "H3 Count", "category": "Structural Elements", "unit": "count"},
    {"field": "h4_count", "name": "H4 Count", "category": "Structural Elements", "unit": "count"},
    {"field": "list_block_count", "name": "List Count", "category": "Structural Elements", "unit": "count"},
    {"field": "ordered_list_count", "name": "Ordered List Count", "category": "Structural Elements", "unit": "count"},
    {"field": "table_count", "name": "Table Count", "category": "Structural Elements", "unit": "count"},
    {"field": "code_block_count", "name": "Code Block Count", "category": "Structural Elements", "unit": "count"},
    # Content Patterns (boolean → rate)
    {"field": "has_faq_section", "name": "FAQ Section", "category": "Content Patterns", "unit": "%"},
    {"field": "has_definition_opening", "name": "Definition Opening", "category": "Content Patterns", "unit": "%"},
    {"field": "has_key_takeaways", "name": "Key Takeaways", "category": "Content Patterns", "unit": "%"},
    {"field": "has_comparison_table", "name": "Comparison Table", "category": "Content Patterns", "unit": "%"},
    {"field": "has_step_by_step", "name": "Step-by-Step", "category": "Content Patterns", "unit": "%"},
    {"field": "has_research_refs", "name": "Research References", "category": "Content Patterns", "unit": "%"},
    {"field": "has_expert_quotes", "name": "Expert Quotes", "category": "Content Patterns", "unit": "%"},
    # Factual Density
    {"field": "data_point_count", "name": "Data Point Count", "category": "Factual Density", "unit": "data points"},
    {"field": "citation_density", "name": "Citation Density", "category": "Factual Density", "unit": "per word"},
    {"field": "named_entity_density", "name": "Named Entity Density", "category": "Factual Density", "unit": "per word"},
]


def _safe_float(val: Any) -> Optional[float]:
    """Convert to float, returning None for NaN/Inf/non-numeric (CX-6)."""
    if not isinstance(val, (int, float, bool)):
        return None
    f = float(val)
    if not math.isfinite(f):
        return None
    return f


def _compute_signal_averages(
    enriched: List[Dict[str, Any]],
) -> List[SignalAverageRow]:
    """Compute mean structural signals across all enriched citations.

    Only includes signals that have at least one non-None value (handles
    old 11-field format vs new 45-field format).
    """
    accumulators: Dict[str, List[float]] = defaultdict(list)

    for cit in enriched:
        ss = cit.get("structural_signals")
        if not ss or not isinstance(ss, dict):
            continue
        for sig_def in _SIGNAL_DEFS:
            f = _safe_float(ss.get(sig_def["field"]))
            if f is not None:
                accumulators[sig_def["field"]].append(f)

    rows: List[SignalAverageRow] = []
    for sig_def in _SIGNAL_DEFS:
        values = accumulators.get(sig_def["field"])
        if not values:
            continue
        avg = sum(values) / len(values)
        rec = f"Citation average: {avg:.2f} {sig_def['unit']}"
        rows.append(
            SignalAverageRow(
                signal=sig_def["name"],
                category=sig_def["category"],
                citation_avg=round(avg, 4),
                company_avg=0.0,
                unit=sig_def["unit"],
                recommendation=rec,
            )
        )
    return rows


def _compute_signal_correlations(
    enriched: List[Dict[str, Any]],
) -> List[SignalCorrelationRow]:
    """Compute Pearson correlation of each signal with citation similarity.

    Uses best_paragraphs[0].similarity as the target variable. Skips citations
    with empty best_paragraphs. Returns 0.0 if < 3 data points.
    """
    # Collect (signal_value, similarity) pairs per signal
    pairs: Dict[str, List[Tuple[float, float]]] = defaultdict(list)

    for cit in enriched:
        ss = cit.get("structural_signals")
        bp = cit.get("best_paragraphs", [])
        if not ss or not isinstance(ss, dict) or not bp:
            continue
        raw_sim = bp[0].get("similarity") if isinstance(bp[0], dict) else None
        sim = _safe_float(raw_sim)
        if sim is None:
            continue

        for sig_def in _SIGNAL_DEFS:
            f = _safe_float(ss.get(sig_def["field"]))
            if f is not None:
                pairs[sig_def["field"]].append((f, sim))

    rows: List[SignalCorrelationRow] = []
    for sig_def in _SIGNAL_DEFS:
        data = pairs.get(sig_def["field"], [])
        corr = _pearson(data)
        if corr is not None:
            rows.append(
                SignalCorrelationRow(
                    signal=sig_def["name"],
                    correlation=round(corr, 4),
                    category=sig_def["category"],
                )
            )
    # Sort by absolute correlation descending
    rows.sort(key=lambda r: abs(r.correlation), reverse=True)
    return rows


def _pearson(data: List[Tuple[float, float]]) -> Optional[float]:
    """Compute Pearson correlation coefficient. Returns None if < 3 points."""
    if len(data) < 3:
        return None
    n = len(data)
    sx = sum(x for x, _ in data)
    sy = sum(y for _, y in data)
    sxy = sum(x * y for x, y in data)
    sx2 = sum(x * x for x, _ in data)
    sy2 = sum(y * y for _, y in data)

    product = (n * sx2 - sx * sx) * (n * sy2 - sy * sy)
    if product <= 0:
        return 0.0
    denom = math.sqrt(product)
    if denom == 0:
        return 0.0
    return (n * sxy - sx * sy) / denom


def _compute_cluster_patterns(
    enriched: List[Dict[str, Any]],
    cluster_specs: List[Dict[str, Any]],
) -> List[ClusterPatternRow]:
    """Compute per-cluster content pattern adoption rates.

    Merges cluster_specs data (faq_rate, table_rate, key_takeaways_rate) with
    computed rates from enriched_citations for the remaining patterns.
    """
    _BOOL_PATTERNS = [
        "has_faq_section", "has_definition_opening", "has_key_takeaways",
        "has_comparison_table", "has_step_by_step", "has_research_refs",
        "has_expert_quotes",
    ]

    # Compute from enriched citations
    cluster_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    cluster_totals: Dict[str, int] = defaultdict(int)

    for cit in enriched:
        cname = cit.get("cluster_name")
        ss = cit.get("structural_signals")
        if not cname or not ss or not isinstance(ss, dict):
            continue
        cluster_totals[cname] += 1
        for pat in _BOOL_PATTERNS:
            if ss.get(pat):
                cluster_counts[cname][pat] += 1

    # Build spec lookup for cluster_id
    spec_lookup: Dict[str, Dict[str, Any]] = {}
    for spec in cluster_specs:
        name = spec.get("cluster_name", "")
        spec_lookup[name] = spec

    # Collect all cluster names from both sources
    all_clusters = set(spec_lookup.keys()) | set(cluster_totals.keys())
    rows: List[ClusterPatternRow] = []

    for cname in sorted(all_clusters):
        spec = spec_lookup.get(cname, {})
        total = cluster_totals.get(cname, 1) or 1  # avoid div by zero

        def _rate(pat: str) -> float:
            return round(cluster_counts.get(cname, {}).get(pat, 0) / total, 2)

        rows.append(
            ClusterPatternRow(
                cluster_id=spec.get("cluster_id", ""),
                cluster_name=cname,
                faq=spec.get("faq_rate", _rate("has_faq_section")),
                definition_opening=_rate("has_definition_opening"),
                key_takeaways=spec.get("key_takeaways_rate", _rate("has_key_takeaways")),
                comparison_table=_rate("has_comparison_table"),
                step_by_step=_rate("has_step_by_step"),
                research_refs=_rate("has_research_refs"),
                expert_quotes=_rate("has_expert_quotes"),
            )
        )
    return rows


def _compute_cluster_fingerprints(
    cluster_specs: List[Dict[str, Any]],
) -> Dict[str, Dict[str, float]]:
    """Compute normalized (0-1) radar chart data per cluster.

    Normalizes each signal dimension across all clusters so max = 1.0.
    """
    _FP_FIELDS = {
        "word_count": "avg_word_count",
        "headers": None,  # from structural_rates
        "lists": None,
        "tables": "table_rate",
        "faq": "faq_rate",
        "stats": None,  # from structural_rates
        "citations": None,  # from structural_rates
    }

    raw: Dict[str, Dict[str, float]] = {}
    for spec in cluster_specs:
        cid = spec.get("cluster_id", spec.get("cluster_name", ""))
        rates = spec.get("structural_rates", {})
        raw[cid] = {
            "word_count": spec.get("avg_word_count", 0),
            "headers": rates.get("headers", 0),
            "lists": rates.get("lists", 0),
            "tables": spec.get("table_rate", rates.get("tables", 0)),
            "faq": spec.get("faq_rate", 0),
            "stats": rates.get("stats", 0),
            "citations": rates.get("citations", 0),
        }

    if not raw:
        return {}

    # Find max per dimension for normalization
    dimensions = list(next(iter(raw.values())).keys()) if raw else []
    maxes: Dict[str, float] = {}
    for dim in dimensions:
        maxes[dim] = max((v.get(dim, 0) for v in raw.values()), default=1.0) or 1.0

    # Normalize
    result: Dict[str, Dict[str, float]] = {}
    for cid, vals in raw.items():
        result[cid] = {dim: round(vals.get(dim, 0) / maxes[dim], 2) for dim in dimensions}

    return result


def _compute_platform_agreement(
    enriched: List[Dict[str, Any]],
) -> Dict[str, Dict[str, float]]:
    """Compute pairwise Jaccard similarity between platform URL sets."""
    platform_urls: Dict[str, set[str]] = defaultdict(set)
    for cit in enriched:
        engine = cit.get("engine")
        url = cit.get("url")
        if engine and url:
            display = _map_engine_display(engine)
            platform_urls[display].add(str(url))

    platforms = sorted(platform_urls.keys())
    agreement: Dict[str, Dict[str, float]] = {}
    for p1 in platforms:
        agreement[p1] = {}
        for p2 in platforms:
            if p1 == p2:
                agreement[p1][p2] = 1.0
            else:
                s1, s2 = platform_urls[p1], platform_urls[p2]
                union = len(s1 | s2)
                agreement[p1][p2] = round(len(s1 & s2) / union, 2) if union else 0.0
    return agreement


def _compute_citation_exclusivity(
    enriched: List[Dict[str, Any]],
) -> Dict[str, Dict[str, int]]:
    """Per-cluster: count how many platforms cite each URL."""
    # URL -> set of engines, grouped by cluster
    cluster_url_engines: Dict[str, Dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set),
    )
    for cit in enriched:
        cname = cit.get("cluster_name")
        engine = cit.get("engine")
        url = cit.get("url")
        if cname and engine and url:
            cluster_url_engines[cname][str(url)].add(engine)

    result: Dict[str, Dict[str, int]] = {}
    for cname in sorted(cluster_url_engines.keys()):
        counts = {"all_4": 0, "three": 0, "two": 0, "one": 0}
        for url_engines in cluster_url_engines[cname].values():
            n = len(url_engines)
            if n >= 4:
                counts["all_4"] += 1
            elif n == 3:
                counts["three"] += 1
            elif n == 2:
                counts["two"] += 1
            else:
                counts["one"] += 1
        result[cname] = counts
    return result


# ── Endpoint 2.1: Summary ───────────────────────────────────────────


def get_summary(artifacts_root: Path, slug: str) -> GapSummaryResponse:
    """Build the executive overview response."""
    _validate_slug_dir(artifacts_root, slug)

    data = _load_analysis_data(artifacts_root, slug)
    report = _load_report_data(artifacts_root, slug)
    analysis = data.get("analysis", {})

    # SPA score — find the "all" cluster result
    spa = SPAScore()
    for sr in report.get("spa_results", analysis.get("spa_results", [])):
        cname = sr.get("cluster_name") or sr.get("cluster_id", "")
        if cname == "all" or cname == "":
            spa = SPAScore(
                t_stat=sr.get("t_stat", 0.0) or 0.0,
                p_value=sr.get("p_value", 0.0) or 0.0,
                effect=sr.get("effect", "unknown") or "unknown",
                mean_citation_similarity=sr.get("mean_citation_similarity", 0.0) or 0.0,
                mean_company_similarity=sr.get("mean_company_similarity", 0.0) or 0.0,
            )
            break

    # Proximity stats
    prox = report.get("proximity_stats", analysis.get("proximity_stats", {}))
    proximity_stats = ProximityStats(
        citation_similarity_mean=prox.get("citation_similarity_mean", 0.0) or 0.0,
        citation_similarity_median=prox.get("citation_similarity_median", 0.0) or 0.0,
        company_similarity_mean=prox.get("company_similarity_mean", 0.0) or 0.0,
        company_similarity_median=prox.get("company_similarity_median", 0.0) or 0.0,
    )
    spa.median_citation_similarity = proximity_stats.citation_similarity_median
    spa.median_company_similarity = proximity_stats.company_similarity_median

    # Classification counts
    gaps = report.get("gaps", analysis.get("gaps", []))
    counts = GapClassificationCounts()
    for gap in gaps:
        interp = gap.get("interpretation", "roughly_equal")
        if interp == "significant_gap":
            counts.significant_gap += 1
        elif interp == "gap_to_close":
            counts.gap_to_close += 1
        elif interp == "company_wins":
            counts.company_wins += 1
        else:
            counts.roughly_equal += 1

    # Cluster performance
    cluster_specs = data.get("cluster_specs", [])
    per_cluster_prox = prox.get("per_cluster", {})
    centroids = analysis.get("centroids", [])
    centroid_lookup = {c.get("cluster_name"): c for c in centroids}

    cluster_perf: List[ClusterPerformanceRow] = []
    for spec in cluster_specs:
        cname = spec.get("cluster_name", "")
        cprox = per_cluster_prox.get(cname, {})
        cluster_perf.append(
            ClusterPerformanceRow(
                cluster_id=spec.get("cluster_id"),
                cluster_name=cname,
                query_count=spec.get("query_count", 0),
                citation_count=spec.get("total_citations_analyzed", 0),
                avg_gap=0.0,  # computed below
                avg_citation_sim=cprox.get("mean", 0.0) or 0.0,
                avg_company_sim=0.0,
                structural_rates=spec.get("structural_rates", {}),
            )
        )

    # Compute per-cluster avg_gap from gaps
    cluster_gap_accum: Dict[str, List[float]] = defaultdict(list)
    for gap in gaps:
        cname = gap.get("cluster_name")
        g = gap.get("gap")
        if cname and g is not None:
            cluster_gap_accum[cname].append(g)
    for cp in cluster_perf:
        gap_vals = cluster_gap_accum.get(cp.cluster_name, [])
        if gap_vals:
            cp.avg_gap = round(sum(gap_vals) / len(gap_vals), 4)

    # Decision metrics
    dm = report.get("decision_metrics", analysis.get("decision_metrics", {}))

    return GapSummaryResponse(
        spa_score=spa,
        proximity_stats=proximity_stats,
        classification_counts=counts,
        cluster_performance=cluster_perf,
        total_queries=dm.get("total_queries", len(gaps)),
        total_citations=dm.get("total_citations", 0),
        average_gap=dm.get("avg_gap", 0.0) or 0.0,
        executive_summary=report.get("executive_summary", ""),
        recommendations=report.get("recommendations", []),
    )


# ── Endpoint 2.2: Queries ───────────────────────────────────────────


def get_queries(
    artifacts_root: Path,
    slug: str,
    *,
    cluster: Optional[str] = None,
    classification: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "gap_score",
    sort_dir: str = "desc",
    page: int = 1,
    page_size: int = 15,
) -> QueryListResponse:
    """Build paginated, filterable query list."""
    _validate_slug_dir(artifacts_root, slug)

    data = _load_analysis_data(artifacts_root, slug)
    report = _load_report_data(artifacts_root, slug)
    analysis = data.get("analysis", {})
    gaps = report.get("gaps", analysis.get("gaps", []))

    # Build platform index from enriched citations
    enriched = _load_enriched(artifacts_root, slug)
    platform_index = _build_platform_index(enriched)

    # Transform gaps into QueryRow objects
    rows: List[QueryRow] = []
    for gap in gaps:
        brief = gap.get("content_brief")
        exemplars_raw = gap.get("top_cited_exemplars", [])

        # Extract content brief fields (None-safe)
        target_words = _tuple_to_range(brief.get("target_word_count") if brief else None)
        reading_level = _tuple_to_range(
            brief.get("target_reading_level") if brief else None,
            default_min=0.0, default_max=0.0,
        )
        rec_headers = brief.get("recommended_header_count") if brief else None
        if isinstance(rec_headers, (list, tuple)) and len(rec_headers) >= 2:
            headers = rec_headers[1]  # take max
        elif isinstance(rec_headers, (int, float)):
            headers = int(rec_headers)
        else:
            headers = 0

        patterns = _extract_patterns(brief)

        # Top exemplar
        top_domain = None
        top_exemplar_sim = 0.0
        if exemplars_raw:
            top = exemplars_raw[0]
            top_domain = top.get("domain")
            top_exemplar_sim = top.get("similarity", 0.0) or 0.0

        # Build exemplar list
        exemplars: List[QueryExemplar] = []
        for ex in exemplars_raw[:3]:
            ss = ex.get("structural_signals") or {}
            exemplars.append(
                QueryExemplar(
                    similarity=ex.get("similarity", 0.0) or 0.0,
                    domain=ex.get("domain"),
                    url=str(ex.get("url", "")),
                    snippet=ex.get("snippet"),
                    authority_type=ex.get("authority_type"),
                    content_type=ss.get("content_type") or ex.get("content_type"),
                )
            )

        # Build content brief response
        content_brief_resp = None
        if brief:
            content_brief_resp = QueryContentBrief(
                target_word_count=target_words,
                target_reading_level=reading_level,
                recommended_header_count=headers,
                header_hierarchy=brief.get("header_hierarchy", {}),
                content_patterns=patterns,
                dominant_authority=brief.get("dominant_authority_type"),
                dominant_content_type=brief.get("dominant_content_type"),
                exemplars_analyzed=brief.get("exemplar_count", 0),
            )

        qid = gap.get("query_id", "")
        rows.append(
            QueryRow(
                query_id=qid,
                query_text=gap.get("query_text", ""),
                cluster_id=gap.get("cluster_id"),
                cluster_name=gap.get("cluster_name"),
                gap_score=gap.get("gap") or 0.0,
                classification=gap.get("interpretation", "roughly_equal"),
                company_sim=gap.get("best_company_similarity") or 0.0,
                citation_sim=gap.get("avg_citation_similarity") or 0.0,
                target_words=target_words,
                reading_level=reading_level,
                headers=headers,
                patterns=patterns,
                top_domain=top_domain,
                top_exemplar_sim=top_exemplar_sim,
                platform_citations=dict(platform_index.get(qid, {})),
                content_brief=content_brief_resp,
                top_exemplars=exemplars,
            )
        )

    # Apply filters
    filtered = rows
    if cluster:
        filtered = [r for r in filtered if r.cluster_name == cluster or r.cluster_id == cluster]
    if classification:
        filtered = [r for r in filtered if r.classification == classification]
    if search:
        search_lower = search.lower()
        filtered = [r for r in filtered if search_lower in r.query_text.lower()]

    total = len(filtered)

    # Sort — type-aware to prevent mixed str/int TypeError (CX-3)
    _STRING_SORT_FIELDS = {"query_text", "cluster_name"}
    _NUMERIC_SORT_FIELDS = {"gap_score", "company_sim", "citation_sim", "headers", "top_exemplar_sim"}
    _SORT_FIELDS = _STRING_SORT_FIELDS | _NUMERIC_SORT_FIELDS | {"classification"}
    if sort_by not in _SORT_FIELDS:
        sort_by = "gap_score"
    reverse = sort_dir != "asc"
    if sort_by == "classification":
        # Severity-ranked sort (PB-7)
        _RANK = {
            "significant_gap": 4, "gap_to_close": 3,
            "roughly_equal": 2, "company_wins": 1, "no_data": 0,
        }
        filtered.sort(key=lambda r: _RANK.get(str(getattr(r, "classification", "")), 0), reverse=reverse)
    elif sort_by in _STRING_SORT_FIELDS:
        filtered.sort(key=lambda r: str(getattr(r, sort_by, "") or ""), reverse=reverse)
    else:
        filtered.sort(key=lambda r: float(getattr(r, sort_by, 0) or 0), reverse=reverse)

    # Paginate
    total_pages = max(1, math.ceil(total / page_size))
    page = max(1, min(page, total_pages))  # Clamp to valid range (PB-9)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = filtered[start:end]

    return QueryListResponse(
        queries=page_items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ── Endpoint 2.3: Clusters ──────────────────────────────────────────


def get_clusters(artifacts_root: Path, slug: str) -> ClusterListResponse:
    """Build cluster specifications response."""
    _validate_slug_dir(artifacts_root, slug)

    data = _load_analysis_data(artifacts_root, slug)
    analysis = data.get("analysis", {})
    cluster_specs = data.get("cluster_specs", analysis.get("cluster_specs", []))
    centroids = analysis.get("centroids", [])

    # Build centroid lookup
    centroid_lookup: Dict[str, float] = {}
    for c in centroids:
        cname = c.get("cluster_name")
        dist = c.get("distance")
        if cname and dist is not None:
            centroid_lookup[cname] = dist

    clusters: List[ClusterSpecResponse] = []
    for spec in cluster_specs:
        cname = spec.get("cluster_name", "")
        wc_range = spec.get("word_count_range", [0, 0])

        clusters.append(
            ClusterSpecResponse(
                cluster_id=spec.get("cluster_id"),
                cluster_name=cname,
                query_count=spec.get("query_count", 0),
                citations_analyzed=spec.get("total_citations_analyzed", 0),
                centroid_distance=centroid_lookup.get(cname),
                min_similarity_threshold=spec.get("min_similarity_threshold"),
                word_count_range=_tuple_to_range(wc_range),
                required_elements=spec.get("required_elements", []),
                structural_rates=spec.get("structural_rates", {}),
                avg_word_count=spec.get("avg_word_count", 0.0),
                faq_rate=spec.get("faq_rate", 0.0),
                table_rate=spec.get("table_rate", 0.0),
                key_takeaways_rate=spec.get("key_takeaways_rate", 0.0),
                dominant_content_type=spec.get("dominant_content_type"),
                dominant_authority_type=spec.get("dominant_authority_type"),
                exemplar_themes=spec.get("exemplar_themes", []),
            )
        )

    return ClusterListResponse(clusters=clusters)


# ── Endpoint 2.4: Signals ───────────────────────────────────────────


def get_signals(artifacts_root: Path, slug: str) -> SignalAveragesResponse:
    """Build structural signal averages, correlations, and cluster patterns."""
    _validate_slug_dir(artifacts_root, slug)

    enriched = _load_enriched(artifacts_root, slug)
    data = _load_analysis_data(artifacts_root, slug)
    analysis = data.get("analysis", {})
    cluster_specs = data.get("cluster_specs", analysis.get("cluster_specs", []))

    signals = _compute_signal_averages(enriched)
    correlations = _compute_signal_correlations(enriched)
    cluster_patterns = _compute_cluster_patterns(enriched, cluster_specs)
    fingerprints = _compute_cluster_fingerprints(cluster_specs)

    return SignalAveragesResponse(
        signals=signals,
        correlations=correlations,
        cluster_patterns=cluster_patterns,
        cluster_fingerprints=fingerprints,
    )


# ── Endpoint 2.5: Platforms ─────────────────────────────────────────


def get_platforms(artifacts_root: Path, slug: str) -> PlatformListResponse:
    """Build per-platform citation breakdown with agreement and exclusivity."""
    _validate_slug_dir(artifacts_root, slug)

    enriched = _load_enriched(artifacts_root, slug)

    # Group by engine
    engine_data: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "domains": [],
            "sims": [],
            "cluster_counts": defaultdict(int),
            "domain_counter": Counter(),
        }
    )

    for cit in enriched:
        engine = cit.get("engine")
        if not engine:
            continue
        display = _map_engine_display(engine)
        ed = engine_data[display]
        domain = cit.get("domain")
        if domain:
            ed["domains"].append(domain)
            ed["domain_counter"][domain] += 1

        bp = cit.get("best_paragraphs", [])
        if bp and isinstance(bp[0], dict):
            sim = bp[0].get("similarity")
            if isinstance(sim, (int, float)):
                ed["sims"].append(sim)

        cname = cit.get("cluster_name")
        if cname:
            ed["cluster_counts"][cname] += 1

    platforms: List[PlatformSummaryResponse] = []
    for display_name in sorted(engine_data.keys()):
        ed = engine_data[display_name]
        per_cluster = dict(ed["cluster_counts"])
        unique = len(set(ed["domains"]))
        sims = ed["sims"]
        avg_sim = round(sum(sims) / len(sims), 4) if sims else 0.0
        mc = ed["domain_counter"].most_common(1)
        most_cited = mc[0][0] if mc else None

        # Best/worst cluster
        best_cluster = max(per_cluster, key=per_cluster.get, default=None) if per_cluster else None
        worst_cluster = min(per_cluster, key=per_cluster.get, default=None) if per_cluster else None

        platforms.append(
            PlatformSummaryResponse(
                name=display_name,
                total_citations=len(ed["domains"]),
                unique_domains=unique,
                avg_citation_sim=avg_sim,
                most_cited_domain=most_cited,
                best_cluster=best_cluster,
                worst_cluster=worst_cluster,
                per_cluster=per_cluster,
            )
        )

    agreement = _compute_platform_agreement(enriched)
    exclusivity = _compute_citation_exclusivity(enriched)

    return PlatformListResponse(
        platforms=platforms,
        agreement=agreement,
        citation_exclusivity=exclusivity,
    )


# ── Endpoint 2.6: Heatmap ───────────────────────────────────────────


def get_heatmap(artifacts_root: Path, slug: str) -> HeatmapResponse:
    """Build gap score heatmap grouped by cluster."""
    _validate_slug_dir(artifacts_root, slug)

    data = _load_analysis_data(artifacts_root, slug)
    report = _load_report_data(artifacts_root, slug)
    analysis = data.get("analysis", {})
    gaps = report.get("gaps", analysis.get("gaps", []))

    # Group by cluster
    cluster_map: Dict[str, List[HeatmapQuery]] = defaultdict(list)
    cluster_ids: Dict[str, Optional[str]] = {}
    min_gap = float("inf")
    max_gap = float("-inf")

    for gap in gaps:
        cname = gap.get("cluster_name", "Unknown")
        cid = gap.get("cluster_id")
        g = gap.get("gap") or 0.0
        interp = gap.get("interpretation", "roughly_equal")

        cluster_ids.setdefault(cname, cid)
        cluster_map[cname].append(
            HeatmapQuery(
                query_id=gap.get("query_id", ""),
                query_text=gap.get("query_text", ""),
                gap_score=g,
                classification=interp,
            )
        )
        if g < min_gap:
            min_gap = g
        if g > max_gap:
            max_gap = g

    if min_gap == float("inf"):
        min_gap = 0.0
    if max_gap == float("-inf"):
        max_gap = 0.0

    clusters: List[HeatmapCluster] = []
    for cname in sorted(cluster_map.keys()):
        queries = cluster_map[cname]
        queries.sort(key=lambda q: q.gap_score, reverse=True)
        avg_gap = sum(q.gap_score for q in queries) / len(queries) if queries else 0.0
        clusters.append(
            HeatmapCluster(
                cluster_name=cname,
                cluster_id=cluster_ids.get(cname),
                queries=queries,
                avg_gap=round(avg_gap, 4),
            )
        )

    return HeatmapResponse(
        clusters=clusters,
        min_gap=round(min_gap, 4),
        max_gap=round(max_gap, 4),
    )


# ── Endpoint 3.4: Embedding Projections ──────────────────────────────


def get_embedding_projection(
    artifacts_root: Path, slug: str, method: Literal["umap", "tsne"] = "umap",
) -> EmbeddingProjectionResponse:
    """Load pre-computed 2D embedding projection from s7 JSON output."""
    _validate_slug_dir(artifacts_root, slug)

    filename = f"visualizations/embedding_projections_{method}.json"
    data = _load_json_cached(artifacts_root, slug, filename)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Embedding projection '{method}' not found for '{slug}'. "
                "Run gap analysis pipeline first."
            ),
        )

    try:
        points = [EmbeddingPoint(**p) for p in data.get("points", [])]
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Malformed embedding projection data for '{slug}': {exc.error_count()} validation errors",
        )
    return EmbeddingProjectionResponse(
        method=data.get("method", method),
        point_count=len(points),
        points=points,
    )
