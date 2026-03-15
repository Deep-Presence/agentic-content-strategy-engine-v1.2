"""Phase 1 infrastructure wiring tests for daily tracker DB readiness.

Covers:
    - PipelineType enum includes daily_tracker
    - PipelineTask Literal accepts daily_tracker
    - ORM models registered in Base.metadata.tables
    - Migration 0014 file exists with correct ALTER TYPE
"""
from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError


class TestPipelineTypeEnum:
    """daily_tracker must be a valid PipelineType enum value."""

    def test_daily_tracker_in_pipeline_type_enum(self) -> None:
        from core.db.enums import PipelineType

        pt = PipelineType("daily_tracker")
        assert pt == PipelineType.daily_tracker
        assert pt.value == "daily_tracker"


class TestPipelineTaskLiteral:
    """PipelineTask must accept 'daily_tracker' as a pipeline value."""

    def test_daily_tracker_in_pipeline_task_literal(self) -> None:
        from api.tasks.models import PipelineTask

        task = PipelineTask(task_id="test-123", pipeline="daily_tracker")
        assert task.pipeline == "daily_tracker"

    def test_invalid_pipeline_rejected(self) -> None:
        from api.tasks.models import PipelineTask

        with pytest.raises(ValidationError):
            PipelineTask(task_id="test-123", pipeline="nonexistent_pipeline")


class TestORMModelRegistry:
    """Daily tracker ORM models must be registered in Base.metadata."""

    def test_daily_tracker_models_in_metadata(self) -> None:
        import core.db.models  # noqa: F401 — trigger registration
        from core.db.base import Base

        table_names = set(Base.metadata.tables.keys())
        assert "tracked_prompts" in table_names
        assert "daily_runs" in table_names
        assert "daily_run_responses" in table_names


class TestMigration0014:
    """Migration 0014 must exist and add daily_tracker to pipeline_type_enum."""

    def test_migration_file_exists(self) -> None:
        migration_path = (
            Path(__file__).resolve().parents[2]
            / "core"
            / "db"
            / "migrations"
            / "versions"
            / "0014_daily_tracker_enum.py"
        )
        assert migration_path.exists(), f"Migration not found: {migration_path}"

    def test_migration_contains_daily_tracker_alter(self) -> None:
        migration_path = (
            Path(__file__).resolve().parents[2]
            / "core"
            / "db"
            / "migrations"
            / "versions"
            / "0014_daily_tracker_enum.py"
        )
        content = migration_path.read_text()
        assert "daily_tracker" in content
        assert "pipeline_type_enum" in content
        assert "ADD VALUE" in content
        assert 'down_revision: str = "0013"' in content
