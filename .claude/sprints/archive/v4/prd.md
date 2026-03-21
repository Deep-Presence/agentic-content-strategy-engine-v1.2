# Company Knowledge Base Architecture
## Deep Presence — Brand Brain Knowledge Foundation

---

## 1. The Core Problem

The current Research Pipeline runs a **single DeepAgent** (Gemini + Perplexity) that attempts to research everything about a company in one pass. This produces a single `company_context/{slug}.md` artifact. The result is:

- **Shallow coverage** — one agent can't deeply research competitors, reviews, brand perception, AND company overview in a single invocation
- **No granularity** — everything lives in one monolithic markdown file, making partial updates impossible
- **No living document capability** — re-running means discarding everything and starting from scratch
- **No separation of source material from synthesized output** — raw research and the final artifact are the same thing

### What We Want Instead

A **layered knowledge architecture** where:
1. Multiple specialist research agents each produce deep, focused research documents
2. Raw research is stored as versioned source material in a knowledge base
3. A synthesis step compresses source materials into a final Company Profile artifact
4. Any individual research workstream can be re-run independently without losing other work
5. The final artifact updates incrementally when source materials change

---

## 2. Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    LAYER 3: OPERATIONAL CONTEXT                  │
│                                                                   │
│  Company Profile Artifact    Persona Artifact    Style Guide     │
│  (synthesized, compressed)   (synthesized)       (synthesized)   │
│                                                                   │
│  → These are what get injected into Gap Analysis & Content Engine │
├─────────────────────────────────────────────────────────────────┤
│                    LAYER 2: KNOWLEDGE BASE                       │
│                                                                   │
│  Versioned source documents — each produced by a specialist      │
│  research agent or uploaded by the user                          │
│                                                                   │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────────┐ │
│  │ Company       │ │ Customer     │ │ Competitor               │ │
│  │ Overview      │ │ Reviews &    │ │ Landscape                │ │
│  │ Research      │ │ Testimonials │ │ (registry + profiles)    │ │
│  └──────────────┘ └──────────────┘ └──────────────────────────┘ │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────────┐ │
│  │ Competitor    │ │ Brand        │ │ User-Uploaded            │ │
│  │ Weaknesses &  │ │ Perception   │ │ Documents                │ │
│  │ Industry Gaps │ │ Brief        │ │ (transcripts, decks...)  │ │
│  └──────────────┘ └──────────────┘ └──────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                    LAYER 1: RAW INPUTS                           │
│                                                                   │
│  Web research results, API responses, scraped reviews,           │
│  uploaded PDFs, sales call transcripts, internal notes           │
│  (ephemeral — consumed during research, not persisted long-term) │
└─────────────────────────────────────────────────────────────────┘
```

**Key insight**: Layer 2 is the new thing. Currently you jump from Layer 1 (raw Perplexity search) straight to Layer 3 (final artifact). The knowledge base layer is the missing middle — it stores structured, reviewed research that can be independently updated and re-synthesized.

---

## 3. Knowledge Base Document Types

Each document in the knowledge base (Layer 2) is a **typed, versioned, independently producible** research artifact.

### 3.1 Document Type Registry

| Type ID | Name | Producer | Update Cadence | Depends On |
|---------|------|----------|----------------|------------|
| `company_overview` | Company Overview Research | Agent: Company Overview | Quarterly / on-demand | None |
| `customer_reviews` | Customer Reviews & Testimonials | Agent: Review Harvester | Monthly / on-demand | None |
| `competitor_registry` | Competitor Landscape Registry | Agent: Competitor Scanner | Quarterly / on-demand | `company_overview` (for category context) |
| `competitor_weaknesses` | Competitor Weakness Analysis | Agent: Weakness Analyst | Quarterly / on-demand | `competitor_registry` |
| `brand_perception` | Brand Perception Brief | Agent: Perception Analyst | Monthly / on-demand | `customer_reviews`, `competitor_registry` |
| `user_upload` | User-Uploaded Document | Manual upload | On upload | None |

### 3.2 Document Schema (Pydantic)

```python
class KnowledgeDocument(BaseModel):
    """A single document in the company knowledge base."""
    
    id: str                          # UUID
    company_slug: str
    product_slug: Optional[str]      # None = company-level
    doc_type: KnowledgeDocType       # Enum of the types above
    title: str
    version: int                     # Monotonically increasing
    status: Literal["draft", "approved", "stale"]
    
    # Content
    content_md: str                  # Markdown body
    content_structured: Optional[dict]  # Parsed structured data (JSON)
    
    # Provenance
    produced_by: Literal["agent", "user", "synthesis"]
    agent_model: Optional[str]       # e.g. "gemini-3-flash-preview"
    source_run_id: Optional[str]     # Research pipeline run that created this
    sources: List[SourceReference]   # Citations / data sources used
    
    # Lifecycle
    created_at: datetime
    updated_at: datetime
    researched_at: datetime          # When the underlying research was performed
    staleness_days: int = 90         # After this many days, mark as "stale"
    
    # Relationships
    depends_on: List[str] = []       # IDs of upstream documents
    supersedes: Optional[str]        # ID of previous version


