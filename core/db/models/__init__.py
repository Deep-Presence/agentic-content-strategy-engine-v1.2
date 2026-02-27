"""ORM model registry — import all modules to register metadata with Base."""
from core.db.models import (  # noqa: F401
    api_tasks,
    cache,
    content,
    embeddings,
    gap_analysis,
    knowledge_docs,
    organization,
    pipelines,
    site_audit,
    topic_discovery,
    tracking,
)
