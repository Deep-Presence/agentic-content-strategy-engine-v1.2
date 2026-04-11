from __future__ import annotations

from core.content_inventory.models import CannibalizationMatch
from core.models.topic_discovery import IntentType, TopicAssignment
from core.topic_discovery.cannibalization_service import (
    assess_assignment_cannibalization,
)


def _make_match(
    *,
    title: str,
    url: str,
    similarity: float,
    content_type_detected: str = "blog_post",
) -> CannibalizationMatch:
    return CannibalizationMatch(
        inventory_id="inv-123",
        url=url,
        title=title,
        similarity=similarity,
        word_count=1800,
        content_preview="Detailed coverage of the same buyer problem.",
        content_type_detected=content_type_detected,
    )


class TestAssessAssignmentCannibalization:
    def test_no_matches_returns_safe_defaults(self):
        assignment = TopicAssignment(
            topic_text="Expense management automation",
            intent_type=IntentType.informational,
            metadata={},
        )

        result = assess_assignment_cannibalization(assignment, [])

        assert result["cannibalization_risk"] == 0.0
        assert result["cannibalization_risk_score"] == 0.0
        assert result["cannibalization_risk_level"] == "none"
        assert result["cannibalization_recommended_action"] == "safe_to_create_new"
        assert result["cannibalization_matches"] == []
        assert result["cannibalization_reasons"] == []

    def test_high_similarity_comparison_topic_is_high_risk(self):
        assignment = TopicAssignment(
            topic_text="Ramp vs Brex for expense management",
            intent_type=IntentType.commercial,
            metadata={
                "description": "Comparison for finance teams evaluating platforms.",
                "target_keywords": {
                    "primary": "ramp vs brex",
                    "secondary": ["expense management comparison", "brex alternatives"],
                },
                "content_format": "comparison",
            },
        )

        result = assess_assignment_cannibalization(
            assignment,
            [
                _make_match(
                    title="Ramp vs Brex: expense management comparison",
                    url="https://example.com/blog/ramp-vs-brex-expense-management",
                    similarity=0.91,
                ),
            ],
        )

        assert result["cannibalization_risk"] == 0.91
        assert result["cannibalization_risk_level"] == "high"
        assert result["cannibalization_recommended_action"] == "merge_or_refresh_existing"
        assert result["cannibalization_risk_score"] >= 0.85
        assert result["cannibalization_reasons"]
        top_match = result["cannibalization_matches"][0]
        assert top_match["risk_level"] == "high"
        assert top_match["risk_score"] >= 0.85
        assert top_match["signals"]["semantic_similarity"] == 0.91
        assert top_match["signals"]["lexical_overlap"] > 0.2

    def test_medium_similarity_with_different_angle_stays_medium(self):
        assignment = TopicAssignment(
            topic_text="How to automate AP approvals",
            intent_type=IntentType.informational,
            metadata={
                "description": "Workflow guide for operations teams.",
                "target_keywords": {
                    "primary": "automate AP approvals",
                    "secondary": ["accounts payable approval workflow"],
                },
                "content_format": "guide",
            },
        )

        result = assess_assignment_cannibalization(
            assignment,
            [
                _make_match(
                    title="AP automation checklist for controllers",
                    url="https://example.com/resources/ap-automation-checklist",
                    similarity=0.82,
                    content_type_detected="landing_page",
                ),
            ],
        )

        assert result["cannibalization_risk"] == 0.82
        assert result["cannibalization_risk_level"] == "medium"
        assert result["cannibalization_recommended_action"] == "differentiate_angle"
        top_match = result["cannibalization_matches"][0]
        assert top_match["risk_level"] in {"medium", "high"}
        assert top_match["signals"]["format_overlap"] < 1.0

    def test_query_and_citation_overlap_raise_match_score(self):
        assignment = TopicAssignment(
            topic_text="Expense management software comparison",
            intent_type=IntentType.commercial,
            metadata={
                "target_keywords": {
                    "primary": "expense management software comparison",
                    "secondary": ["best expense management software"],
                },
                "content_format": "comparison",
            },
        )

        baseline = assess_assignment_cannibalization(
            assignment,
            [
                _make_match(
                    title="Expense software buyer guide",
                    url="https://example.com/blog/expense-software-buyers-guide",
                    similarity=0.82,
                ),
            ],
        )
        result = assess_assignment_cannibalization(
            assignment,
            [
                _make_match(
                    title="Expense software buyer guide",
                    url="https://example.com/blog/expense-software-buyers-guide",
                    similarity=0.82,
                ),
            ],
            match_signal_overrides={
                "inv-123": {
                    "query_overlap_score": 0.9,
                    "overlapping_query_count": 2,
                    "matched_queries": [
                        "expense management software comparison",
                        "best expense management software",
                    ],
                    "citation_overlap_score": 0.8,
                    "citation_count": 6,
                },
            },
        )

        top_match = result["cannibalization_matches"][0]
        assert top_match["risk_score"] > baseline["cannibalization_matches"][0]["risk_score"]
        assert top_match["signals"]["query_overlap"] == 0.9
        assert top_match["signals"]["citation_overlap"] == 0.8
        assert any("tracked query overlap" in reason.lower() for reason in top_match["reasons"])
