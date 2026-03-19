"""Artifact writer — writes content to StorageBackend + persists DB metadata.

Filesystem-first, DB-additive: storage write always happens first, DB write
is optional and fails gracefully. Each DB write opens its own session from
the factory to avoid shared-session races in concurrent workers.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

from core.db.enums import ContentArtifactStage
from core.storage.backends.base import StorageBackend

logger = logging.getLogger(__name__)


async def persist_stage_artifact(
    *,
    storage: StorageBackend,
    session_factory: Optional[async_sessionmaker],
    piece_id: Optional[uuid.UUID],
    stage: ContentArtifactStage,
    relative_path: str,
    content: str,
    content_type: str = "text/markdown",
) -> str:
    """Write content to storage, then record metadata in DB.

    Args:
        storage: StorageBackend instance (LocalStorageBackend or future S3).
        session_factory: SQLAlchemy async session factory. None = skip DB.
        piece_id: ContentPieceModel.id. None = skip DB.
        stage: Which pipeline stage produced this artifact.
        relative_path: Path relative to storage root (e.g. "content/ramp/content/brief-001/outline.json").
        content: The artifact content (text or JSON string).
        content_type: MIME type ("text/markdown" or "application/json").

    Returns:
        The storage_key (relative_path as written by the backend).
    """
    # 1. Write via StorageBackend (filesystem-first, always succeeds or raises)
    storage_key = storage.write(relative_path, content)

    # 2. Compute metadata
    content_bytes = content.encode("utf-8")
    size_bytes = len(content_bytes)
    word_count = len(content.split()) if "markdown" in content_type else None
    checksum = hashlib.sha256(content_bytes).hexdigest()

    # 3. Persist to DB (each call opens its OWN session — safe for concurrent workers)
    if session_factory is not None and piece_id is not None:
        try:
            from core.db.repositories.content_artifact_repo import (
                ContentArtifactRepository,
            )

            async with session_factory() as session:
                repo = ContentArtifactRepository(session)
                await repo.upsert_artifact(
                    piece_id=piece_id,
                    stage=stage,
                    storage_key=storage_key,
                    content_type=content_type,
                    size_bytes=size_bytes,
                    word_count=word_count,
                    checksum=checksum,
                )
                await session.commit()
        except Exception:
            logger.warning(
                "persist_stage_artifact: DB write failed for piece=%s stage=%s "
                "— artifact is on storage at %s",
                piece_id,
                stage.value,
                storage_key,
                exc_info=True,
            )

    return storage_key
