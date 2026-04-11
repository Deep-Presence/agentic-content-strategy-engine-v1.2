"""Display ID generation for topic assignments.

Generates human-readable, globally-unique-per-company display IDs
(e.g., "WE-001", "IH-042") that persist across the full topic lifecycle:
Topic Discovery → Gap Analysis → Content Engine → Content Studio.

Design:
- Counter stored on ``companies`` table (``display_id_counter``, ``display_id_prefix``).
- ``SELECT FOR UPDATE`` on companies row prevents duplicate IDs under concurrency.
- ``backfill_display_ids()`` is the main entry point — called after every bulk write.
- Gap-tolerant (Linear-style): deleted/rejected assignments never reuse IDs.
"""
from __future__ import annotations

import logging
import uuid as _uuid
from typing import List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def derive_prefix(company_name: str) -> str:
    """Derive a short prefix from the company name for human-readable IDs.

    Mirrors the frontend ``deriveCompanyPrefix()`` logic:
    - Multi-word → initials (e.g., "Insight Health" → "IH")
    - Single word → first two letters uppercased (e.g., "Webflow" → "WE")
    - Fallback → "DP" (Deep Presence)
    """
    words = company_name.strip().split()
    words = [w for w in words if w]  # filter empty
    if not words:
        return "DP"
    if len(words) == 1:
        raw = words[0][:2].upper()
    else:
        raw = "".join(w[0] for w in words).upper()
    # Clamp to 10 chars to fit String(10) column on companies table
    return raw[:10]


async def allocate_display_ids(
    session: AsyncSession,
    company_id: _uuid.UUID,
    count: int,
) -> List[str]:
    """Atomically allocate ``count`` display IDs for a company.

    Uses ``SELECT FOR UPDATE`` on the companies row to serialize
    concurrent allocation and prevent gaps or duplicates.

    Args:
        session: Active async session (caller manages transaction).
        company_id: UUID of the company.
        count: Number of IDs to allocate.

    Returns:
        List of display IDs like ``["WE-042", "WE-043"]``.

    Raises:
        ValueError: If the company row is not found.
    """
    if count <= 0:
        return []

    from core.db.models.organization import CompanyModel

    result = await session.execute(
        select(CompanyModel)
        .where(CompanyModel.id == company_id)
        .with_for_update()
    )
    company = result.scalar_one_or_none()
    if company is None:
        raise ValueError(f"Company {company_id} not found")

    prefix = company.display_id_prefix or derive_prefix(company.name or "")
    start = company.display_id_counter + 1
    ids = [f"{prefix}-{start + i:03d}" for i in range(count)]

    company.display_id_counter = start + count - 1
    if not company.display_id_prefix:
        company.display_id_prefix = prefix
    await session.flush()

    return ids


async def backfill_display_ids(
    session: AsyncSession,
    company_id: _uuid.UUID,
    discovery_id: _uuid.UUID,
) -> int:
    """Assign display IDs to assignments that have ``display_id IS NULL``.

    Called after bulk write operations (``db_write_matrix``,
    ``db_write_assignments_for_subdomain``, ``create_assignment``).
    Only assigns to NULL rows, preserving existing display IDs that
    were carried through the Pydantic model during delete+insert cycles.

    Args:
        session: Active async session (caller manages transaction).
        company_id: UUID of the company (for counter lookup).
        discovery_id: Filter assignments to this discovery.

    Returns:
        Count of newly assigned display IDs.
    """
    from core.db.models.topic_discovery import TopicAssignmentModel

    result = await session.execute(
        select(TopicAssignmentModel)
        .where(
            TopicAssignmentModel.discovery_id == discovery_id,
            TopicAssignmentModel.display_id.is_(None),
        )
        .order_by(TopicAssignmentModel.created_at)
    )
    assignments: Sequence[TopicAssignmentModel] = result.scalars().all()
    if not assignments:
        return 0

    ids = await allocate_display_ids(session, company_id, len(assignments))
    for assignment, display_id in zip(assignments, ids):
        assignment.display_id = display_id
    await session.flush()

    logger.info(
        "backfill_display_ids: assigned %d IDs for discovery %s (company %s)",
        len(ids), discovery_id, company_id,
    )
    return len(assignments)
