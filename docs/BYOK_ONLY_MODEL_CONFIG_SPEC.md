# BYOK-Only Model Configuration Spec

Status: Draft for spec-driven implementation

Branch: `feat/byok-only-model-config`

## 1. Product Contract

Deep Presence is BYOK-only for LLM usage. Each workspace must supply an OpenRouter API key before any LLM-backed product workflow can run. Every agent resolves its runtime model from workspace-scoped configuration.

The workspace is the owner of:

- OpenRouter API key.
- Per-agent model choices.
- Per-agent runtime options.
- LLM usage attribution.

The platform may still hold non-LLM operational secrets such as DB, Redis, storage, Webflow OAuth, GA4 OAuth, and CMS encryption keys. Those are outside this spec.

## 2. Definitions

### Workspace

The top-level tenant. Identified by `workspace_id` and `workspace_slug`.

### Agent

A stable logical LLM call site. Example: `content.brief_builder` or `topic_discovery.source_c_deep_research`.

### Agent catalog

Code-defined registry of all supported agents, their defaults, capabilities, and display grouping.

### Credential

Encrypted workspace OpenRouter API key plus metadata. Only one active OpenRouter credential is supported per workspace in v1.

### Model config

Workspace override for one agent. If no row exists, the resolver uses the code catalog default for that agent. Catalog defaults do not bypass missing credentials.

### BYOK-only

The product runtime never falls back to platform-owned LLM keys. Missing or invalid workspace credentials fail closed.

## 3. Data Model

### 3.1 `workspace_llm_credentials`

Stores encrypted LLM gateway credentials per workspace.

Columns:

```text
id uuid primary key
workspace_id uuid not null references workspaces(id) on delete cascade
provider varchar not null default 'openrouter'
encrypted_api_key text not null
api_key_fingerprint varchar not null
api_key_masked varchar not null
status varchar not null default 'active'
last_validated_at timestamptz null
last_validation_error text null
created_by uuid null references users(id)
updated_by uuid null references users(id)
deleted_at timestamptz null
created_at timestamptz not null default now()
updated_at timestamptz not null default now()
```

Constraints and indexes:

```text
unique active credential per (workspace_id, provider) where deleted_at is null
index workspace_id
index provider
index status
```

Allowed `provider` values:

- `openrouter`

Allowed `status` values:

- `active`
- `invalid`
- `deleted`

The raw key is never stored outside `encrypted_api_key`.

`api_key_fingerprint` is a SHA-256 hash of the normalized key plus a server-side salt or pepper. It is used for audit/debug and dedup checks, never for auth.

`api_key_masked` format:

```text
sk-or-...abcd
```

Only last 4 characters are retained.

### 3.2 `workspace_agent_model_configs`

Stores per-agent model overrides.

Columns:

```text
id uuid primary key
workspace_id uuid not null references workspaces(id) on delete cascade
agent_key varchar not null
provider varchar not null default 'openrouter'
model varchar not null
temperature float null
max_tokens integer null
timeout_s float null
extra_body jsonb null
enabled boolean not null default true
created_by uuid null references users(id)
updated_by uuid null references users(id)
created_at timestamptz not null default now()
updated_at timestamptz not null default now()
```

Constraints and indexes:

```text
unique (workspace_id, agent_key)
index workspace_id
index agent_key
index provider
```

Rules:

- `agent_key` must exist in the code catalog.
- `provider` must be `openrouter` for v1.
- `model` must be provider-prefixed or prefixable by `_ensure_model_prefix()`.
- `extra_body` must not contain secrets.
- Null runtime options mean "use catalog default."

### 3.3 `llm_cost_events` additions

Add nullable fields:

```text
agent_key varchar null
credential_id uuid null references workspace_llm_credentials(id) on delete set null
model_config_id uuid null references workspace_agent_model_configs(id) on delete set null
actual_provider varchar null
workspace_billed boolean not null default true
```

Rules:

- `workspace_id` should be populated for all BYOK runtime calls.
- `agent_key` should be populated for all agent calls.
- `workspace_billed=true` means usage was charged to the workspace OpenRouter account.

