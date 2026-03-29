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


class TestResetClients:
    def test_clears_cached_clients(self):
        with patch.object(openrouter_client, "_get_settings") as mock_settings:
            mock_settings.return_value.openrouter_api_key = "sk-or-test"
            mock_settings.return_value.openrouter_base_url = "https://openrouter.ai/api/v1"

            client1 = openrouter_client.get_async_client()
            openrouter_client.reset_clients()
            client2 = openrouter_client.get_async_client()

            assert client1 is not client2
