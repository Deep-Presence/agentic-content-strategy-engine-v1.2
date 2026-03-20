"""Tests for ResearchArtifactRepository."""
from __future__ import annotations

import os
import uuid

import pytest

from core.db.enums import ArtifactStatus, ArtifactType
from core.db.repositories.research_artifact_repo import ResearchArtifactRepository

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL", ""),
    reason="TEST_DATABASE_URL not set",
)


# ── Helpers ──────────────────────────────────────────────────────────


async def _create_artifact(repo, company_id, **overrides):
    """Shortcut to create an artifact with sensible defaults."""
    defaults = {
        "company_id": company_id,
        "effective_slug": "test-co",
        "artifact_type": ArtifactType.knowledge_base,
        "version": 1,
        "storage_key": "knowledge_base/test-co/company_overview/v1.md",
        "title": "company_overview",
        "status": ArtifactStatus.fresh,
    }
    defaults.update(overrides)
    return await repo.upsert_artifact(**defaults)


# ── Create / Get ─────────────────────────────────────────────────────


async def test_create_and_get_by_id(db_session, sample_company):
    """upsert_artifact() creates a row retrievable by get_by_id()."""
    repo = ResearchArtifactRepository(db_session)
    artifact = await _create_artifact(repo, sample_company.id)

    assert artifact.id is not None
    fetched = await repo.get_by_id(artifact.id)
    assert fetched is not None
    assert fetched.effective_slug == "test-co"
    assert fetched.artifact_type == ArtifactType.knowledge_base


async def test_get_by_slug_and_type(db_session, sample_company):
    """get_by_slug_and_type() returns matching artifact."""
    repo = ResearchArtifactRepository(db_session)
    await _create_artifact(repo, sample_company.id)

    result = await repo.get_by_slug_and_type(
        "test-co", ArtifactType.knowledge_base,
    )
    assert result is not None
    assert result.title == "company_overview"


async def test_get_by_slug_and_type_with_version(db_session, sample_company):
    """get_by_slug_and_type() with explicit version returns exact match."""
    repo = ResearchArtifactRepository(db_session)
    await _create_artifact(repo, sample_company.id, version=1)
    await _create_artifact(repo, sample_company.id, version=2,
                           storage_key="knowledge_base/test-co/company_overview/v2.md")

    v1 = await repo.get_by_slug_and_type(
        "test-co", ArtifactType.knowledge_base, version=1,
    )
    assert v1 is not None
    assert v1.version == 1


async def test_get_by_slug_and_type_returns_latest_by_default(db_session, sample_company):
    """Without version, get_by_slug_and_type() returns highest version."""
    repo = ResearchArtifactRepository(db_session)
    await _create_artifact(repo, sample_company.id, version=1)
    await _create_artifact(repo, sample_company.id, version=3,
                           storage_key="knowledge_base/test-co/company_overview/v3.md")

    latest = await repo.get_by_slug_and_type(
        "test-co", ArtifactType.knowledge_base,
    )
    assert latest is not None
    assert latest.version == 3


async def test_get_latest_by_slug_and_type(db_session, sample_company):
    """get_latest_by_slug_and_type() delegates correctly."""
    repo = ResearchArtifactRepository(db_session)
    await _create_artifact(repo, sample_company.id, version=2,
                           storage_key="knowledge_base/test-co/company_overview/v2.md")

    latest = await repo.get_latest_by_slug_and_type(
        "test-co", ArtifactType.knowledge_base,
    )
    assert latest is not None
    assert latest.version == 2


# ── List ─────────────────────────────────────────────────────────────


async def test_list_by_slug(db_session, sample_company):
    """list_by_slug() returns all artifacts for a slug."""
    repo = ResearchArtifactRepository(db_session)
    await _create_artifact(repo, sample_company.id,
                           artifact_type=ArtifactType.knowledge_base,
                           title="company_overview")
    await _create_artifact(repo, sample_company.id,
                           artifact_type=ArtifactType.persona,
                           title="cfo_persona",
                           storage_key="audience_persona/test-co/cfo/v1.md")

    results = await repo.list_by_slug("test-co")
    assert len(results) >= 2
    types = {r.artifact_type for r in results}
    assert ArtifactType.knowledge_base in types
    assert ArtifactType.persona in types


