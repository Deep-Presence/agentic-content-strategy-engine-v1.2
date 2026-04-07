"""Tests for competitor registry JSON extraction (two-pass pipeline).

Covers:
  - Happy path extraction with mocked llm_call
  - JSON fence handling (Claude Haiku wraps in ```json)
  - LLM failure returns None (graceful degradation)
  - Invalid JSON returns None
  - Metadata population (extraction_model, extraction_timestamp)
  - all_competitor_names() deduplication
  - resolve_competitors_from_kb() with and without JSON sidecar
  - Pipeline integration (_maybe_extract_competitor_json)
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models.knowledge_base import (
    CompetitorProfile,
    CompetitorRegistryStructured,
    KBAgentResult,
    KBDocType,
    KnowledgeBaseInput,
)


# ── Fixtures ──────────────────────────────────────────────────────


SAMPLE_COMPETITOR_JSON = {
    "direct_competitors": [
        {
            "name": "Wix",
            "domain": "wix.com",
            "relevance": "direct",
            "relevance_score": 0.9,
            "key_differentiators": ["800+ templates", "AI builder"],
            "market_position": "Accessibility-first website builder",
            "strengths": ["Large template library", "Freemium model"],
            "weaknesses": ["Limited customization", "Weak CMS"],
            "funding_info": "Public (NASDAQ: WIX)",
            "primary_use_case": "Small business websites",
        },
        {
            "name": "Framer",
            "domain": "framer.com",
            "relevance": "direct",
            "relevance_score": 0.85,
            "key_differentiators": ["Design-native", "Micro-interactions"],
            "market_position": "Designer's website builder",
            "strengths": ["Fast time-to-market", "Real-time collaboration"],
            "weaknesses": ["Limited CMS", "No e-commerce"],
        },
    ],
    "mindshare_competitors": [
        {
            "name": "WordPress",
            "domain": "wordpress.org",
            "relevance": "mindshare",
            "relevance_score": 0.8,
            "strengths": ["Open source", "60k plugins"],
            "weaknesses": ["Operational complexity"],
        },
    ],
    "niche_competitors": [
        {
            "name": "Softr",
            "domain": "softr.io",
            "relevance": "niche",
            "relevance_score": 0.3,
        },
    ],
    "emerging_competitors": [],
    "market_map": "The no-code web platform market segments by feature depth vs ease of use.",
    "competitive_positioning": "Webflow sits at the intersection of design freedom and CMS power.",
    "feature_comparison_summary": "Webflow leads in design flexibility; Wix in templates; Shopify in e-commerce.",
    "total_competitor_count": 4,
    "extraction_model": "",
    "extraction_timestamp": "",
}

SAMPLE_MARKDOWN = """\
# Competitive Landscape: Webflow

## Direct Competitors

### Wix: The Accessibility-First Alternative
Wix has 800+ templates and an AI builder.
**Wix's Competitive Strengths:** Large template library, Freemium model.
**Where Wix Falls Short:** Limited customization, Weak CMS.
**Comparative Relevance: Direct (High)**

### Framer: The Design-Native Competitor
Framer enables fast design-to-site workflows.
**Comparative Relevance: Direct (High)**

## Mindshare Competitors