## 4. Agent Catalog

Location:

```text
core/model_config/agent_catalog.py
```

Types:

```python
class AgentCapability(str, Enum):
    chat = "chat"
    structured_output = "structured_output"
    embeddings = "embeddings"
    deep_research = "deep_research"
    web_citations = "web_citations"

class AgentDefinition(BaseModel):
    agent_key: str
    display_name: str
    group: str
    pipeline: str
    pipeline_step: str
    default_model: str
    default_temperature: float | None = None
    default_max_tokens: int | None = None
    default_timeout_s: float | None = None
    capabilities: list[AgentCapability] = Field(default_factory=list)
    required: bool = True
    description: str = ""
```

All Pydantic fields must have defaults where possible, following repo rules.

Catalog functions:

```python
def all_agent_definitions() -> list[AgentDefinition]: ...
def get_agent_definition(agent_key: str) -> AgentDefinition | None: ...
def required_agents_for_pipeline(pipeline: str) -> list[AgentDefinition]: ...
```

Initial agent keys:

```text
shared.embeddings.default

gap.query_generation
gap.report_generation
gap.search.perplexity
gap.search.openai
gap.search.claude
gap.search.gemini

content.planner
content.strategic_planner
content.brief_builder
content.worker.outliner
content.worker.drafter
content.worker.reviser
content.worker.fact_enricher
content.worker.linker
content.formatter
content.judge.style
content.judge.factual
content.judge.eeat
content.embedding.semantic

topic_discovery.source_a_company
topic_discovery.source_b_persona
topic_discovery.source_c_deep_research
topic_discovery.source_d_adversarial
topic_discovery.hierarchy_unified_s2
topic_discovery.subdomain_expansion
topic_discovery.relevance_filter
topic_discovery.topic_generation
topic_discovery.dedup
topic_discovery.cannibalization_embedding

research.kb.company_overview
research.kb.customer_reviews
research.kb.competitor_scanner
research.kb.competitor_extractor
research.kb.weakness_analyst
research.kb.brand_perception
research.kb.synthesis

research.ap.suggester
research.ap.profile_generator

research.vsg.author_discovery
research.vsg.author_research
research.vsg.synthesis

daily_tracker.fanout
daily_tracker.content_to_prompt
daily_tracker.platform.perplexity
daily_tracker.platform.openai
daily_tracker.platform.claude
daily_tracker.platform.gemini

reddit_hil.ranking_drafting
```

## 5. Backend Service Contracts

### 5.1 `ModelConfigService`

Location:

```text
core/model_config/service.py
```

Responsibilities:

- Return catalog plus workspace overrides.
- Store encrypted OpenRouter key.
- Delete key by soft-delete.
- Validate key against OpenRouter.
- Upsert agent config.
- Test an agent config with current workspace key.
- Produce preflight status for a list of agent keys.

Public methods:

```python
async def get_workspace_model_config(workspace_id: str) -> WorkspaceModelConfigView: ...

async def upsert_openrouter_key(
    workspace_id: str,
    user_id: str,
    api_key: str,
) -> CredentialStatus: ...

async def delete_openrouter_key(workspace_id: str, user_id: str) -> None: ...

async def test_openrouter_key(workspace_id: str, api_key: str | None = None) -> CredentialTestResult: ...

async def upsert_agent_config(
    workspace_id: str,
    user_id: str,
    agent_key: str,
    update: AgentModelConfigUpdate,
) -> AgentModelConfigView: ...

async def test_agent_config(
    workspace_id: str,
    agent_key: str,
) -> AgentConfigTestResult: ...

async def preflight(
    workspace_id: str,
    agent_keys: list[str],
) -> ModelConfigPreflightResult: ...
```

### 5.2 `ModelConfigResolver`

Location:

```text
core/model_config/resolver.py
```

Responsibilities:

- Resolve active credential.
- Resolve agent model config with catalog fallback.
- Decrypt key only inside the resolver.
- Return a runtime-safe resolved object.
- Never log raw key.

