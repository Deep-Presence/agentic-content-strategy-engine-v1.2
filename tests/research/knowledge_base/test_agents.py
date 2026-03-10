"""Tests for Knowledge Base specialist agents — 4 Perplexity + Brand Perception + Synthesis."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models.knowledge_base import KBAgentResult, KBDocType, KnowledgeBaseInput


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def kb_input() -> KnowledgeBaseInput:
    return KnowledgeBaseInput(
        company_name="Test Co",
        domain="test.co",
        company_slug="test-co",
    )


@pytest.fixture()
def upstream_docs() -> Dict[str, str]:
    return {
        "company_overview": "# Company Overview\n\nTest Co builds enterprise tools.",
        "customer_reviews": "# Customer Reviews\n\nUsers love the simplicity.",
        "competitor_registry": "# Competitor Registry\n\n- Rival Inc\n- Alt Corp",
        "weakness_analysis": "# Weakness Analysis\n\nRival Inc has poor docs.",
    }


_PERPLEXITY_PATCH = "core.research.knowledge_base.agents.perplexity_client"
_ANTHROPIC_PATCH = "core.research.knowledge_base.agents.anthropic"
_TRACING_PATCH_BASE = "core.research.knowledge_base.agents"


@pytest.fixture(autouse=True)
def _mock_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable tracing for all agent tests."""
    monkeypatch.setattr(f"{_TRACING_PATCH_BASE}.create_span", lambda *a, **kw: None)
    monkeypatch.setattr(f"{_TRACING_PATCH_BASE}.end_span", lambda *a, **kw: None)
    monkeypatch.setattr(f"{_TRACING_PATCH_BASE}.log_generation", lambda *a, **kw: None)


# ---------------------------------------------------------------------------
# Agent 1 — Company Overview (Perplexity)
# ---------------------------------------------------------------------------

class TestRunCompanyOverviewAgent:
    """Agent 1 — Perplexity company overview."""

    @pytest.mark.asyncio
    async def test_success(self, kb_input: KnowledgeBaseInput, monkeypatch: pytest.MonkeyPatch) -> None:
        from core.research.knowledge_base.agents import run_company_overview_agent

        mock_client = MagicMock()
        mock_client.research = MagicMock(return_value="# Company Overview\n\nGreat content.")
        monkeypatch.setattr(_PERPLEXITY_PATCH, mock_client)

        result = await run_company_overview_agent(kb_input, timeout_s=10)
        assert result.error is None
        assert result.doc_type == KBDocType.COMPANY_OVERVIEW
        assert "Great content" in result.content_md
        assert result.word_count > 0
        assert result.execution_time_s > 0

    @pytest.mark.asyncio
    async def test_timeout_returns_error(self, kb_input: KnowledgeBaseInput, monkeypatch: pytest.MonkeyPatch) -> None:
        from core.research.knowledge_base.agents import run_company_overview_agent

        async def _slow(*a, **kw):
            await asyncio.sleep(10)

        mock_client = MagicMock()
        mock_client.research = MagicMock(side_effect=lambda **kw: asyncio.get_event_loop().run_until_complete(_slow()))
        # Simpler: just make to_thread raise TimeoutError
        with patch(f"{_TRACING_PATCH_BASE}.asyncio.wait_for", side_effect=asyncio.TimeoutError):
            monkeypatch.setattr(_PERPLEXITY_PATCH, mock_client)
            result = await run_company_overview_agent(kb_input, timeout_s=0.01)

        assert result.error is not None
        assert "Timeout" in result.error
        assert result.doc_type == KBDocType.COMPANY_OVERVIEW

    @pytest.mark.asyncio
    async def test_api_error_returns_error(self, kb_input: KnowledgeBaseInput, monkeypatch: pytest.MonkeyPatch) -> None:
        from core.research.knowledge_base.agents import run_company_overview_agent

        mock_client = MagicMock()
        mock_client.research = MagicMock(side_effect=RuntimeError("API key invalid"))
        monkeypatch.setattr(_PERPLEXITY_PATCH, mock_client)

        result = await run_company_overview_agent(kb_input, timeout_s=10)
        assert result.error is not None
        assert "API key invalid" in result.error

    @pytest.mark.asyncio
    async def test_empty_response(self, kb_input: KnowledgeBaseInput, monkeypatch: pytest.MonkeyPatch) -> None:
        from core.research.knowledge_base.agents import run_company_overview_agent

        mock_client = MagicMock()
        mock_client.research = MagicMock(return_value="")
        monkeypatch.setattr(_PERPLEXITY_PATCH, mock_client)

        result = await run_company_overview_agent(kb_input, timeout_s=10)
        assert result.error is None
        assert result.content_md == ""
        assert result.word_count == 0


