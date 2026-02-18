"""Shared fixtures for content engine tests.

Provides mock LLM responses, sample briefs, and formatted content
for testing all pipeline stages without real API calls.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models.content_generation import (
    ContentBrief,
    ContentDraft,
    ContentGenerationInput,
    ContentOutline,
    EnrichedDraft,
    ExemplarSummary,
    FormattedContent,
    OutlineSection,
    PlannerOutput,
    StructuralTargets,
    TargetQuery,
)


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_input() -> ContentGenerationInput:
    return ContentGenerationInput(
        company_name="TestCo",
        domain="testco.com",
        company_context_path=None,
        max_briefs=2,
        max_concurrent_workers=1,
        max_revision_cycles=1,
        auto_approve=True,
    )


@pytest.fixture
def sample_brief() -> ContentBrief:
    return ContentBrief(
        brief_id="brief-001",
        title="Understanding 409A Valuations for Startups",
        target_queries=[
            TargetQuery(query_text="what is a 409A valuation", cluster_name="equity"),
            TargetQuery(query_text="409A valuation startup", cluster_name="equity"),
        ],
        target_cluster="equity",
        content_format="long_blog",
        funnel_stage="awareness",
        word_count_range=(1200, 2000),
        structural_targets=StructuralTargets(
            min_headers=4, min_lists=2, min_citations=3,
            min_paragraphs=10, faq_rate=0.4, min_stats=3,
        ),
        key_topics=["409A", "startup equity", "fair market value"],
        key_angles=["compliance requirements", "timing considerations"],
        exemplar_summaries=[
            ExemplarSummary(
                url="https://carta.com/blog/409a-valuations",
                word_count=2200,
                header_count=7,
                list_item_count=12,
                stat_count=5,
                citation_count=4,
                authority_type="industry_report",
                content_type="long_blog",
                snippet="A 409A valuation determines the fair market value...",
            ),
            ExemplarSummary(
                url="https://example.com/equity-comp-guide",
                word_count=1800,
                header_count=5,
                list_item_count=8,
                stat_count=3,
                authority_type="company_blog",
                content_type="how_to",
            ),
        ],
        exemplar_themes=["compliance-driven", "step-by-step process", "IRS regulations"],
    )


@pytest.fixture
def sample_outline() -> ContentOutline:
    return ContentOutline(
        brief_id="brief-001",
        title="Understanding 409A Valuations for Startups",
        sections=[
            OutlineSection(
                heading="What Is a 409A Valuation?",
                level=2,
                key_points=["Definition", "Legal basis"],
                target_word_count=300,
                structural_elements=["definition", "statistics"],
                self_contained_claims=2,
            ),
            OutlineSection(
                heading="Why Startups Need 409A Valuations",
                level=2,
                key_points=["Compliance", "Tax implications"],
                target_word_count=400,
                structural_elements=["bullet_list", "statistics"],
                self_contained_claims=3,
            ),
            OutlineSection(
                heading="The 409A Valuation Process",
                level=2,
                key_points=["Steps", "Timeline", "Providers"],
                target_word_count=400,
                structural_elements=["numbered_list", "table"],
                self_contained_claims=2,
            ),
            OutlineSection(
                heading="Key Considerations and Timing",
                level=2,
                key_points=["When to get one", "Cost factors"],
                target_word_count=300,
                structural_elements=["bullet_list"],
                self_contained_claims=1,
            ),
        ],
        total_target_words=1400,
        has_faq_section=False,
        has_table_section=True,
        has_key_takeaways=False,
    )


@pytest.fixture
def sample_draft() -> ContentDraft:
    return ContentDraft(
        brief_id="brief-001",
        title="Understanding 409A Valuations for Startups",
        markdown="# Understanding 409A Valuations\n\n## What Is a 409A Valuation?\n\n"
        "A 409A valuation is an independent appraisal of the fair market value of a "
        "private company's common stock. Named after Section 409A of the Internal Revenue Code, "
        "this valuation is required whenever a company issues stock options to employees.\n\n"
        "## Why Startups Need 409A Valuations\n\n"
        "Every startup that grants stock options must obtain a 409A valuation. "
        "Failure to do so can result in significant tax penalties for employees.\n\n"
        "- Compliance with IRS regulations\n- Protection from tax penalties\n"
        "- Fair pricing for stock options\n\n"
        "## The 409A Valuation Process\n\n"
        "The process typically involves:\n\n"
        "1. Selecting a qualified valuation firm\n"
        "2. Providing financial documents\n"
        "3. Analysis using accepted methodologies\n"
        "4. Delivery of the valuation report\n\n"
        "[STAT: percentage of startups that get 409A valuations]\n\n"
        "## Key Considerations\n\n"
        "Companies should get a new 409A valuation every 12 months or after a material event "
        "such as a funding round. Costs range from $5,000 to $50,000 depending on complexity.",
        word_count=180,
    )


@pytest.fixture
def sample_enriched() -> EnrichedDraft:
    return EnrichedDraft(
        brief_id="brief-001",
        title="Understanding 409A Valuations for Startups",
        markdown="# Understanding 409A Valuations\n\n## What Is a 409A Valuation?\n\n"
        "A 409A valuation is an independent appraisal of the fair market value of a "
        "private company's common stock [IRS, 2024]. Named after Section 409A of the IRC, "
        "this valuation is required whenever a company issues stock options.\n\n"
        "## Why Startups Need 409A Valuations\n\n"
        "93% of venture-backed startups obtain 409A valuations [Carta, 2024]. "
        "Failure to comply can result in a 20% additional tax penalty for employees.\n\n"
        "- Compliance with IRS regulations\n- Protection from tax penalties\n"
        "- Fair pricing for stock options\n- $2.1B in penalties avoided annually [EY, 2023]\n\n"
        "## The 409A Valuation Process\n\n"
        "The process typically involves:\n\n"
        "1. Selecting a qualified valuation firm\n"
        "2. Providing financial documents\n"
        "3. Analysis using accepted methodologies\n"
        "4. Delivery of the valuation report\n\n"
        "## Key Considerations\n\n"
        "Companies should get a new 409A valuation every 12 months or after a material event "
        "such as a funding round. Costs range from $5,000 to $50,000 depending on complexity.",
        word_count=190,
        facts_added=[
            {"citation": "IRS, 2024"},
            {"citation": "Carta, 2024"},
            {"citation": "EY, 2023"},
        ],
    )


@pytest.fixture
def sample_formatted() -> FormattedContent:
    return FormattedContent(
        brief_id="brief-001",
        title="Understanding 409A Valuations for Startups",
        markdown="# Understanding 409A Valuations\n\n## What Is a 409A Valuation?\n\n"
        "A **409A valuation** is an independent appraisal of the fair market value of a "
        "private company's common stock [IRS, 2024]. Named after Section 409A of the IRC, "
        "this valuation is required whenever a company issues stock options.\n\n"
        "## Why Startups Need 409A Valuations\n\n"
        "**93%** of venture-backed startups obtain 409A valuations [Carta, 2024]. "
        "Failure to comply can result in a 20% additional tax penalty for employees.\n\n"
        "- Compliance with IRS regulations\n- Protection from tax penalties\n"
        "- Fair pricing for stock options\n- **$2.1B** in penalties avoided annually [EY, 2023]\n\n"
        "## The 409A Valuation Process\n\n"
        "The process typically involves:\n\n"
        "1. Selecting a qualified valuation firm\n"
        "2. Providing financial documents\n"
        "3. Analysis using accepted methodologies\n"
        "4. Delivery of the valuation report\n\n"
        "## Key Considerations\n\n"
        "Companies should get a new 409A valuation every 12 months or after a material event.",
        word_count=1500,
        header_count=4,
        list_count=8,
        stat_count=3,
        citation_count=3,
    )


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class MockAnthropicResponse:
    """Mock for AsyncAnthropic.messages.create response."""

    def __init__(self, text: str, input_tokens: int = 100, output_tokens: int = 200):
        self.content = [MagicMock(text=text)]
        self.usage = MagicMock(input_tokens=input_tokens, output_tokens=output_tokens)


@pytest.fixture
def mock_anthropic_planner(sample_brief):
    """Mock AsyncAnthropic that returns a valid PlannerOutput JSON."""
    planner_output = PlannerOutput(
        briefs=[sample_brief],
        planning_metadata={"model": "test"},
    )
    response_text = json.dumps(planner_output.model_dump(mode="json"), default=str)

    mock_response = MockAnthropicResponse(response_text)

    with patch("core.content_engine.planner.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client
        yield mock_cls


@pytest.fixture
def mock_anthropic_outliner(sample_outline):
    """Mock AsyncAnthropic that returns a valid ContentOutline JSON."""
    response_text = json.dumps(sample_outline.model_dump(mode="json"), default=str)
    mock_response = MockAnthropicResponse(response_text)

    with patch("core.content_engine.workers.outliner.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client
        yield mock_cls


@pytest.fixture
def mock_anthropic_drafter(sample_draft):
    """Mock AsyncAnthropic that returns markdown draft."""
    mock_response = MockAnthropicResponse(sample_draft.markdown)

    with patch("core.content_engine.workers.drafter.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client
        yield mock_cls


@pytest.fixture
def mock_anthropic_formatter(sample_formatted):
    """Mock AsyncAnthropic that returns formatted markdown."""
    mock_response = MockAnthropicResponse(sample_formatted.markdown)

    with patch("core.content_engine.workers.formatter.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client
        yield mock_cls


@pytest.fixture
def mock_perplexity(sample_enriched):
    """Mock httpx client that returns enriched content from Perplexity."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": sample_enriched.markdown}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 200},
    }
    mock_response.raise_for_status = MagicMock()

    with patch("core.content_engine.workers.fact_enricher.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client
        yield mock_cls


@pytest.fixture
def mock_embeddings():
    """Mock async_embed_texts to return deterministic embeddings."""
    # Return simple unit vectors for testing
    async def _mock_embed(texts, **kwargs):
        import numpy as np
        return [np.random.default_rng(42 + i).random(3072).tolist() for i in range(len(texts))]

    with patch("core.content_engine.evaluator.semantic.async_embed_texts", side_effect=_mock_embed):
        yield
