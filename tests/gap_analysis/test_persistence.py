"""Unit tests for core.gap_analysis.persistence — DB persistence hooks.

Tests the 8 persist_sN functions plus helper functions (_safe_float,
_classify, _map_engine, _should_persist).

These are pure unit tests — no real DB needed. All DB interaction is
mocked via AsyncMock session factories and patched repositories.

The persist functions import ORM models and repositories lazily inside
their try blocks. We patch those at their source modules. We also patch
the module-level ``delete`` / ``select`` / ``func`` from sqlalchemy so
that the idempotent-delete statements don't try to introspect MagicMock
objects as real ORM tables.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.gap_analysis.persistence import (
    _classify,
    _hash_text,
    _map_engine,
    _safe_float,
    _should_persist,
    persist_s1,
    persist_s2,
    persist_s3,
    persist_s4,
    persist_s5,
    persist_s6,
    persist_s7,
    persist_s8,
)
from core.models.gap_analysis import (
    AnalysisResult,
    CitationExemplar,
    CitationRef,
    CentroidResult,
    ClusterContentSpec,
    EnrichedCitation,
    GapContentBrief,
    GeneratedQuery,
    PlatformResult,
    QueryGap,
    SemanticUnit,
    SpaResult,
    StructuralSignals,
)


# ── Shared fixtures ──────────────────────────────────────────────────────

RUN_ID = uuid.uuid4()
COMPANY_ID = uuid.uuid4()
SLUG = "test-co"
EMBEDDING_1536 = [0.01] * 1536


class _FakeSession:
    """Async context manager that yields itself and tracks calls."""

    def __init__(self) -> None:
        self.execute = AsyncMock()
        self.commit = AsyncMock()
        self.get = AsyncMock(return_value=None)

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


def _mock_delete(model_cls):
    """Replacement for sqlalchemy.delete() that returns a chainable mock."""
    m = MagicMock()
    m.where.return_value = m  # .where() returns itself for chaining
    return m


def _mock_select(*args):
    """Replacement for sqlalchemy.select() that returns a chainable mock."""
    m = MagicMock()
    m.select_from.return_value = m
    m.where.return_value = m
    return m


def _mock_func():
    """Replacement for sqlalchemy.func that returns a chainable mock."""
    m = MagicMock()
    return m


# ── Patch targets ────────────────────────────────────────────────────────
# ORM models and repos are lazily imported inside the persist functions.
# Patch at their source modules.

_EMBEDDING_REPO = "core.db.repositories.embedding_repo.EmbeddingRepository"
_SEMANTIC_UNIT_MODEL = "core.db.models.embeddings.SemanticUnitModel"
_QUERY_EMBEDDING_MODEL = "core.db.models.embeddings.QueryEmbeddingModel"
_PARAGRAPH_EMBEDDING_MODEL = "core.db.models.embeddings.ParagraphEmbeddingModel"

_GAP_REPO = "core.db.repositories.gap_analysis_repo.GapAnalysisRepository"
_RUN_QUERY_MODEL = "core.db.models.gap_analysis.RunQueryModel"
_RUN_CITATION_MODEL = "core.db.models.gap_analysis.RunCitationModel"
_QUERY_GAP_MODEL = "core.db.models.gap_analysis.QueryGapModel"
_QUERY_EXEMPLAR_MODEL = "core.db.models.gap_analysis.QueryExemplarModel"
_CLUSTER_SPEC_MODEL = "core.db.models.gap_analysis.ClusterSpecModel"
_SPA_RESULT_MODEL = "core.db.models.gap_analysis.SpaResultModel"
_CENTROID_RESULT_MODEL = "core.db.models.gap_analysis.CentroidResultModel"

_CACHE_REPO = "core.db.repositories.cache_repo.CacheRepository"

_PIPELINE_RUN_MODEL = "core.db.models.pipelines.PipelineRunModel"
_PIPELINE_STATUS = "core.db.enums.PipelineStatus"

# Module-level sqlalchemy imports that interact with ORM models
_DELETE = "core.gap_analysis.persistence.delete"
_SELECT = "core.gap_analysis.persistence.select"
_FUNC = "core.gap_analysis.persistence.func"


@pytest.fixture(autouse=True)
def _patch_sqlalchemy_dml():
    """Patch delete/select/func so mocked ORM models don't cause errors."""
    with patch(_DELETE, side_effect=_mock_delete), \
         patch(_SELECT, side_effect=_mock_select), \
         patch(_FUNC, _mock_func()):
        yield