class KnowledgeBase(BaseModel):
    """The full knowledge base for a company."""
    
    company_slug: str
    documents: Dict[str, KnowledgeDocument]  # id -> doc
    
    # Convenience accessors
    def get_by_type(self, doc_type: KnowledgeDocType) -> List[KnowledgeDocument]: ...
    def get_latest(self, doc_type: KnowledgeDocType) -> Optional[KnowledgeDocument]: ...
    def get_stale_documents(self) -> List[KnowledgeDocument]: ...
    def get_completeness_score(self) -> float: ...
```

### 3.3 Document Interdependencies (DAG)

```
company_overview ──────┬──────────────────────────────┐
                       │                               │
                       ▼                               │
              competitor_registry ───┐                 │
                       │             │                 │
                       ▼             │                 │
            competitor_weaknesses    │                 │
                                     │                 │
customer_reviews ────────────────────┤                 │
                                     │                 │
                                     ▼                 ▼
                              brand_perception    SYNTHESIS
                                     │               ▲
                                     └───────────────┘
                                                      │
                                                      ▼
                                          Company Profile Artifact
                                              (Layer 3)
```

This DAG governs:
- **Execution order**: Which research agents can run in parallel vs sequentially
- **Staleness propagation**: If `competitor_registry` updates, `competitor_weaknesses` and `brand_perception` become stale
- **Incremental re-synthesis**: Only re-synthesize the Company Profile if any upstream document changed

---

## 4. Research Agent Design (Layer 2 Producers)

### 4.1 Architecture Pattern: Specialist Agents

Each research workstream gets its own specialist agent rather than one monolithic agent. This follows the principle you already use for content generation — Orchestrator-Workers pattern.

```
┌─────────────────────────────────────────────────────────┐
│                KNOWLEDGE RESEARCH ORCHESTRATOR            │
│                                                           │
│  Input: company_name, domain, options                    │
│  Output: Updated KnowledgeBase with all research docs    │
│                                                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │ Company      │  │ Review      │  │ Competitor      │  │
│  │ Overview     │  │ Harvester   │  │ Scanner         │  │
│  │ Agent        │  │ Agent       │  │ Agent           │  │
│  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘  │
│         │                │        ┌──────────┘           │
│         │                │        │                      │
│         │                │        ▼                      │
│         │                │  ┌─────────────────┐          │
│         │                │  │ Weakness         │          │
│         │                │  │ Analyst Agent    │          │
│         │                │  └────────┬────────┘          │
│         │                │           │                   │
│         ▼                ▼           ▼                   │
│  ┌─────────────────────────────────────────────────┐    │
│  │         Brand Perception Analyst Agent           │    │
│  └──────────────────────┬──────────────────────────┘    │
│                          │                               │
│                          ▼                               │
│  ┌─────────────────────────────────────────────────┐    │
│  │         SYNTHESIS AGENT (Company Profile)        │    │
│  │         Reads all Layer 2 docs → produces L3     │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

### 4.2 Execution Strategy

**Phase 1 — Parallel (no dependencies)**:
- Company Overview Agent
- Customer Review Harvester Agent

**Phase 2 — Depends on Phase 1**:
- Competitor Scanner Agent (needs company_overview for category/market context)

**Phase 3 — Depends on Phase 2**:
- Competitor Weakness Analyst (needs competitor_registry)

**Phase 4 — Depends on Phases 1-3**:
- Brand Perception Analyst (needs customer_reviews + competitor_registry)

**Phase 5 — Synthesis**:
- Company Profile Synthesizer (reads ALL Layer 2 docs → produces Layer 3 artifact)

**HITL Checkpoints** (matching your existing pattern):
- After Phase 1+2: Review company overview + reviews (lightweight check)
- After Phase 3+4: Review competitor landscape + brand perception (substantive review)
- After Phase 5: Review final Company Profile artifact (approve/revise/reject)

