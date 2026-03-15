"""Tests for KB-specific repositories (KBRunRepository, KBDocumentRepository, KBSynthesisRepository).

These are integration tests that require a real PostgreSQL database.
Skipped automatically when TEST_DATABASE_URL is not set.
"""
from __future__ import annotations

import os
import uuid

import pytest

from core.db.enums import ResearchRunStatus
from core.db.repositories.kb_repo import (
    KBDocumentRepository,
    KBRunRepository,
    KBSynthesisRepository,
)

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL", ""),
    reason="TEST_DATABASE_URL not set",
)


# ── Helpers ──────────────────────────────────────────────────────────


async def _create_kb_run(repo, company_id, **overrides):
    defaults = {
        "company_id": company_id,
        "effective_slug": "test-co",
        "mode": "full",
        "status": ResearchRunStatus.running,
    }
    defaults.update(overrides)
    return await repo.upsert_run(**defaults)


async def _create_kb_doc(repo, kb_run_id, **overrides):
    defaults = {
        "kb_run_id": kb_run_id,
        "doc_type": "company_overview",
        "version": 1,
        "storage_key": "knowledge_base/test-co/company_overview/v1.md",
        "status": "fresh",
        "word_count": 100,
    }
    defaults.update(overrides)
    return await repo.upsert_document(**defaults)


async def _create_synthesis(repo, kb_run_id, **overrides):
    defaults = {
        "kb_run_id": kb_run_id,
        "version": 1,
        "storage_key": "knowledge_base/test-co/synthesis/v1.md",
        "word_count": 300,
    }
    defaults.update(overrides)
    return await repo.upsert_synthesis(**defaults)


# ── KBRunRepository ─────────────────────────────────────────────────


async def test_create_and_get_by_slug(db_session, sample_company):
    repo = KBRunRepository(db_session)
    run = await _create_kb_run(repo, sample_company.id)

    assert run.id is not None
    fetched = await repo.get_by_effective_slug("test-co")
    assert fetched is not None
    assert fetched.effective_slug == "test-co"


async def test_get_by_company(db_session, sample_company):
    repo = KBRunRepository(db_session)
    await _create_kb_run(repo, sample_company.id)

    results = await repo.get_by_company(sample_company.id)
    assert len(results) >= 1
    assert all(r.company_id == sample_company.id for r in results)


async def test_update_status(db_session, sample_company):
    repo = KBRunRepository(db_session)
    run = await _create_kb_run(repo, sample_company.id)

    updated = await repo.update_status(run.id, ResearchRunStatus.completed)
    assert updated is not None
    assert updated.status == ResearchRunStatus.completed


async def test_update_synthesis_version(db_session, sample_company):
    repo = KBRunRepository(db_session)
    run = await _create_kb_run(repo, sample_company.id)

    updated = await repo.update_synthesis_version(run.id, 3)
    assert updated is not None
    assert updated.synthesis_version == 3


async def test_upsert_run_idempotent(db_session, sample_company):
    repo = KBRunRepository(db_session)
    run1 = await _create_kb_run(repo, sample_company.id)
    run2 = await _create_kb_run(
        repo, sample_company.id, status=ResearchRunStatus.completed,
    )
    assert run1.id == run2.id
    assert run2.status == ResearchRunStatus.completed


# ── KBDocumentRepository ────────────────────────────────────────────


async def test_create_and_get_doc(db_session, sample_company):
    run_repo = KBRunRepository(db_session)
    doc_repo = KBDocumentRepository(db_session)

    run = await _create_kb_run(run_repo, sample_company.id)
    doc = await _create_kb_doc(doc_repo, run.id)

    assert doc.id is not None
    fetched = await doc_repo.get_by_run_and_type(run.id, "company_overview")
    assert fetched is not None
    assert fetched.doc_type == "company_overview"


async def test_list_by_run(db_session, sample_company):
    run_repo = KBRunRepository(db_session)
    doc_repo = KBDocumentRepository(db_session)

    run = await _create_kb_run(run_repo, sample_company.id)
    await _create_kb_doc(doc_repo, run.id, doc_type="company_overview")
    await _create_kb_doc(
        doc_repo, run.id,
        doc_type="customer_reviews",
        storage_key="knowledge_base/test-co/customer_reviews/v1.md",
    )

    results = await doc_repo.list_by_run(run.id)
    assert len(results) >= 2
    types = {d.doc_type for d in results}
    assert "company_overview" in types
    assert "customer_reviews" in types


async def test_upsert_doc_idempotent(db_session, sample_company):
    run_repo = KBRunRepository(db_session)
    doc_repo = KBDocumentRepository(db_session)

    run = await _create_kb_run(run_repo, sample_company.id)
    doc1 = await _create_kb_doc(doc_repo, run.id, word_count=100)
    doc2 = await _create_kb_doc(doc_repo, run.id, word_count=200)
    assert doc1.id == doc2.id
    assert doc2.word_count == 200


async def test_delete_by_run(db_session, sample_company):
    run_repo = KBRunRepository(db_session)
    doc_repo = KBDocumentRepository(db_session)

    run = await _create_kb_run(run_repo, sample_company.id)
    await _create_kb_doc(doc_repo, run.id)
    await _create_kb_doc(
        doc_repo, run.id,
        doc_type="customer_reviews",
        storage_key="knowledge_base/test-co/customer_reviews/v1.md",
    )

    count = await doc_repo.delete_by_run(run.id)
    assert count == 2

    remaining = await doc_repo.list_by_run(run.id)
    assert len(remaining) == 0


# ── KBSynthesisRepository ──────────────────────────────────────────


async def test_create_and_get_synthesis(db_session, sample_company):
    run_repo = KBRunRepository(db_session)
    synth_repo = KBSynthesisRepository(db_session)

    run = await _create_kb_run(run_repo, sample_company.id)
    synth = await _create_synthesis(synth_repo, run.id)

    assert synth.id is not None
    fetched = await synth_repo.get_by_run(run.id)
    assert fetched is not None
    assert fetched.version == 1


async def test_get_synthesis_specific_version(db_session, sample_company):
    run_repo = KBRunRepository(db_session)
    synth_repo = KBSynthesisRepository(db_session)

    run = await _create_kb_run(run_repo, sample_company.id)
    await _create_synthesis(synth_repo, run.id, version=1)
    await _create_synthesis(
        synth_repo, run.id, version=2,
        storage_key="knowledge_base/test-co/synthesis/v2.md",
    )

    v1 = await synth_repo.get_by_run(run.id, version=1)
    assert v1 is not None
    assert v1.version == 1


async def test_upsert_synthesis_idempotent(db_session, sample_company):
    run_repo = KBRunRepository(db_session)
    synth_repo = KBSynthesisRepository(db_session)

    run = await _create_kb_run(run_repo, sample_company.id)
    s1 = await _create_synthesis(synth_repo, run.id, word_count=300)
    s2 = await _create_synthesis(synth_repo, run.id, word_count=500)
    assert s1.id == s2.id
    assert s2.word_count == 500
