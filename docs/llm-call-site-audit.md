# LLM Call Site Audit — Complete Inventory

> **Date:** 2026-03-29
> **Purpose:** Catalog every LLM call in the codebase to plan migration to OpenRouter for centralized cost tracking.

---

## Summary

| Category | Call Sites | Sync | Async | SDK / Method |
|----------|-----------|------|-------|--------------|
| **Anthropic (direct SDK)** | 3 | 0 | 3 | `anthropic.AsyncAnthropic` / `client.messages.create` |
| **Anthropic (raw HTTP)** | 1 | 0 | 1 | `httpx.AsyncClient` → `api.anthropic.com` |
| **OpenAI (direct SDK)** | 4 | 0 | 4 | `openai.AsyncOpenAI` / `client.responses.create` |
| **Google Gemini (direct SDK)** | 1 | 0 | 1 | `google.genai` / `client.aio.models.generate_content` |
| **Google Gemini (raw HTTP)** | 1 | 0 | 1 | `httpx.AsyncClient` → `generativelanguage.googleapis.com` |
| **Google Gemini (LangChain)** | 1 | 1 | 0 | `langchain_google_genai.ChatGoogleGenerativeAI` / `.invoke()` |
| **LangChain `init_chat_model`** | 1 | 0 | 1 | LangGraph `create_react_agent` / `.ainvoke()` |
| **Perplexity (direct SDK)** | 1 | 1 | 0 | `Perplexity` / `client.chat.completions.create` |
| **Perplexity (async SDK)** | 1 | 0 | 1 | `AsyncPerplexity` / `pplx_client.chat.completions.create` |
| **LiteLLM (content engine)** | 1 wrapper, 11 callers | 0 | 12 | `litellm.acompletion` via `llm_call()` |
| **LiteLLM (topic discovery)** | 1 wrapper, 8+ callers | 0 | 9+ | `litellm.acompletion` via `_run_completion()` |
| **LiteLLM (voice style guide)** | 2 | 0 | 2 | `litellm.acompletion` direct |
| **OpenAI Embeddings (sync)** | 1 | 1 | 0 | `openai.OpenAI` / `client.embeddings.create` |
| **OpenAI Embeddings (async)** | 1 | 0 | 1 | `openai.AsyncOpenAI` / `client.embeddings.create` |
| **Perplexity via `perplexity_client`** | 5 indirect callers | 0 | 5 | `asyncio.to_thread(perplexity_client.research, ...)` |
| **TOTAL** | **~53 call sites** | **3** | **~50** | — |

---

## Detailed Call Sites by Pipeline

---

### Pipeline 0 — Site Audit

**No LLM calls.** Fully deterministic (crawler + scoring). No migration needed.

---

### Pipeline 1a — Knowledge Base (6-agent DAG)

#### KB-1: Company Overview Agent
| Field | Value |
|-------|-------|
| **File** | `core/research/knowledge_base/agents.py` |
| **Function** | `agent_kb_company_overview()` → calls `_run_perplexity_agent()` |
| **Call Line** | ~L159-165 (inside `_run_perplexity_agent`) |
| **SDK** | `perplexity_client.research()` (sync) wrapped in `asyncio.to_thread()` |
| **Model** | `sonar-deep-research` (from `settings.perplexity_deep_research_model`) |
| **Sync/Async** | Sync SDK call, wrapped async |

#### KB-2: Customer Reviews Agent
| Field | Value |
|-------|-------|
| **File** | `core/research/knowledge_base/agents.py` |
| **Function** | `agent_kb_customer_reviews()` → calls `_run_perplexity_agent()` |
| **Call Line** | ~L159-165 (inside `_run_perplexity_agent`) |
| **SDK** | `perplexity_client.research()` (sync) wrapped in `asyncio.to_thread()` |
| **Model** | `sonar-deep-research` |
| **Sync/Async** | Sync SDK call, wrapped async |

#### KB-3: Competitor Scanner Agent
| Field | Value |
|-------|-------|
| **File** | `core/research/knowledge_base/agents.py` |
| **Function** | `agent_kb_competitor_scanner()` → calls `_run_perplexity_agent()` |
| **Call Line** | ~L159-165 (inside `_run_perplexity_agent`) |
| **SDK** | `perplexity_client.research()` (sync) wrapped in `asyncio.to_thread()` |
| **Model** | `sonar-deep-research` |
| **Sync/Async** | Sync SDK call, wrapped async |

#### KB-4: Weakness Analyst Agent
| Field | Value |
|-------|-------|
| **File** | `core/research/knowledge_base/agents.py` |
| **Function** | `agent_kb_weakness_analyst()` → calls `_run_perplexity_agent()` |
| **Call Line** | ~L159-165 (inside `_run_perplexity_agent`) |
| **SDK** | `perplexity_client.research()` (sync) wrapped in `asyncio.to_thread()` |
| **Model** | `sonar-deep-research` |
| **Sync/Async** | Sync SDK call, wrapped async |

