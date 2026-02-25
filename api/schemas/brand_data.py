"""Response schemas for Brand Brain + Run History endpoints (Phase 4)."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


# ── Endpoint 1: Research Artifacts ──────────────────────────────────


class ArtifactContent(BaseModel):
    """Single research artifact with content and status."""

    content: Optional[str] = None
    status: str = "none"  # "none" | "draft" | "approved"
    updated_at: Optional[str] = None  # ISO8601 from file mtime


class PersonaArtifact(BaseModel):
    """A persona artifact with metadata derived from filename."""

    id: str  # e.g., "persona-icp" (extracted from filename)
    name: str = ""  # e.g., "Persona Icp" (title-cased from id)
    type: str = "secondary"  # "icp" if "icp" in id, else "secondary"
    content: str = ""
    status: str = "approved"  # "draft" | "approved"
    updated_at: Optional[str] = None


class ResearchArtifactsResponse(BaseModel):
    """GET /research/artifacts — all research artifacts with content."""

    company_context: ArtifactContent = Field(default_factory=ArtifactContent)
    personas: List[PersonaArtifact] = Field(default_factory=list)
    style_guide: ArtifactContent = Field(default_factory=ArtifactContent)


# ── Endpoint 2: Run History ────────────────────────────────────────


class RunHistoryItem(BaseModel):
    """Single pipeline run in the history."""

    id: str
    pipeline: str = ""  # "gap_analysis" | "research" | "content"
    company: str = ""  # display name derived from slug
    company_slug: str = ""
    status: str = "completed"
    started: str = ""  # ISO8601
    duration: str = ""  # human-readable: "3h 46m"
    queries: int = 0  # from gap analysis result (0 for non-gap)
    citations: int = 0
    spa_score: float = 0.0
    steps_completed: int = 0
    total_steps: int = 0  # 8=gap, 3=research, 4=content


class RunHistoryResponse(BaseModel):
    """GET /runs — run history across all pipelines."""

    runs: List[RunHistoryItem] = Field(default_factory=list)
    total: int = 0


# ── Endpoint 3: SPA Score Trend ────────────────────────────────────


class SPATrendPoint(BaseModel):
    """Single data point in the SPA score trend chart."""

    run_id: str = ""
    run: str = ""  # short date label for x-axis: "Feb 18"
    timestamp: str = ""  # ISO8601
    spa_score: float = 0.0
    citation_advantage: float = 0.0
    company_advantage: float = 0.0
    total_queries: int = 0
    total_citations: int = 0


class SPATrendResponse(BaseModel):
    """GET /gap-analysis/trend — SPA score trend across runs."""

    trend: List[SPATrendPoint] = Field(default_factory=list)
