"""Response models for content data endpoints (Phase 3).

Maps backend ContentBrief/ContentPiece/RevisionHistory models
to frontend ContentBriefItem/ContentBriefStatus TypeScript types.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Brief list (matches frontend ContentBriefItem)
# ---------------------------------------------------------------------------


class GapContextSummary(BaseModel):
    """Gap analysis context attached to a content brief for the sidebar."""

    gap_score: float = 0.0
    classification: str = ""
    company_similarity: float = 0.0
    citation_similarity: float = 0.0
    company_cited: bool = False
    company_best_url: str = ""
    why_picked: List[str] = Field(default_factory=list)
    success_indicators: List[Dict[str, str]] = Field(default_factory=list)
    exemplars: List[Dict[str, Any]] = Field(default_factory=list)


class ContentBriefListItem(BaseModel):
    """Summary item for the brief list view."""

    id: str  # brief_id
    title: str = ""
    status: str = "suggested"
    content_type: str = "blog"  # mapped from backend content_format
    cluster: str = ""
    target_word_count: int = 0
    citability_score: Optional[float] = None  # 0-100, from eval overall_score
    cycle_id: Optional[str] = None  # run_metadata session_id
    created_at: str = ""  # ISO string, from briefs.json mtime
    updated_at: str = ""  # ISO string, from latest stage file mtime
    gap_context: Optional[GapContextSummary] = None


class ContentBriefListResponse(BaseModel):
    """Response for GET /briefs."""

    briefs: List[ContentBriefListItem] = Field(default_factory=list)
    total: int = 0


class AddBriefRequest(BaseModel):
    """Request body for POST /briefs — immediately add a topic to the content cycle."""

    title: str = Field(..., min_length=1, max_length=500)
    cluster: str = ""
    description: str = ""
    source: str = "manual"  # "citation", "topic_discovery", "manual"
    gap_query_id: str = ""  # direct query_id for deterministic gap context lookup


# ---------------------------------------------------------------------------
# Brief detail
# ---------------------------------------------------------------------------


class EvalDimension(BaseModel):
    """Single evaluation dimension result."""

    dimension: str = ""
    passed: bool = False
    score: float = 0.0
    feedback: str = ""


class EvalCycle(BaseModel):
    """One evaluation cycle across all dimensions."""

    cycle: int = 0
    dimensions: List[EvalDimension] = Field(default_factory=list)
    overall_passed: bool = False
    overall_score: float = 0.0


class BriefExemplar(BaseModel):
    """Structural fingerprint of a top-cited exemplar."""

    url: str = ""
    word_count: int = 0
    authority_type: str = ""
    content_type: str = ""
    snippet: str = ""


class ContentBriefDetailResponse(BaseModel):
    """Response for GET /briefs/{brief_id}."""

    id: str
    title: str = ""
    status: str = "suggested"
    content_type: str = "blog"
    cluster: str = ""
    target_word_count: Dict[str, int] = Field(
        default_factory=lambda: {"min": 0, "max": 0}
    )
    structural_targets: Dict[str, Any] = Field(default_factory=dict)
    key_topics: List[str] = Field(default_factory=list)
    key_angles: List[str] = Field(default_factory=list)
    priority_score: float = 0.0
    citability_score: Optional[float] = None
    eval_history: List[EvalCycle] = Field(default_factory=list)
    final_passed: bool = False
    exemplars: List[BriefExemplar] = Field(default_factory=list)
    available_stages: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage content
# ---------------------------------------------------------------------------


class StageContentResponse(BaseModel):
    """Response for GET /briefs/{brief_id}/{stage}."""

    brief_id: str
    stage: str
    content_type: str = "text/markdown"  # or "application/json"
    content: Any = ""  # str for markdown, dict for JSON stages


# ---------------------------------------------------------------------------
# Embedding projections (used by gap_data router)
# ---------------------------------------------------------------------------


class EmbeddingPoint(BaseModel):
    """Single 2D point in embedding projection."""

    x: float = 0.0
    y: float = 0.0
    type: str = ""  # "query", "citation", "company"
    id: str = ""  # "q-0", "c-14", "co-3"
    label: str = ""
    cluster: str = ""
    cluster_id: str = ""  # for frontend drill-down lookup
    query_id: Optional[str] = None
    similarity: Optional[float] = None
    gap_score: Optional[float] = None


class EmbeddingProjectionResponse(BaseModel):
    """Response for GET /gap-analysis/embeddings."""

    method: str = "umap"
    point_count: int = 0
    points: List[EmbeddingPoint] = Field(default_factory=list)
