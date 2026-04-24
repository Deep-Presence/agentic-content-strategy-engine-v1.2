"""DB integration tests for ContentInventoryRepository.

Requires TEST_DATABASE_URL to be set. Tests use savepoint-based rollback
via the ``db_session`` fixture from ``conftest.py``.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from core.db.enums import ContentIngestionSource
from core.db.models.content_inventory import ContentInventoryModel
from core.db.repositories.content_inventory_repo import ContentInventoryRepository

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL", ""),
    reason="TEST_DATABASE_URL not set",
)


@pytest_asyncio.fixture
async def repo(db_session):
    """Return a ContentInventoryRepository bound to the test session."""
    return ContentInventoryRepository(db_session)


@pytest_asyncio.fixture
async def sample_inventory_page(db_session, sample_company, repo):
    """Create and return a sample content inventory record."""
    model = await repo.upsert_page(
        company_id=sample_company.id,
        effective_slug="test-co",
        url="https://example.com/blog/existing-post",
        title="Existing Post",
        ingestion_source=ContentIngestionSource.site_audit_crawl,
        ingestion_run_id=uuid.uuid4(),
        h1_text="Existing Post Title",
        meta_description="A test description",
        content_preview="First 500 chars of content...",
        word_count=1200,
        has_faq_section=True,
        heading_count=5,
        content_type_detected="blog_post",
    )
    return model


# ── upsert_page ───────────────────────────────────────────────────


class TestUpsertPage:
    """Tests for single-page upsert."""

    @pytest.mark.asyncio
    async def test_insert_new_page(self, repo, sample_company):
        model = await repo.upsert_page(
            company_id=sample_company.id,
            effective_slug="test-co",
            url="https://example.com/blog/new",
            title="New Post",
            ingestion_source=ContentIngestionSource.site_audit_crawl,
        )
        assert model is not None
        assert model.title == "New Post"
        assert model.url_normalized == "https://example.com/blog/new"
        assert model.ingestion_source == ContentIngestionSource.site_audit_crawl

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(self, repo, sample_company):
        """Second upsert with same URL should update, not duplicate."""
        url = "https://example.com/blog/dedup-test"

        m1 = await repo.upsert_page(
            company_id=sample_company.id,
            effective_slug="test-co",
            url=url,
            title="Original Title",
            ingestion_source=ContentIngestionSource.site_audit_crawl,
        )
        m2 = await repo.upsert_page(
            company_id=sample_company.id,
            effective_slug="test-co",
            url=url,
            title="Updated Title",
            ingestion_source=ContentIngestionSource.cms_sync,
        )
        assert m2.title == "Updated Title"
        assert m2.ingestion_source == ContentIngestionSource.cms_sync

    @pytest.mark.asyncio
    async def test_url_normalization_in_upsert(self, repo, sample_company):
        """URLs with different query params / www / http should dedup."""
        m1 = await repo.upsert_page(
            company_id=sample_company.id,
            effective_slug="test-co",
            url="http://www.example.com/page?ref=social",
            title="Page V1",
            ingestion_source=ContentIngestionSource.site_audit_crawl,
        )
        m2 = await repo.upsert_page(
            company_id=sample_company.id,
            effective_slug="test-co",
            url="https://example.com/page",
            title="Page V2",
            ingestion_source=ContentIngestionSource.cms_sync,
        )
        # Should update same record due to URL normalization
        assert m2.title == "Page V2"


# ── bulk_upsert_from_crawl ────────────────────────────────────────


class TestBulkUpsert:
    """Tests for batch upsert from site audit crawl."""

    @pytest.mark.asyncio
    async def test_bulk_insert(self, repo, sample_company):
        from core.content_inventory.models import CrawledPageData

        pages = [
            CrawledPageData(url="https://example.com/p1", title="Page 1", word_count=500),
            CrawledPageData(url="https://example.com/p2", title="Page 2", word_count=800),
            CrawledPageData(url="https://example.com/p3", title="Page 3", word_count=1000),
        ]
        count = await repo.bulk_upsert_from_crawl(
            company_id=sample_company.id,
            effective_slug="test-co",
            ingestion_run_id=uuid.uuid4(),
            pages=pages,
        )
        assert count == 3

    @pytest.mark.asyncio
    async def test_bulk_upsert_handles_duplicates(self, repo, sample_company):
        from core.content_inventory.models import CrawledPageData

        run_id = uuid.uuid4()
        pages = [CrawledPageData(url="https://example.com/dup", title="V1")]
        await repo.bulk_upsert_from_crawl(
            company_id=sample_company.id,
            effective_slug="test-co",
            ingestion_run_id=run_id,
            pages=pages,
        )
        # Second upsert with updated title
        pages2 = [CrawledPageData(url="https://example.com/dup", title="V2")]
        count = await repo.bulk_upsert_from_crawl(
            company_id=sample_company.id,
            effective_slug="test-co",
            ingestion_run_id=run_id,
            pages=pages2,
        )
        assert count == 1

    @pytest.mark.asyncio
    async def test_bulk_empty_list(self, repo, sample_company):
        count = await repo.bulk_upsert_from_crawl(
            company_id=sample_company.id,
            effective_slug="test-co",
            ingestion_run_id=uuid.uuid4(),
            pages=[],
        )
        assert count == 0


# ── get_by_company ────────────────────────────────────────────────


class TestGetByCompany:
    """Tests for paginated listing."""

    @pytest.mark.asyncio
    async def test_list_empty(self, repo, sample_company):
        items, total = await repo.get_by_company(sample_company.id)
        assert total == 0
        assert items == []

    @pytest.mark.asyncio
    async def test_list_with_items(self, repo, sample_company, sample_inventory_page):
        items, total = await repo.get_by_company(sample_company.id)
        assert total >= 1
        assert any(i.title == "Existing Post" for i in items)

    @pytest.mark.asyncio
    async def test_filter_by_source(self, repo, sample_company, sample_inventory_page):
        items, total = await repo.get_by_company(
            sample_company.id,
            ingestion_source=ContentIngestionSource.site_audit_crawl,
        )
        assert total >= 1

        items_csv, total_csv = await repo.get_by_company(
            sample_company.id,
            ingestion_source=ContentIngestionSource.csv_import,
        )
        assert total_csv == 0

    @pytest.mark.asyncio
    async def test_pagination(self, repo, sample_company):
        from core.content_inventory.models import CrawledPageData

        pages = [
            CrawledPageData(url=f"https://example.com/pag-{i}", title=f"P{i}")
            for i in range(5)
        ]
        await repo.bulk_upsert_from_crawl(
            company_id=sample_company.id,
            effective_slug="test-co",
            ingestion_run_id=uuid.uuid4(),
            pages=pages,
        )
        items, total = await repo.get_by_company(
            sample_company.id, limit=2, offset=0
        )
        assert total == 5


class TestFindSimilarBatch:
    """Tests for batched similarity retrieval."""

    @pytest.mark.asyncio
    async def test_returns_top_matches_per_query_key(self, repo, sample_company):
        page_a = await repo.upsert_page(
            company_id=sample_company.id,
            effective_slug="test-co",
            url="https://example.com/a",
            title="Page A",
            ingestion_source=ContentIngestionSource.site_audit_crawl,
        )
        page_b = await repo.upsert_page(
            company_id=sample_company.id,
            effective_slug="test-co",
            url="https://example.com/b",
            title="Page B",
            ingestion_source=ContentIngestionSource.site_audit_crawl,
        )

        emb_a = [1.0] + ([0.0] * 1535)
        emb_b = [0.0, 1.0] + ([0.0] * 1534)
        await repo.update_embeddings_batch(
            [
                (page_a.id, emb_a),
                (page_b.id, emb_b),
            ]
        )

        results = await repo.find_similar_batch(
            sample_company.id,
            {
                "query-a": emb_a,
                "query-b": emb_b,
            },
            threshold=0.5,
            limit=1,
        )

        assert results["query-a"][0]["inventory_id"] == page_a.id
        assert results["query-a"][0]["url"] == "https://example.com/a"
        assert results["query-b"][0]["inventory_id"] == page_b.id
        assert results["query-b"][0]["url"] == "https://example.com/b"
        assert len(items) == 2


# ── get_stats ─────────────────────────────────────────────────────


class TestGetStats:
    """Tests for aggregate stats."""

    @pytest.mark.asyncio
    async def test_stats_empty(self, repo, sample_company):
        stats = await repo.get_stats(sample_company.id)
        assert stats["total_pages"] == 0
        assert stats["by_source"] == {}

    @pytest.mark.asyncio
    async def test_stats_with_data(self, repo, sample_company, sample_inventory_page):
        stats = await repo.get_stats(sample_company.id)
        assert stats["total_pages"] >= 1
        assert "site_audit_crawl" in str(stats["by_source"])


# ── delete_by_company ─────────────────────────────────────────────


class TestDeleteByCompany:
    """Tests for bulk deletion."""

    @pytest.mark.asyncio
    async def test_delete_returns_count(self, repo, sample_company, sample_inventory_page):
        count = await repo.delete_by_company(sample_company.id)
        assert count >= 1

    @pytest.mark.asyncio
    async def test_delete_empty_returns_zero(self, repo, sample_company):
        count = await repo.delete_by_company(sample_company.id)
        assert count == 0
