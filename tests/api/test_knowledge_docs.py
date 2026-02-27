"""Tests for Phase 2A: Knowledge Doc Upload endpoints.

Endpoints tested:
  POST   /api/v1/companies/{slug}/knowledge-docs
  GET    /api/v1/companies/{slug}/knowledge-docs
  GET    /api/v1/companies/{slug}/knowledge-docs/{doc_id}
  DELETE /api/v1/companies/{slug}/knowledge-docs/{doc_id}
  GET    /api/v1/companies/{slug}/knowledge-docs/{doc_id}/download
"""
from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.auth.store import AuthStore
from core.models.organization import Company, UserProfile


def _make_file(content: bytes, filename: str, content_type: str = "text/plain"):
    """Create a file-like object suitable for TestClient upload."""
    return {"file": (filename, io.BytesIO(content), content_type)}


class TestUploadDocument:
    """POST /companies/{slug}/knowledge-docs."""

    def test_upload_markdown(
        self, client: TestClient, test_company: Company, test_user: UserProfile
    ) -> None:
        resp = client.post(
            f"/api/v1/companies/{test_company.slug}/knowledge-docs",
            files=_make_file(b"# Internal Doc\n\nSome content here.", "handbook.md"),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["filename"] == "handbook.md"
        assert data["content_type"] == "text/markdown"
        assert data["file_size_bytes"] > 0
        assert data["word_count"] > 0
        assert data["is_embedded"] is False

    def test_upload_txt(
        self, client: TestClient, test_company: Company, test_user: UserProfile
    ) -> None:
        resp = client.post(
            f"/api/v1/companies/{test_company.slug}/knowledge-docs",
            files=_make_file(b"Plain text content for the pipeline.", "notes.txt"),
        )
        assert resp.status_code == 201
        assert resp.json()["content_type"] == "text/plain"

    def test_upload_unsupported_extension(
        self, client: TestClient, test_company: Company, test_user: UserProfile
    ) -> None:
        resp = client.post(
            f"/api/v1/companies/{test_company.slug}/knowledge-docs",
            files=_make_file(b"data", "virus.exe"),
        )
        assert resp.status_code == 422
        assert "unsupported" in resp.json()["detail"].lower()

    def test_upload_oversized_file(
        self, client: TestClient, test_company: Company, test_user: UserProfile
    ) -> None:
        """Files exceeding the size limit are rejected."""
        # Patch the default max to 100 bytes for testing
        with patch("api.services.knowledge_doc_service.DEFAULT_MAX_UPLOAD_BYTES", 100):
            resp = client.post(
                f"/api/v1/companies/{test_company.slug}/knowledge-docs",
                files=_make_file(b"x" * 200, "big.txt"),
            )
        assert resp.status_code == 422
        assert "too large" in resp.json()["detail"].lower()

    def test_upload_cross_tenant_blocked(
        self, client: TestClient, auth_store: AuthStore, test_user: UserProfile
    ) -> None:
        auth_store.create_company("other-co", "Other Co", "other.com")
        resp = client.post(
            "/api/v1/companies/other-co/knowledge-docs",
            files=_make_file(b"content", "doc.md"),
        )
        assert resp.status_code == 403

    def test_upload_unauthenticated(
        self, public_client: TestClient, test_company: Company
    ) -> None:
        resp = public_client.post(
            f"/api/v1/companies/{test_company.slug}/knowledge-docs",
            files=_make_file(b"content", "doc.md"),
        )
        assert resp.status_code == 401

    def test_viewer_cannot_upload(
        self, viewer_client: TestClient, test_company: Company, test_user: UserProfile
    ) -> None:
        resp = viewer_client.post(
            f"/api/v1/companies/{test_company.slug}/knowledge-docs",
            files=_make_file(b"content", "doc.md"),
        )
        assert resp.status_code == 403

    def test_upload_with_product_slug(
        self, client: TestClient, test_company: Company, test_user: UserProfile
    ) -> None:
        resp = client.post(
            f"/api/v1/companies/{test_company.slug}/knowledge-docs?product_slug=widget",
            files=_make_file(b"Product-specific doc.", "product_brief.md"),
        )
        assert resp.status_code == 201

    def test_upload_pdf(
        self, client: TestClient, test_company: Company, test_user: UserProfile
    ) -> None:
        """PDF upload stores the file (extraction tested separately)."""
        # Create a minimal valid-ish PDF (just check upload works)
        with patch("api.services.knowledge_doc_service.extract_text", return_value="extracted text"):
            resp = client.post(
                f"/api/v1/companies/{test_company.slug}/knowledge-docs",
                files=_make_file(b"%PDF-1.4 fake pdf", "report.pdf", "application/pdf"),
            )
        assert resp.status_code == 201
        assert resp.json()["content_type"] == "application/pdf"


class TestListDocuments:
    """GET /companies/{slug}/knowledge-docs."""

    def test_list_empty(
        self, client: TestClient, test_company: Company, test_user: UserProfile
    ) -> None:
        resp = client.get(f"/api/v1/companies/{test_company.slug}/knowledge-docs")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["documents"] == []

    def test_list_after_upload(
        self, client: TestClient, test_company: Company, test_user: UserProfile
    ) -> None:
        # Upload two docs
        client.post(
            f"/api/v1/companies/{test_company.slug}/knowledge-docs",
            files=_make_file(b"doc 1 content", "doc1.md"),
        )
        client.post(
            f"/api/v1/companies/{test_company.slug}/knowledge-docs",
            files=_make_file(b"doc 2 content", "doc2.txt"),
        )
        resp = client.get(f"/api/v1/companies/{test_company.slug}/knowledge-docs")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2
        filenames = {d["filename"] for d in resp.json()["documents"]}
        assert "doc1.md" in filenames
        assert "doc2.txt" in filenames

    def test_list_cross_tenant_blocked(
        self, client: TestClient, auth_store: AuthStore
    ) -> None:
        auth_store.create_company("other-co", "Other Co", "other.com")
        resp = client.get("/api/v1/companies/other-co/knowledge-docs")
        assert resp.status_code == 403


class TestGetDocument:
    """GET /companies/{slug}/knowledge-docs/{doc_id}."""

    def test_get_document_metadata(
        self, client: TestClient, test_company: Company, test_user: UserProfile
    ) -> None:
        upload_resp = client.post(
            f"/api/v1/companies/{test_company.slug}/knowledge-docs",
            files=_make_file(b"some content", "test.md"),
        )
        doc_id = upload_resp.json()["id"]

        resp = client.get(
            f"/api/v1/companies/{test_company.slug}/knowledge-docs/{doc_id}"
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == doc_id
        assert resp.json()["filename"] == "test.md"

    def test_get_nonexistent_document(
        self, client: TestClient, test_company: Company, test_user: UserProfile
    ) -> None:
        resp = client.get(
            f"/api/v1/companies/{test_company.slug}/knowledge-docs/nonexistent"
        )
        assert resp.status_code == 404


class TestDeleteDocument:
    """DELETE /companies/{slug}/knowledge-docs/{doc_id}."""

    def test_delete_document(
        self, client: TestClient, test_company: Company, test_user: UserProfile, artifacts_root: Path
    ) -> None:
        # Upload
        upload_resp = client.post(
            f"/api/v1/companies/{test_company.slug}/knowledge-docs",
            files=_make_file(b"delete me", "temp.md"),
        )
        doc_id = upload_resp.json()["id"]

        # Delete
        resp = client.delete(
            f"/api/v1/companies/{test_company.slug}/knowledge-docs/{doc_id}"
        )
        assert resp.status_code == 204

        # Verify gone
        resp = client.get(
            f"/api/v1/companies/{test_company.slug}/knowledge-docs/{doc_id}"
        )
        assert resp.status_code == 404

    def test_delete_nonexistent(
        self, client: TestClient, test_company: Company, test_user: UserProfile
    ) -> None:
        resp = client.delete(
            f"/api/v1/companies/{test_company.slug}/knowledge-docs/nonexistent"
        )
        assert resp.status_code == 404

    def test_viewer_cannot_delete(
        self, viewer_client: TestClient, client: TestClient, test_company: Company, test_user: UserProfile
    ) -> None:
        upload_resp = client.post(
            f"/api/v1/companies/{test_company.slug}/knowledge-docs",
            files=_make_file(b"content", "doc.md"),
        )
        doc_id = upload_resp.json()["id"]
        resp = viewer_client.delete(
            f"/api/v1/companies/{test_company.slug}/knowledge-docs/{doc_id}"
        )
        assert resp.status_code == 403


class TestDownloadDocument:
    """GET /companies/{slug}/knowledge-docs/{doc_id}/download."""

    def test_download_file(
        self, client: TestClient, test_company: Company, test_user: UserProfile
    ) -> None:
        content = b"# My Handbook\n\nAll the internal knowledge."
        upload_resp = client.post(
            f"/api/v1/companies/{test_company.slug}/knowledge-docs",
            files=_make_file(content, "handbook.md"),
        )
        doc_id = upload_resp.json()["id"]

        resp = client.get(
            f"/api/v1/companies/{test_company.slug}/knowledge-docs/{doc_id}/download"
        )
        assert resp.status_code == 200
        assert resp.content == content

    def test_download_nonexistent(
        self, client: TestClient, test_company: Company, test_user: UserProfile
    ) -> None:
        resp = client.get(
            f"/api/v1/companies/{test_company.slug}/knowledge-docs/nonexistent/download"
        )
        assert resp.status_code == 404
