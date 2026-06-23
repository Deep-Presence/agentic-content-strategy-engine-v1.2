# BYOK-Only Model Configuration Plan

Branch: `feat/byok-only-model-config`

## Implementation Status

As of 2026-06-23, the branch has implemented the BYOK storage/API/service layer, runtime resolver, workspace OpenRouter client builders, pipeline launch preflight, major customer runtime migrations, and the Settings Models UI.

Completed in this branch:

- Workspace OpenRouter credential and per-agent model config persistence.
- Code-defined agent catalog seeded from the current platform model defaults.
- Model config API under `/api/v1/workspaces/{workspace_slug}/model-config`.
- BYOK-aware `llm_call_for_agent()` and OpenRouter client builders for resolved workspace keys.
- Workspace/agent/credential/model-config cost metadata plumbing.
- Runtime migration for Content Engine v1.3, Topic Discovery, KB/AP/VSG, Daily Tracker fanout/content-to-prompt/platform Perplexity, embeddings, Reddit HIL, and the primary Gap Analysis model calls.
- Gap Analysis and Daily Tracker native OpenAI/Claude/Gemini search engines disabled when workspace BYOK context is present; BYOK v1 uses OpenRouter-routed Perplexity for web-grounded search.
- Launch-route preflight for Content v1.3, Gap Analysis, Research Orchestrator, and Daily Tracker runs, returning HTTP 409 with `byok_model_config_required` before durable task creation.
- Settings Models tab wired to the real workspace model-config API with admin-gated key and agent controls.
- Static guard test that prevents new product runtime references to platform-owned LLM keys or singleton OpenRouter helpers outside the explicit legacy allowlist.

Remaining before branch exit:

- Run the final broad affected backend/frontend validation slice after the static guard/docs commit.
- Optionally remove the remaining no-workspace legacy allowlist entries once test/admin compatibility no longer needs them. Customer launch paths should already pass workspace context and fail closed through preflight.

## Summary