# ── Helper tests ─────────────────────────────────────────────────────────


class TestSafeFloat:
    def test_none(self):
        assert _safe_float(None) == 0.0

    def test_normal_float(self):
        assert _safe_float(3.14) == 3.14

    def test_nan(self):
        assert _safe_float(float("nan")) == 0.0

    def test_inf(self):
        assert _safe_float(float("inf")) == 0.0

    def test_neg_inf(self):
        assert _safe_float(float("-inf")) == 0.0

    def test_int(self):
        assert _safe_float(42) == 42.0

    def test_string_number(self):
        assert _safe_float("2.5") == 2.5

    def test_non_numeric_string(self):
        assert _safe_float("not-a-number") == 0.0


class TestClassify:
    def test_exact_enum_value(self):
        from core.db.enums import GapClassification

        assert _classify("significant_gap") == GapClassification.significant_gap

    def test_legacy_large_gap(self):
        from core.db.enums import GapClassification

        assert _classify("large_gap") == GapClassification.significant_gap

    def test_legacy_moderate_gap(self):
        from core.db.enums import GapClassification

        assert _classify("moderate_gap") == GapClassification.gap_to_close

    def test_legacy_no_gap(self):
        from core.db.enums import GapClassification

        assert _classify("no_gap") == GapClassification.company_wins

    def test_unknown_falls_to_no_data(self):
        from core.db.enums import GapClassification

        assert _classify("totally_unknown") == GapClassification.no_data


class TestMapEngine:
    def test_valid_engines(self):
        from core.db.enums import SearchEngine

        assert _map_engine("openai") == SearchEngine.openai
        assert _map_engine("Claude") == SearchEngine.claude
        assert _map_engine("GEMINI") == SearchEngine.gemini
        assert _map_engine("perplexity") == SearchEngine.perplexity

    def test_unknown_engine(self):
        assert _map_engine("bing") is None


class TestShouldPersist:
    def test_all_present(self):
        factory = MagicMock()
        assert _should_persist(factory, RUN_ID, COMPANY_ID) is True

    def test_no_factory(self):
        assert _should_persist(None, RUN_ID, COMPANY_ID) is False

    def test_no_run_id(self):
        assert _should_persist(MagicMock(), None, COMPANY_ID) is False

    def test_no_company_id(self):
        assert _should_persist(MagicMock(), RUN_ID, None) is False

    def test_all_none(self):
        assert _should_persist(None, None, None) is False


class TestHashText:
    def test_deterministic(self):
        assert _hash_text("hello") == _hash_text("hello")

    def test_different_inputs(self):
        assert _hash_text("hello") != _hash_text("world")


# ── persist_s1 tests ─────────────────────────────────────────────────────
# persist_s1 is now a no-op (VectorStoreClient writes during S1 execution).
# Tests verify it doesn't crash and doesn't touch the DB.


@pytest.mark.asyncio
async def test_persist_s1_noop_with_units():
    """persist_s1 is a no-op — should not touch DB, just log."""
    factory = _make_session_factory()
    units = [
        SemanticUnit(
            unit_id="u1", url="https://example.com", title="Page",
            text="Some content", embedding=EMBEDDING_1536,
            char_count=100, word_count=20, discovery_source="website",
        ),
    ]
    await persist_s1(factory, RUN_ID, COMPANY_ID, SLUG, units)
    # Should NOT have opened a session
    factory.assert_not_called()


@pytest.mark.asyncio
async def test_persist_s1_noop_without_session():
    """persist_s1 no-op works even with None session_factory."""
    units = [SemanticUnit(unit_id="u1", text="x", embedding=EMBEDDING_1536)]
    await persist_s1(None, RUN_ID, COMPANY_ID, SLUG, units)


@pytest.mark.asyncio
async def test_persist_s1_noop_without_run_id():
    factory = _make_session_factory()
    units = [SemanticUnit(unit_id="u1", text="x", embedding=EMBEDDING_1536)]
    await persist_s1(factory, None, COMPANY_ID, SLUG, units)
    factory.assert_not_called()


