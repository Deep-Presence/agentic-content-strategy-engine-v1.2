"""Unit tests for core.site_audit.persistence — DB persistence hooks for site audit.

Pure unit tests — no real DB needed. All DB interaction is mocked via
AsyncMock session factories and patched repositories.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models.site_audit import (
    AuditCheckSeverity,
    AuditDimension,
    AuditFinding,
    PageAuditResult,
    SiteAuditResult,
)


# ── Shared fixtures ──────────────────────────────────────────────────────

RUN_ID = uuid.uuid4()
COMPANY_ID = uuid.uuid4()
SLUG = "test-co"
AUDIT_ID = str(uuid.uuid4())


class _FakeSession:
    """Async context manager that yields itself and tracks calls."""

    def __init__(self) -> None:
        self.commit = AsyncMock()
        self.add = MagicMock()
        self.flush = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def _make_session_factory() -> MagicMock:
    """Return a callable that produces _FakeSession instances."""
    session = _FakeSession()
    factory = MagicMock()
    factory.return_value = session
    factory._session = session  # stash for assertions
    return factory


def _make_audit_result(**overrides) -> SiteAuditResult:
    """Build a minimal SiteAuditResult for testing."""
    defaults = {
        "audit_id": AUDIT_ID,
        "domain": "test.com",
        "overall_score": 72.5,
        "grade": "C",
        "pages_crawled": 5,
        "pages_discovered": 10,
        "duration_seconds": 12.3,
        "status": "completed",
    }
    defaults.update(overrides)
    return SiteAuditResult(**defaults)


def _make_page_with_findings(url: str = "https://test.com/page1") -> PageAuditResult:
    """Create a PageAuditResult with two findings."""
    return PageAuditResult(
        url=url,
        status_code=200,
        crawl_depth=1,
        title="Test Page",
        word_count=500,
        findings=[
            AuditFinding(
                finding_type="missing_title",
                dimension=AuditDimension.on_page_seo,
                severity=AuditCheckSeverity.high,
                message="Page is missing a title tag",
                recommendation="Add a descriptive <title> tag",
                url=url,
            ),
            AuditFinding(
                finding_type="no_https",
                dimension=AuditDimension.security,
                severity=AuditCheckSeverity.critical,
                message="Page not served over HTTPS",
                recommendation="Enable HTTPS",
                url=url,
            ),
        ],
    )


_REPO_PATH = "core.db.repositories.site_audit_repo.SiteAuditRepository"


# ── Guard Tests ──────────────────────────────────────────────────────────


class TestShouldPersist:
    def test_all_present_returns_true(self):
        from core.site_audit.persistence import _should_persist

        assert _should_persist(MagicMock(), RUN_ID, COMPANY_ID) is True

    def test_none_session_factory_returns_false(self):
        from core.site_audit.persistence import _should_persist

        assert _should_persist(None, RUN_ID, COMPANY_ID) is False

    def test_none_run_id_returns_false(self):
        from core.site_audit.persistence import _should_persist

        assert _should_persist(MagicMock(), None, COMPANY_ID) is False

    def test_none_company_id_returns_false(self):
        from core.site_audit.persistence import _should_persist

        assert _should_persist(MagicMock(), RUN_ID, None) is False


# ── Main Persistence Tests ───────────────────────────────────────────────


class TestPersistSiteAuditResult:
    @pytest.mark.asyncio
    async def test_skip_when_no_session_factory(self):
        """Should return immediately without DB interaction."""
        from core.site_audit.persistence import persist_site_audit_result

        result = _make_audit_result()
        # Should not raise
        await persist_site_audit_result(
            None, RUN_ID, COMPANY_ID, SLUG, result,
        )

    @pytest.mark.asyncio
    async def test_happy_path_creates_audit_and_findings(self):
        """Should create SiteAuditModel + AuditFindingModel rows."""
        from core.site_audit.persistence import persist_site_audit_result

        sf = _make_session_factory()
        page = _make_page_with_findings()
        result = _make_audit_result(page_results=[page])

        mock_repo = MagicMock()
        mock_repo.create = AsyncMock(return_value=MagicMock())
        mock_repo.bulk_insert_findings = AsyncMock(return_value=[])
        mock_repo.bulk_insert_page_results = AsyncMock()

        with patch(_REPO_PATH, return_value=mock_repo):
            await persist_site_audit_result(
                sf, RUN_ID, COMPANY_ID, SLUG, result,
            )

        # session.commit() called
        sf._session.commit.assert_awaited_once()
        # Audit was created with correct fields
        mock_repo.create.assert_awaited_once()
        create_kwargs = mock_repo.create.call_args[1]
        assert create_kwargs["company_id"] == COMPANY_ID
        assert create_kwargs["site_domain"] == "test.com"
        assert create_kwargs["overall_score"] == 72.5
        assert create_kwargs["grade"] == "C"
        assert create_kwargs["effective_slug"] == SLUG
        assert create_kwargs["is_degraded"] is False

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_db_error(self):
        """DB exception should be caught — pipeline must not crash."""
        from core.site_audit.persistence import persist_site_audit_result

        sf = _make_session_factory()
        result = _make_audit_result()

        with patch(_REPO_PATH, side_effect=RuntimeError("DB gone")):
            # Should NOT raise
            await persist_site_audit_result(
                sf, RUN_ID, COMPANY_ID, SLUG, result,
            )

    @pytest.mark.asyncio
    async def test_degraded_result_maps_correctly(self):
        """status='degraded' should map to PipelineStatus.completed + is_degraded=True."""
        from core.site_audit.persistence import persist_site_audit_result

        sf = _make_session_factory()
        result = _make_audit_result(
            status="degraded",
            failed_steps=[2, 4],
            degraded_dimensions=["on_page_seo", "extractability"],
        )

        mock_repo = MagicMock()
        mock_repo.create = AsyncMock(return_value=MagicMock())
        mock_repo.bulk_insert_findings = AsyncMock(return_value=[])
        mock_repo.bulk_insert_page_results = AsyncMock()

        with patch(_REPO_PATH, return_value=mock_repo):
            await persist_site_audit_result(
                sf, RUN_ID, COMPANY_ID, SLUG, result,
            )

        create_kwargs = mock_repo.create.call_args[1]
        from core.db.enums import PipelineStatus

        assert create_kwargs["status"] == PipelineStatus.completed
        assert create_kwargs["is_degraded"] is True
        assert create_kwargs["failed_steps"] == [2, 4]
        assert create_kwargs["degraded_dimensions"] == ["on_page_seo", "extractability"]

    @pytest.mark.asyncio
    async def test_finding_dedup(self):
        """Overlapping findings from page_results and top_findings should be deduplicated."""
        from core.site_audit.persistence import persist_site_audit_result

        sf = _make_session_factory()

        finding = AuditFinding(
            finding_type="missing_title",
            dimension=AuditDimension.on_page_seo,
            severity=AuditCheckSeverity.high,
            message="Page missing title",
            url="https://test.com/",
        )
        page = PageAuditResult(url="https://test.com/", findings=[finding])
        # top_findings has the same finding as a dict
        top_finding_dict = {
            "finding_type": "missing_title",
            "dimension": "on_page_seo",
            "severity": "high",
            "message": "Page missing title",
            "url": "https://test.com/",
        }
        result = _make_audit_result(
            page_results=[page],
            top_findings=[top_finding_dict],
        )

        mock_repo = MagicMock()
        mock_repo.create = AsyncMock(return_value=MagicMock())
        mock_repo.bulk_insert_findings = AsyncMock(return_value=[])
        mock_repo.bulk_insert_page_results = AsyncMock()

        with patch(_REPO_PATH, return_value=mock_repo):
            await persist_site_audit_result(
                sf, RUN_ID, COMPANY_ID, SLUG, result,
            )

        # Should be called with deduplicated findings (1, not 2)
        findings_arg = mock_repo.bulk_insert_findings.call_args[0][1]
        assert len(findings_arg) == 1

    @pytest.mark.asyncio
    async def test_severity_enum_mapping(self):
        """Severity strings should be mapped to FindingSeverity enum."""
        from core.site_audit.persistence import persist_site_audit_result

        sf = _make_session_factory()
        finding = AuditFinding(
            finding_type="test_finding",
            dimension=AuditDimension.crawlability,
            severity=AuditCheckSeverity.critical,
            message="Test",
            url="https://test.com/",
        )
        page = PageAuditResult(url="https://test.com/", findings=[finding])
        result = _make_audit_result(page_results=[page])

        mock_repo = MagicMock()
        mock_repo.create = AsyncMock(return_value=MagicMock())
        mock_repo.bulk_insert_findings = AsyncMock(return_value=[])
        mock_repo.bulk_insert_page_results = AsyncMock()

        with patch(_REPO_PATH, return_value=mock_repo):
            await persist_site_audit_result(
                sf, RUN_ID, COMPANY_ID, SLUG, result,
            )

        from core.db.enums import FindingSeverity

        findings_arg = mock_repo.bulk_insert_findings.call_args[0][1]
        assert findings_arg[0]["severity"] == FindingSeverity.critical

    @pytest.mark.asyncio
    async def test_dimension_included_in_findings(self):
        """Findings should include the dimension field."""
        from core.site_audit.persistence import persist_site_audit_result

        sf = _make_session_factory()
        finding = AuditFinding(
            finding_type="test",
            dimension=AuditDimension.security,
            severity=AuditCheckSeverity.low,
            message="Test",
            url="https://test.com/",
        )
        page = PageAuditResult(url="https://test.com/", findings=[finding])
        result = _make_audit_result(page_results=[page])

        mock_repo = MagicMock()
        mock_repo.create = AsyncMock(return_value=MagicMock())
        mock_repo.bulk_insert_findings = AsyncMock(return_value=[])
        mock_repo.bulk_insert_page_results = AsyncMock()

        with patch(_REPO_PATH, return_value=mock_repo):
            await persist_site_audit_result(
                sf, RUN_ID, COMPANY_ID, SLUG, result,
            )

        findings_arg = mock_repo.bulk_insert_findings.call_args[0][1]
        assert findings_arg[0]["dimension"] == "security"

    @pytest.mark.asyncio
    async def test_page_results_bulk_inserted(self):
        """Page results should be bulk inserted with page_index and result_json."""
        from core.site_audit.persistence import persist_site_audit_result

        sf = _make_session_factory()
        page1 = PageAuditResult(url="https://test.com/a", status_code=200)
        page2 = PageAuditResult(url="https://test.com/b", status_code=404)
        result = _make_audit_result(page_results=[page1, page2])

        mock_repo = MagicMock()
        mock_repo.create = AsyncMock(return_value=MagicMock())
        mock_repo.bulk_insert_findings = AsyncMock(return_value=[])
        mock_repo.bulk_insert_page_results = AsyncMock()

        with patch(_REPO_PATH, return_value=mock_repo):
            await persist_site_audit_result(
                sf, RUN_ID, COMPANY_ID, SLUG, result,
            )

        mock_repo.bulk_insert_page_results.assert_awaited_once()
        pages_arg = mock_repo.bulk_insert_page_results.call_args[0][1]
        assert len(pages_arg) == 2
        assert pages_arg[0]["page_index"] == 0
        assert pages_arg[0]["url"] == "https://test.com/a"
        assert pages_arg[1]["page_index"] == 1
        assert pages_arg[1]["url"] == "https://test.com/b"
        # result_json should be present
        assert "result_json" in pages_arg[0]

    @pytest.mark.asyncio
    async def test_invalid_audit_id_generates_new_uuid(self):
        """Non-UUID audit_id should generate a new UUID instead of crashing."""
        from core.site_audit.persistence import persist_site_audit_result

        sf = _make_session_factory()
        result = _make_audit_result(audit_id="not-a-uuid")

        mock_repo = MagicMock()
        mock_repo.create = AsyncMock(return_value=MagicMock())
        mock_repo.bulk_insert_findings = AsyncMock(return_value=[])
        mock_repo.bulk_insert_page_results = AsyncMock()

        with patch(_REPO_PATH, return_value=mock_repo):
            await persist_site_audit_result(
                sf, RUN_ID, COMPANY_ID, SLUG, result,
            )

        # Should succeed — the id is a valid UUID (generated)
        create_kwargs = mock_repo.create.call_args[1]
        assert isinstance(create_kwargs["id"], uuid.UUID)

    @pytest.mark.asyncio
    async def test_empty_page_results(self):
        """Should handle audit with zero pages gracefully."""
        from core.site_audit.persistence import persist_site_audit_result

        sf = _make_session_factory()
        result = _make_audit_result(page_results=[])

        mock_repo = MagicMock()
        mock_repo.create = AsyncMock(return_value=MagicMock())
        mock_repo.bulk_insert_findings = AsyncMock(return_value=[])
        mock_repo.bulk_insert_page_results = AsyncMock()

        with patch(_REPO_PATH, return_value=mock_repo):
            await persist_site_audit_result(
                sf, RUN_ID, COMPANY_ID, SLUG, result,
            )

        sf._session.commit.assert_awaited_once()
        # bulk_insert_findings called with empty list
        mock_repo.bulk_insert_findings.assert_awaited_once()
        assert mock_repo.bulk_insert_findings.call_args[0][1] == []
        # bulk_insert_page_results called with empty list
        mock_repo.bulk_insert_page_results.assert_awaited_once()
        assert mock_repo.bulk_insert_page_results.call_args[0][1] == []

    @pytest.mark.asyncio
    async def test_pipeline_run_id_passed_through(self):
        """pipeline_run_id kwarg should be stored on the audit row."""
        from core.site_audit.persistence import persist_site_audit_result

        sf = _make_session_factory()
        result = _make_audit_result()
        prid = uuid.uuid4()

        mock_repo = MagicMock()
        mock_repo.create = AsyncMock(return_value=MagicMock())
        mock_repo.bulk_insert_findings = AsyncMock(return_value=[])
        mock_repo.bulk_insert_page_results = AsyncMock()

        with patch(_REPO_PATH, return_value=mock_repo):
            await persist_site_audit_result(
                sf, RUN_ID, COMPANY_ID, SLUG, result,
                pipeline_run_id=prid,
            )

        create_kwargs = mock_repo.create.call_args[1]
        assert create_kwargs["pipeline_run_id"] == prid
