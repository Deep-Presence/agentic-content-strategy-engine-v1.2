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
    """Mock for AsyncAnthropic.messages.create response (v1.0 planner only)."""

    def __init__(self, text: str, input_tokens: int = 100, output_tokens: int = 200):
        self.content = [MagicMock(text=text)]
        self.usage = MagicMock(input_tokens=input_tokens, output_tokens=output_tokens)


def _make_llm_response(text: str, input_tokens: int = 100, output_tokens: int = 200):
    """Create an LLMResponse for mocking llm_call()."""
    from core.models.content_generation_v13 import LLMResponse

    return LLMResponse(
        content=text,
        model="test-model",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        finish_reason="stop",
    )


@pytest.fixture
def mock_anthropic_planner(sample_brief):
    """Mock AsyncAnthropic that returns a valid PlannerOutput JSON (v1.0 planner)."""
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
    """Mock llm_call in outliner that returns a valid ContentOutline JSON."""
    response_text = json.dumps(sample_outline.model_dump(mode="json"), default=str)
    mock_response = _make_llm_response(response_text)

    with patch("core.content_engine.workers.outliner.llm_call", new_callable=AsyncMock, return_value=mock_response):
        yield


@pytest.fixture
def mock_anthropic_drafter(sample_draft):
    """Mock llm_call in drafter that returns markdown draft."""
    mock_response = _make_llm_response(sample_draft.markdown)

    with patch("core.content_engine.workers.drafter.llm_call", new_callable=AsyncMock, return_value=mock_response):
        yield


@pytest.fixture
def mock_anthropic_formatter(sample_formatted):
    """Mock llm_call in formatter that returns formatted markdown."""
    mock_response = _make_llm_response(sample_formatted.markdown)

    with patch("core.content_engine.workers.formatter.llm_call", new_callable=AsyncMock, return_value=mock_response):
        yield


@pytest.fixture
def mock_perplexity(sample_enriched):
    """Mock llm_call in fact_enricher that returns enriched content."""
    mock_response = _make_llm_response(sample_enriched.markdown)

    with patch("core.content_engine.workers.fact_enricher.llm_call", new_callable=AsyncMock, return_value=mock_response):
        yield


@pytest.fixture
def mock_embeddings():
    """Mock async_embed_texts to return deterministic embeddings."""
    # Return simple unit vectors for testing
    async def _mock_embed(texts, **kwargs):
        import numpy as np
        return [np.random.default_rng(42 + i).random(1536).tolist() for i in range(len(texts))]

    with patch("core.content_engine.evaluator.semantic.async_embed_texts", side_effect=_mock_embed):
        yield


# ---------------------------------------------------------------------------
# v1.3 fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_analysis_json() -> Dict[str, Any]:
    """Minimal analysis.json shape with 3 gaps, 2 clusters, 1 cluster_spec."""
    return {
        "gaps": [
            {
                "query_id": "q-001",
                "query_text": "what is a 409A valuation",
                "cluster_name": "equity",
                "gap": 0.35,
                "best_company_similarity": 0.55,
                "avg_citation_similarity": 0.90,
                "interpretation": "significant_gap",
                "best_company_unit_text": "We offer cap table management.",
                "top_cited_exemplars": [
                    {
                        "url": "https://example.com/409a",
                        "similarity": 0.92,
                        "authority_type": "industry_report",
                        "snippet": "A 409A valuation is an independent appraisal.",
                        "structural_signals": {"word_count": 2200, "header_count": 7},
                    }
                ],
                "content_brief": {
                    "target_format": "long_blog",
                    "target_word_count": 1800,
                },
            },
            {
                "query_id": "q-002",
                "query_text": "cap table management tools",
                "cluster_name": "equity",
                "gap": 0.10,
                "best_company_similarity": 0.80,
                "avg_citation_similarity": 0.90,
                "interpretation": "roughly_equal",
                "best_company_unit_text": "",
                "top_cited_exemplars": [],
                "content_brief": None,
            },
            {
                "query_id": "q-003",
                "query_text": "startup fundraising best practices",
                "cluster_name": "fundraising",
                "gap": 0.42,
                "best_company_similarity": 0.45,
                "avg_citation_similarity": 0.87,
                "interpretation": "significant_gap",
                "best_company_unit_text": "",
                "top_cited_exemplars": [
                    {
                        "url": "https://vc.example.com/guide",
                        "similarity": 0.88,
                        "authority_type": "company_blog",
                        "snippet": "Fundraising requires a clear pitch deck.",
                        "structural_signals": {"word_count": 3000, "header_count": 10},
                    },
                    {
                        "url": "https://startup.example.com/tips",
                        "similarity": 0.85,
                        "authority_type": "company_blog",
                        "snippet": "",
                        "structural_signals": {},
                    },
                ],
                "content_brief": {
                    "target_format": "how_to",
                    "target_word_count": 2200,
                },
            },
        ],
        "cluster_specs": [
            {
                "cluster_name": "equity",
                "dominant_content_type": "long_blog",
                "dominant_authority_type": "industry_report",
            },
            {
                "cluster_name": "fundraising",
                "dominant_content_type": "how_to",
                "dominant_authority_type": "company_blog",
            },
        ],
    }


