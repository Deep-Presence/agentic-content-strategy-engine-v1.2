"""Tests for core.research.utils — shared research pipeline helpers."""
from __future__ import annotations

from pathlib import Path

import pytest

from core.research.utils import load_persona_profiles, read_company_context
from core.storage.backends.local import LocalStorageBackend


@pytest.fixture()
def backend(tmp_path: Path) -> LocalStorageBackend:
    return LocalStorageBackend(tmp_path)


# ── read_company_context ────────────────────────────────────────────


class TestReadCompanyContext:
    def test_returns_content_for_effective_slug(self, backend: LocalStorageBackend) -> None:
        backend.write("company_context/ramp.md", "# Ramp profile")
        result = read_company_context(backend, "ramp")
        assert result == "# Ramp profile"

    def test_fallback_to_company_slug(self, backend: LocalStorageBackend) -> None:
        backend.write("company_context/ramp.md", "# Ramp profile")
        result = read_company_context(backend, "ramp__product", "ramp")
        assert result == "# Ramp profile"

    def test_effective_slug_takes_precedence(self, backend: LocalStorageBackend) -> None:
        backend.write("company_context/ramp.md", "# Company level")
        backend.write("company_context/ramp__product.md", "# Product level")
        result = read_company_context(backend, "ramp__product", "ramp")
        assert result == "# Product level"

    def test_returns_none_when_missing(self, backend: LocalStorageBackend) -> None:
        result = read_company_context(backend, "missing-co")
        assert result is None

    def test_returns_none_for_empty_file(self, backend: LocalStorageBackend) -> None:
        backend.write("company_context/ramp.md", "   ")
        result = read_company_context(backend, "ramp")
        assert result is None

    def test_company_slug_none(self, backend: LocalStorageBackend) -> None:
        backend.write("company_context/ramp.md", "# Ramp")
        result = read_company_context(backend, "ramp", None)
        assert result == "# Ramp"


# ── load_persona_profiles ───────────────────────────────────────────


class TestLoadPersonaProfiles:
    def _seed_personas(self, backend: LocalStorageBackend, slug: str) -> None:
        """Create a minimal persona manifest + profile markdown files via backend."""
        import json

        manifest = {
            "slug": slug,
            "company_name": "Test Co",
            "personas": {
                "p1": {"title": "Persona 1", "status": "fresh", "current_version": 1},
                "p2": {"title": "Persona 2", "status": "fresh", "current_version": 1},
                "p3": {"title": "Persona 3", "status": "archived", "current_version": 1},
            },
        }
        backend.write(f"audience_personas/{slug}/_manifest.json", json.dumps(manifest))
        # PersonaStorage.read_version reads from {prefix}{pid}/v{ver}.md
        for pid in ("p1", "p2", "p3"):
            backend.write(
                f"audience_personas/{slug}/{pid}/v1.md",
                f"# {pid} profile",
            )

    def test_loads_fresh_profiles(self, backend: LocalStorageBackend) -> None:
        self._seed_personas(backend, "test-co")
        result = load_persona_profiles(backend, "test-co")
        assert len(result) == 2
        assert "# p1 profile" in result
        assert "# p2 profile" in result

    def test_skips_archived_profiles(self, backend: LocalStorageBackend) -> None:
        self._seed_personas(backend, "test-co")
        result = load_persona_profiles(backend, "test-co")
        assert all("p3" not in md for md in result)

    def test_fallback_to_company_slug(self, backend: LocalStorageBackend) -> None:
        self._seed_personas(backend, "test-co")
        result = load_persona_profiles(backend, "test-co__product", "test-co")
        assert len(result) == 2

    def test_returns_empty_when_no_personas(self, backend: LocalStorageBackend) -> None:
        result = load_persona_profiles(backend, "missing-co")
        assert result == []
