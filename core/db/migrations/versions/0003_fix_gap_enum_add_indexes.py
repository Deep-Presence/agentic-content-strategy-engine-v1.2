"""Fix gap_classification_enum values to match s6 pipeline output + add composite indexes.

The original enum (0001) had placeholder values: large_gap, moderate_gap, small_gap,
no_gap, already_cited.  The actual s6_analyze.py pipeline produces: significant_gap,
gap_to_close, roughly_equal, company_wins.  This migration renames the enum values
to match reality and adds a 5th value ``no_data`` for edge cases.

Also adds composite indexes on pipeline_runs for the run-history and slug-resolution
queries used by the Phase 3 service layer.

Revision ID: 0003
Revises: 0002
Create Date: 2026-02-28
"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str = "0002"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ── Rename gap_classification_enum values to match s6 pipeline output ──
    op.execute("ALTER TYPE gap_classification_enum RENAME VALUE 'large_gap' TO 'significant_gap'")
    op.execute("ALTER TYPE gap_classification_enum RENAME VALUE 'moderate_gap' TO 'gap_to_close'")
    op.execute("ALTER TYPE gap_classification_enum RENAME VALUE 'small_gap' TO 'roughly_equal'")
    op.execute("ALTER TYPE gap_classification_enum RENAME VALUE 'no_gap' TO 'company_wins'")
    op.execute("ALTER TYPE gap_classification_enum RENAME VALUE 'already_cited' TO 'no_data'")

    # ── Composite indexes for Phase 3 service layer queries ────────────────

    # Run history: WHERE effective_slug = :slug ORDER BY created_at DESC
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_pipeline_runs_slug_created "
        "ON pipeline_runs (effective_slug, created_at DESC)"
    )

    # Slug resolution: WHERE effective_slug = :slug AND status = 'completed'
    # AND pipeline_type = :type ORDER BY completed_at DESC LIMIT 1
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_pipeline_runs_slug_type_status "
        "ON pipeline_runs (effective_slug, pipeline_type, status, completed_at DESC)"
    )

    # Gap queries by run + classification (used by get_gaps_by_run with filter)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_query_gaps_run_classification "
        "ON query_gaps (run_id, classification)"
    )

    # Run citations by run (used by signal aggregation queries)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_run_citations_run_id "
        "ON run_citations (run_id)"
    )


def downgrade() -> None:
    # ── Drop indexes ──────────────────────────────────────────────────────
    op.execute("DROP INDEX IF EXISTS ix_run_citations_run_id")
    op.execute("DROP INDEX IF EXISTS ix_query_gaps_run_classification")
    op.execute("DROP INDEX IF EXISTS ix_pipeline_runs_slug_type_status")
    op.execute("DROP INDEX IF EXISTS ix_pipeline_runs_slug_created")

    # ── Revert enum values ────────────────────────────────────────────────
    op.execute("ALTER TYPE gap_classification_enum RENAME VALUE 'no_data' TO 'already_cited'")
    op.execute("ALTER TYPE gap_classification_enum RENAME VALUE 'company_wins' TO 'no_gap'")
    op.execute("ALTER TYPE gap_classification_enum RENAME VALUE 'roughly_equal' TO 'small_gap'")
    op.execute("ALTER TYPE gap_classification_enum RENAME VALUE 'gap_to_close' TO 'moderate_gap'")
    op.execute("ALTER TYPE gap_classification_enum RENAME VALUE 'significant_gap' TO 'large_gap'")
