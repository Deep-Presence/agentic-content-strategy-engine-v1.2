"""Tests for CMS service orchestrator."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from core.cms.exceptions import CMSError
from core.cms.models import CMSCategory, CMSConnectionStatus, CMSPost, CMSPostStatus, CMSPublishMetadata
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

    @pytest.mark.asyncio
    async def test_publish_brief_uses_publish_metadata_and_registers_inventory(self) -> None:
        md_content = "# Test Article\n\nSome content here."
        storage = _make_mock_storage(md_content)
        conn_repo, pub_repo, _ = _make_mock_repos()
        pub_repo.create.return_value = MagicMock()
        content_repo = AsyncMock()
        content_repo.get_by_slug_and_brief_id.return_value = MagicMock(id=uuid.uuid4())
        inventory_service = AsyncMock()

        service = CMSService(
            connection_repo=conn_repo,
            publish_repo=pub_repo,
            synced_post_repo=AsyncMock(),
            storage=storage,
            fernet_key=_TEST_FERNET_KEY,
            content_repo=content_repo,
            inventory_service=inventory_service,
        )
        conn = _mock_connection()
        conn.company_id = uuid.uuid4()

        published = CMSPost(
            cms_id="123",
            title="Test Article",
            slug="no-code-web-development-enterprise-overview",
            url="https://blog.example.com/no-code-web-development-enterprise-overview/",
            word_count=50,
        )
        with patch(
            "core.services.cms_service.create_cms_adapter"
        ) as mock_factory:
            mock_adapter = AsyncMock()
            mock_adapter.publish_post.return_value = published
            mock_factory.return_value = mock_adapter

            await service.publish_brief(
                company_slug="test-co",
                brief_id="brief-001",
                connection=conn,
                effective_slug="test-co",
                target_status="publish",
                publish_metadata=CMSPublishMetadata(
                    slug="no-code-web-development-enterprise-overview",
                    meta_title="No-Code Web Development in the Enterprise | Deep Presence",
                    meta_description="A plain-English guide to no-code for enterprise teams.",
                    canonical_url="https://blog.example.com/no-code-web-development-enterprise-overview/",
                    publish_date="2026-04-11",
                    author="42",
                    tags=["no-code", "enterprise"],
                ),
            )

        post_create = mock_adapter.publish_post.await_args.args[0]
        assert post_create.slug == "no-code-web-development-enterprise-overview"
        assert post_create.seo_title == "No-Code Web Development in the Enterprise | Deep Presence"
        assert post_create.seo_description == "A plain-English guide to no-code for enterprise teams."
        assert post_create.canonical_url == "https://blog.example.com/no-code-web-development-enterprise-overview/"
        assert post_create.tags == ["no-code", "enterprise"]
        assert post_create.author == "42"
        assert post_create.published_at is not None
        inventory_service.register_published_content.assert_awaited_once()


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
            mock_adapter.list_all_posts.return_value = (posts, False)
            mock_adapter.list_categories.return_value = categories
            mock_factory.return_value = mock_adapter

            result = await service.sync_existing_content("test-co", conn)

        assert result["synced"] == 2
        assert result["stale"] == 1
        assert result["categories"] == 1
        assert result["truncated"] is False
        assert synced_repo.upsert_from_cms.call_count == 2
        # new_page_ids is present (empty when no inventory service injected)
        assert "new_page_ids" in result

    @pytest.mark.asyncio
    async def test_sync_truncated_result(self) -> None:
        conn_repo, _, synced_repo = _make_mock_repos()
        synced_repo.upsert_from_cms.return_value = MagicMock()
        conn_repo.update_sync_metadata.return_value = None

        service = _make_service(conn_repo=conn_repo, synced_repo=synced_repo)
        conn = _mock_connection()

        posts = [CMSPost(cms_id="1", title="P", slug="p", categories=[])]
        with patch(
            "core.services.cms_service.create_cms_adapter"
        ) as mock_factory:
            mock_adapter = AsyncMock()
            mock_adapter.list_all_posts.return_value = (posts, True)
            mock_adapter.list_categories.return_value = []
            mock_factory.return_value = mock_adapter

            result = await service.sync_existing_content("test-co", conn)

        assert result["truncated"] is True


# ── Cache Integration Tests ──────────────────────────────────────────


class TestCategoriesCacheIntegration:
    @pytest.mark.asyncio
    async def test_list_categories_cache_hit(self) -> None:
        """When cache has categories, adapter is NOT called."""
        service = _make_service()
        conn = _mock_connection()

        cached_cats = [{"cms_id": "10", "name": "AI", "slug": "ai"}]
        with patch(
            "core.services.cms_service.create_cms_adapter"
        ) as mock_factory, patch(
            "core.services.cms_cache.get_sync_redis_or_none"
        ) as mock_redis_fn:
            mock_adapter = AsyncMock()
            mock_factory.return_value = mock_adapter

            # Simulate cache hit
            mock_redis = MagicMock()
            import json
            mock_redis.get.return_value = json.dumps(cached_cats)
            mock_redis_fn.return_value = mock_redis

            result = await service.list_categories(conn)

        assert len(result) == 1
        assert result[0].name == "AI"
        # Adapter was NOT called
        mock_adapter.list_categories.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_categories_cache_miss(self) -> None:
        """On cache miss, adapter is called and result is cached."""
        service = _make_service()
        conn = _mock_connection()

        with patch(
            "core.services.cms_service.create_cms_adapter"
        ) as mock_factory, patch(
            "core.services.cms_cache.get_sync_redis_or_none"
        ) as mock_redis_fn:
            mock_adapter = AsyncMock()
            mock_adapter.list_categories.return_value = [
                CMSCategory(cms_id="10", name="AI")
            ]
            mock_factory.return_value = mock_adapter

            mock_redis = MagicMock()
            mock_redis.get.return_value = None  # cache miss
            mock_redis_fn.return_value = mock_redis

            result = await service.list_categories(conn)

        assert len(result) == 1
        mock_adapter.list_categories.assert_called_once()
        # cache_set was called (via setex)
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_categories_no_redis(self) -> None:
        """Without Redis, adapter is called directly."""
        service = _make_service()
        conn = _mock_connection()

        with patch(
            "core.services.cms_service.create_cms_adapter"
        ) as mock_factory, patch(
            "core.services.cms_cache.get_sync_redis_or_none",
            return_value=None,
        ):
            mock_adapter = AsyncMock()
            mock_adapter.list_categories.return_value = [
                CMSCategory(cms_id="10", name="AI")
            ]
            mock_factory.return_value = mock_adapter

            result = await service.list_categories(conn)

        assert len(result) == 1
        mock_adapter.list_categories.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_invalidates_categories_cache(self) -> None:
        """publish_brief invalidates categories cache when categories provided."""
        md_content = "# Test\n\nContent."
        storage = _make_mock_storage(md_content)
        _, pub_repo, _ = _make_mock_repos()
        pub_repo.create.return_value = MagicMock()

        service = _make_service(pub_repo=pub_repo, storage=storage)
        conn = _mock_connection()

        published = CMSPost(cms_id="1", url="https://x.com/1/", word_count=10)
        with patch(
            "core.services.cms_service.create_cms_adapter"
        ) as mock_factory, patch(
            "core.services.cms_cache.get_sync_redis_or_none"
        ) as mock_redis_fn:
            mock_adapter = AsyncMock()
            mock_adapter.publish_post.return_value = published
            mock_factory.return_value = mock_adapter

            mock_redis = MagicMock()
            mock_redis_fn.return_value = mock_redis

            await service.publish_brief(
                "test-co", "b1", conn,
                effective_slug="test-co",
                category_names=["AI"],
            )

        # Categories cache should have been invalidated (delete called)
        mock_redis.delete.assert_called()


class TestStaleActionsCacheIntegration:
    @pytest.mark.asyncio
    async def test_cache_hit(self) -> None:
        """Cached stale actions returned without DB query."""
        _, _, synced_repo = _make_mock_repos()
        service = _make_service(synced_repo=synced_repo)

        cached_actions = [{"title": "Cached Post", "staleness_days": 30}]
        with patch(
            "core.services.cms_cache.get_sync_redis_or_none"
        ) as mock_redis_fn:
            mock_redis = MagicMock()
            import json
            mock_redis.get.return_value = json.dumps(cached_actions)
            mock_redis_fn.return_value = mock_redis

            result = await service.get_stale_actions("test-co")

        assert result == cached_actions
        synced_repo.get_stale.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_miss(self) -> None:
        """On cache miss, DB is queried and result is cached."""
        _, _, synced_repo = _make_mock_repos()
        mock_post = MagicMock()
        mock_post.id = uuid.uuid4()
        mock_post.cms_post_id = "42"
        mock_post.title = "Old"
        mock_post.url = "https://x.com/"
        mock_post.staleness_days = 45
        mock_post.queued_for_refresh = False
        synced_repo.get_stale.return_value = [mock_post]

        service = _make_service(synced_repo=synced_repo)

        with patch(
            "core.services.cms_cache.get_sync_redis_or_none"
        ) as mock_redis_fn:
            mock_redis = MagicMock()
            mock_redis.get.return_value = None  # cache miss
            mock_redis_fn.return_value = mock_redis

            result = await service.get_stale_actions("test-co")

        assert len(result) == 1
        synced_repo.get_stale.assert_called_once()
        mock_redis.setex.assert_called_once()


class TestSyncedPostsCacheIntegration:
    @pytest.mark.asyncio
    async def test_cache_hit_returns_simplenamespace(self) -> None:
        """Cached synced posts are deserialized to SimpleNamespace."""
        _, _, synced_repo = _make_mock_repos()
        service = _make_service(synced_repo=synced_repo)

        cached_posts = [{"id": "abc", "title": "Cached", "categories": ["AI"]}]
        with patch(
            "core.services.cms_cache.get_sync_redis_or_none"
        ) as mock_redis_fn:
            mock_redis = MagicMock()
            import json
            mock_redis.get.return_value = json.dumps(cached_posts)
            mock_redis_fn.return_value = mock_redis

            result = await service.list_synced_posts("test-co")

        assert len(result) == 1
        assert result[0].title == "Cached"
        assert result[0].categories == ["AI"]
        synced_repo.list_by_company.assert_not_called()
