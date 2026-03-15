"""Tests for VSG-specific repositories (VSGRunRepository, VSGAuthorRepository, VSGGuideRepository).

These are integration tests that require a real PostgreSQL database.
Skipped automatically when TEST_DATABASE_URL is not set.
"""
from __future__ import annotations

import os
import uuid

import pytest

from core.db.enums import ResearchRunStatus
from core.db.repositories.vsg_repo import (
    VSGAuthorRepository,
    VSGGuideRepository,
    VSGRunRepository,
)

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL", ""),
    reason="TEST_DATABASE_URL not set",
)


# ── Helpers ──────────────────────────────────────────────────────────


async def _create_vsg_run(repo, company_id, **overrides):
    defaults = {
        "company_id": company_id,
        "effective_slug": "test-co",
        "status": ResearchRunStatus.running,
    }
    defaults.update(overrides)
    return await repo.upsert_run(**defaults)


async def _create_author(repo, vsg_run_id, **overrides):
    defaults = {
        "vsg_run_id": vsg_run_id,
        "author_id": "author-001",
        "name": "Jane Doe",
        "version": 1,
        "storage_key": "voice_style_guide/test-co/author-001/v1.md",
        "status": "fresh",
        "word_count": 80,
    }
    defaults.update(overrides)
    return await repo.upsert_author(**defaults)


async def _create_guide(repo, vsg_run_id, **overrides):
    defaults = {
        "vsg_run_id": vsg_run_id,
        "version": 1,
        "storage_key": "voice_style_guide/test-co/guide/v1.md",
        "word_count": 150,
        "source_authors": ["author-001", "author-002"],
    }
    defaults.update(overrides)
    return await repo.upsert_guide(**defaults)


# ── VSGRunRepository ────────────────────────────────────────────────


async def test_create_and_get_by_slug(db_session, sample_company):
    repo = VSGRunRepository(db_session)
    run = await _create_vsg_run(repo, sample_company.id)

    assert run.id is not None
    fetched = await repo.get_by_effective_slug("test-co")
    assert fetched is not None
    assert fetched.effective_slug == "test-co"


async def test_get_by_company(db_session, sample_company):
    repo = VSGRunRepository(db_session)
    await _create_vsg_run(repo, sample_company.id)

    results = await repo.get_by_company(sample_company.id)
    assert len(results) >= 1


async def test_update_status(db_session, sample_company):
    repo = VSGRunRepository(db_session)
    run = await _create_vsg_run(repo, sample_company.id)

    updated = await repo.update_status(run.id, ResearchRunStatus.completed)
    assert updated is not None
    assert updated.status == ResearchRunStatus.completed


async def test_upsert_run_idempotent(db_session, sample_company):
    repo = VSGRunRepository(db_session)
    run1 = await _create_vsg_run(repo, sample_company.id)
    run2 = await _create_vsg_run(
        repo, sample_company.id, status=ResearchRunStatus.completed,
    )
    assert run1.id == run2.id
    assert run2.status == ResearchRunStatus.completed


# ── VSGAuthorRepository ─────────────────────────────────────────────


async def test_create_and_get_author(db_session, sample_company):
    run_repo = VSGRunRepository(db_session)
    author_repo = VSGAuthorRepository(db_session)

    run = await _create_vsg_run(run_repo, sample_company.id)
    author = await _create_author(author_repo, run.id)

    assert author.id is not None
    fetched = await author_repo.get_by_run_and_author_id(run.id, "author-001")
    assert fetched is not None
    assert fetched.name == "Jane Doe"


async def test_list_authors_by_run(db_session, sample_company):
    run_repo = VSGRunRepository(db_session)
    author_repo = VSGAuthorRepository(db_session)

    run = await _create_vsg_run(run_repo, sample_company.id)
    await _create_author(author_repo, run.id, author_id="author-001")
    await _create_author(
        author_repo, run.id,
        author_id="author-002",
        name="John Smith",
        storage_key="voice_style_guide/test-co/author-002/v1.md",
    )

    results = await author_repo.list_by_run(run.id)
    assert len(results) >= 2
    aids = {a.author_id for a in results}
    assert "author-001" in aids
    assert "author-002" in aids


async def test_upsert_author_idempotent(db_session, sample_company):
    run_repo = VSGRunRepository(db_session)
    author_repo = VSGAuthorRepository(db_session)

    run = await _create_vsg_run(run_repo, sample_company.id)
    a1 = await _create_author(author_repo, run.id, word_count=80)
    a2 = await _create_author(author_repo, run.id, word_count=120)
    assert a1.id == a2.id
    assert a2.word_count == 120


async def test_get_author_specific_version(db_session, sample_company):
    run_repo = VSGRunRepository(db_session)
    author_repo = VSGAuthorRepository(db_session)

    run = await _create_vsg_run(run_repo, sample_company.id)
    await _create_author(author_repo, run.id, version=1)
    await _create_author(
        author_repo, run.id, version=2,
        storage_key="voice_style_guide/test-co/author-001/v2.md",
    )

    v1 = await author_repo.get_by_run_and_author_id(
        run.id, "author-001", version=1,
    )
    assert v1 is not None
    assert v1.version == 1


# ── VSGGuideRepository ──────────────────────────────────────────────


async def test_create_and_get_guide(db_session, sample_company):
    run_repo = VSGRunRepository(db_session)
    guide_repo = VSGGuideRepository(db_session)

    run = await _create_vsg_run(run_repo, sample_company.id)
    guide = await _create_guide(guide_repo, run.id)

    assert guide.id is not None
    fetched = await guide_repo.get_by_run(run.id)
    assert fetched is not None
    assert fetched.version == 1


async def test_get_guide_specific_version(db_session, sample_company):
    run_repo = VSGRunRepository(db_session)
    guide_repo = VSGGuideRepository(db_session)

    run = await _create_vsg_run(run_repo, sample_company.id)
    await _create_guide(guide_repo, run.id, version=1)
    await _create_guide(
        guide_repo, run.id, version=2,
        storage_key="voice_style_guide/test-co/guide/v2.md",
    )

    v1 = await guide_repo.get_by_run(run.id, version=1)
    assert v1 is not None
    assert v1.version == 1


async def test_upsert_guide_idempotent(db_session, sample_company):
    run_repo = VSGRunRepository(db_session)
    guide_repo = VSGGuideRepository(db_session)

    run = await _create_vsg_run(run_repo, sample_company.id)
    g1 = await _create_guide(guide_repo, run.id, word_count=150)
    g2 = await _create_guide(guide_repo, run.id, word_count=250)
    assert g1.id == g2.id
    assert g2.word_count == 250


async def test_guide_source_authors(db_session, sample_company):
    run_repo = VSGRunRepository(db_session)
    guide_repo = VSGGuideRepository(db_session)

    run = await _create_vsg_run(run_repo, sample_company.id)
    guide = await _create_guide(
        guide_repo, run.id,
        source_authors=["Jane Doe", "John Smith"],
    )
    assert guide.source_authors == ["Jane Doe", "John Smith"]