@pytest.mark.asyncio
async def test_persist_s1_noop_empty_units():
    factory = _make_session_factory()
    await persist_s1(factory, RUN_ID, COMPANY_ID, SLUG, [])
    factory.assert_not_called()


# ── persist_s2 tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_persist_s2_stores_queries():
    factory = _make_session_factory()
    queries = [
        GeneratedQuery(
            query_id="q1", cluster_id="c1", cluster_name="Topic A",
            query_text="What is X?", buyer_stage="awareness",
        ),
    ]

    with patch(_GAP_REPO) as MockRepo, \
         patch(_RUN_QUERY_MODEL):
        mock_repo = AsyncMock()
        MockRepo.return_value = mock_repo

        await persist_s2(factory, RUN_ID, COMPANY_ID, SLUG, queries)

        mock_repo.bulk_insert_run_queries.assert_awaited_once()
        factory._session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_persist_s2_skips_without_session():
    await persist_s2(None, RUN_ID, COMPANY_ID, SLUG, [])


@pytest.mark.asyncio
async def test_persist_s2_handles_exception():
    factory = _make_session_factory()
    queries = [GeneratedQuery(query_id="q1", cluster_id="c1", cluster_name="A", query_text="Q?")]

    with patch(_GAP_REPO, side_effect=RuntimeError("db fail")), \
         patch(_RUN_QUERY_MODEL):
        await persist_s2(factory, RUN_ID, COMPANY_ID, SLUG, queries)


# ── persist_s3 tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_persist_s3_stores_citations():
    factory = _make_session_factory()
    # Mock execute to return a result with scalar_one() == 0 for the count query.
    # But execute is used for both the delete and the select. We use side_effect
    # to return different things: first call = delete (returns anything),
    # second call = select count (returns scalar_one=0).
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    factory._session.execute = AsyncMock(
        side_effect=[MagicMock(), count_result]
    )

    platform_results = [
        PlatformResult(
            engine="openai", query_id="q1", query_text="What?",
            citations=[CitationRef(url="https://example.com/a", title="A", source="example.com")],
        ),
    ]
    queries = [
        GeneratedQuery(query_id="q1", cluster_id="c1", cluster_name="Topic", query_text="What?"),
    ]

    with patch(_GAP_REPO) as MockRepo, \
         patch(_RUN_CITATION_MODEL), \
         patch(_RUN_QUERY_MODEL):
        mock_repo = AsyncMock()
        MockRepo.return_value = mock_repo

        await persist_s3(factory, RUN_ID, COMPANY_ID, SLUG, platform_results, queries)

        mock_repo.bulk_insert_run_queries.assert_awaited_once()
        mock_repo.bulk_insert_run_citations.assert_awaited_once()
        factory._session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_persist_s3_skips_query_backfill_when_exists():
    factory = _make_session_factory()
    # scalar_one returns 5 → queries exist → no backfill
    count_result = MagicMock()
    count_result.scalar_one.return_value = 5
    factory._session.execute = AsyncMock(
        side_effect=[MagicMock(), count_result]
    )

    platform_results = [
        PlatformResult(
            engine="claude", query_id="q1",
            citations=[CitationRef(url="https://example.com/b")],
        ),
    ]
    queries = [GeneratedQuery(query_id="q1", cluster_id="c1", cluster_name="T", query_text="Q?")]

    with patch(_GAP_REPO) as MockRepo, \
         patch(_RUN_CITATION_MODEL), \
         patch(_RUN_QUERY_MODEL):
        mock_repo = AsyncMock()
        MockRepo.return_value = mock_repo

        await persist_s3(factory, RUN_ID, COMPANY_ID, SLUG, platform_results, queries)

        mock_repo.bulk_insert_run_queries.assert_not_awaited()
        mock_repo.bulk_insert_run_citations.assert_awaited_once()


@pytest.mark.asyncio
async def test_persist_s3_skips_unknown_engine():
    factory = _make_session_factory()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 1
    factory._session.execute = AsyncMock(
        side_effect=[MagicMock(), count_result]
    )

    platform_results = [
        PlatformResult(
            engine="bing",  # unknown engine
            query_id="q1",
            citations=[CitationRef(url="https://example.com/c")],
        ),
    ]

    with patch(_GAP_REPO) as MockRepo, \
         patch(_RUN_CITATION_MODEL), \
         patch(_RUN_QUERY_MODEL):
        mock_repo = AsyncMock()
        MockRepo.return_value = mock_repo

        await persist_s3(factory, RUN_ID, COMPANY_ID, SLUG, platform_results, [])

        mock_repo.bulk_insert_run_citations.assert_not_awaited()


