"""Tests for CMS service orchestrator."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from core.cms.exceptions import CMSError
from core.cms.models import CMSCategory, CMSConnectionStatus, CMSPost, CMSPostStatus
from core.db.enums import CMSProvider
from core.services.cms_service import CMSService

# Generate a valid Fernet key for tests
_TEST_FERNET_KEY = Fernet.generate_key().decode()


def _make_mock_repos() -> tuple[AsyncMock, AsyncMock, AsyncMock]:
    """Create mock repos with AsyncMock."""
    conn_repo = AsyncMock()
    pub_repo = AsyncMock()
    synced_repo = AsyncMock()
    return conn_repo, pub_repo, synced_repo


def _make_mock_storage(content: str | None = None) -> MagicMock:
    """Create a mock StorageBackend."""
    storage = MagicMock()
    storage.read.return_value = content
    return storage


def _make_service(
    conn_repo: AsyncMock | None = None,
    pub_repo: AsyncMock | None = None,
    synced_repo: AsyncMock | None = None,
    storage: MagicMock | None = None,
    fernet_key: str = _TEST_FERNET_KEY,
) -> CMSService:
    cr, pr, sr = _make_mock_repos()
    return CMSService(
        connection_repo=conn_repo or cr,
        publish_repo=pub_repo or pr,
        synced_post_repo=synced_repo or sr,
        storage=storage or _make_mock_storage(),
        fernet_key=fernet_key,
    )


def _mock_connection(
    *,
    provider: str = "wordpress",
    site_url: str = "https://blog.example.com",
    encrypted_credentials: str = "",
    fernet_key: str = _TEST_FERNET_KEY,
) -> MagicMock:
    """Build a mock CMSConnectionModel."""
    if not encrypted_credentials:
        import json

        payload = json.dumps({"username": "admin", "api_key": "secret"})
        encrypted_credentials = Fernet(fernet_key.encode()).encrypt(
            payload.encode()
        ).decode()

    conn = MagicMock()
    conn.id = uuid.uuid4()
    conn.provider = CMSProvider(provider)
    conn.site_url = site_url
    conn.encrypted_credentials = encrypted_credentials
    conn.company_slug = "test-co"
    return conn


# ── Connect Tests ─────────────────────────────────────────────────────


class TestConnect:
    @pytest.mark.asyncio
    async def test_connect_success(self) -> None:
        conn_repo, pub_repo, synced_repo = _make_mock_repos()
        conn_repo.get_by_company_slug.return_value = None
        conn_repo.create.return_value = MagicMock()

        service = _make_service(conn_repo=conn_repo)

        mock_status = CMSConnectionStatus(
            connected=True, site_name="Test Blog"
        )
        with patch(
            "core.services.cms_service.create_cms_adapter"
        ) as mock_factory:
            mock_adapter = AsyncMock()
            mock_adapter.validate_connection.return_value = mock_status
            mock_factory.return_value = mock_adapter

            result = await service.connect(
                company_id=uuid.uuid4(),
                company_slug="test-co",
                tenant_id="tenant-1",
                provider="wordpress",
                site_url="https://blog.example.com",
                username="admin",
                api_key="secret",
            )

        assert result["connected"] is True
        assert result["site_name"] == "Test Blog"
        conn_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_invalid_credentials(self) -> None:
        conn_repo, _, _ = _make_mock_repos()
        service = _make_service(conn_repo=conn_repo)

        mock_status = CMSConnectionStatus(
            connected=False, error="Invalid credentials"
        )
        with patch(
            "core.services.cms_service.create_cms_adapter"
        ) as mock_factory:
            mock_adapter = AsyncMock()
            mock_adapter.validate_connection.return_value = mock_status
            mock_factory.return_value = mock_adapter

            result = await service.connect(
                company_id=uuid.uuid4(),
                company_slug="test-co",
                tenant_id="tenant-1",
                provider="wordpress",
                site_url="https://blog.example.com",
                username="admin",
                api_key="wrong",
            )

        assert result["connected"] is False
        conn_repo.create.assert_not_called()


# ── Disconnect Tests ──────────────────────────────────────────────────


class TestDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_deactivates(self) -> None:
        conn_repo, _, _ = _make_mock_repos()
        conn = _mock_connection()
        conn_repo.get_by_company_slug.return_value = conn
        conn_repo.deactivate.return_value = True

        service = _make_service(conn_repo=conn_repo)
        result = await service.disconnect("test-co", "tenant-1")
        assert result is True
        conn_repo.deactivate.assert_called_once_with(conn.id)

    @pytest.mark.asyncio
    async def test_disconnect_no_connection(self) -> None:
        conn_repo, _, _ = _make_mock_repos()
        conn_repo.get_by_company_slug.return_value = None

        service = _make_service(conn_repo=conn_repo)
        result = await service.disconnect("test-co", "tenant-1")
        assert result is False


# ── Get Connection Tests ──────────────────────────────────────────────


class TestGetConnection:
    @pytest.mark.asyncio
    async def test_returns_active(self) -> None:
        conn_repo, _, _ = _make_mock_repos()
        conn = _mock_connection()
        conn_repo.get_by_company_slug.return_value = conn

        service = _make_service(conn_repo=conn_repo)
        result = await service.get_connection("test-co", "tenant-1")
        assert result is conn


# ── Publish Tests ─────────────────────────────────────────────────────


class TestPublish:
    @pytest.mark.asyncio
    async def test_publish_brief_reads_storage_converts_records(self) -> None:
        md_content = "# Test Article\n\nSome content here."
        storage = _make_mock_storage(md_content)
        conn_repo, pub_repo, _ = _make_mock_repos()
        pub_repo.create.return_value = MagicMock()

        service = _make_service(
            conn_repo=conn_repo, pub_repo=pub_repo, storage=storage
        )
        conn = _mock_connection()

        published = CMSPost(
            cms_id="123",
            title="Test Article",
            slug="test-article",
            url="https://blog.example.com/test-article/",
            word_count=50,
        )
        with patch(
            "core.services.cms_service.create_cms_adapter"
        ) as mock_factory:
            mock_adapter = AsyncMock()
            mock_adapter.publish_post.return_value = published
            mock_factory.return_value = mock_adapter

            result = await service.publish_brief(
                company_slug="test-co",
                brief_id="brief-001",
                connection=conn,
                effective_slug="test-co",
            )

        assert result.cms_id == "123"
        # Storage was read with correct path
        storage.read.assert_called_once_with(
            "content/test-co/content/brief-001/final.md"
        )
        pub_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_brief_missing_final_md(self) -> None:
        storage = _make_mock_storage(None)
        service = _make_service(storage=storage)
        conn = _mock_connection()

        with pytest.raises(CMSError, match="No final.md"):
            await service.publish_brief(
                company_slug="test-co",
                brief_id="brief-999",
                connection=conn,
                effective_slug="test-co",
            )


# ── Refresh Tests ─────────────────────────────────────────────────────


class TestRefresh:
    @pytest.mark.asyncio
    async def test_refresh_post_updates_existing(self) -> None:
        md_content = "# Updated Article\n\nNew content."
        storage = _make_mock_storage(md_content)
        _, pub_repo, _ = _make_mock_repos()
        pub_repo.create.return_value = MagicMock()

        service = _make_service(pub_repo=pub_repo, storage=storage)
        conn = _mock_connection()

        updated = CMSPost(cms_id="42", url="https://blog.example.com/updated/", word_count=30)
        with patch(
            "core.services.cms_service.create_cms_adapter"
        ) as mock_factory:
            mock_adapter = AsyncMock()
            mock_adapter.update_post.return_value = updated
            mock_factory.return_value = mock_adapter

            result = await service.refresh_post(
                company_slug="test-co",
                cms_post_id="42",
                brief_id="refresh-001",
                connection=conn,
                effective_slug="test-co",
            )

        assert result.cms_id == "42"
        # Verify action=refresh in the create call
        call_kwargs = pub_repo.create.call_args[1]
        from core.db.enums import CMSPublishAction

        assert call_kwargs["action"] == CMSPublishAction.refresh


# ── Credential Encryption Tests ───────────────────────────────────────


class TestCredentialEncryption:
    def test_roundtrip(self) -> None:
        service = _make_service()
        encrypted = service._encrypt_credentials("admin", "s3cr3t-key!")
        username, api_key = service._decrypt_credentials(encrypted)
        assert username == "admin"
        assert api_key == "s3cr3t-key!"


# ── Markdown Conversion Tests ─────────────────────────────────────────


class TestMarkdownToHtml:
    def test_tables_and_fenced_code(self) -> None:
        md = "| A | B |\n|---|---|\n| 1 | 2 |\n\n```python\nprint('hi')\n```"
        html = CMSService._markdown_to_html(md)
        assert "<table>" in html
        assert "<code" in html  # <code class="language-python">

    def test_h1_conversion(self) -> None:
        md = "# Hello World"
        html = CMSService._markdown_to_html(md)
        assert "<h1" in html  # toc extension adds id attr: <h1 id="hello-world">
        assert "Hello World" in html


# ── Stale Actions Tests ───────────────────────────────────────────────


class TestStaleActions:
    @pytest.mark.asyncio
    async def test_get_stale_actions(self) -> None:
        _, _, synced_repo = _make_mock_repos()
        mock_post = MagicMock()
        mock_post.id = uuid.uuid4()
        mock_post.cms_post_id = "42"
        mock_post.title = "Old Article"
        mock_post.url = "https://blog.example.com/old/"
        mock_post.staleness_days = 45
        mock_post.queued_for_refresh = False
        synced_repo.get_stale.return_value = [mock_post]

        service = _make_service(synced_repo=synced_repo)
        actions = await service.get_stale_actions("test-co")

        assert len(actions) == 1
        assert actions[0]["title"] == "Old Article"
        assert actions[0]["staleness_days"] == 45
        assert "45 days ago" in actions[0]["description"]


# ── Sync Tests ────────────────────────────────────────────────────────


class TestSync:
    @pytest.mark.asyncio
    async def test_sync_existing_content(self) -> None:
        conn_repo, _, synced_repo = _make_mock_repos()
        synced_repo.upsert_from_cms.return_value = MagicMock()
        conn_repo.update_sync_metadata.return_value = None

        service = _make_service(
            conn_repo=conn_repo, synced_repo=synced_repo
        )
        conn = _mock_connection()

        # Mock adapter that returns 2 posts + 1 category
        now = datetime.now(timezone.utc)
        old_date = now - timedelta(days=60)

        posts = [
            CMSPost(
                cms_id="1",
                title="Fresh",
                slug="fresh",
                modified_at=now,
                categories=["10"],
            ),
            CMSPost(
                cms_id="2",
                title="Stale",
                slug="stale",
                modified_at=old_date,
                categories=["10"],
            ),
        ]
        categories = [CMSCategory(cms_id="10", name="AI")]

        with patch(
            "core.services.cms_service.create_cms_adapter"
        ) as mock_factory:
            mock_adapter = AsyncMock()
            mock_adapter.list_all_posts.return_value = posts
            mock_adapter.list_categories.return_value = categories
            mock_factory.return_value = mock_adapter

            result = await service.sync_existing_content("test-co", conn)

        assert result["synced"] == 2
        assert result["stale"] == 1
        assert result["categories"] == 1
        assert synced_repo.upsert_from_cms.call_count == 2
