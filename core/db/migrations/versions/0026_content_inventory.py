"""Content Inventory — universal CMS-agnostic content registry.

New table:
  content_inventory — canonical registry of all known published content pages
                      per company. Deduplicated on (company_id, url_normalized).

New enum type:
  content_ingestion_source_enum

Schema changes:
  cms_synced_posts — adds nullable FK content_inventory_id → content_inventory.id

Indexes:
  HNSW index on content_inventory.embedding for pgvector similarity queries.

Revision ID: 0026
Revises: 0025
Create Date: 2026-04-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ENUM as PgENUM
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision: str = "0026"
down_revision: str = "0025"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ── 1. Create enum type (idempotent) ─────────────────────────

    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE content_ingestion_source_enum AS ENUM "
        "('site_audit_crawl', 'cms_sync', 'csv_import', 'content_engine', 'manual'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; "
        "END $$"
    )

    # ── 2. Create content_inventory table ────────────────────────

    op.create_table(
        "content_inventory",
        # PK
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        # Timestamps (matching TimestampMixin)
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # Company scope
        sa.Column(
            "company_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("effective_slug", sa.String, nullable=False),
        # Page identity
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column(
            "url_normalized",
            sa.String(2048),
            nullable=False,
            comment="Lowercase, no trailing slash, no fragment, no query params. Dedup key.",
        ),
        sa.Column("slug", sa.String(512), server_default=""),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("h1_text", sa.String(512), server_default=""),
        sa.Column("meta_description", sa.Text, server_default=""),
        # Content summary
        sa.Column(
            "content_preview",
            sa.Text,
            server_default="",
            comment="First ~500 chars of plaintext content, HTML stripped.",
        ),
        sa.Column("word_count", sa.Integer, server_default="0"),
        # Taxonomy / classification
        sa.Column("categories", JSONB, nullable=True),
        sa.Column("tags", JSONB, nullable=True),
        sa.Column(
            "detected_primary_topic",
            sa.String(255),
            server_default="",
            comment="LLM-detected or keyword-extracted primary topic. Populated async.",
        ),
        # SEO metadata
        sa.Column("seo_title", sa.String(512), server_default=""),
        sa.Column("seo_description", sa.Text, server_default=""),
        # Timestamps
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "content_modified_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last modified date from CMS or sitemap lastmod.",
        ),
        sa.Column(
            "last_crawled_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When we last fetched/verified this page.",
        ),
        # Embedding
        sa.Column(
            "embedding",
            Vector(1536),
            nullable=True,
            comment="Page-level embedding of title + content_preview. For cannibalization similarity.",
        ),
        # Ingestion provenance
        sa.Column(
            "ingestion_source",
            PgENUM(name="content_ingestion_source_enum", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "ingestion_run_id",
            PgUUID(as_uuid=True),
            nullable=True,
            comment="pipeline_runs.id that discovered this page.",
        ),
        # Structural signals
        sa.Column("has_faq_section", sa.Boolean, server_default="false"),
        sa.Column("has_schema_markup", sa.Boolean, server_default="false"),
        sa.Column("heading_count", sa.Integer, server_default="0"),
        sa.Column(
            "content_type_detected",
            sa.String(50),
            server_default="",
            comment="blog_post, landing_page, docs, glossary, etc.",
        ),
        # Cannibalization analysis
        sa.Column(
            "cannibalization_cluster_id",
            sa.String(255),
            server_default="",
            comment="Cluster label if this page was grouped with similar inventory pages.",
        ),
    )

    # ── 3. Create indexes ────────────────────────────────────────

    op.create_index(
        "uq_content_inventory_company_url",
        "content_inventory",
        ["company_id", "url_normalized"],
        unique=True,
    )
    op.create_index(
        "ix_content_inv_company",
        "content_inventory",
        ["company_id"],
    )
    op.create_index(
        "ix_content_inv_company_source",
        "content_inventory",
        ["company_id", "ingestion_source"],
    )
    op.create_index(
        "ix_content_inv_effective_slug",
        "content_inventory",
        ["effective_slug"],
    )

    # ── 4. HNSW index for pgvector similarity ────────────────────

    op.execute(
        "CREATE INDEX ix_content_inv_embedding_hnsw "
        "ON content_inventory "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )

    # ── 5. Add FK from cms_synced_posts → content_inventory ──────

    op.add_column(
        "cms_synced_posts",
        sa.Column(
            "content_inventory_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("content_inventory.id", ondelete="SET NULL"),
            nullable=True,
            comment="Link to the canonical content inventory record for this CMS post.",
        ),
    )

    op.create_index(
        "ix_cms_synced_content_inv",
        "cms_synced_posts",
        ["content_inventory_id"],
    )


def downgrade() -> None:
    # Reverse order
    op.drop_index("ix_cms_synced_content_inv", table_name="cms_synced_posts")
    op.drop_column("cms_synced_posts", "content_inventory_id")
    op.execute("DROP INDEX IF EXISTS ix_content_inv_embedding_hnsw")
    op.drop_index("ix_content_inv_effective_slug", table_name="content_inventory")
    op.drop_index("ix_content_inv_company_source", table_name="content_inventory")
    op.drop_index("ix_content_inv_company", table_name="content_inventory")
    op.drop_index("uq_content_inventory_company_url", table_name="content_inventory")
    op.drop_table("content_inventory")
    op.execute("DROP TYPE IF EXISTS content_ingestion_source_enum")
