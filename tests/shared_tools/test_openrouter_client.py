"""Tests for core.shared_tools.openrouter_client — shared OpenRouter client factory."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from openai import AsyncOpenAI, OpenAI

from core.shared_tools import openrouter_client


@pytest.fixture(autouse=True)
def _reset_clients():
    """Ensure singleton state doesn't leak between tests."""
    openrouter_client.reset_clients()
    yield
    openrouter_client.reset_clients()


class TestGetAsyncClient:
    def test_returns_async_openai_instance(self):
        with patch.object(openrouter_client, "_get_settings") as mock_settings:
            mock_settings.return_value.openrouter_api_key = "sk-or-test"
            mock_settings.return_value.openrouter_base_url = "https://openrouter.ai/api/v1"

            client = openrouter_client.get_async_client()

            assert isinstance(client, AsyncOpenAI)

    def test_raises_without_api_key(self):
        with patch.object(openrouter_client, "_get_settings") as mock_settings:
            mock_settings.return_value.openrouter_api_key = None

            with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY is not set"):
                openrouter_client.get_async_client()

    def test_caches_client(self):
        with patch.object(openrouter_client, "_get_settings") as mock_settings:
            mock_settings.return_value.openrouter_api_key = "sk-or-test"
            mock_settings.return_value.openrouter_base_url = "https://openrouter.ai/api/v1"

            client1 = openrouter_client.get_async_client()
            client2 = openrouter_client.get_async_client()

            assert client1 is client2

    def test_max_retries_zero(self):
        with patch.object(openrouter_client, "_get_settings") as mock_settings:
            mock_settings.return_value.openrouter_api_key = "sk-or-test"
            mock_settings.return_value.openrouter_base_url = "https://openrouter.ai/api/v1"

            client = openrouter_client.get_async_client()

            assert client.max_retries == 0


class TestGetSyncClient:
    def test_returns_sync_openai_instance(self):
        with patch.object(openrouter_client, "_get_settings") as mock_settings:
            mock_settings.return_value.openrouter_api_key = "sk-or-test"
            mock_settings.return_value.openrouter_base_url = "https://openrouter.ai/api/v1"

            client = openrouter_client.get_sync_client()

            assert isinstance(client, OpenAI)

    def test_raises_without_api_key(self):
        with patch.object(openrouter_client, "_get_settings") as mock_settings:
            mock_settings.return_value.openrouter_api_key = None

            with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY is not set"):
                openrouter_client.get_sync_client()

    def test_caches_client(self):
        with patch.object(openrouter_client, "_get_settings") as mock_settings:
            mock_settings.return_value.openrouter_api_key = "sk-or-test"
            mock_settings.return_value.openrouter_base_url = "https://openrouter.ai/api/v1"

            client1 = openrouter_client.get_sync_client()
            client2 = openrouter_client.get_sync_client()

            assert client1 is client2

    def test_max_retries_zero(self):
        with patch.object(openrouter_client, "_get_settings") as mock_settings:
            mock_settings.return_value.openrouter_api_key = "sk-or-test"
            mock_settings.return_value.openrouter_base_url = "https://openrouter.ai/api/v1"

            client = openrouter_client.get_sync_client()

            assert client.max_retries == 0


class TestBuildClientsForKey:
    def test_async_client_for_key_uses_supplied_key_without_cache(self):
        with patch.object(openrouter_client, "AsyncOpenAI") as mock_ctor:
            with patch.object(openrouter_client, "_get_settings") as mock_settings:
                mock_settings.return_value.openrouter_base_url = "https://settings.example/v1"

                first = openrouter_client.build_async_client_for_key("sk-or-workspace-1")
                second = openrouter_client.build_async_client_for_key(
                    "sk-or-workspace-2",
                    base_url="https://custom.example/v1",
                    timeout_s=12.0,
                )

        assert first is mock_ctor.return_value
        assert second is mock_ctor.return_value
        assert mock_ctor.call_args_list[0].kwargs == {
            "base_url": "https://settings.example/v1",
            "api_key": "sk-or-workspace-1",
            "max_retries": 0,
        }
        assert mock_ctor.call_args_list[1].kwargs == {
            "base_url": "https://custom.example/v1",
            "api_key": "sk-or-workspace-2",
            "max_retries": 0,
            "timeout": 12.0,
        }

    def test_sync_client_for_key_uses_supplied_key_without_cache(self):
        with patch.object(openrouter_client, "OpenAI") as mock_ctor:
            with patch.object(openrouter_client, "_get_settings") as mock_settings:
                mock_settings.return_value.openrouter_base_url = "https://settings.example/v1"

                openrouter_client.build_sync_client_for_key("sk-or-workspace")

        mock_ctor.assert_called_once_with(
            base_url="https://settings.example/v1",
            api_key="sk-or-workspace",
            max_retries=0,
        )


