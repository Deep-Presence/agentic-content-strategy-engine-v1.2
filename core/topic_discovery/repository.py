"""Re-export from canonical location for backward compatibility.

All repository classes now live in ``core.db.repositories.topic_discovery_repo``.
"""
from core.db.repositories.topic_discovery_repo import (  # noqa: F401
    PersonaAffinityRepository,
    SourceResultRepository,
    SubdomainNodeRepository,
    TaxonomyTreeRepository,
    TopicAssignmentCannibalizationRepository,
    TopicAssignmentRepository,
    TopicDiscoveryRepository,
)

__all__ = [
    "TopicDiscoveryRepository",
    "TaxonomyTreeRepository",
    "SubdomainNodeRepository",
    "TopicAssignmentRepository",
    "TopicAssignmentCannibalizationRepository",
    "SourceResultRepository",
    "PersonaAffinityRepository",
]
