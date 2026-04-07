"""Tests for ContentInventoryService — all methods with mocked repo + embeddings."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.content_inventory.models import (
    CannibalizationMatch,
    CrawledPageData,
    ExistingCoverageResult,
)
from core.db.enums import ContentIngestionSource
from core.services.content_inventory_service import ContentInventoryService


def _make_repo() -> AsyncMock:
    """Create a mocked ContentInventoryRepository."""
    repo = AsyncMock()
    repo.upsert_page = AsyncMock()
    repo.bulk_upsert_from_crawl = AsyncMock(return_value=5)
    repo.update_embeddings_batch = AsyncMock(return_value=3)
    repo.find_similar = AsyncMock(return_value=[])
    repo.get_pages_missing_embeddings = AsyncMock(return_value=[])
    repo.get_by_company = AsyncMock(return_value=([], 0))
    repo.get_stats = AsyncMock(return_value={"total_pages": 0})
    repo.delete_by_company = AsyncMock(return_value=0)
    return repo


def _make_service(repo: AsyncMock | None = None) -> ContentInventoryService:
    return ContentInventoryService(inventory_repo=repo or _make_repo())


def _make_page_audit_result(**overrides):
    """Create a mock PageAuditResult."""
    defaults = {
        "url": "https://example.com/blog/post",
        "title": "Test Post",
        "h1_text": "Test H1",
        "meta_description": "Test description",
        "word_count": 1000,
        "headings": [{"tag": "h2", "text": "Section 1"}],
        "aeo": SimpleNamespace(content_patterns={"faq_section": True}),
        "schema_result": SimpleNamespace(schemas_found=["Article"]),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_discovery_output(urls_with_html=None, sitemap_lastmod_map=None):
    """Create a mock S1DiscoveryOutput."""
    return SimpleNamespace(
        pages_with_html=urls_with_html or [],
        sitemap_lastmod_map=sitemap_lastmod_map or {},
    )


# ── ingest_from_site_audit ────────────────────────────────────────


class TestIngestFromSiteAudit:
    """Service: ingest_from_site_audit"""

    @pytest.mark.asyncio
    async def test_builds_crawled_pages_and_calls_bulk_upsert(self):
        repo = _make_repo()
        repo.bulk_upsert_from_crawl = AsyncMock(return_value=2)
        svc = _make_service(repo)

        company_id = uuid.uuid4()
        run_id = uuid.uuid4()

        discovery = _make_discovery_output(
            urls_with_html=[
                ("https://example.com/p1", "<html>..."),
                ("https://example.com/p2", "<html>..."),
            ],
            sitemap_lastmod_map={
                "https://example.com/p1": "2026-01-01T00:00:00Z",
            },
        )
        page_results = [
            _make_page_audit_result(url="https://example.com/p1"),
            _make_page_audit_result(url="https://example.com/p2"),
        ]

        result = await svc.ingest_from_site_audit(
            company_id=company_id,
            effective_slug="test-co",
            pipeline_run_id=run_id,
            discovery_output=discovery,
            page_results=page_results,
        )

        assert result["upserted"] == 2
        assert result["skipped"] == 0
        repo.bulk_upsert_from_crawl.assert_awaited_once()
        call_args = repo.bulk_upsert_from_crawl.call_args
        assert call_args.kwargs["company_id"] == company_id
        assert len(call_args.kwargs["pages"]) == 2

    @pytest.mark.asyncio
    async def test_skips_pages_without_audit_result(self):
        repo = _make_repo()
        repo.bulk_upsert_from_crawl = AsyncMock(return_value=1)
        svc = _make_service(repo)

        discovery = _make_discovery_output(
            urls_with_html=[
                ("https://example.com/p1", "<html>..."),
                ("https://example.com/no-result", "<html>..."),
            ],
        )
        page_results = [
            _make_page_audit_result(url="https://example.com/p1"),
        ]

        result = await svc.ingest_from_site_audit(
            company_id=uuid.uuid4(),
            effective_slug="test-co",
            pipeline_run_id=uuid.uuid4(),
            discovery_output=discovery,
            page_results=page_results,
        )
        assert result["skipped"] == 1


# ── ingest_from_cms_sync ──────────────────────────────────────────


class TestIngestFromCmsSync:
    """Service: ingest_from_cms_sync"""

    @pytest.mark.asyncio
    async def test_upserts_each_post(self):
        repo = _make_repo()
        mock_model = MagicMock()
        mock_model.id = uuid.uuid4()
        repo.upsert_page = AsyncMock(return_value=mock_model)
        repo.get_existing_urls = AsyncMock(return_value=set())
        svc = _make_service(repo)

        posts = [
            SimpleNamespace(
                url="https://example.com/post1",
                title="Post 1",
                cms_post_id="cms-1",
                h1_text="",
                excerpt="Excerpt",
                content_preview="Preview",
                word_count=500,
                categories=["tech"],
                tags=["ai"],
                seo_title="SEO Title",
                seo_description="SEO Desc",
                published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                modified_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            ),
        ]

        pairs, new_page_ids = await svc.ingest_from_cms_sync(
            company_id=uuid.uuid4(),
            effective_slug="test-co",
            cms_posts=posts,
        )
        assert len(pairs) == 1
        assert pairs[0][0] == mock_model.id
        assert pairs[0][1] == "cms-1"
        repo.upsert_page.assert_awaited_once()
        # All pages are new (empty existing set)
        assert len(new_page_ids) == 1
        assert new_page_ids[0] == mock_model.id

    @pytest.mark.asyncio
    async def test_skips_posts_without_url(self):
        repo = _make_repo()
        repo.get_existing_urls = AsyncMock(return_value=set())
        svc = _make_service(repo)

        posts = [SimpleNamespace(url="", title="No URL")]
        pairs, new_page_ids = await svc.ingest_from_cms_sync(
            company_id=uuid.uuid4(),
            effective_slug="test-co",
            cms_posts=posts,
        )
        assert len(pairs) == 0
        assert len(new_page_ids) == 0
        repo.upsert_page.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_identifies_new_vs_existing_pages(self):
        """Only pages whose URL is NOT in existing_urls are flagged as new."""
        repo = _make_repo()
        # Simulate: post1 already exists, post2 is new
        repo.get_existing_urls = AsyncMock(
            return_value={"https://example.com/post1"},
        )
        model1 = MagicMock()
        model1.id = uuid.uuid4()
        model2 = MagicMock()
        model2.id = uuid.uuid4()
        repo.upsert_page = AsyncMock(side_effect=[model1, model2])
        svc = _make_service(repo)

        posts = [
            SimpleNamespace(
                url="https://example.com/post1", title="Post 1",
                cms_post_id="cms-1", h1_text="", excerpt="", content_preview="",
                word_count=0, categories=None, tags=None, seo_title="", seo_description="",
                published_at=None, modified_at=None,
            ),
            SimpleNamespace(
                url="https://example.com/post2", title="Post 2",
                cms_post_id="cms-2", h1_text="", excerpt="", content_preview="",
                word_count=0, categories=None, tags=None, seo_title="", seo_description="",
                published_at=None, modified_at=None,
            ),
        ]

        pairs, new_page_ids = await svc.ingest_from_cms_sync(
            company_id=uuid.uuid4(),
            effective_slug="test-co",
            cms_posts=posts,
        )
        assert len(pairs) == 2
        assert len(new_page_ids) == 1
        assert new_page_ids[0] == model2.id

    @pytest.mark.asyncio
    async def test_all_existing_no_new_pages(self):
        """When all URLs already exist, new_page_ids is empty."""
        repo = _make_repo()
        repo.get_existing_urls = AsyncMock(
            return_value={"https://example.com/post1"},
        )
        mock_model = MagicMock()
        mock_model.id = uuid.uuid4()
        repo.upsert_page = AsyncMock(return_value=mock_model)
        svc = _make_service(repo)

        posts = [
            SimpleNamespace(
                url="https://example.com/post1", title="Post 1",
                cms_post_id="cms-1", h1_text="", excerpt="", content_preview="",
                word_count=0, categories=None, tags=None, seo_title="", seo_description="",
                published_at=None, modified_at=None,
            ),
        ]

        pairs, new_page_ids = await svc.ingest_from_cms_sync(
            company_id=uuid.uuid4(),
            effective_slug="test-co",
            cms_posts=posts,
        )
        assert len(pairs) == 1
        assert len(new_page_ids) == 0


# ── ingest_from_csv ───────────────────────────────────────────────


class TestIngestFromCsv:
    """Service: ingest_from_csv"""

    @pytest.mark.asyncio
    async def test_valid_rows_imported(self):
        repo = _make_repo()
        mock_model = MagicMock()
        mock_model.id = uuid.uuid4()
        repo.upsert_page = AsyncMock(return_value=mock_model)
        svc = _make_service(repo)

        rows = [
            {"url": "https://example.com/p1", "title": "Page 1", "word_count": "500"},
            {"url": "https://example.com/p2", "title": "Page 2"},
        ]
        result = await svc.ingest_from_csv(
            company_id=uuid.uuid4(),
            effective_slug="test-co",
            csv_rows=rows,
        )
        assert result["imported"] == 2
        assert result["skipped"] == 0

    @pytest.mark.asyncio
    async def test_missing_url_skipped(self):
        repo = _make_repo()
        svc = _make_service(repo)

        rows = [
            {"url": "", "title": "No URL"},
            {"title": "Also no URL"},
        ]
        result = await svc.ingest_from_csv(
            company_id=uuid.uuid4(),
            effective_slug="test-co",
            csv_rows=rows,
        )
        assert result["skipped"] == 2
        assert len(result["errors"]) == 2


# ── register_published_content ────────────────────────────────────


class TestRegisterPublishedContent:
    """Service: register_published_content"""

    @pytest.mark.asyncio
    @patch("core.shared_tools.async_embedding_client.async_embed_texts", new_callable=AsyncMock)
    async def test_upserts_and_embeds(self, mock_embed):
        mock_embed.return_value = [[0.1] * 1536]
        repo = _make_repo()
        mock_model = MagicMock()
        mock_model.id = uuid.uuid4()
        repo.upsert_page = AsyncMock(return_value=mock_model)
        svc = _make_service(repo)

        result = await svc.register_published_content(
            company_id=uuid.uuid4(),
            effective_slug="test-co",
            url="https://example.com/new-article",
            title="New Article",
            word_count=2000,
            content_text="Full article content here...",
        )
        assert result is mock_model
        repo.upsert_page.assert_awaited_once()
        # Embedding should have been generated inline
        repo.update_embeddings_batch.assert_awaited_once()


# ── generate_embeddings_for_company ───────────────────────────────


class TestGenerateEmbeddings:
    """Service: generate_embeddings_for_company"""

    @pytest.mark.asyncio
    @patch("core.shared_tools.async_embedding_client.async_embed_texts", new_callable=AsyncMock)
    async def test_generates_embeddings(self, mock_embed):
        mock_embed.return_value = [[0.1] * 1536, [0.2] * 1536]

        repo = _make_repo()
        page1 = MagicMock()
        page1.id = uuid.uuid4()
        page1.title = "Page 1"
        page1.h1_text = "H1"
        page1.meta_description = "Desc"
        page1.content_preview = "Preview text"

        page2 = MagicMock()
        page2.id = uuid.uuid4()
        page2.title = "Page 2"
        page2.h1_text = ""
        page2.meta_description = ""
        page2.content_preview = ""

        repo.get_pages_missing_embeddings = AsyncMock(return_value=[page1, page2])
        repo.update_embeddings_batch = AsyncMock(return_value=2)
        svc = _make_service(repo)

        count = await svc.generate_embeddings_for_company(uuid.uuid4())
        assert count == 2
        mock_embed.assert_awaited_once()
        repo.update_embeddings_batch.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_pages_returns_zero(self):
        repo = _make_repo()
        repo.get_pages_missing_embeddings = AsyncMock(return_value=[])
        svc = _make_service(repo)

        count = await svc.generate_embeddings_for_company(uuid.uuid4())
        assert count == 0


# ── check_cannibalization ─────────────────────────────────────────


class TestCheckCannibalization:
    """Service: check_cannibalization + check_cannibalization_batch"""

    @pytest.mark.asyncio
    @patch("core.shared_tools.async_embedding_client.async_embed_texts", new_callable=AsyncMock)
    async def test_returns_matches(self, mock_embed):
        mock_embed.return_value = [[0.1] * 1536]
        repo = _make_repo()

        mock_model = MagicMock()
        mock_model.id = uuid.uuid4()
        mock_model.url = "https://example.com/existing"
        mock_model.title = "Existing"
        mock_model.word_count = 1000
        mock_model.content_preview = "Preview"
        mock_model.content_type_detected = "blog_post"

        repo.find_similar = AsyncMock(return_value=[(mock_model, 0.88)])
        svc = _make_service(repo)

        matches = await svc.check_cannibalization(
            company_id=uuid.uuid4(),
            topic_text="How to use AI for content",
        )
        assert len(matches) == 1
        assert isinstance(matches[0], CannibalizationMatch)
        assert matches[0].similarity == 0.88

    @pytest.mark.asyncio
    @patch("core.shared_tools.async_embedding_client.async_embed_texts", new_callable=AsyncMock)
    async def test_batch_returns_dict(self, mock_embed):
        mock_embed.return_value = [[0.1] * 1536, [0.2] * 1536]
        repo = _make_repo()
        repo.find_similar = AsyncMock(return_value=[])
        svc = _make_service(repo)

        result = await svc.check_cannibalization_batch(
            company_id=uuid.uuid4(),
            topics=["Topic A", "Topic B"],
        )
        assert "Topic A" in result
        assert "Topic B" in result
        assert mock_embed.await_count == 1  # single batch call

    @pytest.mark.asyncio
    async def test_batch_empty_topics(self):
        svc = _make_service()
        result = await svc.check_cannibalization_batch(
            company_id=uuid.uuid4(), topics=[]
        )
        assert result == {}


# ── find_existing_coverage ────────────────────────────────────────


class TestFindExistingCoverage:
    """Service: find_existing_coverage"""

    @pytest.mark.asyncio
    @patch("core.shared_tools.async_embedding_client.async_embed_texts", new_callable=AsyncMock)
    async def test_returns_coverage_results(self, mock_embed):
        mock_embed.return_value = [[0.1] * 1536]
        repo = _make_repo()

        mock_model = MagicMock()
        mock_model.id = uuid.uuid4()
        mock_model.url = "https://example.com/existing"
        mock_model.title = "Existing"
        mock_model.word_count = 1500
        mock_model.content_preview = "Preview text"
        mock_model.categories = ["tech", "ai"]
        mock_model.content_modified_at = datetime(2026, 3, 1, tzinfo=timezone.utc)

        repo.find_similar = AsyncMock(return_value=[(mock_model, 0.83)])
        svc = _make_service(repo)

        results = await svc.find_existing_coverage(
            company_id=uuid.uuid4(),
            query_text="AI content strategy",
        )
        assert len(results) == 1
        assert isinstance(results[0], ExistingCoverageResult)
        assert results[0].similarity == 0.83
        assert results[0].categories == ["tech", "ai"]
        assert results[0].content_modified_at is not None

    @pytest.mark.asyncio
    @patch("core.shared_tools.async_embedding_client.async_embed_texts", new_callable=AsyncMock)
    async def test_empty_embeddings_returns_empty(self, mock_embed):
        mock_embed.return_value = [[]]
        svc = _make_service()

        results = await svc.find_existing_coverage(
            company_id=uuid.uuid4(),
            query_text="Anything",
        )
        assert results == []


# ── find_similar_pages (intra-inventory cannibalization) ──────────


class TestFindSimilarPages:
    """Service: find_similar_pages — intra-inventory cannibalization."""

    @pytest.mark.asyncio
    async def test_returns_matches_excluding_self(self):
        repo = _make_repo()
        mock_model = MagicMock()
        mock_model.id = uuid.uuid4()
        mock_model.url = "https://example.com/similar"
        mock_model.title = "Similar Page"
        mock_model.word_count = 1200
        mock_model.content_preview = "Preview of similar page"
        mock_model.content_type_detected = "blog_post"

        repo.find_similar_to_page = AsyncMock(return_value=[(mock_model, 0.85)])
        svc = _make_service(repo)

        results = await svc.find_similar_pages(
            company_id=uuid.uuid4(),
            page_id=uuid.uuid4(),
        )
        assert len(results) == 1
        assert isinstance(results[0], CannibalizationMatch)
        assert results[0].similarity == 0.85
        assert results[0].title == "Similar Page"
        assert results[0].content_type_detected == "blog_post"

    @pytest.mark.asyncio
    async def test_no_embedding_returns_empty(self):
        repo = _make_repo()
        repo.find_similar_to_page = AsyncMock(return_value=[])
        svc = _make_service(repo)

        results = await svc.find_similar_pages(
            company_id=uuid.uuid4(),
            page_id=uuid.uuid4(),
        )
        assert results == []

    @pytest.mark.asyncio
    async def test_threshold_and_limit_passed_through(self):
        repo = _make_repo()
        repo.find_similar_to_page = AsyncMock(return_value=[])
        svc = _make_service(repo)
        company_id = uuid.uuid4()
        page_id = uuid.uuid4()

        await svc.find_similar_pages(
            company_id=company_id,
            page_id=page_id,
            threshold=0.90,
            limit=3,
        )
        repo.find_similar_to_page.assert_called_once_with(
            company_id, page_id, threshold=0.90, limit=3,
        )
