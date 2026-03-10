"""Tests for the Fact Enricher worker."""
from __future__ import annotations

import pytest

from core.content_engine.workers.fact_enricher import enrich_with_facts


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
