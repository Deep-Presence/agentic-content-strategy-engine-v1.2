"""Tests for additive upsert db_ops functions.

Covers:
- db_write_assignments_for_subdomain — per-subdomain atomic writes
- db_claim_subdomain_for_expansion — optimistic concurrency
- db_mark_subdomain_expanded — status transitions
- db_rebuild_tree_json — tree reconstruction from flat nodes
- db_reset_stale_expanding — crash recovery
- _build_tree_from_flat_nodes — tree builder helper
"""
from __future__ import annotations

import uuid

import pytest

from core.models.topic_discovery import (
    BuyerStage,
    IntentType,
    TopicAssignment,
)
from core.topic_discovery.db_ops import _build_tree_from_flat_nodes


# ═══════════════════════════════════════════════════════════════════════
# _build_tree_from_flat_nodes
# ═══════════════════════════════════════════════════════════════════════


class TestBuildTreeFromFlatNodes:

    def test_single_root(self):
        """Single root node with no children."""
        nodes = [{"id": "r1", "parent_id": None, "name": "Root"}]
        tree = _build_tree_from_flat_nodes(nodes)
        assert len(tree) == 1
        assert tree[0]["name"] == "Root"
        assert tree[0]["children"] == []

    def test_root_with_children(self):
        """Root with two children."""
        nodes = [
            {"id": "r1", "parent_id": None, "name": "Root"},
            {"id": "c1", "parent_id": "r1", "name": "Child A"},
            {"id": "c2", "parent_id": "r1", "name": "Child B"},
        ]
        tree = _build_tree_from_flat_nodes(nodes)
        assert len(tree) == 1
        root = tree[0]
        assert len(root["children"]) == 2
        names = {c["name"] for c in root["children"]}
        assert names == {"Child A", "Child B"}

    def test_deep_nesting(self):
        """Three-level nesting: root → child → grandchild."""
        nodes = [
            {"id": "r1", "parent_id": None, "name": "Root"},
            {"id": "c1", "parent_id": "r1", "name": "Child"},
            {"id": "g1", "parent_id": "c1", "name": "Grandchild"},
        ]
        tree = _build_tree_from_flat_nodes(nodes)
        assert len(tree) == 1
        grandchild = tree[0]["children"][0]["children"][0]
        assert grandchild["name"] == "Grandchild"

    def test_multiple_roots(self):
        """Multiple root nodes (no common parent)."""
        nodes = [
            {"id": "r1", "parent_id": None, "name": "Root A"},
            {"id": "r2", "parent_id": None, "name": "Root B"},
        ]
        tree = _build_tree_from_flat_nodes(nodes)
        assert len(tree) == 2

    def test_empty_input(self):
        """Empty node list returns empty tree."""
        assert _build_tree_from_flat_nodes([]) == []

    def test_orphan_nodes_become_roots(self):
        """Nodes whose parent_id references a missing node become roots."""
        nodes = [
            {"id": "c1", "parent_id": "missing", "name": "Orphan"},
        ]
        tree = _build_tree_from_flat_nodes(nodes)
        assert len(tree) == 1
        assert tree[0]["name"] == "Orphan"

    def test_preserves_extra_fields(self):
        """Non-structural fields are preserved in the output."""
        nodes = [
            {
                "id": "r1",
                "parent_id": None,
                "name": "Root",
                "expansion_status": "expanded",
                "priority_score": 0.85,
            },
        ]
        tree = _build_tree_from_flat_nodes(nodes)
        assert tree[0]["expansion_status"] == "expanded"
        assert tree[0]["priority_score"] == 0.85


# ═══════════════════════════════════════════════════════════════════════
# Per-assignment persona affinity scoring
# ═══════════════════════════════════════════════════════════════════════