### 4.3 Agent Specifications

#### Agent 1: Company Overview Research

**Purpose**: Deep research on origin story, business model, products, market position, team, recent news.

**Tools**: `internet_search` (Perplexity sonar-deep-research), `read_local_text`

**Output**: `company_overview` document (~3,000-5,000 words)

**Prompt structure**: (Your existing prompt from the message, the "Research [COMPANY NAME]" prompt with Origin Story, Business Reality, What They Actually Do, etc.)

**Key difference from current**: This agent ONLY produces the company overview. It does NOT try to also do reviews, competitors, and brand perception. Focused = deeper.

---

#### Agent 2: Customer Review Harvester

**Purpose**: Find 100+ real customer quotes, reviews, testimonials across platforms.

**Tools**: `internet_search`, `platform_search` (G2, Capterra, TrustRadius, Reddit, app stores)

**Output**: `customer_reviews` document with structured data:

```python
class CustomerReview(BaseModel):
    quote: str
    source_platform: str           # "G2", "Reddit", "Capterra", etc.
    source_url: Optional[str]
    reviewer_role: Optional[str]   # "CFO at mid-market SaaS"
    sentiment: Literal["positive", "negative", "neutral", "mixed"]
    themes: List[str]              # ["ease of use", "pricing", "support"]
    use_case: Optional[str]        # "expense management for remote teams"
    date: Optional[str]

class CustomerReviewsDocument(BaseModel):
    total_reviews_analyzed: int
    reviews: List[CustomerReview]
    
    # Aggregated analysis
    sentiment_distribution: Dict[str, int]    # {"positive": 67, "negative": 18, ...}
    top_positive_themes: List[ThemeCount]
    top_negative_themes: List[ThemeCount]
    common_use_cases: List[str]
    notable_quotes: List[str]                 # Best 10-15 for marketing use
```

---

#### Agent 3: Competitor Scanner

**Purpose**: Identify top 20 direct + mindshare competitors with structured profiles.

**Tools**: `internet_search`, `site_analyzer` (basic domain metrics)

**Output**: `competitor_registry` document:

```python
class CompetitorProfile(BaseModel):
    name: str
    domain: str
    website: str
    relevance: Literal["direct", "indirect", "mindshare", "niche"]
    relevance_score: float                   # 0.0-1.0
    category_overlap: List[str]              # shared product categories
    estimated_authority: Optional[str]       # "high", "medium", "low"
    organic_presence: Optional[str]          # qualitative assessment
    key_differentiators: List[str]
    target_audience_overlap: float           # 0.0-1.0
    market_position: str                     # brief positioning statement
    
class CompetitorRegistryDocument(BaseModel):
    direct_competitors: List[CompetitorProfile]        # Top 10 direct
    mindshare_competitors: List[CompetitorProfile]     # Top 10 audience overlap
    market_map: str                                     # Markdown narrative
    competitive_positioning_summary: str
```

**Output format**: Both human-readable markdown AND structured JSON (the `content_structured` field on KnowledgeDocument). The JSON is what downstream agents and the gap analysis pipeline consume.

---

#### Agent 4: Competitor Weakness Analyst

**Purpose**: Deep-dive into negative reviews and shortcomings of the top-k direct competitors.

**Tools**: `internet_search`, `platform_search` (review sites)

**Input dependency**: Reads `competitor_registry` to know which competitors to analyze.

**Output**: `competitor_weaknesses` document:

```python
class CompetitorWeakness(BaseModel):
    competitor_name: str
    competitor_domain: str
    weakness_category: str            # "UX", "pricing", "support", "reliability", etc.
    description: str
    severity: Literal["critical", "significant", "minor"]
    evidence: List[str]               # Specific review quotes or data points
    opportunity_for_us: str           # How our client can exploit this gap

class IndustryProblem(BaseModel):
    problem: str
    affected_competitors: List[str]
    user_impact: str
    is_solvable: bool

class CompetitorWeaknessDocument(BaseModel):
    per_competitor: Dict[str, List[CompetitorWeakness]]    # competitor_name -> weaknesses
    systemic_industry_problems: List[IndustryProblem]
    strategic_opportunities: List[str]                      # Top opportunities for our client
```

---

#### Agent 5: Brand Perception Analyst

**Purpose**: Cross-platform sentiment analysis and market position assessment.

**Tools**: `internet_search`, `platform_search` (Reddit, G2, Quora, app stores, Glassdoor)

**Input dependencies**: Reads `customer_reviews` + `competitor_registry`

