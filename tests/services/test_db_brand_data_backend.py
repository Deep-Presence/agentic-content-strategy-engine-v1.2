"""Unit tests for DbBrandDataService StorageBackend injection (Phase 7).

These tests verify that DbBrandDataService correctly uses StorageBackend
instead of raw filesystem Path operations.  They do NOT require a database.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.services.db_brand_data import DbBrandDataService
from core.storage.backends.local import LocalStorageBackend


class TestConstructor:
    """Verify StorageBackend injection in constructor."""

    def test_backend_none_defaults_to_local(self, tmp_path):
        svc = DbBrandDataService(
            pipeline_repo=MagicMock(),
            artifacts_root=tmp_path,
        )
        assert isinstance(svc._backend, LocalStorageBackend)

    def test_backend_injected_is_used(self, tmp_path):
        mock_backend = MagicMock()
        svc = DbBrandDataService(
            pipeline_repo=MagicMock(),
            artifacts_root=tmp_path,
            backend=mock_backend,
        )
        assert svc._backend is mock_backend


class TestResearchArtifactsPassesBackend:
    """Verify get_research_artifacts() passes StorageBackend to delegate."""

    @pytest.mark.asyncio
    async def test_passes_backend_kwarg(self, tmp_path):
        mock_backend = MagicMock()

        svc = DbBrandDataService(
            pipeline_repo=AsyncMock(),
            artifacts_root=tmp_path,
            backend=mock_backend,
        )

        with patch(
            "api.services.brand_data_service.get_research_artifacts",
        ) as mock_fn:
            from api.schemas.brand_data import ResearchArtifactsResponse
            mock_fn.return_value = ResearchArtifactsResponse()
            await svc.get_research_artifacts("test-co")
            mock_fn.assert_called_once()
            call_kwargs = mock_fn.call_args
            assert call_kwargs.kwargs.get("backend") is mock_backend

    @pytest.mark.asyncio
    async def test_reads_artifacts_via_backend(self, tmp_path):
        """End-to-end: write artifacts via backend, verify they are found."""
        backend = LocalStorageBackend(tmp_path)
        backend.write("company_context/test-co.md", "# Company Context")
        backend.write("style_guides/test-co.md", "# Style Guide")

        svc = DbBrandDataService(
            pipeline_repo=AsyncMock(),
            artifacts_root=tmp_path,
            backend=backend,
        )

        resp = await svc.get_research_artifacts("test-co")
        assert resp.company_context.status == "approved"
        assert resp.company_context.content == "# Company Context"
        assert resp.style_guide.status == "approved"
        assert resp.style_guide.content == "# Style Guide"
