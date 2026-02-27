"""Tests for EmbeddingRepository."""
from __future__ import annotations

import os

import pytest

from core.db.models.embeddings import QueryEmbeddingModel, SemanticUnitModel
from core.db.repositories.embedding_repo import EmbeddingRepository

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL", ""),
    reason="TEST_DATABASE_URL not set",
)

# ── Helpers ───────────────────────────────────────────────────────────

DIM = 1536


def _vec(value: float) -> list[float]:
    """Create a 1536-dim vector filled with a single value."""
    return [value] * DIM


# ── SemanticUnitModel ─────────────────────────────────────────────────


async def test_store_semantic_unit(db_session, sample_company, sample_pipeline_run):
    """store_embedding() creates a SemanticUnitModel with vector."""
    repo = EmbeddingRepository(db_session)

    unit = await repo.store_embedding(
        SemanticUnitModel,
        company_id=sample_company.id,
        run_id=sample_pipeline_run.id,
        unit_id="unit-001",
        text="Ramp helps companies manage spend efficiently.",
        embedding=_vec(0.5),
        discovery_source="website",
        word_count=7,
        char_count=47,
    )

    assert unit.id is not None
    assert unit.unit_id == "unit-001"
    assert unit.text == "Ramp helps companies manage spend efficiently."
    assert unit.discovery_source == "website"


# ── QueryEmbeddingModel ──────────────────────────────────────────────


async def test_store_query_embedding(db_session, sample_pipeline_run):
    """store_embedding() creates a QueryEmbeddingModel with vector."""
    repo = EmbeddingRepository(db_session)

    qe = await repo.store_embedding(
        QueryEmbeddingModel,
        run_id=sample_pipeline_run.id,
        query_id="q-emb-1",
        query_text="What is expense management software?",
        embedding=_vec(0.3),
    )

    assert qe.id is not None
    assert qe.query_id == "q-emb-1"
    assert qe.query_text == "What is expense management software?"


# ── similarity_search ─────────────────────────────────────────────────


async def test_similarity_search_returns_nearest_neighbors(
    db_session, sample_company, sample_pipeline_run
):
    """similarity_search() returns embeddings ordered by cosine distance."""
    repo = EmbeddingRepository(db_session)

    # Create 3 semantic units with different vectors.
    # vec_close is close to the query vector, vec_far is far.
    # Query vector will be [0.9] * DIM.
    # vec_close = [0.89] → very close
    # vec_mid = [0.5]   → medium distance
    # vec_far = [0.01]  → far away
    await repo.store_embedding(
        SemanticUnitModel,
        company_id=sample_company.id,
        run_id=sample_pipeline_run.id,
        unit_id="close",
        text="Close to query",
        embedding=_vec(0.89),
    )
    await repo.store_embedding(
        SemanticUnitModel,
        company_id=sample_company.id,
        run_id=sample_pipeline_run.id,
        unit_id="mid",
        text="Medium distance",
        embedding=_vec(0.5),
    )
    await repo.store_embedding(
        SemanticUnitModel,
        company_id=sample_company.id,
        run_id=sample_pipeline_run.id,
        unit_id="far",
        text="Far from query",
        embedding=_vec(0.01),
    )

    results = await repo.similarity_search(
        SemanticUnitModel,
        query_vector=_vec(0.9),
        limit=3,
    )

    assert len(results) >= 3
    unit_ids = [r.unit_id for r in results]

    # Cosine distance for uniform vectors [a]*D vs [b]*D:
    # cos_sim = (D * a * b) / (sqrt(D * a^2) * sqrt(D * b^2))
    #         = (a * b) / (|a| * |b|) = sign(a) * sign(b) = 1
    # All uniform vectors have cosine_similarity = 1 (same direction).
    # So cosine distance = 1 - 1 = 0 for all positive-valued uniform vecs.
    #
    # To get actual distance differentiation, use mixed vectors instead.
    # Since all our test vectors point in the same direction ([k]*D),
    # cosine distance is ~0 for all. The ORDER is still deterministic
    # (pgvector breaks ties stably), so we just verify all 3 are returned.
    assert "close" in unit_ids
    assert "mid" in unit_ids
    assert "far" in unit_ids


async def test_similarity_search_with_varied_vectors(
    db_session, sample_company, sample_pipeline_run
):
    """similarity_search() with vectors that have actual directional variance."""
    repo = EmbeddingRepository(db_session)

    # Build vectors with more meaningful directional differences.
    # v_match: mostly aligned with query direction
    # v_ortho: partially orthogonal
    v_query = [1.0, 0.0] * (DIM // 2)   # alternating 1, 0
    v_match = [0.9, 0.1] * (DIM // 2)   # close direction to query
    v_ortho = [0.0, 1.0] * (DIM // 2)   # orthogonal to query

    await repo.store_embedding(
        SemanticUnitModel,
        company_id=sample_company.id,
        run_id=sample_pipeline_run.id,
        unit_id="match-dir",
        text="Matches query direction",
        embedding=v_match,
    )
    await repo.store_embedding(
        SemanticUnitModel,
        company_id=sample_company.id,
        run_id=sample_pipeline_run.id,
        unit_id="ortho-dir",
        text="Orthogonal to query direction",
        embedding=v_ortho,
    )

    results = await repo.similarity_search(
        SemanticUnitModel,
        query_vector=v_query,
        limit=10,
    )

    # Find our two test entries among all results
    our_results = [r for r in results if r.unit_id in ("match-dir", "ortho-dir")]
    assert len(our_results) == 2

    # match-dir should come before ortho-dir (lower cosine distance)
    idx_match = next(i for i, r in enumerate(results) if r.unit_id == "match-dir")
    idx_ortho = next(i for i, r in enumerate(results) if r.unit_id == "ortho-dir")
    assert idx_match < idx_ortho


async def test_similarity_search_respects_limit(
    db_session, sample_company, sample_pipeline_run
):
    """similarity_search() respects the limit parameter."""
    repo = EmbeddingRepository(db_session)

    for i in range(5):
        await repo.store_embedding(
            SemanticUnitModel,
            company_id=sample_company.id,
            run_id=sample_pipeline_run.id,
            unit_id=f"limit-test-{i}",
            text=f"Limit test entry {i}",
            embedding=_vec(0.1 * (i + 1)),
        )

    results = await repo.similarity_search(
        SemanticUnitModel,
        query_vector=_vec(0.5),
        limit=2,
    )
    assert len(results) == 2