Deep Presence should become a BYOK-only LLM platform: every workspace supplies its own OpenRouter API key, and every LLM-powered agent resolves its model configuration from workspace-scoped agent settings at runtime. Product pipelines must not use a platform-owned `OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or Google model key for customer work.

The initial codebase was already partially OpenRouter-centered, but the contract was still environment-driven:

- Global settings define model names in `core/config/settings.py`.
- OpenRouter clients are singleton factories bound to `settings.openrouter_api_key` in `core/shared_tools/openrouter_client.py`.
- Many LLM call sites use shared OpenRouter helpers, but several high-value paths still instantiate native provider clients or direct HTTP calls.
- Cost tracking exists, and `llm_cost_events` already has `workspace_id`, but current runtime calls usually do not pass workspace id, agent key, credential id, or model config id into the cost event.

This plan makes the workspace the billing and configuration boundary. Users can be members of multiple workspaces, but the active workspace controls the OpenRouter key and agent model matrix.

## Goals

1. Make OpenRouter BYOK mandatory for all customer LLM runs.
2. Store exactly one active OpenRouter credential per workspace.
3. Provide per-agent model configuration for every user-visible agent and pipeline step.
4. Resolve the model config at runtime from `(workspace_id, agent_key)`, not from global settings.
5. Fail closed before starting a pipeline when the active workspace is missing required BYOK setup.
6. Preserve compatibility defaults through a code-defined agent catalog, while ensuring product runtime cannot silently fall back to platform-owned keys.
7. Record usage against workspace, agent, model config, and credential metadata.
8. Replace the current mock Models tab with a workspace-backed settings UI.

## Non-Goals

- Do not add LangChain wrappers to pipeline codepaths that currently forbid them.
- Do not implement provider-native BYOK in this change. The platform standard is OpenRouter key only.
- Do not store API keys in `workspaces.settings_json`.
- Do not use `CMSConnectionModel` for LLM credentials. Reuse the encryption pattern, not the CMS tables.
- Do not make model config user-scoped. The workspace owns runtime billing and model choices.
- Do not allow product runs to use platform-owned keys in production.

## Current Architecture Findings

### Workspace boundary already exists

The active workspace model is already present and should be reused:

- `workspaces` and `workspace_memberships` exist in migrations `0042` through `0044`.
- `WorkspaceService.assert_workspace_access()` is the authorization gate.
- Route helpers already resolve workspace scope in `api/routers/_helpers.py`.
- Frontend active workspace state exists in `frontend/src/stores/workspace.ts`.

BYOK should attach to `workspace_id`, not legacy `company_slug`.

### OpenRouter is centralized, but only around a platform key

`core/shared_tools/openrouter_client.py` exposes:

- `get_async_client()`
- `get_sync_client()`
- `build_chat_openai_via_openrouter()`
- `_ensure_model_prefix()`

All three client builders require `settings.openrouter_api_key`. This is the primary seam to replace. Runtime client creation must accept a resolved workspace credential.

### Model defaults are global settings

`core/config/settings.py` currently contains defaults for:

- Gap Analysis query/report/search engines.
- Content Engine planner, worker, formatter, judges, fact enricher, linker.
- Content Engine v1.3 planner, brief builder, worker, formatter, judges, fact enricher, linker.
- Research KB agents.
- Audience Persona agents.
- Voice Style Guide agents.
- Topic Discovery agents.
- Daily Tracker fanout.
- Reddit HIL Gemini model.
- Embeddings.

Those defaults should move into a code-defined agent catalog, not stay as the runtime source of truth. Env settings can remain as bootstrap defaults for tests, local dev, and migrations, but product runtime must resolve through the workspace model config service.

### Runtime LLM call sites fall into four groups

Group A: already routed through `llm_call()`.

- Content Engine v1.3 brief builder, strategic planner, workers, evaluators.
- KB competitor extraction.

Group B: already OpenRouter, but bypasses `llm_call()`.

- Topic Discovery `_run_completion()`.
- Daily Tracker query fanout.
- Daily Tracker content-to-prompt generation.
- Research Perplexity deep research helper.
- Embeddings.
- Reddit HIL ChatOpenAI builder.
- KB synthesis ChatOpenAI builder.
- Content Engine older planner path.

Group C: native provider keys still used.

- Gap Analysis OpenAI engine uses `AsyncOpenAI(api_key=settings.openai_api_key)` plus Responses web search.
- Gap Analysis Claude engine uses Anthropic HTTP with `settings.anthropic_api_key` and web search beta.
- Gap Analysis Gemini engine uses Google API key directly.
- KB brand perception uses `anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)`.
- VSG author discovery and synthesis still pass `settings.anthropic_api_key` into LiteLLM or direct OpenRouter-adjacent paths.

Group D: non-LLM external credentials.

- Webflow, WordPress, GA4, Reddit, R2, Redis, DB. These are not part of BYOK LLM scope.

Group C is the main product decision. If BYOK-only means "only OpenRouter key," those native provider paths must be migrated or disabled before production BYOK enforcement.

## Target Architecture

### New modules

Add a small model configuration package:

```text
core/model_config/
  __init__.py
  agent_catalog.py
  credentials.py
  resolver.py
  service.py
  protocols.py
