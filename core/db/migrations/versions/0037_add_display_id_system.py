"""Add universal display ID system for topic assignments.

Adds human-readable, globally-unique-per-company display IDs (e.g., "WE-001",
"IH-042") that persist from Topic Discovery through Content Engine.

Schema changes:
- companies: add display_id_prefix (VARCHAR 10), display_id_counter (INTEGER)
- topic_assignments: add display_id (VARCHAR 20, indexed)

Data migration:
- Derive prefix from company name (multi-word → initials, single → first 2 chars)
- Backfill existing assignments ordered by created_at with sequential display IDs
- Set display_id_counter to the max assigned number per company

Revision ID: 0037
Revises: 0036
Create Date: 2026-04-08
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0037"
down_revision: str = "0036"
branch_labels: str | None = None
depends_on: str | None = None


def _derive_prefix(company_name: str) -> str:
    """Derive display ID prefix from company name (mirrors core/topic_discovery/display_id.py)."""
    words = company_name.strip().split()
    words = [w for w in words if w]
    if not words:
        return "DP"
    if len(words) == 1:
        raw = words[0][:2].upper()
    else:
        raw = "".join(w[0] for w in words).upper()
    return raw[:10]  # Clamp to fit String(10) column


def upgrade() -> None:
    # 1. Add columns to companies
    op.add_column(
        "companies",
        sa.Column("display_id_prefix", sa.String(10), nullable=True),
    )
    op.add_column(
        "companies",
        sa.Column(
            "display_id_counter",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    # 2. Add display_id column to topic_assignments
    op.add_column(
        "topic_assignments",
        sa.Column("display_id", sa.String(20), nullable=True),
    )
    op.create_index(
        "ix_topic_assignments_display_id",
        "topic_assignments",
        ["display_id"],
    )

    # 3. Backfill existing data
    conn = op.get_bind()

    # Get all companies
    companies = conn.execute(
        sa.text("SELECT id, name FROM companies")
    ).fetchall()

    for company_id, company_name in companies:
        prefix = _derive_prefix(company_name or "")

        # Set prefix on company
        conn.execute(
            sa.text(
                "UPDATE companies SET display_id_prefix = :prefix WHERE id = :cid"
            ),
            {"prefix": prefix, "cid": company_id},
        )

        # Get all assignments for this company (via topic_discoveries FK),
        # ordered by created_at for stable numbering
        assignments = conn.execute(
            sa.text("""
                SELECT ta.id
                FROM topic_assignments ta
                JOIN topic_discoveries td ON ta.discovery_id = td.id
                WHERE td.company_id = :cid
                ORDER BY ta.created_at ASC, ta.id ASC
            """),
            {"cid": company_id},
        ).fetchall()

        if not assignments:
            continue

        # Assign sequential display IDs
        for idx, (assignment_id,) in enumerate(assignments, start=1):
            display_id = f"{prefix}-{idx:03d}"
            conn.execute(
                sa.text(
                    "UPDATE topic_assignments SET display_id = :did WHERE id = :aid"
                ),
                {"did": display_id, "aid": assignment_id},
            )

        # Update company counter
        conn.execute(
            sa.text(
                "UPDATE companies SET display_id_counter = :cnt WHERE id = :cid"
            ),
            {"cnt": len(assignments), "cid": company_id},
        )


def downgrade() -> None:
    op.drop_index("ix_topic_assignments_display_id", table_name="topic_assignments")
    op.drop_column("topic_assignments", "display_id")
    op.drop_column("companies", "display_id_counter")
    op.drop_column("companies", "display_id_prefix")
