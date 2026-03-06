# Audience Persona Research Pipeline — Implementation Plan

## Context

Deep Presence helps B2B companies get cited in AI search results. The existing Knowledge Base (KB) pipeline produces company-level research artifacts (company overview, customer reviews, competitors, etc.) via a 6-agent DAG with 3 HITL checkpoints.

**Problem**: There is no structured pipeline for producing detailed audience persona artifacts. The existing persona agent (`core/research/agents/persona_agent.py`) uses the old DeepAgents + Gemini framework and produces generic ICP + 2 secondary personas without leveraging the knowledge base.

**Goal**: Build a new, production-grade Audience Persona Research Pipeline that:
1. Leverages KB artifacts (company profile, customer reviews) + user-uploaded knowledge docs as context
2. Uses a 2-agent architecture: Suggester (briefs) + Generator (detailed profiles)
3. Supports per-persona HITL approval (approve/modify/reject each brief individually)
4. Supports manual persona brief entry by humans
5. Stores versioned persona profiles with manifest tracking
6. Integrates with the content engine as contextual input

---

## Architecture Decision: New Module

**Decision**: Create `core/research/audience_persona/` as a new module, separate from the KB pipeline.

**Rationale**:
- Different data model: multi-artifact (3-5 personas) vs single-doc-per-agent
- Different HITL pattern: per-persona decisions vs batch doc-review
- Different storage: N persona profiles each versioned vs typed KB documents
- Keeps the KB module well-scoped; avoids conflating concerns

The new module mirrors KB's structure (`agents.py`, `pipeline.py`, `graph.py`, `storage.py`) for codebase consistency, while **reusing shared infrastructure** (HITL checkpoint runner `run_kb_hitl_checkpoint()`, `_emit()` helper, knowledge doc loading, Perplexity client) to avoid duplicating common patterns.

---

## Module Structure

```
core/research/audience_persona/
    __init__.py
    agents.py               # Agent 1 (Suggester) + Agent 2 (Profile Generator)
    graph.py                # LangGraph HITL sub-graphs (brief review + profile review)
    pipeline.py             # DAG orchestrator with 2 HITL checkpoints
    storage.py              # PersonaStorage — versioned per-persona artifacts

core/research/prompts/
    persona_suggester.py    # System + user prompt builders for Agent 1
    persona_generator.py    # System + user prompt builders for Agent 2

core/models/
    audience_persona.py     # New Pydantic models

api/routers/
    audience_persona.py     # REST endpoints

api/tasks/runner.py         # Add run_audience_persona_pipeline_task()

tests/research/audience_persona/
    test_models_ap.py
    test_storage_ap.py
    test_agents_ap.py
    test_graph_ap.py
    test_pipeline_ap.py
    test_prompts_ap.py

tests/api/
    test_audience_persona_router.py
```

---

## 1. Pydantic Models (`core/models/audience_persona.py`)

### PersonaBrief (Agent 1 output / Manual entry)
```python
class PersonaBrief(BaseModel):
    brief_id: str = ""                              # "pb-001", generated server-side
    persona_name: str = ""                          # "James"
    tagline: str = ""                               # "VP of Finance at mid-market SaaS"
    description: str = ""                           # One-line description
    rationale: List[str] = Field(default_factory=list)  # 2-3 bullet points
    source: Literal["agent", "manual", "hybrid"] = "agent"
```

### PersonaBriefReview (HITL-1 per-persona decision)
```python
class PersonaBriefDecision(str, Enum):
    APPROVE = "approve"
    MODIFY = "modify"
    REJECT = "reject"

class PersonaBriefReview(BaseModel):
    brief_id: str = ""
    decision: PersonaBriefDecision = PersonaBriefDecision.APPROVE
    modified_brief: Optional[PersonaBrief] = None   # Present when decision="modify"
```

### PersonaProfileEntry (Manifest entry per persona)
```python
class PersonaProfileEntry(BaseModel):
    persona_id: str = ""                # Slugified from persona_name
    persona_name: str = ""
    tagline: str = ""
    kind: Literal["icp", "secondary"] = "secondary"
    current_version: int = 0
    last_updated: Optional[datetime] = None
    status: Literal["fresh", "stale", "missing", "pending_review", "archived"] = "missing"
    created_by: Literal["agent", "manual", "hybrid"] = "agent"
    word_count: int = 0
    sha256: str = ""
```

### PersonaManifest
```python
class PersonaManifest(BaseModel):
    slug: str = ""
    company_name: str = ""
    created_at: datetime = Field(default_factory=_utcnow)
    last_full_run: Optional[datetime] = None
    personas: Dict[str, PersonaProfileEntry] = Field(default_factory=dict)
    kb_synthesis_version: Optional[int] = None      # Tracks KB dependency
    kb_synthesis_updated_at: Optional[datetime] = None
```

### PersonaAgentResult
```python
class PersonaAgentResult(BaseModel):
    brief_id: str = ""
    persona_name: str = ""
    content_md: str = ""
    content_json: Optional[Dict[str, Any]] = None
    word_count: int = 0
    execution_time_s: float = 0.0
    error: Optional[str] = None
```

### Pipeline I/O
```python
class AudiencePersonaInput(BaseModel):
    company_name: str
    domain: Optional[str] = None
    company_slug: Optional[str] = None
    product_slug: Optional[str] = None
    product_name: Optional[str] = None
    max_personas: int = Field(default=5, ge=3, le=7)
    language: str = "en"
    region: Optional[str] = None
    additional_constraints: Optional[str] = None
    auto_approve_checkpoints: List[int] = Field(default_factory=list)
    # Checkpoint 1 = brief approval, Checkpoint 2 = profile review

class AudiencePersonaOutput(BaseModel):
    slug: str = ""
    company_name: str = ""
    manifest: Optional[PersonaManifest] = None
    briefs_suggested: int = 0
    briefs_approved: int = 0
    profiles_generated: int = 0
    persona_results: Dict[str, PersonaAgentResult] = Field(default_factory=dict)
    persona_dir: str = ""
    total_execution_time_s: float = 0.0
```

