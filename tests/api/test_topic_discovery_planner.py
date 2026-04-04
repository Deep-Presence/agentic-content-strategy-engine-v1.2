"""Tests for Content Planner endpoints in the Topic Discovery API.

Covers four new endpoints:
- GET  /{slug}/summary        — Discovery summary
- GET  /{slug}/assignments     — Paginated assignment list with filters
- PATCH /{slug}/assignments/{id} — Update assignment status (approve/reject/restore)
- POST  /{slug}/assignments    — Create custom assignment
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI

from api.dependencies import get_td_data_service


# ── Constants ─────────────────────────────────────────────────────────

PREFIX = "/api/v1/topic-discovery"

SUMMARY_DATA = {
    "slug": "test-co",
    "company_name": "Test Co",
    "has_taxonomy": True,
    "taxonomy_version": 1,
    "has_matrix": True,
    "matrix_version": 1,
    "scoring_version": 1,
    "persona_affinity_version": 1,
    "status": "discovery_complete",
    "last_updated": "2026-04-04T00:00:00Z",
}

ASSIGNMENT_ITEM = {
    "id": "aaaaaaaa-1111-2222-3333-444444444444",
    "topic_text": "Test Topic",
    "buyer_stage": "tofu",
    "intent_type": "informational",
    "priority_score": 0.75,
    "status": "not_started",
    "persona_id": "sf",
    "persona_name": "Solo Founder",
    "subdomain_id": "sd-1",
    "subdomain_name": "Test Subdomain",
    "is_manually_added": False,
    "metadata": {},
}

ASSIGNMENT_LIST_DATA = {
    "items": [ASSIGNMENT_ITEM],
    "total": 1,
    "page": 1,
    "page_size": 50,
}

UPDATED_ASSIGNMENT = {
    "id": "aaaaaaaa-1111-2222-3333-444444444444",
    "status": "approved",
    "topic_text": "Test Topic",
}

CREATED_ASSIGNMENT = {
    "id": "bbbbbbbb-1111-2222-3333-444444444444",
    "topic_text": "Custom Topic",
    "buyer_stage": "mofu",
    "intent_type": "commercial",
    "priority_score": 0.5,
    "status": "not_started",
    "is_manually_added": True,
    "subdomain_id": "",
    "subdomain_name": "",
    "persona_id": "",
    "persona_name": "",
}


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def td_svc_mock():
    """AsyncMock with sensible defaults for all TD data service methods."""
    mock = AsyncMock()
    mock.get_discovery_summary.return_value = SUMMARY_DATA.copy()
    mock.list_assignments.return_value = {
        **ASSIGNMENT_LIST_DATA,
        "items": [ASSIGNMENT_ITEM.copy()],
    }
    mock.update_assignment_status.return_value = UPDATED_ASSIGNMENT.copy()
    mock.create_assignment.return_value = CREATED_ASSIGNMENT.copy()
    return mock


@pytest.fixture(autouse=True)
def _override_td_svc(app: FastAPI, td_svc_mock: AsyncMock):
    """Inject mock TD data service via dependency override.

    The ``get_td_data_service`` dependency is an async generator, so the
    override must also be an async generator that yields the mock.
    """

    async def _override():
        yield td_svc_mock

    app.dependency_overrides[get_td_data_service] = _override
    yield
    app.dependency_overrides.pop(get_td_data_service, None)


# ═══════════════════════════════════════════════════════════════════════
# GET /{slug}/summary
# ═══════════════════════════════════════════════════════════════════════


class TestGetDiscoverySummary:
    """Tests for GET /topic-discovery/{slug}/summary."""

    def test_summary_200(self, client):
        resp = client.get(f"{PREFIX}/test-co/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "test-co"
        assert data["has_taxonomy"] is True
        assert data["has_matrix"] is True
        assert data["status"] == "discovery_complete"

    def test_summary_tenant_isolation_403(self, client):
        resp = client.get(f"{PREFIX}/other-co/summary")
        assert resp.status_code == 403

    def test_summary_404_when_no_discovery(self, client, td_svc_mock):
        td_svc_mock.get_discovery_summary.return_value = None
        resp = client.get(f"{PREFIX}/test-co/summary")
        assert resp.status_code == 404

    def test_summary_requires_auth(self, public_client):
        resp = public_client.get(f"{PREFIX}/test-co/summary")
        assert resp.status_code in (401, 403)

    def test_summary_prefix_attack_403(self, client):
        """Slug 'test-coa' must NOT match company 'test-co'."""
        resp = client.get(f"{PREFIX}/test-coa/summary")
        assert resp.status_code == 403

    def test_summary_product_scoped_slug(self, client):
        """Effective slug 'test-co__product' is allowed for company 'test-co'."""
        resp = client.get(f"{PREFIX}/test-co__product/summary")
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════
# GET /{slug}/assignments
# ═══════════════════════════════════════════════════════════════════════


class TestListAssignments:
    """Tests for GET /topic-discovery/{slug}/assignments."""

    def test_assignments_200(self, client):
        resp = client.get(f"{PREFIX}/test-co/assignments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "test-co"
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["topic_text"] == "Test Topic"

    def test_assignments_buyer_stage_filter(self, client, td_svc_mock):
        resp = client.get(f"{PREFIX}/test-co/assignments?buyer_stage=tofu")
        assert resp.status_code == 200
        # Verify filter was passed to service
        call_kwargs = td_svc_mock.list_assignments.call_args
        assert call_kwargs.kwargs["buyer_stage"] == "tofu"

    def test_assignments_status_filter(self, client, td_svc_mock):
        resp = client.get(f"{PREFIX}/test-co/assignments?status=approved")
        assert resp.status_code == 200
        call_kwargs = td_svc_mock.list_assignments.call_args
        assert call_kwargs.kwargs["status"] == "approved"

    def test_assignments_intent_type_filter(self, client, td_svc_mock):
        resp = client.get(
            f"{PREFIX}/test-co/assignments?intent_type=commercial"
        )
        assert resp.status_code == 200
        call_kwargs = td_svc_mock.list_assignments.call_args
        assert call_kwargs.kwargs["intent_type"] == "commercial"

    def test_assignments_persona_id_filter(self, client, td_svc_mock):
        resp = client.get(f"{PREFIX}/test-co/assignments?persona_id=sf")
        assert resp.status_code == 200
        call_kwargs = td_svc_mock.list_assignments.call_args
        assert call_kwargs.kwargs["persona_id"] == "sf"

    def test_assignments_empty(self, client, td_svc_mock):
        td_svc_mock.list_assignments.return_value = {
            "items": [],
            "total": 0,
            "page": 1,
            "page_size": 50,
        }
        resp = client.get(f"{PREFIX}/test-co/assignments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_assignments_tenant_isolation_403(self, client):
        resp = client.get(f"{PREFIX}/other-co/assignments")
        assert resp.status_code == 403

    def test_assignments_product_scoped_slug(self, client):
        resp = client.get(f"{PREFIX}/test-co__product/assignments")
        assert resp.status_code == 200

    def test_assignments_pagination(self, client, td_svc_mock):
        resp = client.get(
            f"{PREFIX}/test-co/assignments?page=2&page_size=10"
        )
        assert resp.status_code == 200
        call_kwargs = td_svc_mock.list_assignments.call_args
        assert call_kwargs.kwargs["page"] == 2
        assert call_kwargs.kwargs["page_size"] == 10

    def test_assignments_requires_auth(self, public_client):
        resp = public_client.get(f"{PREFIX}/test-co/assignments")
        assert resp.status_code in (401, 403)


# ═══════════════════════════════════════════════════════════════════════
# PATCH /{slug}/assignments/{assignment_id}
# ═══════════════════════════════════════════════════════════════════════


class TestUpdateAssignmentStatus:
    """Tests for PATCH /topic-discovery/{slug}/assignments/{id}."""

    ASSIGNMENT_ID = "aaaaaaaa-1111-2222-3333-444444444444"

    def test_approve_200(self, client):
        resp = client.patch(
            f"{PREFIX}/test-co/assignments/{self.ASSIGNMENT_ID}",
            json={"status": "approved"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["assignment_id"] == self.ASSIGNMENT_ID
        assert data["status"] == "approved"

    def test_reject_200(self, client, td_svc_mock):
        td_svc_mock.update_assignment_status.return_value = {
            "id": self.ASSIGNMENT_ID,
            "status": "rejected",
            "topic_text": "Test Topic",
        }
        resp = client.patch(
            f"{PREFIX}/test-co/assignments/{self.ASSIGNMENT_ID}",
            json={"status": "rejected"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"

    def test_restore_not_started_200(self, client, td_svc_mock):
        td_svc_mock.update_assignment_status.return_value = {
            "id": self.ASSIGNMENT_ID,
            "status": "not_started",
            "topic_text": "Test Topic",
        }
        resp = client.patch(
            f"{PREFIX}/test-co/assignments/{self.ASSIGNMENT_ID}",
            json={"status": "not_started"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "not_started"

    def test_tenant_isolation_403(self, client):
        resp = client.patch(
            f"{PREFIX}/other-co/assignments/{self.ASSIGNMENT_ID}",
            json={"status": "approved"},
        )
        assert resp.status_code == 403

    def test_not_found_404(self, client, td_svc_mock):
        td_svc_mock.update_assignment_status.return_value = None
        resp = client.patch(
            f"{PREFIX}/test-co/assignments/nonexistent-id",
            json={"status": "approved"},
        )
        assert resp.status_code == 404

    def test_invalid_status_422(self, client):
        resp = client.patch(
            f"{PREFIX}/test-co/assignments/{self.ASSIGNMENT_ID}",
            json={"status": "garbage"},
        )
        assert resp.status_code == 422

    def test_viewer_rejected_403(self, viewer_client):
        resp = viewer_client.patch(
            f"{PREFIX}/test-co/assignments/{self.ASSIGNMENT_ID}",
            json={"status": "approved"},
        )
        assert resp.status_code == 403

    def test_idempotent_already_approved(self, client, td_svc_mock):
        """Approving an already-approved assignment returns success."""
        td_svc_mock.update_assignment_status.return_value = {
            "id": self.ASSIGNMENT_ID,
            "status": "approved",
            "topic_text": "Test Topic",
        }
        resp = client.patch(
            f"{PREFIX}/test-co/assignments/{self.ASSIGNMENT_ID}",
            json={"status": "approved"},
        )
        assert resp.status_code == 200

    def test_prefix_attack_403(self, client):
        """Slug 'test-coa' must NOT match company 'test-co'."""
        resp = client.patch(
            f"{PREFIX}/test-coa/assignments/{self.ASSIGNMENT_ID}",
            json={"status": "approved"},
        )
        assert resp.status_code == 403

    def test_missing_status_field_422(self, client):
        resp = client.patch(
            f"{PREFIX}/test-co/assignments/{self.ASSIGNMENT_ID}",
            json={},
        )
        assert resp.status_code == 422

    def test_extra_fields_rejected_422(self, client):
        resp = client.patch(
            f"{PREFIX}/test-co/assignments/{self.ASSIGNMENT_ID}",
            json={"status": "approved", "bogus": True},
        )
        assert resp.status_code == 422

    def test_requires_auth(self, public_client):
        resp = public_client.patch(
            f"{PREFIX}/test-co/assignments/{self.ASSIGNMENT_ID}",
            json={"status": "approved"},
        )
        assert resp.status_code in (401, 403)


# ═══════════════════════════════════════════════════════════════════════
# POST /{slug}/assignments
# ═══════════════════════════════════════════════════════════════════════


class TestCreateCustomAssignment:
    """Tests for POST /topic-discovery/{slug}/assignments."""

    def test_create_201(self, client):
        resp = client.post(
            f"{PREFIX}/test-co/assignments",
            json={
                "topic_text": "Custom Topic for Testing",
                "buyer_stage": "mofu",
                "intent_type": "commercial",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["is_manually_added"] is True
        assert data["topic_text"] == "Custom Topic"

    def test_create_tenant_isolation_403(self, client):
        resp = client.post(
            f"{PREFIX}/other-co/assignments",
            json={"topic_text": "Custom Topic for Testing"},
        )
        assert resp.status_code == 403

    def test_create_missing_topic_text_422(self, client):
        resp = client.post(
            f"{PREFIX}/test-co/assignments",
            json={"buyer_stage": "tofu"},
        )
        assert resp.status_code == 422

    def test_create_topic_text_too_short_422(self, client):
        resp = client.post(
            f"{PREFIX}/test-co/assignments",
            json={"topic_text": "abc"},
        )
        assert resp.status_code == 422

    def test_create_viewer_rejected_403(self, viewer_client):
        resp = viewer_client.post(
            f"{PREFIX}/test-co/assignments",
            json={"topic_text": "Custom Topic for Testing"},
        )
        assert resp.status_code == 403

    def test_create_requires_auth(self, public_client):
        resp = public_client.post(
            f"{PREFIX}/test-co/assignments",
            json={"topic_text": "Custom Topic for Testing"},
        )
        assert resp.status_code in (401, 403)

    def test_create_with_all_optional_fields(self, client, td_svc_mock):
        resp = client.post(
            f"{PREFIX}/test-co/assignments",
            json={
                "topic_text": "Full Custom Topic",
                "buyer_stage": "bofu",
                "intent_type": "transactional",
                "subdomain_id": "sd-5",
                "subdomain_name": "Enterprise",
                "persona_id": "cto",
                "persona_name": "CTO",
                "priority_score": 0.9,
            },
        )
        assert resp.status_code == 201
        # Verify all fields were passed to service
        call_kwargs = td_svc_mock.create_assignment.call_args
        assignment_data = call_kwargs.kwargs["assignment_data"]
        assert assignment_data["subdomain_id"] == "sd-5"
        assert assignment_data["persona_id"] == "cto"
        assert assignment_data["priority_score"] == 0.9
        assert assignment_data["buyer_stage"] == "bofu"
        assert assignment_data["intent_type"] == "transactional"

    def test_create_invalid_buyer_stage_422(self, client):
        resp = client.post(
            f"{PREFIX}/test-co/assignments",
            json={"topic_text": "Custom Topic for Testing", "buyer_stage": "invalid"},
        )
        assert resp.status_code == 422

    def test_create_invalid_intent_type_422(self, client):
        resp = client.post(
            f"{PREFIX}/test-co/assignments",
            json={"topic_text": "Custom Topic for Testing", "intent_type": "invalid"},
        )
        assert resp.status_code == 422

    def test_create_priority_out_of_range_422(self, client):
        resp = client.post(
            f"{PREFIX}/test-co/assignments",
            json={"topic_text": "Custom Topic for Testing", "priority_score": 1.5},
        )
        assert resp.status_code == 422

    def test_create_extra_fields_rejected_422(self, client):
        resp = client.post(
            f"{PREFIX}/test-co/assignments",
            json={"topic_text": "Custom Topic for Testing", "bogus": True},
        )
        assert resp.status_code == 422

    def test_create_no_matrix_409(self, client, td_svc_mock):
        """Creating assignment without prior discovery returns 409."""
        td_svc_mock.create_assignment.side_effect = ValueError(
            "No matrix found for this slug. Run topic discovery first."
        )
        resp = client.post(
            f"{PREFIX}/test-co/assignments",
            json={"topic_text": "Custom Topic for Testing"},
        )
        assert resp.status_code == 409
        assert "No matrix found" in resp.json()["detail"]

    def test_create_prefix_attack_403(self, client):
        """Slug 'test-coa' must NOT match company 'test-co'."""
        resp = client.post(
            f"{PREFIX}/test-coa/assignments",
            json={"topic_text": "Custom Topic for Testing"},
        )
        assert resp.status_code == 403

    def test_create_product_scoped_slug(self, client):
        """Effective slug 'test-co__product' is allowed for company 'test-co'."""
        resp = client.post(
            f"{PREFIX}/test-co__product/assignments",
            json={"topic_text": "Custom Topic for Testing"},
        )
        assert resp.status_code == 201
