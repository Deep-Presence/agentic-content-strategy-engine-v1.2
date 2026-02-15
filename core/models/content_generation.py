"""Pydantic models for the Content Generation Engine (Pipeline 3).

All models used across the 4-stage pipeline:
  Stage 1 — Strategic Planner (briefs)
  Stage 2 — Orchestrator-Workers (outline, draft, enriched, formatted)
  Stage 3 — Evaluator-Optimizer (eval results, revision history)
  Stage 4 — HITL Review (content pieces, final output)
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------


class ContentGenerationInput(BaseModel):
    """Top-level input to the content generation pipeline."""

    company_name: str
    domain: str
    company_context_path: Optional[str] = None
    persona_paths: List[str] = Field(default_factory=list)
    style_guide_path: Optional[str] = None
    gap_report_json_path: Optional[str] = None
    generation_spec_json_path: Optional[str] = None
    analysis_json_path: Optional[str] = None
    max_briefs: int = 10
    max_concurrent_workers: int = 3
    max_revision_cycles: int = 2
    auto_approve: bool = False
    skip_stages: List[int] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage 1 — Strategic Planner
# ---------------------------------------------------------------------------


class TargetQuery(BaseModel):
    """A query the content piece should optimize for."""

    query_text: str
    cluster_name: str
    embedding: Optional[List[float]] = None


class StructuralTargets(BaseModel):
    """Cluster-derived structural targets for content."""

    header_rate: float = 0.0
    list_rate: float = 0.0
    stat_rate: float = 0.0
    citation_rate: float = 0.0
    min_headers: int = 3
    min_lists: int = 1
    min_citations: int = 2


class ContentBrief(BaseModel):
    """A single content brief produced by the Strategic Planner."""

    brief_id: str
    title: str
    target_queries: List[TargetQuery] = Field(default_factory=list)
    target_cluster: str = ""
    content_format: Literal[
        "long_blog", "short_faq", "pillar_page", "comparison", "how_to"
    ] = "long_blog"
    funnel_stage: Literal[
        "awareness", "consideration", "decision", "retention"
    ] = "awareness"
    channel: Literal[
        "blog", "help_center", "landing_page", "resource_hub"
    ] = "blog"
    priority_score: float = 0.0
    word_count_range: Tuple[int, int] = (1200, 2000)
    structural_targets: StructuralTargets = Field(default_factory=StructuralTargets)
    required_structural_elements: List[str] = Field(default_factory=list)
    key_topics: List[str] = Field(default_factory=list)
    key_angles: List[str] = Field(default_factory=list)
    competitor_exemplars: List[str] = Field(default_factory=list)
    semantic_threshold: float = 0.65


class PlannerOutput(BaseModel):
    """Full output of Stage 1."""

    briefs: List[ContentBrief] = Field(default_factory=list)
    planning_metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Stage 2 — Workers
# ---------------------------------------------------------------------------


class OutlineSection(BaseModel):
    """A single section in the content outline."""

    heading: str
    level: int = 2
    key_points: List[str] = Field(default_factory=list)
    target_word_count: int = 300


class ContentOutline(BaseModel):
    """Structured outline produced by the Outliner."""

    brief_id: str
    title: str
    sections: List[OutlineSection] = Field(default_factory=list)
    total_target_words: int = 1500


class ContentDraft(BaseModel):
    """Raw markdown draft produced by the Drafter."""

    brief_id: str
    title: str
    markdown: str = ""
    word_count: int = 0


class EnrichedDraft(BaseModel):
    """Draft enriched with verified facts by the Fact Enricher."""

    brief_id: str
    title: str
    markdown: str = ""
    word_count: int = 0
    facts_added: List[Dict[str, str]] = Field(default_factory=list)


class FormattedContent(BaseModel):
    """Final formatted content from the Formatter."""

    brief_id: str
    title: str
    markdown: str = ""
    word_count: int = 0
    header_count: int = 0
    list_count: int = 0
    stat_count: int = 0
    citation_count: int = 0


# ---------------------------------------------------------------------------
# Stage 3 — Evaluator
# ---------------------------------------------------------------------------


class DimensionResult(BaseModel):
    """Result from a single evaluation dimension."""

    dimension: str  # "structural" | "semantic" | "style" | "factual"
    passed: bool = False
    score: float = 0.0
    feedback: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)


class EvalResult(BaseModel):
    """Results from one evaluation cycle across all dimensions."""

    brief_id: str
    cycle: int = 0
    dimensions: List[DimensionResult] = Field(default_factory=list)
    overall_passed: bool = False
    overall_score: float = 0.0


class RevisionHistory(BaseModel):
    """Complete revision history for a content piece."""

    brief_id: str
    cycles: List[EvalResult] = Field(default_factory=list)
    final_passed: bool = False


# ---------------------------------------------------------------------------
# Stage 4 — HITL Review
# ---------------------------------------------------------------------------


class ContentStatus(str, Enum):
    """Human review status for a content piece."""

    PENDING = "pending"
    APPROVED = "approved"
    EDITED = "edited"
    REJECTED = "rejected"


class ContentPiece(BaseModel):
    """A single reviewed content piece with its final state."""

    brief_id: str
    title: str
    status: ContentStatus = ContentStatus.PENDING
    final_markdown: str = ""
    eval_summary: Dict[str, Any] = Field(default_factory=dict)
    human_notes: Optional[str] = None
    artifact_path: Optional[str] = None


class ContentGenerationOutput(BaseModel):
    """Final output of the content generation pipeline."""

    company_slug: str
    total_briefs: int = 0
    total_approved: int = 0
    total_rejected: int = 0
    pieces: List[ContentPiece] = Field(default_factory=list)
    run_metadata: Dict[str, Any] = Field(default_factory=dict)
