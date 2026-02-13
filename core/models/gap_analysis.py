from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl


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
    char_count: int = 0
    word_count: int = 0


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
    has_headers: bool = False
    has_lists: bool = False
    has_numbers: bool = False
    authority_type: Optional[str] = None
    content_type: Optional[str] = None


class ParagraphMatch(BaseModel):
    paragraph: str
    embedding: Optional[List[float]] = None
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
    best_company_similarity: Optional[float] = None
    avg_citation_similarity: Optional[float] = None
    gap: Optional[float] = None
    interpretation: Optional[str] = None


class AnalysisResult(BaseModel):
    proximity_stats: Dict[str, Any] = Field(default_factory=dict)
    spa_results: List[SpaResult] = Field(default_factory=list)
    centroids: List[CentroidResult] = Field(default_factory=list)
    gaps: List[QueryGap] = Field(default_factory=list)
    citation_patterns: Dict[str, Any] = Field(default_factory=dict)
    decision_metrics: Dict[str, Any] = Field(default_factory=dict)


class GapReport(BaseModel):
    report_md: Optional[str] = None
    report_json: Dict[str, Any] = Field(default_factory=dict)
    generation_spec_md: Optional[str] = None
    generation_spec_json: Dict[str, Any] = Field(default_factory=dict)
    visualization_paths: List[str] = Field(default_factory=list)
