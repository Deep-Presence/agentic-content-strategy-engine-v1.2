"""Tests for core.content_engine.state_helpers — SSE emission from pipeline state writes.

Validates that _write_pipeline_state_async emits company-wide SSE events
so the frontend Kanban updates immediately at every worker transition.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def mock_async_redis() -> AsyncMock:
    """Mock async redis.asyncio.Redis client."""
    r = AsyncMock()
    r.expire = AsyncMock()
    return r


@pytest.fixture
def tmp_artifact_dir(tmp_path: Path) -> Path:
    d = tmp_path / "content" / "acme"
    d.mkdir(parents=True)
    return d


# ── Async write + SSE emission tests ──────────────────────────────


class TestWritePipelineStateAsyncEmitsSSE:
    """_write_pipeline_state_async must emit state_changed after every write."""

    @pytest.mark.asyncio
    async def test_emits_state_changed(
        self, mock_async_redis: AsyncMock, tmp_artifact_dir: Path
    ) -> None:
        """After writing state, _emit_company is called with state_changed."""
        with patch(
            "core.content_engine.state_helpers._emit_company"
        ) as mock_emit, patch(
            "core.content_engine.state_redis.write_pipeline_state_redis_async",
            new_callable=AsyncMock,
        ):
            from core.content_engine.state_helpers import _write_pipeline_state_async

            await _write_pipeline_state_async(
                tmp_artifact_dir,
                ["brief-001"],
                "outlining",
                task_id="task-1",
                redis_client=mock_async_redis,
                effective_slug="acme",
            )

            mock_emit.assert_called_once_with(
                "acme",
                "state_changed",
                {"changed": ["brief-001"], "hint": "outlining"},
            )

    @pytest.mark.asyncio
    async def test_extracts_company_from_compound_slug(
        self, mock_async_redis: AsyncMock, tmp_artifact_dir: Path
    ) -> None:
        """effective_slug='acme__widget' → company_slug='acme'."""
        with patch(
            "core.content_engine.state_helpers._emit_company"
        ) as mock_emit, patch(
            "core.content_engine.state_redis.write_pipeline_state_redis_async",
            new_callable=AsyncMock,
        ):
            from core.content_engine.state_helpers import _write_pipeline_state_async

            await _write_pipeline_state_async(
                tmp_artifact_dir,
                ["brief-001"],
                "drafting",
                redis_client=mock_async_redis,
                effective_slug="acme__widget",
            )

            # First arg to _emit_company should be "acme", not "acme__widget"
            assert mock_emit.call_args[0][0] == "acme"

    @pytest.mark.asyncio
    async def test_extracts_company_from_simple_slug(
        self, mock_async_redis: AsyncMock, tmp_artifact_dir: Path
    ) -> None:
        """effective_slug='acme' (no __) → company_slug='acme'."""
        with patch(
            "core.content_engine.state_helpers._emit_company"
        ) as mock_emit, patch(
            "core.content_engine.state_redis.write_pipeline_state_redis_async",
            new_callable=AsyncMock,
        ):
            from core.content_engine.state_helpers import _write_pipeline_state_async

            await _write_pipeline_state_async(
                tmp_artifact_dir,
                ["brief-001"],
                "linking",
                redis_client=mock_async_redis,
                effective_slug="acme",
            )

            assert mock_emit.call_args[0][0] == "acme"

    @pytest.mark.asyncio
    async def test_no_emit_when_no_slug(
        self, tmp_artifact_dir: Path
    ) -> None:
        """When effective_slug is None, _emit_company is NOT called."""
        with patch(
            "core.content_engine.state_helpers._emit_company"
        ) as mock_emit:
            from core.content_engine.state_helpers import _write_pipeline_state_async

            await _write_pipeline_state_async(
                tmp_artifact_dir,
                ["brief-001"],
                "enriching",
            )

            mock_emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_emit_failure_does_not_raise(
        self, mock_async_redis: AsyncMock, tmp_artifact_dir: Path
    ) -> None:
        """If _emit_company raises, the Redis write still succeeds (no file write)."""
        mock_redis_write = AsyncMock()
        with patch(
            "core.content_engine.state_helpers._emit_company",
            side_effect=RuntimeError("bus exploded"),
        ), patch(
            "core.content_engine.state_redis.write_pipeline_state_redis_async",
            mock_redis_write,
        ):
            from core.content_engine.state_helpers import _write_pipeline_state_async

            # Should NOT raise
            await _write_pipeline_state_async(
                tmp_artifact_dir,
                ["brief-001"],
                "evaluating",
                redis_client=mock_async_redis,
                effective_slug="acme",
            )

            # Redis write succeeded — file should NOT be written
            mock_redis_write.assert_called_once()
            state_path = tmp_artifact_dir / "pipeline_state.json"
            assert not state_path.is_file()

    @pytest.mark.asyncio
    async def test_emits_all_brief_ids(
        self, mock_async_redis: AsyncMock, tmp_artifact_dir: Path
    ) -> None:
        """Multiple brief_ids appear in data['changed']."""
        with patch(
            "core.content_engine.state_helpers._emit_company"
        ) as mock_emit, patch(
            "core.content_engine.state_redis.write_pipeline_state_redis_async",
            new_callable=AsyncMock,
        ):
            from core.content_engine.state_helpers import _write_pipeline_state_async

            await _write_pipeline_state_async(
                tmp_artifact_dir,
                ["brief-001", "brief-002", "brief-003"],
                "drafting",
                redis_client=mock_async_redis,
                effective_slug="acme",
            )

            call_data = mock_emit.call_args[0][2]
            assert call_data["changed"] == ["brief-001", "brief-002", "brief-003"]
            assert call_data["hint"] == "drafting"

    @pytest.mark.asyncio
    async def test_emits_authoritative_topic_run_changed_when_durable_update_succeeds(
        self, mock_async_redis: AsyncMock, tmp_artifact_dir: Path
    ) -> None:
        with patch(
            "core.content_engine.state_helpers._emit_company"
        ) as mock_emit, patch(
            "core.content_engine.state_redis.write_pipeline_state_redis_async",
            new_callable=AsyncMock,
        ), patch(
            "core.content_engine.state_helpers._sync_td_topic_runs_for_briefs",
            new_callable=AsyncMock,
            return_value=[{
                "topic_run_id": "run-1",
                "batch_run_id": "batch-1",
                "topic_assignment_id": "ta-1",
                "display_id": "WE-003",
                "topic_text": "Topic",
                "brief_id": "WE-003",
                "ga_run_id": "ga-1",
                "pipeline_task_id": "task-1",
                "status": "drafting",
                "stage": "drafting",
                "seq": 4,
                "content_piece_id": None,
                "created_at": "2026-04-10T00:00:00+00:00",
                "updated_at": "2026-04-10T00:00:01+00:00",
                "effective_slug": "acme",
            }],
        ) as mock_sync:
            from core.content_engine.state_helpers import _write_pipeline_state_async

            await _write_pipeline_state_async(
                tmp_artifact_dir,
                ["WE-003"],
                "drafting",
                task_id="task-1",
                redis_client=mock_async_redis,
                effective_slug="acme",
                session_factory=MagicMock(),
            )

            mock_sync.assert_awaited_once()
            assert mock_emit.call_args_list[0].args == (
                "acme",
                "topic_run_changed",
                {
                    "topic_run_id": "run-1",
                    "batch_run_id": "batch-1",
                    "topic_assignment_id": "ta-1",
                    "display_id": "WE-003",
                    "topic_text": "Topic",
                    "brief_id": "WE-003",
                    "ga_run_id": "ga-1",
                    "pipeline_task_id": "task-1",
                    "status": "drafting",
                    "stage": "drafting",
                    "seq": 4,
                    "content_piece_id": None,
                    "created_at": "2026-04-10T00:00:00+00:00",
                    "updated_at": "2026-04-10T00:00:01+00:00",
                    "effective_slug": "acme",
                },
            )
            assert mock_emit.call_args_list[1].args == (
                "acme",
                "state_changed",
                {"changed": ["WE-003"], "hint": "drafting"},
            )


class TestSelfAcquireRedis:
    """_write_pipeline_state_async self-acquires Redis when redis_client=None.

    This is the safety net that prevents the 4-min kanban sync lag when
    callers (e.g. TD orchestrator) forget to pass redis_client.
    """

    @pytest.mark.asyncio
    async def test_self_acquires_redis_when_client_is_none(
        self, tmp_artifact_dir: Path
    ) -> None:
        """When redis_client=None but Redis is configured, self-acquires async client."""
        mock_redis = AsyncMock()
        mock_redis.expire = AsyncMock()

        with patch(
            "core.content_engine.state_helpers._emit_company"
        ), patch(
            "core.content_engine.state_redis.write_pipeline_state_redis_async",
            new_callable=AsyncMock,
        ) as mock_write_redis, patch(
            "core.config.settings.settings"
        ) as mock_settings, patch(
            "core.redis.get_redis_or_none", return_value=mock_redis,
        ):
            mock_settings.redis_pipeline_state = True
            mock_settings.redis_url = "redis://localhost"

            from core.content_engine.state_helpers import _write_pipeline_state_async

            await _write_pipeline_state_async(
                tmp_artifact_dir,
                ["brief-001"],
                "outlining",
                task_id="task-1",
                redis_client=None,  # No client passed — must self-acquire
                effective_slug="acme",
            )

            # Redis write MUST have been called (self-acquired)
            mock_write_redis.assert_called_once_with(
                mock_redis, "acme", ["brief-001"], "outlining", task_id="task-1"
            )

            # File NOT written when Redis succeeded
            state_path = tmp_artifact_dir / "pipeline_state.json"
            assert not state_path.is_file()

    @pytest.mark.asyncio
    async def test_skips_redis_when_not_configured(
        self, tmp_artifact_dir: Path
    ) -> None:
        """When Redis is not configured, only file write happens (no error)."""
        with patch(
            "core.content_engine.state_helpers._emit_company"
        ), patch(
            "core.content_engine.state_redis.write_pipeline_state_redis_async",
            new_callable=AsyncMock,
        ) as mock_write_redis, patch(
            "core.config.settings.settings"
        ) as mock_settings:
            mock_settings.redis_pipeline_state = False
            mock_settings.redis_url = None

            from core.content_engine.state_helpers import _write_pipeline_state_async

            await _write_pipeline_state_async(
                tmp_artifact_dir,
                ["brief-001"],
                "outlining",
                redis_client=None,
                effective_slug="acme",
            )

            mock_write_redis.assert_not_called()

            # File write still happened
            state_path = tmp_artifact_dir / "pipeline_state.json"
            assert state_path.is_file()

    @pytest.mark.asyncio
    async def test_prefers_explicit_client_over_self_acquire(
        self, mock_async_redis: AsyncMock, tmp_artifact_dir: Path
    ) -> None:
        """When redis_client is explicitly provided, uses it (no self-acquire)."""
        with patch(
            "core.content_engine.state_helpers._emit_company"
        ), patch(
            "core.content_engine.state_redis.write_pipeline_state_redis_async",
            new_callable=AsyncMock,
        ) as mock_write_redis:
            from core.content_engine.state_helpers import _write_pipeline_state_async

            await _write_pipeline_state_async(
                tmp_artifact_dir,
                ["brief-001"],
                "drafting",
                redis_client=mock_async_redis,
                effective_slug="acme",
            )

            # Must have used the explicit client, not self-acquired
            mock_write_redis.assert_called_once_with(
                mock_async_redis, "acme", ["brief-001"], "drafting", task_id=None
            )

    @pytest.mark.asyncio
    async def test_self_acquire_failure_graceful(
        self, tmp_artifact_dir: Path
    ) -> None:
        """If get_redis_or_none() raises, falls through to file-only write."""
        with patch(
            "core.content_engine.state_helpers._emit_company"
        ), patch(
            "core.content_engine.state_redis.write_pipeline_state_redis_async",
            new_callable=AsyncMock,
        ) as mock_write_redis, patch(
            "core.config.settings.settings"
        ) as mock_settings, patch(
            "core.redis.get_redis_or_none",
            side_effect=RuntimeError("Redis init failed"),
        ):
            mock_settings.redis_pipeline_state = True
            mock_settings.redis_url = "redis://localhost"

            from core.content_engine.state_helpers import _write_pipeline_state_async

            # Should NOT raise
            await _write_pipeline_state_async(
                tmp_artifact_dir,
                ["brief-001"],
                "formatting",
                redis_client=None,
                effective_slug="acme",
            )

            # Redis write not called (self-acquire failed gracefully)
            mock_write_redis.assert_not_called()

            # File write succeeded
            state_path = tmp_artifact_dir / "pipeline_state.json"
            assert state_path.is_file()
            data = json.loads(state_path.read_text())
            assert data["brief-001"] == "formatting"


class TestCleanupSelfAcquireRedis:
    """_cleanup_pipeline_state_async self-acquires Redis when redis_client=None."""

    @pytest.mark.asyncio
    async def test_self_acquires_redis_for_cleanup(
        self, tmp_artifact_dir: Path
    ) -> None:
        """Cleanup self-acquires async Redis when client is None."""
        mock_redis = AsyncMock()

        # Write a state file first so cleanup has something to clean
        state_path = tmp_artifact_dir / "pipeline_state.json"
        state_path.write_text(json.dumps({"brief-001": "completed"}))

        with patch(
            "core.content_engine.state_redis.cleanup_pipeline_state_redis_async",
            new_callable=AsyncMock,
        ) as mock_cleanup_redis, patch(
            "core.config.settings.settings"
        ) as mock_settings, patch(
            "core.redis.get_redis_or_none", return_value=mock_redis,
        ):
            mock_settings.redis_pipeline_state = True
            mock_settings.redis_url = "redis://localhost"

            from core.content_engine.state_helpers import _cleanup_pipeline_state_async

            await _cleanup_pipeline_state_async(
                tmp_artifact_dir,
                ["brief-001"],
                redis_client=None,
                effective_slug="acme",
            )

            mock_cleanup_redis.assert_called_once_with(
                mock_redis, "acme", ["brief-001"]
            )


class TestSyncWriteDoesNotEmit:
    """The sync _write_pipeline_state must NOT call _emit_company."""

    def test_sync_write_does_not_emit(self, tmp_artifact_dir: Path) -> None:
        with patch(
            "core.content_engine.state_helpers._emit_company"
        ) as mock_emit:
            from core.content_engine.state_helpers import _write_pipeline_state

            _write_pipeline_state(
                tmp_artifact_dir,
                ["brief-001"],
                "outlining",
                task_id="task-1",
                effective_slug="acme",
            )

            mock_emit.assert_not_called()

            # But file write should still work
            state_path = tmp_artifact_dir / "pipeline_state.json"
            assert state_path.is_file()
            data = json.loads(state_path.read_text())
            assert data["brief-001"] == "outlining"
