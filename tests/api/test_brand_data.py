"""Tests for Brand Brain + Run History endpoints (Phase 4).

TDD: These tests are written BEFORE the service/router implementation.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.tasks.models import PipelineTask, TaskStatus
from api.tasks.store import TaskStore


# ── Helpers ──────────────────────────────────────────────────────────


def _write_artifact(path: Path, content: str) -> None:
    """Write content to a file, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_gap_result(
    spa_t_stat: float = 14.975,
    total_queries: int = 72,
    total_citations: int = 1422,
    mean_citation_sim: float = 0.65,
    mean_company_sim: float = 0.45,
) -> dict:
    """Build a realistic gap_analysis task result dict."""
    return {
        "report_json": {
            "spa_results": [
                {
                    "cluster_name": "all",
                    "t_stat": spa_t_stat,
                    "p_value": 0.001,
                    "mean_citation_similarity": mean_citation_sim,
                    "mean_company_similarity": mean_company_sim,
                    "effect": "citation_advantage",
                }
            ],
            "decision_metrics": {
                "total_queries": total_queries,
                "total_citations": total_citations,
                "avg_gap": 0.12,
            },
        }
    }


def _create_task(
    task_store: TaskStore,
    pipeline: str,
    slug: str,
    *,
    status: TaskStatus = TaskStatus.COMPLETED,
    current_step: str | None = None,
    result: dict | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> PipelineTask:
    """Create a task with specific attributes for testing."""
    task = task_store.create_task(pipeline, slug)
    updates: dict = {"status": status}
    if current_step is not None:
        updates["current_step"] = current_step
    if result is not None:
        updates["result"] = result
    if created_at is not None:
        updates["created_at"] = created_at
    if updated_at is not None:
        updates["updated_at"] = updated_at
    task_store.update_task(task.task_id, **updates)
    # Patch timestamps AFTER update_task (which auto-sets updated_at to now)
    stored = task_store._tasks[task.task_id]
    if created_at is not None:
        stored.created_at = created_at
    if updated_at is not None:
        stored.updated_at = updated_at
    # Release slug lock so we can create more tasks for the same slug
    task_store.release_slug_lock(f"{pipeline}:{slug}")
    return task_store.get_task(task.task_id)


# ── Autouse fixture: clear service caches ────────────────────────────


@pytest.fixture(autouse=True)
def _clear_caches():
    """Clear module-level caches between tests."""
    try:
        from api.services import brand_data_service

        brand_data_service._CACHE.clear()
    except (ImportError, AttributeError):
        pass
    yield
    try:
        from api.services import brand_data_service

        brand_data_service._CACHE.clear()
    except (ImportError, AttributeError):
        pass


# ══════════════════════════════════════════════════════════════════════
#  ENDPOINT 1: GET /api/v1/companies/{slug}/research/artifacts
# ══════════════════════════════════════════════════════════════════════


class TestResearchArtifacts:
    """Tests for the research artifacts endpoint."""

    URL = "/api/v1/companies/{slug}/research/artifacts"

    # ── Slug validation ──

    def test_invalid_slug_returns_403(self, client: TestClient):
        # Invalid slug doesn't match authenticated user's company → 403
        resp = client.get(self.URL.format(slug="INVALID!!"))
        assert resp.status_code == 403

    def test_path_traversal_slug_returns_error(self, client: TestClient):
        resp = client.get(self.URL.format(slug="../etc"))
        # Tenant check or FastAPI parser rejects before handler
        assert resp.status_code in (400, 403, 404, 422)

    # ── Empty state ──

    def test_no_artifacts_returns_all_none(
        self, client: TestClient, artifacts_root: Path
    ):
        resp = client.get(self.URL.format(slug="test-co"))
        assert resp.status_code == 200
        data = resp.json()
        assert data["company_context"]["status"] == "none"
        assert data["company_context"]["content"] is None
        assert data["personas"] == []
        assert data["style_guide"]["status"] == "none"

    def test_missing_company_context_dir(
        self, client: TestClient, artifacts_root: Path
    ):
        # Only personas dir exists
        (artifacts_root / "personas").mkdir(parents=True)
        resp = client.get(self.URL.format(slug="test-co"))
        assert resp.status_code == 200
        assert resp.json()["company_context"]["status"] == "none"

    # ── Company context ──

    def test_approved_company_context(
        self, client: TestClient, artifacts_root: Path
    ):
        _write_artifact(
            artifacts_root / "company_context" / "test-co.md",
            "# Webflow Company Context",
        )
        resp = client.get(self.URL.format(slug="test-co"))
        assert resp.status_code == 200
        data = resp.json()["company_context"]
        assert data["status"] == "approved"
        assert data["content"] == "# Webflow Company Context"
        assert data["updated_at"] is not None

    def test_draft_company_context(
        self, client: TestClient, artifacts_root: Path
    ):
        _write_artifact(
            artifacts_root / "company_context" / "test-co.draft.md",
            "# Draft Context",
        )
        resp = client.get(self.URL.format(slug="test-co"))
        data = resp.json()["company_context"]
        assert data["status"] == "draft"
        assert data["content"] == "# Draft Context"

    def test_both_draft_and_approved_returns_approved(
        self, client: TestClient, artifacts_root: Path
    ):
        _write_artifact(
            artifacts_root / "company_context" / "test-co.md",
            "# Approved",
        )
        _write_artifact(
            artifacts_root / "company_context" / "test-co.draft.md",
            "# Draft",
        )
        resp = client.get(self.URL.format(slug="test-co"))
        data = resp.json()["company_context"]
        assert data["status"] == "approved"
        assert data["content"] == "# Approved"

    # ── Personas ──

    def test_single_persona_icp(
        self, client: TestClient, artifacts_root: Path
    ):
        _write_artifact(
            artifacts_root / "personas" / "test-co__persona-icp.md",
            "# ICP Persona",
        )
        resp = client.get(self.URL.format(slug="test-co"))
        personas = resp.json()["personas"]
        assert len(personas) == 1
        p = personas[0]
        assert p["id"] == "persona-icp"
        assert p["type"] == "icp"
        assert p["content"] == "# ICP Persona"
        assert p["status"] == "approved"

    def test_multiple_personas(
        self, client: TestClient, artifacts_root: Path
    ):
        _write_artifact(
            artifacts_root / "personas" / "test-co__persona-icp.md",
            "# ICP",
        )
        _write_artifact(
            artifacts_root / "personas" / "test-co__persona-secondary-sales.md",
            "# Secondary Sales",
        )
        resp = client.get(self.URL.format(slug="test-co"))
        personas = resp.json()["personas"]
        assert len(personas) == 2
        ids = {p["id"] for p in personas}
        assert "persona-icp" in ids
        assert "persona-secondary-sales" in ids

    def test_persona_draft_detection(
        self, client: TestClient, artifacts_root: Path
    ):
        _write_artifact(
            artifacts_root / "personas" / "test-co__persona-icp.draft.md",
            "# Draft Persona",
        )
        resp = client.get(self.URL.format(slug="test-co"))
        personas = resp.json()["personas"]
        assert len(personas) == 1
        assert personas[0]["status"] == "draft"
        assert personas[0]["content"] == "# Draft Persona"

    def test_persona_approved_over_draft(
        self, client: TestClient, artifacts_root: Path
    ):
        """When both .md and .draft.md exist, approved wins."""
        _write_artifact(
            artifacts_root / "personas" / "test-co__persona-icp.md",
            "# Approved Persona",
        )
        _write_artifact(
            artifacts_root / "personas" / "test-co__persona-icp.draft.md",
            "# Draft Persona",
        )
        resp = client.get(self.URL.format(slug="test-co"))
        personas = resp.json()["personas"]
        icp = [p for p in personas if p["id"] == "persona-icp"]
        assert len(icp) == 1
        assert icp[0]["status"] == "approved"
        assert icp[0]["content"] == "# Approved Persona"

    def test_persona_type_secondary(
        self, client: TestClient, artifacts_root: Path
    ):
        _write_artifact(
            artifacts_root / "personas" / "test-co__persona-secondary-finance.md",
            "# Finance Persona",
        )
        resp = client.get(self.URL.format(slug="test-co"))
        personas = resp.json()["personas"]
        assert personas[0]["type"] == "secondary"

    def test_persona_name_derived_from_id(
        self, client: TestClient, artifacts_root: Path
    ):
        _write_artifact(
            artifacts_root / "personas" / "test-co__persona-icp.md",
            "# ICP",
        )
        resp = client.get(self.URL.format(slug="test-co"))
        # Name should be title-cased from id with hyphens as spaces
        name = resp.json()["personas"][0]["name"]
        assert name == "Persona Icp"

    def test_personas_from_other_slug_excluded(
        self, client: TestClient, artifacts_root: Path
    ):
        """Personas for a different slug should not appear."""
        _write_artifact(
            artifacts_root / "personas" / "ramp__persona-icp.md",
            "# Ramp ICP",
        )
        resp = client.get(self.URL.format(slug="test-co"))
        assert resp.json()["personas"] == []

    def test_non_persona_files_excluded(
        self, client: TestClient, artifacts_root: Path
    ):
        """Files like {slug}__notes.md should not appear as personas (Codex CX-4)."""
        _write_artifact(
            artifacts_root / "personas" / "test-co__notes.md",
            "# Internal notes",
        )
        _write_artifact(
            artifacts_root / "personas" / "test-co__persona-icp.md",
            "# ICP",
        )
        resp = client.get(self.URL.format(slug="test-co"))
        personas = resp.json()["personas"]
        assert len(personas) == 1
        assert personas[0]["id"] == "persona-icp"

    # ── Style guide ──

    def test_approved_style_guide(
        self, client: TestClient, artifacts_root: Path
    ):
        _write_artifact(
            artifacts_root / "style_guides" / "test-co.md",
            "# Style Guide",
        )
        resp = client.get(self.URL.format(slug="test-co"))
        data = resp.json()["style_guide"]
        assert data["status"] == "approved"
        assert data["content"] == "# Style Guide"

    def test_draft_style_guide(
        self, client: TestClient, artifacts_root: Path
    ):
        _write_artifact(
            artifacts_root / "style_guides" / "test-co.draft.md",
            "# Draft Guide",
        )
        resp = client.get(self.URL.format(slug="test-co"))
        data = resp.json()["style_guide"]
        assert data["status"] == "draft"
        assert data["content"] == "# Draft Guide"

    # ── Updated at ──

    def test_updated_at_from_file_mtime(
        self, client: TestClient, artifacts_root: Path
    ):
        path = artifacts_root / "company_context" / "test-co.md"
        _write_artifact(path, "# Context")
        resp = client.get(self.URL.format(slug="test-co"))
        updated_at = resp.json()["company_context"]["updated_at"]
        assert updated_at is not None
        # Should be a parseable ISO datetime
        dt = datetime.fromisoformat(updated_at)
        assert dt.year >= 2026

    # ── Full integration ──

    def test_full_company_all_artifacts(
        self, client: TestClient, artifacts_root: Path
    ):
        _write_artifact(
            artifacts_root / "company_context" / "test-co.md",
            "# Company",
        )
        _write_artifact(
            artifacts_root / "personas" / "test-co__persona-icp.md",
            "# ICP",
        )
        _write_artifact(
            artifacts_root / "personas" / "test-co__persona-secondary-sales.md",
            "# Sales",
        )
        _write_artifact(
            artifacts_root / "style_guides" / "test-co.md",
            "# Style",
        )
        resp = client.get(self.URL.format(slug="test-co"))
        assert resp.status_code == 200
        data = resp.json()
        assert data["company_context"]["status"] == "approved"
        assert len(data["personas"]) == 2
        assert data["style_guide"]["status"] == "approved"


# ══════════════════════════════════════════════════════════════════════
#  ENDPOINT 2: GET /api/v1/companies/{slug}/runs
# ══════════════════════════════════════════════════════════════════════


class TestRunHistory:
    """Tests for the run history endpoint."""

    URL = "/api/v1/companies/{slug}/runs"

    # ── Slug validation ──

    def test_invalid_slug_returns_403(self, client: TestClient):
        # Invalid slug doesn't match authenticated user's company → 403
        resp = client.get(self.URL.format(slug="INVALID!!"))
        assert resp.status_code == 403

    # ── Empty state ──

    def test_no_tasks_returns_empty(
        self, client: TestClient, task_store: TaskStore
    ):
        resp = client.get(self.URL.format(slug="test-co"))
        assert resp.status_code == 200
        data = resp.json()
        assert data["runs"] == []
        assert data["total"] == 0

    def test_no_matching_slug_returns_empty(
        self, client: TestClient, task_store: TaskStore
    ):
        _create_task(task_store, "gap_analysis", "ramp")
        resp = client.get(self.URL.format(slug="test-co"))
        assert resp.json()["total"] == 0

    # ── Basic listing ──

    def test_completed_gap_run_with_metrics(
        self, client: TestClient, task_store: TaskStore
    ):
        result = _make_gap_result(spa_t_stat=14.975, total_queries=72, total_citations=1422)
        _create_task(
            task_store,
            "gap_analysis",
            "test-co",
            status=TaskStatus.COMPLETED,
            result=result,
        )
        resp = client.get(self.URL.format(slug="test-co"))
        data = resp.json()
        assert data["total"] == 1
        run = data["runs"][0]
        assert run["pipeline"] == "gap_analysis"
        assert run["status"] == "completed"
        assert run["spa_score"] == pytest.approx(14.975)
        assert run["queries"] == 72
        assert run["citations"] == 1422
        assert run["steps_completed"] == 8
        assert run["total_steps"] == 8

    def test_failed_run_zero_metrics(
        self, client: TestClient, task_store: TaskStore
    ):
        _create_task(
            task_store,
            "gap_analysis",
            "test-co",
            status=TaskStatus.FAILED,
            current_step="s4_enrich_citations",
        )
        resp = client.get(self.URL.format(slug="test-co"))
        run = resp.json()["runs"][0]
        assert run["status"] == "failed"
        assert run["spa_score"] == 0.0
        assert run["queries"] == 0

    def test_running_task_with_partial_steps(
        self, client: TestClient, task_store: TaskStore
    ):
        _create_task(
            task_store,
            "gap_analysis",
            "test-co",
            status=TaskStatus.RUNNING,
            current_step="s4_enrich_citations",
        )
        resp = client.get(self.URL.format(slug="test-co"))
        run = resp.json()["runs"][0]
        assert run["status"] == "running"
        assert run["steps_completed"] == 4

    def test_multiple_runs_sorted_by_started_desc(
        self, client: TestClient, task_store: TaskStore
    ):
        _create_task(
            task_store,
            "gap_analysis",
            "test-co",
            status=TaskStatus.COMPLETED,
            result=_make_gap_result(spa_t_stat=10.0),
            created_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
            updated_at=datetime(2026, 1, 15, 4, tzinfo=timezone.utc),
        )
        _create_task(
            task_store,
            "gap_analysis",
            "test-co",
            status=TaskStatus.COMPLETED,
            result=_make_gap_result(spa_t_stat=15.0),
            created_at=datetime(2026, 2, 18, tzinfo=timezone.utc),
            updated_at=datetime(2026, 2, 18, 4, tzinfo=timezone.utc),
        )
        resp = client.get(self.URL.format(slug="test-co"))
        runs = resp.json()["runs"]
        assert len(runs) == 2
        # Most recent first
        assert runs[0]["spa_score"] == pytest.approx(15.0)
        assert runs[1]["spa_score"] == pytest.approx(10.0)

    # ── Duration ──

    def test_duration_hours_and_minutes(
        self, client: TestClient, task_store: TaskStore
    ):
        _create_task(
            task_store,
            "gap_analysis",
            "test-co",
            status=TaskStatus.COMPLETED,
            result=_make_gap_result(),
            created_at=datetime(2026, 2, 18, 20, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 2, 18, 23, 46, tzinfo=timezone.utc),
        )
        resp = client.get(self.URL.format(slug="test-co"))
        assert resp.json()["runs"][0]["duration"] == "3h 46m"

    def test_duration_minutes_only(
        self, client: TestClient, task_store: TaskStore
    ):
        _create_task(
            task_store,
            "gap_analysis",
            "test-co",
            status=TaskStatus.COMPLETED,
            result=_make_gap_result(),
            created_at=datetime(2026, 2, 18, 20, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 2, 18, 20, 23, tzinfo=timezone.utc),
        )
        resp = client.get(self.URL.format(slug="test-co"))
        assert resp.json()["runs"][0]["duration"] == "23m"

    def test_duration_running_empty_string(
        self, client: TestClient, task_store: TaskStore
    ):
        _create_task(
            task_store,
            "gap_analysis",
            "test-co",
            status=TaskStatus.RUNNING,
            current_step="s3_search_platforms",
        )
        resp = client.get(self.URL.format(slug="test-co"))
        run = resp.json()["runs"][0]
        # Running tasks have no meaningful duration yet
        assert run["status"] == "running"

    # ── Steps completed inference ──

    def test_gap_completed_8_of_8(
        self, client: TestClient, task_store: TaskStore
    ):
        _create_task(
            task_store,
            "gap_analysis",
            "test-co",
            status=TaskStatus.COMPLETED,
            result=_make_gap_result(),
        )
        resp = client.get(self.URL.format(slug="test-co"))
        run = resp.json()["runs"][0]
        assert run["steps_completed"] == 8
        assert run["total_steps"] == 8

    def test_gap_running_at_s4(
        self, client: TestClient, task_store: TaskStore
    ):
        _create_task(
            task_store,
            "gap_analysis",
            "test-co",
            status=TaskStatus.RUNNING,
            current_step="s4_enrich_citations",
        )
        resp = client.get(self.URL.format(slug="test-co"))
        run = resp.json()["runs"][0]
        assert run["steps_completed"] == 4
        assert run["total_steps"] == 8

    def test_content_completed_4_of_4(
        self, client: TestClient, task_store: TaskStore
    ):
        _create_task(
            task_store,
            "content",
            "test-co",
            status=TaskStatus.COMPLETED,
            result={"total_briefs": 3},
        )
        resp = client.get(self.URL.format(slug="test-co"))
        run = resp.json()["runs"][0]
        assert run["steps_completed"] == 4
        assert run["total_steps"] == 4

    # ── Metrics extraction ──

    def test_spa_score_from_report_json(
        self, client: TestClient, task_store: TaskStore
    ):
        result = _make_gap_result(spa_t_stat=11.234)
        _create_task(
            task_store, "gap_analysis", "test-co",
            status=TaskStatus.COMPLETED, result=result,
        )
        resp = client.get(self.URL.format(slug="test-co"))
        assert resp.json()["runs"][0]["spa_score"] == pytest.approx(11.234)

    def test_nan_spa_score_returns_zero(
        self, client: TestClient, task_store: TaskStore
    ):
        result = _make_gap_result(spa_t_stat=float("nan"))
        _create_task(
            task_store, "gap_analysis", "test-co",
            status=TaskStatus.COMPLETED, result=result,
        )
        resp = client.get(self.URL.format(slug="test-co"))
        assert resp.json()["runs"][0]["spa_score"] == 0.0

    def test_missing_result_returns_zero_metrics(
        self, client: TestClient, task_store: TaskStore
    ):
        _create_task(
            task_store, "gap_analysis", "test-co",
            status=TaskStatus.COMPLETED, result=None,
        )
        resp = client.get(self.URL.format(slug="test-co"))
        run = resp.json()["runs"][0]
        assert run["spa_score"] == 0.0
        assert run["queries"] == 0
        assert run["citations"] == 0

    # ── Filters ──

    def test_filter_by_pipeline(
        self, client: TestClient, task_store: TaskStore
    ):
        _create_task(task_store, "gap_analysis", "test-co",
                      status=TaskStatus.COMPLETED, result=_make_gap_result())
        _create_task(task_store, "research", "test-co",
                      status=TaskStatus.COMPLETED, result={"stage": "complete"})
        resp = client.get(
            self.URL.format(slug="test-co"), params={"pipeline": "gap_analysis"}
        )
        data = resp.json()
        assert data["total"] == 1
        assert data["runs"][0]["pipeline"] == "gap_analysis"

    def test_filter_by_status(
        self, client: TestClient, task_store: TaskStore
    ):
        _create_task(task_store, "gap_analysis", "test-co",
                      status=TaskStatus.COMPLETED, result=_make_gap_result())
        _create_task(task_store, "gap_analysis", "test-co",
                      status=TaskStatus.FAILED)
        resp = client.get(
            self.URL.format(slug="test-co"), params={"status": "completed"}
        )
        data = resp.json()
        assert data["total"] == 1
        assert data["runs"][0]["status"] == "completed"

    def test_filter_pipeline_and_status(
        self, client: TestClient, task_store: TaskStore
    ):
        _create_task(task_store, "gap_analysis", "test-co",
                      status=TaskStatus.COMPLETED, result=_make_gap_result())
        _create_task(task_store, "research", "test-co",
                      status=TaskStatus.COMPLETED, result={"stage": "complete"})
        _create_task(task_store, "gap_analysis", "test-co",
                      status=TaskStatus.FAILED)
        resp = client.get(
            self.URL.format(slug="test-co"),
            params={"pipeline": "gap_analysis", "status": "completed"},
        )
        data = resp.json()
        assert data["total"] == 1

    # ── Mapped-status filters (Codex CX-1) ──

    def test_filter_running_includes_pending_approval(
        self, client: TestClient, task_store: TaskStore
    ):
        """pending_approval maps to 'running' so ?status=running should include it."""
        _create_task(task_store, "research", "test-co",
                      status=TaskStatus.PENDING_APPROVAL)
        _create_task(task_store, "gap_analysis", "test-co",
                      status=TaskStatus.RUNNING)
        resp = client.get(
            self.URL.format(slug="test-co"), params={"status": "running"},
        )
        data = resp.json()
        assert data["total"] == 2
        assert all(r["status"] == "running" for r in data["runs"])

    def test_filter_failed_includes_cancelled(
        self, client: TestClient, task_store: TaskStore
    ):
        """cancelled maps to 'failed' so ?status=failed should include it."""
        _create_task(task_store, "gap_analysis", "test-co",
                      status=TaskStatus.CANCELLED)
        _create_task(task_store, "gap_analysis", "test-co",
                      status=TaskStatus.FAILED)
        resp = client.get(
            self.URL.format(slug="test-co"), params={"status": "failed"},
        )
        data = resp.json()
        assert data["total"] == 2
        assert all(r["status"] == "failed" for r in data["runs"])

    # ── Company name ──

    def test_company_name_from_slug(
        self, client: TestClient, task_store: TaskStore
    ):
        _create_task(
            task_store, "gap_analysis", "test-co",
            status=TaskStatus.COMPLETED, result=_make_gap_result(),
        )
        resp = client.get(self.URL.format(slug="test-co"))
        assert resp.json()["runs"][0]["company"] == "Test Co"

    def test_compound_slug_company_name(
        self, client: TestClient, task_store: TaskStore
    ):
        """Compound slugs with hyphens derive title-cased company name.

        Note: this test reuses the test-co slug (matching the test tenant)
        and verifies the name derivation for its slug format.
        """
        _create_task(
            task_store, "gap_analysis", "test-co",
            status=TaskStatus.COMPLETED, result=_make_gap_result(),
        )
        resp = client.get(self.URL.format(slug="test-co"))
        assert resp.json()["runs"][0]["company"] == "Test Co"

    # ── Started field ──

    def test_started_is_iso_string(
        self, client: TestClient, task_store: TaskStore
    ):
        _create_task(
            task_store, "gap_analysis", "test-co",
            status=TaskStatus.COMPLETED, result=_make_gap_result(),
            created_at=datetime(2026, 2, 18, 20, 0, tzinfo=timezone.utc),
        )
        resp = client.get(self.URL.format(slug="test-co"))
        started = resp.json()["runs"][0]["started"]
        dt = datetime.fromisoformat(started)
        assert dt.year == 2026
        assert dt.month == 2


# ══════════════════════════════════════════════════════════════════════
#  ENDPOINT 3: GET /api/v1/companies/{slug}/gap-analysis/trend
# ══════════════════════════════════════════════════════════════════════


class TestSPATrend:
    """Tests for the SPA score trend endpoint."""

    URL = "/api/v1/companies/{slug}/gap-analysis/trend"

    # ── Slug validation ──

    def test_invalid_slug_returns_403(self, client: TestClient):
        # Invalid slug doesn't match authenticated user's company → 403
        resp = client.get(self.URL.format(slug="INVALID!!"))
        assert resp.status_code == 403

    # ── Empty state ──

    def test_no_runs_returns_empty_trend(
        self, client: TestClient, task_store: TaskStore
    ):
        resp = client.get(self.URL.format(slug="test-co"))
        assert resp.status_code == 200
        assert resp.json()["trend"] == []

    def test_no_gap_runs_returns_empty(
        self, client: TestClient, task_store: TaskStore
    ):
        _create_task(task_store, "research", "test-co",
                      status=TaskStatus.COMPLETED, result={"stage": "complete"})
        resp = client.get(self.URL.format(slug="test-co"))
        assert resp.json()["trend"] == []

    def test_incomplete_gap_runs_excluded(
        self, client: TestClient, task_store: TaskStore
    ):
        _create_task(task_store, "gap_analysis", "test-co",
                      status=TaskStatus.FAILED)
        resp = client.get(self.URL.format(slug="test-co"))
        assert resp.json()["trend"] == []

    # ── Single run ──

    def test_single_completed_run(
        self, client: TestClient, task_store: TaskStore
    ):
        result = _make_gap_result(
            spa_t_stat=14.975, total_queries=72, total_citations=1422,
            mean_citation_sim=0.65, mean_company_sim=0.45,
        )
        _create_task(
            task_store, "gap_analysis", "test-co",
            status=TaskStatus.COMPLETED, result=result,
            created_at=datetime(2026, 2, 18, tzinfo=timezone.utc),
        )
        resp = client.get(self.URL.format(slug="test-co"))
        trend = resp.json()["trend"]
        assert len(trend) == 1
        point = trend[0]
        assert point["spa_score"] == pytest.approx(14.975)
        assert point["total_queries"] == 72
        assert point["total_citations"] == 1422
        assert point["citation_advantage"] == pytest.approx(0.2)
        assert point["company_advantage"] == pytest.approx(-0.2)

    # ── Multiple runs ──

    def test_multiple_runs_sorted_by_timestamp_asc(
        self, client: TestClient, task_store: TaskStore
    ):
        _create_task(
            task_store, "gap_analysis", "test-co",
            status=TaskStatus.COMPLETED, result=_make_gap_result(spa_t_stat=12.0),
            created_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
            updated_at=datetime(2026, 1, 15, 4, tzinfo=timezone.utc),
        )
        _create_task(
            task_store, "gap_analysis", "test-co",
            status=TaskStatus.COMPLETED, result=_make_gap_result(spa_t_stat=15.0),
            created_at=datetime(2026, 2, 18, tzinfo=timezone.utc),
            updated_at=datetime(2026, 2, 18, 4, tzinfo=timezone.utc),
        )
        resp = client.get(self.URL.format(slug="test-co"))
        trend = resp.json()["trend"]
        assert len(trend) == 2
        # Oldest first (ascending for chart x-axis)
        assert trend[0]["spa_score"] == pytest.approx(12.0)
        assert trend[1]["spa_score"] == pytest.approx(15.0)

    def test_run_label_short_date_format(
        self, client: TestClient, task_store: TaskStore
    ):
        _create_task(
            task_store, "gap_analysis", "test-co",
            status=TaskStatus.COMPLETED, result=_make_gap_result(),
            created_at=datetime(2026, 2, 18, tzinfo=timezone.utc),
        )
        resp = client.get(self.URL.format(slug="test-co"))
        point = resp.json()["trend"][0]
        assert point["run"] == "Feb 18"

    # ── Guard rails ──

    def test_nan_spa_score_returns_zero(
        self, client: TestClient, task_store: TaskStore
    ):
        result = _make_gap_result(spa_t_stat=float("nan"))
        _create_task(
            task_store, "gap_analysis", "test-co",
            status=TaskStatus.COMPLETED, result=result,
        )
        resp = client.get(self.URL.format(slug="test-co"))
        assert resp.json()["trend"][0]["spa_score"] == 0.0

    def test_missing_report_json_skips_run(
        self, client: TestClient, task_store: TaskStore
    ):
        _create_task(
            task_store, "gap_analysis", "test-co",
            status=TaskStatus.COMPLETED, result={"some_other": "data"},
        )
        resp = client.get(self.URL.format(slug="test-co"))
        # Run without report_json should be skipped
        assert resp.json()["trend"] == []

    def test_missing_spa_results_skips_run(
        self, client: TestClient, task_store: TaskStore
    ):
        _create_task(
            task_store, "gap_analysis", "test-co",
            status=TaskStatus.COMPLETED,
            result={"report_json": {"decision_metrics": {"total_queries": 10}}},
        )
        resp = client.get(self.URL.format(slug="test-co"))
        assert resp.json()["trend"] == []

    def test_other_slug_excluded(
        self, client: TestClient, task_store: TaskStore
    ):
        _create_task(
            task_store, "gap_analysis", "ramp",
            status=TaskStatus.COMPLETED, result=_make_gap_result(),
        )
        resp = client.get(self.URL.format(slug="test-co"))
        assert resp.json()["trend"] == []

    def test_run_id_populated(
        self, client: TestClient, task_store: TaskStore
    ):
        task = _create_task(
            task_store, "gap_analysis", "test-co",
            status=TaskStatus.COMPLETED, result=_make_gap_result(),
        )
        resp = client.get(self.URL.format(slug="test-co"))
        assert resp.json()["trend"][0]["run_id"] == task.task_id