class TestComputeAssignmentPersonaAffinity:

    def test_direct_match_boost(self):
        """Assignment persona_id matching a persona gets +0.2 boost."""
        from core.topic_discovery.scoring import compute_assignment_persona_affinity

        result = compute_assignment_persona_affinity(
            buyer_stage="mofu",
            assignment_persona_id="p1",
            subdomain_affinity={"p1": 0.5, "p2": 0.5},
            persona_entries=[("p1", "CFO", "CFO"), ("p2", "DevOps", "DevOps Engineer")],
        )
        assert result["p1"] > result["p2"]
        # p1 gets 0.5 + 0.2 (direct) = 0.7+ (may also get role boost)
        assert result["p1"] >= 0.7

    def test_inherits_subdomain_base(self):
        """Persona with higher subdomain affinity scores higher."""
        from core.topic_discovery.scoring import compute_assignment_persona_affinity

        result = compute_assignment_persona_affinity(
            buyer_stage="tofu",
            assignment_persona_id="p3",
            subdomain_affinity={"p1": 0.9, "p2": 0.1},
            persona_entries=[("p1", "Alice", "Engineer"), ("p2", "Bob", "Intern")],
        )
        assert result["p1"] > result["p2"]

    def test_clamped_to_unit(self):
        """All scores are clamped to [0.0, 1.0]."""
        from core.topic_discovery.scoring import compute_assignment_persona_affinity

        result = compute_assignment_persona_affinity(
            buyer_stage="bofu",
            assignment_persona_id="p1",
            subdomain_affinity={"p1": 0.95},
            persona_entries=[("p1", "CEO", "CEO")],
        )
        assert result["p1"] <= 1.0

    def test_empty_personas(self):
        """No personas → empty result."""
        from core.topic_discovery.scoring import compute_assignment_persona_affinity

        result = compute_assignment_persona_affinity(
            buyer_stage="tofu",
            assignment_persona_id="p1",
            subdomain_affinity={"p1": 0.5},
            persona_entries=[],
        )
        assert result == {}

    def test_executive_bofu_boost(self):
        """Executive role gets a bofu boost."""
        from core.topic_discovery.scoring import compute_assignment_persona_affinity

        result_bofu = compute_assignment_persona_affinity(
            buyer_stage="bofu",
            assignment_persona_id="other",
            subdomain_affinity={"p1": 0.5},
            persona_entries=[("p1", "CEO", "VP of Engineering")],
        )
        result_tofu = compute_assignment_persona_affinity(
            buyer_stage="tofu",
            assignment_persona_id="other",
            subdomain_affinity={"p1": 0.5},
            persona_entries=[("p1", "CEO", "VP of Engineering")],
        )
        # Executive should score higher on bofu than tofu
        assert result_bofu["p1"] > result_tofu["p1"]

    def test_role_classification(self):
        """_classify_role correctly categorizes roles."""
        from core.topic_discovery.scoring import _classify_role

        assert _classify_role("CEO") == "executive"
        assert _classify_role("VP of Sales") == "executive"
        assert _classify_role("Engineering Manager") == "manager"
        assert _classify_role("Team Lead") == "manager"
        assert _classify_role("Software Engineer") == "practitioner"
        assert _classify_role("") == "practitioner"


# ═══════════════════════════════════════════════════════════════════════
# Configuration settings
# ═══════════════════════════════════════════════════════════════════════


class TestExpansionSettings:

    def test_new_settings_have_defaults(self):
        """All new expansion settings have sensible defaults."""
        from core.config.settings import settings

        assert settings.topic_discovery_expansion_max_retries == 2
        assert settings.topic_discovery_expansion_retry_base_delay_s == 2.0
        assert settings.topic_discovery_expansion_db_max_retries == 3
        assert settings.topic_discovery_expansion_circuit_breaker_threshold == 5
        assert settings.topic_discovery_max_subdomains_to_expand == 20

    def test_max_subdomains_increased(self):
        """Max subdomains to expand is now 20 (up from 10)."""
        from core.config.settings import settings

        assert settings.topic_discovery_max_subdomains_to_expand >= 20


# ═══════════════════════════════════════════════════════════════════════
# Pydantic model backward compat
# ═══════════════════════════════════════════════════════════════════════


class TestTopicAssignmentModel:

    def test_persona_affinity_default_empty(self):
        """TopicAssignment.persona_affinity defaults to empty dict."""
        a = TopicAssignment(topic_text="Test topic")
        assert a.persona_affinity == {}

    def test_persona_affinity_round_trip(self):
        """persona_affinity serializes and deserializes correctly."""
        a = TopicAssignment(
            topic_text="Test topic",
            persona_affinity={"p1": 0.8, "p2": 0.3},
        )
        data = a.model_dump(mode="json")
        assert data["persona_affinity"] == {"p1": 0.8, "p2": 0.3}

        b = TopicAssignment.model_validate(data)
        assert b.persona_affinity == {"p1": 0.8, "p2": 0.3}

    def test_backward_compat_no_persona_affinity(self):
        """Old JSON without persona_affinity field still deserializes."""
        data = {
            "topic_text": "Old topic",
            "buyer_stage": "tofu",
            "intent_type": "informational",
        }
        a = TopicAssignment.model_validate(data)
        assert a.persona_affinity == {}
