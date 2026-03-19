"""Pydantic models for the Content Engine Pipeline v1.3.

New models introduced by the v1.3 overhaul:
  - Phase 1: PlannerScorecard, QueryScorecard, ClusterSummary
  - Phase 1 output: TopicSelection, StrategicPlannerOutput
  - Phase 2: WorkerQueryContext, BlueprintSection, ContentBlueprint
  - Entry modes: EntryMode, ContentGenerationInputV13, ManualPromptInput
  - Feedback: FeedbackRoute

All models have defaults on every field for backward compatibility
with existing JSON artifacts.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

from core.models.content_generation import ContentBrief, ContentGenerationInput


# ---------------------------------------------------------------------------
# Phase 1 — Strategic Planner Scorecard
# ---------------------------------------------------------------------------


class QueryScorecard(BaseModel):
    """Lightweight per-query summary for Strategic Planner triage.

    Contains only the fields the planner needs to make prioritization
    decisions — roughly 50 tokens per query. For 200 queries this totals
    ~10K tokens, a 5-6x reduction from sending the full analysis.
    """

    query_id: str = ""
    query_text: str = ""
    cluster_name: str = ""
    gap: float = 0.0
    best_company_similarity: float = 0.0
    avg_citation_similarity: float = 0.0
    interpretation: str = ""
    exemplar_count: int = 0
    has_brief: bool = False
    company_cited: bool = False


class ClusterSummary(BaseModel):
    """Per-cluster aggregate for Strategic Planner.

    Roughly 60 tokens per cluster. Computed by grouping QueryScorecard
    records by cluster_name and aggregating gap statistics.
    """

    cluster_name: str = ""
    query_count: int = 0
    avg_gap: float = 0.0
    max_gap: float = 0.0
    significant_gap_count: int = 0
    dominant_content_type: Optional[str] = None
    dominant_authority_type: Optional[str] = None


class PlannerScorecard(BaseModel):
    """Complete scorecard input to the Strategic Planner (Agent 1).

    Two sections:
      1. Per-query scorecards (~50 tokens each, 200 queries ≈ 10K tokens)
      2. Per-cluster summaries (~60 tokens each, 10-15 clusters ≈ 900 tokens)

    Total budget: approximately 11K tokens.
    """

    queries: List[QueryScorecard] = Field(default_factory=list)
    clusters: List[ClusterSummary] = Field(default_factory=list)
    company_summary: str = ""  # First ~600 chars of company context
    product_focus: Optional[str] = None
    total_queries: int = 0
    total_clusters: int = 0


# ---------------------------------------------------------------------------
# Phase 1 — Strategic Planner Output
# ---------------------------------------------------------------------------


class TopicSelection(BaseModel):
    """A single topic selected by the Strategic Planner.

    The planner ranks 4-6 highest-impact content opportunities
    from the full query scorecard. Each selection may consolidate
    multiple related queries into a single content piece.

    The ``rationale`` field must explain WHY this topic was chosen
    based on the gap analysis evidence — what gap it fills, what
    opportunity it captures — not merely describe the topic.
    """

    rank: int = 0
    query_ids: List[str] = Field(default_factory=list)
    query_texts: List[str] = Field(default_factory=list)
    cluster_name: str = ""
    rationale: str = ""
    consolidation_note: str = ""
    estimated_impact: Literal["high", "medium", "low"] = "medium"


class StrategicPlannerOutput(BaseModel):
    """Output of the Strategic Planner (Agent 1).

    Contains ranked topic selections and metadata about the
    planner's decision-making process.
    """

    selections: List[TopicSelection] = Field(default_factory=list)
    selection_metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Phase 2 — Full Context + Brief Builder
# ---------------------------------------------------------------------------


class WorkerQueryContext(BaseModel):
    """Complete context for a single approved query, fed to Agent 2.

    This is the 'full context pull' — the complete QueryGap data
    with all exemplars, structural signals, content brief, and
    cluster spec. Only loaded for the 4-6 approved queries, not
    all 200.
    """

    query_gap: Dict[str, Any] = Field(default_factory=dict)
    cluster_spec: Dict[str, Any] = Field(default_factory=dict)
    exemplars: List[Dict[str, Any]] = Field(default_factory=list)
    gap_content_brief: Optional[Dict[str, Any]] = None
    company_best_text: str = ""
    company_best_url: str = ""


class BlueprintSection(BaseModel):
    """Detailed section specification within a ContentBlueprint.

    Agent 2 produces a section-by-section outline with per-section
    word count allocations, structural element requirements, and
    must-include checklist items.
    """

    heading: str = ""
    level: int = 2
    key_points: List[str] = Field(default_factory=list)
    target_word_count: int = 300
    structural_elements: List[str] = Field(default_factory=list)
    must_include: List[str] = Field(default_factory=list)


class ContentBlueprint(ContentBrief):
    """Extended ContentBrief produced by Agent 2 (Brief Builder).

    Inherits ALL ContentBrief fields so it is accepted anywhere
    ContentBrief is expected — workers, evaluators, persistence
    hooks all work transparently with blueprints.

    Adds richer detail: section-level outline, territory analysis,
    reading hierarchy, must-hit checklist, and user feedback from
    HITL Checkpoint 2.
    """

    sections: List[BlueprintSection] = Field(default_factory=list)
    territory_queries: List[str] = Field(default_factory=list)
    reading_hierarchy: Dict[str, int] = Field(default_factory=dict)
    must_hit_checklist: List[str] = Field(default_factory=list)
    user_feedback: str = ""
    gap_context: Optional[WorkerQueryContext] = None

    # --- Direction & persona fields (v1.3.1) ---
    gap_reasoning: List[str] = Field(
        default_factory=list,
        description="3 points explaining how this brief overcomes the identified content gap",
    )
    tone_voice_description: str = Field(
        default="",
        description="Tone, voice, and register guidance for downstream workers",
    )
    target_persona: str = Field(
        default="",
        description="The target audience persona for this content piece",
    )
    buyer_stage: str = Field(
        default="",
        description="Buyer journey stage (e.g. problem-unaware, problem-aware, solution-aware)",
    )
    intent_stage: str = Field(
        default="",
        description="Search intent stage (informational, navigational, commercial, transactional)",
    )
    # Topic Discovery traceability
    topic_assignment_id: Optional[str] = Field(
        default=None,
        description="TD TopicAssignment ID this blueprint was built from",
    )


# ---------------------------------------------------------------------------
# Entry Modes
# ---------------------------------------------------------------------------


class EntryMode(str, Enum):
    """Pipeline entry mode."""

    AUTONOMOUS = "autonomous"
    MANUAL = "manual"
    TOPIC_DISCOVERY = "topic_discovery"


class ManualPromptInput(BaseModel):
    """User-provided input for manual entry mode.

    The user specifies a topic heading and description. The system
    runs a lightweight gap analysis (s3-s6) on the prompt, then
    feeds the result into the Brief Builder.
    """

    prompt: str = ""
    description: str = ""
    cluster_name: str = ""


class ContentGenerationInputV13(ContentGenerationInput):
    """Extended input for the v1.3 pipeline.

    Adds entry mode selection, topic count limit for autonomous mode,
    and manual prompt fields. All new fields have defaults for
    backward compatibility.
    """

    entry_mode: EntryMode = EntryMode.AUTONOMOUS
    max_topics: int = 6
    # Manual mode fields
    manual_prompt: Optional[str] = None
    manual_description: Optional[str] = None
    manual_cluster: Optional[str] = None
    gap_query_id: Optional[str] = None  # Direct gap lookup key from Analytics
    # Topic Discovery mode fields
    topic_assignment_ids: List[str] = Field(default_factory=list)
    td_effective_slug: Optional[str] = None
    td_ga_run_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Feedback Routing
# ---------------------------------------------------------------------------


class FeedbackRoute(str, Enum):
    """Evaluation feedback routing classification.

    Determines where failed evaluation results are routed:
      - PASS: all dimensions passed, proceed to HITL or publish
      - SECTION_LEVEL: targeted revision of specific sections/dimensions
      - MAJOR_CHANGE: fundamental re-brief via Agent 2
    """

    PASS = "pass"
    SECTION_LEVEL = "section_level"
    MAJOR_CHANGE = "major_change"


# ---------------------------------------------------------------------------
# LLM Client Response
# ---------------------------------------------------------------------------


class LLMResponse(BaseModel):
    """Standardised response from the LiteLLM wrapper."""

    content: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    finish_reason: str = ""
