"""Tests for core.content_engine.evaluator.eeat_judge — E-E-A-T evaluation.

Tests evaluate_eeat() with mocked llm_call.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models.content_generation import ContentBrief, DimensionResult, FormattedContent
from tests.content_engine.conftest import _make_llm_response


@pytest.fixture
def content():
    return FormattedContent(
        brief_id="brief-001",
        title="Test Article",
        markdown="# Test Article\n\nSome content about 409A valuations.",
        word_count=1500,
    )


@pytest.fixture
def brief():
    return ContentBrief(
        brief_id="brief-001",
        title="Test Article",
        key_topics=["409A", "equity"],
    )


# Patch tracing (eeat_judge uses v1.0 tracing module)
_TRACING_PATCHES = [
    "core.content_engine.evaluator.eeat_judge.create_span",
    "core.content_engine.evaluator.eeat_judge.end_span",
    "core.content_engine.evaluator.eeat_judge.log_generation",
    "core.content_engine.evaluator.eeat_judge.log_score",
]


@pytest.fixture(autouse=True)
def _mock_tracing():
    """Disable tracing for all eeat tests."""
    with patch(_TRACING_PATCHES[0], return_value=MagicMock()), \
         patch(_TRACING_PATCHES[1]), \
         patch(_TRACING_PATCHES[2]), \
         patch(_TRACING_PATCHES[3]):
        yield


def _eeat_response(score=0.75, passed=True, feedback="Good E-E-A-T signals"):
    """Build a JSON response mimicking eeat_judge LLM output."""
    return json.dumps({
        "score": score,
        "passed": passed,
        "feedback": feedback,
        "dimension_scores": {
            "experience": 0.8,
            "expertise": 0.7,
            "authoritativeness": 0.75,
            "trustworthiness": 0.8,
        },
        "specific_findings": ["Good use of statistics", "Clear methodology"],
    })


class TestEvaluateEeat:
    """Tests for evaluate_eeat()."""

    @pytest.mark.asyncio
    async def test_returns_dimension_result(self, content, brief):
        from core.content_engine.evaluator.eeat_judge import evaluate_eeat

        resp = _make_llm_response(_eeat_response())
        with patch("core.content_engine.evaluator.eeat_judge.llm_call",
                   new_callable=AsyncMock, return_value=resp):
            result = await evaluate_eeat(content, brief)

        assert isinstance(result, DimensionResult)
        assert result.dimension == "eeat"

    @pytest.mark.asyncio
    async def test_score_parsed(self, content, brief):
        from core.content_engine.evaluator.eeat_judge import evaluate_eeat

        resp = _make_llm_response(_eeat_response(score=0.82))
        with patch("core.content_engine.evaluator.eeat_judge.llm_call",
                   new_callable=AsyncMock, return_value=resp):
            result = await evaluate_eeat(content, brief)

        assert result.score == pytest.approx(0.82)

    @pytest.mark.asyncio
    async def test_passed_true_when_score_high(self, content, brief):
        from core.content_engine.evaluator.eeat_judge import evaluate_eeat

        resp = _make_llm_response(_eeat_response(score=0.75, passed=True))
        with patch("core.content_engine.evaluator.eeat_judge.llm_call",
                   new_callable=AsyncMock, return_value=resp):
            result = await evaluate_eeat(content, brief)

        assert result.passed is True

    @pytest.mark.asyncio
    async def test_passed_false_when_score_low(self, content, brief):
        from core.content_engine.evaluator.eeat_judge import evaluate_eeat

        resp = _make_llm_response(_eeat_response(score=0.4, passed=False))
        with patch("core.content_engine.evaluator.eeat_judge.llm_call",
                   new_callable=AsyncMock, return_value=resp):
            result = await evaluate_eeat(content, brief)

        assert result.passed is False

    @pytest.mark.asyncio
    async def test_handles_markdown_code_fences(self, content, brief):
        from core.content_engine.evaluator.eeat_judge import evaluate_eeat

        fenced = "```json\n" + _eeat_response(score=0.70) + "\n```"
        resp = _make_llm_response(fenced)
        with patch("core.content_engine.evaluator.eeat_judge.llm_call",
                   new_callable=AsyncMock, return_value=resp):
            result = await evaluate_eeat(content, brief)

        assert result.score == pytest.approx(0.70)
        assert result.dimension == "eeat"

    @pytest.mark.asyncio
    async def test_json_parse_error_returns_fallback(self, content, brief):
        from core.content_engine.evaluator.eeat_judge import evaluate_eeat

        resp = _make_llm_response("This is not JSON")
        with patch("core.content_engine.evaluator.eeat_judge.llm_call",
                   new_callable=AsyncMock, return_value=resp):
            result = await evaluate_eeat(content, brief)

        assert result.dimension == "eeat"
        assert result.passed is False
        assert result.score == pytest.approx(0.5)
        assert "parse error" in result.feedback.lower() or "error" in result.feedback.lower()

    @pytest.mark.asyncio
    async def test_llm_failure_returns_fallback(self, content, brief):
        from core.content_engine.evaluator.eeat_judge import evaluate_eeat

        with patch("core.content_engine.evaluator.eeat_judge.llm_call",
                   new_callable=AsyncMock, side_effect=RuntimeError("LLM down")):
            result = await evaluate_eeat(content, brief)

        assert result.dimension == "eeat"
        assert result.passed is False
        assert result.score == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_dimension_scores_in_details(self, content, brief):
        from core.content_engine.evaluator.eeat_judge import evaluate_eeat

        resp = _make_llm_response(_eeat_response())
        with patch("core.content_engine.evaluator.eeat_judge.llm_call",
                   new_callable=AsyncMock, return_value=resp):
            result = await evaluate_eeat(content, brief)

        assert "dimension_scores" in result.details
        assert "experience" in result.details["dimension_scores"]

    @pytest.mark.asyncio
    async def test_specific_findings_in_details(self, content, brief):
        from core.content_engine.evaluator.eeat_judge import evaluate_eeat

        resp = _make_llm_response(_eeat_response())
        with patch("core.content_engine.evaluator.eeat_judge.llm_call",
                   new_callable=AsyncMock, return_value=resp):
            result = await evaluate_eeat(content, brief)

        assert "specific_findings" in result.details
        assert len(result.details["specific_findings"]) == 2

    @pytest.mark.asyncio
    async def test_feedback_string(self, content, brief):
        from core.content_engine.evaluator.eeat_judge import evaluate_eeat

        resp = _make_llm_response(_eeat_response(feedback="Add more data points"))
        with patch("core.content_engine.evaluator.eeat_judge.llm_call",
                   new_callable=AsyncMock, return_value=resp):
            result = await evaluate_eeat(content, brief)

        assert result.feedback == "Add more data points"


class TestEeatUsageLogging:
    """Regression tests for usage tracking in log_generation() call.

    Ensures the sentinel-based guard (response is not None) works correctly
    in all three scenarios: llm_call success, llm_call failure, and parse error.
    """

    @pytest.mark.asyncio
    async def test_llm_failure_does_not_raise_name_error(self, content, brief):
        """When llm_call raises, evaluate_eeat must not raise NameError / UnboundLocalError.

        Regression for the 'response in dir()' anti-pattern replaced by
        'response is not None' sentinel.
        """
        from core.content_engine.evaluator.eeat_judge import evaluate_eeat

        with patch("core.content_engine.evaluator.eeat_judge.llm_call",
                   new_callable=AsyncMock, side_effect=RuntimeError("LLM connection failed")):
            # Must not raise NameError, UnboundLocalError, or any other exception
            result = await evaluate_eeat(content, brief)

        assert result.dimension == "eeat"
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_log_generation_usage_is_zero_on_llm_failure(self, content, brief):
        """When llm_call raises, log_generation must receive usage={input:0, output:0}."""
        from core.content_engine.evaluator.eeat_judge import evaluate_eeat

        with patch("core.content_engine.evaluator.eeat_judge.llm_call",
                   new_callable=AsyncMock, side_effect=RuntimeError("LLM down")), \
             patch("core.content_engine.evaluator.eeat_judge.log_generation") as mock_log:
            await evaluate_eeat(content, brief)

        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args[1]
        assert call_kwargs["usage"]["prompt_tokens"] == 0
        assert call_kwargs["usage"]["completion_tokens"] == 0
        assert call_kwargs["usage"]["total_tokens"] == 0

    @pytest.mark.asyncio
    async def test_log_generation_usage_populated_on_success(self, content, brief):
        """When llm_call succeeds, log_generation receives the actual token counts."""
        from core.content_engine.evaluator.eeat_judge import evaluate_eeat

        resp = _make_llm_response(_eeat_response(), input_tokens=500, output_tokens=300)
        with patch("core.content_engine.evaluator.eeat_judge.llm_call",
                   new_callable=AsyncMock, return_value=resp), \
             patch("core.content_engine.evaluator.eeat_judge.log_generation") as mock_log:
            await evaluate_eeat(content, brief)

        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args[1]
        assert call_kwargs["usage"]["prompt_tokens"] == 500
        assert call_kwargs["usage"]["completion_tokens"] == 300

    @pytest.mark.asyncio
    async def test_log_generation_usage_nonzero_on_parse_error(self, content, brief):
        """When llm_call succeeds but JSON parse fails, response IS assigned.

        The sentinel guard must NOT zero-out usage in this case — the response
        object exists even though parsing failed, so token counts should be reported.
        """
        from core.content_engine.evaluator.eeat_judge import evaluate_eeat

        resp = _make_llm_response("this is not valid json", input_tokens=200, output_tokens=100)
        with patch("core.content_engine.evaluator.eeat_judge.llm_call",
                   new_callable=AsyncMock, return_value=resp), \
             patch("core.content_engine.evaluator.eeat_judge.log_generation") as mock_log:
            result = await evaluate_eeat(content, brief)

        # Verify parse error path was taken
        assert result.passed is False
        assert "error" in result.feedback.lower()

        # Verify token counts are still reported (response was assigned before parse failed)
        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args[1]
        assert call_kwargs["usage"]["prompt_tokens"] == 200
        assert call_kwargs["usage"]["completion_tokens"] == 100
