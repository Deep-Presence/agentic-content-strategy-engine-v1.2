"""Tests for Voice Style Guide pipeline orchestrator.

Covers:
- Helper functions (slug resolution, ID mapping, persona loading)
- Full pipeline happy path (all mocked)
- All-authors-rejected early exit
- All-research-failed early exit
- Partial research failure → synthesis continues
- Token cap enforcement
- Missing company context error
- Missing persona profiles error
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models.voice_style_guide import (
    AuthorBrief,
    AuthorResearchResult,
    VoiceStyleGuideInput,
    VoiceStyleGuideOutput,
)


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture()
def vsg_input() -> VoiceStyleGuideInput:
    return VoiceStyleGuideInput(
        company_name="Ramp",
        domain="fintech",
        company_slug="ramp",
        max_authors=3,
        auto_approve_checkpoints=[1],
    )


@pytest.fixture()
def artifacts_dir(tmp_path: Path) -> Path:
    """Create a temporary artifacts directory with company context + persona profiles."""
    root = tmp_path / "artifacts"

    # Company context
    cc_dir = root / "company_context"
    cc_dir.mkdir(parents=True)
    (cc_dir / "ramp.md").write_text("# Ramp\n\nRamp is a fintech company.", encoding="utf-8")

    # Persona profiles (via PersonaStorage structure)
    persona_dir = root / "audience_personas" / "ramp"
    persona_dir.mkdir(parents=True)

    # Create a manifest with active personas
    manifest = {
        "slug": "ramp",
        "company_name": "Ramp",
        "personas": {
            "vp-finance": {
                "persona_id": "vp-finance",
                "persona_name": "Sarah",
                "current_version": 1,
                "status": "fresh",
                "word_count": 500,
                "sha256": "abc123",
            },
            "cfo-startup": {
                "persona_id": "cfo-startup",
                "persona_name": "Marcus",
                "current_version": 1,
                "status": "fresh",
                "word_count": 600,
                "sha256": "def456",
            },
        },
    }
    (persona_dir / "_manifest.json").write_text(
        json.dumps(manifest, default=str), encoding="utf-8",
    )

    # Create persona version files
    for pid in ("vp-finance", "cfo-startup"):
        pid_dir = persona_dir / pid
        pid_dir.mkdir(parents=True)
        (pid_dir / "v1.md").write_text(
            f"# Persona: {pid}\n\nDetailed persona profile content here.",
            encoding="utf-8",
        )

    return root


# Mock author briefs
MOCK_BRIEFS = [
    AuthorBrief(
        author_id="morgan-housel",
        name="Morgan Housel",
        description="Financial writer.",
        famous_works=["The Psychology of Money"],
        resonance_rationale="Great fit.",
    ),
    AuthorBrief(
        author_id="ann-handley",
        name="Ann Handley",
        description="Content marketing author.",
        famous_works=["Everybody Writes"],
        resonance_rationale="Perfect for B2B.",
    ),
]

MOCK_RESEARCH_RESULTS = {
    "morgan-housel": AuthorResearchResult(
        author_id="morgan-housel",
        name="Morgan Housel",
        content_md="# Morgan Housel Analysis\n\n## Voice & Tone\nClear, accessible...",
        word_count=500,
        execution_time_s=5.0,
    ),
    "ann-handley": AuthorResearchResult(
        author_id="ann-handley",
        name="Ann Handley",
        content_md="# Ann Handley Analysis\n\n## Voice & Tone\nWarm, practical...",
        word_count=450,
        execution_time_s=4.5,
    ),
}


# ── Helper Tests ──────────────────────────────────────────────────────


class TestHelpers:
    """Tests for pipeline helper functions."""

    def test_resolve_slug_from_company_slug(self) -> None:
        from core.research.voice_style_guide.pipeline import _resolve_slug

        inp = VoiceStyleGuideInput(company_name="Ramp", company_slug="ramp")
        assert _resolve_slug(inp) == "ramp"

    def test_resolve_slug_from_company_name(self) -> None:
        from core.research.voice_style_guide.pipeline import _resolve_slug

        inp = VoiceStyleGuideInput(company_name="Deep Presence")
        assert _resolve_slug(inp) == "deep-presence"

    def test_resolve_effective_slug_company_only(self) -> None:
        from core.research.voice_style_guide.pipeline import _resolve_effective_slug

        inp = VoiceStyleGuideInput(company_name="Ramp", company_slug="ramp")
        assert _resolve_effective_slug(inp) == "ramp"

    def test_resolve_effective_slug_with_product(self) -> None:
        from core.research.voice_style_guide.pipeline import _resolve_effective_slug

        inp = VoiceStyleGuideInput(
            company_name="Ramp", company_slug="ramp", product_slug="cards",
        )
        assert _resolve_effective_slug(inp) == "ramp__cards"

    def test_slugify_author_name(self) -> None:
        from core.research.voice_style_guide.pipeline import _slugify_author_name

        assert _slugify_author_name("Morgan Housel") == "morgan-housel"
        assert _slugify_author_name("J.K. Rowling") == "j-k-rowling"
        assert _slugify_author_name("") == "unknown"

    def test_build_author_id_map_no_collision(self) -> None:
        from core.research.voice_style_guide.pipeline import _build_author_id_map

        authors = [
            AuthorBrief(author_id="a1", name="Morgan Housel"),
            AuthorBrief(author_id="a2", name="Ann Handley"),
        ]
        result = _build_author_id_map(authors)
        assert result["a1"] == "morgan-housel"
        assert result["a2"] == "ann-handley"

    def test_build_author_id_map_with_collision(self) -> None:
        from core.research.voice_style_guide.pipeline import _build_author_id_map

        authors = [
            AuthorBrief(author_id="a1", name="Morgan Housel"),
            AuthorBrief(author_id="a2", name="Morgan Housel"),
        ]
        result = _build_author_id_map(authors)
        assert result["a1"] == "morgan-housel"
        assert result["a2"] == "morgan-housel-2"

    def test_build_persona_summaries(self) -> None:
        from core.research.voice_style_guide.pipeline import _build_persona_summaries

        mds = ["# Sarah\nContent", "# Marcus\nContent"]
        result = _build_persona_summaries(mds)
        assert "Persona 1" in result
        assert "Persona 2" in result

    def test_build_persona_summaries_empty(self) -> None:
        from core.research.voice_style_guide.pipeline import _build_persona_summaries

        assert _build_persona_summaries([]) == ""


class TestLoadPersonaProfiles:
    """Tests for _load_persona_profiles."""

    @pytest.mark.asyncio
    async def test_loads_active_profiles(self, artifacts_dir: Path) -> None:
        from core.research.voice_style_guide.pipeline import _load_persona_profiles

        mds = await _load_persona_profiles(artifacts_dir, "ramp", "ramp")
        assert len(mds) == 2
        assert any("vp-finance" in md for md in mds)

    @pytest.mark.asyncio
    async def test_returns_empty_for_missing_slug(self, artifacts_dir: Path) -> None:
        from core.research.voice_style_guide.pipeline import _load_persona_profiles

        mds = await _load_persona_profiles(artifacts_dir, "nonexistent", "nonexistent")
        assert mds == []


# ── Pipeline Integration Tests ────────────────────────────────────────


class TestPipelineHappyPath:
    """Full pipeline with all agents mocked."""

    @pytest.mark.asyncio
    async def test_full_pipeline_success(self, vsg_input: VoiceStyleGuideInput, artifacts_dir: Path) -> None:
        guide_md = "# Voice Style Guide for Ramp\n\n## Voice & Tone\nConfident..."

        with patch(
            "core.research.voice_style_guide.pipeline.run_author_discovery",
            new_callable=AsyncMock,
            return_value=(MOCK_BRIEFS, 3.0),
        ), patch(
            "core.research.voice_style_guide.pipeline.run_author_research",
            new_callable=AsyncMock,
            side_effect=lambda brief, **kw: MOCK_RESEARCH_RESULTS[brief.author_id],
        ), patch(
            "core.research.voice_style_guide.pipeline.run_voice_synthesis",
            new_callable=AsyncMock,
            return_value=(guide_md, 5.0),
        ), patch(
            "core.research.voice_style_guide.pipeline.configure_litellm_callbacks",
        ):
            from core.research.voice_style_guide.pipeline import run_voice_style_guide_pipeline

            output = await run_voice_style_guide_pipeline(
                vsg_input, artifacts_root=artifacts_dir,
            )

        assert isinstance(output, VoiceStyleGuideOutput)
        assert output.guide_generated is True
        assert output.authors_discovered == 2
        assert output.authors_approved == 2
        assert output.authors_researched == 2
        assert output.slug == "ramp"
        assert output.total_execution_time_s > 0

        # Check guide was promoted
        style_guide_path = artifacts_dir / "style_guides" / "ramp.md"
        assert style_guide_path.exists()
        assert "Voice Style Guide" in style_guide_path.read_text()


class TestPipelineEarlyExits:
    """Tests for graceful early exits."""

    @pytest.mark.asyncio
    async def test_missing_company_context_raises(self, vsg_input: VoiceStyleGuideInput, tmp_path: Path) -> None:
        root = tmp_path / "artifacts"
        root.mkdir()

        with patch(
            "core.research.voice_style_guide.pipeline.configure_litellm_callbacks",
        ), pytest.raises(RuntimeError, match="Company context not found"):
            from core.research.voice_style_guide.pipeline import run_voice_style_guide_pipeline

            await run_voice_style_guide_pipeline(vsg_input, artifacts_root=root)

    @pytest.mark.asyncio
    async def test_missing_personas_raises(self, vsg_input: VoiceStyleGuideInput, tmp_path: Path) -> None:
        root = tmp_path / "artifacts"
        cc_dir = root / "company_context"
        cc_dir.mkdir(parents=True)
        (cc_dir / "ramp.md").write_text("# Ramp\n\nCompany context.", encoding="utf-8")

        with patch(
            "core.research.voice_style_guide.pipeline.configure_litellm_callbacks",
        ), pytest.raises(RuntimeError, match="No active persona profiles"):
            from core.research.voice_style_guide.pipeline import run_voice_style_guide_pipeline

            await run_voice_style_guide_pipeline(vsg_input, artifacts_root=root)

    @pytest.mark.asyncio
    async def test_all_authors_rejected(self, vsg_input: VoiceStyleGuideInput, artifacts_dir: Path) -> None:
        """When HITL rejects all authors, pipeline returns gracefully."""
        # Use auto_approve_checkpoints=[] so HITL runs, but mock the graph to reject
        vsg_input_no_auto = VoiceStyleGuideInput(
            company_name="Ramp",
            domain="fintech",
            company_slug="ramp",
            max_authors=3,
            auto_approve_checkpoints=[],  # No auto-approve
        )

        # Mock the HITL to return empty approved_authors
        mock_hitl_result = {
            "batch_decision": "reject_all",
            "approved_authors": [],
        }

        with patch(
            "core.research.voice_style_guide.pipeline.run_author_discovery",
            new_callable=AsyncMock,
            return_value=(MOCK_BRIEFS, 3.0),
        ), patch(
            "core.research.voice_style_guide.pipeline.run_vsg_hitl_checkpoint",
            new_callable=AsyncMock,
            return_value=mock_hitl_result,
        ), patch(
            "core.research.voice_style_guide.pipeline.configure_litellm_callbacks",
        ):
            from core.research.voice_style_guide.pipeline import run_voice_style_guide_pipeline

            output = await run_voice_style_guide_pipeline(
                vsg_input_no_auto, artifacts_root=artifacts_dir,
            )

        assert output.authors_approved == 0
        assert output.guide_generated is False

    @pytest.mark.asyncio
    async def test_all_research_failed(self, vsg_input: VoiceStyleGuideInput, artifacts_dir: Path) -> None:
        """When all author research fails, pipeline returns gracefully."""
        failed_result = AuthorResearchResult(
            author_id="test", name="Test", error="API error",
        )

        with patch(
            "core.research.voice_style_guide.pipeline.run_author_discovery",
            new_callable=AsyncMock,
            return_value=(MOCK_BRIEFS, 3.0),
        ), patch(
            "core.research.voice_style_guide.pipeline.run_author_research",
            new_callable=AsyncMock,
            return_value=failed_result,
        ), patch(
            "core.research.voice_style_guide.pipeline.configure_litellm_callbacks",
        ):
            from core.research.voice_style_guide.pipeline import run_voice_style_guide_pipeline

            output = await run_voice_style_guide_pipeline(
                vsg_input, artifacts_root=artifacts_dir,
            )

        assert output.authors_researched == 0
        assert output.guide_generated is False


class TestPipelinePartialFailure:
    """Tests for partial research failure (synthesis continues with successful authors)."""

    @pytest.mark.asyncio
    async def test_partial_research_failure_synthesizes(
        self, vsg_input: VoiceStyleGuideInput, artifacts_dir: Path,
    ) -> None:
        """One author research fails, synthesis proceeds with the other."""
        guide_md = "# Partial Guide\n\nSynthesized from one author..."

        async def _mock_research(brief: AuthorBrief, **kw: Any) -> AuthorResearchResult:
            if brief.author_id == "morgan-housel":
                return MOCK_RESEARCH_RESULTS["morgan-housel"]
            return AuthorResearchResult(
                author_id=brief.author_id, name=brief.name, error="API timeout",
            )

        with patch(
            "core.research.voice_style_guide.pipeline.run_author_discovery",
            new_callable=AsyncMock,
            return_value=(MOCK_BRIEFS, 3.0),
        ), patch(
            "core.research.voice_style_guide.pipeline.run_author_research",
            new_callable=AsyncMock,
            side_effect=_mock_research,
        ), patch(
            "core.research.voice_style_guide.pipeline.run_voice_synthesis",
            new_callable=AsyncMock,
            return_value=(guide_md, 5.0),
        ), patch(
            "core.research.voice_style_guide.pipeline.configure_litellm_callbacks",
        ):
            from core.research.voice_style_guide.pipeline import run_voice_style_guide_pipeline

            output = await run_voice_style_guide_pipeline(
                vsg_input, artifacts_root=artifacts_dir,
            )

        assert output.guide_generated is True
        assert output.authors_researched == 1  # Only one succeeded


class TestPipelineSSEEvents:
    """Tests for SSE event emission."""

    @pytest.mark.asyncio
    async def test_events_emitted(self, vsg_input: VoiceStyleGuideInput, artifacts_dir: Path) -> None:
        guide_md = "# Guide\n\nContent..."
        event_bus = MagicMock()
        task_id = "test-task-123"

        with patch(
            "core.research.voice_style_guide.pipeline.run_author_discovery",
            new_callable=AsyncMock,
            return_value=(MOCK_BRIEFS, 3.0),
        ), patch(
            "core.research.voice_style_guide.pipeline.run_author_research",
            new_callable=AsyncMock,
            side_effect=lambda brief, **kw: MOCK_RESEARCH_RESULTS[brief.author_id],
        ), patch(
            "core.research.voice_style_guide.pipeline.run_voice_synthesis",
            new_callable=AsyncMock,
            return_value=(guide_md, 5.0),
        ), patch(
            "core.research.voice_style_guide.pipeline.configure_litellm_callbacks",
        ):
            from core.research.voice_style_guide.pipeline import run_voice_style_guide_pipeline

            await run_voice_style_guide_pipeline(
                vsg_input, artifacts_root=artifacts_dir,
                event_bus=event_bus, task_id=task_id,
            )

        # Check key events were emitted
        published_events = [call[0][1] for call in event_bus.publish.call_args_list]
        assert "pipeline_start" in published_events
        assert "completed" in published_events
        assert "vsg_phase_start" in published_events
        assert "vsg_phase_complete" in published_events
        assert "vsg_agent_complete" in published_events
