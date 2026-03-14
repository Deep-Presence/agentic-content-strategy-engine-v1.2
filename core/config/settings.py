"""
Centralized settings loaded from .env.local (and .env) at repo root.

All environment variables for the content-strategy-engine are loaded here via pydantic-settings.
Import `settings` and use `settings.perplexity_api_key`, etc. instead of load_dotenv/os.getenv.
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# core/config/settings.py -> parents[0]=config, parents[1]=core, parents[2]=content-strategy-engine
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PARENT_DIR = _PROJECT_ROOT.parent  # parent of content-strategy-engine (for .env.local discovery)
# Load .env first, then .env.local (overrides), then .env.test.local (test overrides)
_ENV_FILES = [
    _PROJECT_ROOT / ".env",
    _PROJECT_ROOT / ".env.local",
    _PROJECT_ROOT / ".env.test.local",
    _PARENT_DIR / ".env",
    _PARENT_DIR / ".env.local",
    _PARENT_DIR / ".env.test.local",
]


class Settings(BaseSettings):
    """All environment variables for the content-strategy-engine. Loaded from .env.local at repo root."""

    model_config = SettingsConfigDict(
        env_file=[str(p) for p in _ENV_FILES if p.exists()],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Perplexity
    perplexity_api_key: str | None = None
    perplexity_deep_research_model: str = "sonar-deep-research"
    perplexity_search_model: str = "sonar-pro"

    # OpenAI
    openai_api_key: str | None = None
    embedding_model: str = "text-embedding-3-small"

    # Anthropic / Claude
    anthropic_api_key: str | None = None
    brave_search_api_key: str | None = None

    # Google / Gemini – Legacy API key fallbacks (used by Reddit HIL + Audience Persona)
    google_api_key_company_deepagent: str | None = None
    google_api_key_persona_research_deepagent: str | None = None

    # Google / Gemini – Gap Analysis
    google_api_key_gap_analysis: str | None = None

    # Google / Gemini – Reddit HIL
    google_api_key_reddit_hil: str | None = None
    google_gemini_model_reddit_hil: str = "gemini-3-flash-preview"

    # Pipeline / Agent
    aeo_agent_invoke_timeout_s: int = 900

    # Gap Analysis — Crawl
    gap_analysis_max_crawl_pages: int = 500
    gap_analysis_max_crawl_depth: int = 4

    # Gap Analysis — S3 Concurrency (two-level: global + per-engine)
    gap_analysis_s3_global_concurrency: int = 30
    gap_analysis_s3_concurrency_default: int = 8
    gap_analysis_s3_openai_concurrency: int = 12
    gap_analysis_s3_claude_concurrency: int = 6
    gap_analysis_s3_gemini_concurrency: int = 10
    gap_analysis_s3_perplexity_concurrency: int = 8

    # Gap Analysis — S3 Retry + Circuit Breaker
    gap_analysis_s3_max_retries: int = 2
    gap_analysis_s3_retry_base_delay_s: float = 2.0
    gap_analysis_s3_circuit_breaker_threshold: int = 5

    # Gap Analysis — S4 Concurrency
    gap_analysis_s4_fetch_concurrency: int = 40
    gap_analysis_s4_parse_workers: int = 16
    gap_analysis_s4_http_pool_size: int = 50

    # Gap Analysis — S5 Embedding
    gap_analysis_s5_embed_batch_size: int = 256
    gap_analysis_s5_embed_concurrent_batches: int = 6

    # ChromaDB (local vector store for gap analysis embeddings)
    chroma_persist_dir: str = "artifacts/chroma_db"
    chroma_collection_prefix: str = "gap_company"

    # Gap Analysis – Models
    gap_analysis_query_gen_model: str = "gpt-5.2-2025-12-11"
    gap_analysis_report_model: str = "gpt-5.2-2025-12-11"
    gap_analysis_openai_engine_model: str = "gpt-5.2-2025-12-11"
    gap_analysis_claude_engine_model: str = "claude-sonnet-4-5-20250929"
    gap_analysis_gemini_engine_model: str = "gemini-3-flash-preview"

    # Supabase – primary env vars
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_anon_key: str | None = None
    supabase_agent_id: str | None = None

    # Supabase – fallback from Next.js public vars (client-side)
    next_public_supabase_url: str | None = None
    next_public_supabase_anon_key: str | None = None

    # Reddit (PRAW)
    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    reddit_user_agent: str | None = None

    # Webhooks
    slack_webhook_url: str = ""
    discord_webhook_url: str = ""

    # Content Generation Engine – Models
    content_engine_planner_model: str = "claude-opus-4-6"
    content_engine_worker_model: str = "claude-sonnet-4-5-20250929"
    content_engine_formatter_model: str = "claude-haiku-4-5-20251001"
    content_engine_style_judge_model: str = "claude-haiku-4-5-20251001"
    content_engine_factual_judge_model: str = "claude-sonnet-4-5-20250929"
    content_engine_fact_enricher_model: str = "sonar-pro"

    # Content Generation Engine – Concurrency
    content_engine_max_concurrent_workers: int = 3
    content_engine_max_revision_cycles: int = 2

    # Content Generation Engine – Format-aware revision cycles (v2.0)
    # JSON string mapping content_format enum → max revision cycles
    content_engine_revision_cycles_by_format: str = (
        '{"pillar_page": 3, "comparison": 3, "long_blog": 2, "how_to": 2, "short_faq": 1}'
    )

    # --- Content Engine v1.3 — LiteLLM model identifiers ---
    # Provider-prefixed strings for LiteLLM routing
    content_engine_v13_planner_model: str = "anthropic/claude-sonnet-4-5-20250929"
    content_engine_v13_brief_builder_model: str = "anthropic/claude-sonnet-4-5-20250929"
    content_engine_v13_worker_model: str = "anthropic/claude-sonnet-4-5-20250929"
    content_engine_v13_formatter_model: str = "anthropic/claude-haiku-4-5-20251001"
    content_engine_v13_style_judge_model: str = "anthropic/claude-haiku-4-5-20251001"
    content_engine_v13_factual_judge_model: str = "anthropic/claude-sonnet-4-5-20250929"
    content_engine_v13_eeat_judge_model: str = "anthropic/claude-sonnet-4-5-20250929"
    content_engine_v13_fact_enricher_model: str = "perplexity/sonar-pro"
    content_engine_v13_linker_model: str = "perplexity/sonar-pro"

    # --- Content Engine v1.3 — Pipeline defaults ---
    content_engine_v13_max_topics: int = 6
    content_engine_v13_max_concurrent_workers: int = 3

    # --- LangSmith (observability + Hub) ---
    langsmith_api_key: str | None = None
    langsmith_workspace_id: str | None = None
    langsmith_project: str = "content-engine"
    langsmith_use_hub: bool = False
    langsmith_hub_tag: str = "production"

    # --- Research Knowledge Base ---
    research_kb_project: str = "research-kb"
    # Agent 5 (Brand Perception) — raw Anthropic SDK, plain model ID
    research_kb_brand_perception_model: str = "claude-sonnet-4-5-20250929"
    # Synthesis agent — init_chat_model(), needs provider:model format
    research_kb_synthesis_model: str = "anthropic:claude-opus-4-6"

    # --- Audience Persona Pipeline ---
    google_api_key_audience_persona: str | None = None
    audience_persona_suggester_model: str = "gemini-3-flash-preview"
    audience_persona_generator_model: str = "sonar-deep-research"
    audience_persona_max_concurrent_generators: int = 3

    # --- Voice Style Guide Pipeline ---
    voice_style_guide_discovery_model: str = "anthropic/claude-sonnet-4-6"
    voice_style_guide_synthesis_model: str = "anthropic/claude-sonnet-4-6"
    voice_style_guide_max_concurrent_researchers: int = 3

    # --- Topic Discovery Pipeline ---
    topic_discovery_brainstorm_model: str = "anthropic/claude-sonnet-4-6"
    topic_discovery_dedup_model: str = "anthropic/claude-haiku-4-5-20251001"
    topic_discovery_max_expansion_rounds: int = 4
    topic_discovery_dedup_threshold: float = 0.85
    topic_discovery_max_concurrent_sources: int = 4
    topic_discovery_source_timeout_s: float = 120.0
    topic_discovery_expansion_timeout_s: float = 300.0
    # Algorithmic subdomain scoring weights (JSON string for env override)
    topic_discovery_scoring_weights: str = (
        '{"source_confidence": 0.30, "content_coverage": 0.20, '
        '"gap_severity": 0.25, "competitive_density": 0.0, "persona_breadth": 0.25}'
    )
    topic_discovery_scoring_similarity_threshold: float = 0.60
    topic_discovery_persona_affinity_weights: str = (
        '{"provenance": 0.6, "embedding": 0.4}'
    )
    topic_discovery_max_subdomains_to_expand: int = 20

    # --- CPS Model (Citation Signal Predictor) ---
    cps_enabled: bool = True
    cps_target_weight: float = 0.5

    # Legacy / optional
    tavily_api_key_company_context: str | None = None

    # --- Database (PostgreSQL) ---
    database_url: str | None = None  # postgresql+asyncpg://localhost:5432/deep_presence
    database_echo: bool = False  # SQL logging
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # --- Auth ---
    invite_ttl_days: int = 7  # Invite codes expire after 7 days

    # --- Cache TTLs ---
    platform_cache_ttl_days: int = 7  # Re-search platforms after 7 days
    url_enrichment_cache_ttl_days: int = 14  # Re-scrape URLs after 14 days

    # --- Site Audit (Pipeline 0) ---
    site_audit_max_pages: int = 200  # Default max pages to crawl
    site_audit_max_depth: int = 4  # Default BFS crawl depth
    site_audit_concurrency: int = 30  # Concurrent page-analysis requests
    site_audit_request_timeout: float = 15.0  # Per-request HTTP timeout (seconds)
    site_audit_max_redirects: int = 5  # Max redirect hops before marking broken

    @property
    def database_url_sync(self) -> str | None:
        """Derive sync URL from async URL for Alembic (avoids drift)."""
        if not self.database_url:
            return None
        return self.database_url.replace("+asyncpg", "").replace(
            "asyncpg://", "postgresql://"
        )

    @property
    def effective_supabase_url(self) -> str | None:
        """SUPABASE_URL or NEXT_PUBLIC_SUPABASE_URL fallback."""
        return self.supabase_url or self.next_public_supabase_url

    @property
    def effective_supabase_anon_key(self) -> str | None:
        """SUPABASE_ANON_KEY or NEXT_PUBLIC_SUPABASE_ANON_KEY fallback."""
        return self.supabase_anon_key or self.next_public_supabase_anon_key

    @property
    def effective_supabase_key(self) -> str | None:
        """Service role key preferred; anon key as fallback."""
        return self.supabase_service_role_key or self.effective_supabase_anon_key


# Singleton instance – import this from anywhere
settings = Settings()
