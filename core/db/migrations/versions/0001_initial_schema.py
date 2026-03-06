"""Create initial schema — all tables, enums, pgvector extension.

Revision ID: 0001
Revises: -
Create Date: 2026-02-27
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


# ── Enum type names ──────────────────────────────────────────────────────

user_role_enum = sa.Enum(
    "superuser", "member", "viewer", name="user_role_enum"
)
pipeline_type_enum = sa.Enum(
    "research", "gap_analysis", "content", "content_refresh",
    "site_audit", "topic_discovery", name="pipeline_type_enum"
)
pipeline_status_enum = sa.Enum(
    "pending", "running", "completed", "failed", "cancelled",
    name="pipeline_status_enum"
)
stage_status_enum = sa.Enum(
    "pending", "running", "completed", "failed", "skipped", "cached",
    name="stage_status_enum"
)
search_engine_enum = sa.Enum(
    "openai", "claude", "gemini", "perplexity", name="search_engine_enum"
)
gap_classification_enum = sa.Enum(
    "large_gap", "moderate_gap", "small_gap", "no_gap", "already_cited",
    name="gap_classification_enum"
)
artifact_type_enum = sa.Enum(
    "company_context", "persona", "style_guide", name="artifact_type_enum"
)
artifact_status_enum = sa.Enum(
    "draft", "approved", "archived", name="artifact_status_enum"
)
content_piece_status_enum = sa.Enum(
    "planned", "drafting", "review", "approved", "published", "archived",
    name="content_piece_status_enum"
)
finding_severity_enum = sa.Enum(
    "critical", "high", "medium", "low", "info",
    name="finding_severity_enum"
)
tracking_status_enum = sa.Enum(
    "pending", "completed", "failed", name="tracking_status_enum"
)


def upgrade() -> None:
    # ── pgvector extension ───────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── Create all enum types ────────────────────────────────────────────
    user_role_enum.create(op.get_bind(), checkfirst=True)
    pipeline_type_enum.create(op.get_bind(), checkfirst=True)
    pipeline_status_enum.create(op.get_bind(), checkfirst=True)
    stage_status_enum.create(op.get_bind(), checkfirst=True)
    search_engine_enum.create(op.get_bind(), checkfirst=True)
    gap_classification_enum.create(op.get_bind(), checkfirst=True)
    artifact_type_enum.create(op.get_bind(), checkfirst=True)
    artifact_status_enum.create(op.get_bind(), checkfirst=True)
    content_piece_status_enum.create(op.get_bind(), checkfirst=True)
    finding_severity_enum.create(op.get_bind(), checkfirst=True)
    tracking_status_enum.create(op.get_bind(), checkfirst=True)

    # ── 1. companies ─────────────────────────────────────────────────────
    op.create_table(
        "companies",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String, unique=True, nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("domain", sa.String, nullable=False),
        sa.Column("additional_domains", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("is_archived", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── 2. products ──────────────────────────────────────────────────────
    op.create_table(
        "products",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("slug", sa.String, nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("domain", sa.String, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "slug", name="uq_products_company_slug"),
    )

    # ── 3. users ─────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("email", sa.String, unique=True, nullable=False),
        sa.Column("password_hash", sa.String, nullable=False),
        sa.Column("first_name", sa.String, default=""),
        sa.Column("last_name", sa.String, default=""),
        sa.Column("role", sa.Enum("superuser", "member", "viewer", name="user_role_enum",
                                  create_type=False), default="member"),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_company_id", "users", ["company_id"])
    op.create_index("ix_users_email", "users", ["email"])

    # ── 4. invites ───────────────────────────────────────────────────────
    op.create_table(
        "invites",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("code", sa.String, unique=True, nullable=False),
        sa.Column("role", sa.Enum("superuser", "member", "viewer", name="user_role_enum",
                                  create_type=False), default="member"),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("redeemed_by", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── 5. company_pipeline_defaults ─────────────────────────────────────
    op.create_table(
        "company_pipeline_defaults",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("companies.id"), unique=True, nullable=False),
        sa.Column("defaults_json", postgresql.JSONB, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── 6. pipeline_runs ─────────────────────────────────────────────────
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("product_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("products.id"), nullable=True),
        sa.Column("effective_slug", sa.String, nullable=False),
        sa.Column("pipeline_type", sa.Enum(
            "research", "gap_analysis", "content", "content_refresh",
            "site_audit", "topic_discovery",
            name="pipeline_type_enum", create_type=False), nullable=False),
        sa.Column("parent_run_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pipeline_runs.id"), nullable=True),
        sa.Column("status", sa.Enum(
            "pending", "running", "completed", "failed", "cancelled",
            name="pipeline_status_enum", create_type=False), nullable=False),
        sa.Column("config", postgresql.JSONB, nullable=True),
        sa.Column("summary", postgresql.JSONB, nullable=True),
        sa.Column("stages_executed", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_pipeline_runs_company_type", "pipeline_runs",
                    ["company_id", "pipeline_type"])
    op.create_index("ix_pipeline_runs_slug_type", "pipeline_runs",
                    ["effective_slug", "pipeline_type"])
    op.create_index("ix_pipeline_runs_active", "pipeline_runs", ["status"],
                    postgresql_where=sa.text("status IN ('pending','running')"))

    # ── 7. pipeline_stage_logs ───────────────────────────────────────────
    op.create_table(
        "pipeline_stage_logs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_name", sa.String, nullable=False),
        sa.Column("status", sa.Enum(
            "pending", "running", "completed", "failed", "skipped", "cached",
            name="stage_status_enum", create_type=False), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer, nullable=True),
        sa.Column("items_processed", sa.Integer, nullable=True),
        sa.Column("items_from_cache", sa.Integer, nullable=True),
        sa.Column("metadata_json", postgresql.JSONB, nullable=True),
    )
    op.create_index("ix_pipeline_stage_logs_run_id", "pipeline_stage_logs", ["run_id"])

    # ── 8. platform_result_cache ─────────────────────────────────────────
    op.create_table(
        "platform_result_cache",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("query_text_hash", sa.String, nullable=False),
        sa.Column("query_text", sa.Text, nullable=False),
        sa.Column("engine", sa.Enum(
            "openai", "claude", "gemini", "perplexity",
            name="search_engine_enum", create_type=False), nullable=False),
        sa.Column("model_version", sa.String, nullable=True),
        sa.Column("response_text", sa.Text, nullable=True),
        sa.Column("citations", postgresql.JSONB, nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("query_text_hash", "engine", name="uq_platform_cache_hash_engine"),
    )
    op.create_index("ix_platform_cache_hash_engine_fetched", "platform_result_cache",
                    ["query_text_hash", "engine", "fetched_at"])

    # ── 9. url_enrichment_cache ──────────────────────────────────────────
    op.create_table(
        "url_enrichment_cache",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("url_hash", sa.String, unique=True, nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("final_url", sa.Text, nullable=True),
        sa.Column("domain", sa.String, nullable=True),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("authority_type", sa.String, nullable=True),
        sa.Column("content_type", sa.String, nullable=True),
        sa.Column("paragraph_count", sa.Integer, nullable=True),
        sa.Column("http_status", sa.Integer, nullable=True),
        sa.Column("scraped_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_paragraphs_storage_key", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_url_enrichment_hash_scraped", "url_enrichment_cache",
                    ["url_hash", "scraped_at"])
    op.create_index("ix_url_enrichment_domain", "url_enrichment_cache", ["domain"])

    # ── 10. url_structural_signals ───────────────────────────────────────
    op.create_table(
        "url_structural_signals",
        # PK is the FK itself — 1:1 relationship
        sa.Column("url_enrichment_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("url_enrichment_cache.id"), primary_key=True),
        # Original signals (11)
        sa.Column("word_count", sa.Integer, default=0),
        sa.Column("paragraph_count", sa.Integer, default=0),
        sa.Column("header_count", sa.Integer, default=0),
        sa.Column("list_item_count", sa.Integer, default=0),
        sa.Column("stat_count", sa.Integer, default=0),
        sa.Column("citation_count", sa.Integer, default=0),
        sa.Column("has_headers", sa.Boolean, default=False),
        sa.Column("has_lists", sa.Boolean, default=False),
        sa.Column("has_numbers", sa.Boolean, default=False),
        # Category A: Content depth (9)
        sa.Column("main_content_word_count", sa.Integer, default=0),
        sa.Column("sentence_count", sa.Integer, default=0),
        sa.Column("avg_paragraph_length", sa.Float, default=0.0),
        sa.Column("median_paragraph_length", sa.Float, default=0.0),
        sa.Column("max_paragraph_word_count", sa.Integer, default=0),
        sa.Column("avg_sentence_length", sa.Float, default=0.0),
        sa.Column("avg_sentence_count_per_paragraph", sa.Float, default=0.0),
        sa.Column("reading_level", sa.Float, default=0.0),
        sa.Column("self_contained_ratio", sa.Float, default=0.0),
        # Category B: Structural elements (13)
        sa.Column("h1_count", sa.Integer, default=0),
        sa.Column("h2_count", sa.Integer, default=0),
        sa.Column("h3_count", sa.Integer, default=0),
        sa.Column("h4_count", sa.Integer, default=0),
        sa.Column("ordered_list_count", sa.Integer, default=0),
        sa.Column("unordered_list_count", sa.Integer, default=0),
        sa.Column("table_count", sa.Integer, default=0),
        sa.Column("definition_list_count", sa.Integer, default=0),
        sa.Column("blockquote_count", sa.Integer, default=0),
        sa.Column("code_block_count", sa.Integer, default=0),
        sa.Column("list_block_count", sa.Integer, default=0),
        sa.Column("bullets_per_list_block", sa.Float, default=0.0),
        sa.Column("min_bullets_per_list", sa.Integer, default=0),
        # Category C: AI-friendly patterns (8)
        sa.Column("has_faq_section", sa.Boolean, default=False),
        sa.Column("has_definition_opening", sa.Boolean, default=False),
        sa.Column("has_key_takeaways", sa.Boolean, default=False),
        sa.Column("has_toc", sa.Boolean, default=False),
        sa.Column("has_comparison_table", sa.Boolean, default=False),
        sa.Column("has_step_by_step", sa.Boolean, default=False),
        sa.Column("has_research_refs", sa.Boolean, default=False),
        sa.Column("has_expert_quotes", sa.Boolean, default=False),
        # Category D: Data density (3)
        sa.Column("data_point_count", sa.Integer, default=0),
        sa.Column("citation_density", sa.Float, default=0.0),
        sa.Column("named_entity_density", sa.Float, default=0.0),
    )

    # ── 11. run_queries ──────────────────────────────────────────────────
    op.create_table(
        "run_queries",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pipeline_runs.id"), nullable=False),
        sa.Column("query_id", sa.String, nullable=False),
        sa.Column("cluster_id", sa.String, nullable=True),
        sa.Column("cluster_name", sa.String, nullable=False),
        sa.Column("query_text", sa.Text, nullable=False),
        sa.Column("buyer_stage", sa.String, nullable=True),
        sa.Column("persona_tag", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("run_id", "query_id", name="uq_run_queries_run_query"),
    )
    op.create_index("ix_run_queries_run_cluster", "run_queries", ["run_id", "cluster_name"])

    # ── 12. run_citations ────────────────────────────────────────────────
    op.create_table(
        "run_citations",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("query_id", sa.String, nullable=False),
        sa.Column("cluster_name", sa.String, nullable=True),
        sa.Column("engine", sa.Enum(
            "openai", "claude", "gemini", "perplexity",
            name="search_engine_enum", create_type=False), nullable=False),
        sa.Column("url_enrichment_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("url_enrichment_cache.id"), nullable=True),
        sa.Column("citation_rank", sa.Integer, nullable=True),
        sa.Column("snippet", sa.Text, nullable=True),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("domain", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_run_citations_run_query", "run_citations", ["run_id", "query_id"])
    op.create_index("ix_run_citations_run_engine", "run_citations", ["run_id", "engine"])
    op.create_index("ix_run_citations_url_enrichment", "run_citations", ["url_enrichment_id"])
    # Composite FK to run_queries(run_id, query_id)
    op.create_foreign_key(
        "fk_run_citations_run_query", "run_citations", "run_queries",
        ["run_id", "query_id"], ["run_id", "query_id"],
    )

    # ── 13. content_pieces ───────────────────────────────────────────────
    # Created before query_gaps because query_gaps.targeted_by_content_id → content_pieces.id
    op.create_table(
        "content_pieces",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pipeline_runs.id"), nullable=False),
        sa.Column("gap_run_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pipeline_runs.id"), nullable=True),
        sa.Column("query_id", sa.String, nullable=True),
        sa.Column("cluster_name", sa.String, nullable=True),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("content_type", sa.String, nullable=True),
        sa.Column("status", sa.Enum(
            "planned", "drafting", "review", "approved", "published", "archived",
            name="content_piece_status_enum", create_type=False), nullable=True),
        sa.Column("storage_key", sa.String, nullable=True),
        sa.Column("word_count", sa.Integer, default=0),
        sa.Column("citability_score", sa.Float, nullable=True),
        sa.Column("evaluation_results", postgresql.JSONB, nullable=True),
        sa.Column("revision_count", sa.Integer, default=0),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_url", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_content_pieces_run", "content_pieces", ["run_id"])
    op.create_index("ix_content_pieces_gap_query", "content_pieces",
                    ["gap_run_id", "query_id"])
    op.create_index("ix_content_pieces_status", "content_pieces", ["status"])

    # ── 14. query_gaps ───────────────────────────────────────────────────
    op.create_table(
        "query_gaps",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("query_id", sa.String, nullable=False),
        sa.Column("query_text", sa.Text, nullable=False),
        sa.Column("cluster_name", sa.String, nullable=False),
        sa.Column("cluster_id", sa.String, nullable=True),
        sa.Column("avg_citation_similarity", sa.Float, nullable=True),
        sa.Column("best_company_similarity", sa.Float, nullable=True),
        sa.Column("best_company_unit_id", sa.String, nullable=True),
        sa.Column("best_company_unit_text", sa.Text, nullable=True),
        sa.Column("gap", sa.Float, nullable=False),
        sa.Column("classification", sa.Enum(
            "large_gap", "moderate_gap", "small_gap", "no_gap", "already_cited",
            name="gap_classification_enum", create_type=False), nullable=False),
        sa.Column("content_brief", postgresql.JSONB, nullable=True),
        sa.Column("targeted_by_content_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("content_pieces.id", ondelete="SET NULL"), nullable=True),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refreshed_by_run_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pipeline_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("run_id", "query_id", name="uq_query_gaps_run_query"),
    )
    op.create_index("ix_query_gaps_run_classification", "query_gaps",
                    ["run_id", "classification"])
    op.create_index("ix_query_gaps_run_cluster", "query_gaps", ["run_id", "cluster_name"])
    op.create_index("ix_query_gaps_targeted", "query_gaps", ["targeted_by_content_id"],
                    postgresql_where=sa.text("targeted_by_content_id IS NOT NULL"))

    # ── 15. query_exemplars ──────────────────────────────────────────────
    op.create_table(
        "query_exemplars",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("query_gap_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("query_gaps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url_enrichment_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("url_enrichment_cache.id"), nullable=True),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("domain", sa.String, nullable=True),
        sa.Column("similarity", sa.Float, nullable=False),
        sa.Column("snippet", sa.Text, nullable=True),
        sa.Column("authority_type", sa.String, nullable=True),
        sa.Column("rank", sa.Integer, nullable=False),
    )
    op.create_index("ix_query_exemplars_gap", "query_exemplars", ["query_gap_id"])

    # ── 16. cluster_specs ────────────────────────────────────────────────
    op.create_table(
        "cluster_specs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pipeline_runs.id"), nullable=False),
        sa.Column("cluster_id", sa.String, nullable=True),
        sa.Column("cluster_name", sa.String, nullable=False),
        sa.Column("query_count", sa.Integer, default=0),
        sa.Column("total_citations_analyzed", sa.Integer, default=0),
        sa.Column("min_similarity_threshold", sa.Float, nullable=True),
        sa.Column("word_count_min", sa.Integer, default=0),
        sa.Column("word_count_max", sa.Integer, default=0),
        sa.Column("avg_word_count", sa.Float, default=0.0),
        sa.Column("avg_paragraph_word_count", sa.Float, default=0.0),
        sa.Column("avg_sentence_count_per_paragraph", sa.Float, default=0.0),
        sa.Column("min_bullets_per_list", sa.Integer, default=0),
        sa.Column("faq_rate", sa.Float, default=0.0),
        sa.Column("table_rate", sa.Float, default=0.0),
        sa.Column("definition_rate", sa.Float, default=0.0),
        sa.Column("code_block_rate", sa.Float, default=0.0),
        sa.Column("key_takeaways_rate", sa.Float, default=0.0),
        sa.Column("dominant_content_type", sa.String, nullable=True),
        sa.Column("dominant_authority_type", sa.String, nullable=True),
        sa.Column("required_elements", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("structural_rates", postgresql.JSONB, nullable=True),
        sa.Column("exemplar_themes", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("run_id", "cluster_name", name="uq_cluster_specs_run_cluster"),
    )

    # ── 17. spa_results ──────────────────────────────────────────────────
    op.create_table(
        "spa_results",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pipeline_runs.id"), nullable=False),
        sa.Column("cluster_id", sa.String, nullable=True),
        sa.Column("cluster_name", sa.String, nullable=False),
        sa.Column("t_stat", sa.Float, nullable=True),
        sa.Column("p_value", sa.Float, nullable=True),
        sa.Column("mean_citation_similarity", sa.Float, nullable=True),
        sa.Column("mean_company_similarity", sa.Float, nullable=True),
        sa.Column("effect", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("run_id", "cluster_name", name="uq_spa_results_run_cluster"),
    )

    # ── 18. centroid_results ─────────────────────────────────────────────
    op.create_table(
        "centroid_results",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pipeline_runs.id"), nullable=False),
        sa.Column("cluster_name", sa.String, nullable=False),
        sa.Column("distance", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("run_id", "cluster_name", name="uq_centroid_results_run_cluster"),
    )

    # ── 19. semantic_units (pgvector) ────────────────────────────────────
    op.create_table(
        "semantic_units",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("run_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pipeline_runs.id"), nullable=False),
        sa.Column("unit_id", sa.String, nullable=False),
        sa.Column("url", sa.Text, nullable=True),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("discovery_source", sa.String, default="website"),
        sa.Column("char_count", sa.Integer, default=0),
        sa.Column("word_count", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_semantic_units_company_run", "semantic_units",
                    ["company_id", "run_id"])

    # ── 20. query_embeddings (pgvector) ──────────────────────────────────
    op.create_table(
        "query_embeddings",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pipeline_runs.id"), nullable=False),
        sa.Column("query_id", sa.String, nullable=False),
        sa.Column("query_text", sa.Text, nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("run_id", "query_id", name="uq_query_embeddings_run_query"),
    )

    # ── 21. paragraph_embeddings (pgvector) ──────────────────────────────
    op.create_table(
        "paragraph_embeddings",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("url_enrichment_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("url_enrichment_cache.id"), nullable=False),
        sa.Column("embedding_id", sa.String, unique=True, nullable=False),
        sa.Column("paragraph_text", sa.Text, nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("original_paragraph_index", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_paragraph_embeddings_url_enrichment", "paragraph_embeddings",
                    ["url_enrichment_id"])

    # ── 22. run_paragraph_scores ─────────────────────────────────────────
    op.create_table(
        "run_paragraph_scores",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_citation_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("run_citations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("paragraph_embedding_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("paragraph_embeddings.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("similarity", sa.Float, nullable=False),
        sa.Column("rank", sa.Integer, nullable=False),
    )
    op.create_index("ix_run_paragraph_scores_citation", "run_paragraph_scores",
                    ["run_citation_id"])

    # ── 23. research_artifacts ───────────────────────────────────────────
    op.create_table(
        "research_artifacts",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("product_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("products.id"), nullable=True),
        sa.Column("effective_slug", sa.String, nullable=False),
        sa.Column("artifact_type", sa.Enum(
            "company_context", "persona", "style_guide",
            name="artifact_type_enum", create_type=False), nullable=False),
        sa.Column("title", sa.String, nullable=True),
        sa.Column("status", sa.Enum(
            "draft", "approved", "archived",
            name="artifact_status_enum", create_type=False), default="draft"),
        sa.Column("version", sa.Integer, default=1),
        sa.Column("storage_key", sa.String, nullable=False),
        sa.Column("content_hash", sa.String, nullable=True),
        sa.Column("metadata_json", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_research_artifacts_company_type", "research_artifacts",
                    ["company_id", "artifact_type"])
    op.create_index("ix_research_artifacts_slug_type", "research_artifacts",
                    ["effective_slug", "artifact_type"])

    # ── 24. site_audits ──────────────────────────────────────────────────
    op.create_table(
        "site_audits",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("site_domain", sa.String, nullable=False),
        sa.Column("status", sa.Enum(
            "pending", "running", "completed", "failed", "cancelled",
            name="pipeline_status_enum", create_type=False), default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("findings_count", sa.Integer, default=0),
        sa.Column("pages_crawled", sa.Integer, default=0),
        sa.Column("config", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_site_audits_company_created", "site_audits",
                    ["company_id", "created_at"])

    # ── 25. audit_findings ───────────────────────────────────────────────
    op.create_table(
        "audit_findings",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("audit_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("site_audits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_url", sa.Text, nullable=False),
        sa.Column("finding_type", sa.String, nullable=False),
        sa.Column("severity", sa.Enum(
            "critical", "high", "medium", "low", "info",
            name="finding_severity_enum", create_type=False), nullable=False),
        sa.Column("details", postgresql.JSONB, nullable=True),
        sa.Column("is_resolved", sa.Boolean, default=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_findings_audit_severity", "audit_findings",
                    ["audit_id", "severity"])
    op.create_index("ix_audit_findings_audit_type", "audit_findings",
                    ["audit_id", "finding_type"])
    op.create_index("ix_audit_findings_audit_resolved", "audit_findings",
                    ["audit_id", "is_resolved"])

    # ── 26. topic_discoveries ────────────────────────────────────────────
    op.create_table(
        "topic_discoveries",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("product_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("products.id"), nullable=True),
        sa.Column("pipeline_run_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pipeline_runs.id"), nullable=True),
        sa.Column("status", sa.Enum(
            "pending", "running", "completed", "failed", "cancelled",
            name="pipeline_status_enum", create_type=False), default="pending"),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_topic_discoveries_company", "topic_discoveries", ["company_id"])

    # ── 27. discovered_topics ────────────────────────────────────────────
    op.create_table(
        "discovered_topics",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("discovery_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("topic_discoveries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("topic_text", sa.Text, nullable=False),
        sa.Column("relevance_score", sa.Float, nullable=True),
        sa.Column("cluster_id", sa.String, nullable=True),
        sa.Column("buyer_stage", sa.String, nullable=True),
        sa.Column("metadata_json", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_discovered_topics_discovery", "discovered_topics", ["discovery_id"])

    # ── 28. knowledge_documents ──────────────────────────────────────────
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("effective_slug", sa.String, nullable=False),
        sa.Column("filename", sa.String, nullable=False),
        sa.Column("content_type", sa.String, nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=False),
        sa.Column("word_count", sa.Integer, default=0),
        sa.Column("storage_key", sa.String, nullable=False),
        sa.Column("is_embedded", sa.Boolean, default=False),
        sa.Column("last_embedded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_knowledge_documents_company_slug", "knowledge_documents",
                    ["company_id", "effective_slug"])

    # ── 29. tracking_snapshots ───────────────────────────────────────────
    op.create_table(
        "tracking_snapshots",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("product_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("products.id"), nullable=True),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("gap_run_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pipeline_runs.id"), nullable=True),
        sa.Column("status", sa.Enum(
            "pending", "completed", "failed",
            name="tracking_status_enum", create_type=False), default="pending"),
        sa.Column("queries_checked", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tracking_snapshots_company_date", "tracking_snapshots",
                    ["company_id", "snapshot_date"])
    # Partial unique indexes for NULL-safe product_id uniqueness
    op.create_index("ix_tracking_snapshots_with_product", "tracking_snapshots",
                    ["company_id", "product_id", "snapshot_date"], unique=True,
                    postgresql_where=sa.text("product_id IS NOT NULL"))
    op.create_index("ix_tracking_snapshots_no_product", "tracking_snapshots",
                    ["company_id", "snapshot_date"], unique=True,
                    postgresql_where=sa.text("product_id IS NULL"))

    # ── 30a. content_mention_tracking ────────────────────────────────────
    op.create_table(
        "content_mention_tracking",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("snapshot_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tracking_snapshots.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("query_text", sa.Text, nullable=False),
        sa.Column("query_id", sa.String, nullable=True),
        sa.Column("cluster_name", sa.String, nullable=True),
        sa.Column("engine", sa.Enum(
            "openai", "claude", "gemini", "perplexity",
            name="search_engine_enum", create_type=False), nullable=False),
        sa.Column("company_mentioned", sa.Boolean, nullable=False),
        sa.Column("company_citation_rank", sa.Integer, nullable=True),
        sa.Column("company_url_cited", sa.Text, nullable=True),
        sa.Column("competitor_urls_cited", postgresql.JSONB, nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_content_mention_tracking_snap_engine",
                    "content_mention_tracking", ["snapshot_id", "engine"])
    op.create_index("ix_content_mention_tracking_snap_cluster",
                    "content_mention_tracking", ["snapshot_id", "cluster_name"])

    # ── 30b. content_piece_tracking ──────────────────────────────────────
    op.create_table(
        "content_piece_tracking",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("snapshot_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tracking_snapshots.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("content_piece_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("content_pieces.id"), nullable=True),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("mention_count", sa.Integer, default=0),
        sa.Column("citation_count_by_platform", postgresql.JSONB, nullable=True),
        sa.Column("avg_citation_rank", sa.Float, nullable=True),
        sa.Column("traffic_estimate", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_content_piece_tracking_snap_url", "content_piece_tracking",
                    ["snapshot_id", "url"])
    op.create_index("ix_content_piece_tracking_piece_snap", "content_piece_tracking",
                    ["content_piece_id", "snapshot_id"])


def downgrade() -> None:
    # ── Drop tables in reverse FK-dependency order ───────────────────────
    op.drop_table("content_piece_tracking")
    op.drop_table("content_mention_tracking")
    op.drop_table("tracking_snapshots")
    op.drop_table("knowledge_documents")
    op.drop_table("discovered_topics")
    op.drop_table("topic_discoveries")
    op.drop_table("audit_findings")
    op.drop_table("site_audits")
    op.drop_table("research_artifacts")
    op.drop_table("run_paragraph_scores")
    op.drop_table("paragraph_embeddings")
    op.drop_table("query_embeddings")
    op.drop_table("semantic_units")
    op.drop_table("centroid_results")
    op.drop_table("spa_results")
    op.drop_table("cluster_specs")
    op.drop_table("query_exemplars")
    op.drop_table("query_gaps")
    op.drop_table("content_pieces")
    op.drop_table("run_citations")
    op.drop_table("run_queries")
    op.drop_table("url_structural_signals")
    op.drop_table("url_enrichment_cache")
    op.drop_table("platform_result_cache")
    op.drop_table("pipeline_stage_logs")
    op.drop_table("pipeline_runs")
    op.drop_table("company_pipeline_defaults")
    op.drop_table("invites")
    op.drop_table("users")
    op.drop_table("products")
    op.drop_table("companies")

    # ── Drop enum types ──────────────────────────────────────────────────
    tracking_status_enum.drop(op.get_bind(), checkfirst=True)
    finding_severity_enum.drop(op.get_bind(), checkfirst=True)
    content_piece_status_enum.drop(op.get_bind(), checkfirst=True)
    artifact_status_enum.drop(op.get_bind(), checkfirst=True)
    artifact_type_enum.drop(op.get_bind(), checkfirst=True)
    gap_classification_enum.drop(op.get_bind(), checkfirst=True)
    search_engine_enum.drop(op.get_bind(), checkfirst=True)
    stage_status_enum.drop(op.get_bind(), checkfirst=True)
    pipeline_status_enum.drop(op.get_bind(), checkfirst=True)
    pipeline_type_enum.drop(op.get_bind(), checkfirst=True)
    user_role_enum.drop(op.get_bind(), checkfirst=True)

    # ── Drop pgvector extension ──────────────────────────────────────────
    op.execute("DROP EXTENSION IF EXISTS vector")