---

## 2. Storage (`core/research/audience_persona/storage.py`)

### Disk Layout
```
artifacts/audience_personas/{slug}/
    _manifest.json
    {persona_id}/
        brief.json          # Approved brief
        v1.md               # Full persona profile (version 1)
        v1.json             # Structured sidecar (optional)
        v2.md               # Version 2 after refresh
```

### PersonaStorage Class (✅ Implemented)
Mirrors `KBStorage` patterns:
- `read_manifest() -> PersonaManifest`
- `write_manifest(manifest) -> None` (atomic via tempfile + os.replace)
- `write_brief(persona_id, brief: PersonaBrief) -> None`
- `read_brief(persona_id) -> Optional[PersonaBrief]`
- `write_version(persona_id, persona_name, content_md, content_json=None, *, kind, created_by, tagline, status) -> int`
- `read_version(persona_id, version) -> Optional[Dict[str, Any]]` — returns {version, content_md, content_json, word_count, sha256}
- `get_latest_version(persona_id) -> Optional[Dict[str, Any]]`
- `get_all_latest() -> Dict[str, Optional[Dict[str, Any]]]`
- `list_persona_ids() -> List[str]` — all persona IDs from manifest
- `list_active_persona_ids() -> List[str]` — fresh/stale/pending_review (excludes archived/missing)
- `list_persona_paths() -> List[str]` — fresh/stale only (content engine integration)
- `check_staleness(persona_id, threshold_days) -> bool` — per-persona age-based
- `check_kb_staleness(kb_synthesis_version: int) -> bool` — manifest vs KB synthesis version
- `mark_persona_status(persona_id, status) -> None` — update status in manifest

### Staleness
- Per-persona: age-based (`last_updated` vs `staleness_days` threshold)
- KB-triggered: if `kb_synthesis_version` in persona manifest < current KB synthesis version, all personas marked stale
- Refresh modes: `full` (re-run all), `refresh` (stale only), `single` (one persona)

---

## 3. Agents (`core/research/audience_persona/agents.py`)

### Agent 1 — Persona Suggester
- **Model**: Google Gemini Flash (`gemini-3-flash-preview`) via raw `google.genai` SDK
- **Why Gemini Flash**: Lightweight structured output task (3-5 short JSON briefs). Cheaper and faster than Claude Sonnet for this use case. Consistent with KB agents using Gemini.
- **Input**: company context md + customer reviews md + knowledge docs text (truncated with token budget)
- **Output**: `List[PersonaBrief]` (3-5 briefs)
- **Implementation**: Single `generate_content()` call with JSON schema enforcement; parse response
- **Validation**: If output has < 3 briefs, duplicates, or malformed JSON → automatic retry once with repair prompt. If still invalid → return partial results with error flag.

```python
async def run_persona_suggester(
    input_data: AudiencePersonaInput,
    company_context_md: str,
    customer_reviews_md: str,
    knowledge_docs_text: str = "",
    parent_span: Optional[Any] = None,
    timeout_s: float = 120.0,
) -> Tuple[List[PersonaBrief], float]:
    """Returns (briefs, execution_time_s). Validates and retries on malformed output."""
```

### Agent 2 — Persona Profile Generator
- **Model**: Perplexity `sonar-deep-research` via `asyncio.to_thread(perplexity_client.research, ...)`
- **Why Perplexity**: Deep web research to fill realistic KPIs, pain points, buying triggers, quotes with citations
- **Input**: Approved `PersonaBrief` + company context + customer reviews + knowledge docs
- **Output**: Full persona profile markdown with stable section headers (matching existing `PersonaArtifact.to_markdown()`)
- **Revision support**: `revision_note` appended as `## Reviewer Feedback` in prompt

```python
async def run_persona_profile_generator(
    brief: PersonaBrief,
    input_data: AudiencePersonaInput,
    company_context_md: str,
    customer_reviews_md: str,
    knowledge_docs_text: str = "",
    parent_span: Optional[Any] = None,
    timeout_s: float = 300.0,
    revision_note: Optional[str] = None,
) -> PersonaAgentResult:
    """Generate detailed persona profile from an approved brief."""
```

### Knowledge Docs Loading Helper
```python
async def _load_knowledge_docs(
    artifacts_root: Path,
    effective_slug: str,
    company_slug: str,
    max_chars: int = 50_000,
) -> str:
    """Load and concatenate text from uploaded knowledge docs.

    Follows effective_slug -> company_slug fallback chain.
    Per-doc: header with filename, then extracted text.
    Truncates total to max_chars with warning log.
    Returns empty string if no docs uploaded.
    """
```

Uses existing `load_metadata()`, `slug_dir()`, `extract_text()` from `core/shared_tools/`.

### Context Truncation Strategy
- Company context MD: first 15K chars (well within Gemini/Perplexity context)
- Customer reviews MD: first 10K chars
- Knowledge docs: 50K chars total (split proportionally across docs)
- Each context section prefixed with a `--- {section_name} ---` header for model clarity

---

## 4. Prompts (`core/research/prompts/`)

Both prompt files follow the existing KB prompt pattern: `SYSTEM_PROMPT` constant + `_HUB_NAME` + `get_*_system_prompt()` with hub fallback + `build_*_user_prompt()` builder.

### `core/research/prompts/persona_suggester.py`

**Hub name**: `research-persona-suggester-system`

**Functions**:
- `get_persona_suggester_system_prompt() -> str`
- `build_persona_suggester_user_prompt(input_data, company_context_md, customer_reviews_md, knowledge_docs_text) -> str`

