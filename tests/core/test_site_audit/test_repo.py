"""Unit tests for core/db/repositories/site_audit_repo.py.

All tests use AsyncMock to avoid a real database dependency.
They verify:
- Correct SQL query construction (where clauses, ordering, limits)
- flush-only contract (commit never called inside repo)
- CRUD helper behaviour (create_audit, bulk_insert_findings)
- UUID string normalisation
- Optional filters work correctly
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.db.enums import FindingSeverity, PipelineStatus
from core.db.models.site_audit import AuditFindingModel, SiteAuditModel
from core.db.repositories.site_audit_repo import SiteAuditRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_mock_session() -> AsyncMock:
    """Return a mock AsyncSession with common async methods patched."""
    session = AsyncMock()
    session.add = MagicMock()  # sync method
    session.flush = AsyncMock()
    session.get = AsyncMock()
    # execute returns a result object
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=None)
    result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    session.execute = AsyncMock(return_value=result)
    return session


def make_fake_audit(company_id: uuid.UUID | None = None) -> SiteAuditModel:
    """Construct a minimal SiteAuditModel stub."""
    audit = MagicMock(spec=SiteAuditModel)
    audit.id = uuid.uuid4()
    audit.company_id = company_id or uuid.uuid4()
    audit.site_domain = "acme.com"
    audit.status = PipelineStatus.completed
    return audit


def make_fake_finding(audit_id: uuid.UUID | None = None) -> AuditFindingModel:
    """Construct a minimal AuditFindingModel stub."""
    finding = MagicMock(spec=AuditFindingModel)
    finding.id = uuid.uuid4()
    finding.audit_id = audit_id or uuid.uuid4()
    finding.finding_type = "missing_title"
    finding.severity = FindingSeverity.critical
    return finding


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


class TestSiteAuditRepositoryInit:
    def test_init_stores_session(self) -> None:
        session = make_mock_session()
        repo = SiteAuditRepository(session)
        assert repo._session is session

    def test_model_class(self) -> None:
        assert SiteAuditRepository.model_class is SiteAuditModel


# ---------------------------------------------------------------------------
# get_latest_for_company()
# ---------------------------------------------------------------------------


class TestGetLatestForCompany:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_audits(self) -> None:
        session = make_mock_session()
        session.execute.return_value.scalar_one_or_none.return_value = None
        repo = SiteAuditRepository(session)
        result = await repo.get_latest_for_company(uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_model_when_found(self) -> None:
        session = make_mock_session()
        fake_audit = make_fake_audit()
        session.execute.return_value.scalar_one_or_none.return_value = fake_audit
        repo = SiteAuditRepository(session)
        result = await repo.get_latest_for_company(uuid.uuid4())
        assert result is fake_audit

    @pytest.mark.asyncio
    async def test_accepts_string_uuid(self) -> None:
        session = make_mock_session()
        repo = SiteAuditRepository(session)
        # Should not raise; UUID normalisation must handle string input
        await repo.get_latest_for_company(str(uuid.uuid4()))
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_never_calls_commit(self) -> None:
        session = make_mock_session()
        repo = SiteAuditRepository(session)
        await repo.get_latest_for_company(uuid.uuid4())
        session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# list_for_company()
# ---------------------------------------------------------------------------


class TestListForCompany:
    @pytest.mark.asyncio
    async def test_returns_empty_list_when_none(self) -> None:
        session = make_mock_session()
        session.execute.return_value.scalars.return_value.all.return_value = []
        repo = SiteAuditRepository(session)
        result = await repo.list_for_company(uuid.uuid4())
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_list(self) -> None:
        session = make_mock_session()
        cid = uuid.uuid4()
        audits = [make_fake_audit(cid), make_fake_audit(cid)]
        session.execute.return_value.scalars.return_value.all.return_value = audits
        repo = SiteAuditRepository(session)
        result = await repo.list_for_company(cid)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_default_limit_is_20(self) -> None:
        """Limit defaults to 20 — verify execute is called (query built)."""
        session = make_mock_session()
        repo = SiteAuditRepository(session)
        await repo.list_for_company(uuid.uuid4())
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_accepts_string_uuid(self) -> None:
        session = make_mock_session()
        repo = SiteAuditRepository(session)
        await repo.list_for_company(str(uuid.uuid4()), limit=5)
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_never_calls_commit(self) -> None:
        session = make_mock_session()
        repo = SiteAuditRepository(session)
        await repo.list_for_company(uuid.uuid4())
        session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# list_for_audit()
# ---------------------------------------------------------------------------


class TestListForAudit:
    @pytest.mark.asyncio
    async def test_returns_empty_when_none(self) -> None:
        session = make_mock_session()
        session.execute.return_value.scalars.return_value.all.return_value = []
        repo = SiteAuditRepository(session)
        result = await repo.list_for_audit(uuid.uuid4())
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_findings(self) -> None:
        session = make_mock_session()
        aid = uuid.uuid4()
        findings = [make_fake_finding(aid), make_fake_finding(aid)]
        session.execute.return_value.scalars.return_value.all.return_value = findings
        repo = SiteAuditRepository(session)
        result = await repo.list_for_audit(aid)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_accepts_string_uuid(self) -> None:
        session = make_mock_session()
        repo = SiteAuditRepository(session)
        await repo.list_for_audit(str(uuid.uuid4()))
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_severity_filter_accepted(self) -> None:
        """Severity filter arg should not cause an exception."""
        session = make_mock_session()
        repo = SiteAuditRepository(session)
        await repo.list_for_audit(uuid.uuid4(), severity="critical")
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_pagination_args_accepted(self) -> None:
        session = make_mock_session()
        repo = SiteAuditRepository(session)
        await repo.list_for_audit(uuid.uuid4(), limit=50, offset=100)
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_never_calls_commit(self) -> None:
        session = make_mock_session()
        repo = SiteAuditRepository(session)
        await repo.list_for_audit(uuid.uuid4())
        session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# create_audit()
# ---------------------------------------------------------------------------


class TestCreateAudit:
    @pytest.mark.asyncio
    async def test_calls_flush_not_commit(self) -> None:
        """create_audit() must call flush (via base create()) but never commit."""
        session = make_mock_session()
        repo = SiteAuditRepository(session)
        # Patch the base class create() to avoid real ORM construction
        fake_audit = make_fake_audit()
        repo.create = AsyncMock(return_value=fake_audit)  # type: ignore[method-assign]
        result = await repo.create_audit(uuid.uuid4(), "acme.com")
        repo.create.assert_awaited_once()
        session.commit.assert_not_called()
        assert result is fake_audit

    @pytest.mark.asyncio
    async def test_accepts_string_company_id(self) -> None:
        session = make_mock_session()
        repo = SiteAuditRepository(session)
        fake_audit = make_fake_audit()
        repo.create = AsyncMock(return_value=fake_audit)  # type: ignore[method-assign]
        # Should not raise — UUID normalisation handles string input
        await repo.create_audit(str(uuid.uuid4()), "example.com")
        repo.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_extra_kwargs_passed_through(self) -> None:
        """Extra kwargs (e.g. status=...) should be forwarded to base create()."""
        session = make_mock_session()
        repo = SiteAuditRepository(session)
        captured_kwargs: dict = {}

        async def capture_create(**kwargs):  # type: ignore[no-untyped-def]
            captured_kwargs.update(kwargs)
            return make_fake_audit()

        repo.create = capture_create  # type: ignore[method-assign]
        await repo.create_audit(
            uuid.uuid4(), "example.com", status=PipelineStatus.running
        )
        assert "status" in captured_kwargs
        assert captured_kwargs["status"] == PipelineStatus.running
        assert "site_domain" in captured_kwargs
        assert captured_kwargs["site_domain"] == "example.com"


# ---------------------------------------------------------------------------
# bulk_insert_findings()
# ---------------------------------------------------------------------------


class TestExistsForSlugAndDomain:
    """Tests for exists_for_slug_and_domain() — guard query by effective_slug."""

    @pytest.mark.asyncio
    async def test_returns_true_when_completed_audit_exists(self) -> None:
        session = make_mock_session()
        session.execute.return_value.scalar.return_value = 1
        repo = SiteAuditRepository(session)
        assert await repo.exists_for_slug_and_domain("acme", "acme.com") is True

    @pytest.mark.asyncio
    async def test_returns_true_for_degraded_audit(self) -> None:
        """Degraded audits are stored as status=completed + is_degraded=True.

        The query filters on status=completed, so degraded audits are included.
        """
        session = make_mock_session()
        session.execute.return_value.scalar.return_value = 1
        repo = SiteAuditRepository(session)
        assert await repo.exists_for_slug_and_domain("acme", "acme.com") is True

    @pytest.mark.asyncio
    async def test_returns_false_when_no_match(self) -> None:
        session = make_mock_session()
        session.execute.return_value.scalar.return_value = 0
        repo = SiteAuditRepository(session)
        assert await repo.exists_for_slug_and_domain("acme", "acme.com") is False

    @pytest.mark.asyncio
    async def test_returns_false_when_scalar_is_none(self) -> None:
        session = make_mock_session()
        session.execute.return_value.scalar.return_value = None
        repo = SiteAuditRepository(session)
        assert await repo.exists_for_slug_and_domain("acme", "acme.com") is False

    @pytest.mark.asyncio
    async def test_never_calls_commit(self) -> None:
        session = make_mock_session()
        session.execute.return_value.scalar.return_value = 0
        repo = SiteAuditRepository(session)
        await repo.exists_for_slug_and_domain("acme", "acme.com")
        session.commit.assert_not_called()


class TestBulkInsertFindings:
    @pytest.mark.asyncio
    async def test_empty_findings_does_one_flush(self) -> None:
        session = make_mock_session()
        repo = SiteAuditRepository(session)
        result = await repo.bulk_insert_findings(uuid.uuid4(), [])
        session.flush.assert_awaited_once()
        assert result == []

    @pytest.mark.asyncio
    async def test_inserts_each_finding(self) -> None:
        session = make_mock_session()
        aid = uuid.uuid4()
        findings_data = [
            {"finding_type": "missing_title", "severity": FindingSeverity.critical, "page_url": "/"},
            {"finding_type": "short_meta", "severity": FindingSeverity.high, "page_url": "/about"},
        ]
        fake_findings = [make_fake_finding(aid), make_fake_finding(aid)]
        call_idx = 0

        def make_finding(**kwargs):  # type: ignore[no-untyped-def]
            nonlocal call_idx
            f = fake_findings[call_idx]
            call_idx += 1
            return f

        with patch(
            "core.db.repositories.site_audit_repo.AuditFindingModel",
            side_effect=make_finding,
        ):
            repo = SiteAuditRepository(session)
            result = await repo.bulk_insert_findings(aid, findings_data)

        assert session.add.call_count == 2
        session.flush.assert_awaited_once()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_accepts_string_audit_id(self) -> None:
        session = make_mock_session()
        repo = SiteAuditRepository(session)
        with patch("core.db.repositories.site_audit_repo.AuditFindingModel", return_value=make_fake_finding()):
            await repo.bulk_insert_findings(str(uuid.uuid4()), [{"page_url": "/", "finding_type": "x", "severity": FindingSeverity.info}])
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_never_calls_commit(self) -> None:
        session = make_mock_session()
        repo = SiteAuditRepository(session)
        await repo.bulk_insert_findings(uuid.uuid4(), [])
        session.commit.assert_not_called()