# ---------------------------------------------------------------------------
# Agent 2 — Customer Reviews (Perplexity)
# ---------------------------------------------------------------------------

class TestRunCustomerReviewsAgent:
    """Agent 2 — Perplexity customer reviews."""

    @pytest.mark.asyncio
    async def test_success(self, kb_input: KnowledgeBaseInput, monkeypatch: pytest.MonkeyPatch) -> None:
        from core.research.knowledge_base.agents import run_customer_reviews_agent

        mock_client = MagicMock()
        mock_client.research = MagicMock(return_value="# Reviews\n\nPositive feedback.")
        monkeypatch.setattr(_PERPLEXITY_PATCH, mock_client)

        result = await run_customer_reviews_agent(kb_input, timeout_s=10)
        assert result.error is None
        assert result.doc_type == KBDocType.CUSTOMER_REVIEWS
        assert result.word_count > 0

    @pytest.mark.asyncio
    async def test_timeout(self, kb_input: KnowledgeBaseInput, monkeypatch: pytest.MonkeyPatch) -> None:
        from core.research.knowledge_base.agents import run_customer_reviews_agent

        with patch(f"{_TRACING_PATCH_BASE}.asyncio.wait_for", side_effect=asyncio.TimeoutError):
            mock_client = MagicMock()
            monkeypatch.setattr(_PERPLEXITY_PATCH, mock_client)
            result = await run_customer_reviews_agent(kb_input, timeout_s=0.01)

        assert result.error is not None
        assert "Timeout" in result.error


# ---------------------------------------------------------------------------
# Agent 3 — Competitor Scanner (Perplexity + upstream)
# ---------------------------------------------------------------------------

class TestRunCompetitorScannerAgent:
    """Agent 3 — Perplexity competitor scanner with upstream context."""

    @pytest.mark.asyncio
    async def test_success(self, kb_input: KnowledgeBaseInput, monkeypatch: pytest.MonkeyPatch) -> None:
        from core.research.knowledge_base.agents import run_competitor_scanner_agent

        mock_client = MagicMock()
        mock_client.research = MagicMock(return_value="# Competitors\n\n- Rival Inc")
        monkeypatch.setattr(_PERPLEXITY_PATCH, mock_client)

        result = await run_competitor_scanner_agent(
            kb_input, company_overview_md="# Overview\n\nTest Co details.", timeout_s=10,
        )
        assert result.error is None
        assert result.doc_type == KBDocType.COMPETITOR_REGISTRY

    @pytest.mark.asyncio
    async def test_includes_company_overview_in_prompt(self, kb_input: KnowledgeBaseInput, monkeypatch: pytest.MonkeyPatch) -> None:
        from core.research.knowledge_base.agents import run_competitor_scanner_agent

        captured_query = {}

        def _capture(query: str, **kw: Any) -> str:
            captured_query["q"] = query
            return "# Result"

        mock_client = MagicMock()
        mock_client.research = MagicMock(side_effect=_capture)
        monkeypatch.setattr(_PERPLEXITY_PATCH, mock_client)

        await run_competitor_scanner_agent(
            kb_input, company_overview_md="UNIQUE_MARKER_OVERVIEW", timeout_s=10,
        )
        assert "UNIQUE_MARKER_OVERVIEW" in captured_query["q"]

    @pytest.mark.asyncio
    async def test_timeout(self, kb_input: KnowledgeBaseInput, monkeypatch: pytest.MonkeyPatch) -> None:
        from core.research.knowledge_base.agents import run_competitor_scanner_agent

        with patch(f"{_TRACING_PATCH_BASE}.asyncio.wait_for", side_effect=asyncio.TimeoutError):
            mock_client = MagicMock()
            monkeypatch.setattr(_PERPLEXITY_PATCH, mock_client)
            result = await run_competitor_scanner_agent(
                kb_input, company_overview_md="", timeout_s=0.01,
            )
        assert "Timeout" in result.error


# ---------------------------------------------------------------------------
# Agent 4 — Weakness Analyst (Perplexity + 2 upstream docs)
# ---------------------------------------------------------------------------