#### KB-5: Brand Perception Agent
| Field | Value |
|-------|-------|
| **File** | `core/research/knowledge_base/agents.py` |
| **Function** | `run_brand_perception_agent()` |
| **Call Lines** | L307 (client init), L316 (initial call), L353 (continuation/pause_turn loop) |
| **SDK** | `anthropic.AsyncAnthropic()` → `client.messages.create()` |
| **Model** | `claude-sonnet-4-6` (from `settings.research_kb_brand_perception_model`) |
| **Sync/Async** | **Async** |
| **Special** | Uses `web_search_20250305` server-side tool. Pause_turn continuation loop (max 5 turns). |

#### KB-6: Synthesis Agent
| Field | Value |
|-------|-------|
| **File** | `core/research/knowledge_base/agents.py` |
| **Function** | `run_synthesis_agent()` |
| **Call Lines** | L67-98 (`_build_model`), L511 (model build), L519 (`create_react_agent`) |
| **SDK** | `langchain.chat_models.init_chat_model()` → LangGraph `create_react_agent().ainvoke()` |
| **Model** | `claude-opus-4-6` (from `settings.research_kb_synthesis_model`) |
| **Sync/Async** | **Async** (via LangGraph `.ainvoke()`) |
| **Special** | LangGraph ReAct agent with file-reading tool. LangChain tracer. **Hardest to migrate** — not a simple chat completion call. |

---

### Pipeline 1b — Audience Persona

#### AP-1: Persona Suggester
| Field | Value |
|-------|-------|
| **File** | `core/research/audience_persona/agents.py` |
| **Function** | `run_persona_suggester()` |
| **Call Lines** | L199 (client init), L216 (initial call), L252 (retry call) |
| **SDK** | `google.genai.Client()` → `client.aio.models.generate_content()` |
| **Model** | `gemini-3-flash-preview` (from `settings.audience_persona_suggester_model`) |
| **Sync/Async** | **Async** |
| **Special** | Uses `genai_types.GenerateContentConfig()` with `response_mime_type="application/json"`. Retry with validation. |

#### AP-2: Persona Profile Generator
| Field | Value |
|-------|-------|
| **File** | `core/research/audience_persona/agents.py` |
| **Function** | `run_persona_profile_generator()` |
| **Call Lines** | L340-346 |
| **SDK** | `perplexity_client.research()` (sync) wrapped in `asyncio.to_thread()` |
| **Model** | `sonar-deep-research` (from `settings.audience_persona_generator_model`) |
| **Sync/Async** | Sync SDK call, wrapped async |

---

### Pipeline 1c — Voice Style Guide

#### VSG-1: Author Discovery
| Field | Value |
|-------|-------|
| **File** | `core/research/voice_style_guide/agents.py` |
| **Function** | `run_author_discovery()` → calls `_run_discovery_completion()` |
| **Call Lines** | L120 (inside `_run_discovery_completion`), called at L425, L463 |
| **SDK** | `litellm.acompletion()` |
| **Model** | `settings.voice_style_guide_discovery_model` (Claude Sonnet via LiteLLM) |
| **Sync/Async** | **Async** |
| **Special** | Pause_turn continuation (max 3 turns). |

#### VSG-2: Author Research
| Field | Value |
|-------|-------|
| **File** | `core/research/voice_style_guide/agents.py` |
| **Function** | `run_author_research()` |
| **Call Lines** | L545-552 |
| **SDK** | `perplexity_client.research()` (sync) wrapped in `asyncio.to_thread()` |
| **Model** | `sonar-deep-research` (from `settings.perplexity_deep_research_model`) |
| **Sync/Async** | Sync SDK call, wrapped async |

#### VSG-3: Voice Synthesis
| Field | Value |
|-------|-------|
| **File** | `core/research/voice_style_guide/agents.py` |
| **Function** | `run_voice_synthesis_agent()` |
| **Call Line** | L634 |
| **SDK** | `litellm.acompletion()` |
| **Model** | `claude-sonnet-4-6` (from `settings.voice_style_guide_synthesis_model`) |
| **Sync/Async** | **Async** |

---

### Pipeline 2 — Gap Analysis (8 steps)

#### GA-S1: Embed Assets
| Field | Value |
|-------|-------|
| **File** | `core/gap_analysis/steps/s1_embed_assets.py` |
| **Call Line** | ~L136+ |
| **SDK** | `async_embed_texts()` → `openai.AsyncOpenAI().embeddings.create()` |
| **Model** | `text-embedding-3-small` (from `settings.embedding_model`) |
| **Sync/Async** | **Async** |
| **Type** | **Embedding** (not chat completion) |

