"""Tests for v1.3 persistence hooks — persist_v13_planner_output and persist_v13_brief_approval.

Pattern matches existing tests/content_engine/test_persistence.py — mock AsyncSession.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.content_engine.persistence import (
    persist_v13_brief_approval,
    persist_v13_planner_output,
)


def _make_session_factory(run_model=None):
    """Build a mock async session_factory returning a session context manager."""
    session = AsyncMock()

    if run_model is not None:
        session.get = AsyncMock(return_value=run_model)
    else:
        session.get = AsyncMock(return_value=None)

    session.commit = AsyncMock()

    # session_factory() returns an async context manager
    factory = MagicMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    factory.return_value = ctx

    return factory, session


def _make_pipeline_run(config=None):
    """Build a mock PipelineRunModel."""
    run = MagicMock()
    run.config = config
    return run


# ═══════════════════════════════════════════════════════════════════════
# persist_v13_planner_output
# ═══════════════════════════════════════════════════════════════════════


class TestPersistV13PlannerOutput:
    """Tests for persist_v13_planner_output()."""

    @pytest.mark.asyncio
    async def test_noop_when_session_factory_is_none(self):
        """No-op when session_factory is None."""
        await persist_v13_planner_output(
            session_factory=None,
            run_id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            slug="test-co",
            planner_output={"selections": []},
            approval_decision="approve",
            approved_topic_ranks=[0, 1],
        )
        # Should not raise

    @pytest.mark.asyncio
    async def test_noop_when_run_id_is_none(self):
        """No-op when run_id is None."""
        factory, _ = _make_session_factory()
        await persist_v13_planner_output(
            session_factory=factory,
            run_id=None,
            company_id=uuid.uuid4(),
            slug="test-co",
            planner_output={},
            approval_decision="approve",
            approved_topic_ranks=[],
        )
        factory.assert_not_called()

    @pytest.mark.asyncio
    async def test_writes_config_v13_planner(self):
        """Writes to config['v13_planner'] JSONB."""
        run = _make_pipeline_run(config={})
        factory, session = _make_session_factory(run_model=run)

        with patch("core.content_engine.persistence.PipelineRunModel", create=True):
            await persist_v13_planner_output(
                session_factory=factory,
                run_id=uuid.uuid4(),
                company_id=uuid.uuid4(),
                slug="test-co",
                planner_output={"selections": [{"rank": 1}]},
                approval_decision="approve",
                approved_topic_ranks=[0],
            )

        assert run.config["v13_planner"]["selections"] == {"selections": [{"rank": 1}]}
        assert run.config["v13_planner"]["approval_decision"] == "approve"
        assert run.config["v13_planner"]["approved_topic_ranks"] == [0]
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_preserves_existing_config(self):
        """Existing config fields are preserved."""
        run = _make_pipeline_run(config={"existing_key": "value"})
        factory, _ = _make_session_factory(run_model=run)

        with patch("core.content_engine.persistence.PipelineRunModel", create=True):
            await persist_v13_planner_output(
                session_factory=factory,
                run_id=uuid.uuid4(),
                company_id=uuid.uuid4(),
                slug="test-co",
                planner_output={},
                approval_decision="approve",
                approved_topic_ranks=[],
            )

        assert run.config["existing_key"] == "value"
        assert "v13_planner" in run.config

    @pytest.mark.asyncio
    async def test_handles_none_config(self):
        """Works when run.config is None."""
        run = _make_pipeline_run(config=None)
        factory, _ = _make_session_factory(run_model=run)

        with patch("core.content_engine.persistence.PipelineRunModel", create=True):
            await persist_v13_planner_output(
                session_factory=factory,
                run_id=uuid.uuid4(),
                company_id=uuid.uuid4(),
                slug="test-co",
                planner_output={"test": True},
                approval_decision="modify",
                approved_topic_ranks=[0, 1, 2],
            )

        assert run.config["v13_planner"]["approval_decision"] == "modify"

    @pytest.mark.asyncio
    async def test_run_not_found_noop(self):
        """When PipelineRunModel not found, logs warning and returns."""
        factory, session = _make_session_factory(run_model=None)

        with patch("core.content_engine.persistence.PipelineRunModel", create=True):
            await persist_v13_planner_output(
                session_factory=factory,
                run_id=uuid.uuid4(),
                company_id=uuid.uuid4(),
                slug="test-co",
                planner_output={},
                approval_decision="approve",
                approved_topic_ranks=[],
            )

        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_db_error_caught_gracefully(self):
        """DB errors are caught and logged, never crash pipeline."""
        factory = MagicMock()
        factory.return_value.__aenter__ = AsyncMock(side_effect=RuntimeError("DB down"))
        factory.return_value.__aexit__ = AsyncMock()

        # Should not raise
        await persist_v13_planner_output(
            session_factory=factory,
            run_id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            slug="test-co",
            planner_output={},
            approval_decision="approve",
            approved_topic_ranks=[],
        )


# ═══════════════════════════════════════════════════════════════════════
# persist_v13_brief_approval
# ═══════════════════════════════════════════════════════════════════════


class TestPersistV13BriefApproval:
    """Tests for persist_v13_brief_approval()."""

    @pytest.mark.asyncio
    async def test_noop_when_session_factory_is_none(self):
        await persist_v13_brief_approval(
            session_factory=None,
            run_id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            slug="test-co",
            blueprints=[],
            approval_decisions=[],
        )

    @pytest.mark.asyncio
    async def test_noop_when_company_id_is_none(self):
        factory, _ = _make_session_factory()
        await persist_v13_brief_approval(
            session_factory=factory,
            run_id=uuid.uuid4(),
            company_id=None,
            slug="test-co",
            blueprints=[],
            approval_decisions=[],
        )
        factory.assert_not_called()

    @pytest.mark.asyncio
    async def test_writes_config_v13_briefs(self):
        """Writes to config['v13_briefs'] JSONB."""
        run = _make_pipeline_run(config={})
        factory, session = _make_session_factory(run_model=run)

        blueprints_data = [{"brief_id": "b-001", "title": "Test"}]
        decisions = [{"brief_id": "b-001", "decision": "approve"}]

        with patch("core.content_engine.persistence.PipelineRunModel", create=True):
            await persist_v13_brief_approval(
                session_factory=factory,
                run_id=uuid.uuid4(),
                company_id=uuid.uuid4(),
                slug="test-co",
                blueprints=blueprints_data,
                approval_decisions=decisions,
            )

        assert run.config["v13_briefs"]["blueprints"] == blueprints_data
        assert run.config["v13_briefs"]["approval_decisions"] == decisions
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_not_found_noop(self):
        factory, session = _make_session_factory(run_model=None)

        with patch("core.content_engine.persistence.PipelineRunModel", create=True):
            await persist_v13_brief_approval(
                session_factory=factory,
                run_id=uuid.uuid4(),
                company_id=uuid.uuid4(),
                slug="test-co",
                blueprints=[],
                approval_decisions=[],
            )

        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_db_error_caught_gracefully(self):
        factory = MagicMock()
        factory.return_value.__aenter__ = AsyncMock(side_effect=RuntimeError("DB down"))
        factory.return_value.__aexit__ = AsyncMock()

        await persist_v13_brief_approval(
            session_factory=factory,
            run_id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            slug="test-co",
            blueprints=[],
            approval_decisions=[],
        )

    @pytest.mark.asyncio
    async def test_writes_reject_decision_correctly(self):
        """Reject decisions are stored as-is in config['v13_briefs']['approval_decisions']."""
        run = _make_pipeline_run(config={})
        factory, session = _make_session_factory(run_model=run)

        blueprints_data = [
            {"brief_id": "b-001", "title": "Test"},
            {"brief_id": "b-002", "title": "Rejected Brief"},
        ]
        decisions = [
            {"brief_id": "b-001", "decision": "approve", "feedback": "", "feedback_attempts": 0},
            {"brief_id": "b-002", "decision": "reject", "feedback": "Not relevant", "feedback_attempts": 1},
        ]

        with patch("core.content_engine.persistence.PipelineRunModel", create=True):
            await persist_v13_brief_approval(
                session_factory=factory,
                run_id=uuid.uuid4(),
                company_id=uuid.uuid4(),
                slug="test-co",
                blueprints=blueprints_data,
                approval_decisions=decisions,
            )

        stored = run.config["v13_briefs"]["approval_decisions"]
        assert len(stored) == 2
        reject_entry = next(d for d in stored if d["brief_id"] == "b-002")
        assert reject_entry["decision"] == "reject"
        assert reject_entry["feedback"] == "Not relevant"
        assert reject_entry["feedback_attempts"] == 1
