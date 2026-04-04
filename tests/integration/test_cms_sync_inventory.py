"""Integration tests for CMS sync → content inventory hydration.

Tests the inventory wiring in CMSService.sync_existing_content() —
non-blocking error isolation, FK linking, and graceful skip.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from contextlib import asynccontextmanager


@asynccontextmanager
async def _mock_begin_nested():
    """Mock async context manager for session.begin_nested()."""
    yield MagicMock()


def _make_synced_post_repo():
    """Build a synced post repo mock with properly mocked session."""
    repo = AsyncMock()
    # Mock the _session.begin_nested to return a real async context manager
    mock_session = MagicMock()
    mock_session.begin_nested = lambda: _mock_begin_nested()
    repo._session = mock_session
    return repo


def _make_cms_post(**overrides):
    """Build a minimal CMS post mock."""
    defaults = dict(
        cms_id="wp-100",
        title="Blog Post",
        slug="blog-post",
        url="https://blog.testco.com/blog-post",
        content_html="<p>Content</p>",
        excerpt="<p>Excerpt</p>",
        content_preview="Content",
        word_count=800,
        published_at=datetime.now(timezone.utc),
        modified_at=datetime.now(timezone.utc),
        categories=[],
        tags=[],
        seo_title="",
        seo_description="",
        status="publish",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_connection(**overrides):
    """Build a minimal CMS connection mock."""
    conn = MagicMock()
    conn.id = overrides.get("id", uuid.uuid4())
    conn.company_id = overrides.get("company_id", uuid.uuid4())
    conn.provider = MagicMock(value="wordpress")
    conn.site_url = "https://blog.testco.com"
    return conn


class TestCMSSyncInventoryIntegration:
    """CMSService.sync_existing_content() → content inventory hydration."""

    @pytest.mark.asyncio
    async def test_inventory_hydrated_during_sync(self):
        """ingest_from_cms_sync is called with synced posts."""
        from core.services.cms_service import CMSService

        # Build mocks
        conn_repo = AsyncMock()
        publish_repo = AsyncMock()
        synced_post_repo = _make_synced_post_repo()
        storage = MagicMock()

        inventory_service = AsyncMock()
        inv_id = uuid.uuid4()
        inventory_service.ingest_from_cms_sync = AsyncMock(
            return_value=[(inv_id, "wp-100")]
        )

        svc = CMSService(
            connection_repo=conn_repo,
            publish_repo=publish_repo,
            synced_post_repo=synced_post_repo,
            storage=storage,
            fernet_key="test-key",
            inventory_service=inventory_service,
        )

        # Mock adapter
        posts = [_make_cms_post()]
        connection = _make_connection()

        with patch.object(svc, "_reconstruct_adapter") as mock_adapter:
            adapter = AsyncMock()
            adapter.list_all_posts = AsyncMock(return_value=(posts, False))
            adapter.list_categories = AsyncMock(return_value=[])
            mock_adapter.return_value = adapter

            result = await svc.sync_existing_content("test-co", connection)

        # Verify inventory service was called
        inventory_service.ingest_from_cms_sync.assert_called_once()
        call_kwargs = inventory_service.ingest_from_cms_sync.call_args.kwargs
        assert call_kwargs["company_id"] == connection.company_id
        assert call_kwargs["effective_slug"] == "test-co"

        # Verify FK linking
        synced_post_repo.batch_link_inventory_ids.assert_called_once_with(
            connection_id=connection.id,
            pairs=[(inv_id, "wp-100")],
        )

        # Verify sync still succeeded
        assert result["synced"] == 1

    @pytest.mark.asyncio
    async def test_inventory_failure_does_not_crash_sync(self):
        """Inventory error is caught — sync still returns successfully."""
        from core.services.cms_service import CMSService

        conn_repo = AsyncMock()
        publish_repo = AsyncMock()
        synced_post_repo = _make_synced_post_repo()
        storage = MagicMock()

        inventory_service = AsyncMock()
        inventory_service.ingest_from_cms_sync = AsyncMock(
            side_effect=RuntimeError("DB connection lost")
        )

        svc = CMSService(
            connection_repo=conn_repo,
            publish_repo=publish_repo,
            synced_post_repo=synced_post_repo,
            storage=storage,
            fernet_key="test-key",
            inventory_service=inventory_service,
        )

        connection = _make_connection()
        posts = [_make_cms_post()]

        with patch.object(svc, "_reconstruct_adapter") as mock_adapter:
            adapter = AsyncMock()
            adapter.list_all_posts = AsyncMock(return_value=(posts, False))
            adapter.list_categories = AsyncMock(return_value=[])
            mock_adapter.return_value = adapter

            # Should NOT raise
            result = await svc.sync_existing_content("test-co", connection)

        # Sync still succeeded despite inventory failure
        assert result["synced"] == 1
        # FK linking was NOT called (inventory failed before that)
        synced_post_repo.batch_link_inventory_ids.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_inventory_service_skips_gracefully(self):
        """inventory_service=None → no error, no inventory call."""
        from core.services.cms_service import CMSService

        conn_repo = AsyncMock()
        publish_repo = AsyncMock()
        synced_post_repo = _make_synced_post_repo()
        storage = MagicMock()

        svc = CMSService(
            connection_repo=conn_repo,
            publish_repo=publish_repo,
            synced_post_repo=synced_post_repo,
            storage=storage,
            fernet_key="test-key",
            inventory_service=None,  # No inventory service
        )

        connection = _make_connection()
        posts = [_make_cms_post()]

        with patch.object(svc, "_reconstruct_adapter") as mock_adapter:
            adapter = AsyncMock()
            adapter.list_all_posts = AsyncMock(return_value=(posts, False))
            adapter.list_categories = AsyncMock(return_value=[])
            mock_adapter.return_value = adapter

            result = await svc.sync_existing_content("test-co", connection)

        assert result["synced"] == 1
        # No FK linking attempted
        synced_post_repo.batch_link_inventory_ids.assert_not_called()

    @pytest.mark.asyncio
    async def test_fk_link_failure_does_not_crash_sync(self):
        """batch_link_inventory_ids failure is caught — sync still succeeds."""
        from core.services.cms_service import CMSService

        conn_repo = AsyncMock()
        publish_repo = AsyncMock()
        synced_post_repo = _make_synced_post_repo()
        synced_post_repo.batch_link_inventory_ids = AsyncMock(
            side_effect=RuntimeError("FK constraint failed")
        )
        storage = MagicMock()

        inventory_service = AsyncMock()
        inv_id = uuid.uuid4()
        inventory_service.ingest_from_cms_sync = AsyncMock(
            return_value=[(inv_id, "wp-100")]
        )

        svc = CMSService(
            connection_repo=conn_repo,
            publish_repo=publish_repo,
            synced_post_repo=synced_post_repo,
            storage=storage,
            fernet_key="test-key",
            inventory_service=inventory_service,
        )

        connection = _make_connection()
        posts = [_make_cms_post()]

        with patch.object(svc, "_reconstruct_adapter") as mock_adapter:
            adapter = AsyncMock()
            adapter.list_all_posts = AsyncMock(return_value=(posts, False))
            adapter.list_categories = AsyncMock(return_value=[])
            mock_adapter.return_value = adapter

            # Should NOT raise
            result = await svc.sync_existing_content("test-co", connection)

        assert result["synced"] == 1

    @pytest.mark.asyncio
    async def test_empty_pairs_skips_fk_linking(self):
        """No pairs from inventory → batch_link_inventory_ids not called."""
        from core.services.cms_service import CMSService

        conn_repo = AsyncMock()
        publish_repo = AsyncMock()
        synced_post_repo = _make_synced_post_repo()
        storage = MagicMock()

        inventory_service = AsyncMock()
        inventory_service.ingest_from_cms_sync = AsyncMock(return_value=[])

        svc = CMSService(
            connection_repo=conn_repo,
            publish_repo=publish_repo,
            synced_post_repo=synced_post_repo,
            storage=storage,
            fernet_key="test-key",
            inventory_service=inventory_service,
        )

        connection = _make_connection()
        posts = [_make_cms_post(url="")]  # Will be skipped by service

        with patch.object(svc, "_reconstruct_adapter") as mock_adapter:
            adapter = AsyncMock()
            adapter.list_all_posts = AsyncMock(return_value=(posts, False))
            adapter.list_categories = AsyncMock(return_value=[])
            mock_adapter.return_value = adapter

            result = await svc.sync_existing_content("test-co", connection)

        synced_post_repo.batch_link_inventory_ids.assert_not_called()
