"""Tests for DbVSGDataService — Postgres-backed VSG read service."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.services.db_vsg_data import DbVSGDataService
from core.services.vsg_data import VSGDataServiceProtocol


def _make_vsg_run(*, effective_slug: str = "test-co") -> MagicMock:
    run = MagicMock()
    run.id = "vsg-run-uuid-001"
    run.effective_slug = effective_slug
    return run


def _make_vsg_author(
    *,
    author_id: str = "author-001",
    name: str = "Jane Doe",
    version: int = 1,
    status: str = "fresh",
    storage_key: str = "voice_style_guide/test-co/author-001/v1.md",
    word_count: int = 80,
) -> MagicMock:
    a = MagicMock()
    a.author_id = author_id
    a.name = name
    a.version = version
    a.status = status
    a.storage_key = storage_key
    a.word_count = word_count
    a.created_at = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    return a


def _make_vsg_guide(
    *,
    version: int = 1,
    storage_key: str = "voice_style_guide/test-co/guide/v1.md",
    word_count: int = 150,
    source_authors: list | None = None,
) -> MagicMock:
    g = MagicMock()
    g.version = version
    g.storage_key = storage_key
    g.word_count = word_count
    g.source_authors = source_authors or ["author-001", "author-002"]
    g.created_at = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    return g


def _make_pipeline_run(*, completed_at: datetime | None = None) -> MagicMock:
    run = MagicMock()
    run.completed_at = completed_at or datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    run.summary = {"authors_researched": 2, "guide_generated": True}
    return run


@pytest.fixture
def svc(tmp_path: Path) -> DbVSGDataService:
    return DbVSGDataService(
        vsg_run_repo=AsyncMock(),
        vsg_author_repo=AsyncMock(),
        vsg_guide_repo=AsyncMock(),
        pipeline_repo=AsyncMock(),
        artifacts_root=tmp_path,
    )


class TestDbVSGDataService:
    async def test_protocol_conformance(self, tmp_path):
        svc = DbVSGDataService(
            vsg_run_repo=MagicMock(),
            vsg_author_repo=MagicMock(),
            vsg_guide_repo=MagicMock(),
            pipeline_repo=MagicMock(),
            artifacts_root=tmp_path,
        )
        assert isinstance(svc, VSGDataServiceProtocol)

    async def test_get_summary(self, svc, tmp_path):
        vsg_run = _make_vsg_run()
        author = _make_vsg_author()
        guide = _make_vsg_guide()
        run = _make_pipeline_run()

        svc._vsg_run_repo.get_by_effective_slug.return_value = vsg_run
        svc._vsg_author_repo.list_by_run.return_value = [author]
        svc._vsg_guide_repo.get_by_run.return_value = guide
        svc._pipeline_repo.get_latest_completed.return_value = run

        result = await svc.get_summary("test-co")

        assert result["slug"] == "test-co"
        assert result["has_guide"] is True
        assert result["guide_word_count"] > 0
        assert result["authors_count"] == 1
        assert "company_name" in result
        assert result["last_full_run"] is not None

    async def test_get_summary_no_run(self, svc):
        svc._vsg_run_repo.get_by_effective_slug.return_value = None
        svc._pipeline_repo.get_latest_completed.return_value = None

        result = await svc.get_summary("test-co")

        assert result["has_guide"] is False
        assert result["guide_word_count"] == 0
        assert result["last_full_run"] is None

    async def test_get_guide(self, svc, tmp_path):
        guide_path = tmp_path / "voice_style_guide" / "test-co" / "guide"
        guide_path.mkdir(parents=True)
        (guide_path / "v1.md").write_text("# Voice Guide\n\nAuthoritative yet approachable.")

        vsg_run = _make_vsg_run()
        guide = _make_vsg_guide()
        svc._vsg_run_repo.get_by_effective_slug.return_value = vsg_run
        svc._vsg_guide_repo.get_by_run.return_value = guide

        result = await svc.get_guide("test-co")

        assert result is not None
        assert "Authoritative" in result["content_md"]
        assert result["version"] == 1
        assert result["last_updated"] is not None
        assert result["source_authors"] == ["author-001", "author-002"]

    async def test_get_guide_missing_run(self, svc):
        svc._vsg_run_repo.get_by_effective_slug.return_value = None

        result = await svc.get_guide("test-co")
        assert result is None

    async def test_get_guide_missing_guide(self, svc):
        svc._vsg_run_repo.get_by_effective_slug.return_value = _make_vsg_run()
        svc._vsg_guide_repo.get_by_run.return_value = None

        result = await svc.get_guide("test-co")
        assert result is None

    async def test_list_authors(self, svc):
        vsg_run = _make_vsg_run()
        author1 = _make_vsg_author()
        author2 = _make_vsg_author(
            author_id="author-002", name="John Smith",
            storage_key="voice_style_guide/test-co/author-002/v1.md",
        )
        svc._vsg_run_repo.get_by_effective_slug.return_value = vsg_run
        svc._vsg_author_repo.list_by_run.return_value = [author1, author2]

        result = await svc.list_authors("test-co")

        assert len(result) == 2
        names = {a["name"] for a in result}
        assert "Jane Doe" in names

    async def test_list_authors_no_run(self, svc):
        svc._vsg_run_repo.get_by_effective_slug.return_value = None

        result = await svc.list_authors("test-co")
        assert result == []

    async def test_get_author_research(self, svc, tmp_path):
        author_path = tmp_path / "voice_style_guide" / "test-co" / "author-001"
        author_path.mkdir(parents=True)
        (author_path / "v1.md").write_text("# Jane Doe Research\n\nWriting analysis.")

        vsg_run = _make_vsg_run()
        author = _make_vsg_author()
        svc._vsg_run_repo.get_by_effective_slug.return_value = vsg_run
        svc._vsg_author_repo.get_by_run_and_author_id.return_value = author

        result = await svc.get_author_research("test-co", "author-001")

        assert result is not None
        assert "Writing analysis" in result["content_md"]

    async def test_get_author_research_missing(self, svc):
        svc._vsg_run_repo.get_by_effective_slug.return_value = _make_vsg_run()
        svc._vsg_author_repo.get_by_run_and_author_id.return_value = None

        result = await svc.get_author_research("test-co", "nonexistent")
        assert result is None
