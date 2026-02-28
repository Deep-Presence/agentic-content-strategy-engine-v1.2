"""Pydantic v2 models for the site audit pipeline (Pipeline 0).

All output models use ``Field(default=...)`` or ``Field(default_factory=...)``
so that existing JSON artefacts can always be deserialised without errors —
even when new fields are added in future sprints.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AuditDimension(str, Enum):
    """The eight dimensions assessed by the site audit pipeline."""

    crawlability = "crawlability"
    performance = "performance"
    on_page_seo = "on_page_seo"
    extractability = "extractability"  # AEO-specific
    schema_markup = "schema_markup"
    eeat = "eeat"
    freshness = "freshness"
    security = "security"


class AuditCheckSeverity(str, Enum):
    """Severity levels for individual audit findings.

    Penalty values (applied per occurrence):
        critical = 10 pts, high = 5 pts, medium = 2 pts, low = 1 pt, info = 0 pts
    """

    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    info = "info"


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------


class SiteAuditInput(BaseModel):
    """Pipeline entry-point: what to audit and how.

    Unlike output models, required fields here are intentional — the caller
    *must* supply them.  Optional fields control which checks run.
    """

    company_name: str
    domain: str
    company_slug: Optional[str] = None
    product_slug: Optional[str] = None
    max_pages: int = 200
    max_depth: int = 4
    check_core_web_vitals: bool = True
    check_schema_validation: bool = True
    check_ai_bot_access: bool = True


# ---------------------------------------------------------------------------
# Per-finding models
# ---------------------------------------------------------------------------


class AuditFinding(BaseModel):
    """A single check result attached to a page or to the site as a whole.

    Attributes:
        finding_type: Machine-readable identifier, e.g. ``"missing_title"``.
        dimension: Which audit dimension this finding belongs to.
        severity: How serious the issue is (drives score penalty).
        message: Human-readable description of the problem.
        recommendation: Concrete fix recommendation for the user.
        url: The page URL this finding relates to (empty = site-level).
        details: Arbitrary structured data for advanced rendering.
    """

    finding_type: str = ""
    dimension: AuditDimension = AuditDimension.crawlability
    severity: AuditCheckSeverity = AuditCheckSeverity.info
    message: str = ""
    recommendation: str = ""
    url: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Per-page sub-results
# ---------------------------------------------------------------------------


class SchemaDetectionResult(BaseModel):
    """Structured data (JSON-LD / Microdata) found on a single page.

    Attributes:
        has_schema: True when at least one recognised schema block is found.
        schema_types: Extracted ``@type`` values, e.g. ``["Article", "FAQPage"]``.
        raw_jsonld_blocks: Parsed JSON-LD objects (for validation).
        validation_errors: Schema validation error messages.
        inferred_page_type: Best-effort page classification (``"article"``, etc.).
    """

    has_schema: bool = False
    schema_types: list[str] = Field(default_factory=list)
    raw_jsonld_blocks: list[dict[str, Any]] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)
    inferred_page_type: str = "unknown"


class AEOReadinessResult(BaseModel):
    """Answer Engine Optimisation readiness score for a single page.

    Attributes:
        snippet_readiness_score: 0–100 composite score.
        question_heading_ratio: Fraction of headings phrased as questions.
        quick_answer_hook_count: Number of paragraphs that open with a direct answer.
        self_contained_paragraph_ratio: Fraction of paragraphs that stand alone.
        avg_paragraph_word_count: Average word count per paragraph.
        content_patterns: Detected structural patterns
            (keys: faq_section, definition_opening, key_takeaways,
             comparison_table, numbered_steps, toc).
    """

    snippet_readiness_score: float = 0.0
    question_heading_ratio: float = 0.0
    quick_answer_hook_count: int = 0
    self_contained_paragraph_ratio: float = 0.0
    avg_paragraph_word_count: float = 0.0
    content_patterns: dict[str, bool] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Per-page comprehensive result
# ---------------------------------------------------------------------------


class PageAuditResult(BaseModel):
    """All signals gathered for a single crawled page.

    Fields are grouped logically:
        * HTTP / crawl metadata (url, status_code, crawl_depth, ...)
        * On-page SEO signals (title, meta_description, headings, ...)
        * Link signals (internal_link_count, external_link_count)
        * Content signals (word_count, reading_level)
        * Technical SEO (canonical, noindex, nofollow)
        * Security (has_https, has_mixed_content)
        * Freshness / authority (publish_date, has_author, ...)
        * Structured sub-results (schema, aeo, findings)
    """

    # HTTP / crawl metadata
    url: str = ""
    status_code: int = 0
    crawl_depth: int = 0
    redirect_url: Optional[str] = None

    # On-page SEO signals
    title: str = ""
    title_length: int = 0
    meta_description: str = ""
    meta_description_length: int = 0
    h1_count: int = 0
    h1_text: str = ""
    heading_hierarchy_valid: bool = True
    headings: list[dict[str, str]] = Field(default_factory=list)

    # Image signals
    image_count: int = 0
    images_with_alt: int = 0
    images_without_alt: int = 0

    # Link signals
    internal_link_count: int = 0
    external_link_count: int = 0

    # Content signals
    word_count: int = 0
    reading_level: float = 0.0

    # Technical SEO
    is_ssr: bool = True
    has_canonical: bool = False
    canonical_url: Optional[str] = None
    is_noindex: bool = False
    is_nofollow: bool = False

    # Security
    has_https: bool = True
    has_mixed_content: bool = False

    # Freshness / authority
    publish_date: Optional[str] = None
    modified_date: Optional[str] = None
    has_author: bool = False
    author_name: Optional[str] = None

    # Structured sub-results
    schema: SchemaDetectionResult = Field(default_factory=SchemaDetectionResult)
    aeo: AEOReadinessResult = Field(default_factory=AEOReadinessResult)
    findings: list[AuditFinding] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Site-level aggregated results
# ---------------------------------------------------------------------------


class AIBotAccessResult(BaseModel):
    """Summary of which AI crawlers are permitted to access the site.

    Derived from ``robots.txt`` directives and ``llms.txt`` presence.

    Attributes:
        gptbot_allowed: Whether OpenAI's GPTBot is allowed.
        claudebot_allowed: Whether Anthropic's ClaudeBot is allowed.
        perplexitybot_allowed: Whether Perplexity's bot is allowed.
        google_extended_allowed: Whether Google-Extended is allowed.
        ccbot_allowed: Whether Common Crawl's CCBot is allowed.
        has_llms_txt: Whether the site publishes a ``/llms.txt`` file.
        robots_txt_exists: Whether ``/robots.txt`` is present and reachable.
    """

    gptbot_allowed: bool = True
    claudebot_allowed: bool = True
    perplexitybot_allowed: bool = True
    google_extended_allowed: bool = True
    ccbot_allowed: bool = True
    has_llms_txt: bool = False
    robots_txt_exists: bool = False


class SitemapHealthResult(BaseModel):
    """Summary of the site's XML sitemap(s).

    Attributes:
        has_sitemap: Whether a valid sitemap was found.
        sitemap_url_count: Total URLs across all sitemaps.
        sitemap_urls: List of sitemap URLs discovered.
        sitemap_errors: Parse / fetch errors encountered.
        has_sitemap_index: Whether a sitemap index file exists.
    """

    has_sitemap: bool = False
    sitemap_url_count: int = 0
    sitemap_urls: list[str] = Field(default_factory=list)
    sitemap_errors: list[str] = Field(default_factory=list)
    has_sitemap_index: bool = False


class DimensionScore(BaseModel):
    """Score and finding breakdown for one audit dimension.

    Attributes:
        dimension: Which dimension this score represents.
        score: Raw 0–100 score before weighting.
        weight: Configured weight for this dimension (0–1).
        weighted_score: ``score * weight``.
        finding_count: Total findings in this dimension.
        critical_count: Number of critical findings.
        high_count: Number of high findings.
        medium_count: Number of medium findings.
        low_count: Number of low findings.
        info_count: Number of info findings.
    """

    dimension: AuditDimension = AuditDimension.crawlability
    score: float = 100.0
    weight: float = 0.0
    weighted_score: float = 0.0
    finding_count: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0


class SiteAuditResult(BaseModel):
    """Complete output of the site audit pipeline.

    This is the contract between the pipeline and the API / report layer.
    Every field has a default so partial results can always be serialised.

    Attributes:
        audit_id: Unique identifier for this run (UUID string).
        domain: Audited domain (e.g. ``"example.com"``).
        overall_score: Weighted composite score 0–100.
        grade: Letter grade derived from ``overall_score``.
        pages_crawled: Number of pages successfully fetched and analysed.
        pages_discovered: Total URLs found during discovery (may exceed crawled).
        duration_seconds: Wall-clock time for the full pipeline run.
        dimension_scores: One entry per :class:`AuditDimension`.
        ai_bot_access: AI-crawler accessibility summary.
        sitemap_health: XML sitemap health summary.
        page_results: Per-page detailed results.
        total_findings: Aggregate finding count across all pages.
        findings_by_severity: ``{severity_value: count}`` breakdown.
        findings_by_dimension: ``{dimension_value: count}`` breakdown.
        top_findings: Most impactful findings (for executive summary).
        avg_snippet_readiness: Mean AEO snippet readiness score.
        pages_with_schema: Count of pages with any structured data.
        avg_question_heading_ratio: Mean ratio of question headings.
        started_at: Pipeline start timestamp.
        completed_at: Pipeline completion timestamp.
        status: One of ``"pending"``, ``"running"``, ``"completed"``, ``"failed"``.
        error_message: Non-null when ``status == "failed"``.
    """

    audit_id: str = ""
    domain: str = ""
    overall_score: float = 0.0
    grade: str = "F"
    pages_crawled: int = 0
    pages_discovered: int = 0
    duration_seconds: float = 0.0
    dimension_scores: list[DimensionScore] = Field(default_factory=list)
    ai_bot_access: AIBotAccessResult = Field(default_factory=AIBotAccessResult)
    sitemap_health: SitemapHealthResult = Field(default_factory=SitemapHealthResult)
    page_results: list[PageAuditResult] = Field(default_factory=list)
    total_findings: int = 0
    findings_by_severity: dict[str, int] = Field(default_factory=dict)
    findings_by_dimension: dict[str, int] = Field(default_factory=dict)
    top_findings: list[dict[str, Any]] = Field(default_factory=list)
    avg_snippet_readiness: float = 0.0
    pages_with_schema: int = 0
    avg_question_heading_ratio: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "pending"
    error_message: Optional[str] = None
