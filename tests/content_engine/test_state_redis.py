"""Tests for core.content_engine.state_redis — Redis-backed pipeline state helpers."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from unittest.mock import MagicMock, AsyncMock, call, patch


# ── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def mock_sync_redis() -> MagicMock:
    """Mock sync redis.Redis client with pipeline support."""
    r = MagicMock()
    # Pipeline context manager returns self for chaining
    pipe = MagicMock()
    pipe.__enter__ = MagicMock(return_value=pipe)
    pipe.__exit__ = MagicMock(return_value=False)
    pipe.execute = MagicMock(return_value=[True])
    r.pipeline = MagicMock(return_value=pipe)
    r.hgetall = MagicMock(return_value={})
    r.hdel = MagicMock(return_value=0)
    r.delete = MagicMock(return_value=1)
    return r


@pytest.fixture
def mock_async_redis() -> AsyncMock:
    """Mock async redis.asyncio.Redis client."""
    r = AsyncMock()
    r.hgetall = AsyncMock(return_value={})
    return r


# ── Write tests ────────────────────────────────────────────────────


class TestWritePipelineStateRedis:
    def test_sets_hash_fields_for_each_brief(self, mock_sync_redis: MagicMock) -> None:
        """HSET called for each brief_id with the phase value."""
        from core.content_engine.state_redis import write_pipeline_state_redis

        write_pipeline_state_redis(
            mock_sync_redis, "ramp", ["brief-001", "brief-002"], "generating"
        )

        pipe = mock_sync_redis.pipeline.return_value
        # Verify hset calls for both briefs
        hset_calls = [c for c in pipe.method_calls if c[0] == "hset"]
        assert len(hset_calls) >= 2
        # Check fields set
        field_values = {c[2].get("key", c[1][0]) if c[2] else c[1][0]: c for c in hset_calls}
        # All calls should target pipeline_state:ramp
        for c in hset_calls:
            assert c[1][0] == "pipeline_state:ramp" or c[2].get("name") == "pipeline_state:ramp"

    def test_stores_task_id_mapping_with_tid_prefix(self, mock_sync_redis: MagicMock) -> None:
        """HSET stores __tid:{brief_id} = task_id when task_id provided."""
        from core.content_engine.state_redis import write_pipeline_state_redis

        write_pipeline_state_redis(
            mock_sync_redis, "ramp", ["brief-001"], "generating", task_id="task-abc"
        )

        pipe = mock_sync_redis.pipeline.return_value
        # Find the __tid: hset call
        all_calls = str(pipe.method_calls)
        assert "__tid:brief-001" in all_calls
        assert "task-abc" in all_calls

    def test_skips_task_id_when_none(self, mock_sync_redis: MagicMock) -> None:
        """No __tid: fields written when task_id is None."""
        from core.content_engine.state_redis import write_pipeline_state_redis

        write_pipeline_state_redis(
            mock_sync_redis, "ramp", ["brief-001"], "generating"
        )

        pipe = mock_sync_redis.pipeline.return_value
        all_calls = str(pipe.method_calls)
        assert "__tid:" not in all_calls

    def test_refreshes_ttl_on_every_write(self, mock_sync_redis: MagicMock) -> None:
        """EXPIRE called with 86400 after HSET."""
        from core.content_engine.state_redis import write_pipeline_state_redis

        write_pipeline_state_redis(
            mock_sync_redis, "ramp", ["brief-001"], "generating"
        )

        pipe = mock_sync_redis.pipeline.return_value
        expire_calls = [c for c in pipe.method_calls if c[0] == "expire"]
        assert len(expire_calls) >= 1
        # Verify TTL value
        assert expire_calls[0][1] == ("pipeline_state:ramp", 86400)

    def test_validates_phase_against_enum(self, mock_sync_redis: MagicMock) -> None:
        """Unknown phase still writes (with warning log), matching file-based behavior."""
        from core.content_engine.state_redis import write_pipeline_state_redis

        # Should not raise — just log warning
        write_pipeline_state_redis(
            mock_sync_redis, "ramp", ["brief-001"], "unknown_phase"
        )

        # Should still write (matching file-based behavior)
        pipe = mock_sync_redis.pipeline.return_value
        pipe.execute.assert_called_once()

    def test_uses_pipeline_for_atomicity(self, mock_sync_redis: MagicMock) -> None:
        """All HSET + EXPIRE wrapped in a redis pipeline() context manager."""
        from core.content_engine.state_redis import write_pipeline_state_redis

        write_pipeline_state_redis(
            mock_sync_redis, "ramp", ["brief-001", "brief-002"], "generating"
        )

        mock_sync_redis.pipeline.assert_called_once()
        pipe = mock_sync_redis.pipeline.return_value
        pipe.execute.assert_called_once()


# ── Cleanup tests ──────────────────────────────────────────────────


class TestCleanupPipelineStateRedis:
    def test_removes_brief_and_tid_fields(self, mock_sync_redis: MagicMock) -> None:
        """HDEL called with brief_id and __tid:{brief_id} for each brief."""
        from core.content_engine.state_redis import cleanup_pipeline_state_redis

        cleanup_pipeline_state_redis(mock_sync_redis, "ramp", ["brief-001", "brief-002"])

        mock_sync_redis.hdel.assert_called_once()
        args = mock_sync_redis.hdel.call_args[0]
        assert args[0] == "pipeline_state:ramp"
        field_set = set(args[1:])
        assert "brief-001" in field_set
        assert "brief-002" in field_set
        assert "__tid:brief-001" in field_set
        assert "__tid:brief-002" in field_set

    def test_handles_empty_brief_ids(self, mock_sync_redis: MagicMock) -> None:
        """Empty list does not call HDEL."""
        from core.content_engine.state_redis import cleanup_pipeline_state_redis

        cleanup_pipeline_state_redis(mock_sync_redis, "ramp", [])

        mock_sync_redis.hdel.assert_not_called()


# ── Read tests ─────────────────────────────────────────────────────


class TestReadPipelineStateRedis:
    def test_reconstructs_task_ids_dict(self, mock_sync_redis: MagicMock) -> None:
        """HGETALL flat fields → reconstructed __task_ids__ nested dict."""
        from core.content_engine.state_redis import read_pipeline_state_redis

        mock_sync_redis.hgetall.return_value = {
            "brief-001": "generating",
            "brief-002": "evaluating",
            "__tid:brief-001": "task-abc",
            "__tid:brief-002": "task-def",
        }

        result = read_pipeline_state_redis(mock_sync_redis, "ramp")

        assert result["brief-001"] == "generating"
        assert result["brief-002"] == "evaluating"
        assert result["__task_ids__"] == {
            "brief-001": "task-abc",
            "brief-002": "task-def",
        }
        # __tid: fields should NOT appear as top-level keys
        assert "__tid:brief-001" not in result
        assert "__tid:brief-002" not in result

    def test_returns_empty_dict_when_key_missing(self, mock_sync_redis: MagicMock) -> None:
        """Returns {} when Redis key does not exist."""
        from core.content_engine.state_redis import read_pipeline_state_redis

        mock_sync_redis.hgetall.return_value = {}

        result = read_pipeline_state_redis(mock_sync_redis, "ramp")
        assert result == {}

    def test_handles_no_tid_fields(self, mock_sync_redis: MagicMock) -> None:
        """Returns dict without __task_ids__ when no __tid: fields present."""
        from core.content_engine.state_redis import read_pipeline_state_redis

        mock_sync_redis.hgetall.return_value = {
            "brief-001": "generating",
        }

        result = read_pipeline_state_redis(mock_sync_redis, "ramp")
        assert result == {"brief-001": "generating"}
        assert "__task_ids__" not in result


class TestReadPipelineStateRedisAsync:
    @pytest.mark.asyncio
    async def test_reconstructs_task_ids_dict_async(self, mock_async_redis: AsyncMock) -> None:
        """Async version reconstructs __task_ids__ from __tid: fields."""
        from core.content_engine.state_redis import read_pipeline_state_redis_async

        mock_async_redis.hgetall.return_value = {
            "brief-001": "generating",
            "__tid:brief-001": "task-abc",
        }

        result = await read_pipeline_state_redis_async(mock_async_redis, "ramp")

        assert result["brief-001"] == "generating"
        assert result["__task_ids__"] == {"brief-001": "task-abc"}


# ── Stale cleanup tests ───────────────────────────────────────────


class TestCleanupStalePipelineStateRedis:
    def test_skips_cleanup_when_no_task_id(self, mock_sync_redis: MagicMock) -> None:
        """No task_id → logs warning and skips (no DELETE, no HDEL)."""
        from core.content_engine.state_redis import cleanup_stale_pipeline_state_redis

        cleanup_stale_pipeline_state_redis(mock_sync_redis, "ramp")

        # Must NOT delete the entire key (would clobber other runs)
        mock_sync_redis.delete.assert_not_called()
        mock_sync_redis.hdel.assert_not_called()

    def test_task_scoped_cleanup_only_removes_own_briefs(self, mock_sync_redis: MagicMock) -> None:
        """With task_id, only removes briefs belonging to that task."""
        from core.content_engine.state_redis import cleanup_stale_pipeline_state_redis

        mock_sync_redis.hgetall.return_value = {
            "brief-001": "generating",
            "brief-002": "evaluating",
            "__tid:brief-001": "task-abc",  # belongs to failing task
            "__tid:brief-002": "task-other",  # belongs to another run
        }

        cleanup_stale_pipeline_state_redis(mock_sync_redis, "ramp", task_id="task-abc")

        # Should HDEL only brief-001 and __tid:brief-001
        mock_sync_redis.hdel.assert_called_once()
        deleted_fields = set(mock_sync_redis.hdel.call_args[0][1:])
        assert "brief-001" in deleted_fields
        assert "__tid:brief-001" in deleted_fields
        assert "brief-002" not in deleted_fields
        assert "__tid:brief-002" not in deleted_fields
        # Should NOT delete entire key
        mock_sync_redis.delete.assert_not_called()

    def test_task_scoped_cleanup_noop_when_no_matching_briefs(self, mock_sync_redis: MagicMock) -> None:
        """No deletion when no briefs match the task_id."""
        from core.content_engine.state_redis import cleanup_stale_pipeline_state_redis

        mock_sync_redis.hgetall.return_value = {
            "brief-001": "generating",
            "__tid:brief-001": "task-other",
        }

        cleanup_stale_pipeline_state_redis(mock_sync_redis, "ramp", task_id="task-abc")

        mock_sync_redis.hdel.assert_not_called()
        mock_sync_redis.delete.assert_not_called()


# ── Lock TTL refresh tests ────────────────────────────────────────


class TestLockTTLRefresh:
    @pytest.mark.asyncio
    async def test_write_async_refreshes_lock_ttl(self, tmp_path: Path) -> None:
        """_write_pipeline_state_async refreshes lock:content_v13:{slug} TTL."""
        from core.content_engine.state_helpers import _write_pipeline_state_async

        mock_redis = AsyncMock()
        mock_redis.expire = AsyncMock()

        # Patch the inner async write to succeed, so we reach the lock refresh
        with patch(
            "core.content_engine.state_redis.write_pipeline_state_redis_async",
            new_callable=AsyncMock,
        ):
            await _write_pipeline_state_async(
                tmp_path, ["brief-001"], "generating",
                task_id="task-abc",
                redis_client=mock_redis,
                effective_slug="ramp",
            )

        # Lock TTL should be refreshed after successful Redis write
        mock_redis.expire.assert_awaited_once_with(
            "lock:content_v13:ramp", 7200
        )


# ── Read fallback tests ───────────────────────────────────────────


class TestReadFallback:
    def test_consults_file_when_redis_returns_empty(self, tmp_path: Path, mock_sync_redis: MagicMock) -> None:
        """When Redis returns {}, file is consulted (migration window)."""
        # Redis returns empty
        mock_sync_redis.hgetall.return_value = {}

        # File has data — must match the path _load_pipeline_state constructs:
        # artifacts_root / "content" / slug / "pipeline_state.json"
        state_dir = tmp_path / "content" / "ramp"
        state_dir.mkdir(parents=True)
        (state_dir / "pipeline_state.json").write_text(
            json.dumps({"brief-001": "generating"})
        )

        with patch("core.config.settings.settings") as mock_cfg:
            mock_cfg.redis_pipeline_state = True
            mock_cfg.redis_url = "redis://localhost:6379/0"
            with patch("api.services.content_data_service.get_sync_redis_or_none", return_value=mock_sync_redis):
                from api.services.content_data_service import _load_pipeline_state
                result = _load_pipeline_state(tmp_path, "ramp")

        assert result.get("brief-001") == "generating"


# ── state_helpers.py integration tests ─────────────────────────────


class TestWritePipelineStateIntegration:
    def test_uses_redis_and_writes_file(
        self, tmp_path: Path, mock_sync_redis: MagicMock
    ) -> None:
        """Calls write_pipeline_state_redis AND writes file (dual-write)."""
        from core.content_engine.state_helpers import _write_pipeline_state

        _write_pipeline_state(
            tmp_path, ["brief-001"], "generating",
            task_id="task-abc",
            redis_client=mock_sync_redis,
            effective_slug="ramp",
        )

        # Redis pipeline was used
        mock_sync_redis.pipeline.assert_called_once()
        # File ALSO written (dual-write for fallback resilience)
        assert (tmp_path / "pipeline_state.json").exists()

    def test_falls_back_to_file_when_redis_raises(
        self, tmp_path: Path, mock_sync_redis: MagicMock
    ) -> None:
        """Redis raises ConnectionError; file written as fallback."""
        mock_sync_redis.pipeline.side_effect = ConnectionError("Redis down")

        from core.content_engine.state_helpers import _write_pipeline_state

        _write_pipeline_state(
            tmp_path, ["brief-001"], "generating",
            redis_client=mock_sync_redis,
            effective_slug="ramp",
        )

        # File should be written as fallback
        state_path = tmp_path / "pipeline_state.json"
        assert state_path.exists()
        data = json.loads(state_path.read_text())
        assert data["brief-001"] == "generating"

    def test_falls_back_to_file_when_redis_client_is_none(
        self, tmp_path: Path
    ) -> None:
        """redis_client=None → existing file-based behavior unchanged."""
        from core.content_engine.state_helpers import _write_pipeline_state

        _write_pipeline_state(tmp_path, ["brief-001"], "generating")

        state_path = tmp_path / "pipeline_state.json"
        assert state_path.exists()
        data = json.loads(state_path.read_text())
        assert data["brief-001"] == "generating"

    def test_falls_back_to_file_when_slug_is_none(
        self, tmp_path: Path, mock_sync_redis: MagicMock
    ) -> None:
        """effective_slug=None → file-based fallback."""
        from core.content_engine.state_helpers import _write_pipeline_state

        _write_pipeline_state(
            tmp_path, ["brief-001"], "generating",
            redis_client=mock_sync_redis,
            effective_slug=None,
        )

        assert (tmp_path / "pipeline_state.json").exists()


class TestCleanupPipelineStateIntegration:
    def test_uses_redis_when_client_and_slug_provided(
        self, tmp_path: Path, mock_sync_redis: MagicMock
    ) -> None:
        """Calls cleanup_pipeline_state_redis + file cleanup."""
        # Create a file to verify file cleanup also runs
        state_path = tmp_path / "pipeline_state.json"
        state_path.write_text(json.dumps({"brief-001": "generating"}))

        from core.content_engine.state_helpers import _cleanup_pipeline_state

        _cleanup_pipeline_state(
            tmp_path, ["brief-001"],
            redis_client=mock_sync_redis,
            effective_slug="ramp",
        )

        # Redis HDEL was called
        mock_sync_redis.hdel.assert_called_once()
        # File was also cleaned (dual cleanup for safety)
        assert not state_path.exists()

    def test_falls_back_to_file_when_redis_raises(
        self, tmp_path: Path, mock_sync_redis: MagicMock
    ) -> None:
        """Redis raises; file cleanup runs instead."""
        mock_sync_redis.hdel.side_effect = ConnectionError("Redis down")

        state_path = tmp_path / "pipeline_state.json"
        state_path.write_text(json.dumps({"brief-001": "generating"}))

        from core.content_engine.state_helpers import _cleanup_pipeline_state

        _cleanup_pipeline_state(
            tmp_path, ["brief-001"],
            redis_client=mock_sync_redis,
            effective_slug="ramp",
        )

        # File should be cleaned up as fallback
        assert not state_path.exists()
