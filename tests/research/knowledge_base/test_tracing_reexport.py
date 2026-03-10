"""Verify that core.content_engine.tracing_v13 re-exports match core.shared_tools.tracing.

These tests ensure the re-export shim works correctly — all public symbols
from the shared module are accessible via the old import path.
"""
from __future__ import annotations

import pytest

import core.content_engine.tracing_v13 as shim
import core.shared_tools.tracing as shared


# The canonical public API that all existing callers rely on.
_EXPECTED_PUBLIC_API = [
    "create_pipeline_trace",
    "create_research_trace",
    "create_session",
    "create_span",
    "create_trace",
    "end_span",
    "flush",
    "get_current_span",
    "log_generation",
    "log_score",
    "set_current_span",
    "update_trace_output",
]


class TestReExportParity:
    def test_all_public_symbols_available_via_shim(self) -> None:
        """Every expected public function is importable from the shim."""
        for name in _EXPECTED_PUBLIC_API:
            assert hasattr(shim, name), f"Missing re-export: {name}"

    def test_shim_objects_are_identical(self) -> None:
        """Re-exported objects are the exact same objects (not copies)."""
        for name in _EXPECTED_PUBLIC_API:
            shim_obj = getattr(shim, name)
            shared_obj = getattr(shared, name)
            assert shim_obj is shared_obj, f"{name}: shim is not the same object"

    def test_shim_all_matches_expected(self) -> None:
        """The shim's __all__ contains exactly the expected public API."""
        assert set(shim.__all__) == set(_EXPECTED_PUBLIC_API)

    def test_shared_has_all_expected(self) -> None:
        """The shared module actually defines all expected symbols."""
        for name in _EXPECTED_PUBLIC_API:
            assert hasattr(shared, name), f"Missing in shared module: {name}"


class TestCreateResearchTrace:
    """Verify the new create_research_trace helper exists and is callable."""

    def test_returns_none_when_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With no API key, should return None gracefully."""
        monkeypatch.setattr(shared.settings, "langsmith_api_key", None)
        # Reset cached client
        monkeypatch.setattr(shared, "_client_instance", None)
        result = shared.create_research_trace("test-co", company_name="Test Co")
        assert result is None

    def test_importable_from_shim(self) -> None:
        assert shim.create_research_trace is shared.create_research_trace
