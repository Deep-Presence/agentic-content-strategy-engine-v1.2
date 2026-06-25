"""Pydantic models for the Audience Persona Research Pipeline.

Two-agent architecture:
  Agent 1 (Suggester) → 3-5 PersonaBriefs → HITL-1 per-brief approval
  Agent 2 (Profile Generator) → full persona profiles → HITL-2 per-profile review

All fields have defaults for backward compatibility with existing JSON artifacts.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PersonaBriefDecision(str, Enum):
    """Per-brief HITL decision."""

    APPROVE = "approve"
    MODIFY = "modify"
    REJECT = "reject"


class PersonaProfileDecision(str, Enum):
    """Per-profile HITL-2 decision."""

    APPROVE = "approve"
    REVISE = "revise"
    REJECT = "reject"


# Default staleness threshold for persona profiles (days).
PERSONA_DEFAULT_STALENESS_DAYS: int = 60


# ---------------------------------------------------------------------------
# Agent 1 — Persona Brief (Suggester output / Manual entry)
# ---------------------------------------------------------------------------


class PersonaBrief(BaseModel):
    """A lightweight persona hypothesis produced by Agent 1 or entered manually."""

    brief_id: str = ""
    persona_name: str = ""
    tagline: str = ""
    career_role: str = ""
    description: str = ""
    rationale: List[str] = Field(default_factory=list)
    source: Literal["agent", "manual", "hybrid"] = "agent"


class PersonaBriefReview(BaseModel):
    """Per-brief HITL-1 decision from the reviewer."""

    brief_id: str = ""
    decision: PersonaBriefDecision = PersonaBriefDecision.APPROVE
    modified_brief: Optional[PersonaBrief] = None


# ---------------------------------------------------------------------------
# Storage — Per-Persona Profile Entry (manifest entry)
# ---------------------------------------------------------------------------


class PersonaProfileEntry(BaseModel):
    """Manifest entry tracking the state of one persona profile."""

    persona_id: str = ""
    persona_name: str = ""
    tagline: str = ""
    career_role: str = ""
    kind: Literal["icp", "secondary"] = "secondary"
    current_version: int = 0
    last_updated: Optional[datetime] = None
    status: Literal["fresh", "stale", "missing", "pending_review", "archived"] = "missing"
    created_by: Literal["agent", "manual", "hybrid"] = "agent"
    word_count: int = 0
    sha256: str = ""


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


class PersonaManifest(BaseModel):
    """Top-level manifest for a company's audience persona artifacts."""

    slug: str = ""
    company_name: str = ""
    created_at: datetime = Field(default_factory=_utcnow)
    last_full_run: Optional[datetime] = None
    personas: Dict[str, PersonaProfileEntry] = Field(default_factory=dict)
    kb_synthesis_version: Optional[int] = None
    kb_synthesis_updated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Agent 2 — Profile Generator Result
# ---------------------------------------------------------------------------


class PersonaAgentResult(BaseModel):
    """Result from a single persona profile generation (Agent 2)."""

    brief_id: str = ""
    persona_name: str = ""
    content_md: str = ""
    content_json: Optional[Dict[str, Any]] = None
    word_count: int = 0
    execution_time_s: float = 0.0
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Pipeline I/O
# ---------------------------------------------------------------------------


class AudiencePersonaInput(BaseModel):
    """Input for the audience persona pipeline orchestrator."""

    company_name: str
    domain: Optional[str] = None
    company_slug: Optional[str] = None
    workspace_id: str = ""
    workspace_slug: str = ""
    product_slug: Optional[str] = None
    product_name: Optional[str] = None
    max_personas: int = Field(default=5, ge=3, le=7)
    language: str = "en"
    region: Optional[str] = None
    additional_constraints: Optional[str] = None
    auto_approve_checkpoints: List[int] = Field(default_factory=list)
    seed_personas: List[str] = Field(
        default_factory=list,
        description="User-provided persona seeds to guide the suggester agent",
    )


class AudiencePersonaOutput(BaseModel):
    """Output from the audience persona pipeline orchestrator."""

    slug: str = ""
    company_name: str = ""
    manifest: Optional[PersonaManifest] = None
    briefs_suggested: int = 0
    briefs_approved: int = 0
    profiles_generated: int = 0
    persona_results: Dict[str, PersonaAgentResult] = Field(default_factory=dict)
    persona_dir: str = ""
    total_execution_time_s: float = 0.0
