"""Tests for core.content_engine.llm_client — OpenRouter wrapper.

Tests model prefix detection, retry logic, and OpenRouter configuration.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.content_engine.llm_client import _ensure_model_prefix
from core.model_config.schemas import ResolvedModelConfig

# Backward-compatible import alias
from core.content_engine.llm_client import _ensure_litellm_model


# ═══════════════════════════════════════════════════════════════════════
# _ensure_model_prefix (provider prefix detection)
# ═══════════════════════════════════════════════════════════════════════


class TestEnsureModelPrefix:
    """Tests for _ensure_model_prefix()."""

    def test_already_prefixed_passes_through(self):
        assert _ensure_model_prefix("anthropic/claude-sonnet-4-5") == "anthropic/claude-sonnet-4-5"

    def test_claude_gets_anthropic_prefix(self):
        assert _ensure_model_prefix("claude-sonnet-4-5-20250929") == "anthropic/claude-sonnet-4-5-20250929"

    def test_claude_haiku_gets_anthropic_prefix(self):
        assert _ensure_model_prefix("claude-haiku-4-5") == "anthropic/claude-haiku-4-5"

    def test_sonar_gets_perplexity_prefix(self):
        assert _ensure_model_prefix("sonar-pro") == "perplexity/sonar-pro"

    def test_sonar_deep_gets_perplexity_prefix(self):
        assert _ensure_model_prefix("sonar-deep-research") == "perplexity/sonar-deep-research"

    def test_gpt_gets_openai_prefix(self):
        assert _ensure_model_prefix("gpt-5.2-2025-12-11") == "openai/gpt-5.2-2025-12-11"

    def test_o1_gets_openai_prefix(self):
        assert _ensure_model_prefix("o1-preview") == "openai/o1-preview"

    def test_o3_gets_openai_prefix(self):
        assert _ensure_model_prefix("o3-mini") == "openai/o3-mini"

    def test_gemini_gets_google_prefix(self):
        assert _ensure_model_prefix("gemini-3-flash-preview") == "google/gemini-3-flash-preview"

    def test_text_embedding_small_gets_openai_prefix(self):
        assert _ensure_model_prefix("text-embedding-3-small") == "openai/text-embedding-3-small"

    def test_text_embedding_large_gets_openai_prefix(self):
        assert _ensure_model_prefix("text-embedding-3-large") == "openai/text-embedding-3-large"

    def test_unknown_model_passes_through(self):
        assert _ensure_model_prefix("my-custom-model") == "my-custom-model"

    def test_openai_prefixed_passes_through(self):
        assert _ensure_model_prefix("openai/gpt-5.2") == "openai/gpt-5.2"

    def test_backward_compat_alias(self):
        """_ensure_litellm_model is a backward-compatible alias."""
        assert _ensure_litellm_model is _ensure_model_prefix


# ═══════════════════════════════════════════════════════════════════════
# llm_call (async LLM wrapper via OpenRouter)
# ═══════════════════════════════════════════════════════════════════════


def _mock_openai_response(content="Hello", model="test-model",
                           prompt_tokens=50, completion_tokens=100):
    """Create a mock OpenAI chat completion response."""
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


def _mock_async_client(response):
    """Create a mock AsyncOpenAI client with async chat.completions.create."""
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=response)
    return mock_client


class TestLlmCall:
    """Tests for llm_call()."""

    @pytest.mark.asyncio
    async def test_successful_call_returns_llm_response(self):
        from core.content_engine.llm_client import llm_call

        mock_resp = _mock_openai_response(content="Test output", model="anthropic/claude-sonnet-4-5")
        mock_client = _mock_async_client(mock_resp)

        with patch("core.shared_tools.openrouter_client.get_async_client", return_value=mock_client):
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

        mock_resp = _mock_openai_response(content="Eventually works")
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=[Exception("Transient"), mock_resp]
        )

        with patch("core.shared_tools.openrouter_client.get_async_client", return_value=mock_client), \
             patch("core.content_engine.llm_client.asyncio.sleep", new_callable=AsyncMock):
            result = await llm_call(
                model="anthropic/claude-sonnet-4-5",
                system="sys",
                user="usr",
                max_retries=3,
                base_delay=0.01,
            )
        assert result.content == "Eventually works"
        assert mock_client.chat.completions.create.call_count == 2

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        from core.content_engine.llm_client import llm_call

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("Permanent failure")
        )

        with patch("core.shared_tools.openrouter_client.get_async_client", return_value=mock_client), \
             patch("core.content_engine.llm_client.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(Exception, match="Permanent failure"):
                await llm_call(
                    model="test-model",
                    system="sys",
                    user="usr",
                    max_retries=2,
                    base_delay=0.01,
                )
        assert mock_client.chat.completions.create.call_count == 2

    @pytest.mark.asyncio
    async def test_raises_runtime_error_when_no_api_key(self):
        from core.content_engine.llm_client import llm_call

        with patch(
            "core.shared_tools.openrouter_client.get_async_client",
            side_effect=RuntimeError("OPENROUTER_API_KEY is not set"),
        ):
            with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY is not set"):
                await llm_call(
                    model="test-model",
                    system="sys",
                    user="usr",
                )

    @pytest.mark.asyncio
    async def test_metadata_passed_via_extra_body(self):
        from core.content_engine.llm_client import llm_call

        mock_resp = _mock_openai_response()
        mock_client = _mock_async_client(mock_resp)

        with patch("core.shared_tools.openrouter_client.get_async_client", return_value=mock_client):
            await llm_call(
                model="anthropic/claude-sonnet-4-5",
                system="sys",
                user="usr",
                metadata={"run_id": "abc"},
            )
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["extra_body"] == {"metadata": {"run_id": "abc"}}

    @pytest.mark.asyncio
    async def test_content_none_returns_empty_string(self):
        from core.content_engine.llm_client import llm_call

        mock_resp = _mock_openai_response(content=None)
        mock_client = _mock_async_client(mock_resp)

        with patch("core.shared_tools.openrouter_client.get_async_client", return_value=mock_client):
            result = await llm_call(
                model="anthropic/claude-sonnet-4-5",
                system="sys",
                user="usr",
            )
        assert result.content == ""

    @pytest.mark.asyncio
    async def test_missing_usage_returns_zero_tokens(self):
        from core.content_engine.llm_client import llm_call

        mock_resp = _mock_openai_response()
        mock_resp.usage = None
        mock_client = _mock_async_client(mock_resp)

        with patch("core.shared_tools.openrouter_client.get_async_client", return_value=mock_client):
            result = await llm_call(
                model="anthropic/claude-sonnet-4-5",
                system="sys",
                user="usr",
            )
        assert result.input_tokens == 0
        assert result.output_tokens == 0
        assert result.total_tokens == 0


# ═══════════════════════════════════════════════════════════════════════
# llm_call — cost tracking
# ═══════════════════════════════════════════════════════════════════════


class TestLlmCallCostTracking:
    """Verify track_llm_cost() is called inside llm_call()."""

    @pytest.mark.asyncio
    async def test_cost_tracked_on_successful_call(self):
        from core.content_engine.llm_client import llm_call

        mock_resp = _mock_openai_response(
            content="OK", model="anthropic/claude-sonnet-4-6",
            prompt_tokens=50, completion_tokens=100,
        )
        mock_client = _mock_async_client(mock_resp)
        meta = {
            "pipeline": "content_engine",
            "pipeline_step": "outliner",
            "company_slug": "test-co",
        }

        with patch("core.shared_tools.openrouter_client.get_async_client", return_value=mock_client), \
             patch("core.content_engine.llm_client.track_llm_cost") as mock_track:
            await llm_call(
                model="anthropic/claude-sonnet-4-6",
                system="sys", user="usr", metadata=meta,
            )
        mock_track.assert_called_once()
        kw = mock_track.call_args[1]
        assert kw["model"] == "anthropic/claude-sonnet-4-6"
        assert kw["provider"] == "openrouter"
        assert kw["pipeline"] == "content_engine"
        assert kw["pipeline_step"] == "outliner"
        assert kw["prompt_tokens"] == 50
        assert kw["completion_tokens"] == 100
        assert kw["company_slug"] == "test-co"
        assert kw["source"] == "openrouter"
        assert kw["call_site"] == "core.content_engine.llm_client"

    @pytest.mark.asyncio
    async def test_cost_tracked_with_empty_metadata(self):
        from core.content_engine.llm_client import llm_call

        mock_resp = _mock_openai_response()
        mock_client = _mock_async_client(mock_resp)

        with patch("core.shared_tools.openrouter_client.get_async_client", return_value=mock_client), \
             patch("core.content_engine.llm_client.track_llm_cost") as mock_track:
            await llm_call(
                model="anthropic/claude-sonnet-4-6",
                system="sys", user="usr", metadata=None,
            )
        mock_track.assert_called_once()
        kw = mock_track.call_args[1]
        assert kw["pipeline"] == ""
        assert kw["pipeline_step"] == ""
        assert kw["company_slug"] == ""

    @pytest.mark.asyncio
    async def test_cost_tracked_with_partial_metadata(self):
        from core.content_engine.llm_client import llm_call

        mock_resp = _mock_openai_response()
        mock_client = _mock_async_client(mock_resp)

        with patch("core.shared_tools.openrouter_client.get_async_client", return_value=mock_client), \
             patch("core.content_engine.llm_client.track_llm_cost") as mock_track:
            await llm_call(
                model="anthropic/claude-sonnet-4-6",
                system="sys", user="usr",
                metadata={"agent": "outliner"},  # no pipeline keys
            )
        kw = mock_track.call_args[1]
        assert kw["pipeline"] == ""
        assert kw["pipeline_step"] == ""
        assert kw["company_slug"] == ""

    @pytest.mark.asyncio
    async def test_cost_not_tracked_on_failure(self):
        from core.content_engine.llm_client import llm_call

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("Permanent failure")
        )

        with patch("core.shared_tools.openrouter_client.get_async_client", return_value=mock_client), \
             patch("core.content_engine.llm_client.asyncio.sleep", new_callable=AsyncMock), \
             patch("core.content_engine.llm_client.track_llm_cost") as mock_track:
            with pytest.raises(Exception, match="Permanent failure"):
                await llm_call(
                    model="test-model", system="sys", user="usr",
                    max_retries=2, base_delay=0.01,
                )
        mock_track.assert_not_called()


class FakeModelConfigResolver:
    def __init__(self, resolved: ResolvedModelConfig) -> None:
        self.resolved = resolved
        self.calls = []

    async def resolve(
        self,
        workspace_id: str,
        workspace_slug: str,
        agent_key: str,
    ) -> ResolvedModelConfig:
        self.calls.append((workspace_id, workspace_slug, agent_key))
        return self.resolved


class TestLlmCallForAgent:
    """Verify BYOK runtime calls resolve workspace credentials and agent config."""

    @pytest.mark.asyncio
    async def test_uses_resolved_workspace_key_and_tracks_byok_metadata(self):
        from core.content_engine.llm_client import llm_call_for_agent

        resolved = ResolvedModelConfig(
            workspace_id="workspace-1",
            workspace_slug="test-co",
            agent_key="content.brief_builder",
            model="anthropic/claude-sonnet-4-6",
            base_url="https://openrouter.test/api/v1",
            api_key="sk-or-workspace",
            credential_id="cred-1",
            model_config_id="cfg-1",
            temperature=0.2,
            max_tokens=1234,
            timeout_s=12.0,
            extra_body={"provider": {"require_parameters": True}},
        )
        resolver = FakeModelConfigResolver(resolved)
        mock_resp = _mock_openai_response(
            content="BYOK output",
            model="anthropic/claude-sonnet-4-6",
            prompt_tokens=10,
            completion_tokens=20,
        )
        mock_client = _mock_async_client(mock_resp)
        metadata = {
            "pipeline": "content_engine",
            "pipeline_step": "brief_builder",
            "company_slug": "test-co",
            "run_id": "00000000-0000-0000-0000-000000000001",
        }

        with patch(
            "core.shared_tools.openrouter_client.build_async_client_for_key",
            return_value=mock_client,
        ) as mock_factory, patch(
            "core.content_engine.llm_client.track_llm_cost"
        ) as mock_track, patch(
            "core.shared_tools.openrouter_client.get_async_client"
        ) as legacy_factory:
            result = await llm_call_for_agent(
                workspace_id="workspace-1",
                workspace_slug="test-co",
                agent_key="content.brief_builder",
                system="sys",
                user="usr",
                metadata=metadata,
                resolver=resolver,  # type: ignore[arg-type]
            )

        assert result.content == "BYOK output"
        assert resolver.calls == [
            ("workspace-1", "test-co", "content.brief_builder")
        ]
        mock_factory.assert_called_once_with(
            "sk-or-workspace",
            base_url="https://openrouter.test/api/v1",
            timeout_s=12.0,
        )
        legacy_factory.assert_not_called()
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "anthropic/claude-sonnet-4-6"
        assert call_kwargs["max_tokens"] == 1234
        assert call_kwargs["temperature"] == 0.2
        assert call_kwargs["extra_body"] == {
            "provider": {"require_parameters": True},
            "metadata": metadata,
        }

        mock_track.assert_called_once()
        cost_kwargs = mock_track.call_args.kwargs
        assert cost_kwargs["workspace_id"] == "workspace-1"
        assert cost_kwargs["agent_key"] == "content.brief_builder"
        assert cost_kwargs["credential_id"] == "cred-1"
        assert cost_kwargs["model_config_id"] == "cfg-1"
        assert cost_kwargs["workspace_billed"] is True
        assert cost_kwargs["actual_provider"] == "anthropic"
        assert cost_kwargs["prompt_tokens"] == 10
        assert cost_kwargs["completion_tokens"] == 20

    @pytest.mark.asyncio
    async def test_request_overrides_runtime_options_only(self):
        from core.content_engine.llm_client import llm_call_for_agent

        resolved = ResolvedModelConfig(
            workspace_id="workspace-1",
            workspace_slug="test-co",
            agent_key="content.brief_builder",
            model="anthropic/claude-sonnet-4-6",
            base_url="https://openrouter.test/api/v1",
            api_key="sk-or-workspace",
            credential_id="cred-1",
            temperature=0.2,
            max_tokens=1234,
        )
        mock_client = _mock_async_client(_mock_openai_response())

        with patch(
            "core.shared_tools.openrouter_client.build_async_client_for_key",
            return_value=mock_client,
        ), patch("core.content_engine.llm_client.track_llm_cost"):
            await llm_call_for_agent(
                workspace_id="workspace-1",
                workspace_slug="test-co",
                agent_key="content.brief_builder",
                system="sys",
                user="usr",
                max_tokens=99,
                temperature=0.7,
                resolver=FakeModelConfigResolver(resolved),  # type: ignore[arg-type]
            )

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["max_tokens"] == 99
        assert call_kwargs["temperature"] == 0.7

    @pytest.mark.asyncio
    async def test_retries_transient_failures(self):
        from core.content_engine.llm_client import llm_call_for_agent

        resolved = ResolvedModelConfig(
            workspace_id="workspace-1",
            workspace_slug="test-co",
            agent_key="content.brief_builder",
            model="anthropic/claude-sonnet-4-6",
            base_url="https://openrouter.test/api/v1",
            api_key="sk-or-workspace",
            credential_id="cred-1",
        )
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=[Exception("Transient"), _mock_openai_response(content="OK")]
        )

        with patch(
            "core.shared_tools.openrouter_client.build_async_client_for_key",
            return_value=mock_client,
        ), patch(
            "core.content_engine.llm_client.asyncio.sleep", new_callable=AsyncMock
        ), patch("core.content_engine.llm_client.track_llm_cost"):
            result = await llm_call_for_agent(
                workspace_id="workspace-1",
                workspace_slug="test-co",
                agent_key="content.brief_builder",
                system="sys",
                user="usr",
                resolver=FakeModelConfigResolver(resolved),  # type: ignore[arg-type]
                max_retries=2,
                base_delay=0.01,
            )

        assert result.content == "OK"
        assert mock_client.chat.completions.create.call_count == 2


# ═══════════════════════════════════════════════════════════════════════
# configure_openrouter / configure_litellm_callbacks (backward alias)
# ═══════════════════════════════════════════════════════════════════════


class TestConfigureOpenrouter:
    """Tests for configure_openrouter() and its backward-compatible alias."""

    def test_backward_compat_alias_exists(self):
        from core.content_engine.llm_client import (
            configure_litellm_callbacks,
            configure_openrouter,
        )
        assert configure_litellm_callbacks is configure_openrouter

    def test_succeeds_when_api_key_set(self):
        from core.content_engine.llm_client import configure_openrouter

        mock_client = MagicMock()
        with patch(
            "core.shared_tools.openrouter_client.get_async_client",
            return_value=mock_client,
        ):
            configure_openrouter()  # should not raise

    def test_warns_when_api_key_missing(self):
        from core.content_engine.llm_client import configure_openrouter

        with patch(
            "core.shared_tools.openrouter_client.get_async_client",
            side_effect=RuntimeError("OPENROUTER_API_KEY is not set"),
        ):
            # Should not raise — just log a warning
            configure_openrouter()