Public method:

```python
async def resolve(
    workspace_id: str,
    workspace_slug: str,
    agent_key: str,
) -> ResolvedModelConfig: ...
```

Failure modes:

```text
MissingCredentialError
InvalidCredentialError
UnknownAgentKeyError
DisabledAgentError
ModelConfigValidationError
```

### 5.3 OpenRouter client factory

Update `core/shared_tools/openrouter_client.py`:

Current singleton-only functions may remain for test/admin legacy code, but product runtime must use BYOK-aware functions.

New functions:

```python
def build_async_client_for_key(
    api_key: str,
    *,
    base_url: str | None = None,
    timeout_s: float | None = None,
) -> AsyncOpenAI: ...

def build_sync_client_for_key(
    api_key: str,
    *,
    base_url: str | None = None,
    timeout_s: float | None = None,
) -> OpenAI: ...

def build_chat_openai_for_key(
    api_key: str,
    model: str,
    *,
    base_url: str | None = None,
    **kwargs: Any,
) -> ChatOpenAI: ...
```

Do not cache clients by raw API key. If caching is later required, cache by credential id and clear cache on key rotation.

### 5.4 LLM call wrapper

Update or add wrapper:

```python
async def llm_call_for_agent(
    *,
    workspace_id: str,
    workspace_slug: str,
    agent_key: str,
    system: str,
    user: str,
    max_tokens: int | None = None,
    temperature: float | None = None,
    response_format: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    resolver: ModelConfigResolver | None = None,
) -> LLMResponse: ...
```

Resolution order:

1. Catalog definition for `agent_key`.
2. Workspace override row if present.
3. Request-level overrides for `temperature`, `max_tokens`, and response format only where the agent supports them.
4. Decrypted workspace OpenRouter key.

Cost tracking fields:

```text
workspace_id
company_slug / workspace_slug
agent_key
credential_id
model_config_id
model
provider=openrouter
source=openrouter
workspace_billed=true
```

## 6. API Spec

### 6.1 Response models

```python
class CredentialStatusResponse(BaseModel):
    provider: str = "openrouter"
    configured: bool = False
    status: str = ""
    masked_key: str = ""
    last_validated_at: str | None = None
    last_validation_error: str = ""

class AgentCatalogItem(BaseModel):
    agent_key: str = ""
    display_name: str = ""
    group: str = ""
    pipeline: str = ""
    pipeline_step: str = ""
    default_model: str = ""
    capabilities: list[str] = Field(default_factory=list)
    required: bool = True
    description: str = ""

class AgentModelConfigResponse(BaseModel):
    agent_key: str = ""
    model: str = ""
    provider: str = "openrouter"
    temperature: float | None = None
    max_tokens: int | None = None
    timeout_s: float | None = None
    enabled: bool = True
    uses_default: bool = True
    updated_at: str | None = None

class WorkspaceModelConfigResponse(BaseModel):
    workspace_slug: str = ""
    credential: CredentialStatusResponse = Field(default_factory=CredentialStatusResponse)
    catalog: list[AgentCatalogItem] = Field(default_factory=list)
    configs: list[AgentModelConfigResponse] = Field(default_factory=list)
    missing_required_agent_keys: list[str] = Field(default_factory=list)
```

### 6.2 Requests

```python
class OpenRouterKeyUpsertRequest(BaseModel):
    api_key: str = ""

class AgentModelConfigUpdateRequest(BaseModel):
    model: str = ""
    temperature: float | None = None
    max_tokens: int | None = None
    timeout_s: float | None = None
    enabled: bool | None = None
    extra_body: dict[str, Any] | None = None

class ModelConfigPreflightRequest(BaseModel):
    agent_keys: list[str] = Field(default_factory=list)
```

### 6.3 Routes

All routes use:

```text
prefix = /api/v1/workspaces/{workspace_slug}/model-config
```

#### `GET ""`

Read current credential status, catalog, effective config rows, and missing required setup.

