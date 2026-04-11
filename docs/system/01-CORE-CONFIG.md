# Core Configuration

> **Location:** `core/config/`
> **Owner:** Core
> **Dependencies:** Pydantic Settings, environment variables
> **Dependents:** Every module in the system
> **Last Updated:** 2026-04-09

## Overview

The configuration module provides centralized environment variable management via a single Pydantic `Settings` class. Every tunable parameter in the system — API keys, model selections, concurrency limits, feature flags, connection URLs — is defined here with sensible defaults. The module loads `.env` files from both the project root and its parent directory, supporting layered configuration for different environments.

## Architecture

```
.env / .env.local / .env.test.local
              │
              ▼
    ┌─────────────────────┐
    │  Settings(BaseSettings) │  ← 113 fields, 5 computed properties, 1 validator
    └─────────┬───────────┘
              │
              ▼
    settings = Settings()       ← Module-level singleton
              │
              ▼
    from core.config import settings   ← Used everywhere
```

## File Structure

| File | Purpose | Key Exports |
|------|---------|-------------|
| `__init__.py` | Package marker | (empty) |
| `settings.py` | Settings class + singleton | `Settings`, `settings` |

## Detailed Reference

### `settings.py`

#### Constants

| Name | Type | Value | Description |
|------|------|-------|-------------|
| `_PROJECT_ROOT` | `Path` | `Path(__file__).resolve().parents[2]` | Repository root directory |
| `_PARENT_DIR` | `Path` | `_PROJECT_ROOT.parent` | Parent of repo root |
| `_ENV_FILES` | `list[Path]` | 6 paths | `.env`, `.env.local`, `.env.test.local` in both project root and parent |

#### Class: `Settings(BaseSettings)`

Central configuration for the entire application. Uses Pydantic v2 Settings with `SettingsConfigDict(env_file_encoding="utf-8", extra="ignore")`.

##### LLM API Keys

| Field | Type | Default | Env Var |
|-------|------|---------|---------|
| `openrouter_api_key` | `str \| None` | `None` | `OPENROUTER_API_KEY` |
| `openrouter_base_url` | `str` | `"https://openrouter.ai/api/v1"` | `OPENROUTER_BASE_URL` |
| `perplexity_api_key` | `str \| None` | `None` | `PERPLEXITY_API_KEY` |
| `openai_api_key` | `str \| None` | `None` | `OPENAI_API_KEY` |
| `anthropic_api_key` | `str \| None` | `None` | `ANTHROPIC_API_KEY` |
| `brave_search_api_key` | `str \| None` | `None` | `BRAVE_SEARCH_API_KEY` |

##### Google API Keys (Per-Pipeline)

| Field | Type | Default |
|-------|------|---------|
| `google_api_key_gap_analysis` | `str \| None` | `None` |
| `google_api_key_reddit_hil` | `str \| None` | `None` |
| `google_api_key_audience_persona` | `str \| None` | `None` |
| `google_api_key_company_deepagent` | `str \| None` | `None` |
| `google_api_key_persona_research_deepagent` | `str \| None` | `None` |
| `google_gemini_model_reddit_hil` | `str` | `"google/gemini-3-flash-preview"` |

##### Embedding Model

| Field | Type | Default |
|-------|------|---------|
| `embedding_model` | `str` | `"text-embedding-3-small"` |

##### Database (PostgreSQL)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `database_url` | `str \| None` | `None` | Async URL (`postgresql+asyncpg://...`). **Required.** |
| `database_echo` | `bool` | `False` | SQL query logging |
| `database_pool_size` | `int` | `5` | Connection pool size |
| `database_max_overflow` | `int` | `10` | Pool max overflow |

**Validator:** `_normalize_database_url()` — auto-converts `postgresql://` to `postgresql+asyncpg://` (handles Railway databases).

**Computed Property:** `database_url_sync` — derives sync URL by stripping `+asyncpg` (for Alembic migrations).

##### Redis

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `redis_url` | `str \| None` | `None` | Redis connection URL. **Required.** |
| `redis_max_connections` | `int` | `20` | Connection pool max |
| `redis_socket_timeout` | `float` | `20.0` | Socket timeout (seconds) |
| `redis_socket_connect_timeout` | `float` | `2.0` | Connect timeout (seconds) |
| `redis_retry_on_timeout` | `bool` | `True` | Auto-retry on timeout |
| `redis_health_check_interval` | `int` | `30` | Health check interval (seconds) |
| `redis_event_bus` | `bool` | `True` | Use Redis Streams for SSE |
| `redis_pipeline_state` | `bool` | `True` | Use Redis Hashes for pipeline state |
| `redis_checkpointer` | `bool` | `True` | Use RedisSaver for LangGraph HITL |

