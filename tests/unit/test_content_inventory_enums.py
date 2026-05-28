"""Tests for ContentIngestionSource enum."""
from __future__ import annotations

import pytest

from core.db.enums import ContentIngestionSource


class TestContentIngestionSourceEnum:
    """ContentIngestionSource — how a content inventory record was discovered."""

    @pytest.mark.parametrize(
        "member,expected_value",
        [
            (ContentIngestionSource.site_audit_crawl, "site_audit_crawl"),
            (ContentIngestionSource.cms_sync, "cms_sync"),
            (ContentIngestionSource.csv_import, "csv_import"),
            (ContentIngestionSource.content_engine, "content_engine"),
            (ContentIngestionSource.manual, "manual"),
        ],
    )
    def test_enum_values(self, member, expected_value):
        assert member.value == expected_value

    def test_is_str_subclass(self):
        assert isinstance(ContentIngestionSource.site_audit_crawl, str)

    def test_roundtrip_from_string(self):
        for val in ("site_audit_crawl", "cms_sync", "csv_import", "content_engine", "manual"):
            assert ContentIngestionSource(val).value == val

    def test_all_members_count(self):
        assert len(ContentIngestionSource) == 5

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            ContentIngestionSource("nonexistent")