Auth: workspace member.

#### `PUT "/openrouter-key"`

Validate, encrypt, and store key.

Auth: owner/admin.

Response: `CredentialStatusResponse`.

#### `DELETE "/openrouter-key"`

Soft-delete key. Runtime calls fail closed after deletion.

Auth: owner/admin.

Response:

```json
{"deleted": true}
```

#### `POST "/openrouter-key/test"`

If body includes `api_key`, test unsaved key. Otherwise test stored key.

Auth: owner/admin.

Response:

```python
class CredentialTestResponse(BaseModel):
    ok: bool = False
    provider: str = "openrouter"
    model: str = ""
    error: str = ""
```

#### `PATCH "/agents/{agent_key}"`

Upsert per-agent config.

Auth: owner/admin.

Response: `AgentModelConfigResponse`.

#### `POST "/agents/{agent_key}/test"`

Resolve stored key + current or supplied agent config and execute a minimal OpenRouter call.

Auth: owner/admin.

#### `POST "/preflight"`

Validate that the workspace can run all requested agents.

Auth: workspace member.

Response:

```python
class ModelConfigPreflightResponse(BaseModel):
    ok: bool = False
    missing_credential: bool = False
    invalid_credential: bool = False
    missing_agent_keys: list[str] = Field(default_factory=list)
    disabled_agent_keys: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
```

## 7. Runtime Integration Spec

### 7.1 Pipeline preflight

Each pipeline start route must compute required agent keys and run preflight before task creation.

Examples:

```text
Gap Analysis:
  gap.query_generation
  gap.report_generation
  gap.search.perplexity

Content Engine v1.3:
  content.strategic_planner
  content.brief_builder
  content.worker.outliner
  content.worker.drafter
  content.worker.fact_enricher
  content.worker.linker
  content.formatter
  content.judge.style
  content.judge.factual
  content.judge.eeat

Research Orchestrator:
  all KB/AP/VSG agent keys needed by selected stages

Daily Tracker fanout:
  daily_tracker.fanout

Content-to-prompt:
  daily_tracker.content_to_prompt
```

Preflight failure response:

```json
{
  "detail": {
    "reason": "model_config_required",
    "missing_credential": true,
    "missing_agent_keys": ["content.brief_builder"],
    "message": "Configure an OpenRouter key and model settings for this workspace before starting this workflow."
  }
}
```

HTTP status: `409 Conflict`.

### 7.2 Background task context

All background task launchers already persist `workspace_id` in `PipelineTask`. Runner functions must build a runtime context:

```python
ModelRuntimeContext(
    workspace_id=task.workspace_id,
    workspace_slug=task.company_slug,
    company_slug=task.company_slug,
)
```

This context must be passed into pipelines and agent helpers that make LLM calls.

### 7.3 Cost tracking

`track_llm_cost()` signature additions:

```python
workspace_id: str | None = None
agent_key: str = ""
credential_id: str | None = None
model_config_id: str | None = None
actual_provider: str = ""
workspace_billed: bool = True
```

DB persistence must set `workspace_id`, not only `company_slug`.

## 8. Native Provider Remediation Spec

### 8.1 Immediate BYOK v1 rule

Only OpenRouter-backed customer LLM calls are supported. Native provider calls that require platform env keys are not allowed in product runtime.

### 8.2 Required migrations

Migrate:

- KB brand perception from `anthropic.AsyncAnthropic` to OpenRouter.
- VSG author discovery/synthesis from Anthropic key usage to OpenRouter.
- Older Content Engine planner/worker model reads to BYOK resolver.

### 8.3 Search engines

Current native search engines:

- `core/gap_analysis/engines/openai_engine.py`
- `core/gap_analysis/engines/claude.py`
- `core/gap_analysis/engines/gemini.py`

These use provider-specific web-search/grounding APIs and cannot be treated as already BYOK-safe.

BYOK v1 behavior:

