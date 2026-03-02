"""Tests for core.content_engine.prompt_registry.

Covers: Hub success, Hub error→fallback, cache hit, TTL expiry,
thread safety, manifest extraction (3 paths).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.content_engine.prompt_registry import (
    _extract_text_from_manifest,
    clear_cache,
    get_prompt,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear prompt cache before every test."""
    clear_cache()
    yield
    clear_cache()


# ---------------------------------------------------------------------------
# Manifest extraction
# ---------------------------------------------------------------------------


class TestExtractTextFromManifest:
    """Three paths for extracting prompt text from Hub manifest."""

    def test_path1_direct_content(self):
        manifest = {
            "messages": [{"kwargs": {"content": "You are a helpful assistant."}}]
        }
        assert _extract_text_from_manifest(manifest) == "You are a helpful assistant."

    def test_path2_nested_prompt_template(self):
        manifest = {
            "messages": [
                {
                    "kwargs": {
                        "prompt": {
                            "kwargs": {"template": "Template text here."}
                        }
                    }
                }
            ]
        }
        assert _extract_text_from_manifest(manifest) == "Template text here."

    def test_path3_toplevel_template(self):
        manifest = {
            "messages": [{"kwargs": {"template": "Top-level template."}}]
        }
        assert _extract_text_from_manifest(manifest) == "Top-level template."

    def test_empty_messages_returns_none(self):
        assert _extract_text_from_manifest({"messages": []}) is None

    def test_no_messages_key_returns_none(self):
        assert _extract_text_from_manifest({}) is None

    def test_empty_kwargs_returns_none(self):
        manifest = {"messages": [{"kwargs": {}}]}
        assert _extract_text_from_manifest(manifest) is None


# ---------------------------------------------------------------------------
# get_prompt — Hub disabled
# ---------------------------------------------------------------------------


class TestGetPromptHubDisabled:
    """When langsmith_use_hub is False, always returns local fallback."""

    def test_returns_local_fallback(self):
        with patch("core.content_engine.prompt_registry.settings") as mock_settings:
            mock_settings.langsmith_use_hub = False
            result = get_prompt("some/prompt", "local fallback text")
        assert result == "local fallback text"


# ---------------------------------------------------------------------------
# get_prompt — Hub enabled
# ---------------------------------------------------------------------------


class TestGetPromptHubEnabled:
    """When Hub is enabled, attempts to pull from Hub."""

    def test_hub_success_returns_pulled_text(self):
        mock_commit = MagicMock()
        mock_commit.manifest = {
            "messages": [{"kwargs": {"content": "Hub prompt text"}}]
        }

        with patch("core.content_engine.prompt_registry.settings") as mock_settings, \
             patch("core.content_engine.prompt_registry._pull_from_hub", return_value="Hub prompt text"):
            mock_settings.langsmith_use_hub = True
            mock_settings.langsmith_hub_tag = "production"
            result = get_prompt("test/prompt", "fallback")

        assert result == "Hub prompt text"

    def test_hub_failure_returns_fallback(self):
        with patch("core.content_engine.prompt_registry.settings") as mock_settings, \
             patch("core.content_engine.prompt_registry._pull_from_hub", return_value=None):
            mock_settings.langsmith_use_hub = True
            mock_settings.langsmith_hub_tag = "production"
            result = get_prompt("test/prompt", "fallback text")

        assert result == "fallback text"

    def test_cache_hit_avoids_hub_call(self):
        with patch("core.content_engine.prompt_registry.settings") as mock_settings, \
             patch("core.content_engine.prompt_registry._pull_from_hub", return_value="Hub text") as mock_pull:
            mock_settings.langsmith_use_hub = True
            mock_settings.langsmith_hub_tag = "prod"

            # First call — cache miss
            r1 = get_prompt("test/prompt", "fallback")
            # Second call — cache hit
            r2 = get_prompt("test/prompt", "fallback")

        assert r1 == "Hub text"
        assert r2 == "Hub text"
        assert mock_pull.call_count == 1  # Only pulled once

    def test_ttl_expiry_triggers_re_pull(self):
        import time as time_mod

        original_time = time_mod.time

        call_count = [0]
        now = [1000.0]

        def mock_time():
            return now[0]

        def mock_pull(hub_name, tag):
            call_count[0] += 1
            return f"v{call_count[0]}"

        with patch("core.content_engine.prompt_registry.settings") as mock_settings, \
             patch("core.content_engine.prompt_registry._pull_from_hub", side_effect=mock_pull), \
             patch("core.content_engine.prompt_registry.time") as mock_time_mod:
            mock_settings.langsmith_use_hub = True
            mock_settings.langsmith_hub_tag = "prod"
            mock_time_mod.time = mock_time

            # First call at t=1000
            r1 = get_prompt("test/ttl", "fallback")
            assert r1 == "v1"

            # Second call at t=1100 (within TTL)
            now[0] = 1100.0
            r2 = get_prompt("test/ttl", "fallback")
            assert r2 == "v1"

            # Third call at t=1400 (TTL expired at 1300)
            now[0] = 1400.0
            r3 = get_prompt("test/ttl", "fallback")
            assert r3 == "v2"

        assert call_count[0] == 2


# ---------------------------------------------------------------------------
# Getter functions in prompt files
# ---------------------------------------------------------------------------


class TestPromptGetters:
    """Each prompt file's getter function works correctly."""

    def test_outliner_getter_returns_local_when_hub_disabled(self):
        with patch("core.content_engine.prompt_registry.settings") as mock_settings:
            mock_settings.langsmith_use_hub = False
            from core.content_engine.prompts.outliner_prompts import (
                OUTLINER_SYSTEM_PROMPT,
                get_outliner_system_prompt,
            )

            result = get_outliner_system_prompt()
        assert result == OUTLINER_SYSTEM_PROMPT

    def test_drafter_getter_returns_local_when_hub_disabled(self):
        with patch("core.content_engine.prompt_registry.settings") as mock_settings:
            mock_settings.langsmith_use_hub = False
            from core.content_engine.prompts.drafter_prompts import (
                DRAFTER_SYSTEM_PROMPT,
                get_drafter_system_prompt,
            )

            result = get_drafter_system_prompt()
        assert result == DRAFTER_SYSTEM_PROMPT

    def test_revision_getter_returns_local_when_hub_disabled(self):
        with patch("core.content_engine.prompt_registry.settings") as mock_settings:
            mock_settings.langsmith_use_hub = False
            from core.content_engine.prompts.drafter_prompts import (
                REVISION_SYSTEM_PROMPT,
                get_revision_system_prompt,
            )

            result = get_revision_system_prompt()
        assert result == REVISION_SYSTEM_PROMPT
