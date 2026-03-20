"""Deterministic mapping from Topic Discovery dimensions to Gap Analysis clusters.

Maps buyer_stage × intent_type → C1-C9 query clusters. Pure data module
with zero LLM calls. Used by ``generate_queries_from_topics()`` in S2.

The mapping table encodes:
  - 6 valid cells (tofu×info, tofu×commercial, mofu×info, mofu×commercial,
    bofu×commercial, bofu×transactional)
  - 6 excluded cells (return None → skip query generation)

Each valid cell specifies primary clusters (3-5 queries), secondary clusters
(1-2 queries), and a queries_range for per-topic budget.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ClusterMapping:
    """Mapping result for a single buyer_stage × intent_type cell.

    Attributes:
        primary: Cluster IDs that receive the majority of queries (3-5).
        secondary: Cluster IDs that receive 1-2 supplementary queries.
        queries_range: (min, max) total queries to generate for this cell.
        brand_rule: Human-readable brand name policy for prompt injection.
    """

    primary: Tuple[str, ...] = ()
    secondary: Tuple[str, ...] = ()
    queries_range: Tuple[int, int] = (3, 5)
    brand_rule: str = "no_brand_names"


# ---------------------------------------------------------------------------
# Cluster metadata (for prompt construction)
# ---------------------------------------------------------------------------

CLUSTER_NAMES: Dict[str, str] = {
    "C1": "Mechanism",
    "C2": "Boundary",
    "C3": "Category Comparison",
    "C4": "Decision Criteria",
    "C5": "Definition",
    "C6": "Problem/Awareness",
    "C7": "Best-of/Consideration",
    "C8": "Branded Evaluation",
    "C9": "Feature Verification",
}

CLUSTER_INTENT_PATTERNS: Dict[str, str] = {
    "C1": "How does X technology work?",
    "C2": "Where does X not work?",
    "C3": "X vs Y (categories, not brands)",
    "C4": "What to evaluate when choosing X?",
    "C5": "What is X?",
    "C6": "Why is X a problem?",
    "C7": "Best X for Y use case",
    "C8": "Competitor-name alternatives",
    "C9": "Does X support Y?",
}

CLUSTER_BRAND_POLICY: Dict[str, str] = {
    "C1": "no_brand_names",
    "C2": "brand_for_known_limitations_only",
    "C3": "no_brand_names",
    "C4": "no_brand_names",
    "C5": "no_brand_names",
    "C6": "no_brand_names",
    "C7": "no_brand_names",
    "C8": "brand_names_required",
    "C9": "no_brand_names",
}


# ---------------------------------------------------------------------------
# The Mapping Table
# ---------------------------------------------------------------------------

_CLUSTER_MAP: Dict[Tuple[str, str], ClusterMapping] = {
    # Cell 1: TOFU × Informational
    # Early-stage buyer educating themselves on the problem space
    ("tofu", "informational"): ClusterMapping(
        primary=("C5", "C6"),
        secondary=("C1",),
        queries_range=(5, 8),
        brand_rule="no_brand_names",
    ),
    # Cell 2: TOFU × Commercial
    # Early-stage buyer starting to explore solution categories
    ("tofu", "commercial"): ClusterMapping(
        primary=("C7",),
        secondary=("C6",),
        queries_range=(3, 5),
        brand_rule="no_brand_names",
    ),
    # Cell 3: MOFU × Informational
    # Buyer evaluating how specific approaches work and where they fail
    ("mofu", "informational"): ClusterMapping(
        primary=("C1", "C2"),
        secondary=("C4",),
        queries_range=(5, 8),
        brand_rule="no_brand_names",
    ),
    # Cell 4: MOFU × Commercial
    # Buyer actively comparing solution categories and approaches
    ("mofu", "commercial"): ClusterMapping(
        primary=("C3", "C7"),
        secondary=("C4",),
        queries_range=(4, 7),
        brand_rule="no_brand_names",
    ),
    # Cell 5: BOFU × Commercial
    # Buyer evaluating specific vendors and making final selection criteria
    ("bofu", "commercial"): ClusterMapping(
        primary=("C8", "C4"),
        secondary=("C3",),
        queries_range=(4, 6),
        brand_rule="brand_names_required_for_c8",
    ),
    # Cell 6: BOFU × Transactional
    # Buyer verifying specific features before purchase decision
    ("bofu", "transactional"): ClusterMapping(
        primary=("C9", "C8"),
        secondary=(),
        queries_range=(3, 5),
        brand_rule="brand_names_required_for_c8",
    ),
}

# Excluded combinations — these produce no useful queries
_EXCLUDED_COMBOS: Dict[Tuple[str, str], str] = {
    ("tofu", "transactional"): "Awareness-stage buyers are not ready to transact",
    ("tofu", "navigational"): "Awareness-stage buyers are not searching for specific brands",
    ("mofu", "navigational"): "Consideration-stage navigational queries are too brand-specific",
    ("mofu", "transactional"): "Consideration-stage buyers are evaluating, not purchasing",
    ("bofu", "informational"): "Decision-stage buyers don't need basic educational content",
    ("bofu", "navigational"): "Navigational queries have no content strategy value",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_cluster_mapping(
    buyer_stage: str, intent_type: str
) -> Optional[ClusterMapping]:
    """Look up the cluster mapping for a buyer_stage × intent_type cell.

    Returns ``None`` for excluded combinations (caller should skip query gen).
    Normalizes inputs to lowercase for robustness.
    """
    key = (buyer_stage.lower().strip(), intent_type.lower().strip())
    return _CLUSTER_MAP.get(key)


def is_excluded_combo(buyer_stage: str, intent_type: str) -> bool:
    """Check if a buyer_stage × intent_type combination is excluded."""
    key = (buyer_stage.lower().strip(), intent_type.lower().strip())
    return key in _EXCLUDED_COMBOS


def get_exclusion_reason(buyer_stage: str, intent_type: str) -> Optional[str]:
    """Return the human-readable reason a combination is excluded, or None."""
    key = (buyer_stage.lower().strip(), intent_type.lower().strip())
    return _EXCLUDED_COMBOS.get(key)


def get_all_valid_cells() -> List[Tuple[str, str]]:
    """Return all valid (buyer_stage, intent_type) cells."""
    return list(_CLUSTER_MAP.keys())


def get_all_excluded_cells() -> List[Tuple[str, str]]:
    """Return all excluded (buyer_stage, intent_type) cells."""
    return list(_EXCLUDED_COMBOS.keys())


def get_cluster_name(cluster_id: str) -> str:
    """Return human-readable cluster name for a cluster ID."""
    return CLUSTER_NAMES.get(cluster_id, cluster_id)


def get_cluster_brand_policy(cluster_id: str) -> str:
    """Return brand name policy for a cluster ID."""
    return CLUSTER_BRAND_POLICY.get(cluster_id, "no_brand_names")