##### Content Engine v1.3 (Production)

| Field | Type | Default |
|-------|------|---------|
| `content_engine_v13_planner_model` | `str` | `"anthropic/claude-sonnet-4-6"` |
| `content_engine_v13_brief_builder_model` | `str` | `"anthropic/claude-sonnet-4-6"` |
| `content_engine_v13_worker_model` | `str` | `"anthropic/claude-sonnet-4-6"` |
| `content_engine_v13_formatter_model` | `str` | `"anthropic/claude-haiku-4-5"` |
| `content_engine_v13_style_judge_model` | `str` | `"anthropic/claude-haiku-4-5"` |
| `content_engine_v13_factual_judge_model` | `str` | `"anthropic/claude-sonnet-4-6"` |
| `content_engine_v13_eeat_judge_model` | `str` | `"anthropic/claude-sonnet-4-6"` |
| `content_engine_v13_fact_enricher_model` | `str` | `"perplexity/sonar-pro"` |
| `content_engine_v13_linker_model` | `str` | `"perplexity/sonar-pro"` |
| `content_engine_v13_max_topics` | `int` | `6` |
| `content_engine_v13_max_concurrent_workers` | `int` | `3` |

##### Content Engine v1.2 (Legacy)

| Field | Type | Default |
|-------|------|---------|
| `content_engine_planner_model` | `str` | `"anthropic/claude-opus-4-6"` |
| `content_engine_worker_model` | `str` | `"claude-sonnet-4-6"` |
| `content_engine_formatter_model` | `str` | `"claude-haiku-4-5"` |
| `content_engine_style_judge_model` | `str` | `"claude-haiku-4-5"` |
| `content_engine_factual_judge_model` | `str` | `"claude-sonnet-4-6"` |
| `content_engine_fact_enricher_model` | `str` | `"sonar-pro"` |
| `content_engine_max_concurrent_workers` | `int` | `3` |
| `content_engine_max_revision_cycles` | `int` | `2` |
| `content_engine_revision_cycles_by_format` | `str` | JSON: pillar_page=3, comparison=3, long_blog=2, how_to=2, short_faq=1 |

##### Gap Analysis Pipeline

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `gap_analysis_max_crawl_pages` | `int` | `500` | Max pages to crawl |
| `gap_analysis_max_crawl_depth` | `int` | `4` | Max BFS depth |
| `gap_analysis_debug` | `bool` | `False` | Microscopic structlog tracing |
| `gap_analysis_pw_fail_threshold` | `int` | `10` | Playwright timeout threshold |
| `gap_analysis_wb_fail_threshold` | `int` | `5` | Wayback failure threshold |
| `gap_analysis_total_fail_threshold` | `int` | `20` | Total failure threshold |
| `gap_analysis_s3_global_concurrency` | `int` | `30` | S3 global concurrency |
| `gap_analysis_s3_concurrency_default` | `int` | `8` | S3 per-engine default |
| `gap_analysis_s3_openai_concurrency` | `int` | `12` | OpenAI engine concurrency |
| `gap_analysis_s3_claude_concurrency` | `int` | `6` | Claude engine concurrency |
| `gap_analysis_s3_gemini_concurrency` | `int` | `10` | Gemini engine concurrency |
| `gap_analysis_s3_perplexity_concurrency` | `int` | `8` | Perplexity engine concurrency |
| `gap_analysis_s3_max_retries` | `int` | `2` | S3 retry count |
| `gap_analysis_s3_retry_base_delay_s` | `float` | `2.0` | S3 retry base delay |
| `gap_analysis_s3_circuit_breaker_threshold` | `int` | `5` | Circuit breaker threshold |
| `gap_analysis_s4_fetch_concurrency` | `int` | `40` | S4 fetch concurrency |
| `gap_analysis_s4_parse_workers` | `int` | `16` | S4 parse workers |
| `gap_analysis_s4_http_pool_size` | `int` | `50` | S4 HTTP pool size |
| `gap_analysis_s5_embed_batch_size` | `int` | `256` | S5 embedding batch size |
| `gap_analysis_s5_embed_concurrent_batches` | `int` | `6` | S5 concurrent batches |
| `gap_analysis_query_gen_model` | `str` | `"gpt-5.2-2025-12-11"` | Query gen model |
| `gap_analysis_report_model` | `str` | `"openai/gpt-5.2-2025-12-11"` | Report gen model |
| `gap_analysis_openai_engine_model` | `str` | `"gpt-5.2-2025-12-11"` | OpenAI engine model |
| `gap_analysis_claude_engine_model` | `str` | `"claude-sonnet-4-6"` | Claude engine model |
| `gap_analysis_gemini_engine_model` | `str` | `"gemini-3-flash-preview"` | Gemini engine model |