#### GA-S2: Generate Queries
| Field | Value |
|-------|-------|
| **File** | `core/gap_analysis/steps/s2_generate_queries.py` |
| **Call Lines** | L171 (LLM call), L396 + L781 (embedding calls) |
| **SDK (LLM)** | `openai.AsyncOpenAI()` → `client.responses.create()` |
| **SDK (Embed)** | `async_embed_texts()` → `openai.AsyncOpenAI().embeddings.create()` |
| **Model (LLM)** | `settings.gap_analysis_openai_engine_model` (reasoning model, e.g. `gpt-5.2-2025-12-11`) |
| **Model (Embed)** | `text-embedding-3-small` |
| **Sync/Async** | **Async** |
| **Special** | Uses `reasoning={"effort": "medium"}`, `max_output_tokens=16384` |

#### GA-S3: Search Platforms (4 engines)
| Field | Value |
|-------|-------|
| **File** | `core/gap_analysis/steps/s3_search_platforms.py` |
| **Function** | `_run_engine_batch()` |
| **Call Lines** | L308-316 (client init per engine), L166 (engine.search dispatch) |
| **Engines** | OpenAI, Claude, Gemini, Perplexity (all 4 called) |
| **Sync/Async** | **Async** |
| **Special** | Per-engine rate limiting, circuit breaker, retry logic. Shared async client per engine type. |

**Engine: OpenAI** (`core/gap_analysis/engines/openai_engine.py`)
| Field | Value |
|-------|-------|
| **Call Lines** | L49 (primary w/ web_search), L72 (fallback) |
| **SDK** | `openai.AsyncOpenAI()` → `client.responses.create()` |
| **Model** | `settings.gap_analysis_openai_engine_model` (e.g. `gpt-5.2-2025-12-11`) |
| **Sync/Async** | **Async** |
| **Special** | Uses `reasoning={"effort": "low"}`, `tools=[{"type": "web_search"}]`, `include=["web_search_call.action.sources"]` |

**Engine: Claude** (`core/gap_analysis/engines/claude.py`)
| Field | Value |
|-------|-------|
| **Call Lines** | L119-123 |
| **SDK** | **Raw HTTP** via `httpx.AsyncClient` → POST `https://api.anthropic.com/v1/messages` |
| **Model** | `claude-sonnet-4-6` (from `settings.gap_analysis_claude_engine_model`) |
| **Sync/Async** | **Async** |
| **Special** | Uses `web-search-2025-03-05` beta header. Temperature 0.3. Raw HTTP, not SDK. |

**Engine: Gemini** (`core/gap_analysis/engines/gemini.py`)
| Field | Value |
|-------|-------|
| **Call Lines** | L74-93 |
| **SDK** | **Raw HTTP** via `httpx.AsyncClient` → POST `generativelanguage.googleapis.com/v1beta` |
| **Model** | `gemini-3-flash-preview` (from `settings.gap_analysis_gemini_engine_model`) |
| **Sync/Async** | **Async** |
| **Special** | Uses `google_search` grounding tool. Temperature 0. Raw HTTP, not SDK. |

**Engine: Perplexity** (`core/gap_analysis/engines/perplexity.py`)
| Field | Value |
|-------|-------|
| **Call Lines** | L25-26 |
| **SDK** | `AsyncPerplexity()` → `pplx_client.chat.completions.create()` |
| **Model** | `sonar-pro` (from `settings.perplexity_search_model`) |
| **Sync/Async** | **Async** |

#### GA-S5: Embed Content
| Field | Value |
|-------|-------|
| **File** | `core/gap_analysis/steps/s5_embed_content.py` |
| **Call Lines** | L163 (query embedding), L281 (citation bulk embedding) |
| **SDK** | `async_embed_texts()` → `openai.AsyncOpenAI().embeddings.create()` |
| **Model** | `text-embedding-3-small` |
| **Sync/Async** | **Async** |
| **Type** | **Embedding** |

#### GA-S8: Generate Report
| Field | Value |
|-------|-------|
| **File** | `core/gap_analysis/steps/s8_generate_report.py` |
| **Call Line** | L35 |
| **SDK** | `openai.AsyncOpenAI()` → `client.responses.create()` |
| **Model** | `settings.gap_analysis_report_model` (e.g. `gpt-5.2-2025-12-11`) |
| **Sync/Async** | **Async** |

---

### Pipeline 3 — Content Engine v1.3

All v1.3 calls go through the **centralized `llm_call()` wrapper** in `core/content_engine/llm_client.py` (L197), which calls `litellm.acompletion()`.

#### CE-0: Content Planner (LEGACY v1.0 — still active)
| Field | Value |
|-------|-------|
| **File** | `core/content_engine/planner.py` |
| **Function** | `plan_content()` |
| **Call Lines** | L122 (client init), L125 (`client.messages.create`) |
| **SDK** | `anthropic.AsyncAnthropic()` → `client.messages.create()` |
| **Model** | `claude-opus-4-6` (from `settings.content_engine_planner_model`) |
| **Sync/Async** | **Async** |
| **Special** | Uses custom `_retry_async_anthropic()` wrapper. Max_tokens=16384. **Direct Anthropic SDK — NOT routed through LiteLLM.** |