async def test_list_by_slug_filtered(db_session, sample_company):
    """list_by_slug() with artifact_type filter narrows results."""
    repo = ResearchArtifactRepository(db_session)
    await _create_artifact(repo, sample_company.id,
                           artifact_type=ArtifactType.knowledge_base,
                           title="company_overview")
    await _create_artifact(repo, sample_company.id,
                           artifact_type=ArtifactType.persona,
                           title="eng_persona",
                           storage_key="audience_persona/test-co/eng/v1.md")

    kb_only = await repo.list_by_slug(
        "test-co", artifact_type=ArtifactType.knowledge_base,
    )
    assert all(r.artifact_type == ArtifactType.knowledge_base for r in kb_only)


async def test_list_by_company(db_session, sample_company):
    """list_by_company() returns artifacts for a company."""
    repo = ResearchArtifactRepository(db_session)
    await _create_artifact(repo, sample_company.id)

    results = await repo.list_by_company(sample_company.id)
    assert len(results) >= 1
    assert all(r.company_id == sample_company.id for r in results)


async def test_list_by_company_filtered(db_session, sample_company):
    """list_by_company() with type filter narrows results."""
    repo = ResearchArtifactRepository(db_session)
    await _create_artifact(repo, sample_company.id,
                           artifact_type=ArtifactType.knowledge_base,
                           title="overview")
    await _create_artifact(repo, sample_company.id,
                           artifact_type=ArtifactType.style_guide,
                           title=None,
                           storage_key="voice_style_guide/test-co/v1.md")

    guides = await repo.list_by_company(
        sample_company.id, artifact_type=ArtifactType.style_guide,
    )
    assert all(r.artifact_type == ArtifactType.style_guide for r in guides)


# ── Upsert Idempotency ──────────────────────────────────────────────


async def test_upsert_updates_existing(db_session, sample_company):
    """upsert_artifact() updates status/hash on duplicate key."""
    repo = ResearchArtifactRepository(db_session)
    first = await _create_artifact(
        repo, sample_company.id,
        status=ArtifactStatus.fresh,
        content_hash="abc123",
    )
    first_id = first.id

    second = await _create_artifact(
        repo, sample_company.id,
        status=ArtifactStatus.approved,
        content_hash="def456",
    )

    # Same row updated, not a new row
    assert second.id == first_id
    assert second.status == ArtifactStatus.approved
    assert second.content_hash == "def456"


async def test_upsert_creates_new_for_different_version(db_session, sample_company):
    """upsert_artifact() inserts new row for different version."""
    repo = ResearchArtifactRepository(db_session)
    v1 = await _create_artifact(repo, sample_company.id, version=1)
    v2 = await _create_artifact(repo, sample_company.id, version=2,
                                storage_key="knowledge_base/test-co/company_overview/v2.md")

    assert v1.id != v2.id
    assert v1.version == 1
    assert v2.version == 2


# ── Delete ───────────────────────────────────────────────────────────


async def test_delete_by_slug_and_type(db_session, sample_company):
    """delete_by_slug_and_type() removes matching rows and returns count."""
    repo = ResearchArtifactRepository(db_session)
    await _create_artifact(repo, sample_company.id, version=1)
    await _create_artifact(repo, sample_company.id, version=2,
                           storage_key="knowledge_base/test-co/company_overview/v2.md")

    count = await repo.delete_by_slug_and_type(
        "test-co", ArtifactType.knowledge_base,
    )
    assert count == 2

    remaining = await repo.list_by_slug(
        "test-co", artifact_type=ArtifactType.knowledge_base,
    )
    assert len(remaining) == 0


async def test_delete_returns_zero_for_nonexistent(db_session, sample_company):
    """delete_by_slug_and_type() returns 0 when no rows match."""
    repo = ResearchArtifactRepository(db_session)
    count = await repo.delete_by_slug_and_type(
        "nonexistent-slug", ArtifactType.knowledge_base,
    )
    assert count == 0
