"""Tests for AP-specific repositories (PersonaRunRepository, PersonaProfileRepository).

These are integration tests that require a real PostgreSQL database.
Skipped automatically when TEST_DATABASE_URL is not set.
"""
from __future__ import annotations

import os
import uuid

import pytest

from core.db.enums import ResearchRunStatus
from core.db.repositories.persona_repo import (
    PersonaProfileRepository,
    PersonaRunRepository,
)

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL", ""),
    reason="TEST_DATABASE_URL not set",
)


# ── Helpers ──────────────────────────────────────────────────────────


async def _create_persona_run(repo, company_id, **overrides):
    defaults = {
        "company_id": company_id,
        "effective_slug": "test-co",
        "status": ResearchRunStatus.running,
    }
    defaults.update(overrides)
    return await repo.upsert_run(**defaults)


async def _create_profile(repo, persona_run_id, **overrides):
    defaults = {
        "persona_run_id": persona_run_id,
        "persona_id": "cfo-001",
        "persona_name": "CFO Persona",
        "version": 1,
        "storage_key": "audience_personas/test-co/cfo-001/v1.md",
        "kind": "icp",
        "status": "fresh",
        "word_count": 200,
    }
    defaults.update(overrides)
    return await repo.upsert_profile(**defaults)


# ── PersonaRunRepository ────────────────────────────────────────────


async def test_create_and_get_by_slug(db_session, sample_company):
    repo = PersonaRunRepository(db_session)
    run = await _create_persona_run(repo, sample_company.id)

    assert run.id is not None
    fetched = await repo.get_by_effective_slug("test-co")
    assert fetched is not None
    assert fetched.effective_slug == "test-co"


async def test_get_by_company(db_session, sample_company):
    repo = PersonaRunRepository(db_session)
    await _create_persona_run(repo, sample_company.id)

    results = await repo.get_by_company(sample_company.id)
    assert len(results) >= 1


async def test_update_status(db_session, sample_company):
    repo = PersonaRunRepository(db_session)
    run = await _create_persona_run(repo, sample_company.id)

    updated = await repo.update_status(run.id, ResearchRunStatus.completed)
    assert updated is not None
    assert updated.status == ResearchRunStatus.completed


async def test_upsert_run_idempotent(db_session, sample_company):
    repo = PersonaRunRepository(db_session)
    run1 = await _create_persona_run(repo, sample_company.id)
    run2 = await _create_persona_run(
        repo, sample_company.id, status=ResearchRunStatus.completed,
    )
    assert run1.id == run2.id
    assert run2.status == ResearchRunStatus.completed


# ── PersonaProfileRepository ────────────────────────────────────────


async def test_create_and_get_profile(db_session, sample_company):
    run_repo = PersonaRunRepository(db_session)
    profile_repo = PersonaProfileRepository(db_session)

    run = await _create_persona_run(run_repo, sample_company.id)
    profile = await _create_profile(profile_repo, run.id)

    assert profile.id is not None
    fetched = await profile_repo.get_by_run_and_persona_id(run.id, "cfo-001")
    assert fetched is not None
    assert fetched.persona_name == "CFO Persona"


async def test_list_by_run(db_session, sample_company):
    run_repo = PersonaRunRepository(db_session)
    profile_repo = PersonaProfileRepository(db_session)

    run = await _create_persona_run(run_repo, sample_company.id)
    await _create_profile(profile_repo, run.id, persona_id="cfo-001")
    await _create_profile(
        profile_repo, run.id,
        persona_id="eng-002",
        persona_name="Engineer Persona",
        storage_key="audience_personas/test-co/eng-002/v1.md",
    )

    results = await profile_repo.list_by_run(run.id)
    assert len(results) >= 2
    pids = {p.persona_id for p in results}
    assert "cfo-001" in pids
    assert "eng-002" in pids


async def test_upsert_profile_idempotent(db_session, sample_company):
    run_repo = PersonaRunRepository(db_session)
    profile_repo = PersonaProfileRepository(db_session)

    run = await _create_persona_run(run_repo, sample_company.id)
    p1 = await _create_profile(profile_repo, run.id, word_count=200)
    p2 = await _create_profile(profile_repo, run.id, word_count=400)
    assert p1.id == p2.id
    assert p2.word_count == 400


async def test_count_by_run(db_session, sample_company):
    run_repo = PersonaRunRepository(db_session)
    profile_repo = PersonaProfileRepository(db_session)

    run = await _create_persona_run(run_repo, sample_company.id)
    await _create_profile(profile_repo, run.id, persona_id="cfo-001")
    await _create_profile(
        profile_repo, run.id,
        persona_id="eng-002",
        persona_name="Engineer",
        storage_key="audience_personas/test-co/eng-002/v1.md",
    )

    count = await profile_repo.count_by_run(run.id)
    assert count == 2


async def test_get_profile_specific_version(db_session, sample_company):
    run_repo = PersonaRunRepository(db_session)
    profile_repo = PersonaProfileRepository(db_session)

    run = await _create_persona_run(run_repo, sample_company.id)
    await _create_profile(profile_repo, run.id, version=1)
    await _create_profile(
        profile_repo, run.id, version=2,
        storage_key="audience_personas/test-co/cfo-001/v2.md",
    )

    v1 = await profile_repo.get_by_run_and_persona_id(
        run.id, "cfo-001", version=1,
    )
    assert v1 is not None
    assert v1.version == 1