#### CE-1: Strategic Planner (v1.3)
| Field | Value |
|-------|-------|
| **File** | `core/content_engine/strategic_planner.py` |
| **Function** | `plan_content_strategy()` |
| **Call Line** | L81 → `llm_call()` |
| **SDK** | LiteLLM via `llm_call()` |
| **Model** | `settings.content_engine_v13_planner_model` (Claude Sonnet) |
| **Sync/Async** | **Async** |

#### CE-2: Brief Builder (v1.3)
| Field | Value |
|-------|-------|
| **File** | `core/content_engine/brief_builder.py` |
| **Function** | `build_brief()` |
| **Call Line** | L100 → `llm_call()` |
| **SDK** | LiteLLM via `llm_call()` |
| **Model** | `settings.content_engine_v13_brief_model` (Claude Sonnet) |
| **Sync/Async** | **Async** |

#### CE-3: Outliner Worker (v1.3)
| Field | Value |
|-------|-------|
| **File** | `core/content_engine/workers/outliner.py` |
| **Function** | `generate_outline()` |
| **Call Line** | L77 → `llm_call()` |
| **SDK** | LiteLLM via `llm_call()` |
| **Model** | `settings.content_engine_v13_outliner_model` (Claude Sonnet) |
| **Sync/Async** | **Async** |

#### CE-4: Drafter Worker (v1.3)
| Field | Value |
|-------|-------|
| **File** | `core/content_engine/workers/drafter.py` |
| **Function** | `draft_content()` / `revise_content()` |
| **Call Lines** | L82 → `llm_call()` (draft), L218 → `llm_call()` (revise) |
| **SDK** | LiteLLM via `llm_call()` |
| **Model** | `settings.content_engine_v13_drafter_model` (Claude Sonnet) |
| **Sync/Async** | **Async** |

#### CE-5: Fact Enricher Worker (v1.3)
| Field | Value |
|-------|-------|
| **File** | `core/content_engine/workers/fact_enricher.py` |
| **Function** | `enrich_facts()` |
| **Call Line** | L84 → `llm_call()` |
| **SDK** | LiteLLM via `llm_call()` |
| **Model** | `perplexity/sonar-pro` (from `settings.content_engine_v13_fact_enricher_model`) |
| **Sync/Async** | **Async** |

#### CE-6: Formatter Worker (v1.3)
| Field | Value |
|-------|-------|
| **File** | `core/content_engine/workers/formatter.py` |
| **Function** | `format_content()` |
| **Call Line** | L88 → `llm_call()` |
| **SDK** | LiteLLM via `llm_call()` |
| **Model** | `settings.content_engine_v13_formatter_model` (Claude Haiku) |
| **Sync/Async** | **Async** |

#### CE-7: Linker Worker (v1.3)
| Field | Value |
|-------|-------|
| **File** | `core/content_engine/workers/linker.py` |
| **Function** | `generate_links()` |
| **Call Line** | L96 → `llm_call()` |
| **SDK** | LiteLLM via `llm_call()` |
| **Model** | `perplexity/sonar-pro` (from `settings.content_engine_v13_linker_model`) |
| **Sync/Async** | **Async** |

#### CE-8: E-E-A-T Judge (v1.3)
| Field | Value |
|-------|-------|
| **File** | `core/content_engine/evaluator/eeat_judge.py` |
| **Function** | `evaluate_eeat()` |
| **Call Line** | L74 → `llm_call()` |
| **SDK** | LiteLLM via `llm_call()` |
| **Model** | `settings.content_engine_v13_eeat_judge_model` (Claude Sonnet) |
| **Sync/Async** | **Async** |

#### CE-9: Style Judge (v1.3)
| Field | Value |
|-------|-------|
| **File** | `core/content_engine/evaluator/style_judge.py` |
| **Function** | `evaluate_style()` |
| **Call Line** | L68 → `llm_call()` |
| **SDK** | LiteLLM via `llm_call()` |
| **Model** | `settings.content_engine_v13_style_judge_model` (Claude Haiku) |
| **Sync/Async** | **Async** |

#### CE-10: Factual Judge (v1.3)
| Field | Value |
|-------|-------|
| **File** | `core/content_engine/evaluator/factual_judge.py` |
| **Function** | `evaluate_factual()` |
| **Call Line** | L70 → `llm_call()` |
| **SDK** | LiteLLM via `llm_call()` |
| **Model** | `settings.content_engine_v13_factual_judge_model` (Claude Sonnet) |
| **Sync/Async** | **Async** |

---

### Pipeline 4 — Topic Discovery

All Topic Discovery LLM calls go through `_run_completion()` helper in `core/topic_discovery/agents.py` (L190), which calls `litellm.acompletion()`.

#### TD-1: Source A — Company Brainstorm
| Field | Value |
|-------|-------|
| **File** | `core/topic_discovery/agents.py` |
| **Function** | `run_source_a_company_brainstorm()` |
| **Call Line** | L349 → `_run_completion()` → L190 `litellm.acompletion()` |
| **Model** | `settings.topic_discovery_brainstorm_model` (Claude Sonnet) |
| **Sync/Async** | **Async** |

