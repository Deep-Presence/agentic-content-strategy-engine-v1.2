"""Request/response schemas for the Content-to-Prompt pipeline API.

Endpoints under ``/api/v1/content-to-prompt/``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Request schemas ───────────────────────────────────────────────────


class GeneratePromptsRequest(BaseModel):
    """POST /generate — trigger prompt generation for content inventory pages."""

    page_ids: list[str] = Field(
        ...,
        description="Content inventory UUIDs to process.",
        min_length=1,
    )
    k: int = Field(
        default=6,
        ge=4,
        le=12,
        description="Number of prompts to generate per page.",
    )
    auto_approve: bool | None = Field(
        default=None,
        description="Override company default. None = use company config.",
    )
    brand_name: str | None = None
    brand_category: str | None = None
    competitors: list[str] | None = None


class GenerateAllRequest(BaseModel):
    """POST /generate-all — generate for all unprocessed inventory pages."""

    k: int = Field(default=6, ge=4, le=12)
    auto_approve: bool | None = None
    brand_name: str | None = None
    brand_category: str | None = None
    competitors: list[str] | None = None


class ApprovePromptsRequest(BaseModel):
    """POST /approve — bulk approve pending prompts."""

    link_ids: list[str] = Field(
        ...,
        description="content_inventory_prompts row UUIDs to approve.",
        min_length=1,
    )


class UpdateConfigRequest(BaseModel):
    """PUT /config — update company content-to-prompt config."""

    auto_approve: bool | None = None
    k: int | None = Field(default=None, ge=4, le=12)


# ── Response schemas ──────────────────────────────────────────────────


class GeneratePromptsResponse(BaseModel):
    """Response for prompt generation endpoints."""

    generation_run_id: str = ""
    task_id: str | None = None
    pages_processed: int = 0
    pages_succeeded: int = 0
    pages_failed: int = 0
    prompts_created: int = 0
    prompts_deduplicated: int = 0
    errors: list[dict[str, str]] = Field(default_factory=list)


class LinkedPromptItem(BaseModel):
    """A tracked prompt linked to a content inventory page."""

    link_id: str = ""
    prompt_id: str = ""
    text: str = ""
    buyer_stage: str | None = None
    intent_type: str | None = None
    is_branded: bool = False
    approved: bool = True
    is_user_edited: bool = False
    active: bool = True
    category: str | None = None
    source: str = ""
    created_at: datetime | None = None


class PagePromptsResponse(BaseModel):
    """GET /pages/{id}/prompts — prompts linked to a page."""

    inventory_id: str = ""
    prompts: list[LinkedPromptItem] = Field(default_factory=list)
    total: int = 0


class PageMetricsResponse(BaseModel):
    """GET /pages/{id}/metrics — per-page aggregated visibility metrics."""

    inventory_id: str = ""
    total_prompts: int = 0
    active_prompts: int = 0
    mention_rate: float = 0.0
    citation_rate: float = 0.0
    total_responses: int = 0
    by_buyer_stage: list[dict[str, Any]] = Field(default_factory=list)


class PendingPromptItem(BaseModel):
    """A pending (unapproved) link awaiting review."""

    link_id: str = ""
    inventory_id: str = ""
    prompt_id: str = ""
    prompt_text: str = ""
    buyer_stage: str | None = None
    intent_type: str | None = None
    is_branded: bool = False
    page_title: str = ""
    page_url: str = ""


class PendingPromptsResponse(BaseModel):
    """GET /pending — list of pending prompts awaiting approval."""

    pending: list[PendingPromptItem] = Field(default_factory=list)
    total: int = 0


class ApprovePromptsResponse(BaseModel):
    """POST /approve — result of bulk approval."""

    approved_count: int = 0


class ContentToPromptConfig(BaseModel):
    """GET/PUT /config — company content-to-prompt configuration."""

    auto_approve: bool = True
    k: int = 6