##### Research Knowledge Base

| Field | Type | Default |
|-------|------|---------|
| `research_kb_project` | `str` | `"research-kb"` |
| `research_kb_company_overview_model` | `str` | `"sonar-deep-research"` |
| `research_kb_customer_reviews_model` | `str` | `"sonar-deep-research"` |
| `research_kb_competitor_scanner_model` | `str` | `"sonar-deep-research"` |
| `research_kb_competitor_extractor_model` | `str` | `"anthropic/claude-haiku-4-5"` |
| `research_kb_weakness_analyst_model` | `str` | `"sonar-deep-research"` |
| `research_kb_brand_perception_model` | `str` | `"claude-sonnet-4-6"` |
| `research_kb_synthesis_model` | `str` | `"anthropic/claude-opus-4-6"` |

##### Audience Persona

| Field | Type | Default |
|-------|------|---------|
| `audience_persona_suggester_model` | `str` | `"google/gemini-3-flash-preview"` |
| `audience_persona_generator_model` | `str` | `"sonar-deep-research"` |
| `audience_persona_max_concurrent_generators` | `int` | `3` |

##### Voice Style Guide

| Field | Type | Default |
|-------|------|---------|
| `voice_style_guide_discovery_model` | `str` | `"anthropic/claude-sonnet-4-6"` |
| `voice_style_guide_synthesis_model` | `str` | `"anthropic/claude-sonnet-4-6"` |
| `voice_style_guide_max_concurrent_researchers` | `int` | `3` |

##### Topic Discovery

| Field | Type | Default |
|-------|------|---------|
| `topic_discovery_brainstorm_model` | `str` | `"anthropic/claude-sonnet-4-6"` |
| `topic_discovery_dedup_model` | `str` | `"anthropic/claude-haiku-4-5"` |
| `topic_discovery_source_c_model` | `str` | `"perplexity/sonar-deep-research"` |
| `topic_discovery_unified_s2_model` | `str` | `"anthropic/claude-sonnet-4-6"` |
| `topic_discovery_max_expansion_rounds` | `int` | `4` |
| `topic_discovery_max_concurrent_sources` | `int` | `4` |
| `topic_discovery_source_timeout_s` | `float` | `120.0` |
| `topic_discovery_source_c_timeout_s` | `float` | `900.0` |
| `topic_discovery_expansion_timeout_s` | `float` | `300.0` |
| `topic_discovery_dedup_threshold` | `float` | `0.85` |
| `topic_discovery_scoring_similarity_threshold` | `float` | `0.60` |
| `topic_discovery_max_subdomains_to_expand` | `int` | `20` |
| `topic_discovery_scoring_weights` | `str` | JSON (source_confidence=0.3, content_coverage=0.2, gap_severity=0.25, persona_breadth=0.25) |
| `topic_discovery_persona_affinity_weights` | `str` | JSON (provenance=0.6, embedding=0.4) |
| `topic_discovery_expansion_max_retries` | `int` | `2` |
| `topic_discovery_expansion_retry_base_delay_s` | `float` | `2.0` |
| `topic_discovery_expansion_db_max_retries` | `int` | `3` |
| `topic_discovery_expansion_circuit_breaker_threshold` | `int` | `5` |
| `td_cannibalization_threshold` | `float` | `0.80` |
| `td_cannibalization_max_matches` | `int` | `5` |

##### Daily Tracker

| Field | Type | Default |
|-------|------|---------|
| `daily_tracker_fanout_model` | `str` | `"anthropic/claude-sonnet-4-6"` |
| `daily_tracker_fanout_target_count` | `int` | `15` |
| `daily_tracker_fanout_temperature` | `float` | `0.3` |
| `daily_tracker_response_retention_days` | `int` | `30` |

