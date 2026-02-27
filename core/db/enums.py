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


class ArtifactStatus(str, Enum):
    draft = "draft"
    approved = "approved"
    archived = "archived"


# ── Content ───────────────────────────────────────────────────────────
class ContentPieceStatus(str, Enum):
    planned = "planned"
    drafting = "drafting"
    review = "review"
    approved = "approved"
    published = "published"
    archived = "archived"


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