@pytest.mark.asyncio
async def test_persist_s3_skips_without_session():
    await persist_s3(None, RUN_ID, COMPANY_ID, SLUG, [], [])


@pytest.mark.asyncio
async def test_persist_s3_handles_exception():
    factory = _make_session_factory()

    with patch(_GAP_REPO, side_effect=RuntimeError("s3 fail")), \
         patch(_RUN_CITATION_MODEL), \
         patch(_RUN_QUERY_MODEL):
        await persist_s3(factory, RUN_ID, COMPANY_ID, SLUG, [], [])


# ── persist_s4 tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_persist_s4_stores_enrichments_and_signals():
    factory = _make_session_factory()
    enriched = [
        EnrichedCitation(
            url="https://example.com/page",
            domain="example.com",
            title="Page Title",
            paragraphs=["para 1", "para 2"],
            structural_signals=StructuralSignals(
                word_count=500, paragraph_count=10, header_count=3,
                has_headers=True, has_lists=True,
            ),
        ),
    ]

    with patch(_CACHE_REPO) as MockRepo:
        mock_repo = AsyncMock()
        MockRepo.return_value = mock_repo

        await persist_s4(factory, RUN_ID, COMPANY_ID, SLUG, enriched)

        mock_repo.bulk_upsert_url_enrichments.assert_awaited_once()
        mock_repo.bulk_insert_structural_signals.assert_awaited_once()
        factory._session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_persist_s4_skips_signals_when_none():
    factory = _make_session_factory()
    enriched = [
        EnrichedCitation(
            url="https://example.com/no-signals",
            structural_signals=None,
        ),
    ]

    with patch(_CACHE_REPO) as MockRepo:
        mock_repo = AsyncMock()
        MockRepo.return_value = mock_repo

        await persist_s4(factory, RUN_ID, COMPANY_ID, SLUG, enriched)

        mock_repo.bulk_upsert_url_enrichments.assert_awaited_once()
        mock_repo.bulk_insert_structural_signals.assert_not_awaited()


@pytest.mark.asyncio
async def test_persist_s4_deterministic_enrichment_id():
    """Regression: enrichment_id must be deterministic (uuid5 from url_hash).

    Previously used uuid4(), causing FK mismatch on reruns: upsert on url_hash
    kept the original id, but signal rows referenced the new random id.
    """
    import uuid as _uuid

    factory = _make_session_factory()
    enriched = [
        EnrichedCitation(
            url="https://example.com/page",
            domain="example.com",
            paragraphs=["para 1"],
            structural_signals=StructuralSignals(
                word_count=100, paragraph_count=1, header_count=0,
                has_headers=False, has_lists=False,
            ),
        ),
    ]

    captured_enrichment_rows: list = []
    captured_signal_rows: list = []

    with patch(_CACHE_REPO) as MockRepo:
        mock_repo = AsyncMock()
        MockRepo.return_value = mock_repo
        mock_repo.bulk_upsert_url_enrichments.side_effect = (
            lambda rows: captured_enrichment_rows.extend(rows)
        )
        mock_repo.bulk_insert_structural_signals.side_effect = (
            lambda rows: captured_signal_rows.extend(rows)
        )

        # Run twice to simulate rerun
        await persist_s4(factory, RUN_ID, COMPANY_ID, SLUG, enriched)
        await persist_s4(factory, RUN_ID, COMPANY_ID, SLUG, enriched)

    # Both runs must produce the SAME enrichment_id for the same URL
    assert len(captured_enrichment_rows) == 2
    assert captured_enrichment_rows[0]["id"] == captured_enrichment_rows[1]["id"]

    # Signal rows must reference the same id as enrichment rows
    assert len(captured_signal_rows) == 2
    assert captured_signal_rows[0]["url_enrichment_id"] == captured_enrichment_rows[0]["id"]
    assert captured_signal_rows[1]["url_enrichment_id"] == captured_enrichment_rows[1]["id"]

    # Must be uuid5 (deterministic), not uuid4 (random)
    eid = captured_enrichment_rows[0]["id"]
    assert eid.version == 5


