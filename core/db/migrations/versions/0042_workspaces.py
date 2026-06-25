"""Add workspaces and workspace_memberships tenant tables.

Backfills one workspace per existing company and one active membership per user
from users.company_id + users.role.

Revision ID: 0042
Revises: 0041
Create Date: 2026-06-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0042"
down_revision: str = "0041"
branch_labels: str | None = None
depends_on: str | None = None


def _map_user_role_to_workspace_role(role: str) -> str:
    if role == "superuser":
        return "owner"
    if role == "viewer":
        return "viewer"
    return "member"


def upgrade() -> None:
    workspace_role_enum = postgresql.ENUM(
        "owner",
        "admin",
        "member",
        "viewer",
        name="workspace_role_enum",
        create_type=False,
    )
    membership_status_enum = postgresql.ENUM(
        "active",
        "invited",
        "suspended",
        name="membership_status_enum",
        create_type=False,
    )

    bind = op.get_bind()
    workspace_role_enum.create(bind, checkfirst=True)
    membership_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("primary_domain", sa.String(), nullable=False),
        sa.Column("additional_domains", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("industry", sa.String(), nullable=True),
        sa.Column(
            "color",
            sa.String(length=32),
            nullable=False,
            server_default="#5BA4C4",
        ),
        sa.Column("logo_url", sa.String(), nullable=True),
        sa.Column("avatar_key", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("settings_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "is_archived",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_workspaces_company_id", "workspaces", ["company_id"])
    op.create_index("ix_workspaces_slug", "workspaces", ["slug"])

    op.create_table(
        "workspace_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "role",
            workspace_role_enum,
            nullable=False,
            server_default="member",
        ),
        sa.Column(
            "status",
            membership_status_enum,
            nullable=False,
            server_default="active",
        ),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "user_id",
            name="uq_workspace_memberships_workspace_user",
        ),
    )
    op.create_index(
        "ix_workspace_memberships_user_id",
        "workspace_memberships",
        ["user_id"],
    )
    op.create_index(
        "ix_workspace_memberships_workspace_id",
        "workspace_memberships",
        ["workspace_id"],
    )

    conn = op.get_bind()

    companies = conn.execute(
        sa.text(
            """
            SELECT id, slug, name, domain, additional_domains, industry, is_archived,
                   created_at, updated_at
            FROM companies
            """
        )
    ).fetchall()

    for row in companies:
        conn.execute(
            sa.text(
                """
                INSERT INTO workspaces (
                    id, company_id, slug, name, primary_domain, additional_domains,
                    industry, is_archived, created_at, updated_at
                ) VALUES (
                    :id, :company_id, :slug, :name, :primary_domain, :additional_domains,
                    :industry, :is_archived, :created_at, :updated_at
                )
                """
            ),
            {
                "id": row.id,
                "company_id": row.id,
                "slug": row.slug,
                "name": row.name,
                "primary_domain": row.domain,
                "additional_domains": row.additional_domains,
                "industry": row.industry,
                "is_archived": row.is_archived,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            },
        )

    users = conn.execute(
        sa.text("SELECT id, company_id, role, created_at, updated_at FROM users")
    ).fetchall()

    for user in users:
        workspace_id = user.company_id
        role = _map_user_role_to_workspace_role(str(user.role))
        conn.execute(
            sa.text(
                """
                INSERT INTO workspace_memberships (
                    id, workspace_id, user_id, role, status, joined_at,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid(), :workspace_id, :user_id, :role, 'active',
                    :joined_at, :created_at, :updated_at
                )
                """
            ),
            {
                "workspace_id": workspace_id,
                "user_id": user.id,
                "role": role,
                "joined_at": user.created_at,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
            },
        )


def downgrade() -> None:
    op.drop_index("ix_workspace_memberships_workspace_id", table_name="workspace_memberships")
    op.drop_index("ix_workspace_memberships_user_id", table_name="workspace_memberships")
    op.drop_table("workspace_memberships")
    op.drop_index("ix_workspaces_slug", table_name="workspaces")
    op.drop_index("ix_workspaces_company_id", table_name="workspaces")
    op.drop_table("workspaces")

    bind = op.get_bind()
    sa.Enum(name="membership_status_enum").drop(bind, checkfirst=True)
    sa.Enum(name="workspace_role_enum").drop(bind, checkfirst=True)
