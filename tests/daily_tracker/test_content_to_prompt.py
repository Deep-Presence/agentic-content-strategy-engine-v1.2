"""Tests for ContentToPromptService — LLM-based prompt generation from pages.

Tests cover:
- Response parsing (valid JSON, bare arrays, malformed input)
- Buyer stage / intent type validation
- Batch generation with concurrency
- Content hash computation
- Distribution validation (at least 1 per buyer stage when k >= 3)
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.daily_tracker.content_to_prompt import (
    ContentToPromptService,
    _build_user_prompt,
    compute_content_hash,
)
from core.models.daily_tracker import (
    GeneratedPagePrompt,
    PageContext,
    PagePromptGenerationResult,
)


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def sample_page() -> PageContext:
    return PageContext(
        inventory_id="inv-001",
        url="https://example.com/blog/ap-automation",
        title="Complete Guide to AP Automation",
        meta_description="Learn how accounts payable automation can reduce costs and errors.",
        content_preview="Accounts payable automation streamlines invoice processing, "
            "reduces manual data entry, and improves cash flow management. "
            "This guide covers the key benefits, implementation steps, and ROI metrics.",
        categories=["finance", "automation"],
        detected_primary_topic="accounts payable automation",
        content_type_detected="blog_post",
        word_count=3200,
    )


@pytest.fixture
def service() -> ContentToPromptService:
    return ContentToPromptService(
        model="test-model",
        max_tokens=1024,
        temperature=0.4,
        max_retries=1,
        base_delay=0.01,
    )


def _make_llm_response(prompts_json: list[dict]) -> str:
    """Build valid JSON response matching LLM output format."""
    return json.dumps({"prompts": prompts_json})


def _make_mock_openai_response(content: str, model: str = "test-model"):
    """Create a mock OpenAI ChatCompletion response."""
    usage = MagicMock()
    usage.prompt_tokens = 100
    usage.completion_tokens = 200
    usage.total_tokens = 300

    message = MagicMock()
    message.content = content

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    response.model = model

    return response


# ── _parse_response tests ─────────────────────────────────────────────


class TestParseResponse:
    """Tests for ContentToPromptService._parse_response."""

    def test_valid_json_with_prompts_key(self):
        raw = _make_llm_response([
            {
                "query_text": "What is AP automation?",
                "buyer_stage": "tofu",
                "intent_type": "informational",
                "is_branded": False,
                "reasoning": "Educational query about the topic",
            },
            {
                "query_text": "Best AP automation software for mid-market",
                "buyer_stage": "mofu",
                "intent_type": "commercial",
                "is_branded": False,
                "reasoning": "Comparison query",
            },
        ])
        result = ContentToPromptService._parse_response(raw)
        assert len(result) == 2
        assert result[0].query_text == "What is AP automation?"
        assert result[0].buyer_stage == "tofu"
        assert result[0].intent_type == "informational"
        assert result[0].is_branded is False
        assert result[1].buyer_stage == "mofu"
        assert result[1].intent_type == "commercial"

    def test_bare_array_format(self):
        raw = json.dumps([
            {"query_text": "How does AP automation work?", "buyer_stage": "tofu", "intent_type": "informational"},
        ])
        result = ContentToPromptService._parse_response(raw)
        assert len(result) == 1
        assert result[0].query_text == "How does AP automation work?"

    def test_empty_query_text_skipped(self):
        raw = _make_llm_response([
            {"query_text": "", "buyer_stage": "tofu", "intent_type": "informational"},
            {"query_text": "Valid query", "buyer_stage": "mofu", "intent_type": "commercial"},
        ])
        result = ContentToPromptService._parse_response(raw)
        assert len(result) == 1
        assert result[0].query_text == "Valid query"

    def test_invalid_buyer_stage_cleared(self):
        raw = _make_llm_response([
            {"query_text": "Some query", "buyer_stage": "invalid_stage", "intent_type": "informational"},
        ])
        result = ContentToPromptService._parse_response(raw)
        assert len(result) == 1
        assert result[0].buyer_stage == ""

    def test_invalid_intent_type_cleared(self):
        raw = _make_llm_response([
            {"query_text": "Some query", "buyer_stage": "tofu", "intent_type": "unknown"},
        ])
        result = ContentToPromptService._parse_response(raw)
        assert len(result) == 1
        assert result[0].intent_type == ""

    def test_malformed_json_with_extractable_array(self):
        raw = 'Here are the prompts: [{"query_text": "Test query", "buyer_stage": "bofu", "intent_type": "transactional"}] hope this helps'
        result = ContentToPromptService._parse_response(raw)
        assert len(result) == 1
        assert result[0].query_text == "Test query"

    def test_completely_invalid_json(self):
        result = ContentToPromptService._parse_response("not json at all")
        assert result == []

    def test_non_dict_items_skipped(self):
        raw = json.dumps({"prompts": ["string", 42, None, {"query_text": "Valid"}]})
        result = ContentToPromptService._parse_response(raw)
        assert len(result) == 1

    def test_alternative_text_key(self):
        """Some LLMs may use 'text' instead of 'query_text'."""
        raw = _make_llm_response([
            {"text": "Alternative key query", "buyer_stage": "tofu", "intent_type": "informational"},
        ])
        result = ContentToPromptService._parse_response(raw)
        assert len(result) == 1
        assert result[0].query_text == "Alternative key query"

    def test_rationale_key_mapped_to_reasoning(self):
        """Some LLMs may use 'rationale' instead of 'reasoning'."""
        raw = _make_llm_response([
            {"query_text": "Q", "buyer_stage": "tofu", "intent_type": "informational", "rationale": "My rationale"},
        ])
        result = ContentToPromptService._parse_response(raw)
        assert result[0].reasoning == "My rationale"

    def test_branded_flag_parsed(self):
        raw = _make_llm_response([
            {"query_text": "Ramp AP automation", "buyer_stage": "bofu", "intent_type": "navigational", "is_branded": True},
        ])
        result = ContentToPromptService._parse_response(raw)
        assert result[0].is_branded is True


# ── Content hash tests ────────────────────────────────────────────────


class TestContentHash:
    def test_same_content_same_hash(self, sample_page: PageContext):
        h1 = compute_content_hash(sample_page)
        h2 = compute_content_hash(sample_page)
        assert h1 == h2

    def test_different_title_different_hash(self, sample_page: PageContext):
        h1 = compute_content_hash(sample_page)
        modified = sample_page.model_copy(update={"title": "Different Title"})
        h2 = compute_content_hash(modified)
        assert h1 != h2

    def test_hash_is_16_chars(self, sample_page: PageContext):
        h = compute_content_hash(sample_page)
        assert len(h) == 16


# ── User prompt construction tests ────────────────────────────────────


class TestBuildUserPrompt:
    def test_includes_page_metadata(self, sample_page: PageContext):
        prompt = _build_user_prompt(sample_page, "Ramp", "Finance", ["Brex", "Bill.com"], 6)
        assert "Complete Guide to AP Automation" in prompt
        assert "Ramp" in prompt
        assert "Brex" in prompt
        assert "6" in prompt

    def test_truncates_content_preview(self):
        page = PageContext(content_preview="x" * 500)
        prompt = _build_user_prompt(page, "Brand", "", [], 4)
        # Content preview should be at most 300 chars in the prompt
        assert "x" * 300 in prompt
        assert "x" * 301 not in prompt


# ── Generate for page (mocked LLM) ──────────────────────────────────


class TestGenerateForPage:
    @pytest.mark.asyncio
    async def test_successful_generation(self, service: ContentToPromptService, sample_page: PageContext):
        llm_output = _make_llm_response([
            {"query_text": "What is AP automation?", "buyer_stage": "tofu", "intent_type": "informational"},
            {"query_text": "Best AP tools", "buyer_stage": "mofu", "intent_type": "commercial"},
        ])
        mock_response = _make_mock_openai_response(llm_output)
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with (
            patch("core.shared_tools.openrouter_client.get_async_client", return_value=mock_client),
            patch("core.shared_tools.openrouter_client._ensure_model_prefix", return_value="test-model"),
            patch("core.shared_tools.cost_tracker.track_llm_cost"),
        ):
            result = await service.generate_prompts_for_page(
                sample_page, "Ramp", "Finance", ["Brex"], k=6,
            )

        assert isinstance(result, PagePromptGenerationResult)
        assert result.inventory_id == "inv-001"
        assert len(result.prompts) == 2
        assert result.model_used == "test-model"
        assert result.token_usage["total_tokens"] == 300

    @pytest.mark.asyncio
    async def test_workspace_context_uses_byok_llm_wrapper(
        self, service: ContentToPromptService, sample_page: PageContext,
    ):
        llm_output = _make_llm_response([
            {"query_text": "What is AP automation?", "buyer_stage": "tofu", "intent_type": "informational"},
        ])
        response = MagicMock(
            content=llm_output,
            model="anthropic/claude-sonnet-4-6",
            input_tokens=11,
            output_tokens=22,
            total_tokens=33,
        )

        with (
            patch(
                "core.content_engine.llm_client.llm_call_for_agent",
                new_callable=AsyncMock,
                return_value=response,
            ) as mock_call,
            patch("core.shared_tools.openrouter_client.get_async_client") as mock_platform,
        ):
            result = await service.generate_prompts_for_page(
                sample_page,
                "Ramp",
                "Finance",
                ["Brex"],
                k=6,
                workspace_id="ws-123",
                workspace_slug="ramp",
                company_slug="ramp",
            )

        assert len(result.prompts) == 1
        assert result.model_used == "anthropic/claude-sonnet-4-6"
        assert result.token_usage["total_tokens"] == 33
        mock_platform.assert_not_called()
        mock_call.assert_awaited_once()
        kwargs = mock_call.call_args.kwargs
        assert kwargs["workspace_id"] == "ws-123"
        assert kwargs["workspace_slug"] == "ramp"
        assert kwargs["agent_key"] == "daily_tracker.content_to_prompt"
        assert kwargs["metadata"]["pipeline_step"] == "generate_prompts"
        assert kwargs["metadata"]["company_slug"] == "ramp"

    @pytest.mark.asyncio
    async def test_retries_on_failure(self, sample_page: PageContext):
        svc = ContentToPromptService(model="test", max_retries=2, base_delay=0.01)

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=RuntimeError("API error"),
        )

        with (
            patch("core.shared_tools.openrouter_client.get_async_client", return_value=mock_client),
            patch("core.shared_tools.openrouter_client._ensure_model_prefix", return_value="test"),
            patch("core.shared_tools.cost_tracker.track_llm_cost"),
        ):
            with pytest.raises(RuntimeError, match="API error"):
                await svc.generate_prompts_for_page(sample_page, "Brand", k=4)

        assert mock_client.chat.completions.create.call_count == 2


# ── Batch generation tests ───────────────────────────────────────────


class TestBatchGeneration:
    @pytest.mark.asyncio
    async def test_batch_returns_results_per_page(self, service: ContentToPromptService):
        pages = [
            PageContext(inventory_id="p1", title="Page 1"),
            PageContext(inventory_id="p2", title="Page 2"),
        ]

        llm_output = _make_llm_response([
            {"query_text": "Q1", "buyer_stage": "tofu", "intent_type": "informational"},
        ])
        mock_response = _make_mock_openai_response(llm_output)
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with (
            patch("core.shared_tools.openrouter_client.get_async_client", return_value=mock_client),
            patch("core.shared_tools.openrouter_client._ensure_model_prefix", return_value="test"),
            patch("core.shared_tools.cost_tracker.track_llm_cost"),
        ):
            results = await service.generate_prompts_batch(
                pages, "Brand", k=4, concurrency=2,
            )

        assert len(results) == 2
        assert results[0].inventory_id == "p1"
        assert results[1].inventory_id == "p2"

    @pytest.mark.asyncio
    async def test_batch_handles_partial_failure(self, service: ContentToPromptService):
        pages = [
            PageContext(inventory_id="good", title="Good Page"),
            PageContext(inventory_id="bad", title="Bad Page"),
        ]

        call_count = 0

        async def _side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("LLM error")
            return _make_mock_openai_response(
                _make_llm_response([{"query_text": "Q", "buyer_stage": "tofu", "intent_type": "informational"}]),
            )

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=_side_effect)

        with (
            patch("core.shared_tools.openrouter_client.get_async_client", return_value=mock_client),
            patch("core.shared_tools.openrouter_client._ensure_model_prefix", return_value="test"),
            patch("core.shared_tools.cost_tracker.track_llm_cost"),
        ):
            results = await service.generate_prompts_batch(pages, "Brand", k=4)

        assert len(results) == 2
        # One succeeds, one returns empty prompts (graceful failure)
        succeeded = [r for r in results if len(r.prompts) > 0]
        failed = [r for r in results if len(r.prompts) == 0]
        assert len(succeeded) == 1
        assert len(failed) == 1


# ── Pydantic model tests ─────────────────────────────────────────────


class TestPydanticModels:
    def test_page_context_defaults(self):
        ctx = PageContext()
        assert ctx.inventory_id == ""
        assert ctx.categories == []
        assert ctx.word_count == 0

    def test_generated_page_prompt_defaults(self):
        p = GeneratedPagePrompt()
        assert p.query_text == ""
        assert p.is_branded is False

    def test_page_prompt_generation_result_defaults(self):
        r = PagePromptGenerationResult()
        assert r.prompts == []
        assert r.token_usage == {}