```

Responsibilities:

- `agent_catalog.py`: code-defined list of supported agent keys and defaults.
- `credentials.py`: encryption, masking, fingerprinting, validation helpers.
- `resolver.py`: runtime resolution from workspace id and agent key.
- `service.py`: CRUD and validation orchestration for API routes.
- `protocols.py`: testable interfaces.

### New persistence

Add migration `0046_byok_model_config.py` with:

1. `workspace_llm_credentials`
2. `workspace_agent_model_configs`
3. Optional new columns on `llm_cost_events`

The credential table stores encrypted OpenRouter keys. The config table stores per-agent model overrides. The catalog remains in code, so new agent definitions ship with code and are visible to every workspace immediately.

### New APIs

Add router `api/routers/model_config.py`.

Preferred canonical routes:

```text
GET    /api/v1/workspaces/{workspace_slug}/model-config
PUT    /api/v1/workspaces/{workspace_slug}/model-config/openrouter-key
DELETE /api/v1/workspaces/{workspace_slug}/model-config/openrouter-key
POST   /api/v1/workspaces/{workspace_slug}/model-config/openrouter-key/test
PATCH  /api/v1/workspaces/{workspace_slug}/model-config/agents/{agent_key}
POST   /api/v1/workspaces/{workspace_slug}/model-config/agents/{agent_key}/test
POST   /api/v1/workspaces/{workspace_slug}/model-config/preflight
```

Authorization:

- Read: active workspace member.
- Write/delete/test key: owner or admin.
- Agent config update: owner or admin.

### Runtime resolution

Every product LLM call should take an `agent_key` and workspace context. The runtime resolver returns:

```text
ResolvedModelConfig(
  workspace_id,
  workspace_slug,
  agent_key,
  model,
  provider="openrouter",
  base_url,
  api_key,
  credential_id,
  model_config_id,
  temperature,
  max_tokens,
  timeout_s,
  extra_body,
)
```

No runtime LLM call should read `settings.openrouter_api_key` directly.

### BYOK enforcement

Add a single feature flag for migration safety:

```text
ALLOW_PLATFORM_OPENROUTER_FALLBACK=false
```

Default must be `false`. Production must leave it false. Tests can override explicitly where old fixtures are still migrating.

When false:

- Missing workspace OpenRouter key fails pipeline preflight.
- Missing required agent config falls back only to catalog defaults, not env keys.
- Invalid key fails pipeline preflight.
- Native provider keys are ignored for customer LLM work.

## Agent Catalog Strategy

Each agent gets a stable string key. The key is the contract between UI, API, runtime, tests, and cost tracking.

Initial catalog groups:

### Shared

- `shared.embeddings.default`

### Gap Analysis

- `gap.query_generation`
- `gap.report_generation`
- `gap.search.perplexity`
- `gap.search.openai`
- `gap.search.claude`
- `gap.search.gemini`

The search agents need special handling because native OpenAI/Claude/Gemini search APIs currently use provider-specific tools. In BYOK-only OpenRouter mode, either:

1. Replace them with OpenRouter-routed model calls and accept changed search semantics, or
2. Disable those platform engines until OpenRouter supports equivalent tools, or
3. Keep only `perplexity/sonar-*` as the web-grounded engine for BYOK v1.

The spec chooses option 3 for the first production-safe BYOK slice, with option 1 as an explicit follow-up.

### Content Engine

- `content.planner`
- `content.strategic_planner`
- `content.brief_builder`
- `content.worker.outliner`
- `content.worker.drafter`
- `content.worker.reviser`
- `content.worker.fact_enricher`
- `content.worker.linker`
- `content.formatter`
- `content.judge.style`
- `content.judge.factual`
- `content.judge.eeat`
- `content.embedding.semantic`

### Topic Discovery

- `topic_discovery.source_a_company`
- `topic_discovery.source_b_persona`
- `topic_discovery.source_c_deep_research`
- `topic_discovery.source_d_adversarial`
- `topic_discovery.hierarchy_unified_s2`
- `topic_discovery.subdomain_expansion`
- `topic_discovery.relevance_filter`
- `topic_discovery.topic_generation`
- `topic_discovery.dedup`
- `topic_discovery.cannibalization_embedding`

### Research Artifacts

Knowledge Base:

- `research.kb.company_overview`
- `research.kb.customer_reviews`
- `research.kb.competitor_scanner`
- `research.kb.competitor_extractor`
- `research.kb.weakness_analyst`
- `research.kb.brand_perception`
- `research.kb.synthesis`

Audience Persona:

- `research.ap.suggester`
- `research.ap.profile_generator`

Voice Style Guide:

- `research.vsg.author_discovery`
- `research.vsg.author_research`
- `research.vsg.synthesis`

Research Orchestrator itself does not need an LLM model. It starts KB/AP/VSG and should preflight those required agent keys.

### Daily Tracker

- `daily_tracker.fanout`
- `daily_tracker.content_to_prompt`
- `daily_tracker.platform.perplexity`
- `daily_tracker.platform.openai`
- `daily_tracker.platform.claude`
- `daily_tracker.platform.gemini`

The same search-engine caveat applies here as Gap Analysis.

### Reddit HIL

- `reddit_hil.ranking_drafting`

## Implementation Phases

### Phase 1: Persistence, catalog, service, and API

Deliverables:

- Add migration `0046_byok_model_config.py`.
- Add ORM models and repositories.
- Add Pydantic API schemas.
- Add `ModelConfigService`.
- Add `api/routers/model_config.py`.
- Register router in `api/app.py`.
- Add tests for permissions, encryption, masking, CRUD, validation failures.

Acceptance:

- Owner/admin can store, rotate, delete, and test a workspace OpenRouter key.
- Member can read status but cannot see or mutate secrets.
- Catalog returns every agent with default model and capability metadata.
- Agent config update validates agent key against catalog.
- No response includes raw API key.

### Phase 2: Runtime resolver and OpenRouter client factory

Deliverables:

- Add `ModelConfigResolver`.
- Replace singleton-only OpenRouter access with BYOK-aware factory functions.
- Add `llm_call_for_agent()` or extend `llm_call()` with `workspace_id` and `agent_key`.
- Update `track_llm_cost()` to accept workspace/model config metadata.
- Add preflight helpers for pipeline routes.

Acceptance:

- Runtime LLM calls can use a workspace credential without reading env key.
- Missing key/config fails closed with typed errors.
- Cost events include workspace id, agent key, credential id, and model config id.
- Existing tests can inject a fake resolver without network calls.

### Phase 3: Migrate OpenRouter-native call sites

Priority order:

1. Content Engine v1.3 `llm_call()` paths.
2. Topic Discovery `_run_completion()`.
3. Research Perplexity helper and KB/AP/VSG OpenRouter calls.
4. Daily Tracker fanout/content-to-prompt.
5. Embedding clients.
6. Reddit HIL ChatOpenAI builder.
7. Older Content Engine planner/worker paths still reading legacy settings.

Acceptance:

- No migrated call site reads `settings.openrouter_api_key`.
- Every migrated call site passes a stable `agent_key`.
- Pipeline start routes preflight required agent keys before task creation where possible.

### Phase 4: Native provider path remediation

Deliverables:

- Remove product runtime dependence on `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and Google model API keys.
- For Gap Analysis and Daily Tracker platform engines, ship BYOK v1 with OpenRouter-routed Perplexity search enabled and non-equivalent native engines disabled by default.
- Add explicit config/status messaging for disabled engines.
- Migrate KB brand perception and VSG discovery/synthesis to OpenRouter client calls.