@pytest.mark.asyncio
async def test_persist_s4_skips_without_session():
    await persist_s4(None, RUN_ID, COMPANY_ID, SLUG, [])


@pytest.mark.asyncio
async def test_persist_s4_handles_exception():
    factory = _make_session_factory()

    with patch(_CACHE_REPO, side_effect=RuntimeError("s4 fail")):
        await persist_s4(factory, RUN_ID, COMPANY_ID, SLUG, [])


# ── persist_s5 tests ─────────────────────────────────────────────────────
# persist_s5 writes query embeddings to DB (citation embeddings handled by VectorStoreClient).


@pytest.mark.asyncio
async def test_persist_s5_stores_query_embeddings():
    factory = _make_session_factory()
    queries = [
        GeneratedQuery(
            query_id="q1", cluster_id="c1", cluster_name="Topic",
            query_text="What is X?", embedding=EMBEDDING_1536,
        ),
    ]
    enriched: list = []

    with patch(_EMBEDDING_REPO) as MockRepo, \
         patch(_QUERY_EMBEDDING_MODEL):
        mock_repo = AsyncMock()
        MockRepo.return_value = mock_repo

        await persist_s5(factory, RUN_ID, COMPANY_ID, SLUG, queries, enriched)

        mock_repo.bulk_store_embeddings.assert_awaited_once()
        factory._session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_persist_s5_skips_queries_without_embedding():
    factory = _make_session_factory()
    queries = [
        GeneratedQuery(query_id="q1", cluster_id="c1", cluster_name="T", query_text="Q?", embedding=None),
        GeneratedQuery(query_id="q2", cluster_id="c1", cluster_name="T", query_text="Q2?", embedding=[0.1] * 100),
    ]

    with patch(_EMBEDDING_REPO) as MockRepo, \
         patch(_QUERY_EMBEDDING_MODEL):
        mock_repo = AsyncMock()
        MockRepo.return_value = mock_repo

        await persist_s5(factory, RUN_ID, COMPANY_ID, SLUG, queries, [])

        mock_repo.bulk_store_embeddings.assert_not_awaited()
        factory._session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_persist_s5_skips_without_session():
    await persist_s5(None, RUN_ID, COMPANY_ID, SLUG, [], [])


@pytest.mark.asyncio
async def test_persist_s5_handles_exception():
    factory = _make_session_factory()
    queries = [GeneratedQuery(query_id="q1", cluster_id="c1", cluster_name="T", query_text="Q?", embedding=EMBEDDING_1536)]

    with patch(_EMBEDDING_REPO, side_effect=RuntimeError("s5 boom")), \
         patch(_QUERY_EMBEDDING_MODEL):
        await persist_s5(factory, RUN_ID, COMPANY_ID, SLUG, queries, [])


# ── persist_s6 tests ─────────────────────────────────────────────────────


def _make_analysis_result() -> AnalysisResult:
    """Build a minimal but realistic AnalysisResult for testing."""
    exemplar = CitationExemplar(
        similarity=0.85, url="https://cited.com/article",
        domain="cited.com", snippet="Top result",
        authority_type="industry_publication",
    )
    gap = QueryGap(
        query_id="q1", cluster_name="Topic A", query_text="What is X?",
        best_company_similarity=0.4, avg_citation_similarity=0.8,
        gap=0.4, interpretation="significant_gap",
        top_cited_exemplars=[exemplar],
        content_brief=GapContentBrief(target_word_count=(800, 1200)),
    )
    spec = ClusterContentSpec(
        cluster_id="c1", cluster_name="Topic A", query_count=5,
        word_count_range=[800, 1500], total_citations_analyzed=20,
        faq_rate=0.3, table_rate=0.1,
    )
    spa = SpaResult(
        cluster_name="Topic A", t_stat=2.5, p_value=0.01,
        mean_citation_similarity=0.8, mean_company_similarity=0.4,
        effect="strong",
    )
    centroid = CentroidResult(cluster_name="Topic A", distance=0.35)
    return AnalysisResult(
        gaps=[gap], cluster_specs=[spec], spa_results=[spa],
        centroids=[centroid],
        decision_metrics={"total_queries": 50, "total_citations": 200, "avg_gap": 0.35},
    )


