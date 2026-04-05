"""Postgres enum types used across ORM models.

Each enum is a Python ``str, Enum`` subclass.  They map to Postgres ENUM
types via ``PgEnum(EnumClass, name="...", create_type=True)`` in the ORM
model columns.  The first migration creates these before any table that
references them.
"""
from __future__ import annotations

from enum import Enum


# ── Organisation & Auth ───────────────────────────────────────────────
class UserRole(str, Enum):
    superuser = "superuser"
    member = "member"
    viewer = "viewer"


# ── Pipeline Infrastructure ───────────────────────────────────────────
class PipelineType(str, Enum):
    research = "research"
    gap_analysis = "gap_analysis"
    content = "content"
    content_refresh = "content_refresh"
    site_audit = "site_audit"
    topic_discovery = "topic_discovery"
    topic_expansion = "topic_expansion"
    knowledge_base = "knowledge_base"
    audience_persona = "audience_persona"
    voice_style_guide = "voice_style_guide"
    onboarding = "onboarding"
    daily_tracker = "daily_tracker"
    td_gap_analysis = "td_gap_analysis"


class PipelineStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class StageStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"
    cached = "cached"


# ── Gap Analysis ──────────────────────────────────────────────────────
class SearchEngine(str, Enum):
    openai = "openai"
    claude = "claude"
    gemini = "gemini"
    perplexity = "perplexity"


class GapClassification(str, Enum):
    significant_gap = "significant_gap"
    gap_to_close = "gap_to_close"
    roughly_equal = "roughly_equal"
    company_wins = "company_wins"
    no_data = "no_data"


# ── Research Artifacts ────────────────────────────────────────────────
class ArtifactType(str, Enum):
    company_context = "company_context"
    persona = "persona"
    style_guide = "style_guide"
    knowledge_base = "knowledge_base"


class ArtifactStatus(str, Enum):
    draft = "draft"
    approved = "approved"
    archived = "archived"
    fresh = "fresh"
    stale = "stale"
    pending_review = "pending_review"


# ── Content ───────────────────────────────────────────────────────────
class ContentPieceStatus(str, Enum):
    planned = "planned"
    drafting = "drafting"
    review = "review"
    approved = "approved"
    published = "published"
    archived = "archived"


class ContentArtifactStage(str, Enum):
    outline = "outline"
    draft = "draft"
    linked = "linked"
    enriched = "enriched"
    eval_history = "eval_history"
    final = "final"


# ── Site Audit ────────────────────────────────────────────────────────
class FindingSeverity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    info = "info"


# ── Tracking ──────────────────────────────────────────────────────────
class TrackingStatus(str, Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"


# ── Topic Discovery ─────────────────────────────────────────────────
class TDStatus(str, Enum):
    draft = "draft"
    hitl_pending = "hitl_pending"
    discovery_complete = "discovery_complete"
    approved = "approved"
    archived = "archived"


class BuyerStage(str, Enum):
    tofu = "tofu"
    mofu = "mofu"
    bofu = "bofu"


class IntentType(str, Enum):
    informational = "informational"
    commercial = "commercial"
    navigational = "navigational"
    transactional = "transactional"


class AudienceSegmentType(str, Enum):
    individual_persona = "individual_persona"
    team_group = "team_group"


class RelevanceCell(str, Enum):
    relevant = "relevant"
    marginal = "marginal"
    irrelevant = "irrelevant"


class TopicAssignmentStatus(str, Enum):
    not_started = "not_started"
    approved = "approved"
    rejected = "rejected"
    in_gap_analysis = "in_gap_analysis"
    gap_analysis_complete = "gap_analysis_complete"
    content_produced = "content_produced"
    published = "published"


# ── Research Pipelines (KB, AP, VSG) ─────────────────────────────────
class ResearchRunStatus(str, Enum):
    draft = "draft"
    running = "running"
    hitl_pending = "hitl_pending"
    completed = "completed"
    failed = "failed"


# ── CMS Integration ──────────────────────────────────────────────────
class CMSProvider(str, Enum):
    wordpress = "wordpress"
    webflow = "webflow"
    strapi = "strapi"
    ghost = "ghost"
    hubspot = "hubspot"


class CMSPostStatus(str, Enum):
    draft = "draft"
    publish = "publish"
    pending = "pending"
    private = "private"


class CMSPublishAction(str, Enum):
    create = "create"
    update = "update"
    refresh = "refresh"


# ── Analytics Integration ────────────────────────────────────────────
class AnalyticsProvider(str, Enum):
    ga4 = "ga4"


class AnalyticsSyncStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    success = "success"
    failed = "failed"
    auth_revoked = "auth_revoked"


# ── Content Inventory ────────────────────────────────────────────────
class ContentIngestionSource(str, Enum):
    """How a content inventory record was discovered."""
    site_audit_crawl = "site_audit_crawl"
    gap_analysis_crawl = "gap_analysis_crawl"
    cms_sync = "cms_sync"
    csv_import = "csv_import"
    content_engine = "content_engine"
    manual = "manual"
