"""Tests for core.checkpointer — shared LangGraph checkpointer factory.

Covers:
- MemorySaver fallback when no Redis URL
- RedisSaver returned when Redis URL is set
- Graceful fallback on RedisSaver init failure
- Explicit override bypasses factory
- Non-BaseCheckpointSaver override falls through to factory
- Singleton: RedisSaver created only once
- reset_checkpointer() clears singleton
- redis_checkpointer=False disables RedisSaver
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the checkpointer singleton before and after each test."""
    from core.checkpointer import reset_checkpointer

    reset_checkpointer()
    yield
    reset_checkpointer()


# ---------------------------------------------------------------------------
# 1. MemorySaver fallback when no Redis URL
# ---------------------------------------------------------------------------


class TestMemorySaverFallback:
    def test_returns_memory_saver_when_no_redis_url(self):
        with patch("core.checkpointer.settings") as mock_settings:
            mock_settings.redis_url = None
            mock_settings.redis_checkpointer = True

            from core.checkpointer import get_checkpointer

            result = get_checkpointer()
            assert isinstance(result, MemorySaver)


# ---------------------------------------------------------------------------
# 2. RedisSaver returned when Redis URL is set
# ---------------------------------------------------------------------------


class TestRedisSaverReturned:
    def test_returns_redis_saver_when_redis_url_set(self):
        mock_saver = MagicMock(spec=BaseCheckpointSaver)

        with (
            patch("core.checkpointer.settings") as mock_settings,
            patch("core.checkpointer._import_redis_saver") as mock_import,
        ):
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.redis_checkpointer = True
            mock_import.return_value = mock_saver

            from core.checkpointer import get_checkpointer

            result = get_checkpointer()
            assert result is mock_saver
            mock_import.assert_called_once()


# ---------------------------------------------------------------------------
# 3. Graceful fallback on RedisSaver init failure
# ---------------------------------------------------------------------------


class TestGracefulFallback:
    def test_fallback_on_redis_init_failure(self):
        with (
            patch("core.checkpointer.settings") as mock_settings,
            patch("core.checkpointer._import_redis_saver") as mock_import,
        ):
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.redis_checkpointer = True
            mock_import.side_effect = ConnectionError("Redis unavailable")

            from core.checkpointer import get_checkpointer

            result = get_checkpointer()
            assert isinstance(result, MemorySaver)


# ---------------------------------------------------------------------------
# 4. Explicit override bypasses factory
# ---------------------------------------------------------------------------


class TestOverride:
    def test_override_bypasses_redis(self):
        custom_cp = MagicMock(spec=BaseCheckpointSaver)

        from core.checkpointer import get_checkpointer

        result = get_checkpointer(override=custom_cp)
        assert result is custom_cp

    def test_override_with_non_saver_falls_through(self):
        """Non-BaseCheckpointSaver override falls through to factory."""
        from core.checkpointer import get_checkpointer

        result = get_checkpointer(override="not-a-saver")
        assert isinstance(result, BaseCheckpointSaver)


# ---------------------------------------------------------------------------
# 5. Singleton: RedisSaver created only once
# ---------------------------------------------------------------------------


class TestSingleton:
    def test_singleton_created_once(self):
        mock_saver = MagicMock(spec=BaseCheckpointSaver)

        with (
            patch("core.checkpointer.settings") as mock_settings,
            patch("core.checkpointer._import_redis_saver") as mock_import,
        ):
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.redis_checkpointer = True
            mock_import.return_value = mock_saver

            from core.checkpointer import get_checkpointer

            result1 = get_checkpointer()
            result2 = get_checkpointer()

            assert result1 is result2
            mock_import.assert_called_once()


# ---------------------------------------------------------------------------
# 6. reset_checkpointer() clears singleton
# ---------------------------------------------------------------------------


class TestReset:
    def test_reset_clears_singleton(self):
        mock_saver_1 = MagicMock(spec=BaseCheckpointSaver)
        mock_saver_2 = MagicMock(spec=BaseCheckpointSaver)

        with (
            patch("core.checkpointer.settings") as mock_settings,
            patch("core.checkpointer._import_redis_saver") as mock_import,
        ):
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.redis_checkpointer = True
            mock_import.return_value = mock_saver_1

            from core.checkpointer import get_checkpointer, reset_checkpointer

            result1 = get_checkpointer()
            assert result1 is mock_saver_1

            # Reset + change mock return
            reset_checkpointer()
            mock_import.return_value = mock_saver_2

            result2 = get_checkpointer()
            assert result2 is mock_saver_2
            assert mock_import.call_count == 2


# ---------------------------------------------------------------------------
# 7. redis_checkpointer=False disables RedisSaver
# ---------------------------------------------------------------------------


class TestConfigDisable:
    def test_disabled_via_config(self):
        with patch("core.checkpointer.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.redis_checkpointer = False

            from core.checkpointer import get_checkpointer

            result = get_checkpointer()
            assert isinstance(result, MemorySaver)