Acceptance:

- A production environment with only DB, Redis, storage, OAuth/CMS keys, and workspace OpenRouter keys can run LLM product flows.
- Native provider keys are not required for any customer LLM path.
- Tests assert that setting native provider env keys does not bypass workspace BYOK.

### Phase 5: Frontend Settings integration

Deliverables:

- Replace mock `ModelsTab` state with backend-backed data.
- Add OpenRouter key form with masked status.
- Add per-agent rows grouped by pipeline.
- Add model update controls and "test" actions.
- Add missing-configuration blocking states on pipeline start buttons.

Acceptance:

- Active workspace switch reloads model config.
- Owner/admin can configure key and agents.
- Member/viewer sees read-only status.
- Raw key is never displayed after save.

### Phase 6: BYOK-only enforcement and cleanup

Deliverables:

- Set `ALLOW_PLATFORM_OPENROUTER_FALLBACK=false` by default.
- Remove product-runtime references to `settings.openrouter_api_key`.
- Keep env model defaults only for catalog bootstrap and tests.
- Update docs and run broad targeted tests.

Acceptance:

- Grep-based test or unit guard fails if new product code calls `get_async_client()` without a BYOK context.
- Full affected backend test slice passes.
- Frontend TypeScript passes.

## Testing Plan

### Unit tests

