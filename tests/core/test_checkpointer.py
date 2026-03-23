"""Tests for the shared checkpointer factory (core/checkpointer.py).

Tests the config-driven factory: override → RedisSaver → MemorySaver fallback.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

import core.checkpointer as checkpointer_mod
from core.checkpointer import get_checkpointer


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset module-level singleton before each test."""
    checkpointer_mod._singleton = None
    yield
    checkpointer_mod._singleton = None


class TestCheckpointerFactory:
    def test_override_with_valid_saver(self):
        """Passing a BaseCheckpointSaver as override returns it directly."""
        custom = MemorySaver()
        result = get_checkpointer(override=custom)
        assert result is custom

    def test_override_with_non_saver_falls_through(self):
        """Non-BaseCheckpointSaver override falls through to factory."""
        result = get_checkpointer(override="not-a-saver")
        assert isinstance(result, BaseCheckpointSaver)

    def test_fallback_to_memory_saver_without_redis(self):
        """No redis_url → MemorySaver."""
        mock_settings = MagicMock()
        mock_settings.redis_checkpointer = False
        mock_settings.redis_url = None

        with patch("core.config.settings.settings", mock_settings):
            result = get_checkpointer()

        assert isinstance(result, MemorySaver)

    def test_singleton_caching(self):
        """Repeated calls return same instance."""
        mock_settings = MagicMock()
        mock_settings.redis_checkpointer = False
        mock_settings.redis_url = None

        with patch("core.config.settings.settings", mock_settings):
            r1 = get_checkpointer()
            r2 = get_checkpointer()

        assert r1 is r2

    def test_redis_import_failure_falls_back(self):
        """If RedisSaver import/init fails, falls back to MemorySaver."""
        mock_settings = MagicMock()
        mock_settings.redis_checkpointer = True
        mock_settings.redis_url = "redis://localhost:6379"

        with patch("core.config.settings.settings", mock_settings):
            result = get_checkpointer()

        # Without a real Redis, RedisSaver init will fail → MemorySaver
        assert isinstance(result, MemorySaver)