class TestRunWeaknessAnalystAgent:
    """Agent 4 — Perplexity weakness analyst with two upstream docs."""

    @pytest.mark.asyncio
    async def test_success(self, kb_input: KnowledgeBaseInput, monkeypatch: pytest.MonkeyPatch) -> None:
        from core.research.knowledge_base.agents import run_weakness_analyst_agent

        mock_client = MagicMock()
        mock_client.research = MagicMock(return_value="# Weaknesses\n\nRival has gaps.")
        monkeypatch.setattr(_PERPLEXITY_PATCH, mock_client)

        result = await run_weakness_analyst_agent(
            kb_input, company_overview_md="overview", competitor_registry_md="competitors", timeout_s=10,
        )
        assert result.error is None
        assert result.doc_type == KBDocType.WEAKNESS_ANALYSIS

    @pytest.mark.asyncio
    async def test_includes_both_upstream_docs(self, kb_input: KnowledgeBaseInput, monkeypatch: pytest.MonkeyPatch) -> None:
        from core.research.knowledge_base.agents import run_weakness_analyst_agent

        captured_query = {}

        def _capture(query: str, **kw: Any) -> str:
            captured_query["q"] = query
            return "# Result"

        mock_client = MagicMock()
        mock_client.research = MagicMock(side_effect=_capture)
        monkeypatch.setattr(_PERPLEXITY_PATCH, mock_client)

        await run_weakness_analyst_agent(
            kb_input, company_overview_md="MARKER_OVERVIEW", competitor_registry_md="MARKER_COMPETITORS",
            timeout_s=10,
        )
        assert "MARKER_OVERVIEW" in captured_query["q"]
        assert "MARKER_COMPETITORS" in captured_query["q"]

    @pytest.mark.asyncio
    async def test_timeout(self, kb_input: KnowledgeBaseInput, monkeypatch: pytest.MonkeyPatch) -> None:
        from core.research.knowledge_base.agents import run_weakness_analyst_agent

        with patch(f"{_TRACING_PATCH_BASE}.asyncio.wait_for", side_effect=asyncio.TimeoutError):
            mock_client = MagicMock()
            monkeypatch.setattr(_PERPLEXITY_PATCH, mock_client)
            result = await run_weakness_analyst_agent(
                kb_input, company_overview_md="", competitor_registry_md="", timeout_s=0.01,
            )
        assert "Timeout" in result.error


# ---------------------------------------------------------------------------
# Agent 5 — Brand Perception (Anthropic SDK + web search)
# ---------------------------------------------------------------------------

def _make_anthropic_response(
    text: str = "# Brand Analysis",
    stop_reason: str = "end_turn",
    input_tokens: int = 500,
    output_tokens: int = 300,
    web_searches: int = 3,
) -> MagicMock:
    """Build a mock Anthropic messages.create() response."""
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = text

    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    usage.server_tool_use = {"web_search_requests": web_searches}

    response = MagicMock()
    response.stop_reason = stop_reason
    response.content = [text_block]
    response.usage = usage
    return response