@pytest.fixture
def sample_scorecard():
    """PlannerScorecard with 3 queries, 2 clusters."""
    from core.models.content_generation_v13 import (
        ClusterSummary,
        PlannerScorecard,
        QueryScorecard,
    )

    return PlannerScorecard(
        queries=[
            QueryScorecard(
                query_id="q-001", query_text="what is a 409A valuation",
                cluster_name="equity", gap=0.35,
                best_company_similarity=0.55, avg_citation_similarity=0.90,
                interpretation="significant_gap", exemplar_count=1, has_brief=True,
            ),
            QueryScorecard(
                query_id="q-002", query_text="cap table management tools",
                cluster_name="equity", gap=0.10,
                best_company_similarity=0.80, avg_citation_similarity=0.90,
                interpretation="roughly_equal", exemplar_count=0, has_brief=False,
            ),
            QueryScorecard(
                query_id="q-003", query_text="startup fundraising best practices",
                cluster_name="fundraising", gap=0.42,
                best_company_similarity=0.45, avg_citation_similarity=0.87,
                interpretation="significant_gap", exemplar_count=2, has_brief=True,
            ),
        ],
        clusters=[
            ClusterSummary(
                cluster_name="equity", query_count=2, avg_gap=0.225,
                max_gap=0.35, significant_gap_count=1,
                dominant_content_type="long_blog",
                dominant_authority_type="industry_report",
            ),
            ClusterSummary(
                cluster_name="fundraising", query_count=1, avg_gap=0.42,
                max_gap=0.42, significant_gap_count=1,
                dominant_content_type="how_to",
                dominant_authority_type="company_blog",
            ),
        ],
        company_summary="TestCo provides equity management for startups.",
        product_focus=None,
        total_queries=3,
        total_clusters=2,
    )


@pytest.fixture
def sample_topic_selections():
    """StrategicPlannerOutput with 2 selected topics."""
    from core.models.content_generation_v13 import (
        StrategicPlannerOutput,
        TopicSelection,
    )

    return StrategicPlannerOutput(
        selections=[
            TopicSelection(
                rank=1, query_ids=["q-001"],
                query_texts=["what is a 409A valuation"],
                cluster_name="equity",
                rationale="High gap, strong exemplars",
                estimated_impact="high",
            ),
            TopicSelection(
                rank=2, query_ids=["q-003"],
                query_texts=["startup fundraising best practices"],
                cluster_name="fundraising",
                rationale="Critical gap in fundraising content",
                estimated_impact="medium",
            ),
        ],
        selection_metadata={"model": "test-model", "total_tokens": 300},
    )


@pytest.fixture
def sample_blueprint(sample_brief):
    """ContentBlueprint extending sample_brief."""
    from core.models.content_generation_v13 import BlueprintSection, ContentBlueprint

    return ContentBlueprint(
        brief_id=sample_brief.brief_id,
        title=sample_brief.title,
        target_queries=sample_brief.target_queries,
        target_cluster=sample_brief.target_cluster,
        content_format=sample_brief.content_format,
        funnel_stage=sample_brief.funnel_stage,
        word_count_range=sample_brief.word_count_range,
        structural_targets=sample_brief.structural_targets,
        key_topics=sample_brief.key_topics,
        key_angles=sample_brief.key_angles,
        exemplar_summaries=sample_brief.exemplar_summaries,
        exemplar_themes=sample_brief.exemplar_themes,
        sections=[
            BlueprintSection(
                heading="What Is a 409A Valuation?", level=2,
                key_points=["Definition", "Legal basis"],
                target_word_count=300,
                structural_elements=["definition", "statistics"],
                must_include=["IRS Section 409A reference"],
            ),
            BlueprintSection(
                heading="Why Startups Need 409A Valuations", level=2,
                key_points=["Compliance", "Tax implications"],
                target_word_count=400,
                structural_elements=["bullet_list"],
                must_include=["Tax penalty risk"],
            ),
        ],
        territory_queries=["409A valuation process", "equity comp guide"],
        reading_hierarchy={"H2": 4, "H3": 2},
        must_hit_checklist=["Define 409A", "Explain tax implications"],
    )


@pytest.fixture
def sample_worker_context():
    """WorkerQueryContext with full exemplar data."""
    from core.models.content_generation_v13 import WorkerQueryContext

    return WorkerQueryContext(
        query_gap={
            "query_id": "q-001",
            "query_text": "what is a 409A valuation",
            "cluster_name": "equity",
            "gap": 0.35,
            "best_company_similarity": 0.55,
            "avg_citation_similarity": 0.90,
            "interpretation": "significant_gap",
        },
        cluster_spec={
            "cluster_name": "equity",
            "dominant_content_type": "long_blog",
            "dominant_authority_type": "industry_report",
        },
        exemplars=[
            {
                "url": "https://example.com/409a",
                "similarity": 0.92,
                "authority_type": "industry_report",
                "snippet": "A 409A valuation is an independent appraisal.",
                "structural_signals": {"word_count": 2200, "header_count": 7},
            }
        ],
        gap_content_brief={
            "target_format": "long_blog",
            "target_word_count": 1800,
        },
        company_best_text="We offer cap table management.",
    )
