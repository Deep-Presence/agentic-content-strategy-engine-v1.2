"""Integration tests for gap analysis → content inventory hydration.

Tests the hydration function's graceful degradation, error isolation,
and correct ingestion source usage.
"""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.content_inventory.hydration import hydrate_content_inventory_from_gap_analysis
from core.db.enums import ContentIngestionSource


def _make_page_analysis(url: str = "https://example.com/p1", title: str = "Page 1") -> dict:
    """Build a minimal CompanyPageAnalysis dict."""
    return {
        "url": url,
        "title": title,
        "word_count": 1200,
        "paragraph_count": 15,
        "structural_signals": {
            "word_count": 1200,
            "paragraph_count": 15,
            "header_count": 5,
            "list_item_count": 8,
            "stat_count": 3,
            "citation_count": 12,
            "has_headers": True,
            "has_lists": True,
            "has_numbers": True,
            "has_faq_section": True,
            "has_key_takeaways": False,
            "has_step_by_step": False,
            "has_toc": True,
            "h1_count": 1,
            "h2_count": 3,
            "h3_count": 1,
            "h4_count": 0,
            "reading_level": 9.5,
        },
    }


def _make_discovered_page(url: str = "https://example.com/p1") -> dict:
    """Build a minimal DiscoveredPage dict."""
    return {
        "url": url,
        "normalized_url": url,
        "title": "Page 1",
        "h1": "Main Heading",
        "meta_description": "A test page about topics.",
        "discovery_source": "sitemap",
        "has_content": True,
    }


def _make_storage(page_analyses: list | None = None, discovered_pages: list | None = None):
    """Build a mock StorageBackend."""
    storage = MagicMock()

    pa_data = json.dumps(page_analyses or [])
    dp_data = json.dumps(discovered_pages or [])

    def exists_fn(path: str) -> bool:
        if "company_page_analysis" in path:
            return page_analyses is not None
        if "discovered_pages" in path:
            return discovered_pages is not None
        return False

    def read_fn(path: str) -> str:
        if "company_page_analysis" in path:
            return pa_data
        if "discovered_pages" in path:
            return dp_data
        return "[]"

    storage.exists = MagicMock(side_effect=exists_fn)
    storage.read = MagicMock(side_effect=read_fn)
    return storage


class TestGapAnalysisHydrationGuards:
    """Hydration should skip gracefully when preconditions are not met."""

    @pytest.mark.asyncio
    async def test_skip_when_session_factory_none(self):
        result = await hydrate_content_inventory_from_gap_analysis(
            session_factory=None,
            company_id=uuid.uuid4(),
            effective_slug="test-co",
            pipeline_run_id=uuid.uuid4(),
            storage=MagicMock(),
            ga_prefix="gap_analysis/test-co",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_skip_when_company_id_none(self):
        result = await hydrate_content_inventory_from_gap_analysis(
            session_factory=MagicMock(),
            company_id=None,
            effective_slug="test-co",
            pipeline_run_id=uuid.uuid4(),
            storage=MagicMock(),
            ga_prefix="gap_analysis/test-co",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_skip_when_pipeline_run_id_none(self):
        result = await hydrate_content_inventory_from_gap_analysis(
            session_factory=MagicMock(),
            company_id=uuid.uuid4(),
            effective_slug="test-co",
            pipeline_run_id=None,
            storage=MagicMock(),
            ga_prefix="gap_analysis/test-co",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_skip_when_no_page_analysis_artifact(self):
        """No company_page_analysis.json → returns None."""
        storage = _make_storage(page_analyses=None)

        result = await hydrate_content_inventory_from_gap_analysis(
            session_factory=MagicMock(),
            company_id=uuid.uuid4(),
            effective_slug="test-co",
            pipeline_run_id=uuid.uuid4(),
            storage=storage,
            ga_prefix="gap_analysis/test-co",
        )
        assert result is None


class TestGapAnalysisHydrationSuccess:
    """Hydration reads from storage and upserts with correct ingestion source."""

    @pytest.mark.asyncio
    async def test_hydrates_from_company_page_analysis_json(self):
        pa = _make_page_analysis()
        dp = _make_discovered_page()
        storage = _make_storage(page_analyses=[pa], discovered_pages=[dp])

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()

        mock_sf = MagicMock()
        mock_sf.return_value = mock_session

        mock_repo = MagicMock()
        mock_repo.bulk_upsert_from_crawl = AsyncMock(return_value=1)

        with patch(
            "core.db.repositories.content_inventory_repo.ContentInventoryRepository",
            return_value=mock_repo,
        ):
            result = await hydrate_content_inventory_from_gap_analysis(
                session_factory=mock_sf,
                company_id=uuid.uuid4(),
                effective_slug="test-co",
                pipeline_run_id=uuid.uuid4(),
                storage=storage,
                ga_prefix="gap_analysis/test-co",
            )

        assert result is not None
        assert result["upserted"] == 1

        # Verify ingestion source is gap_analysis_crawl
        call_kwargs = mock_repo.bulk_upsert_from_crawl.call_args.kwargs
        assert call_kwargs["ingestion_source"] == ContentIngestionSource.gap_analysis_crawl

        # Verify structural signals were passed through
        pages = call_kwargs["pages"]
        assert len(pages) == 1
        assert pages[0].structural_signals is not None
        assert pages[0].has_faq_section is True

    @pytest.mark.asyncio
    async def test_uses_discovered_page_metadata(self):
        """h1 and meta_description from DiscoveredPage are used."""
        pa = _make_page_analysis()
        dp = _make_discovered_page()
        storage = _make_storage(page_analyses=[pa], discovered_pages=[dp])

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()

        mock_sf = MagicMock()
        mock_sf.return_value = mock_session

        mock_repo = MagicMock()
        mock_repo.bulk_upsert_from_crawl = AsyncMock(return_value=1)

        with patch(
            "core.db.repositories.content_inventory_repo.ContentInventoryRepository",
            return_value=mock_repo,
        ):
            await hydrate_content_inventory_from_gap_analysis(
                session_factory=mock_sf,
                company_id=uuid.uuid4(),
                effective_slug="test-co",
                pipeline_run_id=uuid.uuid4(),
                storage=storage,
                ga_prefix="gap_analysis/test-co",
            )

        pages = mock_repo.bulk_upsert_from_crawl.call_args.kwargs["pages"]
        assert pages[0].h1_text == "Main Heading"
        assert pages[0].meta_description == "A test page about topics."


class TestGapAnalysisHydrationErrorIsolation:
    """Hydration failure MUST NOT crash the caller."""

    @pytest.mark.asyncio
    async def test_exception_returns_none(self):
        """Database error → returns None, does not raise."""
        pa = _make_page_analysis()
        storage = _make_storage(page_analyses=[pa])

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(
            side_effect=RuntimeError("DB connection failed")
        )
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_sf = MagicMock()
        mock_sf.return_value = mock_session

        result = await hydrate_content_inventory_from_gap_analysis(
            session_factory=mock_sf,
            company_id=uuid.uuid4(),
            effective_slug="test-co",
            pipeline_run_id=uuid.uuid4(),
            storage=storage,
            ga_prefix="gap_analysis/test-co",
        )

        assert result is None
