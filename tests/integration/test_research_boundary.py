"""Integration tests for research pipeline write-then-read boundary.

Verifies that knowledge base, persona, and style guide artifacts
can be correctly read by the brand data service layer.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services.brand_data_service import get_research_artifacts


# ── Fixtures ─────────────────────────────────────────────────────────


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ── Company context ──────────────────────────────────────────────────


class TestCompanyContext:
    """Test reading company_context/ artifacts."""

    def test_approved_context_detected(self, tmp_path: Path):
        slug = "test-co"
        _write_text(
            tmp_path / "company_context" / f"{slug}.md",
            "# Test Company\n\nA B2B SaaS platform.",
        )

        result = get_research_artifacts(tmp_path, slug)

        assert result.company_context.status == "approved"

    def test_draft_context_detected(self, tmp_path: Path):
        slug = "test-co"
        _write_text(
            tmp_path / "company_context" / f"{slug}.draft.md",
            "# Test Company Draft\n\nWIP.",
        )

        result = get_research_artifacts(tmp_path, slug)

        assert result.company_context.status == "draft"

    def test_missing_context_returns_none_status(self, tmp_path: Path):
        slug = "test-co"

        result = get_research_artifacts(tmp_path, slug)

        assert result.company_context.status == "none"


# ── Style guide ──────────────────────────────────────────────────────


class TestStyleGuide:
    """Test reading style_guides/ artifacts."""

    def test_approved_style_guide_detected(self, tmp_path: Path):
        slug = "test-co"
        _write_text(
            tmp_path / "style_guides" / f"{slug}.md",
            "# Voice Style Guide\n\nTone: Professional.",
        )

        result = get_research_artifacts(tmp_path, slug)

        assert result.style_guide.status == "approved"

    def test_draft_style_guide_detected(self, tmp_path: Path):
        slug = "test-co"
        _write_text(
            tmp_path / "style_guides" / f"{slug}.draft.md",
            "# Voice Style Guide Draft",
        )

        result = get_research_artifacts(tmp_path, slug)

        assert result.style_guide.status == "draft"


# ── Personas ─────────────────────────────────────────────────────────


class TestPersonas:
    """Test reading audience persona artifacts (new + legacy paths)."""

    def test_legacy_persona_detected(self, tmp_path: Path):
        """Legacy path: artifacts/personas/{slug}__persona-{id}.md"""
        slug = "test-co"
        _write_text(
            tmp_path / "personas" / f"{slug}__persona-001.md",
            "# VP of Marketing\n\nSenior decision maker.",
        )

        result = get_research_artifacts(tmp_path, slug)

        assert len(result.personas) >= 1

    def test_no_personas_returns_empty(self, tmp_path: Path):
        slug = "test-co"

        result = get_research_artifacts(tmp_path, slug)

        assert result.personas == []


# ── Effective slug fallback ──────────────────────────────────────────


class TestEffectiveSlugFallback:
    """Test that effective_slug artifacts fall back to company_slug."""

    def test_effective_slug_artifacts_found(self, tmp_path: Path):
        slug = "ramp__card"
        _write_text(
            tmp_path / "company_context" / f"{slug}.md",
            "# Ramp Card\n\nProduct-specific context.",
        )

        result = get_research_artifacts(tmp_path, slug)

        assert result.company_context.status == "approved"

    def test_company_slug_fallback_for_context(self, tmp_path: Path):
        """If effective_slug context missing, company_slug is NOT auto-tried
        (service uses exact slug passed in — caller handles fallback)."""
        slug = "ramp__card"
        # Only write company-level context, not product-level
        _write_text(
            tmp_path / "company_context" / "ramp.md",
            "# Ramp\n\nCompany-level context.",
        )

        result = get_research_artifacts(tmp_path, slug)

        # Service does NOT auto-fallback — caller (router) handles this
        assert result.company_context.status == "none"