**System Prompt** (PERSONA_SUGGESTER_SYSTEM_PROMPT):
```
You are a B2B Audience Research Strategist. Your job is to analyze a company's
product positioning, customer reviews, and internal documents to identify 3-5
distinct buyer personas who represent the company's most important target segments.

## Your Task

Analyze the provided context and produce a JSON array of persona briefs. Each
persona must represent a genuinely different buyer type — different roles, industries,
or buying motivations. Avoid overlapping personas.

## Output Format

Return ONLY a valid JSON array. Each element must have:
- "persona_name": A realistic first name (e.g., "Sarah", "Marcus")
- "tagline": Role + context in <12 words (e.g., "VP of Finance at mid-market SaaS companies")
- "description": One sentence describing who this person is and what they care about
- "rationale": Array of 2-3 bullet points explaining why this persona is a good fit
  for the company's product. Reference specific evidence from the context.

## Rules
- Suggest between {min_personas} and {max_personas} personas
- The FIRST persona should be the ICP (Ideal Customer Profile) — the highest-value buyer
- Secondary personas should represent meaningfully different segments
- Ground every rationale point in evidence from the provided context
- If customer reviews mention specific job titles, pain points, or use cases, use them
- Do NOT invent generic personas — they must be rooted in the data
- Do NOT include any text outside the JSON array
```

**User Prompt** (assembled by builder):
```
## Company Context
{company_context_md[:15000]}

## Customer Reviews & Feedback
{customer_reviews_md[:10000]}

## Internal Documents (uploaded by company)
{knowledge_docs_text[:50000] if knowledge_docs_text else "No internal documents provided."}

## Requirements
- Company: {input_data.company_name}
- Domain: {input_data.domain}
- Target persona count: {input_data.max_personas}
- Language: {input_data.language}
- Region: {input_data.region or "Global"}
{f"- Additional constraints: {input_data.additional_constraints}" if input_data.additional_constraints else ""}

Analyze the above context and return a JSON array of {input_data.max_personas} persona briefs.
```

---

### `core/research/prompts/persona_generator.py`

**Hub name**: `research-persona-generator-system`

**Functions**:
- `get_persona_generator_system_prompt() -> str`
- `build_persona_generator_user_prompt(brief, input_data, company_context_md, customer_reviews_md, knowledge_docs_text, revision_note=None) -> str`

**System Prompt** (PERSONA_GENERATOR_SYSTEM_PROMPT):
```
You are a Deep Audience Research Agent. You are given a persona brief (a hypothesis
about a target buyer) along with company context and customer feedback. Your job is
to research this persona type deeply and produce a comprehensive, evidence-backed
persona profile.

## Output Structure (Stable Section Headers — do not rename)

Write the profile in Markdown with these exact section headers:

# Persona: {persona_name} ({ICP or SECONDARY})

**Company:** {company_name}
**Role/Title:** {role_title}
**Industry context:** {industry}

## Persona Summary
A 3-5 sentence overview of who this person is, what they do, and why they matter
as a buyer for this product.

## Role & Context
What does their typical role look like? Org structure, reporting lines, team size,
budget authority, industry context. Be specific with real-world examples.

## Day-in-the-Life Mechanics
Walk through a typical week. What tools do they use? What meetings do they attend?
What metrics do they track? What frustrations do they encounter daily?

## KPIs / What Success Means
What are they measured on? What would make their boss praise them? What would get
them promoted? Be concrete — revenue targets, efficiency ratios, compliance metrics.

## Pain Points & Blockers
What problems keep them up at night? What's broken in their current workflow?
What have they tried that didn't work? Ground in evidence from reviews or research.

## Buying Triggers
What events or situations trigger them to look for a solution? Budget cycles,
compliance deadlines, team growth, competitive pressure, executive mandates.

## Trust Builders & Objections
What makes them trust a vendor? What are their top 3 objections? How do they
evaluate solutions? Who else influences the decision?

## Annoyances
What do they hate in vendor interactions? What messaging turns them off? What
do competitors do that frustrates them?

## Messaging Angles
3-5 specific messaging approaches that would resonate with this persona. Each should
be a concrete angle with rationale, not a generic "focus on ROI" statement.

## Quotes
5-8 realistic quotes this persona might say, reflecting their pain points, goals,
and buying mindset. Mark real quotes with [Source] and synthesized quotes with
[Synthesized].

## Sources
List all sources used with URLs where available. Use [1], [2], etc. inline citations
throughout the profile.

## Rules
- 2000-5000 words
- Write in third person ("Sarah tends to..." not "You tend to...")
- Ground claims in evidence — cite sources with [N] inline
- Include specific numbers, tools, platforms, job titles, industry benchmarks
- Do NOT use jargon: "leverage", "synergy", "best-in-class", "cutting-edge"
- Do NOT be generic — every section should feel specific to this persona type
- If internal documents provide direct quotes or data, prioritize them
```

**User Prompt** (assembled by builder):
```
## Persona Brief
- Name: {brief.persona_name}
- Tagline: {brief.tagline}
- Description: {brief.description}
- Why this persona fits:
{chr(10).join(f"  - {r}" for r in brief.rationale)}

## Company Context
{company_context_md[:15000]}

## Customer Reviews & Feedback
{customer_reviews_md[:10000]}

## Internal Documents
{knowledge_docs_text[:50000] if knowledge_docs_text else "No internal documents provided."}

## Requirements
- Company: {input_data.company_name}
- Domain: {input_data.domain}
- Language: {input_data.language}
- Region: {input_data.region or "Global"}
{f"- Additional constraints: {input_data.additional_constraints}" if input_data.additional_constraints else ""}

Research this persona type deeply and produce a comprehensive persona profile
following the output structure above.

{f"## Reviewer Feedback\n\nAddress the following feedback from the reviewer:\n\n{revision_note}" if revision_note else ""}
```

---

## 5. Pipeline DAG (`core/research/audience_persona/pipeline.py`)

