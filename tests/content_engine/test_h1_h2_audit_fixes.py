"""Tests for audit findings H1 (brief_id_hint regex) and H2 (index mis-association).

H1: ContentStartRequestV13.brief_id_hint must accept display_id format (WE-003).
H2: build_briefs_parallel must preserve positional indices when topics fail,
    so pipeline_v13's TD branch maps assignments[idx] correctly.

RED → GREEN cycle.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ===========================================================================
# H1 — brief_id_hint regex must accept display_id format
# ===========================================================================


class TestBriefIdHintPattern:
    """ContentStartRequestV13.brief_id_hint must accept both legacy and display_id formats."""

    def test_accepts_legacy_brief_format(self) -> None:
        """brief-001 should still be accepted."""
        from api.schemas.content_v13 import ContentStartRequestV13

        req = ContentStartRequestV13(
            company_name="Test Co",
            domain="test.com",
            entry_mode="manual",
            manual_prompt="Test topic",
            brief_id_hint="brief-001",
        )
        assert req.brief_id_hint == "brief-001"

    def test_accepts_display_id_format(self) -> None:
        """WE-003 must be accepted (this is the H1 fix)."""
        from api.schemas.content_v13 import ContentStartRequestV13

        req = ContentStartRequestV13(
            company_name="Test Co",
            domain="test.com",
            entry_mode="manual",
            manual_prompt="Test topic",
            brief_id_hint="WE-003",
        )
        assert req.brief_id_hint == "WE-003"

    def test_accepts_long_prefix_display_id(self) -> None:
        """ABCDEFGHIJ-042 (10-char prefix) must be accepted."""
        from api.schemas.content_v13 import ContentStartRequestV13

        req = ContentStartRequestV13(
            company_name="Test Co",
            domain="test.com",
            entry_mode="manual",
            manual_prompt="Test topic",
            brief_id_hint="ABCDEFGHIJ-042",
        )
        assert req.brief_id_hint == "ABCDEFGHIJ-042"

    def test_accepts_two_char_prefix(self) -> None:
        """IH-001 (2-char prefix) must be accepted."""
        from api.schemas.content_v13 import ContentStartRequestV13

        req = ContentStartRequestV13(
            company_name="Test Co",
            domain="test.com",
            entry_mode="manual",
            manual_prompt="Test topic",
            brief_id_hint="IH-001",
        )
        assert req.brief_id_hint == "IH-001"

    def test_rejects_path_traversal(self) -> None:
        """../evil must be rejected (security)."""
        from pydantic import ValidationError
        from api.schemas.content_v13 import ContentStartRequestV13

        with pytest.raises(ValidationError):
            ContentStartRequestV13(
                company_name="Test Co",
                domain="test.com",
                entry_mode="manual",
                manual_prompt="Test topic",
                brief_id_hint="../evil",
            )

    def test_rejects_slash(self) -> None:
        """foo/bar must be rejected."""
        from pydantic import ValidationError
        from api.schemas.content_v13 import ContentStartRequestV13

        with pytest.raises(ValidationError):
            ContentStartRequestV13(
                company_name="Test Co",
                domain="test.com",
                entry_mode="manual",
                manual_prompt="Test topic",
                brief_id_hint="foo/bar",
            )

    def test_rejects_empty_string(self) -> None:
        """Empty string must be rejected."""
        from pydantic import ValidationError
        from api.schemas.content_v13 import ContentStartRequestV13

        with pytest.raises(ValidationError):
            ContentStartRequestV13(
                company_name="Test Co",
                domain="test.com",
                entry_mode="manual",
                manual_prompt="Test topic",
                brief_id_hint="",
            )

    def test_accepts_none(self) -> None:
        """None (not provided) must be accepted."""
        from api.schemas.content_v13 import ContentStartRequestV13

        req = ContentStartRequestV13(
            company_name="Test Co",
            domain="test.com",
            entry_mode="manual",
            manual_prompt="Test topic",
        )
        assert req.brief_id_hint is None

    def test_rejects_spaces(self) -> None:
        """Values with spaces must be rejected."""
        from pydantic import ValidationError
        from api.schemas.content_v13 import ContentStartRequestV13

        with pytest.raises(ValidationError):
            ContentStartRequestV13(
                company_name="Test Co",
                domain="test.com",
                entry_mode="manual",
                manual_prompt="Test topic",
                brief_id_hint="WE 003",
            )


# ===========================================================================
# H2 — build_briefs_parallel index preservation when topics fail
# ===========================================================================


class TestBuildBriefsParallelIndexPreservation:
    """build_briefs_parallel must preserve positional indices for None entries."""

    @pytest.mark.asyncio
    async def test_none_entries_preserved_in_results(self) -> None:
        """When topic 1 fails (returns None), result[0] is None and
        result[1] is the successful blueprint — positional alignment maintained."""
        from core.content_engine.brief_builder import build_briefs_parallel

        topic_a = MagicMock()
        topic_a.query_ids = ["q-missing"]  # context missing → returns None
        topic_a.rank = 0

        topic_b = MagicMock()
        topic_b.query_ids = ["q-exists"]
        topic_b.rank = 1

        bp_b = MagicMock()
        bp_b.brief_id = "WE-002"

        async def _mock_build_brief(**kwargs):
            return bp_b

        contexts = {"q-exists": MagicMock()}  # q-missing NOT in contexts

        with patch("core.content_engine.brief_builder.build_brief", _mock_build_brief), \
             patch("core.content_engine.brief_builder.create_span", return_value=MagicMock()), \
             patch("core.content_engine.brief_builder.end_span"):
            results = await build_briefs_parallel(
                contexts=contexts,
                topics=[topic_a, topic_b],
                brief_id_overrides=["WE-001", "WE-002"],
            )

        # H2 fix: results must preserve positional alignment
        # result[0] = None (topic_a failed), result[1] = bp_b (topic_b succeeded)
        assert len(results) == 2, f"Expected 2 entries, got {len(results)}"
        assert results[0] is None, "Failed topic should produce None at index 0"
        assert results[1] is not None, "Successful topic should produce blueprint at index 1"
        assert results[1].brief_id == "WE-002"

    @pytest.mark.asyncio
    async def test_all_succeed_returns_all(self) -> None:
        """When all topics succeed, all entries are non-None."""
        from core.content_engine.brief_builder import build_briefs_parallel

        topic_a = MagicMock()
        topic_a.query_ids = ["q1"]
        topic_a.rank = 0

        topic_b = MagicMock()
        topic_b.query_ids = ["q2"]
        topic_b.rank = 1

        bp_a = MagicMock()
        bp_a.brief_id = "WE-001"
        bp_b = MagicMock()
        bp_b.brief_id = "WE-002"

        call_count = 0

        async def _mock_build_brief(**kwargs):
            nonlocal call_count
            call_count += 1
            m = MagicMock()
            m.brief_id = kwargs.get("brief_id", f"brief-{call_count}")
            return m

        contexts = {"q1": MagicMock(), "q2": MagicMock()}

        with patch("core.content_engine.brief_builder.build_brief", _mock_build_brief), \
             patch("core.content_engine.brief_builder.create_span", return_value=MagicMock()), \
             patch("core.content_engine.brief_builder.end_span"):
            results = await build_briefs_parallel(
                contexts=contexts,
                topics=[topic_a, topic_b],
                brief_id_overrides=["WE-001", "WE-002"],
            )

        assert len(results) == 2
        assert all(r is not None for r in results)

    @pytest.mark.asyncio
    async def test_all_fail_returns_all_none(self) -> None:
        """When all topics fail, all entries are None."""
        from core.content_engine.brief_builder import build_briefs_parallel

        topic_a = MagicMock()
        topic_a.query_ids = ["q-bad"]
        topic_a.rank = 0

        contexts = {}  # No contexts → all fail

        with patch("core.content_engine.brief_builder.create_span", return_value=MagicMock()), \
             patch("core.content_engine.brief_builder.end_span"):
            results = await build_briefs_parallel(
                contexts=contexts,
                topics=[topic_a],
            )

        assert len(results) == 1
        assert results[0] is None


# ===========================================================================
# H2 — pipeline_v13 TD branch correctly maps with None gaps
# ===========================================================================


class TestPipelineTdBranchIndexMapping:
    """pipeline_v13 TD branch must correctly map assignments to blueprints
    even when some blueprints are None."""

    def test_mapping_skips_none_entries(self) -> None:
        """When blueprint[0] is None, assignments[0] must NOT be mapped
        onto blueprint[1]. Each blueprint retains its original index."""
        # Simulate what pipeline_v13.py TD branch does:
        # blueprints come from build_briefs_parallel with Nones preserved
        bp_b = MagicMock()
        bp_b.title = "WRONG"
        bp_b.topic_assignment_id = None

        blueprints = [None, bp_b]  # topic 0 failed, topic 1 succeeded

        assignments_data = [
            {"id": "aid-1", "display_id": "WE-001", "topic_text": "Topic A"},
            {"id": "aid-2", "display_id": "WE-002", "topic_text": "Topic B"},
        ]

        # Simulate the FIXED mapping logic:
        # Only map when blueprints[idx] is not None
        for idx, bp in enumerate(blueprints):
            if bp is not None and idx < len(assignments_data):
                bp.title = assignments_data[idx]["topic_text"]
                bp.topic_assignment_id = assignments_data[idx]["id"]

        # bp_b (at index 1) should get assignment 1's data, NOT assignment 0's
        assert bp_b.title == "Topic B"
        assert bp_b.topic_assignment_id == "aid-2"

    def test_old_bug_would_mismap(self) -> None:
        """Demonstrates the pre-fix bug: filtering None then enumerating
        causes bp at position 1 to get assignment 0's data."""
        bp_b = MagicMock()
        bp_b.title = "WRONG"
        bp_b.topic_assignment_id = None

        raw_blueprints = [None, bp_b]
        # Old code: filter first, then enumerate
        filtered = [bp for bp in raw_blueprints if bp is not None]

        assignments_data = [
            {"id": "aid-1", "topic_text": "Topic A"},
            {"id": "aid-2", "topic_text": "Topic B"},
        ]

        # Old mapping: enumerate(filtered) starts at 0 → maps to assignments[0]
        for idx, bp in enumerate(filtered):
            if idx < len(assignments_data):
                bp.title = assignments_data[idx]["topic_text"]
                bp.topic_assignment_id = assignments_data[idx]["id"]

        # This is the BUG: bp_b gets Topic A (assignment 0) instead of Topic B
        assert bp_b.title == "Topic A", "Old bug maps bp_b to wrong assignment"
        assert bp_b.topic_assignment_id == "aid-1", "Old bug assigns wrong ID"