#### TD-2: Source B — Persona Brainstorm
| Field | Value |
|-------|-------|
| **File** | `core/topic_discovery/agents.py` |
| **Function** | `run_source_b_persona_brainstorm()` |
| **Call Line** | L487 → `_run_completion()` |
| **Model** | `settings.topic_discovery_brainstorm_model` (Claude Sonnet) |
| **Sync/Async** | **Async** |

#### TD-3: Source C — Deep Research (Competitive)
| Field | Value |
|-------|-------|
| **File** | `core/topic_discovery/agents.py` |
| **Function** | `run_source_c_deep_research()` |
| **Call Lines** | L598-606 |
| **SDK** | `perplexity_client.research()` (sync) wrapped in `asyncio.to_thread()` |
| **Model** | `sonar-deep-research` (from `settings.topic_discovery_source_c_model`) |
| **Sync/Async** | Sync SDK call, wrapped async |
| **Special** | **NOT routed through LiteLLM** — uses Perplexity client directly. 900s timeout. |

#### TD-4: Source D — Adversarial Brainstorm
| Field | Value |
|-------|-------|
| **File** | `core/topic_discovery/agents.py` |
| **Function** | `run_source_d_adversarial()` |
| **Call Line** | L742 → `_run_completion()` |
| **Model** | `settings.topic_discovery_brainstorm_model` (Claude Sonnet) |
| **Sync/Async** | **Async** |

#### TD-5: Hierarchy Construction
| Field | Value |
|-------|-------|
| **File** | `core/topic_discovery/agents.py` |
| **Function** | `run_hierarchy_construction()` |
| **Call Lines** | L938, L968 → `_run_completion()` (2 attempts) |
| **Model** | `settings.topic_discovery_brainstorm_model` (Claude Sonnet) |
| **Sync/Async** | **Async** |

#### TD-6: Unified Hierarchy + Scoring
| Field | Value |
|-------|-------|
| **File** | `core/topic_discovery/agents.py` |
| **Function** | `run_unified_hierarchy_and_scoring()` |
| **Call Lines** | L1052, L1100 → `_run_completion()` (2 attempts) |
| **Model** | `settings.topic_discovery_unified_s2_model` (Claude Sonnet) |
| **Sync/Async** | **Async** |

#### TD-7: Relevance Filtering
| Field | Value |
|-------|-------|
| **File** | `core/topic_discovery/agents.py` |
| **Function** | `run_relevance_filtering()` |
| **Call Line** | L1344 → `_run_completion()` |
| **Model** | `settings.topic_discovery_dedup_model` (Claude Haiku) |
| **Sync/Async** | **Async** |

#### TD-8: Topic Generation
| Field | Value |
|-------|-------|
| **File** | `core/topic_discovery/agents.py` |
| **Function** | `run_topic_generation()` |
| **Call Line** | L1401 → `_run_completion()` |
| **Model** | `settings.topic_discovery_brainstorm_model` (Claude Sonnet) |
| **Sync/Async** | **Async** |

#### TD-9: Subdomain Expansion
| Field | Value |
|-------|-------|
| **File** | `core/topic_discovery/agents.py` |
| **Function** | `run_subdomain_expansion()` |
| **Call Line** | L1506 → `_run_completion()` |
| **Model** | `settings.topic_discovery_brainstorm_model` (Claude Sonnet) |
| **Sync/Async** | **Async** |

---

### CPS Model — Embeddings Only

#### CPS-1: Scorer Embeddings
| Field | Value |
|-------|-------|
| **File** | `core/cps_model/scorer.py` |
| **Call Lines** | L355 (sync fallback), L395 (async) |
| **SDK** | `embed_texts()` / `async_embed_texts()` → OpenAI embeddings |
| **Model** | `text-embedding-3-small` |
| **Type** | **Embedding** |

---

### Daily Tracker

#### DT-1: Platform Runner (4 engines)
| Field | Value |
|-------|-------|
| **File** | `core/daily_tracker/platform_runner.py` |
| **Function** | `PlatformRunnerService._run_one()` |
| **Call Line** | L198 → `engine.search()` |
| **SDK** | Delegates to the same 4 gap analysis engines (OpenAI, Claude, Gemini, Perplexity) |
| **Models** | Same as GA-S3 engines |
| **Sync/Async** | **Async** |
| **Special** | **Reuses gap analysis engine classes** — no separate LLM code. Changing GA engines changes DT automatically. |

---

### Reddit HIL Monitor

#### RH-1: Thread Selection + Draft Generation
| Field | Value |
|-------|-------|
| **File** | `core/reddit_hil/graph.py` |
| **Function** | `_llm_select_and_draft()` via `_get_llm()` |
| **Call Lines** | L189-201 (LLM init), L288 (`llm.invoke()`) |
| **SDK** | `langchain_google_genai.ChatGoogleGenerativeAI` → `.invoke()` |
| **Model** | `gemini-3-flash-preview` (from `settings.google_gemini_model_reddit_hil`) |
| **Sync/Async** | **Sync** (LangChain `.invoke()`) |
| **Special** | LangChain wrapper. Single LLM call per monitoring cycle. |

