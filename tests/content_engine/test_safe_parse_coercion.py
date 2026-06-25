"""Tests for Literal field coercion in safe_parse (content_format, funnel_stage, channel)."""
from __future__ import annotations

import json

import pytest

from core.content_engine.utils import safe_parse, _coerce_literal_fields
from core.models.content_generation_v13 import ContentBlueprint


# ---------------------------------------------------------------------------
# Minimal valid blueprint dict (all required fields filled)
# ---------------------------------------------------------------------------

def _blueprint_dict(**overrides) -> dict:
    base = {
        "brief_id": "TST-001",
        "title": "Test Brief",
        "content_format": "long_blog",
        "funnel_stage": "awareness",
        "channel": "blog",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# _coerce_literal_fields unit tests
# ---------------------------------------------------------------------------

class TestCoerceLiteralFields:
    def test_valid_content_format_unchanged(self):
        data = {"content_format": "how_to"}
        _coerce_literal_fields(data)
        assert data["content_format"] == "how_to"

    def test_technical_guide_maps_to_how_to(self):
        data = {"content_format": "technical_guide"}
        _coerce_literal_fields(data)
        assert data["content_format"] == "how_to"

    def test_tutorial_maps_to_how_to(self):
        data = {"content_format": "tutorial"}
        _coerce_literal_fields(data)
        assert data["content_format"] == "how_to"

    def test_listicle_maps_to_short_faq(self):
        data = {"content_format": "listicle"}
        _coerce_literal_fields(data)
        assert data["content_format"] == "short_faq"

    def test_deep_dive_maps_to_long_blog(self):
        data = {"content_format": "deep_dive"}
        _coerce_literal_fields(data)
        assert data["content_format"] == "long_blog"

    def test_roundup_maps_to_comparison(self):
        data = {"content_format": "roundup"}
        _coerce_literal_fields(data)
        assert data["content_format"] == "comparison"

    def test_ultimate_guide_maps_to_pillar_page(self):
        data = {"content_format": "ultimate_guide"}
        _coerce_literal_fields(data)
        assert data["content_format"] == "pillar_page"

    def test_unknown_format_falls_back_to_long_blog(self):
        data = {"content_format": "podcast_transcript"}
        _coerce_literal_fields(data)
        assert data["content_format"] == "long_blog"

    def test_invalid_funnel_stage_falls_back(self):
        data = {"funnel_stage": "exploration"}
        _coerce_literal_fields(data)
        assert data["funnel_stage"] == "awareness"

    def test_invalid_channel_falls_back(self):
        data = {"channel": "social_media"}
        _coerce_literal_fields(data)
        assert data["channel"] == "blog"

    def test_non_dict_passthrough(self):
        assert _coerce_literal_fields([1, 2]) == [1, 2]
        assert _coerce_literal_fields("hello") == "hello"

    def test_missing_fields_no_error(self):
        data = {"title": "foo"}
        _coerce_literal_fields(data)
        assert data == {"title": "foo"}


# ---------------------------------------------------------------------------
# safe_parse integration — full round-trip with ContentBlueprint
# ---------------------------------------------------------------------------

class TestSafeParseCoercion:
    def test_technical_guide_coerced_and_parsed(self):
        raw = json.dumps(_blueprint_dict(content_format="technical_guide"))
        result = safe_parse(raw, ContentBlueprint)
        assert result.content_format == "how_to"
        assert result.brief_id == "TST-001"

    def test_valid_format_passes_through(self):
        raw = json.dumps(_blueprint_dict(content_format="comparison"))
        result = safe_parse(raw, ContentBlueprint)
        assert result.content_format == "comparison"

    def test_unknown_format_with_fenced_json(self):
        payload = _blueprint_dict(content_format="case_study")
        raw = f"```json\n{json.dumps(payload)}\n```"
        result = safe_parse(raw, ContentBlueprint)
        assert result.content_format == "long_blog"

    def test_multiple_invalid_fields_coerced(self):
        raw = json.dumps(_blueprint_dict(
            content_format="guide",
            funnel_stage="exploration",
            channel="social_media",
        ))
        result = safe_parse(raw, ContentBlueprint)
        assert result.content_format == "how_to"
        assert result.funnel_stage == "awareness"
        assert result.channel == "blog"
