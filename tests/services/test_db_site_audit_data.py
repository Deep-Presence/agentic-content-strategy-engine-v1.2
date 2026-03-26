"""Tests for DbSiteAuditDataService — DB-first site audit service.

Tests the DB-first behavior with per-audit filesystem fallback:
- DB-backed methods (audit_exists, get_latest_audit_id, list_audits)
- DB-first reads (get_audit_summary, get_audit_detail, get_findings, get_page_results)
- Filesystem fallback for pre-migration (non-enriched) audits

No real DB required — all repos are mocked.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.services.db_site_audit_data import (
    DbSiteAuditDataService,
    _audit_to_detail_dict,
    _audit_to_summary_dict,
    _finding_to_dict,
    _is_enriched,
    _page_result_to_dict,
)


@pytest.fixture
def mock_company():
    """Create a mock company ORM object."""
    company = MagicMock()
    company.id = uuid.uuid4()
    company.slug = "test-co"
    company.name = "Test Co"
    company.domain = "test.com"
    return company


def _make_enriched_audit(**overrides):
    """Create a mock SiteAuditModel with enriched columns populated."""
    audit = MagicMock()
    audit.id = overrides.get("id", uuid.uuid4())
    audit.company_id = overrides.get("company_id", uuid.uuid4())
    audit.site_domain = overrides.get("site_domain", "test.com")
    audit.status = overrides.get("status", MagicMock(value="completed"))
    audit.started_at = overrides.get(
        "started_at", datetime(2026, 3, 1, tzinfo=timezone.utc)
    )
    audit.completed_at = overrides.get(
        "completed_at", datetime(2026, 3, 1, 0, 5, tzinfo=timezone.utc)
    )
    audit.findings_count = overrides.get("findings_count", 12)
    audit.pages_crawled = overrides.get("pages_crawled", 8)
    # Enriched columns (post-migration)
    audit.overall_score = overrides.get("overall_score", 72.5)
    audit.grade = overrides.get("grade", "C")
    audit.pages_discovered = overrides.get("pages_discovered", 15)
    audit.duration_seconds = overrides.get("duration_seconds", 12.3)
    audit.dimension_scores = overrides.get("dimension_scores", [{"dim": "seo", "score": 70}])
    audit.ai_bot_access = overrides.get("ai_bot_access", {"allowed": True})
    audit.sitemap_health = overrides.get("sitemap_health", {"valid": True})
    audit.findings_by_severity = overrides.get("findings_by_severity", {"critical": 2})
    audit.findings_by_dimension = overrides.get("findings_by_dimension", {"seo": 5})
    audit.avg_snippet_readiness = overrides.get("avg_snippet_readiness", 65.0)
    audit.pages_with_schema = overrides.get("pages_with_schema", 3)
    audit.avg_question_heading_ratio = overrides.get("avg_question_heading_ratio", 0.4)
    audit.error_message = overrides.get("error_message", None)
    audit.effective_slug = overrides.get("effective_slug", "test-co")
    return audit


def _make_thin_audit(**overrides):
    """Create a mock SiteAuditModel WITHOUT enriched columns (pre-migration)."""
    audit = MagicMock()
    audit.id = overrides.get("id", uuid.uuid4())
    audit.company_id = overrides.get("company_id", uuid.uuid4())
    audit.site_domain = overrides.get("site_domain", "test.com")
    audit.status = overrides.get("status", MagicMock(value="completed"))
    audit.started_at = overrides.get("started_at", datetime(2026, 3, 1, tzinfo=timezone.utc))
    audit.completed_at = overrides.get("completed_at", datetime(2026, 3, 1, 0, 5, tzinfo=timezone.utc))
    audit.findings_count = overrides.get("findings_count", 12)
    audit.pages_crawled = overrides.get("pages_crawled", 8)
    # Enriched columns are NULL (pre-migration)
    audit.overall_score = None
    audit.grade = None
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


# ── _is_enriched helper ────────────────────────────────────────────────


class TestIsEnriched:
    def test_enriched_when_overall_score_present(self):
        audit = _make_enriched_audit(overall_score=72.5)
        assert _is_enriched(audit) is True

    def test_not_enriched_when_overall_score_none(self):
        audit = _make_thin_audit()
        assert _is_enriched(audit) is False

    def test_not_enriched_when_overall_score_zero(self):
        """0.0 is a valid score (fully enriched), not None."""
        audit = _make_enriched_audit(overall_score=0.0)
        # 0.0 is falsy but NOT None — this is the edge case
        # _is_enriched checks `is not None`, so 0.0 should be True
        assert _is_enriched(audit) is True


# ── Converter helper tests ──────────────────────────────────────────────


class TestConverterHelpers:
    def test_audit_to_summary_dict(self):
        audit = _make_enriched_audit()
        d = _audit_to_summary_dict(audit)
        assert d["overall_score"] == 72.5
        assert d["grade"] == "C"
        assert d["pages_crawled"] == 8
        assert d["total_findings"] == 12
        assert d["status"] == "completed"

    def test_audit_to_detail_dict(self):
        audit = _make_enriched_audit()
        d = _audit_to_detail_dict(audit)
        assert d["overall_score"] == 72.5
        assert d["dimension_scores"] == [{"dim": "seo", "score": 70}]
        assert d["ai_bot_access"] == {"allowed": True}
        assert d["pages_discovered"] == 15
        assert d["duration_seconds"] == 12.3

    def test_null_coalescing_in_summary(self):
        """NULL columns should coalesce to safe defaults."""
        audit = _make_enriched_audit(
            overall_score=None,
            grade=None,
            pages_crawled=None,
            findings_count=None,
        )
        d = _audit_to_summary_dict(audit)
        assert d["overall_score"] == 0.0
        assert d["grade"] == "F"
        assert d["pages_crawled"] == 0
        assert d["total_findings"] == 0

    def test_null_coalescing_in_detail(self):
        """NULL JSONB/array columns should coalesce to empty containers."""
        audit = _make_enriched_audit(
            dimension_scores=None,
            ai_bot_access=None,
            sitemap_health=None,
            findings_by_severity=None,
            findings_by_dimension=None,
            pages_discovered=None,
            duration_seconds=None,
        )
        d = _audit_to_detail_dict(audit)
        assert d["dimension_scores"] == []
        assert d["ai_bot_access"] == {}
        assert d["sitemap_health"] == {}
        assert d["findings_by_severity"] == {}
        assert d["findings_by_dimension"] == {}
        assert d["pages_discovered"] == 0
        assert d["duration_seconds"] == 0.0

    def test_finding_to_dict(self):
        finding = MagicMock()
        finding.finding_type = "missing_title"
        finding.dimension = "on_page_seo"
        finding.severity = MagicMock(value="high")
        finding.message = "Missing title"
        finding.recommendation = "Add a title"
        finding.page_url = "https://test.com/"
        finding.details = {"extra": "data"}
        d = _finding_to_dict(finding)
        assert d["finding_type"] == "missing_title"
        assert d["dimension"] == "on_page_seo"
        assert d["severity"] == "high"
        assert d["url"] == "https://test.com/"

    def test_page_result_to_dict(self):
        pr = MagicMock()
        pr.url = "https://test.com/page1"
        pr.status_code = 200
        pr.crawl_depth = 1
        pr.title = "Test Page"
        pr.word_count = 500
        pr.reading_level = 8.5
        pr.has_https = True
        pr.is_noindex = False
        pr.finding_count = 3
        pr.result_json = {"schema_result": {"has_schema": True}, "aeo": {"score": 80}}
        d = _page_result_to_dict(pr)
        assert d["url"] == "https://test.com/page1"
        assert d["schema"] == {"has_schema": True}
        assert d["aeo"] == {"score": 80}
        assert d["finding_count"] == 3


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
        self, service, company_repo, audit_repo, mock_company,
    ):
        mock_audit = _make_enriched_audit()
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
    async def test_returns_enriched_audits_from_db(
        self, service, company_repo, audit_repo, mock_company,
    ):
        """Enriched audits should return score/grade from DB columns."""
        enriched = _make_enriched_audit()
        company_repo.get_by_slug = AsyncMock(return_value=mock_company)
        audit_repo.list_for_company = AsyncMock(return_value=[enriched])

        result = await service.list_audits("test-co", limit=10)

        assert len(result) == 1
        assert result[0]["overall_score"] == 72.5
        assert result[0]["grade"] == "C"
        assert result[0]["pages_crawled"] == 8
        assert result[0]["total_findings"] == 12

    @pytest.mark.asyncio
    async def test_thin_audit_enriched_from_fs(
        self, service, company_repo, audit_repo, mock_company,
    ):
        """Pre-migration (thin) audits should be enriched from filesystem."""
        thin = _make_thin_audit()
        company_repo.get_by_slug = AsyncMock(return_value=mock_company)
        audit_repo.list_for_company = AsyncMock(return_value=[thin])

        with patch.object(
            service,
            "_fs_get_audit_summary_safe",
            new_callable=AsyncMock,
            return_value={"overall_score": 80.0, "grade": "B"},
        ):
            result = await service.list_audits("test-co")

        assert result[0]["overall_score"] == 80.0
        assert result[0]["grade"] == "B"

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


# ── get_audit_summary — DB-first ─────────────────────────────────────


class TestGetAuditSummaryFromDB:
    @pytest.mark.asyncio
    async def test_returns_from_db_when_enriched(
        self, service, audit_repo,
    ):
        enriched = _make_enriched_audit()
        audit_repo.get_by_slug_and_audit_id = AsyncMock(return_value=enriched)

        result = await service.get_audit_summary("test-co", str(enriched.id))

        assert result["overall_score"] == 72.5
        assert result["grade"] == "C"
        audit_repo.get_by_slug_and_audit_id.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_falls_back_to_fs_when_not_enriched(
        self, service, audit_repo,
    ):
        thin = _make_thin_audit()
        audit_repo.get_by_slug_and_audit_id = AsyncMock(return_value=thin)

        with patch.object(
            service,
            "_fs_get_audit_summary",
            new_callable=AsyncMock,
            return_value={"overall_score": 80.0, "grade": "B"},
        ) as fs_mock:
            result = await service.get_audit_summary("test-co", str(thin.id))

        assert result["overall_score"] == 80.0
        fs_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_falls_back_to_fs_when_audit_not_in_db(
        self, service, audit_repo,
    ):
        audit_repo.get_by_slug_and_audit_id = AsyncMock(return_value=None)

        with patch.object(
            service,
            "_fs_get_audit_summary",
            new_callable=AsyncMock,
            return_value={"overall_score": 65.0, "grade": "D"},
        ) as fs_mock:
            result = await service.get_audit_summary("test-co", "00000000-0000-4000-8000-000000000001")

        fs_mock.assert_awaited_once()


# ── get_audit_detail — DB-first ──────────────────────────────────────


class TestGetAuditDetailFromDB:
    @pytest.mark.asyncio
    async def test_returns_from_db_when_enriched(
        self, service, audit_repo,
    ):
        enriched = _make_enriched_audit()
        audit_repo.get_by_slug_and_audit_id = AsyncMock(return_value=enriched)

        result = await service.get_audit_detail("test-co", str(enriched.id))

        assert result["overall_score"] == 72.5
        assert result["dimension_scores"] == [{"dim": "seo", "score": 70}]
        assert result["ai_bot_access"] == {"allowed": True}

    @pytest.mark.asyncio
    async def test_falls_back_to_fs_when_not_enriched(
        self, service, audit_repo,
    ):
        thin = _make_thin_audit()
        audit_repo.get_by_slug_and_audit_id = AsyncMock(return_value=thin)

        with patch.object(
            service,
            "_fs_get_audit_detail",
            new_callable=AsyncMock,
            return_value={"overall_score": 80.0, "dimension_scores": []},
        ) as fs_mock:
            result = await service.get_audit_detail("test-co", str(thin.id))

        fs_mock.assert_awaited_once()


# ── get_findings — DB-first ──────────────────────────────────────────


class TestGetFindingsFromDB:
    @pytest.mark.asyncio
    async def test_returns_from_db_when_enriched(
        self, service, audit_repo,
    ):
        mock_finding = MagicMock()
        mock_finding.finding_type = "missing_title"
        mock_finding.dimension = "seo"
        mock_finding.severity = MagicMock(value="high")
        mock_finding.message = "Missing title"
        mock_finding.recommendation = "Add title"
        mock_finding.page_url = "https://test.com/"
        mock_finding.details = None

        audit_repo.has_enriched_data = AsyncMock(return_value=True)
        audit_repo.get_findings_for_audit = AsyncMock(
            return_value=([mock_finding], 1)
        )

        result = await service.get_findings("test-co", "00000000-0000-4000-8000-000000000002")

        assert result["total"] == 1
        assert len(result["findings"]) == 1
        assert result["findings"][0]["finding_type"] == "missing_title"
        assert result["page"] == 1
        assert result["total_pages"] == 1

    @pytest.mark.asyncio
    async def test_paginated_findings(
        self, service, audit_repo,
    ):
        audit_repo.has_enriched_data = AsyncMock(return_value=True)
        audit_repo.get_findings_for_audit = AsyncMock(
            return_value=([], 100)
        )

        result = await service.get_findings(
            "test-co", "00000000-0000-4000-8000-000000000001", page=3, page_size=10
        )

        assert result["total"] == 100
        assert result["page"] == 3
        assert result["total_pages"] == 10
        # Verify correct offset was passed
        call_kwargs = audit_repo.get_findings_for_audit.call_args[1]
        assert call_kwargs["offset"] == 20  # (3-1) * 10
        assert call_kwargs["limit"] == 10

    @pytest.mark.asyncio
    async def test_filters_passed_to_repo(
        self, service, audit_repo,
    ):
        audit_repo.has_enriched_data = AsyncMock(return_value=True)
        audit_repo.get_findings_for_audit = AsyncMock(return_value=([], 0))

        await service.get_findings(
            "test-co", "00000000-0000-4000-8000-000000000001", severity="critical", dimension="seo"
        )

        call_kwargs = audit_repo.get_findings_for_audit.call_args[1]
        assert call_kwargs["severity"] == "critical"
        assert call_kwargs["dimension"] == "seo"

    @pytest.mark.asyncio
    async def test_falls_back_to_fs_when_not_enriched(
        self, service, audit_repo,
    ):
        audit_repo.has_enriched_data = AsyncMock(return_value=False)

        with patch.object(
            service,
            "_fs_get_findings",
            new_callable=AsyncMock,
            return_value={"findings": [], "total": 0, "page": 1},
        ) as fs_mock:
            result = await service.get_findings("test-co", "00000000-0000-4000-8000-000000000001")

        fs_mock.assert_awaited_once()


# ── get_page_results — DB-first ──────────────────────────────────────


class TestGetPageResultsFromDB:
    @pytest.mark.asyncio
    async def test_returns_from_db_when_enriched(
        self, service, audit_repo,
    ):
        mock_pr = MagicMock()
        mock_pr.url = "https://test.com/page1"
        mock_pr.status_code = 200
        mock_pr.crawl_depth = 1
        mock_pr.title = "Test Page"
        mock_pr.word_count = 500
        mock_pr.reading_level = 8.5
        mock_pr.has_https = True
        mock_pr.is_noindex = False
        mock_pr.finding_count = 2
        mock_pr.result_json = {"schema_result": {}, "aeo": {}}

        audit_repo.has_enriched_data = AsyncMock(return_value=True)
        audit_repo.get_page_results_for_audit = AsyncMock(
            return_value=([mock_pr], 1)
        )

        result = await service.get_page_results("test-co", "00000000-0000-4000-8000-000000000001")

        assert result["total"] == 1
        assert len(result["pages"]) == 1
        assert result["pages"][0]["url"] == "https://test.com/page1"

    @pytest.mark.asyncio
    async def test_falls_back_to_fs_when_not_enriched(
        self, service, audit_repo,
    ):
        audit_repo.has_enriched_data = AsyncMock(return_value=False)

        with patch.object(
            service,
            "_fs_get_page_results",
            new_callable=AsyncMock,
            return_value={"pages": [], "total": 0, "page": 1},
        ) as fs_mock:
            result = await service.get_page_results("test-co", "00000000-0000-4000-8000-000000000001")

        fs_mock.assert_awaited_once()


# ── repo method tests ────────────────────────────────────────────────


class TestRepoNewMethods:
    """Verify new repo methods are called with correct arguments."""

    @pytest.mark.asyncio
    async def test_audit_exists_for_slug_delegates_to_repo(
        self, service, audit_repo,
    ):
        """audit_exists_for_slug queries by effective_slug directly (no company lookup)."""
        audit_repo.exists_for_slug_and_domain = AsyncMock(return_value=True)

        result = await service.audit_exists_for_slug("acme__prod", "acme.com")

        assert result is True
        audit_repo.exists_for_slug_and_domain.assert_awaited_once_with(
            "acme__prod", "acme.com"
        )

    @pytest.mark.asyncio
    async def test_audit_exists_for_slug_returns_false(
        self, service, audit_repo,
    ):
        audit_repo.exists_for_slug_and_domain = AsyncMock(return_value=False)

        result = await service.audit_exists_for_slug("acme", "unknown.com")

        assert result is False

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
