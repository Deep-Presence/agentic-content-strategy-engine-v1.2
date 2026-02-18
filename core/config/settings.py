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

    # DeepAgents / LLM
    deepagents_model: str ="claude-sonnet-4-5-20250929"

    # OpenAI
    openai_api_key: str | None = None
    embedding_model: str = "text-embedding-3-large"

    # Anthropic / Claude
    anthropic_api_key: str | None = None
    brave_search_api_key: str | None = None

    # Google / Gemini – Company Research
    google_api_key_company_deepagent: str | None = None
    google_gemini_model_company_deepagent: str = "gemini-3-flash-preview"
    # Google / Gemini – Persona Research
    google_api_key_persona_research_deepagent: str | None = None
    google_persona_deepagents_model: str ="gemini-3-flash-preview"
    # Google / Gemini – Style Guide Research
    google_api_key_style_guide_research_deepagent: str | None = None
    google_style_guide_deepagents_model: str ="gemini-3-flash-preview"

    # Google / Gemini – Gap Analysis
    google_api_key_gap_analysis: str | None = None

    # Google / Gemini – Reddit HIL
    google_api_key_reddit_hil: str | None = None
    google_gemini_model_reddit_hil: str = "gemini-3-flash-preview"

    # Pipeline / Agent
    aeo_agent_invoke_timeout_s: int = 900

    # Gap Analysis
    gap_analysis_max_crawl_pages: int = 500
    gap_analysis_max_crawl_depth: int = 4

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
    content_engine_planner_model: str = "claude-opus-4-5-20260218"
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

    # Langfuse (observability)
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://us.cloud.langfuse.com"

    # Legacy / optional
    tavily_api_key_company_context: str | None = None

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