**Output**: `brand_perception` document following the structure you outlined:

```python
class BrandPerceptionDocument(BaseModel):
    # A. Company Overview
    market_position: str
    brand_positioning: str
    core_positioning: str
    key_differentiators: List[str]
    
    # B. Competitive Landscape
    competitive_strategies: Dict[str, str]       # vs each major player
    
    # C. User Perception
    sentiment_analysis: SentimentBreakdown
    strengths_liked_by_users: List[str]
    challenges_and_pain_points: List[str]
    
    # D. Key Themes
    trust_transparency: str
    platform_insights: PlatformInsights          # iOS, Android, web
    employer_reputation: Optional[str]           # Glassdoor/Indeed
    policy_safety: Optional[str]
    content_aesthetics: Optional[str]
    
    # E. Overall Assessment
    current_state_summary: str
    strategic_recommendations: List[str]
```

---

### 4.4 The Synthesis Agent (Layer 2 → Layer 3)

This is the crucial new component. It reads ALL knowledge base documents and produces the final Company Profile artifact.

**Input**: All approved Layer 2 documents for the company
**Output**: The `company_context/{slug}.md` artifact (Layer 3)

**Why a separate synthesis step matters**:
- The synthesis agent can apply a specific **Company Profile Prompt** (the one you mentioned attaching) that structures the output for downstream consumption
- It can prioritize, compress, and resolve contradictions across source documents
- When a single source document updates, the synthesizer can do a **delta re-synthesis** — it receives the previous artifact + the changed source document and produces an updated artifact
- The synthesis prompt can be versioned and improved independently of the research agents

```python
class SynthesisInput(BaseModel):
    company_slug: str
    knowledge_documents: List[KnowledgeDocument]    # All approved L2 docs
    previous_artifact: Optional[str]                 # Previous Company Profile (for delta mode)
    company_profile_prompt: str                      # The synthesis prompt template
    mode: Literal["full", "delta"]                   # Full rebuild vs incremental update
    
class SynthesisOutput(BaseModel):
    artifact_md: str                                 # The final Company Profile markdown
    sections_changed: List[str]                      # Which sections were updated (delta mode)
    source_coverage: Dict[str, float]                # How much of each source doc was used
    confidence_scores: Dict[str, float]              # Per-section confidence
    open_questions: List[str]                        # Things that need more research
```

---

## 5. Storage Design

### 5.1 Filesystem Layout (extends existing pattern)

```
artifacts/
├── knowledge_base/                              # NEW — Layer 2
│   └── {company_slug}/
│       ├── _manifest.json                       # Index of all docs + metadata
│       ├── company_overview/
│       │   ├── v1.md                            # Version 1 (superseded)
│       │   ├── v2.md                            # Version 2 (current approved)
│       │   └── v2.json                          # Structured data companion
│       ├── customer_reviews/
│       │   ├── v1.md
│       │   └── v1.json                          # Contains List[CustomerReview]
│       ├── competitor_registry/
│       │   ├── v1.md
│       │   ├── v1.json
│       │   └── v1.csv                           # Human-readable export
│       ├── competitor_weaknesses/
│       │   ├── v1.md
│       │   └── v1.json
│       ├── brand_perception/
│       │   ├── v1.md
│       │   └── v1.json
│       └── uploads/                             # User-uploaded documents
│           ├── sales-call-transcript-2026-01.md
│           ├── q4-pitch-deck.md                 # Extracted text from PDF
│           └── existing-persona-draft.md
│
├── company_context/                             # EXISTING — Layer 3 (unchanged)
│   ├── ramp.md                                  # Synthesized Company Profile
│   └── ramp.draft.md
├── personas/                                    # EXISTING — Layer 3
│   └── ramp__persona-icp.md
└── style_guides/                                # EXISTING — Layer 3
    └── ramp.md
```

### 5.2 Manifest File (`_manifest.json`)

The manifest is the index for the knowledge base. It tracks all documents, their versions, statuses, and relationships.

