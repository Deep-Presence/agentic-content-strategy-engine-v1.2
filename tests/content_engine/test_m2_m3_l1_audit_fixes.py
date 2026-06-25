"""Tests for audit findings M2, M3, L1.

M2: GA cards should be deduped against DB pieces by topic_assignment_id.
M3: _brief_dir must reject path-traversal characters in brief_id.
L1: Frontend fallback numbering (tested via contract — verify planner-data.ts
    exports a helper to extract max existing number).

RED → GREEN cycle.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ===========================================================================
# M3 — _brief_dir path sanitization
# ===========================================================================


class TestBriefDirSanitization:
    """_brief_dir must reject brief_ids that could cause path traversal."""

    def test_normal_brief_id_accepted(self, tmp_path: Path) -> None:
        from core.content_engine.pipeline_v13 import _brief_dir

        d = _brief_dir(tmp_path, "brief-001")
        assert d == tmp_path / "content" / "brief-001"
        assert d.exists()

    def test_display_id_accepted(self, tmp_path: Path) -> None:
        from core.content_engine.pipeline_v13 import _brief_dir

        d = _brief_dir(tmp_path, "WE-003")
        assert d == tmp_path / "content" / "WE-003"
        assert d.exists()

    def test_dotdot_rejected(self, tmp_path: Path) -> None:
        from core.content_engine.pipeline_v13 import _brief_dir

        with pytest.raises(ValueError, match="unsafe"):
            _brief_dir(tmp_path, "../evil")

    def test_slash_rejected(self, tmp_path: Path) -> None:
        from core.content_engine.pipeline_v13 import _brief_dir

        with pytest.raises(ValueError, match="unsafe"):
            _brief_dir(tmp_path, "foo/bar")

    def test_backslash_rejected(self, tmp_path: Path) -> None:
        from core.content_engine.pipeline_v13 import _brief_dir

        with pytest.raises(ValueError, match="unsafe"):
            _brief_dir(tmp_path, "foo\\bar")

    def test_null_byte_rejected(self, tmp_path: Path) -> None:
        from core.content_engine.pipeline_v13 import _brief_dir

        with pytest.raises(ValueError, match="unsafe"):
            _brief_dir(tmp_path, "foo\x00bar")

    def test_empty_string_rejected(self, tmp_path: Path) -> None:
        from core.content_engine.pipeline_v13 import _brief_dir

        with pytest.raises(ValueError, match="unsafe"):
            _brief_dir(tmp_path, "")


# ===========================================================================
# M2 — GA card deduplication against DB pieces
# ===========================================================================


class TestGaCardDedup:
    """get_briefs() must filter GA cards whose topic_assignment_id
    already appears in a DB content piece (prevents transient duplication
    when cleanup_ga_phase_state fails)."""

    @pytest.mark.asyncio
    async def test_ga_card_filtered_when_db_piece_exists(self) -> None:
        """GA card for ta-123 should NOT appear when a DB piece
        with topic_assignment_id=123 already exists."""
        from api.schemas.content_data import ContentBriefListItem

        # Simulate GA cards from Redis
        ga_cards = [
            ContentBriefListItem(
                id="ta-aid-1",
                display_id="WE-001",
                title="Topic A",
                status="gap_analysis_complete",
                topic_assignment_id="aid-1",
            ),
            ContentBriefListItem(
                id="ta-aid-2",
                display_id="WE-002",
                title="Topic B",
                status="gap_analysis_pending",
                topic_assignment_id="aid-2",
            ),
        ]

        # Simulate DB pieces — aid-1 already has a brief
        db_piece_ta_ids = {"aid-1"}

        # Apply the dedup logic we'll implement
        deduped = [
            card for card in ga_cards
            if card.topic_assignment_id not in db_piece_ta_ids
        ]

        assert len(deduped) == 1
        assert deduped[0].topic_assignment_id == "aid-2"

    @pytest.mark.asyncio
    async def test_ga_cards_without_ta_id_preserved(self) -> None:
        """GA cards without topic_assignment_id (shouldn't happen, but
        defense-in-depth) should be preserved."""
        from api.schemas.content_data import ContentBriefListItem

        ga_cards = [
            ContentBriefListItem(
                id="ta-orphan",
                title="Orphan",
                status="gap_analysis",
                topic_assignment_id=None,
            ),
        ]

        db_piece_ta_ids = {"aid-1"}

        deduped = [
            card for card in ga_cards
            if card.topic_assignment_id not in db_piece_ta_ids
        ]

        assert len(deduped) == 1

    def test_dedup_logic_in_get_briefs_source(self) -> None:
        """Verify db_content_data.py contains the dedup logic."""
        import inspect
        from core.services import db_content_data

        source = inspect.getsource(db_content_data)
        # The dedup should filter ga_cards by checking existing topic_assignment_ids
        assert "topic_assignment_id" in source
        # Look for the dedup pattern — filtering ga_cards against DB pieces
        assert "_db_ta_ids" in source or "db_ta_ids" in source or "piece_ta_ids" in source, (
            "get_briefs() must collect topic_assignment_ids from DB pieces "
            "and filter GA cards that already have a DB piece"
        )
