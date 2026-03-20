"""Tests for the site audit API endpoints.

Covers:
  - POST /api/v1/site-audit/start      (TestStartSiteAudit, TestStartSiteAuditGuard)
  - GET  /api/v1/site-audit/status/{run_id}  (TestGetSiteAuditStatus)
  - GET  /api/v1/site-audit/companies/{slug}/audits  (TestListAudits)
  - GET  /api/v1/site-audit/companies/{slug}/audits/{id}  (TestGetAuditDetail)
  - GET  /api/v1/site-audit/companies/{slug}/audits/{id}/findings  (TestGetFindings)
  - GET  /api/v1/site-audit/companies/{slug}/audits/{id}/pages  (TestGetPageResults)
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.tasks.models import TaskStatus
from api.tasks.store import TaskStore


# ---------------------------------------------------------------------------
# Minimal valid payload
# ---------------------------------------------------------------------------

MINIMAL_PAYLOAD = {
    "company_name": "Test Co",
    "domain": "testco.com",
}


# ---------------------------------------------------------------------------
# Helpers to create fake audit artifacts on disk
# ---------------------------------------------------------------------------


def _write_audit_result(
    artifacts_root: Path,
    company_slug: str,
    audit_id: str,
    *,
    domain: str = "testco.com",
    status: str = "completed",
    overall_score: float = 72.5,
    grade: str = "C",
    pages_crawled: int = 15,
    total_findings: int = 8,
    page_results: list[dict[str, Any]] | None = None,
    top_findings: list[dict[str, Any]] | None = None,
) -> Path:
    """Write a minimal audit_result.json to disk and return the directory."""
    audit_dir = artifacts_root / "site_audit" / company_slug / audit_id
    audit_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "audit_id": audit_id,
        "domain": domain,
        "overall_score": overall_score,
        "grade": grade,
        "pages_crawled": pages_crawled,
        "pages_discovered": pages_crawled + 5,
        "duration_seconds": 12.3,
        "status": status,
        "total_findings": total_findings,
        "findings_by_severity": {"critical": 1, "high": 2, "medium": 3, "low": 2},
        "findings_by_dimension": {"crawlability": 3, "on_page_seo": 5},
        "avg_snippet_readiness": 62.0,
        "pages_with_schema": 4,
        "avg_question_heading_ratio": 0.15,
        "dimension_scores": [
            {
                "dimension": "crawlability",
                "score": 85.0,
                "weight": 0.2,
                "weighted_score": 17.0,
                "finding_count": 3,
                "critical_count": 0,
                "high_count": 1,
                "medium_count": 2,
                "low_count": 0,
                "info_count": 0,
            }
        ],
        "ai_bot_access": {
            "gptbot_allowed": True,
            "claudebot_allowed": True,
            "perplexitybot_allowed": True,
            "google_extended_allowed": False,
            "ccbot_allowed": True,
            "has_llms_txt": False,
            "robots_txt_exists": True,
        },
        "sitemap_health": {
            "has_sitemap": True,
            "sitemap_url_count": 42,
            "sitemap_urls": ["https://testco.com/sitemap.xml"],
            "sitemap_errors": [],
            "has_sitemap_index": False,
        },
        "page_results": page_results if page_results is not None else _default_page_results(),
        "top_findings": top_findings if top_findings is not None else _default_top_findings(),
        "started_at": "2026-02-28T10:00:00",
        "completed_at": "2026-02-28T10:00:12",
    }

    (audit_dir / "audit_result.json").write_text(
        json.dumps(result), encoding="utf-8"
    )
    return audit_dir


def _default_page_results() -> list[dict[str, Any]]:
    """Return a minimal list of page result dicts."""
    return [
        {
            "url": "https://testco.com/",
            "status_code": 200,
            "crawl_depth": 0,
            "title": "Home | Test Co",
            "word_count": 450,
            "reading_level": 8.2,
            "has_https": True,
            "is_noindex": False,
            "has_canonical": True,
            "canonical_url": "https://testco.com/",
            "schema": {
                "has_schema": True,
                "schema_types": ["Organization"],
                "validation_errors": [],
                "inferred_page_type": "homepage",
            },
            "aeo": {
                "snippet_readiness_score": 55.0,
                "question_heading_ratio": 0.1,
                "quick_answer_hook_count": 2,
                "self_contained_paragraph_ratio": 0.4,
                "avg_paragraph_word_count": 80.0,
                "content_patterns": {"faq_section": False},
            },
            "findings": [
                {
                    "finding_type": "thin_content",
                    "dimension": "on_page_seo",
                    "severity": "medium",
                    "message": "Page has fewer than 500 words",
                    "recommendation": "Expand the page content",
                    "url": "https://testco.com/",
                    "details": {},
                }
            ],
        },
        {
            "url": "https://testco.com/about",
            "status_code": 200,
            "crawl_depth": 1,
            "title": "About | Test Co",
            "word_count": 320,
            "reading_level": 7.5,
            "has_https": True,
            "is_noindex": False,
            "schema": {"has_schema": False, "schema_types": [], "validation_errors": [], "inferred_page_type": "unknown"},
            "aeo": {"snippet_readiness_score": 30.0, "question_heading_ratio": 0.0, "quick_answer_hook_count": 0, "self_contained_paragraph_ratio": 0.2, "avg_paragraph_word_count": 60.0, "content_patterns": {}},
            "findings": [
                {
                    "finding_type": "missing_meta_description",
                    "dimension": "on_page_seo",
                    "severity": "high",
                    "message": "No meta description found",
                    "recommendation": "Add a descriptive meta description",
                    "url": "https://testco.com/about",
                    "details": {},
                },
                {
                    "finding_type": "no_schema",
                    "dimension": "schema_markup",
                    "severity": "medium",
                    "message": "No structured data found",
                    "recommendation": "Add JSON-LD schema markup",
                    "url": "https://testco.com/about",
                    "details": {},
                },
            ],
        },
    ]


def _default_top_findings() -> list[dict[str, Any]]:
    return [
        {
            "finding_type": "missing_sitemap_in_robots",
            "dimension": "crawlability",
            "severity": "high",
            "message": "Sitemap not referenced in robots.txt",
            "recommendation": "Add Sitemap directive to robots.txt",
            "url": "",
            "details": {},
        }
    ]


# ---------------------------------------------------------------------------
# Mock pipeline
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_site_audit_pipeline():
    """Mock run_site_audit_task to return immediately without running the real pipeline.

    IMPORTANT: Patch at the point of use (router's local binding), not the
    source module.  The router does ``from api.tasks.runner import
    run_site_audit_task`` which creates a local name — patching
    ``api.tasks.runner.run_site_audit_task`` does NOT affect the router's
    reference.
    """
    with patch(
        "api.routers.site_audit.run_site_audit_task",
        new_callable=AsyncMock,
    ) as mock_fn:
        yield mock_fn


# ---------------------------------------------------------------------------
# Test: POST /start
# ---------------------------------------------------------------------------


class TestStartSiteAudit:
    def test_returns_run_id_and_202(
        self, client: TestClient, mock_site_audit_pipeline
    ) -> None:
        resp = client.post("/api/v1/site-audit/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 202
        data = resp.json()
        assert "run_id" in data
        assert data["pipeline"] == "site_audit"
        assert data["company_slug"] == "test-co"
        assert data["status"] == "running"
        assert data["already_exists"] is False

    def test_requires_auth_401(self, public_client: TestClient) -> None:
        resp = public_client.post("/api/v1/site-audit/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 401

    def test_requires_member_role_403_for_viewer(
        self, viewer_client: TestClient
    ) -> None:
        resp = viewer_client.post("/api/v1/site-audit/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 403

    def test_superuser_can_start(
        self, superuser_client: TestClient, mock_site_audit_pipeline
    ) -> None:
        resp = superuser_client.post("/api/v1/site-audit/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 202

    def test_tenant_isolation_403(
        self, client: TestClient, mock_site_audit_pipeline
    ) -> None:
        """Cannot start audit for a different company."""
        resp = client.post(
            "/api/v1/site-audit/start",
            json={"company_name": "Other Corp", "domain": "othercorp.com"},
        )
        assert resp.status_code == 403

    def test_slug_lock_conflict_409(
        self, client: TestClient, task_store: TaskStore
    ) -> None:
        """Returns 409 when an audit is already running for this slug."""
        task_store.create_task("site_audit", "test-co")
        resp = client.post("/api/v1/site-audit/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 409

    def test_validation_missing_company_name_422(
        self, client: TestClient
    ) -> None:
        resp = client.post(
            "/api/v1/site-audit/start",
            json={"domain": "testco.com"},
        )
        assert resp.status_code == 422

    def test_validation_missing_domain_422(
        self, client: TestClient
    ) -> None:
        resp = client.post(
            "/api/v1/site-audit/start",
            json={"company_name": "Test Co"},
        )
        assert resp.status_code == 422

    def test_optional_fields_accepted(
        self, client: TestClient, mock_site_audit_pipeline
    ) -> None:
        resp = client.post(
            "/api/v1/site-audit/start",
            json={
                "company_name": "Test Co",
                "domain": "testco.com",
                "max_pages": 100,
                "max_depth": 3,
                "check_core_web_vitals": False,
                "check_schema_validation": True,
                "check_ai_bot_access": False,
            },
        )
        assert resp.status_code == 202

    def test_max_pages_upper_bound_422(
        self, client: TestClient
    ) -> None:
        resp = client.post(
            "/api/v1/site-audit/start",
            json={**MINIMAL_PAYLOAD, "max_pages": 9999},
        )
        assert resp.status_code == 422

    def test_max_depth_upper_bound_422(
        self, client: TestClient
    ) -> None:
        resp = client.post(
            "/api/v1/site-audit/start",
            json={**MINIMAL_PAYLOAD, "max_depth": 99},
        )
        assert resp.status_code == 422

    def test_max_pages_lower_bound_422(
        self, client: TestClient
    ) -> None:
        resp = client.post(
            "/api/v1/site-audit/start",
            json={**MINIMAL_PAYLOAD, "max_pages": 0},
        )
        assert resp.status_code == 422


class TestStartSiteAuditGuard:
    """Guard: return 200 already_exists when a completed audit exists."""

    def test_returns_already_exists_when_completed_audit_present(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        audit_id = str(uuid.uuid4())
        _write_audit_result(artifacts_root, "test-co", audit_id)
        resp = client.post("/api/v1/site-audit/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 200
        data = resp.json()
        assert data["already_exists"] is True
        assert data["status"] == "already_exists"
        assert "force_rerun" in data["message"].lower()

    def test_force_rerun_bypasses_guard(
        self, client: TestClient, artifacts_root: Path, mock_site_audit_pipeline
    ) -> None:
        audit_id = str(uuid.uuid4())
        _write_audit_result(artifacts_root, "test-co", audit_id)
        resp = client.post(
            "/api/v1/site-audit/start",
            json={**MINIMAL_PAYLOAD, "force_rerun": True},
        )
        assert resp.status_code == 202
        assert resp.json()["already_exists"] is False

    def test_guard_ignores_running_status(
        self, client: TestClient, artifacts_root: Path, mock_site_audit_pipeline
    ) -> None:
        """Audits with status != 'completed' do NOT trigger the guard."""
        audit_id = str(uuid.uuid4())
        _write_audit_result(
            artifacts_root, "test-co", audit_id, status="running"
        )
        resp = client.post("/api/v1/site-audit/start", json=MINIMAL_PAYLOAD)
        # Guard should not fire since status != "completed"
        assert resp.status_code == 202

    def test_guard_uses_existing_task_run_id(
        self, client: TestClient, artifacts_root: Path, task_store: TaskStore
    ) -> None:
        audit_id = str(uuid.uuid4())
        _write_audit_result(artifacts_root, "test-co", audit_id)
        task = task_store.create_task("site_audit", "test-co")
        # Release the lock manually so we can update status
        task_store._slug_locks.pop("test-co", None)
        task_store.update_task(
            task.task_id,
            status=TaskStatus.COMPLETED,
            result={"domain": "testco.com", "audit_id": audit_id},
        )
        resp = client.post("/api/v1/site-audit/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 200
        assert resp.json()["run_id"] == task.task_id

    def test_guard_uses_existing_prefix_when_no_task_record(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        audit_id = str(uuid.uuid4())
        _write_audit_result(artifacts_root, "test-co", audit_id)
        resp = client.post("/api/v1/site-audit/start", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"].startswith("existing-")
        assert "test-co" in data["run_id"]

    def test_guard_domain_mismatch_does_not_fire(
        self, client: TestClient, artifacts_root: Path, mock_site_audit_pipeline
    ) -> None:
        """Guard fires only when domain matches."""
        audit_id = str(uuid.uuid4())
        _write_audit_result(
            artifacts_root, "test-co", audit_id, domain="other.com"
        )
        resp = client.post("/api/v1/site-audit/start", json=MINIMAL_PAYLOAD)
        # Domain doesn't match → should launch new run
        assert resp.status_code == 202


# ---------------------------------------------------------------------------
# Test: GET /status/{run_id}
# ---------------------------------------------------------------------------


class TestGetSiteAuditStatus:
    def test_status_after_start(
        self, client: TestClient, task_store: TaskStore
    ) -> None:
        task = task_store.create_task("site_audit", "test-co")
        resp = client.get(f"/api/v1/site-audit/status/{task.task_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["company_slug"] == "test-co"
        assert data["pipeline"] == "site_audit"

    def test_not_found_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/site-audit/status/nonexistent-id")
        assert resp.status_code == 404

    def test_requires_auth_401(
        self, public_client: TestClient, task_store: TaskStore
    ) -> None:
        task = task_store.create_task("site_audit", "test-co")
        resp = public_client.get(f"/api/v1/site-audit/status/{task.task_id}")
        assert resp.status_code == 401

    def test_cross_tenant_access_denied_403(
        self,
        client: TestClient,
        task_store: TaskStore,
    ) -> None:
        """Cannot poll status for a task belonging to a different company."""
        task = task_store.create_task("site_audit", "other-corp")
        resp = client.get(f"/api/v1/site-audit/status/{task.task_id}")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test: GET /companies/{slug}/audits
# ---------------------------------------------------------------------------


class TestListAudits:
    def test_returns_audit_list(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        for _ in range(3):
            audit_id = str(uuid.uuid4())
            _write_audit_result(artifacts_root, "test-co", audit_id)
        resp = client.get("/api/v1/site-audit/companies/test-co/audits")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 3
        # Each item should have required fields
        for item in data:
            assert "audit_id" in item
            assert "domain" in item
            assert "overall_score" in item
            assert "grade" in item

    def test_empty_company_returns_empty_list(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        resp = client.get("/api/v1/site-audit/companies/test-co/audits")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_requires_tenant_access_403(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        """Client authenticated as test-co cannot read audits for other-corp."""
        resp = client.get("/api/v1/site-audit/companies/other-corp/audits")
        assert resp.status_code == 403

    def test_requires_auth_401(
        self, public_client: TestClient
    ) -> None:
        resp = public_client.get("/api/v1/site-audit/companies/test-co/audits")
        assert resp.status_code == 401

    def test_limit_param_respected(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        for _ in range(5):
            _write_audit_result(artifacts_root, "test-co", str(uuid.uuid4()))
        resp = client.get(
            "/api/v1/site-audit/companies/test-co/audits?limit=2"
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2


# ---------------------------------------------------------------------------
# Test: GET /companies/{slug}/audits/{audit_id}
# ---------------------------------------------------------------------------


class TestGetAuditDetail:
    def test_returns_full_audit_detail(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        audit_id = str(uuid.uuid4())
        _write_audit_result(artifacts_root, "test-co", audit_id)
        resp = client.get(f"/api/v1/site-audit/companies/test-co/audits/{audit_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["audit_id"] == audit_id
        assert data["domain"] == "testco.com"
        assert data["overall_score"] == 72.5
        assert data["grade"] == "C"
        assert data["pages_crawled"] == 15
        assert data["total_findings"] == 8
        assert data["status"] == "completed"
        # Dimension scores
        assert isinstance(data["dimension_scores"], list)
        assert len(data["dimension_scores"]) == 1
        assert data["dimension_scores"][0]["dimension"] == "crawlability"

    def test_not_found_404(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        missing = "00000000-0000-0000-0000-000000000000"
        resp = client.get(
            f"/api/v1/site-audit/companies/test-co/audits/{missing}"
        )
        assert resp.status_code == 404

    def test_requires_tenant_403(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        audit_id = str(uuid.uuid4())
        _write_audit_result(artifacts_root, "other-corp", audit_id)
        resp = client.get(
            f"/api/v1/site-audit/companies/other-corp/audits/{audit_id}"
        )
        assert resp.status_code == 403

    def test_requires_auth_401(
        self, public_client: TestClient, artifacts_root: Path
    ) -> None:
        audit_id = str(uuid.uuid4())
        _write_audit_result(artifacts_root, "test-co", audit_id)
        resp = public_client.get(
            f"/api/v1/site-audit/companies/test-co/audits/{audit_id}"
        )
        assert resp.status_code == 401

    def test_ai_bot_access_present(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        audit_id = str(uuid.uuid4())
        _write_audit_result(artifacts_root, "test-co", audit_id)
        resp = client.get(f"/api/v1/site-audit/companies/test-co/audits/{audit_id}")
        data = resp.json()
        assert "ai_bot_access" in data
        assert "gptbot_allowed" in data["ai_bot_access"]
        assert data["ai_bot_access"]["google_extended_allowed"] is False


# ---------------------------------------------------------------------------
# Test: GET /companies/{slug}/audits/{id}/findings
# ---------------------------------------------------------------------------


class TestGetFindings:
    def test_returns_paginated_findings(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        audit_id = str(uuid.uuid4())
        _write_audit_result(artifacts_root, "test-co", audit_id)
        resp = client.get(
            f"/api/v1/site-audit/companies/test-co/audits/{audit_id}/findings"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "findings" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "total_pages" in data
        assert data["total"] > 0

    def test_filter_by_severity(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        audit_id = str(uuid.uuid4())
        _write_audit_result(artifacts_root, "test-co", audit_id)
        resp = client.get(
            f"/api/v1/site-audit/companies/test-co/audits/{audit_id}/findings"
            "?severity=high"
        )
        assert resp.status_code == 200
        data = resp.json()
        for finding in data["findings"]:
            assert finding["severity"] == "high"

    def test_filter_by_dimension(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        audit_id = str(uuid.uuid4())
        _write_audit_result(artifacts_root, "test-co", audit_id)
        resp = client.get(
            f"/api/v1/site-audit/companies/test-co/audits/{audit_id}/findings"
            "?dimension=on_page_seo"
        )
        assert resp.status_code == 200
        data = resp.json()
        for finding in data["findings"]:
            assert finding["dimension"] == "on_page_seo"

    def test_not_found_404(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        missing = "00000000-0000-0000-0000-000000000000"
        resp = client.get(
            f"/api/v1/site-audit/companies/test-co/audits/{missing}/findings"
        )
        assert resp.status_code == 404

    def test_pagination_page_param(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        """page=2 with page_size=1 should return at most 1 finding."""
        audit_id = str(uuid.uuid4())
        _write_audit_result(artifacts_root, "test-co", audit_id)
        resp = client.get(
            f"/api/v1/site-audit/companies/test-co/audits/{audit_id}/findings"
            "?page=2&page_size=1"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["findings"]) <= 1
        assert data["page"] == 2

    def test_requires_tenant_403(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        audit_id = str(uuid.uuid4())
        _write_audit_result(artifacts_root, "other-corp", audit_id)
        resp = client.get(
            f"/api/v1/site-audit/companies/other-corp/audits/{audit_id}/findings"
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test: GET /companies/{slug}/audits/{id}/pages
# ---------------------------------------------------------------------------


class TestGetPageResults:
    def test_returns_paginated_page_results(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        audit_id = str(uuid.uuid4())
        _write_audit_result(artifacts_root, "test-co", audit_id)
        resp = client.get(
            f"/api/v1/site-audit/companies/test-co/audits/{audit_id}/pages"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "pages" in data
        assert "total" in data
        assert data["total"] == 2  # two pages in default fixture
        assert len(data["pages"]) == 2
        # Check first page result fields
        first = data["pages"][0]
        assert first["url"] == "https://testco.com/"
        assert first["status_code"] == 200
        assert first["title"] == "Home | Test Co"
        assert "aeo" in first

    def test_not_found_404(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        missing = "00000000-0000-0000-0000-000000000000"
        resp = client.get(
            f"/api/v1/site-audit/companies/test-co/audits/{missing}/pages"
        )
        assert resp.status_code == 404

    def test_pagination_page_param(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        """Requesting page 2 with page_size=1 returns at most 1 item."""
        audit_id = str(uuid.uuid4())
        _write_audit_result(artifacts_root, "test-co", audit_id)
        resp = client.get(
            f"/api/v1/site-audit/companies/test-co/audits/{audit_id}/pages"
            "?page=2&page_size=1"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["pages"]) <= 1
        assert data["page"] == 2

    def test_requires_tenant_403(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        audit_id = str(uuid.uuid4())
        _write_audit_result(artifacts_root, "other-corp", audit_id)
        resp = client.get(
            f"/api/v1/site-audit/companies/other-corp/audits/{audit_id}/pages"
        )
        assert resp.status_code == 403

    def test_empty_page_results(
        self, client: TestClient, artifacts_root: Path
    ) -> None:
        """An audit with no page_results should return total=0."""
        audit_id = str(uuid.uuid4())
        _write_audit_result(artifacts_root, "test-co", audit_id, page_results=[])
        resp = client.get(
            f"/api/v1/site-audit/companies/test-co/audits/{audit_id}/pages"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["pages"] == []


# ---------------------------------------------------------------------------
# Test: Service — JsonSiteAuditDataService
# ---------------------------------------------------------------------------


class TestJsonSiteAuditDataService:
    """Unit tests for the filesystem-backed service (non-HTTP)."""

    @pytest.fixture
    def service(self, artifacts_root: Path):
        from core.services.json_site_audit_data import JsonSiteAuditDataService

        return JsonSiteAuditDataService(artifacts_root=artifacts_root)

    @pytest.mark.asyncio
    async def test_list_audits_empty(self, service, artifacts_root: Path) -> None:
        result = await service.list_audits("test-co")
        assert result == []

    @pytest.mark.asyncio
    async def test_list_audits_with_data(
        self, service, artifacts_root: Path
    ) -> None:
        for _ in range(2):
            _write_audit_result(artifacts_root, "test-co", str(uuid.uuid4()))
        result = await service.list_audits("test-co")
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_audit_detail_not_found(
        self, service, artifacts_root: Path
    ) -> None:
        from fastapi import HTTPException

        missing = "00000000-0000-0000-0000-000000000000"
        with pytest.raises(HTTPException) as exc_info:
            await service.get_audit_detail("test-co", missing)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_audit_exists_false_when_no_completed(
        self, service, artifacts_root: Path
    ) -> None:
        audit_id = str(uuid.uuid4())
        _write_audit_result(
            artifacts_root, "test-co", audit_id, status="running"
        )
        result = await service.audit_exists("test-co", "testco.com")
        assert result is False

    @pytest.mark.asyncio
    async def test_audit_exists_true_when_completed(
        self, service, artifacts_root: Path
    ) -> None:
        audit_id = str(uuid.uuid4())
        _write_audit_result(artifacts_root, "test-co", audit_id)
        result = await service.audit_exists("test-co", "testco.com")
        assert result is True

    @pytest.mark.asyncio
    async def test_get_latest_audit_id_none_when_empty(
        self, service, artifacts_root: Path
    ) -> None:
        result = await service.get_latest_audit_id("test-co", "testco.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_latest_audit_id_returns_correct_id(
        self, service, artifacts_root: Path
    ) -> None:
        import time

        audit_id_1 = str(uuid.uuid4())
        _write_audit_result(artifacts_root, "test-co", audit_id_1)
        time.sleep(0.01)  # ensure mtime difference
        audit_id_2 = str(uuid.uuid4())
        _write_audit_result(artifacts_root, "test-co", audit_id_2)
        result = await service.get_latest_audit_id("test-co", "testco.com")
        assert result == audit_id_2

    @pytest.mark.asyncio
    async def test_invalid_slug_raises_400(
        self, service, artifacts_root: Path
    ) -> None:
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await service.list_audits("../evil-slug")
        assert exc_info.value.status_code == 400