```json
{
  "company_slug": "ramp",
  "last_full_research": "2026-03-01T10:00:00Z",
  "last_synthesis": "2026-03-01T12:30:00Z",
  "completeness_score": 0.83,
  "documents": [
    {
      "id": "doc-uuid-1",
      "doc_type": "company_overview",
      "title": "Ramp — Company Overview",
      "version": 2,
      "status": "approved",
      "current_file": "company_overview/v2.md",
      "structured_file": "company_overview/v2.json",
      "produced_by": "agent",
      "agent_model": "gemini-3-flash-preview",
      "source_run_id": "run-uuid-abc",
      "researched_at": "2026-03-01T10:15:00Z",
      "staleness_days": 90,
      "is_stale": false,
      "depends_on": []
    },
    {
      "id": "doc-uuid-2",
      "doc_type": "customer_reviews",
      "title": "Ramp — Customer Reviews & Testimonials",
      "version": 1,
      "status": "approved",
      "current_file": "customer_reviews/v1.md",
      "structured_file": "customer_reviews/v1.json",
      "produced_by": "agent",
      "researched_at": "2026-03-01T10:20:00Z",
      "staleness_days": 30,
      "is_stale": false,
      "depends_on": []
    }
  ],
  "uploads": [
    {
      "id": "upload-uuid-1",
      "filename": "sales-call-transcript-2026-01.md",
      "upload_type": "sales_transcript",
      "uploaded_at": "2026-02-15T09:00:00Z",
      "uploaded_by": "user-uuid-123"
    }
  ]
}
```

### 5.3 Production Storage Strategy

In production, knowledge base documents follow the existing Three-Tier storage model established in the SQLAlchemy migration. Document **metadata** (id, company_id, doc_type, version, status, staleness, dependencies, provenance, sha256, word_count) lives in a `knowledge_documents` Postgres table alongside a `content_structured` JSONB column that holds the queryable structured extract for each doc type — competitor names and domains for `competitor_registry`, sentiment distributions for `customer_reviews`, positioning fields for `brand_perception`. This is what the API filters against and what downstream pipelines query programmatically. The **full markdown body** and large JSON companions live in object storage (Supabase Storage / S3) referenced by a `storage_key` pointer on the Postgres row — keeping the relational layer lean and avoiding bloat from 5-30KB documents across multiple versions. The `StorageBackend` abstraction already defined in `core/storage/backends/base.py` swaps `LocalFilesystemBackend` (dev) for `SupabaseStorageBackend` (production) based on environment config, so pipeline agents continue reading from file paths regardless of where the blob physically lives. For pipeline execution, an upfront hydration step pre-fetches needed artifacts from object storage into a temp directory at run start, giving workers local file paths with zero refactoring. The rule of thumb: if downstream code needs to `SELECT ... WHERE` or extract fields from it, it goes in `content_structured` JSONB; if it's consumed as a complete document (read-all-or-nothing), it stays in object storage.

During development, the filesystem layout with `_manifest.json` described above serves as the working implementation — the manifest maps cleanly to the `knowledge_documents` table and version files map to `knowledge_document_versions` rows when the DB migration happens.

---

## 6. The "Living Document" Mechanism

### 6.1 Staleness Tracking

Each document type has a configurable `staleness_days` threshold:

| Document Type | Default Staleness | Rationale |
|---------------|-------------------|-----------|
| `company_overview` | 90 days | Fundamentals change slowly |
| `customer_reviews` | 30 days | New reviews appear frequently |
| `competitor_registry` | 90 days | Competitive landscape shifts slowly |
| `competitor_weaknesses` | 60 days | Product changes affect weakness landscape |
| `brand_perception` | 45 days | Perception shifts with product updates and PR |

The Brand Brain dashboard shows staleness indicators:

```
┌──────────────────────────────────────────────────────┐
│  Knowledge Base Health                    Score: 83%  │
│                                                        │
│  ✅  Company Overview         Updated 12 days ago     │
│  ⚠️  Customer Reviews         Updated 45 days ago     │
│  ✅  Competitor Landscape      Updated 20 days ago     │
│  🔴  Competitor Weaknesses     Updated 95 days ago     │
│  ⚠️  Brand Perception          Updated 50 days ago     │
│                                                        │
│  [🔄 Refresh Stale]  [🔬 Full Research]               │
└──────────────────────────────────────────────────────┘
```

### 6.2 Incremental Update Flow

When a user clicks "Refresh Stale" or a scheduled job fires:

```
1. Check manifest → identify stale documents
2. Resolve dependency order (DAG topological sort)
3. For each stale document:
   a. Run the specialist agent with:
      - Previous version of this document (for delta awareness)
      - Any upstream documents that have been updated since last run
      - New user uploads since last run
   b. Produce new version (v{n+1})
   c. HITL checkpoint: approve/revise/reject
   d. On approve: update manifest, mark as current
4. After all stale docs refreshed:
   a. Run Synthesis Agent in DELTA mode
   b. Input: previous Company Profile + changed source docs
   c. HITL checkpoint on updated Company Profile
5. Propagate staleness: mark downstream documents as stale if
   their dependencies changed
```

