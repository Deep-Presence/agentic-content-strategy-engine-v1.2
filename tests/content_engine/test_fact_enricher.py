"""Tests for the Fact Enricher worker."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from core.content_engine.workers.fact_enricher import enrich_with_facts
from tests.content_engine.conftest import _make_llm_response


@pytest.mark.asyncio
async def test_enrich_with_facts(sample_brief, sample_draft, mock_perplexity):
    """Fact enricher should add citations to a draft."""
    result = await enrich_with_facts(
        draft=sample_draft,
        brief=sample_brief,
        company_name="TestCo",
        domain="testco.com",
    )

    assert result.brief_id == "brief-001"
    assert len(result.markdown) > 0
    assert result.word_count > 0


@pytest.mark.asyncio
async def test_enrich_skips_without_api_key(sample_brief, sample_draft, monkeypatch):
    """Without PERPLEXITY_API_KEY, enricher should pass through unchanged."""
    monkeypatch.setattr(
        "core.content_engine.workers.fact_enricher.settings",
        type("S", (), {"perplexity_api_key": None, "content_engine_fact_enricher_model": "sonar-pro"})(),
    )

    result = await enrich_with_facts(
        draft=sample_draft,
        brief=sample_brief,
        company_name="TestCo",
        domain="testco.com",
    )

    assert result.markdown == sample_draft.markdown
    assert result.facts_added == []


@pytest.mark.asyncio
async def test_byok_workspace_does_not_require_platform_perplexity_key(
    sample_brief, sample_draft, monkeypatch
):
    """Workspace BYOK should use OpenRouter credential, not platform Perplexity key."""
    monkeypatch.setattr(
        "core.content_engine.workers.fact_enricher.settings",
        type("S", (), {"perplexity_api_key": None, "content_engine_fact_enricher_model": "sonar-pro"})(),
    )
    resp = _make_llm_response(sample_draft.markdown + "\n\n[Source, 2024]")

    with patch("core.content_engine.workers.fact_enricher.llm_call_for_agent",
               new_callable=AsyncMock, return_value=resp) as mock_byok, \
         patch("core.content_engine.workers.fact_enricher.llm_call",
               new_callable=AsyncMock) as mock_legacy:
        result = await enrich_with_facts(
            draft=sample_draft,
            brief=sample_brief,
            company_name="TestCo",
            domain="testco.com",
            company_slug="test-co",
            workspace_id="workspace-123",
        )

    assert result.word_count > 0
    mock_legacy.assert_not_called()
    mock_byok.assert_awaited_once()
    kwargs = mock_byok.await_args.kwargs
    assert kwargs["workspace_id"] == "workspace-123"
    assert kwargs["agent_key"] == "content.worker.fact_enricher"
