"""Tests for the worker dispatcher."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from core.content_engine.workers.dispatcher import dispatch_workers
from core.models.content_generation import (
    ContentBrief,
    ContentGenerationInput,
    FormattedContent,
    TargetQuery,
)


@pytest.mark.asyncio
async def test_dispatch_workers_single_brief(tmp_path):
    """Dispatcher should process a single brief through the full chain."""
    brief = ContentBrief(
        brief_id="brief-001",
        title="Test Article",
        target_queries=[TargetQuery(query_text="test query", cluster_name="c1")],
    )
    input_data = ContentGenerationInput(
        company_name="TestCo",
        domain="testco.com",
        max_concurrent_workers=1,
    )

    mock_formatted = FormattedContent(
        brief_id="brief-001",
        title="Test Article",
        markdown="# Test\n\nContent here [Source, 2024].",
        word_count=1500,
        header_count=3,
        list_count=2,
        stat_count=1,
        citation_count=1,
    )

    from core.models.content_generation import ContentDraft, ContentOutline, EnrichedDraft, OutlineSection

    mock_outline = ContentOutline(
        brief_id="brief-001",
        title="Test Article",
        sections=[OutlineSection(heading="Intro")],
    )
    mock_draft = ContentDraft(brief_id="brief-001", title="Test Article", markdown="# Test")
    mock_enriched = EnrichedDraft(brief_id="brief-001", title="Test Article", markdown="# Test")

    with (
        patch(
            "core.content_engine.workers.dispatcher.generate_outline",
            new_callable=AsyncMock,
            return_value=mock_outline,
        ),
        patch(
            "core.content_engine.workers.dispatcher.generate_draft",
            new_callable=AsyncMock,
            return_value=mock_draft,
        ),
        patch(
            "core.content_engine.workers.dispatcher.enrich_with_facts",
            new_callable=AsyncMock,
            return_value=mock_enriched,
        ),
        patch(
            "core.content_engine.workers.dispatcher.format_content",
            new_callable=AsyncMock,
            return_value=mock_formatted,
        ),
    ):
        results = await dispatch_workers(
            briefs=[brief],
            input_data=input_data,
            style_guide_md="",
            company_context_md="",
            max_concurrent=1,
            session_id="test",
            artifact_dir=tmp_path,
        )

    assert len(results) == 1
    assert results[0].brief_id == "brief-001"


@pytest.mark.asyncio
async def test_dispatch_workers_handles_failure(tmp_path):
    """Dispatcher should handle worker failures without cancelling the batch."""
    briefs = [
        ContentBrief(brief_id="brief-001", title="Good Article"),
        ContentBrief(brief_id="brief-002", title="Bad Article"),
    ]
    input_data = ContentGenerationInput(
        company_name="TestCo",
        domain="testco.com",
        max_concurrent_workers=2,
    )

    call_count = 0

    async def _mock_outline(brief, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if brief.brief_id == "brief-002":
            raise RuntimeError("Simulated failure")
        from core.models.content_generation import ContentOutline
        return ContentOutline(brief_id=brief.brief_id, title=brief.title)

    mock_formatted = FormattedContent(
        brief_id="brief-001",
        title="Good Article",
        markdown="# Good\n\nContent.",
        word_count=1500,
    )

    from core.models.content_generation import ContentDraft, EnrichedDraft

    mock_draft = ContentDraft(brief_id="brief-001", title="Good Article", markdown="# Good")
    mock_enriched = EnrichedDraft(brief_id="brief-001", title="Good Article", markdown="# Good")

    with (
        patch(
            "core.content_engine.workers.dispatcher.generate_outline",
            side_effect=_mock_outline,
        ),
        patch(
            "core.content_engine.workers.dispatcher.generate_draft",
            new_callable=AsyncMock,
            return_value=mock_draft,
        ),
        patch(
            "core.content_engine.workers.dispatcher.enrich_with_facts",
            new_callable=AsyncMock,
            return_value=mock_enriched,
        ),
        patch(
            "core.content_engine.workers.dispatcher.format_content",
            new_callable=AsyncMock,
            return_value=mock_formatted,
        ),
    ):
        results = await dispatch_workers(
            briefs=briefs,
            input_data=input_data,
            style_guide_md="",
            company_context_md="",
            max_concurrent=2,
            session_id="test",
            artifact_dir=tmp_path,
        )

    # Should have 1 success (brief-001) — brief-002 failed but didn't crash the batch
    assert len(results) == 1
    assert results[0].brief_id == "brief-001"