### WordPress: The Open-Source Incumbent
WordPress powers 43% of websites.
**Comparative Relevance: Mindshare (Very High)**
"""


def _make_llm_response(content: str, model: str = "anthropic/claude-haiku-4.5"):
    return SimpleNamespace(
        content=content, model=model,
        input_tokens=500, output_tokens=1200, total_tokens=1700,
    )


# ── Extraction Tests ──────────────────────────────────────────────


class TestExtractCompetitorRegistryJson:
    """Tests for extract_competitor_registry_json()."""

    @pytest.mark.asyncio
    async def test_happy_path(self):
        """Successful extraction returns validated dict."""
        response_json = json.dumps(SAMPLE_COMPETITOR_JSON)

        with patch(
            "core.content_engine.llm_client.llm_call",
            new_callable=AsyncMock,
            return_value=_make_llm_response(response_json),
        ):
            from core.research.knowledge_base.extraction import (
                extract_competitor_registry_json,
            )

            result = await extract_competitor_registry_json(
                SAMPLE_MARKDOWN, company_name="Webflow",
            )

        assert result is not None
        assert len(result["direct_competitors"]) == 2
        assert result["direct_competitors"][0]["name"] == "Wix"
        assert result["total_competitor_count"] == 4
        assert result["extraction_model"] != ""
        assert result["extraction_timestamp"] != ""

    @pytest.mark.asyncio
    async def test_fenced_json(self):
        """Handles JSON wrapped in markdown code fences."""
        fenced = "```json\n" + json.dumps(SAMPLE_COMPETITOR_JSON) + "\n```"

        with patch(
            "core.content_engine.llm_client.llm_call",
            new_callable=AsyncMock,
            return_value=_make_llm_response(fenced),
        ):
            from core.research.knowledge_base.extraction import (
                extract_competitor_registry_json,
            )

            result = await extract_competitor_registry_json(
                SAMPLE_MARKDOWN, company_name="Webflow",
            )

        assert result is not None
        assert result["direct_competitors"][0]["name"] == "Wix"

    @pytest.mark.asyncio
    async def test_llm_failure_returns_none(self):
        """LLM call failure returns None without raising."""
        with patch(
            "core.content_engine.llm_client.llm_call",
            new_callable=AsyncMock,
            side_effect=RuntimeError("OpenRouter unavailable"),
        ):
            from core.research.knowledge_base.extraction import (
                extract_competitor_registry_json,
            )

            result = await extract_competitor_registry_json(
                SAMPLE_MARKDOWN, company_name="Webflow",
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_json_returns_none(self):
        """Malformed JSON response returns None."""
        with patch(
            "core.content_engine.llm_client.llm_call",
            new_callable=AsyncMock,
            return_value=_make_llm_response("This is not JSON at all."),
        ):
            from core.research.knowledge_base.extraction import (
                extract_competitor_registry_json,
            )

            result = await extract_competitor_registry_json(
                SAMPLE_MARKDOWN, company_name="Webflow",
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_short_markdown_skipped(self):
        """Markdown shorter than 100 chars is skipped."""
        from core.research.knowledge_base.extraction import (
            extract_competitor_registry_json,
        )

        result = await extract_competitor_registry_json("# Short", company_name="X")
        assert result is None

    @pytest.mark.asyncio
    async def test_metadata_stamped(self):
        """extraction_model and extraction_timestamp are populated."""
        response_json = json.dumps(SAMPLE_COMPETITOR_JSON)

        with patch(
            "core.content_engine.llm_client.llm_call",
            new_callable=AsyncMock,
            return_value=_make_llm_response(response_json, model="anthropic/claude-haiku-4-5"),
        ):
            from core.research.knowledge_base.extraction import (
                extract_competitor_registry_json,
            )

            result = await extract_competitor_registry_json(
                SAMPLE_MARKDOWN, company_name="Webflow",
            )

        assert result is not None
        assert result["extraction_model"] == "anthropic/claude-haiku-4-5"
        assert "T" in result["extraction_timestamp"]  # ISO format


# ── Model Tests ───────────────────────────────────────────────────


class TestAllCompetitorNames:
    """Tests for CompetitorRegistryStructured.all_competitor_names()."""

    def test_deduplication(self):
        """Duplicate names across categories are deduplicated."""
        reg = CompetitorRegistryStructured(
            direct_competitors=[
                CompetitorProfile(name="Wix"),
                CompetitorProfile(name="Framer"),
            ],
            mindshare_competitors=[
                CompetitorProfile(name="Wix"),  # duplicate
                CompetitorProfile(name="WordPress"),
            ],
            niche_competitors=[
                CompetitorProfile(name="Softr"),
            ],
        )
        names = reg.all_competitor_names()
        assert names == ["Wix", "Framer", "WordPress", "Softr"]

    def test_empty(self):
        """Empty registry returns empty list."""
        reg = CompetitorRegistryStructured()
        assert reg.all_competitor_names() == []

    def test_skips_empty_names(self):
        """Competitors with empty name are skipped."""
        reg = CompetitorRegistryStructured(
            direct_competitors=[
                CompetitorProfile(name=""),
                CompetitorProfile(name="Wix"),
            ],
        )
        assert reg.all_competitor_names() == ["Wix"]


# ── Resolve from KB Tests ─────────────────────────────────────────


class TestResolveCompetitorsFromKB:
    """Tests for resolve_competitors_from_kb()."""

    def test_with_json_sidecar(self):
        """Returns competitor names when JSON sidecar exists."""
        mock_version = SimpleNamespace(
            content_md="# Competitors...",
            content_json=SAMPLE_COMPETITOR_JSON,
        )
        mock_storage = MagicMock()

        with patch(
            "core.research.knowledge_base.storage.KBStorage",
        ) as MockKBStorage:
            instance = MockKBStorage.return_value
            instance.get_latest_version.return_value = mock_version

            from core.research.knowledge_base.extraction import (
                resolve_competitors_from_kb,
            )

            names = resolve_competitors_from_kb("webflow", mock_storage)

        assert "Wix" in names
        assert "Framer" in names
        assert "WordPress" in names
        assert len(names) == 4

    def test_no_json_sidecar(self):
        """Returns empty list when no JSON sidecar exists."""
        mock_version = SimpleNamespace(content_md="# Competitors...", content_json=None)
        mock_storage = MagicMock()

        with patch(
            "core.research.knowledge_base.storage.KBStorage",
        ) as MockKBStorage:
            instance = MockKBStorage.return_value
            instance.get_latest_version.return_value = mock_version

            from core.research.knowledge_base.extraction import (
                resolve_competitors_from_kb,
            )

            names = resolve_competitors_from_kb("webflow", mock_storage)

        assert names == []

    def test_no_kb_at_all(self):
        """Returns empty list when no KB exists."""
        mock_storage = MagicMock()

        with patch(
            "core.research.knowledge_base.storage.KBStorage",
        ) as MockKBStorage:
            instance = MockKBStorage.return_value
            instance.get_latest_version.return_value = None

            from core.research.knowledge_base.extraction import (
                resolve_competitors_from_kb,
            )

            names = resolve_competitors_from_kb("unknown-co", mock_storage)

        assert names == []


# ── Pipeline Integration Tests ────────────────────────────────────


class TestMaybeExtractCompetitorJson:
    """Tests for _maybe_extract_competitor_json() pipeline helper."""

    @pytest.mark.asyncio
    async def test_extracts_for_competitor_registry(self):
        """Extraction is called for competitor_registry doc type."""
        result = KBAgentResult(
            doc_type=KBDocType.COMPETITOR_REGISTRY,
            content_md=SAMPLE_MARKDOWN,
        )
        input_data = KnowledgeBaseInput(company_name="Webflow")

        with patch(
            "core.research.knowledge_base.extraction.extract_competitor_registry_json",
            new_callable=AsyncMock,
            return_value=SAMPLE_COMPETITOR_JSON,
        ):
            from core.research.knowledge_base.pipeline import (
                _maybe_extract_competitor_json,
            )

            await _maybe_extract_competitor_json(result, input_data)

        assert result.content_json is not None
        assert result.content_json["direct_competitors"][0]["name"] == "Wix"

    @pytest.mark.asyncio
    async def test_skips_non_competitor_doc(self):
        """Does nothing for non-competitor doc types."""
        result = KBAgentResult(
            doc_type=KBDocType.COMPANY_OVERVIEW,
            content_md="# Company overview...",
        )
        input_data = KnowledgeBaseInput(company_name="Webflow")

        from core.research.knowledge_base.pipeline import (
            _maybe_extract_competitor_json,
        )

        await _maybe_extract_competitor_json(result, input_data)
        assert result.content_json is None

    @pytest.mark.asyncio
    async def test_skips_on_error(self):
        """Does nothing when agent result has an error."""
        result = KBAgentResult(
            doc_type=KBDocType.COMPETITOR_REGISTRY,
            content_md=SAMPLE_MARKDOWN,
            error="Agent failed",
        )
        input_data = KnowledgeBaseInput(company_name="Webflow")

        from core.research.knowledge_base.pipeline import (
            _maybe_extract_competitor_json,
        )

        await _maybe_extract_competitor_json(result, input_data)
        assert result.content_json is None

    @pytest.mark.asyncio
    async def test_graceful_on_extraction_failure(self):
        """Pipeline continues when extraction fails."""
        result = KBAgentResult(
            doc_type=KBDocType.COMPETITOR_REGISTRY,
            content_md=SAMPLE_MARKDOWN,
        )
        input_data = KnowledgeBaseInput(company_name="Webflow")

        with patch(
            "core.research.knowledge_base.extraction.extract_competitor_registry_json",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM down"),
        ):
            from core.research.knowledge_base.pipeline import (
                _maybe_extract_competitor_json,
            )

            # Should not raise
            await _maybe_extract_competitor_json(result, input_data)

        assert result.content_json is None
        assert result.error is None  # Original error not set