### 6.3 Delta Synthesis vs Full Rebuild

**Delta mode** (triggered by incremental refresh):
- Synthesis agent receives the previous Company Profile + only the documents that changed
- Prompt instructs: "Update the following sections based on new research. Preserve sections that haven't changed."
- Faster, cheaper, less disruptive

**Full rebuild** (triggered by "Full Research" or first-time generation):
- All agents run from scratch
- Synthesis agent builds Company Profile from all Layer 2 docs with no prior artifact
- Used on onboarding or when the user wants a complete refresh

---

## 7. Integration with Existing Pipelines

### 7.1 How Gap Analysis Consumes This

Currently, `s2_generate_queries.py` reads `company_context_path` for category context. With the knowledge base:

```python
# Current: reads single file
company_context_md = Path(company_context_path).read_text()

# New: reads Layer 3 artifact (unchanged path)
# BUT the artifact is now richer because it was synthesized from 5+ source documents
company_context_md = Path(f"artifacts/company_context/{slug}.md").read_text()

# NEW CAPABILITY: Gap analysis can also directly read Layer 2 docs
# For competitor names (currently hardcoded or shallow):
competitor_registry = load_knowledge_doc(slug, "competitor_registry")
competitor_names = [c.name for c in competitor_registry.direct_competitors]
```

The key insight: **Layer 3 artifacts remain the primary interface** for downstream pipelines. The knowledge base is an implementation detail of how those artifacts get produced. Existing pipeline code needs minimal changes.

### 7.2 How Content Engine Consumes This

The content engine's `build_drafter_user_prompt` already receives `company_context_md`, `persona_mds`, and `style_guide_md`. These remain the same — they're just higher quality now because they're synthesized from deeper research.

**Optional enhancement**: The content drafter could receive select Layer 2 excerpts:
- `customer_reviews` → Real quotes to weave into content (massive authenticity boost)
- `competitor_weaknesses` → Specific competitor gaps to address in content
- `brand_perception` → Positioning language that resonates with actual user sentiment

### 7.3 How Daily Tracker Benefits

The Daily Tracker's `mention_detector` needs brand + competitor names. Currently these are configured manually. With the knowledge base:

```python
# Competitor names auto-populated from knowledge base
competitor_registry = load_knowledge_doc(slug, "competitor_registry")
competitors = [
    {"name": c.name, "domain": c.domain, "relevance": c.relevance}
    for c in competitor_registry.direct_competitors + competitor_registry.mindshare_competitors
]
```

---

## 8. API Design

### 8.1 New Endpoints

```
# Knowledge Base CRUD
GET    /api/v1/knowledge/{slug}                    → KnowledgeBaseResponse (manifest + doc summaries)
GET    /api/v1/knowledge/{slug}/{doc_type}          → KnowledgeDocumentResponse (latest version)
GET    /api/v1/knowledge/{slug}/{doc_type}/versions  → List[VersionSummary]
GET    /api/v1/knowledge/{slug}/{doc_type}/v/{n}     → Specific version content
PUT    /api/v1/knowledge/{slug}/{doc_type}          → Update/edit a document manually
DELETE /api/v1/knowledge/{slug}/{doc_type}/v/{n}     → Delete specific version

# User Uploads
POST   /api/v1/knowledge/{slug}/uploads             → Upload document (multipart)
GET    /api/v1/knowledge/{slug}/uploads              → List uploads
DELETE /api/v1/knowledge/{slug}/uploads/{upload_id}  → Remove upload

# Research Operations
POST   /api/v1/knowledge/{slug}/research/full        → Run full research (all agents)
POST   /api/v1/knowledge/{slug}/research/refresh      → Refresh stale documents only
POST   /api/v1/knowledge/{slug}/research/{doc_type}   → Run specific agent only
POST   /api/v1/knowledge/{slug}/synthesize            → Re-synthesize Company Profile from current L2 docs

# Health & Status
GET    /api/v1/knowledge/{slug}/health               → Staleness report + completeness score
```

### 8.2 Relationship to Existing Endpoints

The existing research pipeline endpoints (`POST /api/v1/research/start`) continue to work. The knowledge base research is a **superset** — it breaks the monolithic research into focused agents. You could:

**Option A — Replace**: New `/knowledge/{slug}/research/full` replaces `POST /research/start` for the company stage. The persona and style_guide stages continue as-is but now benefit from a richer Company Profile.

