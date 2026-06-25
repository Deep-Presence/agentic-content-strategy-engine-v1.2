"""Tests for the Outliner worker."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from core.content_engine.workers.outliner import generate_outline
from tests.content_engine.conftest import _make_llm_response


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


@pytest.mark.asyncio
async def test_generate_outline_uses_byok_when_workspace_present(sample_brief, sample_outline):
    response_text = json.dumps(sample_outline.model_dump(mode="json"), default=str)
    resp = _make_llm_response(response_text)

    with patch("core.content_engine.workers.outliner.llm_call_for_agent",
               new_callable=AsyncMock, return_value=resp) as mock_byok, \
         patch("core.content_engine.workers.outliner.llm_call",
               new_callable=AsyncMock) as mock_legacy:
        result = await generate_outline(
            brief=sample_brief,
            company_context_md="TestCo context.",
            company_slug="test-co",
            workspace_id="workspace-123",
        )

    assert result.brief_id == "brief-001"
    mock_legacy.assert_not_called()
    mock_byok.assert_awaited_once()
    kwargs = mock_byok.await_args.kwargs
    assert kwargs["workspace_id"] == "workspace-123"
    assert kwargs["agent_key"] == "content.worker.outliner"
    assert kwargs["metadata"]["agent_key"] == "content.worker.outliner"
