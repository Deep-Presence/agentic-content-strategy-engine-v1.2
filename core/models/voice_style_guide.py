"""Pydantic models for the Voice Style Guide pipeline.

Three-stage pipeline:
  Stage 1 — Author Discovery (LiteLLM → Gemini Flash)
  Stage 2 — Author Research (Perplexity sonar-deep-research)
  Stage 3 — Voice Synthesis (LiteLLM → Claude Sonnet)

All fields have defaults for backward compatibility with existing JSON artifacts.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# Single source of truth for author count constraints across the pipeline.
VSG_MIN_AUTHORS: int = 2
VSG_MAX_AUTHORS_LIMIT: int = 3


# ---------------------------------------------------------------------------
# Stage 1 — Author Discovery
# ---------------------------------------------------------------------------


class WorkPersonaMapping(BaseModel):
    """Maps an author's work to a specific audience persona."""

    work_title: str = ""
    persona_id: str = ""
    persona_name: str = ""
    relevance: str = ""


class AuthorBrief(BaseModel):
    """A discovered author from Stage 1."""

    author_id: str = ""
    name: str = ""
    description: str = ""
    famous_works: List[str] = Field(default_factory=list)
    resonance_rationale: str = ""
    work_persona_mapping: List[WorkPersonaMapping] = Field(default_factory=list)
    source: Literal["agent", "manual", "hybrid"] = "agent"


# ---------------------------------------------------------------------------
# Stage 2 — Author Research
# ---------------------------------------------------------------------------


class AuthorResearchResult(BaseModel):
    """Result from deep research on one author."""

    author_id: str = ""
    name: str = ""
    content_md: str = ""
    word_count: int = 0
    execution_time_s: float = 0.0
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Manifest entries
# ---------------------------------------------------------------------------


class AuthorEntry(BaseModel):
    """Manifest entry tracking one author's research."""

    author_id: str = ""
    name: str = ""
    current_version: int = 0
    last_updated: Optional[datetime] = None
    status: Literal["fresh", "stale", "missing", "archived"] = "missing"
    word_count: int = 0
    sha256: str = ""


class VoiceStyleGuideEntry(BaseModel):
    """Manifest entry for the synthesized voice style guide."""

    current_version: int = 0
    last_updated: Optional[datetime] = None
    status: Literal["fresh", "stale", "missing"] = "missing"
    word_count: int = 0
    sha256: str = ""
    source_authors: List[str] = Field(default_factory=list)


class VoiceStyleGuideManifest(BaseModel):
    """Top-level manifest for voice style guide artifacts."""

    slug: str = ""
    company_name: str = ""
    created_at: Optional[datetime] = None
    last_full_run: Optional[datetime] = None
    authors: Dict[str, AuthorEntry] = Field(default_factory=dict)
    guide: VoiceStyleGuideEntry = Field(default_factory=VoiceStyleGuideEntry)
    ap_manifest_version: Optional[str] = None


# ---------------------------------------------------------------------------
# Pipeline I/O
# ---------------------------------------------------------------------------


class VoiceStyleGuideInput(BaseModel):
    """Input for the voice style guide pipeline."""

    company_name: str
    domain: Optional[str] = None
    company_slug: Optional[str] = None
    workspace_id: str = ""
    workspace_slug: str = ""
    product_slug: Optional[str] = None
    product_name: Optional[str] = None
    max_authors: int = Field(default=VSG_MAX_AUTHORS_LIMIT, ge=VSG_MIN_AUTHORS, le=VSG_MAX_AUTHORS_LIMIT)
    language: str = "en"
    region: Optional[str] = None
    additional_constraints: Optional[str] = None
    auto_approve_checkpoints: List[int] = Field(default_factory=list)


class VoiceStyleGuideOutput(BaseModel):
    """Output from the voice style guide pipeline."""

    slug: str = ""
    company_name: str = ""
    manifest: Optional[VoiceStyleGuideManifest] = None
    authors_discovered: int = 0
    authors_approved: int = 0
    authors_researched: int = 0
    guide_generated: bool = False
    guide_dir: str = ""
    style_guide_path: str = ""
    total_execution_time_s: float = 0.0