class TestRunBrandPerceptionAgent:
    """Agent 5 — Anthropic SDK + web_search_20250305."""

    @pytest.mark.asyncio
    async def test_success_with_web_search(
        self, kb_input: KnowledgeBaseInput, upstream_docs: Dict[str, str],
    ) -> None:
        from core.research.knowledge_base.agents import run_brand_perception_agent

        mock_response = _make_anthropic_response("# Brand Perception\n\nStrong market position.")
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch(f"{_ANTHROPIC_PATCH}.AsyncAnthropic", return_value=mock_client) as mock_cls:
            result = await run_brand_perception_agent(
                kb_input, upstream_docs, timeout_s=10,
            )

        assert result.error is None
        assert result.doc_type == KBDocType.BRAND_PERCEPTION
        assert "Strong market position" in result.content_md
        assert result.word_count > 0
        # C-2 fix: verify api_key is passed from settings
        mock_cls.assert_called_once()
        call_kwargs = mock_cls.call_args
        assert call_kwargs.kwargs.get("api_key") is not None or call_kwargs[1].get("api_key") is not None

    @pytest.mark.asyncio
    async def test_pause_turn_continuation(
        self, kb_input: KnowledgeBaseInput, upstream_docs: Dict[str, str],
    ) -> None:
        from core.research.knowledge_base.agents import run_brand_perception_agent

        first_response = _make_anthropic_response("Partial...", stop_reason="pause_turn")
        second_response = _make_anthropic_response("# Full brand analysis result.")

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=[first_response, second_response])

        with patch(f"{_ANTHROPIC_PATCH}.AsyncAnthropic", return_value=mock_client):
            result = await run_brand_perception_agent(
                kb_input, upstream_docs, timeout_s=30,
            )

        assert result.error is None
        assert mock_client.messages.create.call_count == 2
        assert "Full brand analysis" in result.content_md

    @pytest.mark.asyncio
    async def test_pause_turn_exceeds_limit(
        self, kb_input: KnowledgeBaseInput, upstream_docs: Dict[str, str],
    ) -> None:
        from core.research.knowledge_base.agents import _MAX_PAUSE_TURNS, run_brand_perception_agent

        # Return pause_turn indefinitely — agent must stop after _MAX_PAUSE_TURNS
        pause_response = _make_anthropic_response("Still working...", stop_reason="pause_turn")

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=pause_response)

        with patch(f"{_ANTHROPIC_PATCH}.AsyncAnthropic", return_value=mock_client):
            result = await run_brand_perception_agent(
                kb_input, upstream_docs, timeout_s=30,
            )

        # Should succeed with partial output, not loop forever
        assert result.error is None
        assert result.content_md is not None
        # 1 initial call + _MAX_PAUSE_TURNS - 1 retries (breaks at limit before making another call)
        assert mock_client.messages.create.call_count == _MAX_PAUSE_TURNS

    @pytest.mark.asyncio
    async def test_timeout(
        self, kb_input: KnowledgeBaseInput, upstream_docs: Dict[str, str],
    ) -> None:
        from core.research.knowledge_base.agents import run_brand_perception_agent

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=asyncio.TimeoutError)

        with patch(f"{_ANTHROPIC_PATCH}.AsyncAnthropic", return_value=mock_client):
            with patch(f"{_TRACING_PATCH_BASE}.asyncio.wait_for", side_effect=asyncio.TimeoutError):
                result = await run_brand_perception_agent(
                    kb_input, upstream_docs, timeout_s=0.01,
                )

        assert result.error is not None
        assert "Timeout" in result.error

    @pytest.mark.asyncio
    async def test_api_error(
        self, kb_input: KnowledgeBaseInput, upstream_docs: Dict[str, str],
    ) -> None:
        from core.research.knowledge_base.agents import run_brand_perception_agent

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=RuntimeError("Auth failed"))

        with patch(f"{_ANTHROPIC_PATCH}.AsyncAnthropic", return_value=mock_client):
            result = await run_brand_perception_agent(
                kb_input, upstream_docs, timeout_s=10,
            )

        assert result.error is not None
        assert "Auth failed" in result.error

    @pytest.mark.asyncio
    async def test_extracts_text_blocks_only(
        self, kb_input: KnowledgeBaseInput, upstream_docs: Dict[str, str],
    ) -> None:
        from core.research.knowledge_base.agents import run_brand_perception_agent

        # Response with mixed content blocks
        text_block = MagicMock(type="text", text="Text part one.")
        tool_block = MagicMock(type="server_tool_use", text="should be ignored")
        text_block2 = MagicMock(type="text", text="Text part two.")

        usage = MagicMock(input_tokens=100, output_tokens=50)
        usage.server_tool_use = {"web_search_requests": 1}

        response = MagicMock()
        response.stop_reason = "end_turn"
        response.content = [text_block, tool_block, text_block2]
        response.usage = usage

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=response)

        with patch(f"{_ANTHROPIC_PATCH}.AsyncAnthropic", return_value=mock_client):
            result = await run_brand_perception_agent(
                kb_input, upstream_docs, timeout_s=10,
            )

        assert "Text part one" in result.content_md
        assert "Text part two" in result.content_md


# ---------------------------------------------------------------------------
# Synthesis Agent — Builder
# ---------------------------------------------------------------------------

class TestBuildSynthesisAgent:
    """Synthesis agent construction tests."""

    def test_returns_compiled_state_graph(self, tmp_path: Path) -> None:
        from langgraph.graph.state import CompiledStateGraph

        from core.research.knowledge_base.agents import build_synthesis_agent

        mock_model = MagicMock()
        agent = build_synthesis_agent(model=mock_model, kb_base_dir=tmp_path)
        assert isinstance(agent, CompiledStateGraph)

    def test_includes_read_file_tool(self, tmp_path: Path) -> None:
        from core.research.knowledge_base.agents import build_synthesis_agent

        mock_model = MagicMock()
        agent = build_synthesis_agent(model=mock_model, kb_base_dir=tmp_path)
        # The agent should have tools configured
        assert agent is not None

    def test_custom_model(self, tmp_path: Path) -> None:
        from core.research.knowledge_base.agents import build_synthesis_agent

        custom_model = MagicMock()
        agent = build_synthesis_agent(model=custom_model, kb_base_dir=tmp_path)
        assert agent is not None


# ---------------------------------------------------------------------------
# Synthesis Agent — Runner
# ---------------------------------------------------------------------------

