"""Unit tests for core.redis module."""
from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.fixture(autouse=True)
def _reset_redis_module():
    """Reset module-level singletons between tests."""
    import core.redis as redis_mod

    redis_mod._client = None
    redis_mod._pool = None
    redis_mod._sync_client = None
    yield
    redis_mod._client = None
    redis_mod._pool = None
    redis_mod._sync_client = None


class TestGetRedis:
    def test_raises_without_url(self) -> None:
        """get_redis() raises RuntimeError when REDIS_URL is not set."""
        with patch("core.redis.settings") as mock_settings:
            mock_settings.redis_url = None
            from core.redis import get_redis

            with pytest.raises(RuntimeError, match="REDIS_URL is not set"):
                get_redis()

    def test_creates_client_with_url(self) -> None:
        """get_redis() creates a Redis client when REDIS_URL is configured."""
        with patch("core.redis.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.redis_max_connections = 20
            mock_settings.redis_socket_timeout = 5.0
            mock_settings.redis_socket_connect_timeout = 2.0
            mock_settings.redis_retry_on_timeout = True
            mock_settings.redis_health_check_interval = 30

            mock_pool = MagicMock()
            with patch(
                "core.redis.aioredis.ConnectionPool.from_url",
                return_value=mock_pool,
            ):
                from core.redis import get_redis

                client = get_redis()
                assert client is not None

    def test_returns_singleton(self) -> None:
        """get_redis() returns the same instance on subsequent calls."""
        with patch("core.redis.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.redis_max_connections = 20
            mock_settings.redis_socket_timeout = 5.0
            mock_settings.redis_socket_connect_timeout = 2.0
            mock_settings.redis_retry_on_timeout = True
            mock_settings.redis_health_check_interval = 30

            mock_pool = MagicMock()
            with patch(
                "core.redis.aioredis.ConnectionPool.from_url",
                return_value=mock_pool,
            ):
                from core.redis import get_redis

                first = get_redis()
                second = get_redis()
                assert first is second


class TestGetRedisOrNone:
    def test_returns_none_without_url(self) -> None:
        """get_redis_or_none() returns None gracefully."""
        with patch("core.redis.settings") as mock_settings:
            mock_settings.redis_url = None
            from core.redis import get_redis_or_none

            assert get_redis_or_none() is None

    def test_returns_none_on_value_error(self) -> None:
        """Malformed URL (ValueError) returns None, not crash."""
        with patch("core.redis.settings") as mock_settings:
            mock_settings.redis_url = "redis://bad:port:here"
            with patch(
                "core.redis.aioredis.ConnectionPool.from_url",
                side_effect=ValueError("Invalid URL"),
            ):
                from core.redis import get_redis_or_none

                assert get_redis_or_none() is None

    def test_returns_none_on_connection_error(self) -> None:
        """Connection refused (redis.ConnectionError) returns None, not crash."""
        import redis

        with patch("core.redis.settings") as mock_settings:
            mock_settings.redis_url = "redis://unreachable:6379/0"
            with patch(
                "core.redis.aioredis.ConnectionPool.from_url",
                side_effect=redis.ConnectionError("Connection refused"),
            ):
                from core.redis import get_redis_or_none

                assert get_redis_or_none() is None


class TestRedisPing:
    @pytest.mark.asyncio
    async def test_returns_false_on_failure(self) -> None:
        """redis_ping() returns False when Redis is unreachable."""
        with patch("core.redis.get_redis") as mock_get:
            mock_client = AsyncMock()
            mock_client.ping.side_effect = ConnectionError("refused")
            mock_get.return_value = mock_client
            from core.redis import redis_ping

            assert await redis_ping() is False


class TestCloseRedis:
    @pytest.mark.asyncio
    async def test_resets_state(self) -> None:
        """close_redis() resets module-level globals to None."""
        import core.redis as redis_mod

        # Simulate initialized state
        redis_mod._client = AsyncMock()
        redis_mod._pool = AsyncMock()

        from core.redis import close_redis

        await close_redis()

        assert redis_mod._client is None
        assert redis_mod._pool is None

    @pytest.mark.asyncio
    async def test_idempotent(self) -> None:
        """close_redis() can be called twice without error."""
        from core.redis import close_redis

        # Both calls with None globals should succeed
        await close_redis()
        await close_redis()


class TestCloseRedisErrorIsolation:
    @pytest.mark.asyncio
    async def test_pool_closes_when_client_fails(self) -> None:
        """If client.aclose() raises, pool.aclose() still runs."""
        import core.redis as redis_mod

        mock_client = AsyncMock()
        mock_client.aclose.side_effect = ConnectionError("client close failed")
        mock_pool = AsyncMock()

        redis_mod._client = mock_client
        redis_mod._pool = mock_pool

        from core.redis import close_redis

        await close_redis()

        mock_pool.aclose.assert_awaited_once()
        assert redis_mod._client is None
        assert redis_mod._pool is None

    @pytest.mark.asyncio
    async def test_sync_closes_when_async_fails(self) -> None:
        """If both async closes fail, sync.close() still runs."""
        import core.redis as redis_mod

        mock_client = AsyncMock()
        mock_client.aclose.side_effect = ConnectionError("fail")
        mock_pool = AsyncMock()
        mock_pool.aclose.side_effect = ConnectionError("fail")
        mock_sync = MagicMock()

        redis_mod._client = mock_client
        redis_mod._pool = mock_pool
        redis_mod._sync_client = mock_sync

        from core.redis import close_redis

        await close_redis()

        mock_sync.close.assert_called_once()
        assert redis_mod._sync_client is None


class TestRedactUrl:
    def test_redacts_password(self) -> None:
        """_redact_url masks password in Redis URL."""
        from core.redis import _redact_url

        result = _redact_url("redis://user:s3cret@myhost:6379/0")
        assert "s3cret" not in result
        assert "myhost" in result
        assert "***" in result

    def test_no_password_unchanged(self) -> None:
        """_redact_url returns URL unchanged when no password."""
        from core.redis import _redact_url

        url = "redis://localhost:6379/0"
        assert _redact_url(url) == url


class TestGetSyncRedis:
    def test_raises_without_url(self) -> None:
        """get_sync_redis() raises RuntimeError when REDIS_URL not set."""
        with patch("core.redis.settings") as mock_settings:
            mock_settings.redis_url = None
            from core.redis import get_sync_redis

            with pytest.raises(RuntimeError, match="REDIS_URL is not set"):
                get_sync_redis()

    def test_creates_sync_client_with_url(self) -> None:
        """get_sync_redis() creates a sync redis.Redis client with settings."""
        with patch("core.redis.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.redis_socket_timeout = 5.0
            mock_settings.redis_socket_connect_timeout = 2.0

            mock_client = MagicMock()
            with patch(
                "core.redis._sync_redis.from_url",
                return_value=mock_client,
            ) as mock_from_url:
                from core.redis import get_sync_redis

                client = get_sync_redis()
                assert client is mock_client
                mock_from_url.assert_called_once_with(
                    "redis://localhost:6379/0",
                    decode_responses=True,
                    socket_timeout=5.0,
                    socket_connect_timeout=2.0,
                )

    def test_returns_singleton(self) -> None:
        """get_sync_redis() returns the same instance on subsequent calls."""
        with patch("core.redis.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379/0"

            mock_client = MagicMock()
            with patch(
                "core.redis._sync_redis.from_url",
                return_value=mock_client,
            ):
                from core.redis import get_sync_redis

                first = get_sync_redis()
                second = get_sync_redis()
                assert first is second


class TestGetSyncRedisOrNone:
    def test_returns_none_without_url(self) -> None:
        """get_sync_redis_or_none() returns None gracefully."""
        with patch("core.redis.settings") as mock_settings:
            mock_settings.redis_url = None
            from core.redis import get_sync_redis_or_none

            assert get_sync_redis_or_none() is None

    def test_returns_none_on_value_error(self) -> None:
        """Malformed URL (ValueError) returns None, not crash."""
        with patch("core.redis.settings") as mock_settings:
            mock_settings.redis_url = "redis://bad:port:here"
            with patch(
                "core.redis._sync_redis.from_url",
                side_effect=ValueError("Invalid URL"),
            ):
                from core.redis import get_sync_redis_or_none

                assert get_sync_redis_or_none() is None

    def test_returns_none_on_connection_error(self) -> None:
        """Connection refused (redis.ConnectionError) returns None, not crash."""
        import redis

        with patch("core.redis.settings") as mock_settings:
            mock_settings.redis_url = "redis://unreachable:6379/0"
            with patch(
                "core.redis._sync_redis.from_url",
                side_effect=redis.ConnectionError("Connection refused"),
            ):
                from core.redis import get_sync_redis_or_none

                assert get_sync_redis_or_none() is None