```
Phase 0: Preflight + Load Context
  |  VALIDATE: company_context/{slug}.md exists (fail with actionable error if missing)
  |  VALIDATE: knowledge_base/{slug}/customer_reviews/ exists (warn if missing, proceed)
  |  Read company_context/{slug}.md (truncate to 15K chars)
  |  Read knowledge_base/{slug}/customer_reviews/v{latest}.md (truncate to 10K chars)
  |  Load knowledge_docs/{effective_slug}/ (concatenate, truncate to 50K chars)
  |  Record kb_synthesis_version from KB manifest for staleness tracking
  v
Phase 1: Agent 1 — Persona Suggester
  |  Produces 3-5 PersonaBrief objects
  |  Validation: retry once if < 3 briefs or malformed JSON
  |  Edge case: if 0 valid briefs after retry → fail pipeline with clear error
  v
HITL-1: Per-Persona Brief Approval
  |  Present all briefs to human
  |  Per-brief: approve / modify / reject
  |  Human can ADD new briefs (manual entries)
  |  Edge case: if ALL briefs rejected AND no added_briefs → end pipeline gracefully
  |  Collect approved_briefs list
  v
Phase 2: Agent 2 — Profile Generator (parallel)
  |  For each approved brief: run_persona_profile_generator()
  |  asyncio.gather() with return_exceptions=True
  |  Concurrency cap: asyncio.Semaphore(min(len(briefs), settings.max_concurrent))
  |  Per-persona failure: mark error in PersonaAgentResult, don't fail entire pipeline
  |  Storage writes serialized through asyncio.Lock (prevent manifest race conditions)
  |  Store each successful result via PersonaStorage.write_version()
  v
HITL-2: Profile Review (optional, skippable via auto_approve)
  |  Present per-persona: approve / revise (re-run with revision_note) / reject
  |  Send trimmed previews (500 chars) + storage paths (not full content)
  |  Per-persona revision: re-run only that persona with revision_note
  |  Rejected profiles: remove from manifest, mark archived
  v
Phase 3: Finalize
  |  Update manifest with last_full_run + kb_synthesis_version
  |  Emit SSE: completed
```

### Main Entry
```python
async def run_audience_persona_pipeline(
    input_data: AudiencePersonaInput,
    *,
    task_id: Optional[str] = None,
    task_store: Optional[Any] = None,
    event_bus: Optional[Any] = None,
    artifacts_root: Optional[Path] = None,
) -> AudiencePersonaOutput:
```

### Preflight Validation
```python
def _preflight_check(artifacts_root: Path, slug: str) -> Tuple[str, str]:
    """Check KB outputs exist. Returns (company_context_md, customer_reviews_md).
    Raises RuntimeError with actionable message if company context is missing.
    Logs warning if customer reviews missing (proceeds with empty string).
    """
```

### Parallel Agent 2 Execution + Per-Persona HITL-2 (inspired by content engine v1.3)

**Phase 2: All approved briefs run in parallel** via `asyncio.gather()`:
```python
# Dispatch all generators in parallel (like content engine's dispatch_workers_v13)
semaphore = asyncio.Semaphore(min(len(approved_briefs), settings.audience_persona_max_concurrent_generators))

async def _run_single_generator(brief: PersonaBrief) -> PersonaAgentResult:
    async with semaphore:
        gen_span = create_span(phase2_span, f"generator/{brief.brief_id}")
        result = await run_persona_profile_generator(
            brief=brief, input_data=input_data,
            company_context_md=company_md, customer_reviews_md=reviews_md,
            knowledge_docs_text=kdocs_text, parent_span=gen_span,
        )
        log_generation(gen_span, f"persona-gen-{brief.brief_id}", ...)
        end_span(gen_span, output={"word_count": result.word_count})

        # Serialize storage writes through lock (prevent manifest races)
        if not result.error:
            async with storage_lock:
                storage.write_version(brief.brief_id, brief.persona_name,
                                      result.content_md, result.content_json)
        return result

tasks = [_run_single_generator(b) for b in approved_briefs]
raw_results = await asyncio.gather(*tasks, return_exceptions=True)

# Separate successes from failures (like dispatcher.py pattern)
persona_results: Dict[str, PersonaAgentResult] = {}
for brief, res in zip(approved_briefs, raw_results):
    if isinstance(res, Exception):
        res = PersonaAgentResult(brief_id=brief.brief_id, persona_name=brief.persona_name,
                                 error=str(res)[:500])
    persona_results[brief.brief_id] = res
```

