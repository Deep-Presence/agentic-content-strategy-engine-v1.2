"""Tests for the Drafter worker."""
from __future__ import annotations

import pytest

from core.content_engine.workers.drafter import generate_draft


@pytest.mark.asyncio
async def test_generate_draft(sample_brief, sample_outline, mock_anthropic_drafter):
    """Drafter should produce markdown content from an outline."""
    result = await generate_draft(
        outline=sample_outline,
        brief=sample_brief,
        style_guide_md="Write professionally.",
        company_context_md="TestCo context.",
    )

    assert result.brief_id == "brief-001"
    assert len(result.markdown) > 0
    assert result.word_count > 0
