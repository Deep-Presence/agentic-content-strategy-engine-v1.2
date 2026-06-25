"""Tests for core/topic_discovery/display_id.py.

Covers:
- derive_prefix() — multi-word, single-word, empty, whitespace
- allocate_display_ids() — normal, zero count, missing company
- backfill_display_ids() — normal, no NULL rows, empty discovery
- display_id mapping in _db_row_to_pydantic_assignment()
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# derive_prefix()
# ---------------------------------------------------------------------------


class TestDerivePrefix:
    """Unit tests for display ID prefix derivation."""

    def test_multi_word_initials(self):
        from core.topic_discovery.display_id import derive_prefix
        assert derive_prefix("Insight Health") == "IH"

    def test_three_word_initials(self):
        from core.topic_discovery.display_id import derive_prefix
        assert derive_prefix("My Big Company") == "MBC"

    def test_single_word_first_two(self):
        from core.topic_discovery.display_id import derive_prefix
        assert derive_prefix("Webflow") == "WE"

    def test_single_word_short(self):
        from core.topic_discovery.display_id import derive_prefix
        assert derive_prefix("AI") == "AI"

    def test_single_char_word(self):
        from core.topic_discovery.display_id import derive_prefix
        assert derive_prefix("X") == "X"

    def test_empty_string_fallback(self):
        from core.topic_discovery.display_id import derive_prefix
        assert derive_prefix("") == "DP"

    def test_whitespace_only_fallback(self):
        from core.topic_discovery.display_id import derive_prefix
        assert derive_prefix("   ") == "DP"

    def test_leading_trailing_whitespace(self):
        from core.topic_discovery.display_id import derive_prefix
        assert derive_prefix("  Ramp  ") == "RA"

    def test_uppercase_output(self):
        from core.topic_discovery.display_id import derive_prefix
        assert derive_prefix("deep presence") == "DP"

    def test_long_name_clamped_to_10(self):
        """A 12-word company name produces a 12-char prefix, clamped to 10."""
        from core.topic_discovery.display_id import derive_prefix
        result = derive_prefix("A B C D E F G H I J K L")
        assert len(result) <= 10
        assert result == "ABCDEFGHIJ"


# ---------------------------------------------------------------------------
# allocate_display_ids()
# ---------------------------------------------------------------------------


class TestAllocateDisplayIds:
    """Unit tests for atomic display ID allocation."""

    @pytest.mark.asyncio
    async def test_allocates_sequential_ids(self):
        from core.topic_discovery.display_id import allocate_display_ids

        company = MagicMock()
        company.display_id_prefix = "WE"
        company.display_id_counter = 5
        company.name = "Webflow"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = company

        session = AsyncMock()
        session.execute.return_value = mock_result

        ids = await allocate_display_ids(session, uuid.uuid4(), 3)

        assert ids == ["WE-006", "WE-007", "WE-008"]
        assert company.display_id_counter == 8
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_derives_prefix_when_not_set(self):
        from core.topic_discovery.display_id import allocate_display_ids

        company = MagicMock()
        company.display_id_prefix = None
        company.display_id_counter = 0
        company.name = "Insight Health"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = company

        session = AsyncMock()
        session.execute.return_value = mock_result

        ids = await allocate_display_ids(session, uuid.uuid4(), 2)

        assert ids == ["IH-001", "IH-002"]
        assert company.display_id_prefix == "IH"
        assert company.display_id_counter == 2

    @pytest.mark.asyncio
    async def test_zero_count_returns_empty(self):
        from core.topic_discovery.display_id import allocate_display_ids

        session = AsyncMock()
        ids = await allocate_display_ids(session, uuid.uuid4(), 0)

        assert ids == []
        session.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_missing_company_raises(self):
        from core.topic_discovery.display_id import allocate_display_ids

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        session = AsyncMock()
        session.execute.return_value = mock_result

        with pytest.raises(ValueError, match="not found"):
            await allocate_display_ids(session, uuid.uuid4(), 1)


# ---------------------------------------------------------------------------
# backfill_display_ids()
# ---------------------------------------------------------------------------


class TestBackfillDisplayIds:
    """Unit tests for backfill after bulk write."""

    @pytest.mark.asyncio
    async def test_assigns_ids_to_null_rows(self):
        from core.topic_discovery.display_id import backfill_display_ids

        # Mock assignments with NULL display_id
        a1 = MagicMock()
        a1.display_id = None
        a2 = MagicMock()
        a2.display_id = None

        # Mock the SELECT query result
        assignments_result = MagicMock()
        assignments_result.scalars.return_value.all.return_value = [a1, a2]

        # Mock the company query for allocate_display_ids
        company = MagicMock()
        company.display_id_prefix = "RA"
        company.display_id_counter = 10
        company.name = "Ramp"

        company_result = MagicMock()
        company_result.scalar_one_or_none.return_value = company

        session = AsyncMock()
        session.execute.side_effect = [assignments_result, company_result]

        company_id = uuid.uuid4()
        discovery_id = uuid.uuid4()

        count = await backfill_display_ids(session, company_id, discovery_id)

        assert count == 2
        assert a1.display_id == "RA-011"
        assert a2.display_id == "RA-012"
        assert company.display_id_counter == 12

    @pytest.mark.asyncio
    async def test_no_null_rows_returns_zero(self):
        from core.topic_discovery.display_id import backfill_display_ids

        assignments_result = MagicMock()
        assignments_result.scalars.return_value.all.return_value = []

        session = AsyncMock()
        session.execute.return_value = assignments_result

        count = await backfill_display_ids(session, uuid.uuid4(), uuid.uuid4())

        assert count == 0
        # Only one execute call (the SELECT), no allocate
        assert session.execute.await_count == 1


# ---------------------------------------------------------------------------
# _db_row_to_pydantic_assignment — display_id mapping
# ---------------------------------------------------------------------------


class TestRowToPydanticDisplayId:
    """Verify display_id flows through row-to-Pydantic conversion."""

    @staticmethod
    def _make_mock_row(**overrides):
        from core.db.enums import (
            AudienceSegmentType as DBAudienceSegmentType,
            BuyerStage as DBBuyerStage,
            IntentType as DBIntentType,
            RelevanceCell as DBRelevanceCell,
            TopicAssignmentStatus as DBTopicAssignmentStatus,
        )

        row = MagicMock()
        row.id = overrides.get("id", uuid.uuid4())
        row.display_id = overrides.get("display_id", "WE-001")
        row.subdomain_id_text = "sd-1"
        row.subdomain_name = "Test"
        row.topic_text = "Test Topic"
        row.buyer_stage = DBBuyerStage.tofu
        row.intent_type = DBIntentType.informational
        row.audience_segment = "Manager"
        row.audience_segment_type = DBAudienceSegmentType.individual_persona
        row.relevance = DBRelevanceCell.relevant
        row.priority_score = 0.5
        row.priority_factors = {}
        row.status = DBTopicAssignmentStatus.not_started
        row.is_manually_added = False
        row.metadata_json = {}
        row.persona_id = ""
        row.persona_name = ""
        row.persona_affinity_json = {}
        return row

    def test_display_id_mapped(self):
        from core.topic_discovery.db_ops import _db_row_to_pydantic_assignment

        row = self._make_mock_row(display_id="IH-042")
        result = _db_row_to_pydantic_assignment(row)
        assert result.display_id == "IH-042"

    def test_null_display_id_becomes_empty(self):
        from core.topic_discovery.db_ops import _db_row_to_pydantic_assignment

        row = self._make_mock_row(display_id=None)
        result = _db_row_to_pydantic_assignment(row)
        assert result.display_id == ""


# ---------------------------------------------------------------------------
# Pydantic model field
# ---------------------------------------------------------------------------


class TestPydanticModel:
    """Verify TopicAssignment Pydantic model has display_id."""

    def test_default_empty_string(self):
        from core.models.topic_discovery import TopicAssignment

        a = TopicAssignment(topic_text="Test")
        assert a.display_id == ""

    def test_round_trip_serialization(self):
        from core.models.topic_discovery import TopicAssignment

        a = TopicAssignment(topic_text="Test", display_id="WE-003")
        data = a.model_dump(mode="json")
        assert data["display_id"] == "WE-003"

        restored = TopicAssignment.model_validate(data)
        assert restored.display_id == "WE-003"

    def test_backward_compat_missing_field(self):
        """Existing JSON without display_id should still deserialize."""
        from core.models.topic_discovery import TopicAssignment

        old_data = {"topic_text": "Old Topic", "id": "abc-123"}
        a = TopicAssignment.model_validate(old_data)
        assert a.display_id == ""
        assert a.topic_text == "Old Topic"
