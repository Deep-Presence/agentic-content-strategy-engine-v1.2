from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl


# ---------------------------------------------------------------------------
# Site-Tree Discovery Models
# ---------------------------------------------------------------------------


class DiscoverySource(str, Enum):
    """How a URL was discovered during site crawling."""

    SITEMAP = "sitemap"
    SITEMAP_INDEX = "sitemap_index"
    ROBOTS_TXT = "robots_txt"
    BFS_CRAWL = "bfs_crawl"
    CANONICAL = "canonical"
    HREFLANG = "hreflang"
    RSS_FEED = "rss_feed"
    SEED_URL = "seed_url"
    REDIRECT = "redirect"


class DiscoveredPage(BaseModel):
    """Flat representation of a single discovered page."""

    url: str
    normalized_url: str
    title: Optional[str] = None
    h1: Optional[str] = None
    meta_description: Optional[str] = None
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    discovery_source: DiscoverySource
    depth: int = 0
    parent_url: Optional[str] = None
    canonical_url: Optional[str] = None
    hreflang_alternates: Dict[str, str] = Field(default_factory=dict)
    last_modified: Optional[str] = None
    change_frequency: Optional[str] = None
    priority: Optional[float] = None
    word_count: Optional[int] = None
    has_content: bool = True


class SiteTreeNode(BaseModel):
    """Tree node for hierarchical site structure."""

    url: str
    title: Optional[str] = None
    path_segment: str = ""
    discovery_source: DiscoverySource = DiscoverySource.BFS_CRAWL
    depth: int = 0
    status_code: Optional[int] = None
    children: List[SiteTreeNode] = Field(default_factory=list)
    page_count_below: int = 0


class SiteDiscoveryResult(BaseModel):
    """Complete output of the site-tree discovery process."""

    domain: str
    base_url: str
    total_pages_discovered: int = 0
    discovery_stats: Dict[str, int] = Field(default_factory=dict)
    pages: List[DiscoveredPage] = Field(default_factory=list)
    site_tree: Optional[SiteTreeNode] = None
    sitemaps_found: List[str] = Field(default_factory=list)
    rss_feeds_found: List[str] = Field(default_factory=list)
    robots_txt_raw: Optional[str] = None
    crawl_duration_seconds: float = 0.0
    errors: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Gap Analysis Pipeline Models
# ---------------------------------------------------------------------------


class GapAnalysisInput(BaseModel):
    company_id: Optional[str] = Field(
        default=None,
        description="Supabase company UUID (recommended for mirroring gap artifacts).",
    )
    auto_mirror: bool = Field(
        default=False,
        description="If True, mirror gap analysis artifacts to Supabase.",
    )
    company_name: str
    domain: Optional[str] = None
    company_slug: Optional[str] = Field(
        default=None, description="If omitted, derived from company_name."
    )
    seed_urls: List[HttpUrl] = Field(
        default_factory=list, description="Seed URLs for crawling company assets."
    )
    company_context_path: Optional[str] = Field(
        default=None,
        description="Path to company context md (DeepAgents path).",
    )
    persona_paths: List[str] = Field(
        default_factory=list, description="Paths to persona artifacts (DeepAgents paths)."
    )
    style_guide_path: Optional[str] = Field(
        default=None, description="Path to style guide artifact (DeepAgents path)."
    )
    max_queries: int = Field(
        default=150, ge=10, le=500, description="Max queries across all clusters."
    )
    platforms: List[str] = Field(
        default_factory=lambda: ["perplexity", "openai", "gemini", "claude"],
        description="Search platforms to query.",
    )
    language: str = "en"
    region: Optional[str] = None
    additional_constraints: Optional[str] = None
    max_crawl_pages: Optional[int] = Field(
        default=None, description="Override default crawl page limit."
    )
    max_crawl_depth: Optional[int] = Field(
        default=None, description="Override default crawl depth."
    )


class SemanticUnit(BaseModel):
    unit_id: str
    url: Optional[HttpUrl] = None
    title: Optional[str] = None
    text: str
    embedding: Optional[List[float]] = None
    embedding_id: Optional[str] = None
    char_count: int = 0
    word_count: int = 0
    discovery_source: Optional[str] = None


class QueryCluster(BaseModel):
    cluster_id: str
    cluster_name: str
    intent: Optional[str] = None
    citation_behavior: Optional[str] = None
    buyer_stage: Optional[str] = None


