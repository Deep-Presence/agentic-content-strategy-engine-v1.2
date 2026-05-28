"""Data retention cleanup for the Daily Tracker pipeline.

Clears raw LLM response text from ``daily_run_responses`` after a
configurable retention period (default 30 days).  All metric columns
(brand_mentioned, competitor_mentions, citations, etc.) are preserved
for trend analytics.

Uses empty string ``''`` (not NULL) because the ``response_text``
column is ``NOT NULL`` with ``server_default=''``.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import async_sessionmaker

logger = logging.getLogger(__name__)


async def cleanup_old_response_text(
    session_factory: Optional[async_sessionmaker],
    retention_days: int = 30,
) -> int:
    """Clear response_text for responses older than retention_days.

    Sets ``response_text = ''`` where ``created_at < cutoff`` and the
    text has not already been cleared.  Preserves all metric columns
    for trend analytics.

    Args:
        session_factory: Async session factory (None = no-op).
        retention_days: Days to retain response text (default 30).

    Returns:
        Number of rows updated.  Returns 0 if session_factory is None.
    """
    if session_factory is None:
        logger.warning("cleanup_old_response_text: no session_factory, skipping")
        return 0

    try:
        # Lazy import to avoid circular deps
        from core.db.models.daily_tracker import DailyRunResponseModel

        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

        async with session_factory() as session:
            stmt = (
                sa_update(DailyRunResponseModel)
                .where(
                    DailyRunResponseModel.created_at < cutoff,
                    DailyRunResponseModel.response_text != "",
                )
                .values(response_text="")
            )
            result = await session.execute(stmt)
            row_count: int = result.rowcount  # type: ignore[assignment]
            await session.commit()

        logger.info(
            "cleanup_old_response_text: cleared %d rows older than %d days "
            "(cutoff=%s)",
            row_count,
            retention_days,
            cutoff.isoformat(),
        )
        return row_count

    except Exception:
        logger.warning(
            "cleanup_old_response_text failed (retention_days=%d)",
            retention_days,
            exc_info=True,
        )
        return 0
