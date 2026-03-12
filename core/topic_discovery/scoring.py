"""Algorithmic subdomain scoring & persona affinity — zero LLM calls.

After HITL-1 approves the taxonomy, this module computes:
1. A priority score for every subdomain using up to 5 available signals.
2. A persona affinity index mapping each persona to subdomains.

All computations are pure Python + embedding similarity.  No LLM calls.
"""
from __future__ import annotations

import json
import logging
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

from core.config.settings import settings
from core.models.topic_discovery import (
    PersonaAffinityIndex,
    PersonaSubdomainEntry,
    ScoredSubdomainList,
    SubdomainNode,
    SubdomainScore,
    TaxonomyTree,
)
from core.shared_tools.math_utils import cosine_similarity

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Default weight configuration
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS: Dict[str, float] = {
    "source_confidence": 0.30,
    "content_coverage": 0.20,
    "gap_severity": 0.25,
    "competitive_density": 0.0,  # Source C placeholder — set to 0 until implemented
    "persona_breadth": 0.25,
}

DEFAULT_PERSONA_AFFINITY_WEIGHTS: Dict[str, float] = {
    "provenance": 0.6,
    "embedding": 0.4,
}

# Dimension weights for topic priority scoring
BUYER_WEIGHTS: Dict[str, float] = {"tofu": 0.6, "mofu": 0.8, "bofu": 1.0}
INTENT_WEIGHTS: Dict[str, float] = {
    "informational": 0.5,
    "commercial": 0.8,
    "transactional": 1.0,
    "navigational": 0.2,
}


# ---------------------------------------------------------------------------
# Individual scoring signals
# ---------------------------------------------------------------------------


def _score_source_confidence(node: SubdomainNode) -> float:
    """Signal 1: How many of 4 sources discovered this subdomain?

    Manually-added nodes (empty provenance) get neutral score 0.5.
    Range: 0.25 – 1.0  (always available).
    """
    if not node.source_provenance:
        return 0.5
    return sum(1 for v in node.source_provenance.values() if v) / 4.0


def _score_content_coverage(
    subdomain_embedding: List[float],
    page_embeddings: List[List[float]],
    similarity_threshold: float,
) -> Optional[float]:
    """Signal 2: Existing content coverage from site audit.

    Zero matching pages → 1.0 (greenfield = high opportunity).
    Many matching pages → lower score (diminishing returns, saturates at 10).
    Returns None if no site audit data available.
    """
    if not page_embeddings or not subdomain_embedding:
        return None
    matches = sum(
        1
        for pe in page_embeddings
        if cosine_similarity(subdomain_embedding, pe) > similarity_threshold
    )
    return max(0.0, 1.0 - (matches / 10.0))


def _score_gap_severity(
    subdomain_embedding: List[float],
    gap_query_embeddings: List[List[float]],
    gap_scores: List[float],
    similarity_threshold: float,
) -> Optional[float]:
    """Signal 3: Average gap score for semantically aligned queries.

    Higher gap = client underperforming = higher priority.
    Returns None if no gap analysis data available.
    """
    if not gap_query_embeddings or not gap_scores or not subdomain_embedding:
        return None
    aligned_scores = [
        score
        for emb, score in zip(gap_query_embeddings, gap_scores)
        if cosine_similarity(subdomain_embedding, emb) > similarity_threshold
    ]
    if not aligned_scores:
        return None
    return mean(aligned_scores)


def _score_competitive_density(
    subdomain_embedding: List[float],
    competitor_url_embeddings: List[List[float]],
    similarity_threshold: float,
) -> Optional[float]:
    """Signal 4: Count competitor pages aligned with this subdomain.

    More competitor content = commercially important = higher score.
    Saturates at 20+ pages.  Returns None if no competitor data.
    """
    if not competitor_url_embeddings or not subdomain_embedding:
        return None
    matches = sum(
        1
        for ce in competitor_url_embeddings
        if cosine_similarity(subdomain_embedding, ce) > similarity_threshold
    )
    return min(1.0, matches / 20.0)


def _score_persona_breadth(node: SubdomainNode) -> float:
    """Signal 5: Broader provenance = broader audience appeal.

    Source B provenance gets a 0.15 bonus (persona-derived = broader reach).
    Range: 0.0 – 1.0  (always available).
    """
    if not node.source_provenance:
        return 0.5  # neutral for manually-added nodes
    source_count = sum(1 for v in node.source_provenance.values() if v)
    has_persona = node.source_provenance.get("source_b", False)
    base = source_count / 4.0
    return min(1.0, base + (0.15 if has_persona else 0.0))


# ---------------------------------------------------------------------------
# Combination & normalisation
# ---------------------------------------------------------------------------