- Credential encryption/decryption/masking/fingerprint.
- Agent catalog contains unique keys and valid defaults.
- Model config resolver precedence.
- Missing key/config errors.
- OpenRouter client factory does not use platform key when BYOK context is present.
- Cost tracking includes new metadata.

### API tests

- CRUD key/config routes.
- Role permissions.
- No raw key in response.
- Invalid agent key returns 404 or 422.
- Invalid OpenRouter key marks credential invalid.
- Pipeline preflight returns actionable missing config response.

### Pipeline tests

- Content Engine v1.3 resolves each agent key.
- Topic Discovery resolves each source/phase key.
- KB/AP/VSG resolve all research agents.
- Daily Tracker fanout/content-to-prompt resolve workspace config.
- Embeddings resolve `shared.embeddings.default`.

### Frontend tests

- Models tab loads active workspace config.
- Save/delete/test key flows.
- Agent model update flow.
- Role-gated read-only state.
- Workspace switch refreshes state.

### Static guard

Add a targeted test or script to flag product runtime usage of:

- `settings.openrouter_api_key`
- `settings.openai_api_key`
- `settings.anthropic_api_key`
- `settings.google_api_key_gap_analysis`
- `get_async_client()` without a workspace credential context

Allowlisted files:

- Settings definitions.
- Tests.
- Migration/bootstrap utilities.
- Credential validation code.

## Rollout Plan

1. Ship schema/API/UI with fallback still disabled in production but tests using explicit injection.
2. Migrate OpenRouter-native call sites.
3. Disable or replace native provider engines.
4. Run internal workspace smoke test with only a workspace OpenRouter key.
5. Remove platform key from production runtime environment.
6. Monitor cost events by workspace and agent.

## Risks

### Native search parity

OpenAI Responses web search, Anthropic web search beta, and Gemini grounding are not equivalent to simple OpenRouter chat calls. BYOK v1 should not pretend parity if it cannot preserve citations and live web semantics.

Mitigation: keep Perplexity web-grounded BYOK path first; disable non-equivalent engines with explicit UI/API status until equivalent OpenRouter-routed implementations are verified.

### Context propagation

Some background tasks already carry `workspace_id`, but model calls inside deep helper layers do not always receive it. Missing context would lead to resolver failures.

Mitigation: pipeline start preflight plus task-bound runtime context object passed down from runner to pipeline to agent call.

### Secret leakage

OpenRouter keys must never be logged, echoed, serialized in task events, or returned to frontend.

Mitigation: encrypted storage, response schemas with masked fields only, audit masking updates, and tests that assert secret absence.

### Tests built around global settings

Existing tests patch `settings.*_model` and `settings.openrouter_api_key`.

Mitigation: introduce resolver test doubles and keep catalog defaults seeded from current settings values during transition.

## Recommended Branch Exit Criteria

- BYOK docs and spec merged.
- Migration/API/service/frontend implemented.
- At least Content Engine v1.3, Topic Discovery, KB/AP/VSG, Daily Tracker fanout/content-to-prompt, embeddings, and Reddit HIL resolve via workspace BYOK.
- Native search engines are either migrated or explicitly disabled under BYOK-only.
- No product runtime path needs platform-owned LLM keys.
- Targeted backend and frontend test suites pass.
