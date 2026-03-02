"""Tests for core.content_engine.llm_client — LiteLLM wrapper.

Tests model prefix detection, retry logic, and callback configuration.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.content_engine.llm_client import _ensure_litellm_model


# ═══════════════════════════════════════════════════════════════════════
# _ensure_litellm_model (provider prefix detection)
# ═══════════════════════════════════════════════════════════════════════


class TestEnsureLitellmModel:
    """Tests for _ensure_litellm_model()."""

    def test_already_prefixed_passes_through(self):
        assert _ensure_litellm_model("anthropic/claude-sonnet-4-5") == "anthropic/claude-sonnet-4-5"

    def test_claude_gets_anthropic_prefix(self):
        assert _ensure_litellm_model("claude-sonnet-4-5-20250929") == "anthropic/claude-sonnet-4-5-20250929"

    def test_claude_haiku_gets_anthropic_prefix(self):
        assert _ensure_litellm_model("claude-haiku-4-5-20251001") == "anthropic/claude-haiku-4-5-20251001"

    def test_sonar_gets_perplexity_prefix(self):
        assert _ensure_litellm_model("sonar-pro") == "perplexity/sonar-pro"

    def test_sonar_deep_gets_perplexity_prefix(self):
        assert _ensure_litellm_model("sonar-deep-research") == "perplexity/sonar-deep-research"

    def test_gpt_gets_openai_prefix(self):
        assert _ensure_litellm_model("gpt-5.2-2025-12-11") == "openai/gpt-5.2-2025-12-11"

    def test_o1_gets_openai_prefix(self):
        assert _ensure_litellm_model("o1-preview") == "openai/o1-preview"

    def test_o3_gets_openai_prefix(self):
        assert _ensure_litellm_model("o3-mini") == "openai/o3-mini"

    def test_gemini_gets_google_prefix(self):
        assert _ensure_litellm_model("gemini-3-flash-preview") == "google/gemini-3-flash-preview"

    def test_unknown_model_passes_through(self):
        assert _ensure_litellm_model("my-custom-model") == "my-custom-model"

    def test_openai_prefixed_passes_through(self):
        assert _ensure_litellm_model("openai/gpt-5.2") == "openai/gpt-5.2"


# ═══════════════════════════════════════════════════════════════════════
# llm_call (async LLM wrapper)
# ═══════════════════════════════════════════════════════════════════════


def _mock_litellm_response(content="Hello", model="test-model",
                            prompt_tokens=50, completion_tokens=100):
    """Create a mock LiteLLM response object."""
    choice = MagicMock()
    choice.message.content = content
    choice.finish_reason = "stop"
    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    usage.total_tokens = prompt_tokens + completion_tokens
    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    response.model = model
    return response


class TestLlmCall:
    """Tests for llm_call()."""

    @pytest.mark.asyncio
    async def test_successful_call_returns_llm_response(self):
        from core.content_engine.llm_client import llm_call

        mock_resp = _mock_litellm_response(content="Test output", model="anthropic/claude-sonnet-4-5")
        with patch("core.content_engine.llm_client.litellm") as mock_litellm, \
             patch("core.content_engine.llm_client._litellm_available", True):
            mock_litellm.acompletion = AsyncMock(return_value=mock_resp)
            result = await llm_call(
                model="anthropic/claude-sonnet-4-5",
                system="You are a test.",
                user="Hello",
            )
        assert result.content == "Test output"
        assert result.model == "anthropic/claude-sonnet-4-5"
        assert result.input_tokens == 50
        assert result.output_tokens == 100
        assert result.total_tokens == 150
        assert result.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_retry_on_transient_failure(self):
        from core.content_engine.llm_client import llm_call

        mock_resp = _mock_litellm_response(content="Eventually works")
        with patch("core.content_engine.llm_client.litellm") as mock_litellm, \
             patch("core.content_engine.llm_client._litellm_available", True), \
             patch("core.content_engine.llm_client.asyncio.sleep", new_callable=AsyncMock):
            mock_litellm.acompletion = AsyncMock(
                side_effect=[Exception("Transient"), mock_resp]
            )
            result = await llm_call(
                model="anthropic/claude-sonnet-4-5",
                system="sys",
                user="usr",
                max_retries=3,
                base_delay=0.01,
            )
        assert result.content == "Eventually works"
        assert mock_litellm.acompletion.call_count == 2

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        from core.content_engine.llm_client import llm_call

        with patch("core.content_engine.llm_client.litellm") as mock_litellm, \
             patch("core.content_engine.llm_client._litellm_available", True), \
             patch("core.content_engine.llm_client.asyncio.sleep", new_callable=AsyncMock):
            mock_litellm.acompletion = AsyncMock(
                side_effect=Exception("Permanent failure")
            )
            with pytest.raises(Exception, match="Permanent failure"):
                await llm_call(
                    model="test-model",
                    system="sys",
                    user="usr",
                    max_retries=2,
                    base_delay=0.01,
                )
        assert mock_litellm.acompletion.call_count == 2

    @pytest.mark.asyncio
    async def test_raises_runtime_error_when_unavailable(self):
        from core.content_engine.llm_client import llm_call

        with patch("core.content_engine.llm_client._litellm_available", False):
            with pytest.raises(RuntimeError, match="litellm is not installed"):
                await llm_call(
                    model="test-model",
                    system="sys",
                    user="usr",
                )

    @pytest.mark.asyncio
    async def test_metadata_passed_through(self):
        from core.content_engine.llm_client import llm_call

        mock_resp = _mock_litellm_response()
        with patch("core.content_engine.llm_client.litellm") as mock_litellm, \
             patch("core.content_engine.llm_client._litellm_available", True):
            mock_litellm.acompletion = AsyncMock(return_value=mock_resp)
            await llm_call(
                model="anthropic/claude-sonnet-4-5",
                system="sys",
                user="usr",
                metadata={"run_id": "abc"},
            )
        call_kwargs = mock_litellm.acompletion.call_args[1]
        assert call_kwargs["metadata"] == {"run_id": "abc"}


# ═══════════════════════════════════════════════════════════════════════
# configure_litellm_callbacks
# ═══════════════════════════════════════════════════════════════════════


class TestConfigureLitellmCallbacks:
    """Tests for configure_litellm_callbacks()."""

    def test_sets_callbacks_when_langsmith_key_set(self, monkeypatch):
        from core.content_engine.llm_client import configure_litellm_callbacks

        monkeypatch.setenv("LANGSMITH_API_KEY", "test-key")
        with patch("core.content_engine.llm_client.litellm") as mock_litellm, \
             patch("core.content_engine.llm_client._litellm_available", True):
            configure_litellm_callbacks()
            assert mock_litellm.success_callback == ["langsmith"]
            assert mock_litellm.failure_callback == ["langsmith"]

    def test_skips_when_no_langsmith_key(self, monkeypatch):
        from core.content_engine.llm_client import configure_litellm_callbacks

        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
        with patch("core.content_engine.llm_client.litellm") as mock_litellm, \
             patch("core.content_engine.llm_client._litellm_available", True):
            configure_litellm_callbacks()
            # success_callback should NOT have been set
            assert not hasattr(mock_litellm.success_callback, '__iter__') or \
                mock_litellm.success_callback != ["langsmith"]

    def test_noop_when_litellm_unavailable(self):
        from core.content_engine.llm_client import configure_litellm_callbacks

        with patch("core.content_engine.llm_client._litellm_available", False):
            # Should not raise
            configure_litellm_callbacks()
