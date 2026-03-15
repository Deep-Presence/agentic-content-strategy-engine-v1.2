"""Tests for DbKBDataService — Postgres-backed KB read service."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.services.db_kb_data import DbKBDataService
from core.services.kb_data import KBDataServiceProtocol


def _make_kb_run(*, effective_slug: str = "test-co") -> MagicMock:
    run = MagicMock()
    run.id = "run-uuid-001"
    run.effective_slug = effective_slug
    run.status = "running"
    return run


def _make_kb_doc(
    *,
    doc_type: str = "company_overview",
    version: int = 1,
    word_count: int = 100,
    status: str = "fresh",
    storage_key: str = "knowledge_base/test-co/company_overview/v1.md",
    content_hash: str = "abc123",
) -> MagicMock:
    d = MagicMock()
    d.doc_type = doc_type
    d.version = version
    d.word_count = word_count
    d.status = status
    d.storage_key = storage_key
    d.content_hash = content_hash
    d.created_at = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    return d


def _make_kb_synthesis(
    *, version: int = 1, storage_key: str = "knowledge_base/test-co/synthesis/v1.md",
    content_hash: str = "synth123", word_count: int = 300,
) -> MagicMock:
    s = MagicMock()
    s.version = version
    s.storage_key = storage_key
    s.content_hash = content_hash
    s.word_count = word_count
    return s


def _make_pipeline_run(*, completed_at: datetime | None = None) -> MagicMock:
    run = MagicMock()
    run.completed_at = completed_at or datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    run.summary = {"mode": "full", "docs_changed": 3}
    return run


@pytest.fixture
def svc(tmp_path: Path) -> DbKBDataService:
    return DbKBDataService(
        kb_run_repo=AsyncMock(),
        kb_doc_repo=AsyncMock(),
        kb_synth_repo=AsyncMock(),
        pipeline_repo=AsyncMock(),
        artifacts_root=tmp_path,
    )


class TestDbKBDataService:
    async def test_protocol_conformance(self, tmp_path):
        svc = DbKBDataService(
            kb_run_repo=MagicMock(),
            kb_doc_repo=MagicMock(),
            kb_synth_repo=MagicMock(),
            pipeline_repo=MagicMock(),
            artifacts_root=tmp_path,
        )
        assert isinstance(svc, KBDataServiceProtocol)

    async def test_get_summary(self, svc):
        kb_run = _make_kb_run()
        overview = _make_kb_doc(doc_type="company_overview", version=2)
        reviews = _make_kb_doc(
            doc_type="customer_reviews", version=1,
            storage_key="knowledge_base/test-co/customer_reviews/v1.md",
        )
        synthesis = _make_kb_synthesis(version=3)
        run = _make_pipeline_run()

        svc._kb_run_repo.get_by_effective_slug.return_value = kb_run
        svc._kb_doc_repo.list_by_run.return_value = [overview, reviews]
        svc._kb_synth_repo.get_by_run.return_value = synthesis
        svc._pipeline_repo.get_latest_completed.return_value = run

        result = await svc.get_summary("test-co")

        assert result["slug"] == "test-co"
        assert "company_name" in result
        assert "company_overview" in result["docs"]
        assert result["docs"]["company_overview"]["version"] == 2
        assert result["docs"]["company_overview"]["has_content"] is True
        assert result["docs"]["company_overview"]["updated_at"] is not None
        assert result["synthesis_version"] == 3
        assert result["last_full_refresh"] is not None

    async def test_get_summary_no_run(self, svc):
        svc._kb_run_repo.get_by_effective_slug.return_value = None

        result = await svc.get_summary("test-co")

        assert result["synthesis_version"] == 0
        assert result["last_full_refresh"] is None
        assert "company_name" in result

    async def test_get_doc(self, svc, tmp_path):
        doc_path = tmp_path / "knowledge_base" / "test-co" / "company_overview"
        doc_path.mkdir(parents=True)
        (doc_path / "v1.md").write_text("# Company Overview\n\nFintech company.")

        kb_run = _make_kb_run()
        doc = _make_kb_doc(
            storage_key="knowledge_base/test-co/company_overview/v1.md",
        )
        svc._kb_run_repo.get_by_effective_slug.return_value = kb_run
        svc._kb_doc_repo.get_by_run_and_type.return_value = doc

        result = await svc.get_doc("test-co", "company_overview")

        assert result is not None
        assert result["doc_type"] == "company_overview"
        assert "Fintech" in result["content_md"]

    async def test_get_doc_missing_run(self, svc):
        svc._kb_run_repo.get_by_effective_slug.return_value = None

        result = await svc.get_doc("test-co", "nonexistent")
        assert result is None

    async def test_get_doc_missing_doc(self, svc):
        svc._kb_run_repo.get_by_effective_slug.return_value = _make_kb_run()
        svc._kb_doc_repo.get_by_run_and_type.return_value = None

        result = await svc.get_doc("test-co", "nonexistent")
        assert result is None

    async def test_get_doc_with_version(self, svc, tmp_path):
        doc_path = tmp_path / "knowledge_base" / "test-co" / "company_overview"
        doc_path.mkdir(parents=True)
        (doc_path / "v2.md").write_text("# Updated Overview")

        kb_run = _make_kb_run()
        doc = _make_kb_doc(
            version=2,
            storage_key="knowledge_base/test-co/company_overview/v2.md",
        )
        svc._kb_run_repo.get_by_effective_slug.return_value = kb_run
        svc._kb_doc_repo.get_by_run_and_type.return_value = doc

        result = await svc.get_doc("test-co", "company_overview", version=2)
        assert result is not None
        assert result["version"] == 2

    async def test_get_synthesis(self, svc, tmp_path):
        synth_path = tmp_path / "knowledge_base" / "test-co" / "synthesis"
        synth_path.mkdir(parents=True)
        (synth_path / "v1.md").write_text("# Synthesis\n\nConsolidated profile.")

        kb_run = _make_kb_run()
        synthesis = _make_kb_synthesis(
            storage_key="knowledge_base/test-co/synthesis/v1.md",
        )
        svc._kb_run_repo.get_by_effective_slug.return_value = kb_run
        svc._kb_synth_repo.get_by_run.return_value = synthesis

        result = await svc.get_synthesis("test-co")
        assert result is not None
        assert "Consolidated" in result["content_md"]
        assert result["word_count"] > 0
        assert "sha256" in result
        assert result["sha256"] == "synth123"

    async def test_get_synthesis_missing(self, svc):
        svc._kb_run_repo.get_by_effective_slug.return_value = None

        result = await svc.get_synthesis("test-co")
        assert result is None

    async def test_get_health_delegates(self, svc):
        result = await svc.get_health("test-co")
        assert isinstance(result, dict)
