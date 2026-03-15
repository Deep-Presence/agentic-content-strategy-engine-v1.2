"""Tests for DbPersonaDataService — Postgres-backed persona read service."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.services.db_persona_data import DbPersonaDataService
from core.services.persona_data import PersonaDataServiceProtocol


def _make_persona_run(*, effective_slug: str = "test-co") -> MagicMock:
    run = MagicMock()
    run.id = "persona-run-uuid-001"
    run.effective_slug = effective_slug
    run.kb_synthesis_version = 2
    return run


def _make_persona_profile(
    *,
    persona_id: str = "cfo-001",
    persona_name: str = "CFO Persona",
    version: int = 1,
    kind: str = "icp",
    status: str = "fresh",
    tagline: str = "Enterprise CFO",
    storage_key: str = "audience_personas/test-co/cfo-001/v1.md",
    content_hash: str = "def456",
    word_count: int = 200,
    created_by: str = "agent",
) -> MagicMock:
    p = MagicMock()
    p.persona_id = persona_id
    p.persona_name = persona_name
    p.version = version
    p.kind = kind
    p.status = status
    p.tagline = tagline
    p.storage_key = storage_key
    p.content_hash = content_hash
    p.word_count = word_count
    p.created_by = created_by
    p.created_at = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    return p


def _make_pipeline_run(*, completed_at: datetime | None = None) -> MagicMock:
    run = MagicMock()
    run.completed_at = completed_at or datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    run.summary = {"profiles_generated": 2}
    return run


@pytest.fixture
def svc(tmp_path: Path) -> DbPersonaDataService:
    return DbPersonaDataService(
        persona_run_repo=AsyncMock(),
        persona_profile_repo=AsyncMock(),
        pipeline_repo=AsyncMock(),
        artifacts_root=tmp_path,
    )


class TestDbPersonaDataService:
    async def test_protocol_conformance(self, tmp_path):
        svc = DbPersonaDataService(
            persona_run_repo=MagicMock(),
            persona_profile_repo=MagicMock(),
            pipeline_repo=MagicMock(),
            artifacts_root=tmp_path,
        )
        assert isinstance(svc, PersonaDataServiceProtocol)

    async def test_list_personas(self, svc):
        persona_run = _make_persona_run()
        cfo = _make_persona_profile()
        eng = _make_persona_profile(
            persona_id="eng-002", persona_name="Engineer Persona",
            kind="secondary",
            storage_key="audience_personas/test-co/eng-002/v1.md",
        )
        svc._persona_run_repo.get_by_effective_slug.return_value = persona_run
        svc._persona_profile_repo.list_by_run.return_value = [cfo, eng]

        result = await svc.list_personas("test-co")

        assert len(result) == 2
        ids = {p["persona_id"] for p in result}
        assert "cfo-001" in ids
        assert "eng-002" in ids
        for p in result:
            assert "last_updated" in p
            assert p["last_updated"] is not None

    async def test_list_personas_no_run(self, svc):
        svc._persona_run_repo.get_by_effective_slug.return_value = None

        result = await svc.list_personas("test-co")
        assert result == []

    async def test_list_personas_deduplicates_versions(self, svc):
        persona_run = _make_persona_run()
        v1 = _make_persona_profile(version=1)
        v2 = _make_persona_profile(
            version=2,
            storage_key="audience_personas/test-co/cfo-001/v2.md",
        )
        svc._persona_run_repo.get_by_effective_slug.return_value = persona_run
        svc._persona_profile_repo.list_by_run.return_value = [v1, v2]

        result = await svc.list_personas("test-co")

        assert len(result) == 1
        assert result[0]["current_version"] == 2

    async def test_get_persona(self, svc, tmp_path):
        doc_path = tmp_path / "audience_personas" / "test-co" / "cfo-001"
        doc_path.mkdir(parents=True)
        (doc_path / "v1.md").write_text("# CFO Persona\n\nFinance leader.")

        persona_run = _make_persona_run()
        profile = _make_persona_profile()
        svc._persona_run_repo.get_by_effective_slug.return_value = persona_run
        svc._persona_profile_repo.get_by_run_and_persona_id.return_value = profile

        result = await svc.get_persona("test-co", "cfo-001")

        assert result is not None
        assert result["persona_id"] == "cfo-001"
        assert "Finance" in result["content_md"]

    async def test_get_persona_missing_run(self, svc):
        svc._persona_run_repo.get_by_effective_slug.return_value = None

        result = await svc.get_persona("test-co", "nonexistent")
        assert result is None

    async def test_get_persona_missing_profile(self, svc):
        svc._persona_run_repo.get_by_effective_slug.return_value = _make_persona_run()
        svc._persona_profile_repo.get_by_run_and_persona_id.return_value = None

        result = await svc.get_persona("test-co", "nonexistent")
        assert result is None

    async def test_get_persona_with_version(self, svc, tmp_path):
        doc_path = tmp_path / "audience_personas" / "test-co" / "cfo-001"
        doc_path.mkdir(parents=True)
        (doc_path / "v2.md").write_text("# CFO v2")

        persona_run = _make_persona_run()
        profile = _make_persona_profile(
            version=2,
            storage_key="audience_personas/test-co/cfo-001/v2.md",
        )
        svc._persona_run_repo.get_by_effective_slug.return_value = persona_run
        svc._persona_profile_repo.get_by_run_and_persona_id.return_value = profile

        result = await svc.get_persona("test-co", "cfo-001", version=2)
        assert result is not None
        assert result["version"] == 2

    async def test_get_summary(self, svc):
        persona_run = _make_persona_run()
        cfo = _make_persona_profile(status="fresh")
        eng = _make_persona_profile(
            persona_id="eng-002", persona_name="Engineer Persona",
            status="fresh",
            storage_key="audience_personas/test-co/eng-002/v1.md",
        )
        run = _make_pipeline_run()

        svc._persona_run_repo.get_by_effective_slug.return_value = persona_run
        svc._persona_profile_repo.list_by_run.return_value = [cfo, eng]
        svc._pipeline_repo.get_latest_completed.return_value = run

        result = await svc.get_summary("test-co")

        assert result["slug"] == "test-co"
        assert result["total_personas"] == 2
        assert "company_name" in result
        assert result["last_full_run"] is not None
        assert result["kb_synthesis_version"] == 2

    async def test_get_summary_no_runs(self, svc):
        svc._persona_run_repo.get_by_effective_slug.return_value = None
        svc._pipeline_repo.get_latest_completed.return_value = None

        result = await svc.get_summary("test-co")

        assert result["last_full_run"] is None
        assert result["kb_synthesis_version"] is None

    async def test_check_staleness_delegates(self, svc):
        result = await svc.check_staleness("test-co")
        assert isinstance(result, dict)
        assert "stale_personas" in result