---

### Shared Embedding Infrastructure

#### EMB-1: Sync Embedding Client
| Field | Value |
|-------|-------|
| **File** | `core/shared_tools/embedding_client.py` |
| **Function** | `embed_texts()` |
| **Call Line** | L39 |
| **SDK** | `openai.OpenAI()` → `client.embeddings.create()` |
| **Model** | `text-embedding-3-small` (from `settings.embedding_model`) |
| **Sync/Async** | **Sync** |
| **Special** | Batch processing (batch_size=64). Used by CPS scorer fallback. |

#### EMB-2: Async Embedding Client
| Field | Value |
|-------|-------|
| **File** | `core/shared_tools/async_embedding_client.py` |
| **Function** | `async_embed_texts()` |
| **Call Line** | L156 |
| **SDK** | `openai.AsyncOpenAI()` → `client.embeddings.create()` |
| **Model** | `text-embedding-3-small` (from `settings.embedding_model`) |
| **Sync/Async** | **Async** |
| **Special** | Chunking for long texts (max 8191 tokens), mean-pooling, retry logic, semaphore (6 concurrent). |

---

### Shared Perplexity Infrastructure

#### PPLX-1: Perplexity Research Client
| Field | Value |
|-------|-------|
| **File** | `core/research/tools/perplexity_client.py` |
| **Function** | `research()` / `search()` |
| **Call Line** | L57 |
| **SDK** | `Perplexity()` → `client.chat.completions.create()` |
| **Model** | `sonar-deep-research` (default) |
| **Sync/Async** | **Sync** |
| **Callers** | KB agents (4), AP profile gen (1), VSG author research (1), TD source C (1) — all via `asyncio.to_thread()` |

---

## Onboarding (Pipeline 5)

**No direct LLM calls.** Orchestrates other pipelines (KB, AP, VSG). No migration needed.

---

## OpenRouter Migration Plan

### Why OpenRouter

OpenRouter provides a unified OpenAI-compatible API (`chat.completions.create`) that routes to 200+ models across providers. It gives us **centralized cost tracking per API key** — the primary motivation for this migration. Every call routed through OpenRouter shows up in a single billing dashboard with per-model, per-request cost breakdowns.

### What OpenRouter supports
- Standard `chat.completions.create` (system + user messages in, text/JSON out)
- All major models: Claude, GPT, Gemini, Perplexity Sonar, Llama, Mistral, etc.
- `response_format` for structured JSON output
- Streaming
- Embeddings (via `openai/text-embedding-3-small` etc.)

### What OpenRouter does NOT support
- **Anthropic `web_search_20250305` server-side tool** — Claude's built-in web browsing
- **Google `google_search` grounding** — Gemini's native Google Search integration with `groundingMetadata`
- **OpenAI `responses.create` API** — the newer API with `reasoning` parameter and `web_search` tool
- **Provider-specific beta headers** (e.g. `anthropic-beta: web-search-2025-03-05`)
- **LangGraph/LangChain model wrappers** — OpenRouter doesn't ship a LangChain `ChatModel` class (though you can point `ChatOpenAI` at OpenRouter's base URL)

---

### MIGRATE TO OPENROUTER (~37 call sites, ~10 files to change)

These are standard chat completions and embeddings — no provider-specific features needed. OpenRouter handles them natively.

#### Group 1: Centralized wrappers (change 3 files, migrate ~26 callers)

| Wrapper | File to change | Callers auto-migrated | Current SDK | How to migrate |
|---------|---------------|----------------------|-------------|----------------|
| `llm_call()` | `core/content_engine/llm_client.py` | CE-1 through CE-10 (11 callers: strategic planner, brief builder, outliner, drafter x2, fact enricher, formatter, linker, eeat judge, style judge, factual judge) | `litellm.acompletion()` | Swap to `openai.AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_KEY).chat.completions.create()`. Model strings already use `provider/model` format which OpenRouter accepts. |
| `_run_completion()` | `core/topic_discovery/agents.py` | TD-1, TD-2, TD-4 through TD-9 (8+ callers: company brainstorm, persona brainstorm, adversarial, hierarchy x2, unified scoring x2, relevance filtering, topic gen, subdomain expansion) | `litellm.acompletion()` | Same swap as above. |
| `perplexity_client.research()` | `core/research/tools/perplexity_client.py` | KB-1 to KB-4, AP-2, VSG-2, TD-3 (7 callers: company overview, customer reviews, competitors, weakness, persona profile gen, author research, source C deep research) | `Perplexity()` SDK | Swap to OpenRouter `chat.completions.create` with `perplexity/sonar-deep-research` model string. Perplexity models are available on OpenRouter. |

#### Group 2: Direct SDK calls — straightforward swap (change 5 files, migrate ~7 callers)