def _normalize_and_combine(
    signal_scores: Dict[str, Optional[float]],
    weights: Dict[str, float],
) -> Tuple[float, Dict[str, float], Dict[str, float], List[str]]:
    """Exclude unavailable signals, renormalise weights, compute weighted sum.

    Returns (composite, used_scores, used_weights, available_signal_names).
    """
    available: Dict[str, float] = {
        k: v for k, v in signal_scores.items() if v is not None
    }
    if not available:
        return 0.0, {}, {}, []

    # Filter weights to available signals only
    raw_weights = {k: weights.get(k, 0.0) for k in available}
    total_w = sum(raw_weights.values())
    if total_w == 0:
        return 0.0, {}, {}, list(available.keys())

    norm_weights = {k: w / total_w for k, w in raw_weights.items()}
    composite = sum(available[k] * norm_weights[k] for k in available)
    return composite, available, norm_weights, list(available.keys())


# ---------------------------------------------------------------------------
# Flatten taxonomy helper
# ---------------------------------------------------------------------------


def _flatten_nodes(nodes: List[SubdomainNode]) -> List[SubdomainNode]:
    """Recursively flatten taxonomy tree into a flat list of leaf+branch nodes."""
    result: List[SubdomainNode] = []
    for n in nodes:
        result.append(n)
        if n.children:
            result.extend(_flatten_nodes(n.children))
    return result


# ---------------------------------------------------------------------------
# Main scoring entry point
# ---------------------------------------------------------------------------


def _load_weights_config() -> Dict[str, float]:
    """Load scoring weights from settings (JSON string) with fallback."""
    try:
        w = json.loads(settings.topic_discovery_scoring_weights)
        if isinstance(w, dict):
            return w
    except (json.JSONDecodeError, AttributeError):
        pass
    return dict(DEFAULT_WEIGHTS)


async def compute_subdomain_scores(
    taxonomy: TaxonomyTree,
    *,
    site_audit_pages: Optional[List[Dict[str, Any]]] = None,
    gap_query_embeddings: Optional[List[List[float]]] = None,
    gap_scores: Optional[List[float]] = None,
    competitor_url_embeddings: Optional[List[List[float]]] = None,
    subdomain_embeddings: Optional[Dict[str, List[float]]] = None,
    page_embeddings: Optional[List[List[float]]] = None,
    weights_config: Optional[Dict[str, float]] = None,
) -> ScoredSubdomainList:
    """Score all subdomains in the taxonomy using available signals.

    Zero LLM calls.  Embedding vectors should be pre-computed by the caller.

    Args:
        taxonomy: Approved taxonomy tree.
        site_audit_pages: Page dicts from site audit (optional).
        gap_query_embeddings: Embeddings for gap-analysis queries (optional).
        gap_scores: Float gap scores aligned with gap_query_embeddings (optional).
        competitor_url_embeddings: Embeddings for competitor URLs (optional).
        subdomain_embeddings: Pre-computed {subdomain_id: embedding} map.
        page_embeddings: Embeddings for site-audit page titles (optional).
        weights_config: Override scoring weights.

    Returns:
        ScoredSubdomainList with ranked subdomain scores.
    """
    weights = weights_config or _load_weights_config()
    threshold = settings.topic_discovery_scoring_similarity_threshold
    flat = _flatten_nodes(taxonomy.root_nodes)

    scores: List[SubdomainScore] = []
    for node in flat:
        sd_emb = (subdomain_embeddings or {}).get(node.id, [])

        raw_signals: Dict[str, Optional[float]] = {
            "source_confidence": _score_source_confidence(node),
            "content_coverage": _score_content_coverage(
                sd_emb, page_embeddings or [], threshold
            ),
            "gap_severity": _score_gap_severity(
                sd_emb, gap_query_embeddings or [], gap_scores or [], threshold
            ),
            "competitive_density": _score_competitive_density(
                sd_emb, competitor_url_embeddings or [], threshold
            ),
            "persona_breadth": _score_persona_breadth(node),
        }

        composite, used_scores, used_weights, available = _normalize_and_combine(
            raw_signals, weights,
        )

        scores.append(
            SubdomainScore(
                subdomain_id=node.id,
                subdomain_name=node.name,
                composite_score=round(composite, 4),
                signal_scores={k: round(v, 4) for k, v in used_scores.items()},
                signal_weights={k: round(v, 4) for k, v in used_weights.items()},
                signals_available=available,
            )
        )

    # Sort descending by composite score, tie-break alphabetical by name
    scores.sort(key=lambda s: (-s.composite_score, s.subdomain_name))
    for i, sc in enumerate(scores):
        sc.rank = i + 1

    return ScoredSubdomainList(
        scores=scores,
        total_scored=len(scores),
        signals_used=list(weights.keys()),
        weights_config=weights,
    )


