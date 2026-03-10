"""Tests for the Outliner worker."""
from __future__ import annotations

import pytest

from core.content_engine.workers.outliner import generate_outline


@pytest.mark.asyncio
async def test_generate_outline(sample_brief, mock_anthropic_outliner):
    """Outliner should produce a valid outline from a brief."""
    result = await generate_outline(
        brief=sample_brief,
        company_context_md="TestCo context.",
    )

    assert result.brief_id == "brief-001"
    assert len(result.sections) > 0
    assert result.total_target_words > 0