| Call Site ID | File | Current SDK | Model | How to migrate |
|-------------|------|-------------|-------|----------------|
| **CE-0** | `core/content_engine/planner.py` | `anthropic.AsyncAnthropic().messages.create()` | `claude-opus-4-6` | Replace with OpenRouter async client. Standard chat completion — no tools, no web search. Drop `_retry_async_anthropic()` wrapper; use OpenRouter's built-in retry or rewrite retry around new client. |
| **AP-1** | `core/research/audience_persona/agents.py` | `google.genai.Client().aio.models.generate_content()` | `gemini-3-flash-preview` | Replace with OpenRouter async client. Drop `response_mime_type="application/json"` (Gemini-specific); use `response_format={"type": "json_object"}` instead (OpenAI-compatible, supported by OpenRouter). Keep the validation + retry logic. |
| **VSG-1** | `core/research/voice_style_guide/agents.py` L120 | `litellm.acompletion()` | Claude Sonnet | Swap to OpenRouter. Already uses standard chat completion format. Note: `pause_turn` stop_reason handling — verify OpenRouter surfaces Anthropic's `pause_turn` finish reason. If not, cap to single turn. |
| **VSG-3** | `core/research/voice_style_guide/agents.py` L634 | `litellm.acompletion()` | Claude Sonnet | Swap to OpenRouter. Standard completion, no special features. |
| **GA-S8** | `core/gap_analysis/steps/s8_generate_report.py` | `openai.AsyncOpenAI().responses.create()` | GPT-5.2 | Replace with OpenRouter `chat.completions.create`. This call uses no tools, no reasoning param — just prompt in, text out. The `responses.create` API is just being used as a plain completion here. |
| **GA-PPLX** | `core/gap_analysis/engines/perplexity.py` | `AsyncPerplexity().chat.completions.create()` | `sonar-pro` | Swap to OpenRouter. Already OpenAI-compatible format. Change `AsyncPerplexity` to `AsyncOpenAI(base_url=openrouter_url)` with `perplexity/sonar-pro` model. |

#### Group 3: Embeddings (change 2 files, all embedding callers cascade)

| Call Site ID | File | Current SDK | Model | How to migrate |
|-------------|------|-------------|-------|----------------|
| **EMB-1** | `core/shared_tools/embedding_client.py` | `openai.OpenAI().embeddings.create()` | `text-embedding-3-small` | Point `OpenAI(base_url=openrouter_url)` at OpenRouter. Model string: `openai/text-embedding-3-small`. Keep batch logic as-is. |
| **EMB-2** | `core/shared_tools/async_embedding_client.py` | `openai.AsyncOpenAI().embeddings.create()` | `text-embedding-3-small` | Same — point `AsyncOpenAI(base_url=openrouter_url)` at OpenRouter. Keep chunking/pooling/retry/semaphore logic untouched. |

**Cascade:** GA-S1, GA-S2 (embed), GA-S5, CPS-1 all route through EMB-1/EMB-2, so they're automatically migrated.

---

### DO NOT MIGRATE — Keep on native provider APIs (~16 call sites, 6 files)

These call sites depend on **provider-specific features** (web search tools, grounding, reasoning APIs, agent frameworks) that OpenRouter cannot replicate. Migrating them would break core functionality.

#### Web Search / Grounding engines (Gap Analysis + Daily Tracker)

| Call Site ID | File | Provider Feature | Why it must stay |
|-------------|------|-----------------|------------------|
| **GA-S3 Claude Engine** | `core/gap_analysis/engines/claude.py` | Anthropic `web_search_20250305` server-side tool | Claude actually browses the web and returns **cited URLs** in the response. This is the core of gap analysis — "what does Claude say about X, and what sources does it cite?" OpenRouter strips this capability; you'd get a plain text response with zero citations. |
| **GA-S3 Gemini Engine** | `core/gap_analysis/engines/gemini.py` | Google `google_search` grounding + `groundingMetadata` | Gemini searches Google and returns structured `groundingChunks[].web.uri` citation data. OpenRouter doesn't expose the `groundingMetadata` response field — citation extraction would break entirely. |
| **GA-S3 OpenAI Engine** | `core/gap_analysis/engines/openai_engine.py` | OpenAI `responses.create` + `web_search` tool + `reasoning` param | Uses the newer `responses.create` API (not `chat.completions.create`) with `reasoning={"effort": "low"}` and `tools=[{"type": "web_search"}]`. OpenRouter only supports the older `chat.completions.create` endpoint. Would lose both web search and reasoning capability. |
| **GA-S2 Query Gen** | `core/gap_analysis/steps/s2_generate_queries.py` | OpenAI `responses.create` + `reasoning={"effort": "medium"}` | Uses reasoning API for smarter query generation. Could theoretically fall back to `chat.completions.create`, but would degrade output quality. Keep on native API. |
| **DT-1 Platform Runner** | `core/daily_tracker/platform_runner.py` | Reuses all 4 GA engines | The daily tracker imports and delegates to the same `ClaudeEngine`, `GeminiEngine`, `OpenAIEngine`, `PerplexityEngine` classes. Whatever we do with GA engines, DT inherits automatically. Since the GA engines stay native, DT stays native too. |