- Keep `perplexity/sonar-*` search enabled through OpenRouter.
- Disable OpenAI/Claude/Gemini search engines in BYOK-only mode unless explicit OpenRouter-compatible replacements are implemented and tested.
- API should return a clear unsupported-engine error if a workspace requests disabled native engines.

Future v2 can add provider-specific BYOK credentials if the product requires exact ChatGPT/Claude/Gemini search-surface parity.

## 9. Frontend Spec

### 9.1 Data flow

`ModelsTab` loads:

```text
GET /api/v1/workspaces/{activeWorkspaceSlug}/model-config
```

The active workspace comes from `useWorkspaceStore`.

### 9.2 UI sections

1. OpenRouter credential card.
2. Setup/preflight status.
3. Agent config table grouped by pipeline.
4. Usage summary from `llm_cost_events` by workspace and agent.

### 9.3 Role behavior

- owner/admin: save key, delete key, update agent configs, test.
- member/viewer: read-only status and model list.

### 9.4 Key form behavior

- Input is password-style.
- Saved key is never rehydrated.
- After save, show masked key and validation timestamp.
- Delete key requires confirmation.

### 9.5 Agent row behavior

Each row shows:

- Agent display name.
- Pipeline group.
- Current effective model.
- Default model.
- Enabled state.
- Optional temperature/max token controls.
- Test action.
- Last updated timestamp.

## 10. Security Requirements

- Raw API keys must never be logged.
- Raw API keys must never appear in task events, cost events, API responses, frontend state after save, or test snapshots.
- Store keys with Fernet encryption.
- Use a generic `CREDENTIAL_FERNET_KEY`; allow `CMS_FERNET_KEY` fallback only as a temporary migration bridge if needed.
- Add audit masking coverage for OpenRouter key shapes.
- Owners/admins only can mutate credentials.
- Soft-delete credentials rather than hard delete.
- Key rotation invalidates any cached OpenRouter clients for that credential.

## 11. Observability Requirements

Every BYOK call must emit:

- `workspace_id`
- `workspace_slug`
- `agent_key`
- `model`
- `provider=openrouter`
- `actual_provider` if available from OpenRouter response metadata
- `credential_id`
- `model_config_id`
- prompt/completion tokens
- estimated cost
- pipeline and pipeline step

Errors should classify:

- missing credential
- invalid credential
- rate limit/quota exceeded
- unsupported model
- unsupported engine
- OpenRouter outage

## 12. Validation Checklist

### Backend

- `tests/model_config/test_agent_catalog.py`
- `tests/model_config/test_credentials.py`
- `tests/model_config/test_service.py`
- `tests/api/test_model_config.py`
- `tests/shared_tools/test_openrouter_client.py`
- `tests/shared_tools/test_cost_tracker.py`
- Targeted pipeline tests for CE, TD, KB/AP/VSG, Daily Tracker, embeddings.

### Frontend

- TypeScript clean.
- Models tab compiles without mock-only local state.
- API adapter tests if available.

### Static guard

Add a test that scans product runtime files and rejects direct use of platform LLM keys outside allowlisted modules.

Allowlist:

- `core/config/settings.py`
- `core/model_config/credentials.py`
- tests
- migration/bootstrap scripts

Disallowed in product runtime:

- `settings.openrouter_api_key`
- `settings.openai_api_key`
- `settings.anthropic_api_key`
- `settings.google_api_key_gap_analysis`
- direct `AsyncOpenAI(api_key=settings...)`
- direct `anthropic.AsyncAnthropic(api_key=settings...)`

## 13. Acceptance Criteria

The feature is complete when:

1. A new workspace with no OpenRouter key cannot start LLM workflows.
2. Owner/admin can add an OpenRouter key and configure every cataloged agent.
3. Workflows use the workspace key, not platform env keys.
4. Each agent call records workspace and agent-level usage.
5. Native provider env keys are not required in production for customer LLM workflows.
6. The Settings Models tab is backed by real APIs.
7. Tests prove missing/invalid BYOK config fails closed.
8. Tests prove raw keys are not returned or logged.
9. Static guard prevents future direct platform-key call sites.
