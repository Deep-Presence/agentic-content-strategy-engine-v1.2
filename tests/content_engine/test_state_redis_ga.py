"""Tests for GA-phase state helpers in core.content_engine.state_redis.

Covers write_ga_phase_state, read_ga_phase_cards, cleanup_ga_phase_state,
and the async variants. Follows the same mock-Redis patterns as
test_state_redis.py.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest


# ── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def mock_sync_redis() -> MagicMock:
    """Mock sync redis.Redis client with pipeline support."""
    r = MagicMock()
    pipe = MagicMock()
    pipe.__enter__ = MagicMock(return_value=pipe)
    pipe.__exit__ = MagicMock(return_value=False)
    pipe.execute = MagicMock(return_value=[True])
    r.pipeline = MagicMock(return_value=pipe)
    r.hgetall = MagicMock(return_value={})
    r.hdel = MagicMock(return_value=0)
    r.delete = MagicMock(return_value=1)
    return r


# ── Write tests ──────────────────────────────────────────────────


class TestWriteGaPhaseState:
    def test_sets_status_for_each_assignment(self, mock_sync_redis: MagicMock) -> None:
        """HSET called with ta-{id} = phase for each assignment ID."""
        from core.content_engine.state_redis import write_ga_phase_state

        write_ga_phase_state(
            mock_sync_redis, "ramp",
            ["aid-1", "aid-2"],
            "gap_analysis_pending",
        )

        pipe = mock_sync_redis.pipeline.return_value
        hset_calls = [c for c in pipe.method_calls if c[0] == "hset"]
        # At least 2 calls for the two assignment IDs
        call_str = str(hset_calls)
        assert "ta-aid-1" in call_str
        assert "ta-aid-2" in call_str
        assert "gap_analysis_pending" in call_str

    def test_sets_task_id_with_tid_prefix(self, mock_sync_redis: MagicMock) -> None:
        """HSET stores __tid:ta-{id} = task_id when task_id provided."""
        from core.content_engine.state_redis import write_ga_phase_state

        write_ga_phase_state(
            mock_sync_redis, "ramp",
            ["aid-1"],
            "gap_analysis",
            task_id="task-xyz",
        )

        pipe = mock_sync_redis.pipeline.return_value
        call_str = str(pipe.method_calls)
        assert "__tid:ta-aid-1" in call_str
        assert "task-xyz" in call_str

    def test_sets_metadata_as_json(self, mock_sync_redis: MagicMock) -> None:
        """HSET stores __meta:ta-{id} as JSON when topic_data provided."""
        from core.content_engine.state_redis import write_ga_phase_state

        topic_data = {
            "aid-1": {
                "title": "How AP Works",
                "cluster": "AP Automation",
                "priority_score": 0.85,
                "buyer_stage": "TOFU",
                "ga_run_id": "run-abc",
            }
        }

        write_ga_phase_state(
            mock_sync_redis, "ramp",
            ["aid-1"],
            "gap_analysis_pending",
            topic_data=topic_data,
        )

        pipe = mock_sync_redis.pipeline.return_value
        call_str = str(pipe.method_calls)
        assert "__meta:ta-aid-1" in call_str
        # The JSON payload should contain the title
        assert "How AP Works" in call_str

    def test_adds_created_and_updated_timestamps_to_metadata(
        self, mock_sync_redis: MagicMock,
    ) -> None:
        """GA card metadata always includes created_at/updated_at for poll reconciliation."""
        from core.content_engine.state_redis import write_ga_phase_state

        write_ga_phase_state(
            mock_sync_redis, "ramp",
            ["aid-1"],
            "gap_analysis_pending",
            topic_data={"aid-1": {"title": "How AP Works"}},
        )

        pipe = mock_sync_redis.pipeline.return_value
        meta_calls = [
            c for c in pipe.method_calls
            if c[0] == "hset" and c[1][1] == "__meta:ta-aid-1"
        ]
        assert meta_calls
        payload = json.loads(meta_calls[-1][1][2])
        assert payload["title"] == "How AP Works"
        assert payload["created_at"]
        assert payload["updated_at"]

    def test_status_only_update_preserves_created_at_and_bumps_updated_at(
        self, mock_sync_redis: MagicMock,
    ) -> None:
        """Status-only GA writes keep the original created_at but refresh updated_at."""
        from core.content_engine.state_redis import write_ga_phase_state

        existing_meta = {
            "title": "How AP Works",
            "created_at": "2026-04-10T07:00:00+00:00",
            "updated_at": "2026-04-10T07:00:00+00:00",
        }
        mock_sync_redis.hget.return_value = json.dumps(existing_meta)

        write_ga_phase_state(
            mock_sync_redis, "ramp",
            ["aid-1"],
            "gap_analysis_complete",
        )

        pipe = mock_sync_redis.pipeline.return_value
        meta_calls = [
            c for c in pipe.method_calls
            if c[0] == "hset" and c[1][1] == "__meta:ta-aid-1"
        ]
        assert meta_calls
        payload = json.loads(meta_calls[-1][1][2])
        assert payload["title"] == "How AP Works"
        assert payload["created_at"] == "2026-04-10T07:00:00+00:00"
        assert payload["updated_at"] != "2026-04-10T07:00:00+00:00"

    def test_skips_task_id_when_none(self, mock_sync_redis: MagicMock) -> None:
        """No __tid: fields written when task_id is None."""
        from core.content_engine.state_redis import write_ga_phase_state

        write_ga_phase_state(
            mock_sync_redis, "ramp",
            ["aid-1"],
            "gap_analysis_pending",
        )

        pipe = mock_sync_redis.pipeline.return_value
        call_str = str(pipe.method_calls)
        assert "__tid:" not in call_str

    def test_status_only_write_still_refreshes_metadata(self, mock_sync_redis: MagicMock) -> None:
        """Status-only writes still update __meta so poll reconciliation has timestamps."""
        from core.content_engine.state_redis import write_ga_phase_state

        write_ga_phase_state(
            mock_sync_redis, "ramp",
            ["aid-1"],
            "gap_analysis_pending",
        )

        pipe = mock_sync_redis.pipeline.return_value
        call_str = str(pipe.method_calls)
        assert "__meta:ta-aid-1" in call_str

    def test_refreshes_ttl(self, mock_sync_redis: MagicMock) -> None:
        """EXPIRE called with 86400 after HSET."""
        from core.content_engine.state_redis import write_ga_phase_state

        write_ga_phase_state(
            mock_sync_redis, "ramp",
            ["aid-1"],
            "gap_analysis",
        )

        pipe = mock_sync_redis.pipeline.return_value
        expire_calls = [c for c in pipe.method_calls if c[0] == "expire"]
        assert len(expire_calls) >= 1
        assert expire_calls[0][1] == ("pipeline_state:ramp", 86400)

    def test_uses_pipeline_for_atomicity(self, mock_sync_redis: MagicMock) -> None:
        """All HSET + EXPIRE wrapped in a redis pipeline() context."""
        from core.content_engine.state_redis import write_ga_phase_state

        write_ga_phase_state(
            mock_sync_redis, "ramp",
            ["aid-1", "aid-2"],
            "gap_analysis_pending",
        )

        mock_sync_redis.pipeline.assert_called_once()
        pipe = mock_sync_redis.pipeline.return_value
        pipe.execute.assert_called_once()


# ── Read tests ───────────────────────────────────────────────────


class TestReadGaPhaseCards:
    def test_returns_only_ga_phase_entries(self, mock_sync_redis: MagicMock) -> None:
        """Only ta-* entries with GA-phase status are returned, not brief-NNN."""
        from core.content_engine.state_redis import read_ga_phase_cards

        mock_sync_redis.hgetall.return_value = {
            "ta-aid-1": "gap_analysis_pending",
            "ta-aid-2": "gap_analysis_complete",
            "brief-001": "generating",
            "brief-002": "evaluating",
            "__tid:ta-aid-1": "task-abc",
            "__tid:brief-001": "task-def",
            "__meta:ta-aid-1": json.dumps({"title": "Topic A", "cluster": "Cluster X"}),
        }

        cards = read_ga_phase_cards(mock_sync_redis, "ramp")

        assert len(cards) == 2
        card_ids = {c["id"] for c in cards}
        assert card_ids == {"ta-aid-1", "ta-aid-2"}
        # brief-NNN entries should NOT appear
        assert not any(c["id"].startswith("brief-") for c in cards)

    def test_returns_empty_for_empty_hash(self, mock_sync_redis: MagicMock) -> None:
        """Returns empty list when Redis key does not exist."""
        from core.content_engine.state_redis import read_ga_phase_cards

        mock_sync_redis.hgetall.return_value = {}

        cards = read_ga_phase_cards(mock_sync_redis, "ramp")
        assert cards == []

    def test_returns_task_id_and_metadata(self, mock_sync_redis: MagicMock) -> None:
        """Cards include task_id, title, cluster from __tid: and __meta: entries."""
        from core.content_engine.state_redis import read_ga_phase_cards

        meta = {
            "title": "How AP Works",
            "cluster": "AP Automation",
            "priority_score": 0.85,
            "created_at": "2026-04-10T07:00:00+00:00",
            "updated_at": "2026-04-10T07:05:00+00:00",
        }
        mock_sync_redis.hgetall.return_value = {
            "ta-aid-1": "gap_analysis",
            "__tid:ta-aid-1": "task-xyz",
            "__meta:ta-aid-1": json.dumps(meta),
        }

        cards = read_ga_phase_cards(mock_sync_redis, "ramp")

        assert len(cards) == 1
        card = cards[0]
        assert card["id"] == "ta-aid-1"
        assert card["status"] == "gap_analysis"
        assert card["task_id"] == "task-xyz"
        assert card["title"] == "How AP Works"
        assert card["cluster"] == "AP Automation"
        assert card["priority_score"] == 0.85
        assert card["topic_assignment_id"] == "aid-1"
        assert card["created_at"] == "2026-04-10T07:00:00+00:00"
        assert card["updated_at"] == "2026-04-10T07:05:00+00:00"

    def test_passes_through_gap_context(self, mock_sync_redis: MagicMock) -> None:
        """Topic-scoped GA card metadata includes summarized gap_context for Queue detail view."""
        from core.content_engine.state_redis import read_ga_phase_cards

        meta = {
            "title": "How AP Works",
            "cluster": "AP Automation",
            "gap_context": {
                "gap_score": 0.27,
                "classification": "significant_gap",
                "company_similarity": 0.31,
                "citation_similarity": 0.58,
                "company_cited": False,
                "company_best_url": "https://test.co/ap",
                "why_picked": ["Large citation gap"],
                "success_indicators": [{"label": "Gap Score", "value": "0.2700", "sub": "significant gap"}],
                "exemplars": [{"url": "https://a.com", "domain": "a.com"}],
            },
        }
        mock_sync_redis.hgetall.return_value = {
            "ta-aid-1": "gap_analysis_complete",
            "__meta:ta-aid-1": json.dumps(meta),
        }

        cards = read_ga_phase_cards(mock_sync_redis, "ramp")

        assert len(cards) == 1
        assert cards[0]["gap_context"]["gap_score"] == 0.27
        assert cards[0]["gap_context"]["classification"] == "significant_gap"
        assert cards[0]["gap_context"]["company_best_url"] == "https://test.co/ap"

    def test_skips_non_ga_status_on_ta_keys(self, mock_sync_redis: MagicMock) -> None:
        """ta-* entries with non-GA status (e.g. 'generating') are filtered out."""
        from core.content_engine.state_redis import read_ga_phase_cards

        mock_sync_redis.hgetall.return_value = {
            "ta-aid-1": "generating",  # Not a GA phase
            "ta-aid-2": "gap_analysis",  # Valid GA phase
        }

        cards = read_ga_phase_cards(mock_sync_redis, "ramp")
        assert len(cards) == 1
        assert cards[0]["id"] == "ta-aid-2"

    def test_handles_corrupt_metadata_json(self, mock_sync_redis: MagicMock) -> None:
        """Corrupt JSON in __meta: is handled gracefully (empty metadata)."""
        from core.content_engine.state_redis import read_ga_phase_cards

        mock_sync_redis.hgetall.return_value = {
            "ta-aid-1": "gap_analysis_pending",
            "__meta:ta-aid-1": "not-valid-json{{{",
        }

        cards = read_ga_phase_cards(mock_sync_redis, "ramp")
        assert len(cards) == 1
        assert cards[0]["title"] == ""  # Falls back to empty


# ── Cleanup tests ────────────────────────────────────────────────


class TestCleanupGaPhaseState:
    def test_removes_all_three_key_types(self, mock_sync_redis: MagicMock) -> None:
        """HDEL removes ta-{id}, __tid:ta-{id}, and __meta:ta-{id} for each assignment."""
        from core.content_engine.state_redis import cleanup_ga_phase_state

        cleanup_ga_phase_state(mock_sync_redis, "ramp", ["aid-1", "aid-2"])

        mock_sync_redis.hdel.assert_called_once()
        args = mock_sync_redis.hdel.call_args[0]
        assert args[0] == "pipeline_state:ramp"
        field_set = set(args[1:])
        # 3 fields per assignment: ta-{id}, __tid:ta-{id}, __meta:ta-{id}
        assert "ta-aid-1" in field_set
        assert "__tid:ta-aid-1" in field_set
        assert "__meta:ta-aid-1" in field_set
        assert "ta-aid-2" in field_set
        assert "__tid:ta-aid-2" in field_set
        assert "__meta:ta-aid-2" in field_set

    def test_preserves_brief_keys(self, mock_sync_redis: MagicMock) -> None:
        """brief-NNN keys are NOT touched by cleanup."""
        from core.content_engine.state_redis import cleanup_ga_phase_state

        cleanup_ga_phase_state(mock_sync_redis, "ramp", ["aid-1"])

        args = mock_sync_redis.hdel.call_args[0]
        field_set = set(args[1:])
        # No brief-related keys should be in the delete set
        assert not any(f.startswith("brief-") for f in field_set)
        assert not any("__tid:brief-" in f for f in field_set)

    def test_noop_on_empty_assignment_ids(self, mock_sync_redis: MagicMock) -> None:
        """Empty list does not call HDEL."""
        from core.content_engine.state_redis import cleanup_ga_phase_state

        cleanup_ga_phase_state(mock_sync_redis, "ramp", [])

        mock_sync_redis.hdel.assert_not_called()


# ── Write-read roundtrip test ────────────────────────────────────


class TestWriteReadRoundtrip:
    def test_write_then_read_returns_matching_fields(self, mock_sync_redis: MagicMock) -> None:
        """Write → read roundtrip verifies fields match.

        Since we use mock Redis, we simulate the hash state manually
        after the write call, then verify read_ga_phase_cards parses it correctly.
        """
        from core.content_engine.state_redis import (
            write_ga_phase_state,
            read_ga_phase_cards,
        )

        topic_data = {
            "aid-1": {
                "title": "AP Best Practices",
                "cluster": "Accounts Payable",
                "priority_score": 0.72,
                "buyer_stage": "MOFU",
                "ga_run_id": "run-123",
                "gap_context": {
                    "gap_score": 0.42,
                    "classification": "significant_gap",
                    "why_picked": ["Large citation gap"],
                    "success_indicators": [{"label": "Gap Score", "value": "0.4200", "sub": "significant gap"}],
                    "exemplars": [{"url": "https://example.com"}],
                },
            }
        }

        # Step 1: Write
        write_ga_phase_state(
            mock_sync_redis, "ramp",
            ["aid-1"],
            "gap_analysis_complete",
            task_id="task-abc",
            topic_data=topic_data,
        )

        # Step 2: Simulate Redis state after write
        mock_sync_redis.hgetall.return_value = {
            "ta-aid-1": "gap_analysis_complete",
            "__tid:ta-aid-1": "task-abc",
            "__meta:ta-aid-1": json.dumps(topic_data["aid-1"]),
        }

        # Step 3: Read and verify
        cards = read_ga_phase_cards(mock_sync_redis, "ramp")

        assert len(cards) == 1
        card = cards[0]
        assert card["id"] == "ta-aid-1"
        assert card["status"] == "gap_analysis_complete"
        assert card["task_id"] == "task-abc"
        assert card["title"] == "AP Best Practices"
        assert card["cluster"] == "Accounts Payable"
        assert card["priority_score"] == 0.72
        assert card["buyer_stage"] == "MOFU"
        assert card["ga_run_id"] == "run-123"
        assert card["topic_assignment_id"] == "aid-1"
        assert card["gap_context"]["gap_score"] == 0.42