# ---------------------------------------------------------------------------
# Persona affinity computation
# ---------------------------------------------------------------------------


def _load_persona_affinity_weights() -> Dict[str, float]:
    """Load persona affinity weights from settings."""
    try:
        w = json.loads(settings.topic_discovery_persona_affinity_weights)
        if isinstance(w, dict):
            return w
    except (json.JSONDecodeError, AttributeError):
        pass
    return dict(DEFAULT_PERSONA_AFFINITY_WEIGHTS)


async def compute_persona_affinity_index(
    taxonomy: TaxonomyTree,
    subdomain_embeddings: Dict[str, List[float]],
    persona_mds_by_id: Dict[str, str],
    persona_embeddings: Dict[str, List[float]],
    source_b_persona_map: Dict[str, List[str]],
) -> PersonaAffinityIndex:
    """Compute persona-subdomain affinity — zero LLM calls.

    Uses two signals:
    - Source B provenance (weight 0.6): did this persona's brainstorm surface
      this subdomain?
    - Embedding similarity (weight 0.4): cosine sim between persona profile
      embedding and subdomain description embedding.

    Args:
        taxonomy: Approved taxonomy tree.
        subdomain_embeddings: {subdomain_id: embedding}.
        persona_mds_by_id: {persona_id: markdown_content}.
        persona_embeddings: {persona_id: embedding} (first 500 words of profile).
        source_b_persona_map: {subdomain_name_lower: [persona_ids]} from S1.

    Returns:
        PersonaAffinityIndex with per-persona sorted entries.
    """
    aff_weights = _load_persona_affinity_weights()
    prov_w = aff_weights.get("provenance", 0.6)
    emb_w = aff_weights.get("embedding", 0.4)

    flat = _flatten_nodes(taxonomy.root_nodes)
    entries: Dict[str, List[PersonaSubdomainEntry]] = {}

    for pid in persona_mds_by_id:
        persona_emb = persona_embeddings.get(pid, [])
        pid_entries: List[PersonaSubdomainEntry] = []

        for node in flat:
            sd_emb = subdomain_embeddings.get(node.id, [])

            # Signal 1: Source B provenance
            sd_name_lower = node.name.lower().strip()
            persona_ids_for_sd = source_b_persona_map.get(sd_name_lower, [])
            prov_signal = 1.0 if pid in persona_ids_for_sd else 0.0

            # Signal 2: Embedding similarity
            if persona_emb and sd_emb:
                emb_signal = max(0.0, cosine_similarity(persona_emb, sd_emb))
            else:
                emb_signal = 0.0

            affinity = prov_w * prov_signal + emb_w * emb_signal

            # Determine provenance label
            if prov_signal > 0 and emb_signal > 0.3:
                provenance = "both"
            elif prov_signal > 0:
                provenance = "source_b"
            else:
                provenance = "embedding"

            pid_entries.append(
                PersonaSubdomainEntry(
                    subdomain_id=node.id,
                    subdomain_name=node.name,
                    affinity_score=round(affinity, 4),
                    provenance=provenance,
                )
            )

        # Sort by affinity descending
        pid_entries.sort(key=lambda e: -e.affinity_score)
        entries[pid] = pid_entries

    return PersonaAffinityIndex(
        persona_entries=entries,
        total_personas=len(persona_mds_by_id),
        total_subdomains=len(flat),
    )


# ---------------------------------------------------------------------------
# Topic-level priority scoring (algorithmic, post-expansion)
# ---------------------------------------------------------------------------


def compute_topic_priority(
    buyer_stage: str,
    intent_type: str,
    subdomain_composite_score: float,
    *,
    buyer_weights: Optional[Dict[str, float]] = None,
    intent_weights: Optional[Dict[str, float]] = None,
) -> Tuple[float, Dict[str, float]]:
    """Compute priority score for a single topic assignment.

    Formula: priority = ((buyer_weight + intent_weight) / 2) * subdomain_score

    Returns (priority_score, priority_factors dict).
    """
    bw = (buyer_weights or BUYER_WEIGHTS).get(buyer_stage, 0.5)
    iw = (intent_weights or INTENT_WEIGHTS).get(intent_type, 0.5)
    base = (bw + iw) / 2.0
    priority = round(base * subdomain_composite_score, 4)
    return priority, {
        "buyer_weight": round(bw, 4),
        "intent_weight": round(iw, 4),
        "subdomain_score": round(subdomain_composite_score, 4),
        "base_weight": round(base, 4),
    }
