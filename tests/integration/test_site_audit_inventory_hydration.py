"""Integration tests for site audit → content inventory hydration.

Tests the hydration function's graceful degradation and error isolation.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.content_inventory.hydration import (
    hydrate_content_inventory_from_site_audit,
)
from core.content_inventory.models import CrawledPageData


def _make_audit_result(*, page_results=None, status="completed"):
    """Build a minimal audit result mock."""
    result = SimpleNamespace(
        status=status,
        page_results=page_results or [],
    )
    return result


def _make_page_result(url="https://example.com/page", title="Page"):
    """Build a minimal page audit result mock."""
    pr = SimpleNamespace(
        url=url,
        title=title,
        h1_text="",
        meta_description="",
        word_count=500,
        headings=[],
        aeo=None,
        schema_result=None,
    )
    return pr


class TestHydrationGuards:
    """Hydration should skip gracefully when preconditions are not met."""

    @pytest.mark.asyncio
    async def test_skip_when_session_factory_none(self):
        result = await hydrate_content_inventory_from_site_audit(
            session_factory=None,
            company_id=uuid.uuid4(),
            effective_slug="test-co",
            pipeline_run_id=uuid.uuid4(),
            audit_result=_make_audit_result(),
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_skip_when_company_id_none(self):
        result = await hydrate_content_inventory_from_site_audit(
            session_factory=MagicMock(),
            company_id=None,
            effective_slug="test-co",
            pipeline_run_id=uuid.uuid4(),
            audit_result=_make_audit_result(),
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_skip_when_pipeline_run_id_none(self):
        result = await hydrate_content_inventory_from_site_audit(
            session_factory=MagicMock(),
            company_id=uuid.uuid4(),
            effective_slug="test-co",
            pipeline_run_id=None,
            audit_result=_make_audit_result(),
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_skip_when_no_page_results(self):
        result = await hydrate_content_inventory_from_site_audit(
            session_factory=MagicMock(),
            company_id=uuid.uuid4(),
            effective_slug="test-co",
            pipeline_run_id=uuid.uuid4(),
            audit_result=_make_audit_result(page_results=[]),
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_skip_when_page_results_is_none(self):
        audit = SimpleNamespace(status="completed")
        # No page_results attribute at all
        result = await hydrate_content_inventory_from_site_audit(
            session_factory=MagicMock(),
            company_id=uuid.uuid4(),
            effective_slug="test-co",
            pipeline_run_id=uuid.uuid4(),
            audit_result=audit,
        )
        assert result is None


class TestHydrationSuccess:
    """Hydration calls the service and returns counts."""

    @pytest.mark.asyncio
    async def test_returns_upsert_counts(self):
        pages = [_make_page_result(), _make_page_result(url="https://example.com/page2")]
        audit_result = _make_audit_result(page_results=pages)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()

        mock_sf = MagicMock()
        mock_sf.return_value = mock_session

        mock_repo_cls = MagicMock()
        mock_svc_cls = MagicMock()
        mock_svc_instance = MagicMock()
        mock_svc_instance.ingest_from_site_audit = AsyncMock(
            return_value={"upserted": 2, "skipped": 0}
        )
        mock_svc_cls.return_value = mock_svc_instance

        with patch(
            "core.db.repositories.content_inventory_repo.ContentInventoryRepository",
            mock_repo_cls,
        ), patch(
            "core.services.content_inventory_service.ContentInventoryService",
            mock_svc_cls,
        ):
            result = await hydrate_content_inventory_from_site_audit(
                session_factory=mock_sf,
                company_id=uuid.uuid4(),
                effective_slug="test-co",
                pipeline_run_id=uuid.uuid4(),
                audit_result=audit_result,
            )

        assert result is not None
        assert result["upserted"] == 2
        assert result["skipped"] == 0


class TestHydrationErrorIsolation:
    """Hydration failure MUST NOT crash the caller."""

    @pytest.mark.asyncio
    async def test_exception_returns_none(self):
        """Database error → returns None, does not raise."""
        pages = [_make_page_result()]
        audit_result = _make_audit_result(page_results=pages)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(
            side_effect=RuntimeError("DB connection failed")
        )
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_sf = MagicMock()
        mock_sf.return_value = mock_session

        # This should NOT raise — the error is caught
        result = await hydrate_content_inventory_from_site_audit(
            session_factory=mock_sf,
            company_id=uuid.uuid4(),
            effective_slug="test-co",
            pipeline_run_id=uuid.uuid4(),
            audit_result=audit_result,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_service_error_returns_none(self):
        """Service-level error → returns None, does not raise."""
        pages = [_make_page_result()]
        audit_result = _make_audit_result(page_results=pages)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()

        mock_sf = MagicMock()
        mock_sf.return_value = mock_session

        mock_svc_cls = MagicMock()
        mock_svc_instance = MagicMock()
        mock_svc_instance.ingest_from_site_audit = AsyncMock(
            side_effect=RuntimeError("Constraint violation")
        )
        mock_svc_cls.return_value = mock_svc_instance

        with patch(
            "core.db.repositories.content_inventory_repo.ContentInventoryRepository",
            MagicMock(),
        ), patch(
            "core.services.content_inventory_service.ContentInventoryService",
            mock_svc_cls,
        ):
            result = await hydrate_content_inventory_from_site_audit(
                session_factory=mock_sf,
                company_id=uuid.uuid4(),
                effective_slug="test-co",
                pipeline_run_id=uuid.uuid4(),
                audit_result=audit_result,
            )

        assert result is None


class TestHydrationWithHtmlMap:
    """Hydration passes html_map to service for structural signal computation."""

    @pytest.mark.asyncio
    async def test_html_map_forwarded_to_service(self):
        """When html_map is provided, it's passed through to ingest_from_site_audit."""
        pages = [_make_page_result()]
        audit_result = _make_audit_result(page_results=pages)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()

        mock_sf = MagicMock()
        mock_sf.return_value = mock_session

        mock_repo_cls = MagicMock()
        mock_svc_cls = MagicMock()
        mock_svc_instance = MagicMock()
        mock_svc_instance.ingest_from_site_audit = AsyncMock(
            return_value={"upserted": 1, "skipped": 0}
        )
        mock_svc_cls.return_value = mock_svc_instance

        html_map = {"https://example.com/page": "<html><body><p>Content</p></body></html>"}

        with patch(
            "core.db.repositories.content_inventory_repo.ContentInventoryRepository",
            mock_repo_cls,
        ), patch(
            "core.services.content_inventory_service.ContentInventoryService",
            mock_svc_cls,
        ):
            result = await hydrate_content_inventory_from_site_audit(
                session_factory=mock_sf,
                company_id=uuid.uuid4(),
                effective_slug="test-co",
                pipeline_run_id=uuid.uuid4(),
                audit_result=audit_result,
                html_map=html_map,
            )

        assert result is not None
        # Verify html_map was forwarded to the service
        call_kwargs = mock_svc_instance.ingest_from_site_audit.call_args.kwargs
        assert call_kwargs["html_map"] is html_map

    @pytest.mark.asyncio
    async def test_none_html_map_backward_compat(self):
        """When html_map is omitted (None), service gets None — no signals computed."""
        pages = [_make_page_result()]
        audit_result = _make_audit_result(page_results=pages)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()

        mock_sf = MagicMock()
        mock_sf.return_value = mock_session

        mock_svc_cls = MagicMock()
        mock_svc_instance = MagicMock()
        mock_svc_instance.ingest_from_site_audit = AsyncMock(
            return_value={"upserted": 1, "skipped": 0}
        )
        mock_svc_cls.return_value = mock_svc_instance

        with patch(
            "core.db.repositories.content_inventory_repo.ContentInventoryRepository",
            MagicMock(),
        ), patch(
            "core.services.content_inventory_service.ContentInventoryService",
            mock_svc_cls,
        ):
            result = await hydrate_content_inventory_from_site_audit(
                session_factory=mock_sf,
                company_id=uuid.uuid4(),
                effective_slug="test-co",
                pipeline_run_id=uuid.uuid4(),
                audit_result=audit_result,
                # html_map not passed — defaults to None
            )

        assert result is not None
        call_kwargs = mock_svc_instance.ingest_from_site_audit.call_args.kwargs
        assert call_kwargs["html_map"] is None