@pytest.mark.asyncio
async def test_persist_s6_stores_all_tables():
    factory = _make_session_factory()
    analysis = _make_analysis_result()

    with patch(_GAP_REPO) as MockRepo, \
         patch(_QUERY_GAP_MODEL), \
         patch(_QUERY_EXEMPLAR_MODEL), \
         patch(_CLUSTER_SPEC_MODEL), \
         patch(_SPA_RESULT_MODEL), \
         patch(_CENTROID_RESULT_MODEL):
        mock_repo = AsyncMock()
        MockRepo.return_value = mock_repo

        await persist_s6(factory, RUN_ID, COMPANY_ID, SLUG, analysis)

        mock_repo.bulk_insert_query_gaps.assert_awaited_once()
        mock_repo.bulk_insert_query_exemplars.assert_awaited_once()
        mock_repo.bulk_insert_cluster_specs.assert_awaited_once()
        mock_repo.bulk_insert_spa_results.assert_awaited_once()
        mock_repo.bulk_insert_centroid_results.assert_awaited_once()
        factory._session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_persist_s6_gap_row_shape():
    """Verify the dict passed to bulk_insert_query_gaps has correct fields."""
    factory = _make_session_factory()
    analysis = _make_analysis_result()

    with patch(_GAP_REPO) as MockRepo, \
         patch(_QUERY_GAP_MODEL), \
         patch(_QUERY_EXEMPLAR_MODEL), \
         patch(_CLUSTER_SPEC_MODEL), \
         patch(_SPA_RESULT_MODEL), \
         patch(_CENTROID_RESULT_MODEL):
        mock_repo = AsyncMock()
        MockRepo.return_value = mock_repo

        await persist_s6(factory, RUN_ID, COMPANY_ID, SLUG, analysis)

        gap_rows = mock_repo.bulk_insert_query_gaps.call_args[0][0]
        assert len(gap_rows) == 1
        row = gap_rows[0]
        assert row["query_id"] == "q1"
        assert row["query_text"] == "What is X?"
        assert row["best_company_similarity"] == 0.4
        assert row["gap"] == 0.4
        assert row["content_brief"] is not None
        assert row["run_id"] == RUN_ID


@pytest.mark.asyncio
async def test_persist_s6_empty_analysis():
    factory = _make_session_factory()
    analysis = AnalysisResult()  # All empty lists

    with patch(_GAP_REPO) as MockRepo, \
         patch(_QUERY_GAP_MODEL), \
         patch(_QUERY_EXEMPLAR_MODEL), \
         patch(_CLUSTER_SPEC_MODEL), \
         patch(_SPA_RESULT_MODEL), \
         patch(_CENTROID_RESULT_MODEL):
        mock_repo = AsyncMock()
        MockRepo.return_value = mock_repo

        await persist_s6(factory, RUN_ID, COMPANY_ID, SLUG, analysis)

        mock_repo.bulk_insert_query_gaps.assert_not_awaited()
        mock_repo.bulk_insert_query_exemplars.assert_not_awaited()
        mock_repo.bulk_insert_cluster_specs.assert_not_awaited()
        mock_repo.bulk_insert_spa_results.assert_not_awaited()
        mock_repo.bulk_insert_centroid_results.assert_not_awaited()
        factory._session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_persist_s6_skips_without_session():
    await persist_s6(None, RUN_ID, COMPANY_ID, SLUG, _make_analysis_result())


@pytest.mark.asyncio
async def test_persist_s6_handles_exception():
    factory = _make_session_factory()

    with patch(_GAP_REPO, side_effect=RuntimeError("s6 fail")), \
         patch(_QUERY_GAP_MODEL), \
         patch(_QUERY_EXEMPLAR_MODEL), \
         patch(_CLUSTER_SPEC_MODEL), \
         patch(_SPA_RESULT_MODEL), \
         patch(_CENTROID_RESULT_MODEL):
        await persist_s6(factory, RUN_ID, COMPANY_ID, SLUG, _make_analysis_result())


