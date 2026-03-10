"""Evolve topic discovery schema for the Topic Discovery Module.

- Create 6 new PG ENUMs for topic discovery
- ALTER topic_discoveries: add domain_name, effective_slug, taxonomy/matrix
  version columns, change status from pipeline_status_enum to td_status_enum
- DROP discovered_topics (replaced by subdomain_nodes + topic_assignments)
- CREATE taxonomy_trees, subdomain_nodes, topic_assignments

Hand-written migration following project convention.

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-08
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

# New enum types
td_status_enum = sa.Enum(
    "draft", "hitl_pending", "approved", "archived",
    name="td_status_enum",
)
buyer_stage_enum = sa.Enum(
    "tofu", "mofu", "bofu",
    name="buyer_stage_enum",
)
intent_type_enum = sa.Enum(
    "informational", "commercial", "navigational", "transactional",
    name="intent_type_enum",
)
audience_segment_type_enum = sa.Enum(
    "individual_persona", "team_group",
    name="audience_segment_type_enum",
)
relevance_cell_enum = sa.Enum(
    "relevant", "marginal", "irrelevant",
    name="relevance_cell_enum",
)
topic_assignment_status_enum = sa.Enum(
    "not_started", "in_gap_analysis", "content_produced", "published",
    name="topic_assignment_status_enum",
)


def upgrade() -> None:
    # ── 1. Create new enum types ─────────────────────────────────────
    td_status_enum.create(op.get_bind(), checkfirst=True)
    buyer_stage_enum.create(op.get_bind(), checkfirst=True)
    intent_type_enum.create(op.get_bind(), checkfirst=True)
    audience_segment_type_enum.create(op.get_bind(), checkfirst=True)
    relevance_cell_enum.create(op.get_bind(), checkfirst=True)
    topic_assignment_status_enum.create(op.get_bind(), checkfirst=True)

    # ── 2. ALTER topic_discoveries ───────────────────────────────────
    op.add_column(
        "topic_discoveries",
        sa.Column("domain_name", sa.String, nullable=True),
    )
    op.add_column(
        "topic_discoveries",
        sa.Column("effective_slug", sa.String, nullable=True),
    )
    op.add_column(
        "topic_discoveries",
        sa.Column("taxonomy_version", sa.Integer, nullable=False, server_default="0"),
    )
    op.add_column(
        "topic_discoveries",
        sa.Column("matrix_version", sa.Integer, nullable=False, server_default="0"),
    )
    op.add_column(
        "topic_discoveries",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Change status column from pipeline_status_enum → td_status_enum
    op.execute(
        "ALTER TABLE topic_discoveries "
        "ALTER COLUMN status TYPE td_status_enum "
        "USING CASE status::text "
        "  WHEN 'pending' THEN 'draft'::td_status_enum "
        "  WHEN 'running' THEN 'draft'::td_status_enum "
        "  WHEN 'completed' THEN 'approved'::td_status_enum "
        "  WHEN 'failed' THEN 'draft'::td_status_enum "
        "  WHEN 'cancelled' THEN 'archived'::td_status_enum "
        "  ELSE 'draft'::td_status_enum "
        "END"
    )
    op.execute(
        "ALTER TABLE topic_discoveries "
        "ALTER COLUMN status SET DEFAULT 'draft'::td_status_enum"
    )
    op.create_index(
        "ix_topic_discoveries_effective_slug",
        "topic_discoveries",
        ["effective_slug"],
    )

    # ── 3. DROP discovered_topics ────────────────────────────────────
    op.drop_index("ix_discovered_topics_discovery", table_name="discovered_topics")
    op.drop_table("discovered_topics")

    # ── 4. CREATE taxonomy_trees ─────────────────────────────────────
    op.create_table(
        "taxonomy_trees",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "discovery_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("topic_discoveries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("total_subdomains", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_depth", sa.Integer, nullable=False, server_default="0"),
        sa.Column("coverage_score", sa.Float, nullable=True),
        sa.Column("chao1_estimate", sa.Float, nullable=True),
        sa.Column("capture_recapture_est", postgresql.JSONB, nullable=True),
        sa.Column("tree_json", postgresql.JSONB, nullable=True),
        sa.Column(
            "status",
            td_status_enum,
            server_default="draft",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_taxonomy_trees_discovery", "taxonomy_trees", ["discovery_id"]
    )

    # ── 5. CREATE subdomain_nodes ────────────────────────────────────
    op.create_table(
        "subdomain_nodes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "taxonomy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy_trees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("subdomain_nodes.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("depth", sa.Integer, nullable=False, server_default="0"),
        sa.Column("source_provenance", postgresql.JSONB, nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("is_manually_added", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("metadata_json", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_subdomain_nodes_taxonomy", "subdomain_nodes", ["taxonomy_id"]
    )
    op.create_index(
        "ix_subdomain_nodes_parent", "subdomain_nodes", ["parent_id"]
    )

    # ── 6. CREATE topic_assignments ──────────────────────────────────
    op.create_table(
        "topic_assignments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "discovery_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("topic_discoveries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("matrix_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "subdomain_node_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("subdomain_nodes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("topic_text", sa.Text, nullable=False),
        sa.Column(
            "buyer_stage",
            buyer_stage_enum,
            server_default="tofu",
        ),
        sa.Column(
            "intent_type",
            intent_type_enum,
            server_default="informational",
        ),
        sa.Column("audience_segment", sa.String, nullable=True),
        sa.Column(
            "audience_segment_type",
            audience_segment_type_enum,
            server_default="individual_persona",
        ),
        sa.Column(
            "relevance",
            relevance_cell_enum,
            server_default="relevant",
        ),
        sa.Column("priority_score", sa.Float, nullable=True),
        sa.Column("priority_factors", postgresql.JSONB, nullable=True),
        sa.Column(
            "status",
            topic_assignment_status_enum,
            server_default="not_started",
        ),
        sa.Column("is_manually_added", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("metadata_json", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_topic_assignments_discovery", "topic_assignments", ["discovery_id"]
    )
    op.create_index(
        "ix_topic_assignments_subdomain",
        "topic_assignments",
        ["subdomain_node_id"],
    )


def downgrade() -> None:
    # Drop new tables
    op.drop_index("ix_topic_assignments_subdomain", table_name="topic_assignments")
    op.drop_index("ix_topic_assignments_discovery", table_name="topic_assignments")
    op.drop_table("topic_assignments")

    op.drop_index("ix_subdomain_nodes_parent", table_name="subdomain_nodes")
    op.drop_index("ix_subdomain_nodes_taxonomy", table_name="subdomain_nodes")
    op.drop_table("subdomain_nodes")

    op.drop_index("ix_taxonomy_trees_discovery", table_name="taxonomy_trees")
    op.drop_table("taxonomy_trees")

    # Restore discovered_topics
    op.create_table(
        "discovered_topics",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "discovery_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("topic_discoveries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("topic_text", sa.Text, nullable=False),
        sa.Column("relevance_score", sa.Float, nullable=True),
        sa.Column("cluster_id", sa.String, nullable=True),
        sa.Column("buyer_stage", sa.String, nullable=True),
        sa.Column("metadata_json", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_discovered_topics_discovery", "discovered_topics", ["discovery_id"]
    )

    # Revert topic_discoveries ALTER
    op.drop_index(
        "ix_topic_discoveries_effective_slug", table_name="topic_discoveries"
    )
    op.execute(
        "ALTER TABLE topic_discoveries "
        "ALTER COLUMN status TYPE pipeline_status_enum "
        "USING 'pending'::pipeline_status_enum"
    )
    op.execute(
        "ALTER TABLE topic_discoveries "
        "ALTER COLUMN status SET DEFAULT 'pending'::pipeline_status_enum"
    )
    op.drop_column("topic_discoveries", "updated_at")
    op.drop_column("topic_discoveries", "matrix_version")
    op.drop_column("topic_discoveries", "taxonomy_version")
    op.drop_column("topic_discoveries", "effective_slug")
    op.drop_column("topic_discoveries", "domain_name")

    # Drop new enum types
    topic_assignment_status_enum.drop(op.get_bind(), checkfirst=True)
    relevance_cell_enum.drop(op.get_bind(), checkfirst=True)
    audience_segment_type_enum.drop(op.get_bind(), checkfirst=True)
    intent_type_enum.drop(op.get_bind(), checkfirst=True)
    buyer_stage_enum.drop(op.get_bind(), checkfirst=True)
    td_status_enum.drop(op.get_bind(), checkfirst=True)
