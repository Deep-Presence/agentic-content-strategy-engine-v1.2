"""Tests for DbSiteAuditDataService — hybrid DB + filesystem site audit service.

Tests the DB-backed methods (audit_exists, get_latest_audit_id, list_audits)
using mocked repos, and verifies filesystem delegation for detail methods.

No real DB required — all repos are mocked.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.services.db_site_audit_data import DbSiteAuditDataService


@pytest.fixture
def mock_company():
    """Create a mock company ORM object."""
    company = MagicMock()
    company.id = uuid.uuid4()
    company.slug = "test-co"
    company.name = "Test Co"
    company.domain = "test.com"
    return company


@pytest.fixture
def mock_audit(mock_company):
    """Create a mock audit ORM object."""
    audit = MagicMock()
    audit.id = uuid.uuid4()
    audit.company_id = mock_company.id
    audit.site_domain = "test.com"
    audit.status = MagicMock(value="completed")
    audit.started_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
    audit.completed_at = datetime(2026, 3, 1, 0, 5, tzinfo=timezone.utc)
    audit.findings_count = 12
    audit.pages_crawled = 8
    return audit


@pytest.fixture
def audit_repo():
    return MagicMock()


@pytest.fixture
def company_repo():
    return MagicMock()


@pytest.fixture
def service(audit_repo, company_repo, tmp_path):
    return DbSiteAuditDataService(
        audit_repo=audit_repo,
        company_repo=company_repo,
        artifacts_root=tmp_path,
    )


# ── audit_exists ─────────────────────────────────────────────────────


class TestAuditExists:
    @pytest.mark.asyncio
    async def test_returns_true_when_exists(
        self, service, company_repo, audit_repo, mock_company,
    ):
        company_repo.get_by_slug = AsyncMock(return_value=mock_company)
        audit_repo.exists_for_domain = AsyncMock(return_value=True)

        result = await service.audit_exists("test-co", "test.com")

        assert result is True
        company_repo.get_by_slug.assert_awaited_once_with("test-co")
        audit_repo.exists_for_domain.assert_awaited_once_with(
            mock_company.id, "test.com"
        )

    @pytest.mark.asyncio
    async def test_returns_false_when_not_exists(
        self, service, company_repo, audit_repo, mock_company,
    ):
        company_repo.get_by_slug = AsyncMock(return_value=mock_company)
        audit_repo.exists_for_domain = AsyncMock(return_value=False)

        result = await service.audit_exists("test-co", "test.com")
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_company_not_found(
        self, service, company_repo,
    ):
        company_repo.get_by_slug = AsyncMock(return_value=None)

        result = await service.audit_exists("nonexistent", "test.com")
        assert result is False


# ── get_latest_audit_id ──────────────────────────────────────────────


class TestGetLatestAuditId:
    @pytest.mark.asyncio
    async def test_returns_audit_id(
        self, service, company_repo, audit_repo, mock_company, mock_audit,
    ):
        company_repo.get_by_slug = AsyncMock(return_value=mock_company)
        audit_repo.get_latest_for_domain = AsyncMock(return_value=mock_audit)

        result = await service.get_latest_audit_id("test-co", "test.com")

        assert result == str(mock_audit.id)
        audit_repo.get_latest_for_domain.assert_awaited_once_with(
            mock_company.id, "test.com"
        )

    @pytest.mark.asyncio
    async def test_returns_none_when_no_audit(
        self, service, company_repo, audit_repo, mock_company,
    ):
        company_repo.get_by_slug = AsyncMock(return_value=mock_company)
        audit_repo.get_latest_for_domain = AsyncMock(return_value=None)

        result = await service.get_latest_audit_id("test-co", "test.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_company_not_found(
        self, service, company_repo,
    ):
        company_repo.get_by_slug = AsyncMock(return_value=None)

        result = await service.get_latest_audit_id("nonexistent", "test.com")
        assert result is None


# ── list_audits ──────────────────────────────────────────────────────


class TestListAudits:
    @pytest.mark.asyncio
    async def test_returns_audit_list_from_db(
        self, service, company_repo, audit_repo, mock_company, mock_audit,
    ):
        company_repo.get_by_slug = AsyncMock(return_value=mock_company)
        audit_repo.list_for_company = AsyncMock(return_value=[mock_audit])

        # Mock the filesystem enrichment to return score/grade
        with patch.object(
            service,
            "_fs_get_audit_summary_safe",
            new_callable=AsyncMock,
            return_value={"overall_score": 72.5, "grade": "C"},
        ):
            result = await service.list_audits("test-co", limit=10)

        assert len(result) == 1
        assert result[0]["audit_id"] == str(mock_audit.id)
        assert result[0]["domain"] == "test.com"
        assert result[0]["overall_score"] == 72.5
        assert result[0]["grade"] == "C"
        assert result[0]["pages_crawled"] == 8
        assert result[0]["total_findings"] == 12
        assert result[0]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_falls_back_to_filesystem_when_no_company(
        self, service, company_repo,
    ):
        company_repo.get_by_slug = AsyncMock(return_value=None)

        with patch.object(
            service,
            "_fs_list_audits",
            new_callable=AsyncMock,
            return_value=[{"audit_id": "abc", "domain": "test.com"}],
        ) as fs_fallback:
            result = await service.list_audits("nonexistent")

        assert len(result) == 1
        fs_fallback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_falls_back_to_filesystem_when_db_empty(
        self, service, company_repo, audit_repo, mock_company,
    ):
        company_repo.get_by_slug = AsyncMock(return_value=mock_company)
        audit_repo.list_for_company = AsyncMock(return_value=[])

        with patch.object(
            service,
            "_fs_list_audits",
            new_callable=AsyncMock,
            return_value=[],
        ) as fs_fallback:
            result = await service.list_audits("test-co")

        assert result == []
        fs_fallback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handles_missing_fs_summary_gracefully(
        self, service, company_repo, audit_repo, mock_company, mock_audit,
    ):
        """When filesystem summary is unavailable, defaults to 0.0/F."""
        company_repo.get_by_slug = AsyncMock(return_value=mock_company)
        audit_repo.list_for_company = AsyncMock(return_value=[mock_audit])

        with patch.object(
            service,
            "_fs_get_audit_summary_safe",
            new_callable=AsyncMock,
            return_value={},
        ):
            result = await service.list_audits("test-co")

        assert result[0]["overall_score"] == 0.0
        assert result[0]["grade"] == "F"


# ── filesystem delegation ────────────────────────────────────────────


class TestFilesystemDelegation:
    """Verify that detail methods delegate to filesystem helpers."""

    @pytest.mark.asyncio
    async def test_get_audit_summary_delegates(self, service):
        with patch(
            "core.services.db_site_audit_data.asyncio.to_thread",
            new_callable=AsyncMock,
            return_value={"audit_id": "abc", "grade": "B"},
        ) as mock_to_thread:
            result = await service.get_audit_summary("test-co", "abc")

        assert result == {"audit_id": "abc", "grade": "B"}
        mock_to_thread.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_audit_detail_delegates(self, service):
        with patch(
            "core.services.db_site_audit_data.asyncio.to_thread",
            new_callable=AsyncMock,
            return_value={"audit_id": "abc", "dimension_scores": []},
        ) as mock_to_thread:
            result = await service.get_audit_detail("test-co", "abc")

        assert "dimension_scores" in result
        mock_to_thread.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_findings_delegates(self, service):
        with patch(
            "core.services.db_site_audit_data.asyncio.to_thread",
            new_callable=AsyncMock,
            return_value={"findings": [], "total": 0, "page": 1},
        ) as mock_to_thread:
            result = await service.get_findings("test-co", "abc")

        assert "findings" in result
        mock_to_thread.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_page_results_delegates(self, service):
        with patch(
            "core.services.db_site_audit_data.asyncio.to_thread",
            new_callable=AsyncMock,
            return_value={"pages": [], "total": 0, "page": 1},
        ) as mock_to_thread:
            result = await service.get_page_results("test-co", "abc")

        assert "pages" in result
        mock_to_thread.assert_awaited_once()


# ── repo method tests ────────────────────────────────────────────────


class TestRepoNewMethods:
    """Verify new repo methods (get_latest_for_domain, exists_for_domain)
    are called with correct arguments."""

    @pytest.mark.asyncio
    async def test_audit_exists_passes_domain(
        self, service, company_repo, audit_repo, mock_company,
    ):
        company_repo.get_by_slug = AsyncMock(return_value=mock_company)
        audit_repo.exists_for_domain = AsyncMock(return_value=True)

        await service.audit_exists("test-co", "specific-domain.com")

        audit_repo.exists_for_domain.assert_awaited_once_with(
            mock_company.id, "specific-domain.com"
        )

    @pytest.mark.asyncio
    async def test_get_latest_passes_domain(
        self, service, company_repo, audit_repo, mock_company,
    ):
        company_repo.get_by_slug = AsyncMock(return_value=mock_company)
        audit_repo.get_latest_for_domain = AsyncMock(return_value=None)

        await service.get_latest_audit_id("test-co", "specific-domain.com")

        audit_repo.get_latest_for_domain.assert_awaited_once_with(
            mock_company.id, "specific-domain.com"
        )
