"""Tests for JsonPersonaDataService — filesystem-backed persona read service."""
from __future__ import annotations

from pathlib import Path

import pytest

from core.services.json_persona_data import JsonPersonaDataService
from core.services.persona_data import PersonaDataServiceProtocol


@pytest.fixture
def persona_root(tmp_path: Path) -> Path:
    """Create a minimal persona fixture using actual storage class."""
    from core.research.audience_persona.storage import PersonaStorage

    storage = PersonaStorage(tmp_path, "test-co")
    storage.write_version(
        "cfo-001", "CFO Persona",
        "# CFO Persona\n\nFinance leader at mid-market.",
        {"name": "CFO"},
        kind="icp", created_by="agent", tagline="Financial decision-maker",
    )
    storage.write_version(
        "eng-002", "Engineer Persona",
        "# Engineer Persona\n\nSenior platform engineer.",
        {"name": "Engineer"},
        kind="secondary", created_by="agent", tagline="Technical buyer",
    )
    return tmp_path


class TestJsonPersonaDataService:
    async def test_protocol_conformance(self, tmp_path):
        svc = JsonPersonaDataService(tmp_path)
        assert isinstance(svc, PersonaDataServiceProtocol)

    async def test_list_personas(self, persona_root):
        svc = JsonPersonaDataService(persona_root)
        result = await svc.list_personas("test-co")
        assert len(result) == 2
        names = {p["persona_name"] for p in result}
        assert "CFO Persona" in names
        assert "Engineer Persona" in names
        # Verify response model aligned keys
        for p in result:
            assert "current_version" in p
            assert "tagline" in p

    async def test_get_persona(self, persona_root):
        svc = JsonPersonaDataService(persona_root)
        result = await svc.get_persona("test-co", "cfo-001")
        assert result is not None
        assert result["persona_id"] == "cfo-001"
        assert "Finance" in result["content_md"]

    async def test_get_persona_missing(self, persona_root):
        svc = JsonPersonaDataService(persona_root)
        result = await svc.get_persona("test-co", "nonexistent")
        assert result is None

    async def test_get_summary(self, persona_root):
        svc = JsonPersonaDataService(persona_root)
        result = await svc.get_summary("test-co")
        assert result["slug"] == "test-co"
        assert result["total_personas"] == 2

    async def test_check_staleness(self, persona_root):
        svc = JsonPersonaDataService(persona_root)
        result = await svc.check_staleness("test-co")
        assert isinstance(result, dict)
        assert "stale_personas" in result

    async def test_get_summary_missing_slug(self, tmp_path):
        svc = JsonPersonaDataService(tmp_path)
        result = await svc.get_summary("nonexistent")
        assert result["total_personas"] == 0
