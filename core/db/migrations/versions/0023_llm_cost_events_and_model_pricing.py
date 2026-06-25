"""Add llm_cost_events and model_pricing tables for cost analytics.

Revision ID: 0023
Revises: 0022
Create Date: 2026-04-01
"""
from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID

revision: str = "0023"
down_revision: str = "0022"
branch_labels: str | None = None
depends_on: str | None = None

# Default pricing to seed model_pricing table (model, input_cost_per_1m, output_cost_per_1m)
_SEED_PRICING = [
    ("claude-sonnet-4-6", 3.00, 15.00),
    ("claude-opus-4-6", 15.00, 75.00),
    ("claude-haiku-4-5", 0.80, 4.00),
    ("gpt-5.2", 2.00, 8.00),
    ("o1", 15.00, 60.00),
    ("o3-mini", 1.10, 4.40),
    ("gemini-3-flash-preview", 0.10, 0.40),
    ("gemini-2.5-pro", 1.25, 10.00),
    ("sonar-pro", 3.00, 15.00),
    ("sonar-deep-research", 2.00, 8.00),
    ("text-embedding-3-small", 0.02, 0.0),
    ("text-embedding-3-large", 0.13, 0.0),
]


def upgrade() -> None:
    # ── llm_cost_events ──────────────────────────────────────────────
    op.create_table(
        "llm_cost_events",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("pipeline", sa.String(), nullable=False),
        sa.Column("pipeline_step", sa.String(), nullable=False, server_default=""),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("company_slug", sa.String(), nullable=False, server_default=""),
        sa.Column("call_site", sa.String(), nullable=False, server_default=""),
        sa.Column("source", sa.String(), nullable=False, server_default="native"),
        sa.Column("run_id", PgUUID(as_uuid=True), sa.ForeignKey("pipeline_runs.id"), nullable=True),
        sa.Column("extra_json", JSONB(), nullable=True),
    )
    op.create_index("ix_llm_cost_events_event_time", "llm_cost_events", ["event_time"])
    op.create_index("ix_llm_cost_events_model_time", "llm_cost_events", ["model", "event_time"])
    op.create_index("ix_llm_cost_events_pipeline_time", "llm_cost_events", ["pipeline", "event_time"])
    op.create_index(
        "ix_llm_cost_events_run_id", "llm_cost_events", ["run_id"],
        postgresql_where=sa.text("run_id IS NOT NULL"),
    )
    op.create_index("ix_llm_cost_events_slug_time", "llm_cost_events", ["company_slug", "event_time"])

    # ── model_pricing ────────────────────────────────────────────────
    op.create_table(
        "model_pricing",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("model_name", sa.String(), nullable=False, unique=True),
        sa.Column("input_cost_per_1m", sa.Float(), nullable=False),
        sa.Column("output_cost_per_1m", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("uq_model_pricing_model_name", "model_pricing", ["model_name"], unique=True)

    # Seed default pricing
    pricing_table = sa.table(
        "model_pricing",
        sa.column("id", PgUUID(as_uuid=True)),
        sa.column("model_name", sa.String()),
        sa.column("input_cost_per_1m", sa.Float()),
        sa.column("output_cost_per_1m", sa.Float()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(
        pricing_table,
        [
            {
                "id": uuid.uuid4(),
                "model_name": name,
                "input_cost_per_1m": inp,
                "output_cost_per_1m": out,
                "is_active": True,
            }
            for name, inp, out in _SEED_PRICING
        ],
    )


def downgrade() -> None:
    op.drop_table("llm_cost_events")
    op.drop_table("model_pricing")
