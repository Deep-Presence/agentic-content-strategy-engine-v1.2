"""Tests for TopicDiscoveryRepository and related repositories.

These tests require a running Postgres database (DATABASE_URL env var).
They are automatically skipped in CI / local runs without a DB.
"""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set — skipping DB tests",
)


# These tests serve as structural verification that repository imports
# and class definitions are correct. Full DB integration tests require
# a live Postgres instance.


def test_repository_imports():
    """Verify all repository classes can be imported."""
    from core.topic_discovery.repository import (
        TopicDiscoveryRepository,
        TaxonomyTreeRepository,
        SubdomainNodeRepository,
        TopicAssignmentRepository,
    )
    assert TopicDiscoveryRepository.model_class is not None
    assert TaxonomyTreeRepository.model_class is not None
    assert SubdomainNodeRepository.model_class is not None
    assert TopicAssignmentRepository.model_class is not None


def test_repository_model_class_binding():
    """Each repo must bind to the correct ORM model."""
    from core.db.models.topic_discovery import (
        TopicDiscoveryModel,
        TaxonomyTreeModel,
        SubdomainNodeModel,
        TopicAssignmentModel,
    )
    from core.topic_discovery.repository import (
        TopicDiscoveryRepository,
        TaxonomyTreeRepository,
        SubdomainNodeRepository,
        TopicAssignmentRepository,
    )
    assert TopicDiscoveryRepository.model_class is TopicDiscoveryModel
    assert TaxonomyTreeRepository.model_class is TaxonomyTreeModel
    assert SubdomainNodeRepository.model_class is SubdomainNodeModel
    assert TopicAssignmentRepository.model_class is TopicAssignmentModel
