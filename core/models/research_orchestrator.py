"""Pydantic models for the Research Orchestrator — KB → AP → VSG DAG.

Orchestrates three research pipelines sequentially:
  1. Knowledge Base (KB) — company context + agent docs
  2. Audience Persona (AP) — persona profiles (depends on KB)
  3. Voice Style Guide (VSG) — style guide (depends on KB + AP)

All fields have defaults for backward compatibility.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Config models
# ---------------------------------------------------------------------------


class AutoApproveConfig(BaseModel):
    """Per-pipeline auto-approve checkpoint configuration."""

    kb: List[int] = Field(default_factory=list)   # Valid: 1, 2, 3
    ap: List[int] = Field(default_factory=list)   # Valid: 1, 2
    vsg: List[int] = Field(default_factory=list)  # Valid: 1


class PipelineSkipConfig(BaseModel):
    """Controls which pipelines to skip if artifacts are fresh."""

    skip_kb_if_fresh: bool = True
    skip_ap_if_fresh: bool = True
    skip_vsg_if_fresh: bool = True


# ---------------------------------------------------------------------------
# Sub-pipeline result
# ---------------------------------------------------------------------------


class SubPipelineStatus(str, Enum):
    """Status of a single sub-pipeline within the orchestrator."""

    pending = "pending"
    running = "running"
    skipped = "skipped"
    completed = "completed"
    failed = "failed"


class SubPipelineResult(BaseModel):
    """Result from one sub-pipeline within the orchestrator."""

    pipeline: str = ""
    status: SubPipelineStatus = SubPipelineStatus.pending
    skip_reason: Optional[str] = None
    execution_time_s: float = 0.0
    error: Optional[str] = None
    output_summary: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Orchestrator status
# ---------------------------------------------------------------------------


class OrchestratorStatus(str, Enum):
    """Terminal status for the orchestrator run."""

    completed = "completed"                  # All requested pipelines succeeded
    completed_partial = "completed_partial"  # Some skipped by config/exclusion
    failed = "failed"                        # A pipeline errored out


# ---------------------------------------------------------------------------
# Pipeline I/O
# ---------------------------------------------------------------------------


class ResearchOrchestratorInput(BaseModel):
    """Unified input for the KB → AP → VSG orchestrator."""

    company_name: str
    domain: str = ""
    company_slug: Optional[str] = None
    workspace_id: str = ""
    workspace_slug: str = ""
    product_slug: Optional[str] = None
    product_name: Optional[str] = None

    # KB-specific
    seed_urls: List[str] = Field(default_factory=list)
    internal_sources: List[str] = Field(default_factory=list)
    staleness_threshold_days: int = 30

    # AP-specific
    max_personas: int = Field(default=5, ge=3, le=7)

    # VSG-specific
    max_authors: int = Field(default=3, ge=2, le=3)

    # Shared
    language: str = "en"
    region: Optional[str] = None
    additional_constraints: Optional[str] = None
    force_rerun: bool = False

    # Orchestrator-specific
    auto_approve: AutoApproveConfig = Field(default_factory=AutoApproveConfig)
    skip_config: PipelineSkipConfig = Field(default_factory=PipelineSkipConfig)
    pipelines: List[Literal["kb", "ap", "vsg"]] = Field(
        default=["kb", "ap", "vsg"],
        description="Which pipelines to run. Defaults to all 3 in order.",
    )


class ResearchOrchestratorOutput(BaseModel):
    """Unified output from the orchestrator."""

    slug: str = ""
    company_name: str = ""
    effective_slug: str = ""
    orchestrator_status: OrchestratorStatus = OrchestratorStatus.completed
    pipelines_run: List[str] = Field(default_factory=list)
    pipelines_skipped: List[str] = Field(default_factory=list)
    sub_results: Dict[str, SubPipelineResult] = Field(default_factory=dict)
    total_execution_time_s: float = 0.0

    # Promoted artifact paths
    company_context_path: Optional[str] = None
    persona_dir: Optional[str] = None
    style_guide_path: Optional[str] = None
