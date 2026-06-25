"""Tests for CMS integration API endpoints.

Covers all 11 endpoints with auth, tenant isolation, RBAC, and error mapping.
CMS service is mocked via ``app.state.cms_service`` pre-built override (bypasses DI).

Critical test lesson (F12): Patch ``api.routers.cms.run_cms_sync_task``
(point-of-use), NOT ``api.tasks.runner.run_cms_sync_task``.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from core.cms.exceptions import CMSAuthError, CMSError, CMSNotFoundError
from core.cms.models import CMSCategory, CMSPost, CMSPostStatus


# ── Helpers ───────────────────────────────────────────────────────────


def _mock_cms_post(**overrides) -> CMSPost:
    """Return a realistic CMSPost mock."""
    defaults = dict(
        cms_id="wp-123",
        title="Test Post",
        slug="test-post",
        content_html="<p>Hello</p>",
        url="https://blog.testco.com/test-post",
        status=CMSPostStatus.draft,
        word_count=500,
    )
    defaults.update(overrides)
    return CMSPost(**defaults)


def _mock_connection(**overrides):
    """Return a MagicMock resembling CMSConnectionModel."""
    conn = MagicMock()
    conn.id = uuid.uuid4()
    conn.provider = MagicMock(value="wordpress")
    conn.site_url = "https://blog.testco.com"
    conn.site_name = "Test Blog"
    conn.cms_version = "6.4"
    conn.user_display_name = "Test User"
    conn.is_active = True
    conn.last_sync_at = datetime.now(timezone.utc)
    conn.sync_post_count = 10
    conn.provider_config = {}
    for k, v in overrides.items():
        setattr(conn, k, v)
    return conn


def _mock_synced_post(**overrides):
    """Return a MagicMock resembling CMSSyncedPostModel."""
    p = MagicMock()
    p.id = uuid.uuid4()
    p.cms_post_id = "wp-456"
    p.title = "Synced Post"
    p.slug = "synced-post"
    p.url = "https://blog.testco.com/synced-post"
    p.word_count = 300
    p.published_at = datetime.now(timezone.utc)
    p.modified_at = datetime.now(timezone.utc)
    p.is_stale = False
    p.staleness_days = 0
    p.categories = ["Marketing"]
    p.queued_for_refresh = False
    for k, v in overrides.items():
        setattr(p, k, v)
    return p


def _mock_publish_record(**overrides):
    """Return a MagicMock resembling CMSPublishRecordModel."""
    r = MagicMock()
    r.id = uuid.uuid4()
    r.brief_id = "brief-abc123"
    r.effective_slug = "test-co"
    r.cms_post_id = "wp-789"
    r.cms_post_url = "https://blog.testco.com/new-post"
    r.cms_post_slug = "new-post"
    r.action = MagicMock(value="create")
    r.status_at_publish = MagicMock(value="draft")
    r.published_at = datetime.now(timezone.utc)
    r.title_published = "New Post"
    r.word_count = 800
    for k, v in overrides.items():
        setattr(r, k, v)
    return r


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _disable_redis_cache(monkeypatch):
    """Prevent Redis cache from leaking state between CMS tests."""
    monkeypatch.setattr(
        "core.services.cms_cache.get_sync_redis_or_none", lambda: None
    )


@pytest.fixture
def mock_cms_service():
    """Pre-built CMSService mock, set on app.state to bypass DI."""
    svc = AsyncMock()

    # Default returns
    svc.connect = AsyncMock(return_value={
        "connected": True,
        "site_name": "Test Blog",
        "site_url": "https://blog.testco.com",
        "cms_version": "6.4",
        "user_display_name": "Test User",
        "capabilities": [],
        "error": None,
    })
    svc.get_connection = AsyncMock(return_value=None)
    svc.disconnect = AsyncMock(return_value=True)
    svc.sync_existing_content = AsyncMock(return_value={
        "synced": 5, "stale": 2, "categories": 3,
    })
    svc.publish_brief = AsyncMock(return_value=_mock_cms_post())
    svc.refresh_post = AsyncMock(return_value=_mock_cms_post(
        cms_id="wp-456", title="Updated Post", slug="updated-post",
    ))
    svc.get_stale_actions = AsyncMock(return_value=[])
    svc.queue_stale_for_refresh = AsyncMock(return_value={
        "brief_id": "refresh-abc12345",
        "title": "Stale Post",
        "status": "triage",
    })
    svc.list_synced_posts = AsyncMock(return_value=[])
    svc.list_publish_history = AsyncMock(return_value=[])
    svc.list_categories = AsyncMock(return_value=[])
    svc.list_webflow_collections = AsyncMock(return_value=[])
    svc.get_webflow_collection_fields = AsyncMock(return_value={
        "collection_id": "coll-1",
        "fields": [],
        "suggested_mapping": {
            "title_field": "name",
            "slug_field": "slug",
            "body_field": "post-body",
        },
    })
    svc.configure_webflow = AsyncMock(return_value={
        "configured": True,
        "provider_config": {"site_id": "site-1", "collections": []},
    })

    return svc


@pytest.fixture
def app(app, mock_cms_service):
    """Extend the base app fixture with CMS service mock."""
    app.state.cms_service = mock_cms_service
    return app


# ── 1. Connect ────────────────────────────────────────────────────────


class TestCMSConnect:
    """POST /api/v1/cms/connect"""

    def test_connect_success(self, client: TestClient, mock_cms_service: AsyncMock) -> None:
        resp = client.post("/api/v1/cms/connect", json={
            "provider": "wordpress",
            "site_url": "https://blog.testco.com",
            "username": "admin",
            "api_key": "xxxx xxxx xxxx xxxx xxxx xxxx",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is True
        assert data["site_name"] == "Test Blog"
        mock_cms_service.connect.assert_awaited_once()

    def test_connect_missing_api_key(self, client: TestClient) -> None:
        resp = client.post("/api/v1/cms/connect", json={
            "provider": "wordpress",
            "site_url": "https://blog.testco.com",
        })
        assert resp.status_code == 422

    def test_connect_cms_error_returns_connected_false(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        mock_cms_service.connect.return_value = {
            "connected": False,
            "site_name": "",
            "site_url": "",
            "cms_version": "",
            "user_display_name": "",
            "capabilities": [],
            "error": "Invalid credentials",
        }
        resp = client.post("/api/v1/cms/connect", json={
            "provider": "wordpress",
            "site_url": "https://blog.testco.com",
            "username": "admin",
            "api_key": "bad-key",
        })
        assert resp.status_code == 200
        assert resp.json()["connected"] is False
        assert resp.json()["error"] == "Invalid credentials"

    def test_connect_requires_auth(self, public_client: TestClient) -> None:
        resp = public_client.post("/api/v1/cms/connect", json={
            "provider": "wordpress",
            "site_url": "https://x.com",
            "api_key": "k",
        })
        assert resp.status_code in (401, 403)

    def test_connect_viewer_forbidden(self, viewer_client: TestClient) -> None:
        resp = viewer_client.post("/api/v1/cms/connect", json={
            "provider": "wordpress",
            "site_url": "https://x.com",
            "api_key": "k",
        })
        assert resp.status_code == 403

    def test_connect_invalid_provider_raises(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        mock_cms_service.connect.side_effect = ValueError("Unsupported CMS provider: nope")
        resp = client.post("/api/v1/cms/connect", json={
            "provider": "nope",
            "site_url": "https://x.com",
            "api_key": "k",
        })
        assert resp.status_code == 422

    def test_connect_tenant_isolation(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        """Service is called with the authenticated user's company_slug, not body data."""
        resp = client.post("/api/v1/cms/connect", json={
            "provider": "wordpress",
            "site_url": "https://blog.other.com",
            "api_key": "k",
        })
        assert resp.status_code == 200
        call_args = mock_cms_service.connect.call_args
        assert call_args.kwargs.get("company_slug") == "test-co" or call_args[1].get("company_slug") == "test-co"

    def test_connect_invalidates_connection_cache(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        """Connection cache is invalidated after successful connect."""
        with patch("api.routers.cms.invalidate_connection_info") as mock_inv:
            resp = client.post("/api/v1/cms/connect", json={
                "provider": "wordpress",
                "site_url": "https://blog.testco.com",
                "api_key": "k",
            })
        assert resp.status_code == 200
        mock_inv.assert_called_once_with("test-co", "test-co")

    def test_connect_first_time_triggers_auto_sync(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        """First-time connect (last_sync_at=None) fires a background sync."""
        mock_cms_service.get_connection.return_value = _mock_connection(last_sync_at=None)
        with (
            patch("api.tasks.runner.run_cms_sync_task", new_callable=AsyncMock),
            patch("api.routers.cms.invalidate_connection_info"),
        ):
            resp = client.post("/api/v1/cms/connect", json={
                "provider": "wordpress",
                "site_url": "https://blog.testco.com",
                "api_key": "k",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is True
        assert data["sync_task_id"] is not None

    def test_connect_reconnect_skips_auto_sync(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        """Reconnect (last_sync_at set) does NOT fire a background sync."""
        mock_cms_service.get_connection.return_value = _mock_connection(
            last_sync_at=datetime.now(timezone.utc),
        )
        with patch("api.routers.cms.invalidate_connection_info"):
            resp = client.post("/api/v1/cms/connect", json={
                "provider": "wordpress",
                "site_url": "https://blog.testco.com",
                "api_key": "k",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["sync_task_id"] is None

    def test_connect_duplicate_sync_caught(
        self, client: TestClient, mock_cms_service: AsyncMock, app,
    ) -> None:
        """If slug lock is held, auto-sync skips silently (no crash)."""
        from core.services.task_store import TaskConflictError
        mock_cms_service.get_connection.return_value = _mock_connection(last_sync_at=None)
        with (
            patch("api.routers.cms.invalidate_connection_info"),
            patch.object(
                app.state.task_store, "create_task",
                side_effect=TaskConflictError("cms_sync:test-co"),
            ),
        ):
            resp = client.post("/api/v1/cms/connect", json={
                "provider": "wordpress",
                "site_url": "https://blog.testco.com",
                "api_key": "k",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is True
        assert data["sync_task_id"] is None

    def test_connect_failed_no_auto_sync(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        """Failed connect (connected=False) does NOT trigger auto-sync."""
        mock_cms_service.connect.return_value = {
            "connected": False,
            "site_name": "",
            "site_url": "",
            "cms_version": "",
            "user_display_name": "",
            "capabilities": [],
            "error": "Bad creds",
        }
        with patch("api.routers.cms.invalidate_connection_info"):
            resp = client.post("/api/v1/cms/connect", json={
                "provider": "wordpress",
                "site_url": "https://x.com",
                "api_key": "k",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is False
        assert data["sync_task_id"] is None


# ── 2. Get Connection ─────────────────────────────────────────────────


class TestCMSGetConnection:
    """GET /api/v1/cms/connection"""

    def test_get_connection_none(self, client: TestClient) -> None:
        resp = client.get("/api/v1/cms/connection")
        assert resp.status_code == 200
        assert resp.json() is None

    def test_get_connection_exists(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        mock_cms_service.get_connection.return_value = _mock_connection()
        resp = client.get("/api/v1/cms/connection")
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "wordpress"
        assert data["is_active"] is True

    def test_get_connection_requires_auth(self, public_client: TestClient) -> None:
        resp = public_client.get("/api/v1/cms/connection")
        assert resp.status_code in (401, 403)

    def test_get_connection_uses_tenant_slug(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        client.get("/api/v1/cms/connection")
        mock_cms_service.get_connection.assert_awaited_once_with("test-co", tenant_id="test-co")


# ── 3. Disconnect ─────────────────────────────────────────────────────


class TestCMSDisconnect:
    """DELETE /api/v1/cms/connection"""

    def test_disconnect_success(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/cms/connection")
        assert resp.status_code == 200
        assert resp.json()["disconnected"] is True

    def test_disconnect_invalidates_connection_cache(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        """Connection cache is invalidated after disconnect."""
        with patch("api.routers.cms.invalidate_connection_info") as mock_inv:
            resp = client.delete("/api/v1/cms/connection")
        assert resp.status_code == 200
        mock_inv.assert_called_once_with("test-co", "test-co")

    def test_disconnect_no_connection(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        mock_cms_service.disconnect.return_value = False
        resp = client.delete("/api/v1/cms/connection")
        assert resp.status_code == 200
        assert resp.json()["disconnected"] is False

    def test_disconnect_requires_member(self, viewer_client: TestClient) -> None:
        resp = viewer_client.delete("/api/v1/cms/connection")
        assert resp.status_code == 403

    def test_disconnect_requires_auth(self, public_client: TestClient) -> None:
        resp = public_client.delete("/api/v1/cms/connection")
        assert resp.status_code in (401, 403)


# ── 4. Sync ───────────────────────────────────────────────────────────


class TestCMSSync:
    """POST /api/v1/cms/sync"""

    def test_sync_returns_202(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        mock_cms_service.get_connection.return_value = _mock_connection()
        with patch("api.tasks.runner.run_cms_sync_task", new_callable=AsyncMock) as mock_runner:
            with patch("api.routers.cms.asyncio.create_task", return_value=MagicMock()):
                resp = client.post("/api/v1/cms/sync")
        assert resp.status_code == 202
        data = resp.json()
        assert "run_id" in data
        assert data["pipeline"] == "cms_sync"

    def test_sync_no_connection_404(self, client: TestClient) -> None:
        resp = client.post("/api/v1/cms/sync")
        assert resp.status_code == 404

    def test_sync_requires_member(self, viewer_client: TestClient) -> None:
        resp = viewer_client.post("/api/v1/cms/sync")
        assert resp.status_code == 403

    def test_sync_requires_auth(self, public_client: TestClient) -> None:
        resp = public_client.post("/api/v1/cms/sync")
        assert resp.status_code in (401, 403)


# ── 5. Synced Posts ───────────────────────────────────────────────────


class TestCMSSyncedPosts:
    """GET /api/v1/cms/synced-posts"""

    def test_list_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/cms/synced-posts")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_with_data(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        mock_cms_service.list_synced_posts.return_value = [
            _mock_synced_post(),
            _mock_synced_post(title="Second"),
        ]
        resp = client.get("/api/v1/cms/synced-posts")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["title"] == "Synced Post"

    def test_list_stale_only_filter(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        client.get("/api/v1/cms/synced-posts?stale_only=true")
        call_kwargs = mock_cms_service.list_synced_posts.call_args
        assert call_kwargs.kwargs.get("stale_only") is True or call_kwargs[1].get("stale_only") is True

    def test_list_requires_auth(self, public_client: TestClient) -> None:
        resp = public_client.get("/api/v1/cms/synced-posts")
        assert resp.status_code in (401, 403)


# ── 6. Stale Actions ─────────────────────────────────────────────────


class TestCMSStaleActions:
    """GET /api/v1/cms/stale-actions"""

    def test_stale_actions_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/cms/stale-actions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_stale_actions_with_data(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        mock_cms_service.get_stale_actions.return_value = [
            {
                "cms_synced_post_id": str(uuid.uuid4()),
                "cms_post_id": "wp-100",
                "title": "Old Post",
                "url": "https://blog.testco.com/old",
                "staleness_days": 45,
                "description": "Last updated 45 days ago.",
                "queued_for_refresh": False,
            },
        ]
        resp = client.get("/api/v1/cms/stale-actions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["staleness_days"] == 45

    def test_stale_actions_requires_auth(self, public_client: TestClient) -> None:
        resp = public_client.get("/api/v1/cms/stale-actions")
        assert resp.status_code in (401, 403)


# ── 7. Stale → Triage ────────────────────────────────────────────────


class TestCMSStaleToTriage:
    """POST /api/v1/cms/stale-to-triage"""

    def test_stale_to_triage_success(self, client: TestClient) -> None:
        resp = client.post("/api/v1/cms/stale-to-triage", json={
            "cms_synced_post_id": str(uuid.uuid4()),
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "triage"
        assert "brief_id" in data

    def test_stale_to_triage_error(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        mock_cms_service.queue_stale_for_refresh.side_effect = CMSError("Not found")
        resp = client.post("/api/v1/cms/stale-to-triage", json={
            "cms_synced_post_id": str(uuid.uuid4()),
        })
        assert resp.status_code == 400

    def test_stale_to_triage_invalidates_cache(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        """All CMS caches are invalidated after queuing for refresh."""
        with patch("api.routers.cms.invalidate_all_cms_caches") as mock_inv:
            resp = client.post("/api/v1/cms/stale-to-triage", json={
                "cms_synced_post_id": str(uuid.uuid4()),
            })
        assert resp.status_code == 200
        mock_inv.assert_called_once_with("test-co")

    def test_stale_to_triage_requires_member(self, viewer_client: TestClient) -> None:
        resp = viewer_client.post("/api/v1/cms/stale-to-triage", json={
            "cms_synced_post_id": str(uuid.uuid4()),
        })
        assert resp.status_code == 403

    def test_stale_to_triage_requires_auth(self, public_client: TestClient) -> None:
        resp = public_client.post("/api/v1/cms/stale-to-triage", json={
            "cms_synced_post_id": str(uuid.uuid4()),
        })
        assert resp.status_code in (401, 403)


# ── 8. Publish ────────────────────────────────────────────────────────


class TestCMSPublish:
    """POST /api/v1/cms/publish"""

    def test_publish_success(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        mock_cms_service.get_connection.return_value = _mock_connection()
        resp = client.post("/api/v1/cms/publish", json={
            "brief_id": "brief-001",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["cms_post_id"] == "wp-123"
        assert data["title"] == "Test Post"

    def test_publish_no_connection_404(self, client: TestClient) -> None:
        resp = client.post("/api/v1/cms/publish", json={
            "brief_id": "brief-001",
        })
        assert resp.status_code == 404

    def test_publish_brief_not_found(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        mock_cms_service.get_connection.return_value = _mock_connection()
        mock_cms_service.publish_brief.side_effect = CMSError("No final.md found")
        resp = client.post("/api/v1/cms/publish", json={
            "brief_id": "missing-brief",
        })
        assert resp.status_code == 400

    def test_publish_cms_auth_error_maps_to_401(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        mock_cms_service.get_connection.return_value = _mock_connection()
        mock_cms_service.publish_brief.side_effect = CMSAuthError("Insufficient permissions")
        resp = client.post("/api/v1/cms/publish", json={
            "brief_id": "brief-001",
        })
        assert resp.status_code == 401

    def test_publish_with_categories(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        mock_cms_service.get_connection.return_value = _mock_connection()
        resp = client.post("/api/v1/cms/publish", json={
            "brief_id": "brief-001",
            "categories": ["Marketing", "Product"],
        })
        assert resp.status_code == 200
        call_kwargs = mock_cms_service.publish_brief.call_args.kwargs
        assert call_kwargs.get("category_names") == ["Marketing", "Product"]

    def test_publish_with_slug_override(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        mock_cms_service.get_connection.return_value = _mock_connection()
        resp = client.post("/api/v1/cms/publish", json={
            "brief_id": "brief-001",
            "slug_override": "custom-slug",
        })
        assert resp.status_code == 200
        call_kwargs = mock_cms_service.publish_brief.call_args.kwargs
        assert call_kwargs.get("slug_override") == "custom-slug"

    def test_publish_with_publish_metadata(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        mock_cms_service.get_connection.return_value = _mock_connection()
        resp = client.post("/api/v1/cms/publish", json={
            "brief_id": "brief-abc123",
            "effective_slug": "test-co",
            "status": "publish",
            "publish_metadata": {
                "slug": "no-code-web-development-enterprise-overview",
                "meta_title": "No-Code Web Development in the Enterprise | Deep Presence",
                "meta_description": "A plain-English guide to no-code for enterprise teams.",
                "canonical_url": "https://blogs.example.com/no-code-web-development-enterprise-overview",
                "schema_markup": True,
                "publish_date": "2026-04-11",
                "author": "Aryan Keshri",
                "tags": ["no-code", "enterprise"],
            },
        })

        assert resp.status_code == 200
        call_kwargs = mock_cms_service.publish_brief.call_args.kwargs
        assert call_kwargs["publish_metadata"].slug == "no-code-web-development-enterprise-overview"
        assert call_kwargs["publish_metadata"].meta_title == "No-Code Web Development in the Enterprise | Deep Presence"
        assert call_kwargs["publish_metadata"].canonical_url == "https://blogs.example.com/no-code-web-development-enterprise-overview"
        assert call_kwargs["publish_metadata"].tags == ["no-code", "enterprise"]

    def test_publish_with_product_slug(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        mock_cms_service.get_connection.return_value = _mock_connection()
        resp = client.post("/api/v1/cms/publish", json={
            "brief_id": "brief-001",
            "product_slug": "ramp-cards",
        })
        assert resp.status_code == 200
        call_kwargs = mock_cms_service.publish_brief.call_args.kwargs
        assert call_kwargs.get("effective_slug") == "test-co__ramp-cards"

    def test_publish_invalidates_ga4_caches(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        mock_cms_service.get_connection.return_value = _mock_connection()
        with patch("api.routers.cms.invalidate_all_ga4_caches") as mock_inv:
            resp = client.post("/api/v1/cms/publish", json={
                "brief_id": "brief-001",
            })
        assert resp.status_code == 200
        mock_inv.assert_called_once_with("test-co")


# ── 9. Refresh ────────────────────────────────────────────────────────


class TestCMSRefresh:
    """POST /api/v1/cms/refresh/{cms_post_id}"""

    def test_refresh_success(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        mock_cms_service.get_connection.return_value = _mock_connection()
        resp = client.post("/api/v1/cms/refresh/wp-456", json={
            "brief_id": "refresh-001",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated Post"

    def test_refresh_no_connection_404(self, client: TestClient) -> None:
        resp = client.post("/api/v1/cms/refresh/wp-456", json={
            "brief_id": "refresh-001",
        })
        assert resp.status_code == 404

    def test_refresh_brief_not_found(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        mock_cms_service.get_connection.return_value = _mock_connection()
        mock_cms_service.refresh_post.side_effect = CMSError("No final.md")
        resp = client.post("/api/v1/cms/refresh/wp-456", json={
            "brief_id": "missing",
        })
        assert resp.status_code == 400

    def test_refresh_requires_member(self, viewer_client: TestClient) -> None:
        resp = viewer_client.post("/api/v1/cms/refresh/wp-456", json={
            "brief_id": "r",
        })
        assert resp.status_code == 403

    def test_refresh_invalidates_ga4_caches(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        mock_cms_service.get_connection.return_value = _mock_connection()
        with patch("api.routers.cms.invalidate_all_ga4_caches") as mock_inv:
            resp = client.post("/api/v1/cms/refresh/wp-456", json={
                "brief_id": "refresh-001",
            })
        assert resp.status_code == 200
        mock_inv.assert_called_once_with("test-co")

    def test_refresh_requires_auth(self, public_client: TestClient) -> None:
        resp = public_client.post("/api/v1/cms/refresh/wp-456", json={
            "brief_id": "r",
        })
        assert resp.status_code in (401, 403)


# ── 10. Publish History ──────────────────────────────────────────────


class TestCMSPublishHistory:
    """GET /api/v1/cms/publish-history"""

    def test_history_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/cms/publish-history")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_history_with_data(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        mock_cms_service.list_publish_history.return_value = [
            _mock_publish_record(),
        ]
        resp = client.get("/api/v1/cms/publish-history")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["action"] == "create"

    def test_history_pagination(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        client.get("/api/v1/cms/publish-history?limit=10&offset=5")
        call_kwargs = mock_cms_service.list_publish_history.call_args
        assert call_kwargs.kwargs.get("limit") == 10 or call_kwargs[1].get("limit") == 10

    def test_history_requires_auth(self, public_client: TestClient) -> None:
        resp = public_client.get("/api/v1/cms/publish-history")
        assert resp.status_code in (401, 403)


# ── 11. Categories ────────────────────────────────────────────────────


class TestCMSCategories:
    """GET /api/v1/cms/categories"""

    def test_categories_success(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        mock_cms_service.get_connection.return_value = _mock_connection()
        mock_cms_service.list_categories.return_value = [
            CMSCategory(cms_id="1", name="Marketing", slug="marketing", post_count=5),
            CMSCategory(cms_id="2", name="Product", slug="product", post_count=3),
        ]
        resp = client.get("/api/v1/cms/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["name"] == "Marketing"

    def test_categories_no_connection_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/cms/categories")
        assert resp.status_code == 404

    def test_categories_requires_auth(self, public_client: TestClient) -> None:
        resp = public_client.get("/api/v1/cms/categories")
        assert resp.status_code in (401, 403)


# ── 12–14. Webflow configure ──────────────────────────────────────────


class TestWebflowConfigure:
    """Webflow-specific CMS configure endpoints."""

    def _webflow_connection(self):
        return _mock_connection(provider=MagicMock(value="webflow"))

    def test_list_collections_success(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        mock_cms_service.get_connection.return_value = self._webflow_connection()
        mock_cms_service.list_webflow_collections.return_value = [
            {
                "collection_id": "coll-1",
                "collection_slug": "blog",
                "display_name": "Blog Posts",
                "singular_name": "Blog Post",
            }
        ]
        resp = client.get("/api/v1/cms/webflow/collections")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["collection_id"] == "coll-1"

    def test_list_collections_requires_webflow(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        mock_cms_service.get_connection.return_value = _mock_connection()
        resp = client.get("/api/v1/cms/webflow/collections")
        assert resp.status_code == 422

    def test_collection_fields_success(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        mock_cms_service.get_connection.return_value = self._webflow_connection()
        resp = client.get("/api/v1/cms/webflow/collections/coll-1/fields")
        assert resp.status_code == 200
        data = resp.json()
        assert data["collection_id"] == "coll-1"
        assert data["suggested_mapping"]["body_field"] == "post-body"

    def test_configure_success(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        mock_cms_service.get_connection.return_value = self._webflow_connection()
        with (
            patch("api.routers.cms.invalidate_connection_info"),
            patch("api.routers.cms._maybe_trigger_cms_sync", new_callable=AsyncMock) as mock_sync,
        ):
            mock_sync.return_value = "task-123"
            resp = client.post("/api/v1/cms/webflow/configure", json={
                "site_id": "site-1",
                "collections": [
                    {
                        "collection_id": "coll-1",
                        "enabled": True,
                        "field_mapping": {
                            "title_field": "name",
                            "slug_field": "slug",
                            "body_field": "post-body",
                        },
                    }
                ],
                "trigger_sync": True,
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["configured"] is True
        assert data["sync_task_id"] == "task-123"
        mock_cms_service.configure_webflow.assert_awaited_once()

    def test_configure_requires_member(self, viewer_client: TestClient) -> None:
        resp = viewer_client.post("/api/v1/cms/webflow/configure", json={
            "collections": [],
        })
        assert resp.status_code == 403

    def test_connect_passes_provider_config(
        self, client: TestClient, mock_cms_service: AsyncMock,
    ) -> None:
        with patch("api.routers.cms.invalidate_connection_info"):
            resp = client.post("/api/v1/cms/connect", json={
                "provider": "webflow",
                "site_url": "https://marketing.example.com",
                "api_key": "wf-token",
                "provider_config": {"site_id": "site-1"},
            })
        assert resp.status_code == 200
        call_kwargs = mock_cms_service.connect.call_args.kwargs
        assert call_kwargs.get("provider_config") == {"site_id": "site-1"}
