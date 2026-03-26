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

from api.services.brand_data_service import _CACHE, get_research_artifacts


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear TTL cache before each test."""
    _CACHE.clear()
    yield
    _CACHE.clear()


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

    def test_manifest_persona_detected(self, tmp_path: Path):
        """Manifest-based path: audience_personas/{slug}/_manifest.json + {pid}/v1.md"""
        import json as _json

        slug = "test-co"
        base = tmp_path / "audience_personas" / slug
        (base / "persona-001").mkdir(parents=True)
        (base / "persona-001" / "v1.md").write_text("# VP of Marketing\n\nSenior decision maker.")
        manifest = {"slug": slug, "personas": {
            "persona-001": {
                "persona_name": "VP of Marketing",
                "kind": "icp",
                "status": "fresh",
                "current_version": 1,
                "last_updated": "2026-03-24T00:00:00+00:00",
            }
        }}
        (base / "_manifest.json").write_text(_json.dumps(manifest))

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
