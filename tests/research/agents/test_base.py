"""Tests for research agent base infrastructure: singletons, backends, store."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.research.agents.base import (
    backend_factory,
    get_backend,
    get_filesystem_backend,
    get_store,
)


# ---------------------------------------------------------------------------
# get_store()
# ---------------------------------------------------------------------------

class TestGetStore:
    def test_returns_inmemorystore(self):
        from langgraph.store.memory import InMemoryStore
        store = get_store()
        assert isinstance(store, InMemoryStore)

    def test_returns_same_singleton(self):
        s1 = get_store()
        s2 = get_store()
        assert s1 is s2


# ---------------------------------------------------------------------------
# backend_factory()
# ---------------------------------------------------------------------------

class TestBackendFactory:
    def test_returns_composite_backend(self, isolated_artifacts):
        from deepagents.backends import CompositeBackend
        result = backend_factory(MagicMock())
        assert isinstance(result, CompositeBackend)

    def test_has_artifacts_route(self, isolated_artifacts):
        result = backend_factory(MagicMock())
        # CompositeBackend stores routes; check the routes dict attribute
        assert hasattr(result, "routes") or hasattr(result, "_routes")
        routes = getattr(result, "routes", None) or getattr(result, "_routes", {})
        assert "/artifacts/" in routes

    def test_has_memories_route(self, isolated_artifacts):
        result = backend_factory(MagicMock())
        routes = getattr(result, "routes", None) or getattr(result, "_routes", {})
        assert "/memories/" in routes

    def test_creates_artifact_subdirectories(self, isolated_artifacts):
        backend_factory(MagicMock())
        for subdir in ["company_context", "personas", "style_guides", "_logs"]:
            assert (isolated_artifacts / "artifacts" / subdir).is_dir()


# ---------------------------------------------------------------------------
# get_filesystem_backend()
# ---------------------------------------------------------------------------

class TestGetFilesystemBackend:
    def test_returns_filesystem_backend(self, isolated_artifacts):
        from deepagents.backends import FilesystemBackend
        result = get_filesystem_backend()
        assert isinstance(result, FilesystemBackend)

    def test_creates_artifact_subdirectories(self, isolated_artifacts):
        get_filesystem_backend()
        for subdir in ["company_context", "personas", "style_guides", "_logs"]:
            assert (isolated_artifacts / "artifacts" / subdir).is_dir()


# ---------------------------------------------------------------------------
# get_backend()
# ---------------------------------------------------------------------------

class TestGetBackend:
    def test_returns_backend_factory_function(self):
        result = get_backend()
        assert result is backend_factory

    def test_caches_singleton(self):
        b1 = get_backend()
        b2 = get_backend()
        assert b1 is b2