class TestResetClients:
    def test_clears_cached_clients(self):
        with patch.object(openrouter_client, "_get_settings") as mock_settings:
            mock_settings.return_value.openrouter_api_key = "sk-or-test"
            mock_settings.return_value.openrouter_base_url = "https://openrouter.ai/api/v1"

            client1 = openrouter_client.get_async_client()
            openrouter_client.reset_clients()
            client2 = openrouter_client.get_async_client()

            assert client1 is not client2


class TestBuildChatOpenAIViaOpenRouter:
    """Tests for build_chat_openai_via_openrouter() — LangChain ChatOpenAI factory."""

    def test_returns_chat_openai_instance(self):
        from langchain_openai import ChatOpenAI

        with patch.object(openrouter_client, "_get_settings") as mock_settings:
            mock_settings.return_value.openrouter_api_key = "sk-or-test"
            mock_settings.return_value.openrouter_base_url = "https://openrouter.ai/api/v1"

            model = openrouter_client.build_chat_openai_via_openrouter("anthropic/claude-opus-4-6")

            assert isinstance(model, ChatOpenAI)

    def test_sets_base_url_from_settings(self):
        with patch.object(openrouter_client, "_get_settings") as mock_settings:
            mock_settings.return_value.openrouter_api_key = "sk-or-test"
            mock_settings.return_value.openrouter_base_url = "https://custom.example.com/v1"

            model = openrouter_client.build_chat_openai_via_openrouter("anthropic/claude-opus-4-6")

            assert str(model.openai_api_base) == "https://custom.example.com/v1"

    def test_sets_api_key_from_settings(self):
        with patch.object(openrouter_client, "_get_settings") as mock_settings:
            mock_settings.return_value.openrouter_api_key = "sk-or-key-123"
            mock_settings.return_value.openrouter_base_url = "https://openrouter.ai/api/v1"

            model = openrouter_client.build_chat_openai_via_openrouter("anthropic/claude-opus-4-6")

            assert model.openai_api_key.get_secret_value() == "sk-or-key-123"

    def test_applies_model_prefix(self):
        with patch.object(openrouter_client, "_get_settings") as mock_settings:
            mock_settings.return_value.openrouter_api_key = "sk-or-test"
            mock_settings.return_value.openrouter_base_url = "https://openrouter.ai/api/v1"

            model = openrouter_client.build_chat_openai_via_openrouter("claude-opus-4-6")

            assert model.model_name == "anthropic/claude-opus-4-6"

    def test_handles_colon_format(self):
        """Legacy KB synthesis format: 'anthropic:claude-opus-4-6'."""
        with patch.object(openrouter_client, "_get_settings") as mock_settings:
            mock_settings.return_value.openrouter_api_key = "sk-or-test"
            mock_settings.return_value.openrouter_base_url = "https://openrouter.ai/api/v1"

            model = openrouter_client.build_chat_openai_via_openrouter("anthropic:claude-opus-4-6")

            assert model.model_name == "anthropic/claude-opus-4-6"

    def test_passes_already_prefixed(self):
        with patch.object(openrouter_client, "_get_settings") as mock_settings:
            mock_settings.return_value.openrouter_api_key = "sk-or-test"
            mock_settings.return_value.openrouter_base_url = "https://openrouter.ai/api/v1"

            model = openrouter_client.build_chat_openai_via_openrouter("anthropic/claude-opus-4-6")

            assert model.model_name == "anthropic/claude-opus-4-6"

    def test_raises_without_api_key(self):
        with patch.object(openrouter_client, "_get_settings") as mock_settings:
            mock_settings.return_value.openrouter_api_key = None

            with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY is not set"):
                openrouter_client.build_chat_openai_via_openrouter("anthropic/claude-opus-4-6")

    def test_passes_kwargs_through(self):
        with patch.object(openrouter_client, "_get_settings") as mock_settings:
            mock_settings.return_value.openrouter_api_key = "sk-or-test"
            mock_settings.return_value.openrouter_base_url = "https://openrouter.ai/api/v1"

            model = openrouter_client.build_chat_openai_via_openrouter(
                "anthropic/claude-opus-4-6", temperature=0.5,
            )

            assert model.temperature == 0.5