**Option B — Parallel** (recommended for migration): Keep existing research pipeline. Add knowledge base as an independent system. Once knowledge base is stable, wire the Company Profile synthesis output to replace the old `company_context` artifact. Zero disruption.

---

## 9. LangGraph State Machine Design

### 9.1 Knowledge Research Graph

```python
class KnowledgeResearchState(TypedDict):
    company_slug: str
    domain: str
    mode: Literal["full", "refresh", "single"]
    target_doc_types: List[str]
    
    # Phase outputs (populated as agents complete)
    company_overview: Optional[KnowledgeDocument]
    customer_reviews: Optional[KnowledgeDocument]
    competitor_registry: Optional[KnowledgeDocument]
    competitor_weaknesses: Optional[KnowledgeDocument]
    brand_perception: Optional[KnowledgeDocument]
    
    # HITL state
    pending_approval: Optional[str]              # doc_type awaiting approval
    revision_note: Optional[str]
    
    # Synthesis
    synthesis_output: Optional[str]              # Final Company Profile markdown
    synthesis_approved: bool
    
    # User uploads (injected as context to agents)
    user_uploads: List[str]                      # Paths to uploaded docs
```

### 9.2 Graph Topology

```
START
  │
  ├──────────────────────┐
  ▼                      ▼
[company_overview]    [customer_reviews]      ← Phase 1 (parallel)
  │                      │
  ├──────────────────────┤
  ▼                      │
[HITL: review P1]        │                    ← HITL Checkpoint 1
  │                      │
  ▼                      │
[competitor_scanner] ◄───┘                    ← Phase 2 (needs overview)
  │
  ├──────────────────────┐
  ▼                      ▼
[weakness_analyst]    [brand_perception]       ← Phase 3 (parallel)
  │                      │
  ├──────────────────────┤
  ▼
[HITL: review P2-3]                           ← HITL Checkpoint 2
  │
  ▼
[synthesize_company_profile]                  ← Phase 4
  │
  ▼
[HITL: review profile]                        ← HITL Checkpoint 3
  │
  ▼
END → write artifacts to filesystem
```

---

## 10. Product-Level Knowledge Bases

Everything above applies at the product level using your existing `effective_slug` pattern:

```
artifacts/knowledge_base/ramp/                          # Company-level
artifacts/knowledge_base/ramp__ramp-corporate-card/     # Product-level
```

**Inheritance**: Product-level knowledge bases inherit from company-level. If a product doesn't have its own `competitor_registry`, the synthesis agent falls back to the company-level one (matching your existing fallback chain pattern from D2 in §23.2).

---

## 11. Implementation Phasing

### Phase 1 — Foundation ✅ COMPLETE
- [x] `core/models/knowledge_base.py` — 17 Pydantic models (KBDocType, KBDocVersion, KBDocEntry, KBManifest, KBAgentResult, KnowledgeBaseInput/Output, per-agent structured output models)
- [x] `core/research/knowledge_base/storage.py` — KBStorage class (manifest CRUD, versioning, staleness, synthesis read/write)
- [x] `core/shared_tools/tracing.py` — Promoted tracing module from content engine (shared across pipelines)
- [x] `core/content_engine/tracing_v13.py` — Re-export shim (backward compat for 22+ existing importers)
- [x] `core/config/settings.py` — Added `research_kb_project`, `research_kb_brand_perception_model`, `research_kb_synthesis_model`
- [x] 70 new tests: 32 model tests + 32 storage tests + 6 tracing parity tests (all passing)
- **Plan file**: `.claude/plans/resilient-percolating-scroll.md`

### Phase 2 — Specialist Agents ✅ COMPLETE
- [x] 6 prompt files: company_overview, customer_reviews, competitor_scanner, weakness_analyst, brand_perception, synthesis — Hub getters + user prompt builders (core/research/prompts/)
- [x] Tool file: make_read_file_tool() factory with path-traversal guard (core/research/knowledge_base/tools.py)
- [x] Agent file: 6 agent functions + 3 helpers (core/research/knowledge_base/agents.py)
  - Tier 1: 4 Perplexity agents (asyncio.to_thread + wait_for)
  - Tier 2: Brand Perception (Anthropic AsyncAnthropic + web_search_20250305, _MAX_PAUSE_TURNS=5)
  - Tier 3: Synthesis (langgraph.prebuilt.create_react_agent + Claude Opus + read_file tool)