@pytest.mark.asyncio
async def test_persist_s6_no_run_id_on_exemplar_model():
    """Regression: QueryExemplarModel has no run_id column.

    The idempotent-delete loop must NOT reference QueryExemplarModel.run_id.
    Exemplars are cascade-deleted via their FK to query_gaps (ondelete=CASCADE).
    This was the root cause of persist_s6 silently failing and leaving the DB
    empty while JSON artifacts existed — see persist_s6 bug 2026-03-23.
    """
    from core.db.models.gap_analysis import QueryExemplarModel as RealExemplarModel

    # Verify the real model class truly lacks run_id
    assert not hasattr(RealExemplarModel, "run_id"), (
        "QueryExemplarModel should NOT have a run_id column — "
        "it links to query_gaps via query_gap_id FK"
    )

    # Now run persist_s6 with real ORM models (not mocked) for the delete loop,
    # but mock the session.execute and repo to avoid needing a real DB.
    factory = _make_session_factory()
    analysis = _make_analysis_result()

    with patch(_GAP_REPO) as MockRepo:
        mock_repo = AsyncMock()
        MockRepo.return_value = mock_repo

        # Should NOT raise AttributeError on QueryExemplarModel.run_id
        await persist_s6(factory, RUN_ID, COMPANY_ID, SLUG, analysis)

        # Verify data was actually inserted (not short-circuited by error)
        mock_repo.bulk_insert_query_gaps.assert_awaited_once()


# ── persist_s7 tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_persist_s7_is_noop():
    """s7 is a no-op — visualizations stay on filesystem."""
    factory = _make_session_factory()
    await persist_s7(factory, RUN_ID, COMPANY_ID, SLUG, ["/path/to/viz.html"])
    factory.assert_not_called()


@pytest.mark.asyncio
async def test_persist_s7_accepts_none_session():
    await persist_s7(None, None, None, SLUG, None)


# ── persist_s8 tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_persist_s8_updates_pipeline_run():
    factory = _make_session_factory()
    mock_run = MagicMock()
    mock_run.summary = None
    mock_run.status = None
    mock_run.completed_at = None
    mock_run.stages_executed = None
    factory._session.get = AsyncMock(return_value=mock_run)

    analysis = _make_analysis_result()
    report = MagicMock()

    with patch(_PIPELINE_RUN_MODEL), \
         patch(_PIPELINE_STATUS) as MockStatus:
        MockStatus.completed = "completed"

        await persist_s8(factory, RUN_ID, COMPANY_ID, SLUG, report, analysis)

        factory._session.get.assert_awaited_once()
        assert mock_run.summary is not None
        assert mock_run.summary["total_queries"] == 50
        assert mock_run.summary["avg_gap"] == 0.35
        assert mock_run.status == "completed"
        assert len(mock_run.stages_executed) == 8
        factory._session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_persist_s8_run_not_found():
    factory = _make_session_factory()
    factory._session.get = AsyncMock(return_value=None)

    with patch(_PIPELINE_RUN_MODEL), \
         patch(_PIPELINE_STATUS):
        await persist_s8(factory, RUN_ID, COMPANY_ID, SLUG, MagicMock(), MagicMock())

        factory._session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_persist_s8_skips_without_session():
    await persist_s8(None, RUN_ID, COMPANY_ID, SLUG, MagicMock(), MagicMock())


@pytest.mark.asyncio
async def test_persist_s8_handles_exception():
    factory = _make_session_factory()

    with patch(_PIPELINE_RUN_MODEL, side_effect=RuntimeError("s8 fail")), \
         patch(_PIPELINE_STATUS):
        await persist_s8(factory, RUN_ID, COMPANY_ID, SLUG, MagicMock(), MagicMock())


@pytest.mark.asyncio
async def test_persist_s8_spa_score_in_summary():
    """Verify SPA t_stat is included in the summary when spa_results exist."""
    factory = _make_session_factory()
    mock_run = MagicMock()
    factory._session.get = AsyncMock(return_value=mock_run)

    analysis = _make_analysis_result()
    report = MagicMock()

    with patch(_PIPELINE_RUN_MODEL), \
         patch(_PIPELINE_STATUS) as MockStatus:
        MockStatus.completed = "completed"

        await persist_s8(factory, RUN_ID, COMPANY_ID, SLUG, report, analysis)

        assert "spa_score" in mock_run.summary
        assert mock_run.summary["spa_score"] == 2.5
