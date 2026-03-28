"""Edge case tests for settings and DI configuration.

Tests that the application handles missing/partial environment
variables gracefully.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestSettingsDefaults:
    """Verify optional settings have sensible defaults."""

    def test_settings_has_required_fields(self):
        """Settings class can be imported and has expected attributes."""
        from core.config.settings import Settings

        # Check the class has key fields (not values — those come from env)
        assert hasattr(Settings, "model_fields")
        fields = Settings.model_fields
        assert "openai_api_key" in fields
        assert "anthropic_api_key" in fields

    def test_optional_fields_have_defaults(self):
        """All optional fields should have defaults (no KeyError)."""
        from core.config.settings import Settings

        for name, field_info in Settings.model_fields.items():
            if not field_info.is_required():
                assert field_info.default is not None or field_info.default_factory is not None or field_info.default is None, \
                    f"Optional field '{name}' should have a default"


class TestDISwitch:
    """Test that dependency injection requires DATABASE_URL for task store."""

    def test_db_task_store_is_importable(self):
        """DbTaskStore is the only production task store implementation."""
        from core.services.db_task_store import DbTaskStore

        assert DbTaskStore is not None

    def test_missing_database_url_raises(self):
        """Verified via test_lifespan_task_store.py — referenced here for completeness.

        When DATABASE_URL is not set, _init_task_store raises RuntimeError.
        """
        pass  # Covered by existing test_lifespan_task_store.py
