"""Response schemas for gap analysis data endpoints.

These models match the frontend TypeScript types in:
  - frontend-dashboard/src/types/gap-analysis.ts
  - frontend-dashboard/src/app/(dashboard)/signal-analysis/data/sample-data.ts
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── 2.1 Summary ─────────────────────────────────────────────────────


class SPAScore(BaseModel):
    """Semantic Proximity Analysis score (aggregate t-test result)."""

    t_stat: float = 0.0
    p_value: float = 0.0
    effect: str = "unknown"
    mean_citation_similarity: float = 0.0
    mean_company_similarity: float = 0.0
    median_citation_similarity: float = 0.0
    median_company_similarity: float = 0.0


class ProximityStats(BaseModel):
    """Aggregate proximity statistics (citation vs company)."""

    citation_similarity_mean: float = 0.0
    citation_similarity_median: float = 0.0
    company_similarity_mean: float = 0.0
    company_similarity_median: float = 0.0


class GapClassificationCounts(BaseModel):
    """Count of queries per gap classification bucket."""

    significant_gap: int = 0
    gap_to_close: int = 0
    roughly_equal: int = 0
    company_wins: int = 0


class ClusterPerformanceRow(BaseModel):
    """Per-cluster performance summary for the overview heatmap."""

    cluster_id: Optional[str] = None
    cluster_name: str
    query_count: int = 0
    citation_count: int = 0
    avg_gap: float = 0.0
    avg_citation_sim: float = 0.0
    avg_company_sim: float = 0.0
    structural_rates: Dict[str, float] = Field(default_factory=dict)


class GapSummaryResponse(BaseModel):
    """GET /summary — executive overview for the Overview tab."""

    spa_score: SPAScore = Field(default_factory=SPAScore)
    proximity_stats: ProximityStats = Field(default_factory=ProximityStats)
    classification_counts: GapClassificationCounts = Field(
        default_factory=GapClassificationCounts,
    )
    cluster_performance: List[ClusterPerformanceRow] = Field(default_factory=list)
    total_queries: int = 0
    total_citations: int = 0
    company_cited_count: int = 0
    average_gap: float = 0.0
    executive_summary: str = ""
    recommendations: List[Dict[str, Any]] = Field(default_factory=list)


# ── 2.2 Queries ─────────────────────────────────────────────────────


class QueryContentBrief(BaseModel):
    """Content brief derived from citation exemplars for a single query gap."""

    target_word_count: Dict[str, int] = Field(
        default_factory=lambda: {"min": 0, "max": 0},
    )
    target_reading_level: Dict[str, float] = Field(
        default_factory=lambda: {"min": 0.0, "max": 0.0},
    )
    recommended_header_count: int = 0
    header_hierarchy: Dict[str, int] = Field(default_factory=dict)
    content_patterns: List[str] = Field(default_factory=list)
    dominant_authority: Optional[str] = None
    dominant_content_type: Optional[str] = None
    exemplars_analyzed: int = 0


class QueryExemplar(BaseModel):
    """Top-cited exemplar page for a query gap."""

    similarity: float = 0.0
    domain: Optional[str] = None
    url: str = ""
    snippet: Optional[str] = None
    authority_type: Optional[str] = None
    content_type: Optional[str] = None


class QueryRow(BaseModel):
    """Single query in the Query Intelligence table."""

    query_id: str
    query_text: str
    cluster_id: Optional[str] = None
    cluster_name: Optional[str] = None
    gap_score: float = 0.0
    classification: str = "roughly_equal"
    company_sim: float = 0.0
    citation_sim: float = 0.0
    target_words: Dict[str, int] = Field(
        default_factory=lambda: {"min": 0, "max": 0},
    )
    reading_level: Dict[str, float] = Field(
        default_factory=lambda: {"min": 0.0, "max": 0.0},
    )
    headers: int = 0
    patterns: List[str] = Field(default_factory=list)
    top_domain: Optional[str] = None
    top_exemplar_sim: float = 0.0
    platform_citations: Dict[str, int] = Field(default_factory=dict)
    company_cited: bool = False
    company_cited_platforms: List[str] = Field(default_factory=list)
    content_brief: Optional[QueryContentBrief] = None
    top_exemplars: List[QueryExemplar] = Field(default_factory=list)


class QueryListResponse(BaseModel):
    """GET /queries — paginated query list for Query Intelligence tab."""

    queries: List[QueryRow] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 15
    total_pages: int = 0


# ── 2.3 Clusters ────────────────────────────────────────────────────


class ClusterSpecResponse(BaseModel):
    """Cluster content specification with structural rates and themes."""

    cluster_id: Optional[str] = None
    cluster_name: str
    query_count: int = 0
    citations_analyzed: int = 0
    centroid_distance: Optional[float] = None
    min_similarity_threshold: Optional[float] = None
    word_count_range: Dict[str, int] = Field(
        default_factory=lambda: {"min": 0, "max": 0},
    )
    required_elements: List[str] = Field(default_factory=list)
    structural_rates: Dict[str, float] = Field(default_factory=dict)
    avg_word_count: float = 0.0
    faq_rate: float = 0.0
    table_rate: float = 0.0
    key_takeaways_rate: float = 0.0
    dominant_content_type: Optional[str] = None
    dominant_authority_type: Optional[str] = None
    exemplar_themes: List[str] = Field(default_factory=list)


class ClusterListResponse(BaseModel):
    """GET /clusters — cluster specifications for Content Briefs tab."""

    clusters: List[ClusterSpecResponse] = Field(default_factory=list)


# ── 2.4 Signals ─────────────────────────────────────────────────────


class SignalAverageRow(BaseModel):
    """Structural signal average: citation vs company comparison."""

    signal: str
    category: str = ""
    citation_avg: float = 0.0
    company_avg: float = 0.0
    unit: str = ""
    recommendation: str = ""


class SignalCorrelationRow(BaseModel):
    """Signal importance ranking (correlation with citation similarity)."""

    signal: str
    correlation: float = 0.0
    category: str = ""


class ClusterPatternRow(BaseModel):
    """Per-cluster content pattern adoption rates."""

    cluster_id: str
    cluster_name: str
    faq: float = 0.0
    definition_opening: float = 0.0
    key_takeaways: float = 0.0
    comparison_table: float = 0.0
    step_by_step: float = 0.0
    research_refs: float = 0.0
    expert_quotes: float = 0.0


class SignalAveragesResponse(BaseModel):
    """GET /signals — structural signal analysis for Structural Signals tab."""

    signals: List[SignalAverageRow] = Field(default_factory=list)
    correlations: List[SignalCorrelationRow] = Field(default_factory=list)
    cluster_patterns: List[ClusterPatternRow] = Field(default_factory=list)
    cluster_fingerprints: Dict[str, Dict[str, float]] = Field(default_factory=dict)


# ── 2.5 Platforms ───────────────────────────────────────────────────


class PlatformSummaryResponse(BaseModel):
    """Per-platform citation breakdown."""

    name: str
    total_citations: int = 0
    unique_domains: int = 0
    avg_citation_sim: float = 0.0
    most_cited_domain: Optional[str] = None
    best_cluster: Optional[str] = None
    worst_cluster: Optional[str] = None
    per_cluster: Dict[str, int] = Field(default_factory=dict)


class PlatformListResponse(BaseModel):
    """GET /platforms — platform intelligence for Platform Intelligence tab."""

    platforms: List[PlatformSummaryResponse] = Field(default_factory=list)
    agreement: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    citation_exclusivity: Dict[str, Dict[str, int]] = Field(default_factory=dict)


# ── 2.6 Heatmap ─────────────────────────────────────────────────────


class HeatmapQuery(BaseModel):
    """Query entry in the heatmap cluster group."""

    query_id: str
    query_text: str
    gap_score: float = 0.0
    classification: str = "roughly_equal"


class HeatmapCluster(BaseModel):
    """Cluster group in the heatmap matrix."""

    cluster_name: str
    cluster_id: Optional[str] = None
    queries: List[HeatmapQuery] = Field(default_factory=list)
    avg_gap: float = 0.0


class HeatmapResponse(BaseModel):
    """GET /heatmap — gap score matrix grouped by cluster."""

    clusters: List[HeatmapCluster] = Field(default_factory=list)
    min_gap: float = 0.0
    max_gap: float = 0.0


# ── 2.7 Cluster Profiles (Embedding Lab) ──────────────────────────


class ClusterDomainEntry(BaseModel):
    """Domain in the per-cluster leaderboard."""

    domain: str
    citations: int = 0
    is_company: bool = False
    share: float = 0.0
    type: str = "authority"  # direct | mindshare | authority | company


class ClusterProfileResponse(BaseModel):
    """Rich cluster profile for Embedding Lab territory intelligence."""

    cluster_id: str
    cluster_name: str
    query_count: int = 0
    total_citations: int = 0
    unique_domains: int = 0
    company_citations: int = 0
    company_share: float = 0.0
    company_rank: Optional[int] = None
    presence: str = "none"  # none | minimal | low | moderate | strong
    avg_word_count: float = 0.0
    word_count_range: List[int] = Field(default_factory=lambda: [0, 0])
    dominant_content_type: Optional[str] = None
    dominant_authority_type: Optional[str] = None
    structural_rates: Dict[str, float] = Field(default_factory=dict)
    faq_rate: float = 0.0
    table_rate: float = 0.0
    required_elements: List[str] = Field(default_factory=list)
    exemplar_themes: List[str] = Field(default_factory=list)
    authority_signals: Dict[str, int] = Field(default_factory=dict)
    proximity: Optional[Dict[str, float]] = None
    engine_breakdown: Dict[str, int] = Field(default_factory=dict)
    top_domains: List[ClusterDomainEntry] = Field(default_factory=list)


class ClusterProfileListResponse(BaseModel):
    """GET /cluster-profiles — rich cluster profiles for Embedding Lab."""

    profiles: Dict[str, ClusterProfileResponse] = Field(default_factory=dict)


# ── 2.8 Territory Gap Queries (Embedding Lab) ─────────────────────


class TerritoryGapExemplar(BaseModel):
    """Rich exemplar with structural signals for territory intelligence."""

    domain: str = ""
    url: str = ""
    similarity: float = 0.0
    content_type: Optional[str] = None
    authority_type: Optional[str] = None
    word_count: Optional[int] = None
    header_count: Optional[int] = None
    has_faq: bool = False
    has_tables: bool = False
    reading_level: Optional[float] = None
    list_item_count: int = 0
    stat_count: int = 0
    citation_count: int = 0


class TerritoryCompanySignals(BaseModel):
    """Company page structural signals subset."""

    word_count: Optional[int] = None
    header_count: Optional[int] = None
    has_faq: bool = False
    has_tables: bool = False
    reading_level: Optional[float] = None
    list_item_count: int = 0


class TerritoryContentBrief(BaseModel):
    """Winning content profile for a gap query."""

    word_count_range: Optional[List[int]] = None
    reading_level_range: Optional[List[float]] = None
    header_count_range: Optional[List[int]] = None
    header_hierarchy: Optional[Dict[str, int]] = None
    has_faq: float = 0.0
    has_tables: float = 0.0
    has_definition: float = 0.0
    has_key_takeaways: float = 0.0
    has_step_by_step: float = 0.0
    dominant_content_type: Optional[str] = None
    dominant_authority_type: Optional[str] = None
    data_density: Optional[float] = None
    citation_density: Optional[float] = None


class TerritoryGapQuery(BaseModel):
    """Gap query with rich exemplars for Embedding Lab."""

    id: str
    query: str
    cluster: str  # display name
    cluster_id: str  # slugified
    gap: float = 0.0
    classification: str = "roughly_equal"
    company_cited: bool = False
    company_url: Optional[str] = None
    company_similarity: Optional[float] = None
    avg_citation_similarity: float = 0.0
    exemplars: List[TerritoryGapExemplar] = Field(default_factory=list)
    company_signals: Optional[TerritoryCompanySignals] = None
    content_brief: Optional[TerritoryContentBrief] = None


class TerritoryProximityStats(BaseModel):
    """Global proximity statistics for territory intelligence."""

    citation_mean: float = 0.0
    citation_median: float = 0.0
    company_mean: float = 0.0
    company_median: float = 0.0
    similarity_gap: float = 0.0


class TerritorySPA(BaseModel):
    """Semantic Proximity Analysis result for territory intelligence."""

    t_stat: float = 0.0
    p_value: float = 0.0
    effect: str = "unknown"


class TerritoryGapsResponse(BaseModel):
    """GET /territory-gaps — gap queries with rich signals for Embedding Lab."""

    gaps: List[TerritoryGapQuery] = Field(default_factory=list)
    proximity_stats: TerritoryProximityStats = Field(
        default_factory=TerritoryProximityStats,
    )
    spa: TerritorySPA = Field(default_factory=TerritorySPA)
    per_cluster_proximity: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    total_gaps: int = 0
    uncovered_queries: int = 0