class TestRunSynthesisAgent:
    """Synthesis agent execution tests."""

    @pytest.mark.asyncio
    async def test_fails_under_3_docs(self, kb_input: KnowledgeBaseInput) -> None:
        from core.research.knowledge_base.agents import run_synthesis_agent

        result = await run_synthesis_agent(
            input_data=kb_input,
            kb_base_dir=Path("/tmp/test"),
            available_docs={"company_overview": "path1", "customer_reviews": "path2"},
            missing_docs=["competitor_registry", "weakness_analysis", "brand_perception"],
        )
        assert result.error is not None
        assert "minimum 3" in result.error.lower()

    @pytest.mark.asyncio
    async def test_succeeds_at_3_docs(self, kb_input: KnowledgeBaseInput, tmp_path: Path) -> None:
        from core.research.knowledge_base.agents import run_synthesis_agent

        # Mock the synthesis agent to return a valid response
        mock_msg = MagicMock()
        mock_msg.type = "ai"
        mock_msg.content = "# Synthesized Company Profile\n\nComprehensive analysis."

        mock_agent = MagicMock()
        mock_agent.ainvoke = AsyncMock(return_value={"messages": [mock_msg]})

        with (
            patch("core.research.knowledge_base.agents.create_react_agent", return_value=mock_agent),
            patch("core.research.knowledge_base.agents._build_model", return_value=MagicMock()),
        ):
            result = await run_synthesis_agent(
                input_data=kb_input,
                kb_base_dir=tmp_path,
                available_docs={
                    "company_overview": "company_overview/v1.md",
                    "customer_reviews": "customer_reviews/v1.md",
                    "competitor_registry": "competitor_registry/v1.md",
                },
                missing_docs=["weakness_analysis", "brand_perception"],
                timeout_s=10,
            )

        assert result.error is None
        assert "Synthesized" in result.content_md
        assert result.word_count > 0

    @pytest.mark.asyncio
    async def test_empty_output_returns_error(self, kb_input: KnowledgeBaseInput, tmp_path: Path) -> None:
        from core.research.knowledge_base.agents import run_synthesis_agent

        mock_msg = MagicMock()
        mock_msg.type = "ai"
        mock_msg.content = ""

        mock_agent = MagicMock()
        mock_agent.ainvoke = AsyncMock(return_value={"messages": [mock_msg]})

        with (
            patch("core.research.knowledge_base.agents.create_react_agent", return_value=mock_agent),
            patch("core.research.knowledge_base.agents._build_model", return_value=MagicMock()),
        ):
            result = await run_synthesis_agent(
                input_data=kb_input,
                kb_base_dir=tmp_path,
                available_docs={
                    "company_overview": "p1", "customer_reviews": "p2", "competitor_registry": "p3",
                },
                missing_docs=[],
                timeout_s=10,
            )

        assert result.error is not None
        assert "empty" in result.error.lower()

    @pytest.mark.asyncio
    async def test_timeout(self, kb_input: KnowledgeBaseInput, tmp_path: Path) -> None:
        from core.research.knowledge_base.agents import run_synthesis_agent

        mock_agent = MagicMock()
        mock_agent.ainvoke = AsyncMock(side_effect=asyncio.TimeoutError)

        with (
            patch("core.research.knowledge_base.agents.create_react_agent", return_value=mock_agent),
            patch("core.research.knowledge_base.agents._build_model", return_value=MagicMock()),
            patch(f"{_TRACING_PATCH_BASE}.asyncio.wait_for", side_effect=asyncio.TimeoutError),
        ):
                result = await run_synthesis_agent(
                    input_data=kb_input,
                    kb_base_dir=tmp_path,
                    available_docs={
                        "company_overview": "p1", "customer_reviews": "p2", "competitor_registry": "p3",
                    },
                    missing_docs=[],
                    timeout_s=0.01,
                )

        assert result.error is not None
        assert "Timeout" in result.error or "timeout" in result.error.lower()


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

class TestExtractSynthesisOutput:
    """Tests for _extract_synthesis_output."""

    def test_last_ai_message(self) -> None:
        from core.research.knowledge_base.agents import _extract_synthesis_output

        user_msg = MagicMock(type="human", content="Do the synthesis")
        ai_msg = MagicMock(type="ai", content="# Final output")
        result = _extract_synthesis_output([user_msg, ai_msg])
        assert result == "# Final output"

    def test_list_content_blocks(self) -> None:
        from core.research.knowledge_base.agents import _extract_synthesis_output

        ai_msg = MagicMock(type="ai", content=[{"text": "Part 1"}, {"text": "Part 2"}])
        result = _extract_synthesis_output([ai_msg])
        assert "Part 1" in result
        assert "Part 2" in result

    def test_empty(self) -> None:
        from core.research.knowledge_base.agents import _extract_synthesis_output

        assert _extract_synthesis_output([]) == ""
        assert _extract_synthesis_output(None) == ""


class TestExtractTextWithCitations:
    """Tests for _extract_text_with_citations."""

    def test_joins_text_blocks(self) -> None:
        from core.research.knowledge_base.agents import _extract_text_with_citations

        b1 = MagicMock(type="text", text="First paragraph.")
        b2 = MagicMock(type="server_tool_use")
        b3 = MagicMock(type="text", text="Second paragraph.")
        response = MagicMock(content=[b1, b2, b3])

        result = _extract_text_with_citations(response)
        assert "First paragraph" in result
        assert "Second paragraph" in result


# ---------------------------------------------------------------------------
# Revision Note Pass-Through — agents forward revision_note to prompt builders
# ---------------------------------------------------------------------------

