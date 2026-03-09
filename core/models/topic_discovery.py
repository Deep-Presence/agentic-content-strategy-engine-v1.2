"""Pydantic models for the Topic Discovery Module.

Covers the full pipeline data flow:
- Pipeline I/O (TopicDiscoveryInput / TopicDiscoveryOutput)
- S1 raw outputs (SubdomainCandidate, SourceResult)
- S2 merge outputs (CaptureRecaptureResult, SubdomainNode, TaxonomyTree)
- S3 expansion outputs (TopicAssignment, TopicAssignmentMatrix)
- Manifest for filesystem versioning (TopicDiscoveryManifest)

All fields have defaults for backward compatibility with existing JSON artifacts.
"""
from __future__ import annotations

import uuid as _uuid_mod
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(_uuid_mod.uuid4())


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class BuyerStage(str, Enum):
    """Buyer journey stage."""

    TOFU = "tofu"
    MOFU = "mofu"
    BOFU = "bofu"


class IntentType(str, Enum):
    """Search intent classification."""

    informational = "informational"
    commercial = "commercial"
    navigational = "navigational"
    transactional = "transactional"


class AudienceSegmentType(str, Enum):
    """Audience segment granularity."""

    individual_persona = "individual_persona"
    team_group = "team_group"


class TopicDiscoveryStatus(str, Enum):
    """Lifecycle status of a Topic Discovery run."""

    draft = "draft"
    hitl_pending = "hitl_pending"
    approved = "approved"
    archived = "archived"


class TDSource(str, Enum):
    """Subdomain generation source identifier."""

    source_a = "source_a"
    source_b = "source_b"
    source_c = "source_c"
    source_d = "source_d"


class RelevanceCell(str, Enum):
    """Relevance classification for a dimension combination."""

    relevant = "relevant"
    marginal = "marginal"
    irrelevant = "irrelevant"


class TopicAssignmentStatus(str, Enum):
    """Lifecycle status of a single topic assignment."""

    not_started = "not_started"
    in_gap_analysis = "in_gap_analysis"
    content_produced = "content_produced"
    published = "published"


# ---------------------------------------------------------------------------
# Pipeline Input / Output
# ---------------------------------------------------------------------------


class TopicDiscoveryInput(BaseModel):
    """Input for the Topic Discovery pipeline orchestrator."""

    company_name: str = ""
    domain: Optional[str] = None
    company_slug: Optional[str] = None
    company_id: Optional[str] = None
    product_slug: Optional[str] = None
    product_name: Optional[str] = None
    seed_urls: List[str] = Field(default_factory=list)
    language: str = "en"
    region: Optional[str] = None
    additional_constraints: Optional[str] = None
    auto_approve_checkpoints: List[int] = Field(default_factory=list)
    max_expansion_rounds: int = 4
    dedup_threshold: float = 0.85


class TopicDiscoveryOutput(BaseModel):
    """Output from the Topic Discovery pipeline orchestrator."""

    id: str = Field(default_factory=_uuid)
    slug: str = ""
    effective_slug: str = ""
    company_name: str = ""
    taxonomy: Optional[TaxonomyTree] = None
    matrix: Optional[TopicAssignmentMatrix] = None
    coverage: Optional[CaptureRecaptureResult] = None
    manifest: Optional[TopicDiscoveryManifest] = None
    taxonomy_version: int = 0
    matrix_version: int = 0
    total_execution_time_s: float = 0.0
    status: TopicDiscoveryStatus = TopicDiscoveryStatus.draft
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# S1: Multi-Source Subdomain Generation
# ---------------------------------------------------------------------------


class SubdomainCandidate(BaseModel):
    """A single subdomain surfaced by one source in one round."""

    id: str = Field(default_factory=_uuid)
    name: str = ""
    description: str = ""
    source: TDSource = TDSource.source_a
    round_number: int = 1
    specialist_lens: Optional[str] = None
    confidence: float = 0.0


class SourceResult(BaseModel):
    """Aggregated output from one source across all expansion rounds."""

    source: TDSource = TDSource.source_a
    candidates: List[SubdomainCandidate] = Field(default_factory=list)
    total_rounds: int = 0
    singletons: int = 0
    doubletons: int = 0
    chao1_estimate: float = 0.0
    source_sample_coverage: float = 0.0
    execution_time_s: float = 0.0
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# S2: Exhaustiveness Evaluation & Merge
# ---------------------------------------------------------------------------


