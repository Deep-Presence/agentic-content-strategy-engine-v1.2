"""Shared fixtures for Topic Discovery tests."""
from __future__ import annotations

import pytest

from core.models.topic_discovery import (
    BuyerStage,
    IntentType,
    AudienceSegmentType,
    RelevanceCell,
    SubdomainCandidate,
    SubdomainNode,
    SourceResult,
    TaxonomyTree,
    TDSource,
    TopicAssignment,
    TopicAssignmentMatrix,
    TopicAssignmentStatus,
    TopicDiscoveryInput,
    TopicDiscoveryManifest,
    TopicDiscoveryStatus,
)


@pytest.fixture
def td_input() -> TopicDiscoveryInput:
    """Standard Topic Discovery input for tests."""
    return TopicDiscoveryInput(
        company_name="Test Co",
        domain="test.com",
        company_slug="test-co",
        product_slug=None,
        auto_approve_checkpoints=[1, 2],
    )


@pytest.fixture
def sample_subdomain_candidates() -> list[SubdomainCandidate]:
    """A small set of subdomain candidates from mixed sources."""
    return [
        SubdomainCandidate(
            name="expense management",
            description="Automated expense tracking",
            source=TDSource.source_a,
            round_number=1,
            confidence=0.9,
        ),
        SubdomainCandidate(
            name="corporate cards",
            description="Virtual and physical cards",
            source=TDSource.source_b,
            round_number=1,
            confidence=0.8,
        ),
        SubdomainCandidate(
            name="compliance automation",
            description="Regulatory compliance workflows",
            source=TDSource.source_d,
            round_number=1,
            specialist_lens="regulatory expert",
            confidence=0.6,
        ),
    ]


@pytest.fixture
def sample_source_result() -> SourceResult:
    """A SourceResult with 5 candidates across 3 rounds."""
    return SourceResult(
        source=TDSource.source_a,
        candidates=[
            SubdomainCandidate(
                name=f"subdomain-{i}",
                source=TDSource.source_a,
                round_number=(i % 3) + 1,
                confidence=0.5 + i * 0.1,
            )
            for i in range(5)
        ],
        total_rounds=3,
        singletons=2,
        doubletons=1,
        chao1_estimate=7.0,
        source_sample_coverage=0.6,
        execution_time_s=12.5,
    )


@pytest.fixture
def sample_taxonomy() -> TaxonomyTree:
    """A small taxonomy tree with nested nodes."""
    return TaxonomyTree(
        domain_name="fintech",
        version=1,
        status=TopicDiscoveryStatus.approved,
        root_nodes=[
            SubdomainNode(
                name="Expense Management",
                depth=0,
                source_provenance={"source_a": True, "source_b": True},
                confidence=1.0,
                children=[
                    SubdomainNode(
                        name="Receipt Scanning",
                        depth=1,
                        source_provenance={"source_a": True},
                        confidence=0.5,
                    ),
                    SubdomainNode(
                        name="Policy Enforcement",
                        depth=1,
                        source_provenance={"source_b": True, "source_d": True},
                        confidence=0.75,
                    ),
                ],
            ),
            SubdomainNode(
                name="Corporate Cards",
                depth=0,
                source_provenance={"source_a": True, "source_c": True},
                confidence=0.75,
            ),
        ],
        total_subdomains=4,
        max_depth=1,
        coverage_score=0.92,
        chao1_estimate=5.0,
    )


@pytest.fixture
def sample_matrix() -> TopicAssignmentMatrix:
    """A small topic assignment matrix."""
    return TopicAssignmentMatrix(
        version=1,
        status=TopicDiscoveryStatus.approved,
        assignments=[
            TopicAssignment(
                subdomain_name="Expense Management",
                topic_text="Best expense management tools for startups",
                buyer_stage=BuyerStage.TOFU,
                intent_type=IntentType.informational,
                audience_segment="CFO",
                audience_segment_type=AudienceSegmentType.individual_persona,
                relevance=RelevanceCell.relevant,
                priority_score=0.85,
            ),
            TopicAssignment(
                subdomain_name="Corporate Cards",
                topic_text="How to choose a corporate card program",
                buyer_stage=BuyerStage.MOFU,
                intent_type=IntentType.commercial,
                audience_segment="Finance Team",
                audience_segment_type=AudienceSegmentType.team_group,
                relevance=RelevanceCell.relevant,
                priority_score=0.72,
            ),
        ],
        total_assignments=2,
        total_relevant_cells=2,
        total_irrelevant_cells=3,
    )