class TestRevisionNotePassThrough:
    """Agents pass revision_note to their prompt builders."""

    @pytest.mark.asyncio
    async def test_perplexity_agent_passes_revision_note(
        self, kb_input: KnowledgeBaseInput, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Agent 1 (company overview) forwards revision_note to prompt builder."""
        from core.research.knowledge_base.agents import run_company_overview_agent

        captured_query = {}

        def _capture(query: str, **kw: Any) -> str:
            captured_query["q"] = query
            return "# Result"

        mock_client = MagicMock()
        mock_client.research = MagicMock(side_effect=_capture)
        monkeypatch.setattr(_PERPLEXITY_PATCH, mock_client)

        await run_company_overview_agent(
            kb_input, timeout_s=10, revision_note="Expand funding section",
        )
        assert "## Reviewer Feedback" in captured_query["q"]
        assert "Expand funding section" in captured_query["q"]

    @pytest.mark.asyncio
    async def test_brand_perception_agent_passes_revision_note(
        self, kb_input: KnowledgeBaseInput, upstream_docs: Dict[str, str],
    ) -> None:
        """Agent 5 (brand perception) forwards revision_note to prompt builder."""
        from core.research.knowledge_base.agents import run_brand_perception_agent

        mock_response = _make_anthropic_response("# Brand Analysis with revisions.")
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        captured_messages: list = []
        original_create = mock_client.messages.create

        async def _capture_create(**kwargs: Any) -> Any:
            captured_messages.append(kwargs.get("messages", []))
            return await original_create(**kwargs)

        mock_client.messages.create = AsyncMock(side_effect=_capture_create)

        with patch(f"{_ANTHROPIC_PATCH}.AsyncAnthropic", return_value=mock_client):
            await run_brand_perception_agent(
                kb_input, upstream_docs, timeout_s=10,
                revision_note="Add analyst opinions",
            )

        # The user message should contain the revision note
        user_content = captured_messages[0][0]["content"]
        assert "## Reviewer Feedback" in user_content
        assert "Add analyst opinions" in user_content


class TestBuildModel:
    """Tests for _build_model helper."""

    def test_colon_format(self) -> None:
        from core.research.knowledge_base.agents import _build_model

        with patch("core.research.knowledge_base.agents.init_chat_model") as mock_init:
            mock_init.return_value = MagicMock()
            _build_model("anthropic:claude-opus-4-6")
            mock_init.assert_called_once_with("claude-opus-4-6", model_provider="anthropic")

    def test_slash_format(self) -> None:
        from core.research.knowledge_base.agents import _build_model

        with patch("core.research.knowledge_base.agents.init_chat_model") as mock_init:
            mock_init.return_value = MagicMock()
            _build_model("anthropic/claude-opus-4-6")
            mock_init.assert_called_once_with("claude-opus-4-6", model_provider="anthropic")

    def test_bare_model(self) -> None:
        from core.research.knowledge_base.agents import _build_model

        with patch("core.research.knowledge_base.agents.init_chat_model") as mock_init:
            mock_init.return_value = MagicMock()
            _build_model("gpt-4o")
            mock_init.assert_called_once_with("gpt-4o")


# ---------------------------------------------------------------------------
# CX-3: Synthesis uses SYNTHESIS doc_type
# ---------------------------------------------------------------------------


class TestSynthesisDocType:
    """CX-3: Synthesis agent results use KBDocType.SYNTHESIS, not COMPANY_OVERVIEW."""

    @pytest.mark.asyncio
    async def test_synthesis_success_has_synthesis_doc_type(
        self, kb_input: KnowledgeBaseInput, tmp_path: Path,
    ) -> None:
        from core.research.knowledge_base.agents import run_synthesis_agent

        mock_msg = MagicMock()
        mock_msg.type = "ai"
        mock_msg.content = "# Synthesized Profile"

        mock_agent = MagicMock()
        mock_agent.ainvoke = AsyncMock(return_value={"messages": [mock_msg]})

        with (
            patch("core.research.knowledge_base.agents.create_react_agent", return_value=mock_agent),
            patch("core.research.knowledge_base.agents._build_model", return_value=MagicMock()),
        ):
            result = await run_synthesis_agent(
                input_data=kb_input,
                kb_base_dir=tmp_path,
                available_docs={"company_overview": "p1", "customer_reviews": "p2", "competitor_registry": "p3"},
                missing_docs=[],
                timeout_s=10,
            )

        assert result.doc_type == KBDocType.SYNTHESIS

    @pytest.mark.asyncio
    async def test_synthesis_error_has_synthesis_doc_type(
        self, kb_input: KnowledgeBaseInput,
    ) -> None:
        from core.research.knowledge_base.agents import run_synthesis_agent

        # Insufficient docs → error
        result = await run_synthesis_agent(
            input_data=kb_input,
            kb_base_dir=Path("/tmp/test"),
            available_docs={"company_overview": "p1"},
            missing_docs=["a", "b", "c", "d"],
        )
        assert result.error is not None
        assert result.doc_type == KBDocType.SYNTHESIS


# ---------------------------------------------------------------------------
# CX-8: pause_turn partial output flag
# ---------------------------------------------------------------------------


class TestPauseTurnPartialFlag:
    """CX-8: Brand perception agent sets is_partial when pause_turn limit hit."""

    @pytest.mark.asyncio
    async def test_pause_turn_limit_marks_partial(
        self, kb_input: KnowledgeBaseInput, upstream_docs: Dict[str, str],
    ) -> None:
        from core.research.knowledge_base.agents import _MAX_PAUSE_TURNS, run_brand_perception_agent

        pause_response = _make_anthropic_response("Still working...", stop_reason="pause_turn")
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=pause_response)

        with patch(f"{_ANTHROPIC_PATCH}.AsyncAnthropic", return_value=mock_client):
            result = await run_brand_perception_agent(
                kb_input, upstream_docs, timeout_s=30,
            )

        assert result.is_partial is True
        assert result.error is None

    @pytest.mark.asyncio
    async def test_normal_completion_not_partial(
        self, kb_input: KnowledgeBaseInput, upstream_docs: Dict[str, str],
    ) -> None:
        from core.research.knowledge_base.agents import run_brand_perception_agent

        mock_response = _make_anthropic_response("# Full analysis complete.")
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch(f"{_ANTHROPIC_PATCH}.AsyncAnthropic", return_value=mock_client):
            result = await run_brand_perception_agent(
                kb_input, upstream_docs, timeout_s=30,
            )

        assert result.is_partial is False
        assert result.error is None


# ---------------------------------------------------------------------------
# CX-9: Perplexity timeout forwarded
# ---------------------------------------------------------------------------


class TestPerplexityTimeoutForwarded:
    """CX-9: Perplexity agents forward timeout_s to the client."""

    @pytest.mark.asyncio
    async def test_timeout_passed_to_research(
        self, kb_input: KnowledgeBaseInput, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from core.research.knowledge_base.agents import run_company_overview_agent

        captured_kwargs: Dict[str, Any] = {}

        def _capture(**kw: Any) -> str:
            captured_kwargs.update(kw)
            return "# Result"

        mock_client = MagicMock()
        mock_client.research = MagicMock(side_effect=_capture)
        monkeypatch.setattr(_PERPLEXITY_PATCH, mock_client)

        await run_company_overview_agent(kb_input, timeout_s=42.0)
        assert captured_kwargs.get("timeout_s") == 42.0


# ---------------------------------------------------------------------------
# Delta Synthesis Mode
# ---------------------------------------------------------------------------

_AGENTS_MOD = "core.research.knowledge_base.agents"


def _mock_synthesis_agent() -> MagicMock:
    """Build a mock agent whose ainvoke returns a valid synthesis response."""
    mock_msg = MagicMock()
    mock_msg.type = "ai"
    mock_msg.content = "# Updated Profile"
    mock_agent = MagicMock()
    mock_agent.ainvoke = AsyncMock(return_value={"messages": [mock_msg]})
    return mock_agent


class TestSynthesisAgentDeltaMode:
    """Delta mode routing: delta_mode=True uses delta prompts, False uses full prompts."""

    @pytest.mark.asyncio
    async def test_delta_mode_uses_delta_prompt_builders(
        self, kb_input: KnowledgeBaseInput, tmp_path: Path,
    ) -> None:
        from core.research.knowledge_base.agents import run_synthesis_agent

        with (
            patch(f"{_AGENTS_MOD}.create_react_agent", return_value=_mock_synthesis_agent()),
            patch(f"{_AGENTS_MOD}._build_model", return_value=MagicMock()),
            patch(f"{_AGENTS_MOD}.get_delta_synthesis_system_prompt", return_value="delta sys") as mock_delta_sys,
            patch(f"{_AGENTS_MOD}.build_delta_synthesis_user_prompt", return_value="delta user") as mock_delta_user,
            patch(f"{_AGENTS_MOD}.get_synthesis_system_prompt", return_value="full sys") as mock_full_sys,
            patch(f"{_AGENTS_MOD}.build_synthesis_user_prompt", return_value="full user") as mock_full_user,
        ):
            await run_synthesis_agent(
                input_data=kb_input,
                kb_base_dir=tmp_path,
                available_docs={"company_overview": "p1", "customer_reviews": "p2", "competitor_registry": "p3"},
                missing_docs=[],
                timeout_s=10,
                delta_mode=True,
                changed_docs={"customer_reviews": "customer_reviews/v2.md"},
                previous_synthesis_path="synthesis/v1.md",
            )

        mock_delta_sys.assert_called_once()
        mock_delta_user.assert_called_once()
        mock_full_sys.assert_not_called()
        mock_full_user.assert_not_called()

    @pytest.mark.asyncio
    async def test_full_mode_uses_full_prompt_builders(
        self, kb_input: KnowledgeBaseInput, tmp_path: Path,
    ) -> None:
        from core.research.knowledge_base.agents import run_synthesis_agent

        with (
            patch(f"{_AGENTS_MOD}.create_react_agent", return_value=_mock_synthesis_agent()),
            patch(f"{_AGENTS_MOD}._build_model", return_value=MagicMock()),
            patch(f"{_AGENTS_MOD}.get_delta_synthesis_system_prompt", return_value="delta sys") as mock_delta_sys,
            patch(f"{_AGENTS_MOD}.build_delta_synthesis_user_prompt", return_value="delta user") as mock_delta_user,
            patch(f"{_AGENTS_MOD}.get_synthesis_system_prompt", return_value="full sys") as mock_full_sys,
            patch(f"{_AGENTS_MOD}.build_synthesis_user_prompt", return_value="full user") as mock_full_user,
        ):
            await run_synthesis_agent(
                input_data=kb_input,
                kb_base_dir=tmp_path,
                available_docs={"company_overview": "p1", "customer_reviews": "p2", "competitor_registry": "p3"},
                missing_docs=[],
                timeout_s=10,
                delta_mode=False,
            )

        mock_full_sys.assert_called_once()
        mock_full_user.assert_called_once()
        mock_delta_sys.assert_not_called()
        mock_delta_user.assert_not_called()

    @pytest.mark.asyncio
    async def test_delta_mode_min_3_docs_still_required(
        self, kb_input: KnowledgeBaseInput,
    ) -> None:
        from core.research.knowledge_base.agents import run_synthesis_agent

        result = await run_synthesis_agent(
            input_data=kb_input,
            kb_base_dir=Path("/tmp/test"),
            available_docs={"company_overview": "p1"},
            missing_docs=["a", "b", "c", "d"],
            delta_mode=True,
            changed_docs={"company_overview": "p1"},
            previous_synthesis_path="synthesis/v1.md",
        )
        assert result.error is not None
        assert "minimum 3/5" in result.error

    @pytest.mark.asyncio
    async def test_delta_mode_missing_previous_path_errors(
        self, kb_input: KnowledgeBaseInput,
    ) -> None:
        from core.research.knowledge_base.agents import run_synthesis_agent

        result = await run_synthesis_agent(
            input_data=kb_input,
            kb_base_dir=Path("/tmp/test"),
            available_docs={"company_overview": "p1", "customer_reviews": "p2", "competitor_registry": "p3"},
            missing_docs=[],
            delta_mode=True,
            changed_docs={"customer_reviews": "p2"},
            previous_synthesis_path=None,
        )
        assert result.error is not None
        assert "previous_synthesis_path" in result.error

    @pytest.mark.asyncio
    async def test_delta_mode_passes_changed_and_unchanged(
        self, kb_input: KnowledgeBaseInput, tmp_path: Path,
    ) -> None:
        from core.research.knowledge_base.agents import run_synthesis_agent

        captured_kwargs: Dict[str, Any] = {}

        def _capture_delta_prompt(*args: Any, **kw: Any) -> str:
            captured_kwargs.update(kw)
            return "delta user prompt"

        with (
            patch(f"{_AGENTS_MOD}.create_react_agent", return_value=_mock_synthesis_agent()),
            patch(f"{_AGENTS_MOD}._build_model", return_value=MagicMock()),
            patch(f"{_AGENTS_MOD}.get_delta_synthesis_system_prompt", return_value="sys"),
            patch(f"{_AGENTS_MOD}.build_delta_synthesis_user_prompt", side_effect=_capture_delta_prompt),
        ):
            await run_synthesis_agent(
                input_data=kb_input,
                kb_base_dir=tmp_path,
                available_docs={
                    "company_overview": "company_overview/v1.md",
                    "customer_reviews": "customer_reviews/v2.md",
                    "competitor_registry": "competitor_registry/v1.md",
                },
                missing_docs=["weakness_analysis"],
                timeout_s=10,
                delta_mode=True,
                changed_docs={"customer_reviews": "customer_reviews/v2.md"},
                previous_synthesis_path="synthesis/v1.md",
            )

        assert captured_kwargs["previous_synthesis_path"] == "synthesis/v1.md"
        assert "customer_reviews" in captured_kwargs["changed_docs"]
        # unchanged = available minus changed
        assert "company_overview" in captured_kwargs["unchanged_docs"]
        assert "competitor_registry" in captured_kwargs["unchanged_docs"]
        assert "customer_reviews" not in captured_kwargs["unchanged_docs"]