**Why these matter:** Gap analysis and daily tracking exist to answer "what do AI platforms say about this topic?" The web search / grounding tools are **the entire point** — without them you get hallucinated answers with no source citations. There is no OpenRouter equivalent.

#### Anthropic Web Search (Knowledge Base)

| Call Site ID | File | Provider Feature | Why it must stay |
|-------------|------|-----------------|------------------|
| **KB-5 Brand Perception** | `core/research/knowledge_base/agents.py` | Anthropic `web_search_20250305` tool + `pause_turn` continuation | Claude performs live web research about brand perception using its server-side web search tool. The response includes inline citations from real web pages. Additionally uses `pause_turn` stop_reason for multi-turn research continuation (up to 5 turns). OpenRouter doesn't support Anthropic tool use or pause_turn semantics. |

#### LangGraph / LangChain integrations

| Call Site ID | File | Framework | Why it must stay |
|-------------|------|-----------|------------------|
| **KB-6 Synthesis** | `core/research/knowledge_base/agents.py` | LangGraph `create_react_agent()` + LangChain `init_chat_model()` | The LLM (`claude-opus-4-6`) is instantiated inside a **LangGraph ReAct agent** that autonomously reads files, reasons, and synthesizes knowledge. The model is not called directly — it's invoked by the LangGraph runtime as part of a multi-step tool-use loop. You cannot swap this to OpenRouter without rewriting the agent to use a LangChain-compatible OpenRouter chat model (possible but non-trivial — would need `ChatOpenAI(base_url=openrouter_url)` and model name remapping). **Candidate for Phase 2 if we build a LangChain adapter.** |
| **RH-1 Reddit HIL** | `core/reddit_hil/graph.py` | LangChain `ChatGoogleGenerativeAI` `.invoke()` | Uses LangChain's Gemini wrapper. Same story as KB-6: the model is behind a LangChain abstraction. Could be swapped to `ChatOpenAI(base_url=openrouter_url, model="google/gemini-3-flash-preview")` but requires testing that LangChain's `ChatOpenAI` works correctly against OpenRouter for this use case. **Candidate for Phase 2.** |

---

### Cost tracking for non-migrated call sites

Since the primary goal is **centralized cost tracking**, and ~16 call sites will remain on native APIs, we need a supplementary approach for those:

| Option | Effort | Coverage |
|--------|--------|----------|
| **LangSmith (already in place)** | Zero — already configured | Covers all LiteLLM calls and LangChain calls. Doesn't cover raw HTTP calls (claude.py, gemini.py). |
| **Manual token logging** | Low — add `structlog` calls after each native API response | Covers everything. Log `{model, input_tokens, output_tokens, provider, pipeline, call_site}` to structured logs. Aggregate in your analytics pipeline. |
| **Wrapper function** | Medium — create a thin `native_llm_call()` logger that wraps native SDK calls | Centralizes logging for all non-OpenRouter calls. Could push cost events to the same dashboard as OpenRouter. |

**Recommendation:** Option 3 (wrapper function). Create a `track_llm_cost()` utility that logs token usage + estimated cost to the same place OpenRouter reports to. Call it after every native API response. This gives you one unified cost view.

---

### Migration Summary

| Category | Call Sites | Files to Change | Effort |
|----------|-----------|----------------|--------|
| **Migrate via wrappers** (Group 1) | ~26 | 3 | Trivial — swap internals of 3 wrapper functions |
| **Migrate direct SDK** (Group 2) | ~7 | 5 | Easy-Medium — replace client instantiation + API call |
| **Migrate embeddings** (Group 3) | ~4 (+ cascading) | 2 | Easy — point OpenAI client at OpenRouter base URL |
| **Total migratable** | **~37** | **10** | — |
| **Keep on native APIs** | **~16** | 0 (no changes) | N/A |
| **Grand total** | **~53** | — | — |

### Recommended Migration Order

1. **Phase 1 — Wrappers** (highest ROI): Swap `llm_call()` + `_run_completion()` + `perplexity_client.research()`. 3 files changed, ~26 call sites migrated. Covers all of Content Engine v1.3, Topic Discovery, and all Perplexity research calls.
2. **Phase 2 — Direct SDK calls**: Planner, Persona Suggester, VSG agents, GA report, GA Perplexity engine. 5 files, ~7 call sites.
3. **Phase 3 — Embeddings**: Point embedding clients at OpenRouter. 2 files, all embedding callers cascade.
4. **Phase 4 — Cost tracking for native calls**: Build `track_llm_cost()` wrapper for the ~16 non-migrated call sites.
5. **Phase 5 (optional) — LangChain adapter**: If desired, swap KB Synthesis and Reddit HIL to `ChatOpenAI(base_url=openrouter_url)`. Requires testing.
