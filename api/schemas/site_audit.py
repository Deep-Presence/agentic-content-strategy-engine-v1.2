"""Pydantic v2 request/response schemas for the site audit API endpoints.

All response fields use ``Field(default=...)`` or ``Field(default_factory=...)``
so that partial audit results can always be deserialised without errors.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------


class SiteAuditStartRequest(BaseModel):
    """Request body for POST /api/v1/site-audit/start.

    Attributes:
        company_name: Human-readable company name (used to derive the slug).
        domain: Domain to audit, e.g. ``"example.com"``.
        product_slug: Optional product scope (same slug rules as gap-analysis).
        max_pages: Maximum pages to crawl (1–2000).
        max_depth: Maximum crawl depth (1–10).
        check_core_web_vitals: Whether to check Core Web Vitals signals.
        check_schema_validation: Whether to validate JSON-LD schema markup.
        check_ai_bot_access: Whether to check AI-bot access in robots.txt.
        force_rerun: When True, bypass the already-exists guard.
    """

    company_name: str
    domain: str
    product_slug: Optional[str] = None
    max_pages: int = Field(default=200, ge=1, le=2000)
    max_depth: int = Field(default=4, ge=1, le=10)
    check_core_web_vitals: bool = True
    check_schema_validation: bool = True
    check_ai_bot_access: bool = True
    force_rerun: bool = False


# ---------------------------------------------------------------------------
# Response schemas — all fields have defaults
# ---------------------------------------------------------------------------


class DimensionScoreResponse(BaseModel):
    """Score and finding breakdown for one audit dimension."""

    dimension: str = ""
    score: float = 0.0
    weight: float = 0.0
    weighted_score: float = 0.0
    finding_count: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0


class AIBotAccessResponse(BaseModel):
    """Summary of which AI crawlers can access the site."""

    gptbot_allowed: bool = True
    claudebot_allowed: bool = True
    perplexitybot_allowed: bool = True
    google_extended_allowed: bool = True
    ccbot_allowed: bool = True
    has_llms_txt: bool = False
    robots_txt_exists: bool = False


class SitemapHealthResponse(BaseModel):
    """Summary of the site's XML sitemap health."""

    has_sitemap: bool = False
    sitemap_url_count: int = 0
    sitemap_urls: list[str] = Field(default_factory=list)
    sitemap_errors: list[str] = Field(default_factory=list)
    has_sitemap_index: bool = False


class AuditSummaryResponse(BaseModel):
    """GET /companies/{slug}/audits — lightweight audit list item.

    Attributes:
        audit_id: Unique identifier for the audit run.
        domain: The domain that was audited.
        overall_score: Weighted composite score 0–100.
        grade: Letter grade (A–F) derived from overall_score.
        pages_crawled: Number of pages successfully analysed.
        total_findings: Aggregate finding count across all pages.
        status: ``"pending"``, ``"running"``, ``"completed"``, or ``"failed"``.
        started_at: ISO 8601 start timestamp (or empty string).
        completed_at: ISO 8601 completion timestamp (or empty string).
    """

    audit_id: str = ""
    domain: str = ""
    overall_score: float = 0.0
    grade: str = "F"
    pages_crawled: int = 0
    total_findings: int = 0
    status: str = "pending"
    started_at: str = ""
    completed_at: str = ""


class AuditFindingResponse(BaseModel):
    """A single audit finding for the findings list endpoint."""

    finding_type: str = ""
    dimension: str = ""
    severity: str = "info"
    message: str = ""
    recommendation: str = ""
    url: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class AuditDetailResponse(BaseModel):
    """GET /companies/{slug}/audits/{id} — full audit result.

    Attributes:
        audit_id: Unique run identifier.
        domain: Audited domain.
        overall_score: Weighted composite 0–100.
        grade: Letter grade.
        pages_crawled: Pages successfully fetched.
        pages_discovered: Total URLs discovered.
        duration_seconds: Wall-clock pipeline duration.
        dimension_scores: Per-dimension score breakdown.
        ai_bot_access: AI-crawler accessibility summary.
        sitemap_health: XML sitemap health summary.
        total_findings: Aggregate finding count.
        findings_by_severity: ``{severity: count}`` breakdown.
        findings_by_dimension: ``{dimension: count}`` breakdown.
        avg_snippet_readiness: Mean AEO snippet readiness score.
        pages_with_schema: Count of pages with any structured data.
        avg_question_heading_ratio: Mean ratio of question headings.
        status: Pipeline run status string.
        error_message: Non-null when ``status == "failed"``.
        started_at: ISO 8601 start timestamp.
        completed_at: ISO 8601 completion timestamp.
    """

    audit_id: str = ""
    domain: str = ""
    overall_score: float = 0.0
    grade: str = "F"
    pages_crawled: int = 0
    pages_discovered: int = 0
    duration_seconds: float = 0.0
    dimension_scores: list[DimensionScoreResponse] = Field(default_factory=list)
    ai_bot_access: AIBotAccessResponse = Field(default_factory=AIBotAccessResponse)
    sitemap_health: SitemapHealthResponse = Field(default_factory=SitemapHealthResponse)
    total_findings: int = 0
    findings_by_severity: dict[str, int] = Field(default_factory=dict)
    findings_by_dimension: dict[str, int] = Field(default_factory=dict)
    avg_snippet_readiness: float = 0.0
    pages_with_schema: int = 0
    avg_question_heading_ratio: float = 0.0
    status: str = "pending"
    error_message: Optional[str] = None
    started_at: str = ""
    completed_at: str = ""


class AuditFindingsResponse(BaseModel):
    """GET /companies/{slug}/audits/{id}/findings — paginated findings list.

    Attributes:
        findings: Page of finding items.
        total: Total matching findings across all pages.
        page: Current page number (1-based).
        page_size: Items per page.
        total_pages: Total number of pages.
    """

    findings: list[AuditFindingResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50
    total_pages: int = 0


class AEOReadinessResponse(BaseModel):
    """AEO readiness scores for a single page."""

    snippet_readiness_score: float = 0.0
    question_heading_ratio: float = 0.0
    quick_answer_hook_count: int = 0
    self_contained_paragraph_ratio: float = 0.0
    avg_paragraph_word_count: float = 0.0
    content_patterns: dict[str, bool] = Field(default_factory=dict)


class SchemaDetectionResponse(BaseModel):
    """Schema markup detection result for a single page."""

    has_schema: bool = False
    schema_types: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)
    inferred_page_type: str = "unknown"


class PageResultResponse(BaseModel):
    """Summarised per-page result for the pages list endpoint."""

    model_config = {"populate_by_name": True}

    url: str = ""
    status_code: int = 0
    crawl_depth: int = 0
    title: str = ""
    word_count: int = 0
    reading_level: float = 0.0
    has_https: bool = True
    is_noindex: bool = False
    schema_result: SchemaDetectionResponse = Field(
        default_factory=SchemaDetectionResponse,
        alias="schema",
    )
    aeo: AEOReadinessResponse = Field(default_factory=AEOReadinessResponse)
    finding_count: int = 0


class AuditPageResultsResponse(BaseModel):
    """GET /companies/{slug}/audits/{id}/pages — paginated per-page results.

    Attributes:
        pages: Page of per-page result items.
        total: Total pages in the audit across all response pages.
        page: Current page number (1-based).
        page_size: Items per page.
        total_pages: Total number of response pages.
    """

    pages: list[PageResultResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50
    total_pages: int = 0
