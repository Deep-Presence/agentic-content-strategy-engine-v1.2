"""Tests for content inventory API schemas."""
from __future__ import annotations

from datetime import datetime, timezone

from api.schemas.content_inventory import (
    ContentInventoryItem,
    ContentInventoryListResponse,
    ContentInventoryStats,
    CSVImportResponse,
    GenerateEmbeddingsResponse,
    SingleURLImportRequest,
)


class TestContentInventoryItem:
    """ContentInventoryItem response schema."""

    def test_defaults(self):
        item = ContentInventoryItem()
        assert item.id == ""
        assert item.url == ""
        assert item.word_count == 0
        assert item.categories == []
        assert item.tags == []
        assert item.has_embedding is False
        assert item.published_at is None
        assert item.created_at is None

    def test_full_construction(self):
        now = datetime.now(timezone.utc)
        item = ContentInventoryItem(
            id="abc-123",
            url="https://example.com/blog",
            url_normalized="https://example.com/blog",
            title="My Blog",
            h1_text="Blog Title",
            meta_description="A blog post",
            content_preview="First 500 chars...",
            word_count=1500,
            ingestion_source="site_audit_crawl",
            categories=["tech"],
            tags=["ai", "ml"],
            content_type_detected="blog_post",
            has_faq_section=True,
            has_schema_markup=True,
            heading_count=8,
            has_embedding=True,
            published_at=now,
            content_modified_at=now,
            created_at=now,
            updated_at=now,
        )
        assert item.id == "abc-123"
        assert item.word_count == 1500
        assert item.has_embedding is True
        assert item.categories == ["tech"]

    def test_json_roundtrip(self):
        item = ContentInventoryItem(
            id="id-1",
            url="https://example.com",
            title="Test",
            ingestion_source="manual",
        )
        data = item.model_dump(mode="json")
        restored = ContentInventoryItem(**data)
        assert restored.id == item.id
        assert restored.ingestion_source == "manual"

    def test_no_shared_mutable_defaults(self):
        """categories and tags should not share a mutable default."""
        a = ContentInventoryItem()
        b = ContentInventoryItem()
        a.categories.append("x")
        assert b.categories == []


class TestContentInventoryListResponse:
    """ContentInventoryListResponse — paginated list."""

    def test_defaults(self):
        resp = ContentInventoryListResponse()
        assert resp.items == []
        assert resp.total == 0
        assert resp.page == 1
        assert resp.page_size == 50

    def test_with_items(self):
        items = [ContentInventoryItem(id=f"id-{i}") for i in range(3)]
        resp = ContentInventoryListResponse(
            items=items, total=100, page=2, page_size=25
        )
        assert len(resp.items) == 3
        assert resp.total == 100
        assert resp.page == 2


class TestContentInventoryStats:
    """ContentInventoryStats — aggregate stats."""

    def test_defaults(self):
        stats = ContentInventoryStats()
        assert stats.total_pages == 0
        assert stats.by_source == {}
        assert stats.avg_word_count == 0.0
        assert stats.pages_with_embeddings == 0
        assert stats.oldest_content is None

    def test_full(self):
        stats = ContentInventoryStats(
            total_pages=150,
            by_source={"site_audit_crawl": 100, "cms_sync": 50},
            avg_word_count=1250.5,
            pages_with_embeddings=130,
            oldest_content=datetime(2024, 1, 1, tzinfo=timezone.utc),
            newest_content=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
        assert stats.total_pages == 150
        assert stats.by_source["cms_sync"] == 50


class TestCSVImportResponse:
    """CSVImportResponse — CSV import result."""

    def test_defaults(self):
        resp = CSVImportResponse()
        assert resp.imported == 0
        assert resp.skipped == 0
        assert resp.errors == []

    def test_with_errors(self):
        resp = CSVImportResponse(
            imported=5, skipped=2, errors=["Row 3: missing url"]
        )
        assert len(resp.errors) == 1


class TestSingleURLImportRequest:
    """SingleURLImportRequest — URL import request."""

    def test_url_required(self):
        req = SingleURLImportRequest(url="https://example.com")
        assert req.url == "https://example.com"
        assert req.title == ""

    def test_with_title(self):
        req = SingleURLImportRequest(url="https://example.com", title="My Page")
        assert req.title == "My Page"


class TestGenerateEmbeddingsResponse:
    """GenerateEmbeddingsResponse — embedding generation result."""

    def test_defaults(self):
        resp = GenerateEmbeddingsResponse()
        assert resp.generated == 0
        assert resp.message == ""

    def test_with_count(self):
        resp = GenerateEmbeddingsResponse(
            generated=42, message="Generated 42 embeddings"
        )
        assert resp.generated == 42
