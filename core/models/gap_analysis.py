from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl
from typing import Tuple


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
    KNOWLEDGE_DOC = "knowledge_doc"


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
    max_queries: int = Field(
        default=75, ge=10, le=500, description="Max queries across all clusters."
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
    # Product-level scope (optional — omit for company-level runs)
    product_slug: Optional[str] = Field(
        default=None, description="Product slug for product-level pipeline runs."
    )
    product_name: Optional[str] = Field(
        default=None, description="Product display name for prompt injection."
    )
    fast_mode: bool = Field(
        default=False,
        description="Demo/fast mode: caps queries at 30, uses only fastest engines (openai, perplexity).",
    )
    product_description: Optional[str] = Field(
        default=None, description="Product description for prompt injection."
    )
    knowledge_doc_dir: Optional[str] = Field(
        default=None, description="Path to knowledge docs directory for s1 embedding."
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
    # Topic Discovery integration: tracks which TopicAssignment(s) spawned this query.
    # List because cross-topic dedup can merge queries from multiple topics.
    source_topic_ids: List[str] = Field(default_factory=list)


class CitationRef(BaseModel):
    url: HttpUrl
    rank: Optional[int] = None
    title: Optional[str] = None
    snippet: Optional[str] = None
    confidence: Optional[float] = None
    source: Optional[str] = None
    is_company_citation: bool = False


class PlatformResult(BaseModel):
    engine: str
    model: Optional[str] = None
    query_id: str
    query_text: Optional[str] = None
    response_text: Optional[str] = None
    citations: List[CitationRef] = Field(default_factory=list)


class StructuralSignals(BaseModel):
    """Structural signals extracted from a citation's main content.

    Original 11 fields are preserved at the top for backward compatibility.
    New fields are grouped into 4 categories (A-D), all with defaults.
    """

    # --- Original fields (backward compat) ---
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

    # --- Category A: Text Composition (10 fields) ---
    main_content_word_count: int = 0
    sentence_count: int = 0
    avg_paragraph_length: float = 0.0
    median_paragraph_length: float = 0.0
    max_paragraph_word_count: int = 0
    avg_sentence_length: float = 0.0
    avg_sentence_count_per_paragraph: float = 0.0
    reading_level: float = 0.0
    self_contained_ratio: float = 0.0
    per_paragraph_word_counts: List[int] = Field(default_factory=list)

    # --- Category B: Structural Elements (13 fields) ---
    h1_count: int = 0
    h2_count: int = 0
    h3_count: int = 0
    h4_count: int = 0
    ordered_list_count: int = 0
    unordered_list_count: int = 0
    table_count: int = 0
    definition_list_count: int = 0
    blockquote_count: int = 0
    code_block_count: int = 0
    list_block_count: int = 0
    bullets_per_list_block: float = 0.0
    min_bullets_per_list: int = 0

    # --- Category C: Content Patterns (8 fields) ---
    has_faq_section: bool = False
    has_definition_opening: bool = False
    has_key_takeaways: bool = False
    has_toc: bool = False
    has_comparison_table: bool = False
    has_step_by_step: bool = False
    has_research_refs: bool = False
    has_expert_quotes: bool = False

    # --- Category D: Factual Density (3 fields) ---
    data_point_count: int = 0
    citation_density: float = 0.0
    named_entity_density: float = 0.0


class CompanyPageAnalysis(BaseModel):
    """Structural analysis of a company page (page-level, not chunk-level).

    Computed during s1 by reusing the structural signal extraction from s4.
    Stored as a separate artifact (company_page_analysis.json) to avoid
    duplicating signals across the 10-20 SemanticUnit chunks per page.
    """

    url: str
    title: Optional[str] = None
    structural_signals: Optional[StructuralSignals] = None
    word_count: int = 0
    paragraph_count: int = 0


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
    is_company_citation: bool = False


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


class GapContentBrief(BaseModel):
    """Per-query content brief derived from top-cited exemplar structural signals.

    Named GapContentBrief (not ContentBrief) to avoid collision with
    content_generation.ContentBrief which is the downstream consumer model.
    """

    target_word_count: Tuple[int, int] = (0, 0)
    target_reading_level: Tuple[float, float] = (0.0, 0.0)
    avg_paragraph_length: Tuple[int, int] = (0, 0)
    recommended_header_count: Tuple[int, int] = (0, 0)
    header_hierarchy: Dict[str, int] = Field(default_factory=dict)
    has_ordered_lists: float = 0.0
    has_unordered_lists: float = 0.0
    has_tables: float = 0.0
    has_faq_section: float = 0.0
    has_definition_opening: float = 0.0
    has_key_takeaways: float = 0.0
    has_step_by_step: float = 0.0
    target_data_point_density: float = 0.0
    target_citation_density: float = 0.0
    dominant_authority_type: Optional[str] = None
    dominant_content_type: Optional[str] = None
    exemplar_count: int = 0


class QueryGap(BaseModel):
    query_id: str
    cluster_name: Optional[str] = None
    query_text: str
    best_company_unit: Optional[str] = None
    best_company_unit_text: Optional[str] = None
    best_company_url: Optional[str] = None
    best_company_similarity: Optional[float] = None
    avg_citation_similarity: Optional[float] = None
    gap: Optional[float] = None
    interpretation: Optional[str] = None
    top_cited_exemplars: List[CitationExemplar] = Field(default_factory=list)
    content_brief: Optional[GapContentBrief] = None
    best_company_structural_signals: Optional[Dict[str, Any]] = None
    company_cited: bool = False
    company_cited_platforms: List[str] = Field(default_factory=list)
    # Topic Discovery integration: inherited from GeneratedQuery.source_topic_ids in S6.
    source_topic_ids: List[str] = Field(default_factory=list)


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

    # --- Expanded fields (Phase 2) ---
    faq_rate: float = 0.0
    table_rate: float = 0.0
    definition_rate: float = 0.0
    code_block_rate: float = 0.0
    key_takeaways_rate: float = 0.0
    avg_word_count: float = 0.0
    avg_paragraph_word_count: float = 0.0
    avg_sentence_count_per_paragraph: float = 0.0
    min_bullets_per_list: int = 0
    dominant_content_type: Optional[str] = None
    dominant_authority_type: Optional[str] = None
    exemplar_themes: List[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    proximity_stats: Dict[str, Any] = Field(default_factory=dict)
    spa_results: List[SpaResult] = Field(default_factory=list)
    centroids: List[CentroidResult] = Field(default_factory=list)
    gaps: List[QueryGap] = Field(default_factory=list)
    citation_patterns: Dict[str, Any] = Field(default_factory=dict)
    decision_metrics: Dict[str, Any] = Field(default_factory=dict)
    cluster_specs: List[ClusterContentSpec] = Field(default_factory=list)
    # Topic Discovery integration: maps topic_assignment_id → [query_ids].
    # Populated by run_topic_scoped_gap_analysis(); empty dict for standard runs.
    topic_query_map: Dict[str, List[str]] = Field(default_factory=dict)


class GapReport(BaseModel):
    report_md: Optional[str] = None
    report_json: Dict[str, Any] = Field(default_factory=dict)
    generation_spec_md: Optional[str] = None
    generation_spec_json: Dict[str, Any] = Field(default_factory=dict)
    visualization_paths: List[str] = Field(default_factory=list)