##### CPS Model

| Field | Type | Default |
|-------|------|---------|
| `cps_enabled` | `bool` | `True` |
| `cps_target_weight` | `float` | `0.5` |

##### Logging

| Field | Type | Default |
|-------|------|---------|
| `log_level` | `Literal["DEBUG","INFO","WARNING","ERROR","CRITICAL"]` | `"INFO"` |
| `log_format` | `Literal["console","json"]` | `"console"` |
| `log_include_caller` | `bool` | `False` |

##### LangSmith

| Field | Type | Default |
|-------|------|---------|
| `langsmith_api_key` | `str \| None` | `None` |
| `langsmith_workspace_id` | `str \| None` | `None` |
| `langsmith_project` | `str` | `"content-engine"` |
| `langsmith_use_hub` | `bool` | `False` |
| `langsmith_hub_tag` | `str` | `"production"` |
| `gap_analysis_langsmith_project` | `str` | `"gap-analysis"` |
| `audience_persona_langsmith_project` | `str` | `"audience-persona"` |
| `voice_style_guide_langsmith_project` | `str` | `"voice-style-guide"` |
| `topic_discovery_langsmith_project` | `str` | `"topic-discovery"` |
| `onboarding_langsmith_project` | `str` | `"onboarding"` |

##### Storage & CMS

| Field | Type | Default |
|-------|------|---------|
| `storage_backend` | `Literal["local","r2"]` | `"r2"` |
| `r2_account_id` | `str \| None` | `None` |
| `r2_access_key_id` | `str \| None` | `None` |
| `r2_secret_access_key` | `str \| None` | `None` |
| `r2_bucket_name` | `str \| None` | `None` |
| `r2_endpoint_url` | `str \| None` | `None` |
| `cms_fernet_key` | `str \| None` | `None` |
| `auto_prompt_max_pages` | `int` | `50` |

##### Google Analytics (GA4)

| Field | Type | Default |
|-------|------|---------|
| `google_oauth_client_id` | `str \| None` | `None` |
| `google_oauth_client_secret` | `str \| None` | `None` |
| `google_oauth_redirect_uri` | `str` | `"https://app.deeppresence.ai/api/v1/analytics/google/callback"` |
| `google_oauth_frontend_settings_url` | `str` | `"https://app.deeppresence.ai/settings?tab=integrations"` |
| `ga4_sync_lookback_days` | `int` | `7` |
| `ga4_sync_api_key` | `str` | `""` |
| `ai_referral_sources` | `str` | Comma-separated domain→platform mapping |

##### Site Audit

| Field | Type | Default |
|-------|------|---------|
| `site_audit_max_pages` | `int` | `200` |
| `site_audit_max_depth` | `int` | `4` |
| `site_audit_concurrency` | `int` | `30` |
| `site_audit_request_timeout` | `float` | `15.0` |
| `site_audit_max_redirects` | `int` | `5` |

##### Auth & Misc

| Field | Type | Default |
|-------|------|---------|
| `invite_ttl_days` | `int` | `7` |
| `aeo_agent_invoke_timeout_s` | `int` | `900` |
| `platform_cache_ttl_days` | `int` | `7` |
| `url_enrichment_cache_ttl_days` | `int` | `14` |

##### Supabase (Legacy)

| Field | Type | Default |
|-------|------|---------|
| `supabase_url` | `str \| None` | `None` |
| `supabase_service_role_key` | `str \| None` | `None` |
| `supabase_anon_key` | `str \| None` | `None` |
| `supabase_agent_id` | `str \| None` | `None` |

**Computed Properties:** `effective_supabase_url`, `effective_supabase_anon_key`, `effective_supabase_key`, `effective_r2_endpoint_url`, `database_url_sync`

## Integration Points

- **Every module** imports `from core.config import settings` to access configuration
- The singleton is created at module level on first import
- Environment variable names match field names (case-insensitive, Pydantic default behavior)
- `.env.local` overrides `.env` (later files take precedence)

## Common Patterns

```python
from core.config import settings

# Access any setting
api_key = settings.openrouter_api_key
db_url = settings.database_url

# Computed properties
sync_url = settings.database_url_sync  # For Alembic
r2_endpoint = settings.effective_r2_endpoint_url  # Auto-derived
```
