"""Tests for db_read_assignments_by_ids() and _db_row_to_pydantic_assignment().

Covers:
- Normal conversion (mock repo, verify Pydantic fields)
- Invalid UUID skipping
- Empty input returns empty list
- Enum mapping correctness
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# _db_row_to_pydantic_assignment
# ---------------------------------------------------------------------------


class TestDbRowToPydanticAssignment:
    """Unit tests for the row→Pydantic conversion helper."""

    @staticmethod
    def _make_mock_row(**overrides):
        """Create a mock TopicAssignmentModel row with DB enum values."""
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
        row.subdomain_id_text = overrides.get("subdomain_id_text", "sd-001")
        row.subdomain_name = overrides.get("subdomain_name", "AP Automation")
        row.topic_text = overrides.get("topic_text", "How AP Works")
        row.buyer_stage = overrides.get("buyer_stage", DBBuyerStage.tofu)
        row.intent_type = overrides.get("intent_type", DBIntentType.informational)
        row.audience_segment = overrides.get("audience_segment", "AP Manager")
        row.audience_segment_type = overrides.get(
            "audience_segment_type", DBAudienceSegmentType.individual_persona,
        )
        row.relevance = overrides.get("relevance", DBRelevanceCell.relevant)
        row.priority_score = overrides.get("priority_score", 0.85)
        row.priority_factors = overrides.get("priority_factors", {"cps": 0.9})
        row.status = overrides.get("status", DBTopicAssignmentStatus.not_started)
        row.is_manually_added = overrides.get("is_manually_added", False)
        row.metadata_json = overrides.get("metadata_json", {"source": "brainstorm"})
        row.persona_id = overrides.get("persona_id", "persona-1")
        row.persona_name = overrides.get("persona_name", "CFO")
        row.persona_affinity_json = overrides.get("persona_affinity_json", {"persona-1": 0.7})
        return row

    def test_converts_all_fields(self):
        from core.topic_discovery.db_ops import _db_row_to_pydantic_assignment
        from core.models.topic_discovery import BuyerStage, IntentType, TopicAssignmentStatus

        row_id = uuid.uuid4()
        row = self._make_mock_row(id=row_id)
        result = _db_row_to_pydantic_assignment(row)

        assert result.id == str(row_id)
        assert result.subdomain_id == "sd-001"
        assert result.subdomain_name == "AP Automation"
        assert result.topic_text == "How AP Works"
        assert result.buyer_stage == BuyerStage.TOFU
        assert result.intent_type == IntentType.informational
        assert result.audience_segment == "AP Manager"
        assert result.priority_score == 0.85
        assert result.priority_factors == {"cps": 0.9}
        assert result.status == TopicAssignmentStatus.not_started
        assert result.is_manually_added is False
        assert result.metadata == {"source": "brainstorm"}
        assert result.persona_id == "persona-1"
        assert result.persona_name == "CFO"
        assert result.persona_affinity == {"persona-1": 0.7}

    def test_handles_none_nullable_fields(self):
        from core.topic_discovery.db_ops import _db_row_to_pydantic_assignment

        row = self._make_mock_row(
            subdomain_id_text=None,
            subdomain_name=None,
            audience_segment=None,
            priority_score=None,
            priority_factors=None,
            metadata_json=None,
            persona_id=None,
            persona_name=None,
            persona_affinity_json=None,
        )
        result = _db_row_to_pydantic_assignment(row)

        assert result.subdomain_id == ""
        assert result.subdomain_name == ""
        assert result.audience_segment == ""
        assert result.priority_score == 0.0
        assert result.priority_factors == {}
        assert result.metadata == {}
        assert result.persona_id == ""
        assert result.persona_name == ""
        assert result.persona_affinity == {}

    def test_enum_mapping_content_produced(self):
        """Verify non-default enum values map correctly."""
        from core.db.enums import (
            BuyerStage as DBBuyerStage,
            IntentType as DBIntentType,
            TopicAssignmentStatus as DBTopicAssignmentStatus,
        )
        from core.topic_discovery.db_ops import _db_row_to_pydantic_assignment
        from core.models.topic_discovery import BuyerStage, IntentType, TopicAssignmentStatus

        row = self._make_mock_row(
            buyer_stage=DBBuyerStage.bofu,
            intent_type=DBIntentType.transactional,
            status=DBTopicAssignmentStatus.content_produced,
        )
        result = _db_row_to_pydantic_assignment(row)

        assert result.buyer_stage == BuyerStage.BOFU
        assert result.intent_type == IntentType.transactional
        assert result.status == TopicAssignmentStatus.content_produced


# ---------------------------------------------------------------------------
# db_read_assignments_by_ids
# ---------------------------------------------------------------------------


class TestDbReadAssignmentsByIds:
    """Unit tests for the db_read_assignments_by_ids convenience function."""

    @pytest.mark.asyncio
    async def test_empty_input_returns_empty(self):
        from core.topic_discovery.db_ops import db_read_assignments_by_ids

        result = await db_read_assignments_by_ids(MagicMock(), [])
        assert result == []

    @pytest.mark.asyncio
    async def test_invalid_uuids_skipped(self):
        from core.topic_discovery.db_ops import db_read_assignments_by_ids

        result = await db_read_assignments_by_ids(MagicMock(), ["not-a-uuid", "also-bad"])
        assert result == []

    @pytest.mark.asyncio
    async def test_fetches_and_converts(self):
        from core.db.enums import (
            AudienceSegmentType as DBAudienceSegmentType,
            BuyerStage as DBBuyerStage,
            IntentType as DBIntentType,
            RelevanceCell as DBRelevanceCell,
            TopicAssignmentStatus as DBTopicAssignmentStatus,
        )
        from core.topic_discovery.db_ops import db_read_assignments_by_ids

        row_id = uuid.uuid4()
        mock_row = MagicMock()
        mock_row.id = row_id
        mock_row.display_id = "WE-001"
        mock_row.subdomain_id_text = "sd-1"
        mock_row.subdomain_name = "Test Node"
        mock_row.topic_text = "Test Topic"
        mock_row.buyer_stage = DBBuyerStage.tofu
        mock_row.intent_type = DBIntentType.informational
        mock_row.audience_segment = "Manager"
        mock_row.audience_segment_type = DBAudienceSegmentType.individual_persona
        mock_row.relevance = DBRelevanceCell.relevant
        mock_row.priority_score = 0.5
        mock_row.priority_factors = {}
        mock_row.status = DBTopicAssignmentStatus.not_started
        mock_row.is_manually_added = False
        mock_row.metadata_json = {}
        mock_row.persona_id = ""
        mock_row.persona_name = ""
        mock_row.persona_affinity_json = {}

        mock_repo = AsyncMock()
        mock_repo.get_by_ids.return_value = [mock_row]

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_sf = MagicMock()
        mock_sf.return_value = mock_session

        with patch(
            "core.db.repositories.topic_discovery_repo.TopicAssignmentRepository.get_by_ids",
            new_callable=AsyncMock,
            return_value=[mock_row],
        ):
            result = await db_read_assignments_by_ids(mock_sf, [str(row_id)])

        assert len(result) == 1
        assert result[0].id == str(row_id)
        assert result[0].topic_text == "Test Topic"

    @pytest.mark.asyncio
    async def test_mixed_valid_invalid_ids(self):
        from core.topic_discovery.db_ops import db_read_assignments_by_ids

        valid_id = str(uuid.uuid4())

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_sf = MagicMock()
        mock_sf.return_value = mock_session

        with patch(
            "core.db.repositories.topic_discovery_repo.TopicAssignmentRepository.get_by_ids",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_get:
            result = await db_read_assignments_by_ids(
                mock_sf, ["not-a-uuid", valid_id],
            )

        assert result == []
        # Should still attempt query with the one valid UUID
        mock_get.assert_called_once()
        call_args = mock_get.call_args[0][0]
        assert len(call_args) == 1
        assert call_args[0] == uuid.UUID(valid_id)