class GeneratedQuery(BaseModel):
    query_id: str
    cluster_id: str
    cluster_name: str
    query_text: str
    buyer_stage: Optional[str] = None
    persona_tag: Optional[str] = None
    embedding: Optional[List[float]] = None


class CitationRef(BaseModel):
    url: HttpUrl
    rank: Optional[int] = None
    title: Optional[str] = None
    snippet: Optional[str] = None
    confidence: Optional[float] = None
    source: Optional[str] = None


class PlatformResult(BaseModel):
    engine: str
    model: Optional[str] = None
    query_id: str
    query_text: Optional[str] = None
    response_text: Optional[str] = None
    citations: List[CitationRef] = Field(default_factory=list)


class StructuralSignals(BaseModel):
    word_count: int = 0
    paragraph_count: int = 0
    header_count: int = 0
    list_item_count: int = 0
    stat_count: int = 0
    citation_count: int = 0
    has_headers: bool = False
    has_lists: bool = False
    has_numbers: bool = False
    authority_type: Optional[str] = None
    content_type: Optional[str] = None


class CitationExemplar(BaseModel):
    """A top-scoring cited page for a specific query."""

    similarity: float
    domain: Optional[str] = None
    url: str
    snippet: Optional[str] = None
    structural_signals: Optional[StructuralSignals] = None
    authority_type: Optional[str] = None


class ParagraphMatch(BaseModel):
    paragraph: str
    embedding: Optional[List[float]] = None
    embedding_id: Optional[str] = None
    similarity: Optional[float] = None


class EnrichedCitation(BaseModel):
    url: HttpUrl
    domain: Optional[str] = None
    title: Optional[str] = None
    query_id: Optional[str] = None
    cluster_name: Optional[str] = None
    engine: Optional[str] = None
    anchor_text: Optional[str] = None
    paragraphs: List[str] = Field(default_factory=list)
    best_paragraphs: List[ParagraphMatch] = Field(default_factory=list)
    structural_signals: Optional[StructuralSignals] = None


class SpaResult(BaseModel):
    cluster_id: Optional[str] = None
    cluster_name: Optional[str] = None
    t_stat: Optional[float] = None
    p_value: Optional[float] = None
    mean_citation_similarity: Optional[float] = None
    mean_company_similarity: Optional[float] = None
    effect: Optional[str] = None


class CentroidResult(BaseModel):
    cluster_id: Optional[str] = None
    cluster_name: Optional[str] = None
    query_centroid: Optional[List[float]] = None
    citation_centroid: Optional[List[float]] = None
    distance: Optional[float] = None


class QueryGap(BaseModel):
    query_id: str
    cluster_name: Optional[str] = None
    query_text: str
    best_company_unit: Optional[str] = None
    best_company_unit_text: Optional[str] = None
    best_company_similarity: Optional[float] = None
    avg_citation_similarity: Optional[float] = None
    gap: Optional[float] = None
    interpretation: Optional[str] = None
    top_cited_exemplars: List[CitationExemplar] = Field(default_factory=list)


class ClusterContentSpec(BaseModel):
    """Per-cluster content specification derived from citation analysis."""

    cluster_id: Optional[str] = None
    cluster_name: str
    query_count: int = 0
    word_count_range: List[int] = Field(default_factory=lambda: [0, 0])
    min_similarity_threshold: Optional[float] = None
    required_elements: List[str] = Field(default_factory=list)
    authority_signals: Dict[str, int] = Field(default_factory=dict)
    structural_rates: Dict[str, float] = Field(default_factory=dict)
    total_citations_analyzed: int = 0


class AnalysisResult(BaseModel):
    proximity_stats: Dict[str, Any] = Field(default_factory=dict)
    spa_results: List[SpaResult] = Field(default_factory=list)
    centroids: List[CentroidResult] = Field(default_factory=list)
    gaps: List[QueryGap] = Field(default_factory=list)
    citation_patterns: Dict[str, Any] = Field(default_factory=dict)
    decision_metrics: Dict[str, Any] = Field(default_factory=dict)
    cluster_specs: List[ClusterContentSpec] = Field(default_factory=list)


class GapReport(BaseModel):
    report_md: Optional[str] = None
    report_json: Dict[str, Any] = Field(default_factory=dict)
    generation_spec_md: Optional[str] = None
    generation_spec_json: Dict[str, Any] = Field(default_factory=dict)
    visualization_paths: List[str] = Field(default_factory=list)