**HITL-2: Per-persona sequential review** (mirrors content engine v1.3's per-piece HITL-3 loop):

Unlike HITL-1 (batch presentation), HITL-2 presents ALL profiles together in a single interrupt but receives per-persona decisions. The revision loop re-runs only revised personas:

```python
# Present all profiles for review via single HITL checkpoint
profile_summaries = {pid: {"content_preview": r.content_md[:500], "word_count": r.word_count, ...}
                     for pid, r in persona_results.items() if not r.error}

hitl2_state = {"profile_summaries": profile_summaries, "checkpoint": 2,
               "auto_approve": 2 in auto_approve_cps}
hitl2_result = await run_ap_hitl_checkpoint(profile_review_graph, hitl2_state, ...)

# Process per-persona decisions
for review in hitl2_result.get("profile_reviews", []):
    pid = review["persona_id"]
    decision = review["decision"]

    if decision == "approve":
        # Already stored in Phase 2 — mark as approved in manifest
        async with storage_lock:
            _mark_persona_approved(storage, pid)

    elif decision == "revise":
        # Re-run Agent 2 for this persona only (like content engine's _apply_human_edits)
        brief = _get_brief_by_id(approved_briefs, pid)
        revision_note = review.get("revision_note", "")
        rev_span = create_span(hitl2_span, f"revision/{pid}")
        revised = await run_persona_profile_generator(
            brief=brief, input_data=input_data, ...,
            revision_note=revision_note, parent_span=rev_span,
        )
        end_span(rev_span, output={"word_count": revised.word_count})
        if not revised.error:
            async with storage_lock:
                storage.write_version(pid, brief.persona_name,
                                      revised.content_md, revised.content_json)
        persona_results[pid] = revised

    elif decision == "reject":
        async with storage_lock:
            _mark_persona_archived(storage, pid)
```

**Key design insight**: Unlike content engine v1.3 which loops per-piece with while loops (because each piece can be edited/rebriefed multiple times), our HITL-2 allows **one revision pass** per persona — the reviewer sees results, gives feedback, agent re-runs once, result stored. This keeps the pipeline simpler while still providing quality control.

### Concurrency Safety
- `asyncio.Lock` (`storage_lock`) protects `PersonaStorage.write_version()` and `write_manifest()` during Phase 2 parallel writes and HITL-2 revision writes
- Per-slug lock in task_store prevents overlapping pipeline runs for same company
- Shared slug lock scope covers both KB and persona pipelines (prevent simultaneous artifact mutations)

### SSE Events
- `pipeline_start` (pipeline="audience_persona")
- `ap_phase_start` (phase, agents)
- `ap_agent_complete` (agent, persona_name, word_count, has_error)
- `ap_phase_complete` (phase)
- `pending_approval` (stage, checkpoint, briefs/profiles payload)
- `approval_received` (stage, decision)
- `completed` / `failed`

---

## 6. LangGraph HITL Graphs (`core/research/audience_persona/graph.py`)

### HITL-1: Brief Review Graph

```python
class APBriefReviewState(TypedDict, total=False):
    briefs: list                # List[PersonaBrief.model_dump()]
    checkpoint: int             # Always 1
    auto_approve: bool
    presented_at: int
    # Resume values:
    batch_decision: str         # "approve_all" | "partial" | "reject_all"
    brief_reviews: list         # List[PersonaBriefReview.model_dump()]
    added_briefs: list          # List[PersonaBrief.model_dump()] — manual entries
    approved_briefs: list       # Final approved set (computed after resume)
```

**Interrupt payload** (sent to frontend):
```json
{
    "status": "pending_persona_approval",
    "stage": "persona_brief_review",
    "checkpoint": 1,
    "briefs": [{"brief_id": "pb-001", "persona_name": "...", "tagline": "...", ...}]
}
```

**Resume payload** (received from frontend):
```json
{
    "batch_decision": "partial",
    "brief_reviews": [
        {"brief_id": "pb-001", "decision": "approve"},
        {"brief_id": "pb-002", "decision": "modify", "modified_brief": {...}},
        {"brief_id": "pb-003", "decision": "reject"}
    ],
    "added_briefs": [
        {"persona_name": "...", "tagline": "...", "description": "...", "rationale": [...]}
    ]
}
```

**Gate node processing after resume**:
1. Filter out rejected briefs
2. For "modify" decisions: replace brief with `modified_brief`, set `source="hybrid"`
3. Append `added_briefs` with `source="manual"` and generated `brief_id`s
4. Set `approved_briefs` on state

### HITL-2: Profile Review Graph (Per-Persona Decisions)

```python
class APProfileReviewState(TypedDict, total=False):
    profile_summaries: dict     # {persona_id: {content_preview, word_count, has_error, storage_path}}
    checkpoint: int             # Always 2
    auto_approve: bool
    presented_at: int
    # Resume values (per-persona, not batch):
    profile_reviews: list       # List[{persona_id, decision, revision_note}]
    approved_profiles: list     # [persona_id, ...] — computed after resume
```

**Interrupt payload** (sent to frontend — trimmed previews only):
```json
{
    "status": "pending_persona_profile_approval",
    "stage": "persona_profile_review",
    "checkpoint": 2,
    "profiles": {
        "vp-finance": {"content_preview": "first 500 chars...", "word_count": 3200, "has_error": false, "storage_path": "vp-finance/v1.md"},
        "head-ops": {"content_preview": "first 500 chars...", "word_count": 2800, "has_error": false, "storage_path": "head-ops/v1.md"}
    }
}
```

**Resume payload** (per-persona decisions):
```json
{
    "profile_reviews": [
        {"persona_id": "vp-finance", "decision": "approve"},
        {"persona_id": "head-ops", "decision": "revise", "revision_note": "Add more about procurement triggers"}
    ]
}
```

**Gate node processing**: For each profile_review, if `decision == "revise"`, re-run Agent 2 for that persona only with `revision_note`. If `decision == "reject"`, mark persona as archived in manifest.

### Invocation Helper
`run_ap_hitl_checkpoint()` — identical pattern to `run_kb_hitl_checkpoint()` in `core/research/knowledge_base/graph.py`.

---

## 7. API Endpoints (`api/routers/audience_persona.py`)

### POST `/api/v1/audience-persona/start` (202)
- Auth: `require_role("member", "superuser")`
- Request: `AudiencePersonaStartRequest` (company_name, domain, product_slug, max_personas, auto_approve_checkpoints, force_rerun)
- Guard: If persona manifest exists with active personas AND not force_rerun AND not stale → return 200
- **Staleness auto-detect**: If KB synthesis version > manifest's `kb_synthesis_version`, allow rerun even without `force_rerun`
- Creates background task via `asyncio.create_task(run_audience_persona_pipeline_task(...))`
- Returns `PipelineRunResponse` with run_id, status

### GET `/api/v1/audience-persona/{run_id}/status`
- Auth: `require_auth`
- Returns task status with approval_payload if pending

### POST `/api/v1/audience-persona/{run_id}/approve/briefs` (Checkpoint 1)
- Auth: `require_role("member", "superuser")`
- Dedicated endpoint for brief approval (avoids stage-dependent body parsing)
- Request: `PersonaBriefApprovalRequest` with `{batch_decision, brief_reviews, added_briefs}`
- Validation: at least 1 persona must be approved or added (unless batch_decision="reject_all")
- Calls `task_store.submit_approval()`

### POST `/api/v1/audience-persona/{run_id}/approve/profiles` (Checkpoint 2)
- Auth: `require_role("member", "superuser")`
- Dedicated endpoint for profile review
- Request: `PersonaProfileApprovalRequest` with `{profile_reviews}` (per-persona decisions)
- Calls `task_store.submit_approval()`

### POST `/api/v1/audience-persona/{slug}/add-persona` (standalone)
- Auth: `require_role("member", "superuser")`
- For manual persona brief entry OUTSIDE pipeline flow
- Request: `ManualPersonaBrief` body (persona_name, tagline, description, rationale)
- Creates persona_id, writes brief to storage
- Launches Agent 2 as async task to generate profile
- Profile stored with `status="pending_review"` — visible in list but excluded from content engine until reviewed
- Returns persona_id + task_id

### POST `/api/v1/audience-persona/{slug}/personas/{persona_id}/approve` (standalone review)
- Auth: `require_role("member", "superuser")`
- Approve a `pending_review` persona (from standalone add)
- Request: `{decision: "approve" | "reject"}`
- On approve: sets status to "fresh", persona becomes available to content engine

### GET `/api/v1/audience-persona/{slug}/personas`
- Auth: `require_auth`
- List all persona profiles with metadata (includes status field)

---

## 8. Runner Integration (`api/tasks/runner.py`)

### `run_audience_persona_pipeline_task()`
```python
async def run_audience_persona_pipeline_task(
    task_id: str,
    request: Any,
    task_store: TaskStoreProtocol,
    event_bus: EventBus,
    auth_service: Optional[Any] = None,
) -> None:
```

Follows exact same pattern as `run_kb_pipeline_task()`:
1. Derive slug, resolve scope
2. Acquire semaphore
3. Build `AudiencePersonaInput` from request
4. Call `run_audience_persona_pipeline()`
5. Update task with COMPLETED/FAILED + produced_artifacts
6. Release slug lock + remove handle

### Content Engine Integration
Extend `resolve_artifacts()` in `runner.py` to check `artifacts/audience_personas/{slug}/` for persona paths, with fallback to legacy `artifacts/personas/{slug}__persona-*.md`.

---

## 9. LangSmith Tracing Integration

Reuse `core/shared_tools/tracing.py` functions directly — no new tracing module needed.

### Trace Hierarchy
```
pipeline-trace (audience-persona/{slug}) [RunTree]
  ├── span/0-preflight-context                     # Phase 0: load context
  ├── span/1-persona-suggester                     # Phase 1: Agent 1
  │   └── log_generation (gemini-flash, input/output)
  ├── span/hitl-1-brief-review                     # HITL-1
  ├── span/2-profile-generators                    # Phase 2: parallel Agent 2
  │   ├── span/generator/{persona_id_1}            #   per-persona child span
  │   │   └── log_generation (perplexity, input/output)
  │   ├── span/generator/{persona_id_2}
  │   └── ...
  ├── span/hitl-2-profile-review                   # HITL-2
  │   ├── span/revision/{persona_id}               #   if revised, new child span
  │   │   └── log_generation (perplexity, input/output)
  ├── span/3-finalize                              # Phase 3: finalize + manifest
```

### Integration Points in pipeline.py
```python
from core.shared_tools.tracing import (
    create_session, create_pipeline_trace, create_span,
    end_span, log_generation, update_trace_output, flush,
)

# At pipeline start:
session_id = create_session(slug)
pipeline_trace = create_pipeline_trace(
    session_id, slug, input_data.company_name,
    metadata={"pipeline": "audience_persona", "mode": mode},
    project_name=settings.langsmith_project,
)

# Per agent call:
agent_span = create_span(pipeline_trace, f"generator/{persona_id}")
# ... agent execution ...
log_generation(agent_span, f"persona-gen-{persona_id}",
    model=settings.audience_persona_generator_model,
    input_text=user_prompt[:5000], output_text=result.content_md[:5000],
    usage={"word_count": result.word_count})
end_span(agent_span, output={"word_count": result.word_count})

# At pipeline end:
update_trace_output(pipeline_trace, output={
    "profiles_generated": len(persona_results),
    "total_time_s": total_time,
})
flush()
```

### Context-var Propagation for LangGraph Nodes
Since LangGraph serializes state with msgpack (can't serialize RunTree), use `set_current_span()` / `get_current_span()` for out-of-band span propagation to graph nodes — same pattern as content engine v1.3 (`core/content_engine/pipeline_v13.py`).

---

## 10. Settings Additions (`core/config/settings.py`)

```python
audience_persona_suggester_model: str = "gemini-3-flash-preview"
audience_persona_generator_model: str = "sonar-deep-research"  # Uses perplexity_client
audience_persona_max_concurrent_generators: int = 3
```

---

## 11. Phased Implementation (TDD)

### Phase A: Foundation — Models + Storage + Prompts ✅ COMPLETE (106 tests)

**Delivered**: 2026-03-06 | **Tests**: 106 (30 model + 41 storage + 35 prompt)

| File | Type | Lines | Description |
|------|------|-------|-------------|
| `core/models/audience_persona.py` | NEW | 141 | 9 Pydantic models + 2 enums + staleness constant |
| `core/research/audience_persona/__init__.py` | NEW | — | Module init |
| `core/research/audience_persona/storage.py` | NEW | 227 | PersonaStorage — manifest CRUD, brief persistence, versioned profiles, staleness, list helpers |
| `core/research/prompts/persona_suggester.py` | NEW | 79 | Agent 1 system + user prompt builders with Hub fallback |
| `core/research/prompts/persona_generator.py` | NEW | 115 | Agent 2 system + user prompt builders with revision_note support |
| `core/config/settings.py` | MOD | +4 | 3 new settings: `audience_persona_suggester_model`, `audience_persona_generator_model`, `audience_persona_max_concurrent_generators` |
| `tests/research/audience_persona/test_models_ap.py` | NEW | 30 tests | Enums, defaults, bounds validation, JSON roundtrips for all 9 models |
| `tests/research/audience_persona/test_storage_ap.py` | NEW | 41 tests | Manifest CRUD, brief persistence, version writes/reads, list helpers, staleness (age + KB), mark status |
| `tests/research/audience_persona/test_prompts_ap.py` | NEW | 35 tests | System prompts (content, headers, hub), user prompts (all fields, truncation, revision notes) |

**Key implementation details**:
- `PersonaProfileEntry.status` includes `"pending_review"` and `"archived"` (beyond plan's 3 statuses) for manual persona gating
- `PersonaStorage.check_kb_staleness()` takes `kb_synthesis_version: int` directly (simpler than taking `KBStorage` instance)
- `PersonaStorage.list_persona_paths()` excludes `pending_review` profiles (content engine only sees `fresh`/`stale`)
- `PersonaStorage.list_active_persona_ids()` includes `pending_review` (visible in UI, not in content engine)
- Prompt truncation: 15K company context, 10K customer reviews, 50K knowledge docs (matching plan)

### Phase B: Agents ✅ COMPLETE (41 tests)

**Delivered**: 2026-03-06 | **Tests**: 41

| File | Type | Lines | Description |
|------|------|-------|-------------|
| `core/research/audience_persona/agents.py` | NEW | ~150 | `run_persona_suggester()` (Gemini Flash) + `run_persona_profile_generator()` (Perplexity deep research) |
| `tests/research/audience_persona/test_agents_ap.py` | NEW | 41 tests | Mocked LLM calls, happy path, timeout, parse failure, retry on malformed JSON, empty results |

### Phase C: HITL Graphs ✅ COMPLETE (40 tests)

**Delivered**: 2026-03-06 | **Tests**: 40

| File | Type | Lines | Description |
|------|------|-------|-------------|
| `core/research/audience_persona/graph.py` | NEW | ~493 | 2 LangGraph sub-graphs (brief review + profile review), `run_ap_hitl_checkpoint()` invocation helper |
| `tests/research/audience_persona/test_graph_ap.py` | NEW | 40 tests | Brief review (auto-approve, interrupt, resume, modified briefs, added briefs, fail-closed), profile review (auto-approve, interrupt/resume, per-persona decisions, fail-open, empty summaries) |

### Phase D: Pipeline Orchestrator ✅ COMPLETE (45 tests)

**Delivered**: 2026-03-06 | **Tests**: 45 | **Codex-reviewed** (9 findings incorporated)

| File | Type | Lines | Description |
|------|------|-------|-------------|
| `core/research/audience_persona/pipeline.py` | NEW | ~280 | 4-phase orchestrator: preflight → suggester → HITL-1 → parallel generators → HITL-2 → finalize. Frozen ID map, SSE events, LangSmith tracing |
| `tests/research/audience_persona/test_pipeline_ap.py` | NEW | 45 tests | Full flow, auto-approve, reject at HITL-1/HITL-2, knowledge docs loading, manual brief entry, preflight validation, concurrent generator limit, content preview truncation |

### Phase E: API + Runner ✅ COMPLETE (50 tests)

**Delivered**: 2026-03-06 | **Tests**: 50 | **Codex-reviewed** (8 findings incorporated)

| File | Type | Lines | Description |
|------|------|-------|-------------|
| `api/tasks/models.py` | MOD | +1 | Added `"audience_persona"` to `PipelineTask.pipeline` Literal |
| `api/schemas/audience_persona.py` | NEW | ~188 | 12 schema classes: start request, brief/profile approval, standalone add/approve, list response |
| `api/routers/audience_persona.py` | NEW | ~320 | 7 endpoints: start, status, approve/briefs, approve/profiles, add-persona, standalone-approve, list-personas |
| `api/tasks/runner.py` | MOD | +115 | `run_audience_persona_pipeline_task()` + `run_single_persona_generator_task()` |
| `api/app.py` | MOD | +2 | Import + `include_router(audience_persona.router)` |
| `tests/api/test_audience_persona_router.py` | NEW | ~530 | 8 test classes: start (13), status (4), approve/briefs (10), approve/profiles (8), add-persona (4), standalone-approve (5), list-personas (3), auth (3) |

**Key implementation details**:
- Guard logic: only `fresh|stale` personas count as active; `pending_review`/`archived` do NOT block reruns
- KB staleness auto-detect: if KB `synthesis_version` > AP manifest's `kb_synthesis_version` → bypass guard
- Separate HITL approval endpoints per checkpoint (content_v13 pattern, not single /approve like KB)
- Stage-aware validation + nonce replay protection via `_validate_approval_window()` + `expected_nonce`
- Approval data format matches graph resume exactly: CP1 = `{batch_decision, brief_reviews, added_briefs}`, CP2 = `{profile_reviews}`
- Standalone add-persona uses managed task lifecycle: `create_task` + `register_task_handle` + semaphore + slug lock
- Slug scope safety: runner sets `company_slug=scope.effective_slug`; pipeline's `_resolve_slug()` returns as-is, preventing double-suffixing
- Path traversal prevention via regex validation on `persona_id` and `slug` path params

### Phase F: Integration (~20 tests)
16. Extend `resolve_artifacts()` in runner.py to read from `artifacts/audience_personas/{slug}/` directly (no backward-compat copy — content engine reads new path natively, with fallback to legacy `artifacts/personas/` for old data)
17. Concurrency tests: verify `asyncio.Lock` prevents manifest corruption under parallel write_version()
18. Delayed approval tests: mock task_store for hours-later approval, verify state rebuilds correctly
19. Integration tests: full KB → persona → content engine artifact resolution

**Current total: 282 tests** (Phase A: 106, B: 41, C: 40, D: 45, E: 50). Phase F remaining (~20 tests).

**IMPORTANT**: Do NOT run the full test suite (`pytest tests/`) until Phase F is complete. It takes too long. For Phases B-E, only run the audience persona tests (`pytest tests/research/audience_persona/ -v`) and AP API tests (`pytest tests/api/test_audience_persona_router.py -v`) to verify no regressions.

---

## Critical Files to Modify

| File | Change |
|------|--------|
| `core/models/audience_persona.py` | **NEW** — All pipeline models |
| `core/research/audience_persona/` | **NEW** — Full module (agents, pipeline, graph, storage) |
| `core/research/prompts/persona_suggester.py` | **NEW** — Suggester prompts |
| `core/research/prompts/persona_generator.py` | **NEW** — Generator prompts |
| `api/routers/audience_persona.py` | **NEW** — REST endpoints |
| `api/tasks/runner.py` | **MODIFY** — Add pipeline task + extend resolve_artifacts() |
| `api/app.py` | **MODIFY** — Register new router |
| `core/config/settings.py` | **MODIFY** — Add 3 new settings with defaults |

---

## Reference Patterns (Reuse)

| Pattern | Source File | Reuse |
|---------|------------|-------|
| Versioned storage + manifest | `core/research/knowledge_base/storage.py` | Mirror for PersonaStorage |
| LangGraph HITL interrupt/resume | `core/research/knowledge_base/graph.py` | Mirror for persona graphs |
| Pipeline orchestrator with DAG | `core/research/knowledge_base/pipeline.py` | Mirror for persona pipeline |
| Perplexity deep research wrapper | `core/research/tools/perplexity_client.py` | Direct reuse for Agent 2 |
| Knowledge docs loading | `api/services/knowledge_doc_service.py` + `core/shared_tools/knowledge_doc_metadata.py` | Direct reuse |
| Task runner pattern | `api/tasks/runner.py` (run_kb_pipeline_task) | Mirror for persona task |
| PersonaArtifact section headers | `core/models/personas.py` | Reuse stable headers in Agent 2 output |
| SSE event emission | `_emit()` pattern in KB pipeline.py | Direct reuse |
| Prompt registry hub lookup | `core/content_engine/prompt_registry.py` | Direct reuse |
| LangSmith tracing | `core/shared_tools/tracing.py` | Direct reuse (create_session, create_span, etc.) |
| Context-var span propagation | `core/content_engine/pipeline_v13.py` (set_current_span) | Direct reuse for graph nodes |
| Parallel worker dispatch | `core/content_engine/workers/dispatcher.py` (dispatch_workers_v13) | Pattern mirror for Phase 2 parallel generators |
| Per-piece HITL review loop | `core/content_engine/pipeline_v13.py` (HITL-3 per-piece) | Pattern inspiration for HITL-2 per-persona review |
| KB prompt pattern (revision_note) | `core/research/prompts/company_overview.py` | Mirror for persona prompts |

---

## Verification

### How to test end-to-end:
1. **Unit tests**: `pytest tests/research/audience_persona/ -v` — all ~200 tests pass
2. **API tests**: `pytest tests/api/test_audience_persona_router.py -v`
3. **Manual smoke test**:
   - Upload knowledge docs via `POST /api/v1/companies/{slug}/knowledge-docs`
   - Run KB pipeline first to produce company profile + customer reviews
   - Start audience persona pipeline: `POST /api/v1/audience-persona/start`
   - Check status / SSE events for persona brief suggestions
   - Approve briefs via `POST /api/v1/audience-persona/{run_id}/approve`
   - Wait for profile generation, approve profiles
   - Verify artifacts at `artifacts/audience_personas/{slug}/`
   - Verify content engine picks up persona paths via `resolve_artifacts()`

### Key invariants to verify:
- All Pydantic fields have defaults
- No LangChain wrappers used
- LangGraph >=1.0 interrupt model (`__interrupt__` in result dict, not exception)
- Filesystem-first storage (JSON artifacts are source of truth)
- core/ does not import from api/
- Double-underscore separator for effective slugs

---

## Codex Review Feedback (Incorporated)

The plan was reviewed by gpt-5-codex. Key feedback that was incorporated:

1. **Preflight validation** — Pipeline now validates KB outputs exist before running (Phase 0)
2. **Agent 1 validation** — Auto-retry on malformed JSON / < 3 briefs before surfacing to HITL
3. **HITL-2 per-persona** — Changed from batch decision to per-persona `profile_reviews` list
4. **Concurrent write safety** — Added `asyncio.Lock` for PersonaStorage writes during parallel Phase 2
5. **Separate approval endpoints** — Split `/approve` into `/approve/briefs` and `/approve/profiles`
6. **Trimmed payloads** — HITL-2 sends 500-char previews + storage paths, not full content
7. **Manual persona gating** — Standalone `add-persona` stores with `pending_review` status until explicitly approved
8. **Agent 1 model** — Changed from Claude Sonnet to Gemini Flash (cheaper for structured output task)
9. **Semaphore tuning** — `min(len(briefs), settings.max_concurrent)` instead of fixed 3
10. **No backward-compat copy** — Content engine reads from `artifacts/audience_personas/` directly with fallback to legacy path
11. **KB staleness tracking** — Records `kb_synthesis_version` in persona manifest; auto-allows rerun when KB updates
12. **Context truncation** — Explicit per-section char budgets (15K company, 10K reviews, 50K knowledge docs)
13. **All briefs rejected** — Pipeline ends gracefully instead of failing
14. **Concurrency tests** — Added stress tests for parallel writes and delayed approval scenarios
