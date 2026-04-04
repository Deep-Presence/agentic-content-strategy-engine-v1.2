"""Tests for Content Inventory API endpoints.

Content Inventory service is mocked via ``app.state.content_inventory_service``
pre-built override (bypasses DI).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest
from fastapi.testclient import TestClient

from core.db.enums import ContentIngestionSource


# ── Helpers ───────────────────────────────────────────────────────────


def _mock_inventory_model(**overrides):
    """Return a MagicMock resembling ContentInventoryModel."""
    m = MagicMock()
    m.id = overrides.get("id", uuid.uuid4())
    m.url = overrides.get("url", "https://example.com/page")
    m.url_normalized = overrides.get("url_normalized", "https://example.com/page")
    m.title = overrides.get("title", "Test Page")
    m.h1_text = overrides.get("h1_text", "")
    m.meta_description = overrides.get("meta_description", "")
    m.content_preview = overrides.get("content_preview", "")
    m.word_count = overrides.get("word_count", 500)
    m.ingestion_source = overrides.get(
        "ingestion_source", ContentIngestionSource.site_audit_crawl
    )
    m.categories = overrides.get("categories", ["tech"])
    m.tags = overrides.get("tags", [])
    m.content_type_detected = overrides.get("content_type_detected", "blog_post")
    m.has_faq_section = overrides.get("has_faq_section", False)
    m.has_schema_markup = overrides.get("has_schema_markup", False)
    m.heading_count = overrides.get("heading_count", 5)
    m.embedding = overrides.get("embedding", None)
    m.published_at = overrides.get("published_at", datetime.now(timezone.utc))
    m.content_modified_at = overrides.get("content_modified_at", None)
    m.last_crawled_at = overrides.get("last_crawled_at", None)
    m.created_at = overrides.get("created_at", datetime.now(timezone.utc))
    m.updated_at = overrides.get("updated_at", datetime.now(timezone.utc))
    # company_id for tenant isolation
    m.company_id = overrides.get("company_id", None)
    return m


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def mock_inventory_service(test_company):
    """Pre-built ContentInventoryService mock, set on app.state."""
    svc = AsyncMock()

    # Mock the _repo attribute
    repo = AsyncMock()
    repo.get_by_company = AsyncMock(return_value=([], 0))
    repo.get_stats = AsyncMock(return_value={
        "total_pages": 0,
        "by_source": {},
        "avg_word_count": 0.0,
        "pages_with_embeddings": 0,
        "oldest_content": None,
        "newest_content": None,
    })
    repo.get_by_id = AsyncMock(return_value=None)
    repo.delete_by_company = AsyncMock(return_value=0)
    repo.upsert_page = AsyncMock(return_value=_mock_inventory_model(
        company_id=test_company.id,
    ))
    svc._repo = repo

    # Service methods
    svc.ingest_from_csv = AsyncMock(return_value={
        "imported": 0, "skipped": 0, "errors": [],
    })
    svc.generate_embeddings_for_company = AsyncMock(return_value=0)

    return svc


@pytest.fixture
def app(app, mock_inventory_service):
    """Extend the base app fixture with inventory service mock."""
    app.state.content_inventory_service = mock_inventory_service
    return app


# ── 1. List Inventory ─────────────────────────────────────────────────


class TestListInventory:
    """GET /api/v1/content-inventory/"""

    def test_empty_list(self, client: TestClient):
        resp = client.get("/api/v1/content-inventory/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_with_items(self, client: TestClient, mock_inventory_service, test_company):
        models = [_mock_inventory_model(company_id=test_company.id) for _ in range(3)]
        mock_inventory_service._repo.get_by_company.return_value = (models, 3)

        resp = client.get("/api/v1/content-inventory/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 3
        assert data["total"] == 3

    def test_pagination_params(self, client: TestClient, mock_inventory_service):
        resp = client.get("/api/v1/content-inventory/?page=2&page_size=10")
        assert resp.status_code == 200
        # Verify offset calculation
        mock_inventory_service._repo.get_by_company.assert_called_once()
        call_kwargs = mock_inventory_service._repo.get_by_company.call_args
        assert call_kwargs.kwargs.get("offset") == 10  # (page-1) * page_size
        assert call_kwargs.kwargs.get("limit") == 10

    def test_page_size_capped(self, client: TestClient, mock_inventory_service):
        resp = client.get("/api/v1/content-inventory/?page_size=999")
        assert resp.status_code == 200
        call_kwargs = mock_inventory_service._repo.get_by_company.call_args
        assert call_kwargs.kwargs.get("limit") == 200  # hard cap

    def test_source_filter(self, client: TestClient, mock_inventory_service):
        resp = client.get("/api/v1/content-inventory/?source=cms_sync")
        assert resp.status_code == 200
        call_kwargs = mock_inventory_service._repo.get_by_company.call_args
        assert call_kwargs.kwargs.get("ingestion_source") == ContentIngestionSource.cms_sync

    def test_invalid_source_filter(self, client: TestClient):
        resp = client.get("/api/v1/content-inventory/?source=invalid_source")
        assert resp.status_code == 400
        assert "Invalid source filter" in resp.json()["detail"]

    def test_unauthenticated(self, public_client: TestClient):
        resp = public_client.get("/api/v1/content-inventory/")
        assert resp.status_code == 401


# ── 2. Stats ──────────────────────────────────────────────────────────


class TestGetStats:
    """GET /api/v1/content-inventory/stats"""

    def test_empty_stats(self, client: TestClient):
        resp = client.get("/api/v1/content-inventory/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_pages"] == 0

    def test_populated_stats(self, client: TestClient, mock_inventory_service):
        mock_inventory_service._repo.get_stats.return_value = {
            "total_pages": 150,
            "by_source": {"site_audit_crawl": 100, "cms_sync": 50},
            "avg_word_count": 1250.5,
            "pages_with_embeddings": 130,
            "oldest_content": None,
            "newest_content": None,
        }
        resp = client.get("/api/v1/content-inventory/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_pages"] == 150
        assert data["by_source"]["cms_sync"] == 50

    def test_unauthenticated(self, public_client: TestClient):
        resp = public_client.get("/api/v1/content-inventory/stats")
        assert resp.status_code == 401


# ── 3. Single Record ─────────────────────────────────────────────────


class TestGetSingleItem:
    """GET /api/v1/content-inventory/{inventory_id}"""

    def test_found(self, client: TestClient, mock_inventory_service, test_company):
        inv_id = uuid.uuid4()
        model = _mock_inventory_model(id=inv_id, company_id=test_company.id)
        mock_inventory_service._repo.get_by_id.return_value = model

        resp = client.get(f"/api/v1/content-inventory/{inv_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == str(inv_id)

    def test_not_found(self, client: TestClient, mock_inventory_service):
        mock_inventory_service._repo.get_by_id.return_value = None
        resp = client.get(f"/api/v1/content-inventory/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_tenant_isolation(self, client: TestClient, mock_inventory_service):
        """Record belongs to a different company → 404."""
        model = _mock_inventory_model(company_id=uuid.uuid4())  # Different company
        mock_inventory_service._repo.get_by_id.return_value = model

        resp = client.get(f"/api/v1/content-inventory/{model.id}")
        assert resp.status_code == 404

    def test_invalid_uuid_returns_400(self, client: TestClient, mock_inventory_service):
        """Non-UUID inventory_id → 400, not 500."""
        mock_inventory_service._repo.get_by_id.side_effect = ValueError("badly formed UUID")
        resp = client.get("/api/v1/content-inventory/not-a-uuid")
        assert resp.status_code == 400
        assert "Invalid inventory ID" in resp.json()["detail"]
        mock_inventory_service._repo.get_by_id.side_effect = None  # reset


# ── 4. CSV Import ────────────────────────────────────────────────────


class TestCSVImport:
    """POST /api/v1/content-inventory/import"""

    def test_valid_csv(self, client: TestClient, mock_inventory_service):
        mock_inventory_service.ingest_from_csv.return_value = {
            "imported": 3, "skipped": 1, "errors": ["Row 4: missing url"],
        }
        csv_content = "url,title\nhttps://a.com,A\nhttps://b.com,B\nhttps://c.com,C\n,Missing"
        resp = client.post(
            "/api/v1/content-inventory/import",
            files={"file": ("test.csv", csv_content, "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 3

    def test_empty_csv(self, client: TestClient, mock_inventory_service):
        resp = client.post(
            "/api/v1/content-inventory/import",
            files={"file": ("empty.csv", "", "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 0

    def test_viewer_denied(self, viewer_client: TestClient):
        resp = viewer_client.post(
            "/api/v1/content-inventory/import",
            files={"file": ("test.csv", "url,title\nhttps://a.com,A", "text/csv")},
        )
        assert resp.status_code == 403

    def test_unauthenticated(self, public_client: TestClient):
        resp = public_client.post(
            "/api/v1/content-inventory/import",
            files={"file": ("test.csv", "url,title", "text/csv")},
        )
        assert resp.status_code == 401


# ── 5. Single URL Import ────────────────────────────────────────────


class TestSingleURLImport:
    """POST /api/v1/content-inventory/import-url"""

    def test_valid(self, client: TestClient, mock_inventory_service, test_company):
        model = _mock_inventory_model(company_id=test_company.id)
        mock_inventory_service._repo.upsert_page.return_value = model

        resp = client.post(
            "/api/v1/content-inventory/import-url",
            json={"url": "https://example.com/new-page", "title": "New Page"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Test Page"  # From mock

    def test_empty_url(self, client: TestClient):
        resp = client.post(
            "/api/v1/content-inventory/import-url",
            json={"url": "  ", "title": "No URL"},
        )
        assert resp.status_code == 400
        assert "URL is required" in resp.json()["detail"]

    def test_viewer_denied(self, viewer_client: TestClient):
        resp = viewer_client.post(
            "/api/v1/content-inventory/import-url",
            json={"url": "https://example.com"},
        )
        assert resp.status_code == 403


# ── 6. Generate Embeddings ───────────────────────────────────────────


class TestGenerateEmbeddings:
    """POST /api/v1/content-inventory/generate-embeddings"""

    def test_success(self, client: TestClient, mock_inventory_service):
        mock_inventory_service.generate_embeddings_for_company.return_value = 42
        resp = client.post("/api/v1/content-inventory/generate-embeddings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["generated"] == 42

    def test_no_records(self, client: TestClient, mock_inventory_service):
        mock_inventory_service.generate_embeddings_for_company.return_value = 0
        resp = client.post("/api/v1/content-inventory/generate-embeddings")
        assert resp.status_code == 200
        assert "already have embeddings" in resp.json()["message"]

    def test_viewer_denied(self, viewer_client: TestClient):
        resp = viewer_client.post("/api/v1/content-inventory/generate-embeddings")
        assert resp.status_code == 403


# ── 7. Delete All ───────────────────────────────────────────────────


class TestDeleteInventory:
    """DELETE /api/v1/content-inventory/"""

    def test_superuser_only(self, superuser_client: TestClient, mock_inventory_service):
        mock_inventory_service._repo.delete_by_company.return_value = 50
        resp = superuser_client.delete("/api/v1/content-inventory/")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 50

    def test_member_denied(self, client: TestClient):
        resp = client.delete("/api/v1/content-inventory/")
        assert resp.status_code == 403

    def test_viewer_denied(self, viewer_client: TestClient):
        resp = viewer_client.delete("/api/v1/content-inventory/")
        assert resp.status_code == 403

    def test_unauthenticated(self, public_client: TestClient):
        resp = public_client.delete("/api/v1/content-inventory/")
        assert resp.status_code == 401
