"""Pydantic models for the Onboarding Pipeline Orchestrator.

3-phase meta-orchestrator triggered on first login:
  Phase A: Site Audit + KB (parallel, all HITL auto-approved)
  Phase B: AP (sequential after KB, seeded with user personas, HITL auto-approved)
  Phase C: VSG + GA + TD (parallel after AP, HITL auto-approved)

All fields have defaults for backward compatibility.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class OnboardingPhase(str, Enum):
    """Ordered phases of the onboarding pipeline."""

    phase_a = "phase_a"  # Site Audit + KB (parallel)
    phase_b = "phase_b"  # AP (sequential)
    phase_c = "phase_c"  # VSG + GA + TD (parallel)


class OnboardingPhaseStatus(str, Enum):
    """Status of a single onboarding phase."""

    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class OnboardingStatus(str, Enum):
    """Terminal status for the entire onboarding run."""

    completed = "completed"
    completed_partial = "completed_partial"
    failed = "failed"


# ---------------------------------------------------------------------------
# Sub-pipeline result
# ---------------------------------------------------------------------------


class OnboardingSubResult(BaseModel):
    """Result from one sub-pipeline within the onboarding orchestrator."""

    pipeline: str = ""
    phase: str = ""
    status: str = "pending"
    skip_reason: Optional[str] = None
    execution_time_s: float = 0.0
    error: Optional[str] = None
    output_summary: Dict[str, Any] = Field(default_factory=dict)


class OnboardingPhaseResult(BaseModel):
    """Aggregate result for one phase."""

    phase: str = ""
    status: str = "pending"
    pipelines: Dict[str, OnboardingSubResult] = Field(default_factory=dict)
    execution_time_s: float = 0.0
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Pipeline I/O
# ---------------------------------------------------------------------------


class OnboardingInput(BaseModel):
    """Input for the onboarding pipeline orchestrator.

    Collected from the post-registration onboarding form:
    - company_name + domain already known from registration
    - industry provided by user
    - seed_personas provided by user (free-text descriptions)
    """

    company_name: str
    domain: str = ""
    company_slug: Optional[str] = None
    company_id: Optional[str] = None
    industry: Optional[str] = None

    # Persona seeds from the onboarding form
    seed_personas: List[str] = Field(
        default_factory=list,
        description="User-provided persona descriptions (e.g. 'VP of Engineering at B2B SaaS')",
    )

    # Site Audit config
    max_pages: int = Field(default=200, ge=10, le=500)
    max_depth: int = Field(default=4, ge=1, le=10)

    # KB config
    seed_urls: List[str] = Field(default_factory=list)

    # AP config
    max_personas: int = Field(default=5, ge=3, le=7)

    # VSG config
    max_authors: int = Field(default=3, ge=2, le=3)

    # GA config
    max_queries: int = Field(default=75, ge=10, le=500)
    platforms: List[str] = Field(
        default_factory=lambda: ["perplexity", "openai", "gemini", "claude"],
    )

    # Shared
    language: str = "en"
    region: Optional[str] = None

    # Phases to run (allows skipping for re-runs)
    phases: List[OnboardingPhase] = Field(
        default_factory=lambda: [
            OnboardingPhase.phase_a,
            OnboardingPhase.phase_b,
            OnboardingPhase.phase_c,
        ],
    )

    # Force rerun even if artifacts exist
    force_rerun: bool = False


class OnboardingOutput(BaseModel):
    """Output from the onboarding pipeline orchestrator."""

    slug: str = ""
    company_name: str = ""
    onboarding_status: OnboardingStatus = OnboardingStatus.completed
    phases: Dict[str, OnboardingPhaseResult] = Field(default_factory=dict)
    sub_results: Dict[str, OnboardingSubResult] = Field(default_factory=dict)
    total_execution_time_s: float = 0.0

    # Promoted artifact paths
    audit_run_id: Optional[str] = None
    company_context_path: Optional[str] = None
    persona_dir: Optional[str] = None
    style_guide_path: Optional[str] = None
    gap_analysis_dir: Optional[str] = None
    topic_discovery_id: Optional[str] = None

    completed_at: Optional[datetime] = None