class PerSourceCoverage(BaseModel):
    """Chao1/sample-coverage within a single source across its rounds."""

    source: TDSource = TDSource.source_a
    singletons: int = 0
    doubletons: int = 0
    observed: int = 0
    total_observations: int = 0
    chao1_estimate: float = 0.0
    sample_coverage: float = 0.0


class CaptureRecaptureResult(BaseModel):
    """Statistical coverage metrics from Multi-Source Capture-Recapture."""

    pairwise_estimates: Dict[str, float] = Field(default_factory=dict)
    median_estimate: float = 0.0
    estimate_range: List[float] = Field(default_factory=list)
    # Deprecated: kept for backward compat with old JSON artifacts
    chao1_lower_bound: float = 0.0
    sample_coverage: float = 0.0
    observed_count: int = 0
    total_singletons: int = 0
    total_doubletons: int = 0
    coverage_target: float = 0.95
    meets_target: bool = False
    # New: per-source coverage metrics (correct statistical approach)
    per_source_coverage: Dict[str, PerSourceCoverage] = Field(default_factory=dict)
    aggregate_sample_coverage: float = 0.0
    aggregate_chao1_ratio: float = 0.0


class SubdomainNode(BaseModel):
    """Recursive tree node representing a subdomain in the taxonomy.

    Self-referencing via ``children: List[SubdomainNode]``.
    """

    id: str = Field(default_factory=_uuid)
    name: str = ""
    description: str = ""
    depth: int = 0
    source_provenance: Dict[str, bool] = Field(default_factory=dict)
    confidence: float = 0.0
    is_manually_added: bool = False
    sort_order: int = 0
    children: List[SubdomainNode] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaxonomyTree(BaseModel):
    """Complete taxonomy with coverage metadata."""

    id: str = Field(default_factory=_uuid)
    domain_name: str = ""
    version: int = 1
    status: TopicDiscoveryStatus = TopicDiscoveryStatus.draft
    root_nodes: List[SubdomainNode] = Field(default_factory=list)
    total_subdomains: int = 0
    max_depth: int = 0
    coverage_score: float = 0.0
    chao1_estimate: float = 0.0
    capture_recapture_est: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# S3: Dimensionality Expansion
# ---------------------------------------------------------------------------


class TopicAssignment(BaseModel):
    """A single content opportunity in the dimensionality matrix."""

    id: str = Field(default_factory=_uuid)
    subdomain_id: str = ""
    subdomain_name: str = ""
    topic_text: str = ""
    buyer_stage: BuyerStage = BuyerStage.TOFU
    intent_type: IntentType = IntentType.informational
    audience_segment: str = ""
    audience_segment_type: AudienceSegmentType = AudienceSegmentType.individual_persona
    relevance: RelevanceCell = RelevanceCell.relevant
    priority_score: float = 0.0
    priority_factors: Dict[str, float] = Field(default_factory=dict)
    status: TopicAssignmentStatus = TopicAssignmentStatus.not_started
    is_manually_added: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TopicAssignmentMatrix(BaseModel):
    """Full dimensionality matrix with aggregate statistics."""

    id: str = Field(default_factory=_uuid)
    version: int = 1
    status: TopicDiscoveryStatus = TopicDiscoveryStatus.draft
    assignments: List[TopicAssignment] = Field(default_factory=list)
    total_assignments: int = 0
    total_relevant_cells: int = 0
    total_irrelevant_cells: int = 0
    buyer_stage_distribution: Dict[str, int] = Field(default_factory=dict)
    intent_distribution: Dict[str, int] = Field(default_factory=dict)
    audience_distribution: Dict[str, int] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# Manifest (filesystem versioning)
# ---------------------------------------------------------------------------


class TopicDiscoveryManifest(BaseModel):
    """Top-level manifest for a company's topic discovery artifacts."""

    slug: str = ""
    effective_slug: str = ""
    company_name: str = ""
    domain_name: str = ""
    status: TopicDiscoveryStatus = TopicDiscoveryStatus.draft
    taxonomy_version: int = 0
    matrix_version: int = 0
    created_at: str = Field(default_factory=_utcnow)
    last_updated: Optional[str] = None
    source_results_written: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Forward-ref rebuild (required for recursive SubdomainNode)
# ---------------------------------------------------------------------------

SubdomainNode.model_rebuild()
TopicDiscoveryOutput.model_rebuild()