- [x] 54 new tests (15 prompt + 8 tool + 32 agent) — all passing. 124 total KB tests.
- [x] Codex-reviewed (gpt-5.3-codex): C-1 pause_turn guard fixed, C-2 api_key fixed. 7 deferred to backlog.
- **Plan file**: `.claude/plans/flickering-churning-pillow.md`

### Phase 3 — Orchestration ✅ COMPLETE
- [x] `core/research/knowledge_base/graph.py` — 2 HITL sub-graphs (KBDocReviewState, KBSynthesisReviewState) + `run_kb_hitl_checkpoint` async helper
- [x] `core/research/knowledge_base/pipeline.py` — DAG orchestrator: 4 phases, 3 modes (full/refresh/single), `asyncio.gather` parallel execution, revision note injection
- [x] Revision note injection — `revision_note: Optional[str]` on all 6 prompt builders + agent functions
- [x] `api/tasks/runner.py` — `run_kb_pipeline_task()` wrapper (semaphore + handle + slug-lock pattern)
- [x] `api/tasks/models.py` — Added `"knowledge_base"` to `PipelineTask.pipeline` Literal
- [x] 58 new tests (22 graph + 27 pipeline + 9 revision note). 151 total KB tests passing.
- **Plan file**: `.claude/plans/jazzy-wibbling-pelican.md`
- **Decisions**: D-KB-P3-1 (pipeline-with-inline-HITL), D-KB-P3-2 (revision injection), D-KB-P3-3 (self-contained HITL helper)

### Phase 4 — API Router + Schemas + Review Fixes ✅ COMPLETE
- [x] `api/routers/knowledge_base.py` — 3 endpoints (POST /start, GET /status, POST /approve) with tenant isolation, pipeline guard, CX-3 revision note translation
- [x] `api/schemas/common.py` — `KnowledgeBaseStartRequest` (mode, refresh_docs, single_doc, auto_approve_checkpoints, staleness_threshold_days)
- [x] 28 tests: start (11), guard (4), status (3), approve (7), auth (3)
- [x] **Review Fixes (KB-H1, KB-H2, KB-M1, KB-M3, CL-L1)**:
  - KB-H1: Strengthened `_normalize_refresh_docs` validator — `mode=single` without `single_doc` → 422, `mode=refresh` without `refresh_docs` → 422, `mode=full` clears both fields
  - KB-H2: Approval nonce handling — extract `checkpoint_nonce` from `approval_payload`, pass `expected_nonce` to `submit_approval()`, catch `ApprovalWindowError` → 409
  - KB-M1: `auto_approve_checkpoints` field validator — rejects values not in `{1, 2, 3}`
  - KB-M3: 7 new negative tests (3 mode validation, 3 auto_approve validation, 1 duplicate approval 409)
  - CL-L1: Removed unused `MagicMock` import
- [x] 35 total KB API tests passing (28 original + 7 review fixes)

### Phase 5 — Synthesis & Living Document
- [ ] Synthesis Agent (all L2 docs → Company Profile)
- [ ] Delta synthesis mode
- [ ] Staleness tracking + propagation
- [ ] "Refresh Stale" endpoint and scheduled refresh

### Phase 6 — Integration
- [ ] Wire synthesized Company Profile to existing gap analysis pipeline
- [ ] Wire competitor registry to Daily Tracker
- [ ] Frontend: Knowledge Base section in Brand Brain
- [ ] Frontend: Health dashboard with staleness indicators

---

## 12. Key Design Principles

1. **Layer 2 is the differentiator.** Anyone can run a single LLM to research a company. The knowledge base with typed, versioned, independently updatable source documents is what makes the research deep and maintainable.

2. **Layer 3 artifacts remain the interface.** Downstream pipelines (gap analysis, content engine) don't need to know about the knowledge base. They consume the same `company_context/{slug}.md` file — it's just dramatically better quality now.

3. **Filesystem first, database later.** Following your established principle: build on filesystem with JSON manifests, migrate to PostgreSQL when the schema is proven.

4. **Specialist agents over generalist.** Five focused agents that each go deep on their domain produce better results than one agent trying to cover everything. This is the same insight behind your content engine's Orchestrator-Workers pattern.

5. **The DAG governs everything.** Document dependencies determine execution order, staleness propagation, and incremental refresh scope. Get the DAG right and the system is self-managing.

6. **User uploads enrich, not replace.** Uploaded documents (sales transcripts, pitch decks) are injected as additional context to the research agents. They don't replace agent research — they complement it with insider knowledge the agents can't find on the web.