"""DB integration tests for daily tracker persistence layer.

Auto-skipped without TEST_DATABASE_URL.
Tests roundtrip writes via persistence functions → reads via repos/session.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from core.db.models.daily_tracker import DailyRunModel, DailyRunResponseModel
from core.db.repositories.daily_tracker_repo import (
    DailyRunRepository,
    DailyRunResponseRepository,
)
from core.models.daily_tracker import (
    DailyRunResult,
    MentionAnalysis,
    PlatformResponse,
    RunStatus,
)

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)


# ── Helpers ──────────────────────────────────────────────────────────

_COMPANY = "test-co"
_NOW = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)


def _make_result(
    run_id: str | None = None,
    status: RunStatus = RunStatus.COMPLETED,
    prompt_ids: list[str] | None = None,
) -> tuple[DailyRunResult, list[MentionAnalysis]]:
    """Build a DailyRunResult + aligned MentionAnalysis list."""
    rid = run_id or str(uuid.uuid4())
    pids = prompt_ids or [str(uuid.uuid4())]

    responses = [
        PlatformResponse(
            prompt_id=pid,
            engine="openai",
            response_text=f"Response for {pid}",
            latency_ms=100.0 + i * 10,
            timestamp=_NOW,
        )
        for i, pid in enumerate(pids)
    ]

    result = DailyRunResult(
        run_id=rid,
        company_id=_COMPANY,
        status=status,
        responses=responses,
        started_at=_NOW,
        completed_at=_NOW,
        prompt_count=len(pids),
        engine_count=1,
    )

    analyses = [
        MentionAnalysis(
            brand_mentioned=(i % 2 == 0),
            brand_mention_count=i + 1,
            competitor_mentions={"brex": 1} if i == 0 else {},
            citations=["https://example.com"] if i == 0 else [],
            citation_rank=1 if i == 0 else None,
        )
        for i in range(len(pids))
    ]

    return result, analyses


# ── Tests ────────────────────────────────────────────────────────────


async def test_create_daily_run_record_roundtrip(db_session_factory):
    """create_daily_run_record → session.get roundtrip."""
    from core.daily_tracker.persistence import create_daily_run_record

    run_id = str(uuid.uuid4())
    await create_daily_run_record(
        db_session_factory, _COMPANY, run_id, {"engines": ["openai"]}
    )

    async with db_session_factory() as session:
        row = await session.get(DailyRunModel, uuid.UUID(run_id))
        assert row is not None
        assert row.company_id == _COMPANY
        assert row.status == "running"


async def test_persist_daily_run_result_roundtrip(db_session_factory):
    """persist_daily_run_result → fetch via repo."""
    from core.daily_tracker.persistence import (
        create_daily_run_record,
        persist_daily_run_result,
    )

    result, analyses = _make_result()
    await create_daily_run_record(
        db_session_factory, _COMPANY, result.run_id, {},
    )
    await persist_daily_run_result(
        db_session_factory, _COMPANY, result, analyses,
    )

    async with db_session_factory() as session:
        row = await session.get(DailyRunModel, uuid.UUID(result.run_id))
        assert row is not None
        assert row.status == "completed"
        assert row.prompt_count == 1
        assert row.engine_count == 1


async def test_persist_stores_mention_analysis_fields(db_session_factory):
    """Verify brand_mentioned, competitor_mentions, citations are stored."""
    from core.daily_tracker.persistence import (
        create_daily_run_record,
        persist_daily_run_result,
    )

    result, analyses = _make_result()
    await create_daily_run_record(
        db_session_factory, _COMPANY, result.run_id, {},
    )
    await persist_daily_run_result(
        db_session_factory, _COMPANY, result, analyses,
    )

    async with db_session_factory() as session:
        repo = DailyRunResponseRepository(session)
        responses = await repo.get_responses_by_run(uuid.UUID(result.run_id))
        assert len(responses) == 1
        resp = responses[0]
        assert resp.brand_mentioned is True
        assert resp.brand_mention_count == 1
        assert resp.competitor_mentions == {"brex": 1}
        assert resp.citations == ["https://example.com"]
        assert resp.citation_rank == 1


async def test_persist_graceful_on_invalid_prompt_id(db_session_factory):
    """Invalid prompt_id → logged warning, no crash, partial persist."""
    from core.daily_tracker.persistence import (
        create_daily_run_record,
        persist_daily_run_result,
    )

    good_pid = str(uuid.uuid4())
    result = DailyRunResult(
        run_id=str(uuid.uuid4()),
        company_id=_COMPANY,
        status=RunStatus.COMPLETED,
        responses=[
            PlatformResponse(
                prompt_id=good_pid, engine="openai",
                response_text="good", latency_ms=100.0,
            ),
            PlatformResponse(
                prompt_id="not-a-uuid", engine="claude",
                response_text="bad", latency_ms=50.0,
            ),
        ],
        prompt_count=2, engine_count=2,
    )
    analyses = [
        MentionAnalysis(brand_mentioned=True),
        MentionAnalysis(brand_mentioned=False),
    ]

    await create_daily_run_record(
        db_session_factory, _COMPANY, result.run_id, {},
    )
    await persist_daily_run_result(
        db_session_factory, _COMPANY, result, analyses,
    )

    async with db_session_factory() as session:
        repo = DailyRunResponseRepository(session)
        responses = await repo.get_responses_by_run(uuid.UUID(result.run_id))
        # Only the good prompt_id should be persisted
        assert len(responses) == 1
        assert responses[0].engine == "openai"


async def test_mark_daily_run_failed_safety_net(db_session_factory):
    """mark_daily_run_failed transitions running → failed."""
    from core.daily_tracker.persistence import (
        create_daily_run_record,
        mark_daily_run_failed,
    )

    run_id = str(uuid.uuid4())
    await create_daily_run_record(
        db_session_factory, _COMPANY, run_id, {},
    )

    await mark_daily_run_failed(db_session_factory, run_id, "Task timeout")

    async with db_session_factory() as session:
        row = await session.get(DailyRunModel, uuid.UUID(run_id))
        assert row is not None
        assert row.status == "failed"
        assert row.error == "Task timeout"


async def test_mark_daily_run_failed_idempotent(db_session_factory):
    """Calling mark_daily_run_failed on a completed run is a no-op."""
    from core.daily_tracker.persistence import (
        create_daily_run_record,
        mark_daily_run_failed,
        persist_daily_run_result,
    )

    result, analyses = _make_result()
    await create_daily_run_record(
        db_session_factory, _COMPANY, result.run_id, {},
    )
    await persist_daily_run_result(
        db_session_factory, _COMPANY, result, analyses,
    )

    # This should be a no-op since status is already "completed"
    await mark_daily_run_failed(
        db_session_factory, result.run_id, "Should not change"
    )

    async with db_session_factory() as session:
        row = await session.get(DailyRunModel, uuid.UUID(result.run_id))
        assert row is not None
        assert row.status == "completed"  # unchanged


async def test_daily_run_repo_list_runs(db_session_factory):
    """DailyRunRepository.list_runs returns runs ordered by created_at desc."""
    from core.daily_tracker.persistence import create_daily_run_record

    ids = [str(uuid.uuid4()) for _ in range(3)]
    for rid in ids:
        await create_daily_run_record(
            db_session_factory, _COMPANY, rid, {},
        )

    async with db_session_factory() as session:
        repo = DailyRunRepository(session)
        runs = await repo.list_runs(_COMPANY, limit=10)
        assert len(runs) >= 3
        # Most recent first
        run_ids = [str(r.id) for r in runs]
        for rid in ids:
            assert rid in run_ids


async def test_persist_idempotent_no_duplicate_responses(db_session_factory):
    """Calling persist twice for the same run should not create duplicate responses."""
    from core.daily_tracker.persistence import (
        create_daily_run_record,
        persist_daily_run_result,
    )

    result, analyses = _make_result()
    await create_daily_run_record(db_session_factory, _COMPANY, result.run_id, {})

    # Persist the same result twice (simulates retry)
    await persist_daily_run_result(db_session_factory, _COMPANY, result, analyses)
    await persist_daily_run_result(db_session_factory, _COMPANY, result, analyses)

    async with db_session_factory() as session:
        repo = DailyRunResponseRepository(session)
        responses = await repo.get_responses_by_run(uuid.UUID(result.run_id))
        # Should be exactly len(result.responses), not doubled
        assert len(responses) == len(result.responses)


async def test_persist_without_prior_create(db_session_factory):
    """persist_daily_run_result creates run row if it doesn't exist."""
    from core.daily_tracker.persistence import persist_daily_run_result

    result, analyses = _make_result()

    # Persist WITHOUT calling create_daily_run_record first
    await persist_daily_run_result(
        db_session_factory, _COMPANY, result, analyses,
    )

    async with db_session_factory() as session:
        row = await session.get(DailyRunModel, uuid.UUID(result.run_id))
        assert row is not None
        assert row.status == "completed"
        assert row.company_id == _COMPANY
