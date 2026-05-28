# Core Pydantic Models

> **Location:** `core/models/`
> **Owner:** Core
> **Dependencies:** Pydantic v2, datetime, enum
> **Dependents:** All pipelines, API schemas, services, DB layer
> **Last Updated:** 2026-04-09

## Overview

The models module defines all Pydantic v2 data models used throughout the system. These models serve as the contracts between pipelines, API endpoints, services, and storage layers. There are 16 files containing 100+ Pydantic models and 30+ enums. Every model field has a default value for backward compatibility with existing JSON artifacts.

## Architecture

Models are organized by pipeline/domain. They are used for:
1. **Pipeline I/O** — Input/output contracts for each pipeline
2. **Serialization** — `model_dump(mode="json")` for JSON artifacts
3. **Validation** — Type checking and field constraints
4. **API contracts** — Shared types between `core/` and `api/schemas/`

## File Structure

| File | Purpose | Key Exports |
|------|---------|-------------|
| `__init__.py` | Package marker | (empty) |
| `audience_persona.py` | Audience Persona pipeline models | `PersonaBrief`, `PersonaManifest`, `AudiencePersonaInput/Output` |
| `content_generation.py` | Content Engine v1.2 models (legacy) | `ContentBrief`, `ContentGenerationInput` |
| `content_generation_v13.py` | Content Engine v1.3 models (active) | `ContentBlueprint`, `ContentGenerationInputV13`, `BriefV13` |
| `daily_tracker.py` | Daily Tracker models | `TrackedPrompt`, `DailyRunConfig`, `MentionAnalysis` |
| `gap_analysis.py` | Gap Analysis pipeline models | `GapAnalysisInput`, `CrawlResult`, `QueryGap` |
| `knowledge_base.py` | Knowledge Base models | `KBManifest`, `KBDocEntry`, `CompetitorRegistryStructured` |
| `knowledge_docs.py` | Knowledge Documents models | `KnowledgeDocument` |
| `onboarding.py` | Onboarding pipeline models | `OnboardingInput`, `OnboardingOutput` |
| `organization.py` | Organization/company models | `Company`, `Product`, `UserProfile`, `CompanyPipelineDefaults` |
| `pipeline_status.py` | Pipeline status tracking | `BriefPipelineStatus` (enum) |
| `reddit_hil.py` | Reddit HIL models | `RedditThread`, `RedditReplyDraft` |
| `research_orchestrator.py` | Research orchestrator models | `ResearchOrchestratorInput/Output` |
| `site_audit.py` | Site Audit pipeline models | `SiteAuditInput`, `SiteAuditResult` |
| `topic_discovery.py` | Topic Discovery models | `TopicDiscoveryManifest`, `TopicAssignment`, `SubdomainNode` |
| `voice_style_guide.py` | Voice Style Guide models | `AuthorBrief`, `VoiceStyleGuideManifest`, `VoiceStyleGuideInput/Output` |

## Enums Reference

### Pipeline Status Enums

| Enum | File | Values |
|------|------|--------|
| `BriefPipelineStatus` | `pipeline_status.py` | GAP_ANALYSIS_PENDING, GAP_ANALYSIS, GAP_ANALYSIS_COMPLETE, SUGGESTED, BRIEFING, BRIEF_REVIEW, PENDING_BRIEF_APPROVAL, APPROVED, OUTLINING, DRAFTING, LINKING, ENRICHING, EVALUATING, REVISING, REVIEW, PENDING_CONTENT_APPROVAL, COMPLETED, PUBLISHED, REJECTED, FAILED |
| `ContentStatus` | `content_generation.py` | PENDING, APPROVED, EDITED, REJECTED |
| `EntryMode` | `content_generation_v13.py` | AUTONOMOUS, MANUAL, TOPIC_DISCOVERY |
| `FeedbackRoute` | `content_generation_v13.py` | PASS, SECTION_LEVEL, MAJOR_CHANGE |

### Research Pipeline Enums

| Enum | File | Values |
|------|------|--------|
| `PersonaBriefDecision` | `audience_persona.py` | APPROVE, MODIFY, REJECT |
| `PersonaProfileDecision` | `audience_persona.py` | APPROVE, REVISE, REJECT |
| `KBDocType` | `knowledge_base.py` | COMPANY_OVERVIEW, CUSTOMER_REVIEWS, COMPETITOR_REGISTRY, WEAKNESS_ANALYSIS, BRAND_PERCEPTION, SYNTHESIS |
| `SubPipelineStatus` | `research_orchestrator.py` | pending, running, skipped, completed, failed |
| `OrchestratorStatus` | `research_orchestrator.py` | completed, completed_partial, failed |

### Daily Tracker Enums

| Enum | File | Values |
|------|------|--------|
| `Platform` | `daily_tracker.py` | OPENAI, CLAUDE, GEMINI, PERPLEXITY |
| `PromptCategory` | `daily_tracker.py` | BRAND_AWARENESS, PRODUCT_COMPARISON, FEATURE_QUERY, INDUSTRY_KNOWLEDGE, COMPETITOR_ANALYSIS, USE_CASE, GENERAL |
| `PromptSource` | `daily_tracker.py` | MANUAL, GAP_ANALYSIS, IMPORTED, FANOUT, CONTENT_INVENTORY |
| `PromptStatus` | `daily_tracker.py` | ACTIVE, PAUSED, ARCHIVED |
| `RunStatus` | `daily_tracker.py` | PENDING, RUNNING, COMPLETED, FAILED |

### Gap Analysis & Topic Discovery Enums

| Enum | File | Values |
|------|------|--------|
| `DiscoverySource` | `gap_analysis.py` | SITEMAP, SITEMAP_INDEX, ROBOTS_TXT, BFS_CRAWL, CANONICAL, HREFLANG, RSS_FEED, SEED_URL, REDIRECT, KNOWLEDGE_DOC |
| `BuyerStage` | `topic_discovery.py` | TOFU, MOFU, BOFU |
| `IntentType` | `topic_discovery.py` | informational, commercial, navigational, transactional |
| `AudienceSegmentType` | `topic_discovery.py` | individual_persona, team_group |
| `TopicDiscoveryStatus` | `topic_discovery.py` | draft, hitl_pending, discovery_complete, approved, archived |
| `TDSource` | `topic_discovery.py` | source_a, source_b, source_c, source_d |
| `RelevanceCell` | `topic_discovery.py` | relevant, marginal, irrelevant |
| `TopicAssignmentStatus` | `topic_discovery.py` | not_started, approved, rejected, in_gap_analysis, gap_analysis_complete, in_content_production, content_produced, published |

### Site Audit Enums

| Enum | File | Values |
|------|------|--------|
| `AuditDimension` | `site_audit.py` | crawlability, performance, on_page_seo, extractability, schema_markup, eeat, freshness, security |
| `AuditCheckSeverity` | `site_audit.py` | critical, high, medium, low, info |

### Onboarding Enums

| Enum | File | Values |
|------|------|--------|
| `OnboardingPhase` | `onboarding.py` | phase_a, phase_b, phase_c |
| `OnboardingPhaseStatus` | `onboarding.py` | pending, running, completed, failed, skipped |
| `OnboardingStatus` | `onboarding.py` | completed, completed_partial, failed |

## Key Model Groups

### Organization Models (`organization.py`)

```python
class Company(BaseModel):
    id: str = ""
    slug: str = ""
    name: str = ""
    domain: str = ""
    additional_domains: List[str] = []
    products: List[Product] = []
    industry: str = ""
    display_id_prefix: str = ""
    display_id_counter: int = 0

class Product(BaseModel):
    id: str = ""
    slug: str = ""
    name: str = ""
    domain: str = ""
    description: str = ""

class UserProfile(BaseModel):
    id: str = ""
    email: str = ""
    first_name: str = ""
    last_name: str = ""
    role: str = "member"
    company_id: str = ""
    is_active: bool = True
    # Property: full_name -> str

class CompanyPipelineDefaults(BaseModel):
    company_slug: str = ""
    language: str = "en"
    region: str = ""
    additional_constraints: str = ""
    max_personas: int = 5
    max_authors: int = 3
```

### Content Engine v1.3 Models (`content_generation_v13.py`)

```python
class ContentBlueprint(ContentBrief):  # Extends v1.2 ContentBrief
    sections: List[Dict[str, Any]] = []
    territory_queries: List[Dict[str, Any]] = []
    reading_hierarchy: Dict[str, Any] = {}
    must_hit_checklist: List[str] = []
    user_feedback: str = ""
    gap_context: Dict[str, Any] = {}
    gap_reasoning: str = ""
    tone_guidance: str = ""
    voice_guidance: str = ""
    register_guidance: str = ""
    target_persona: str = ""
    buyer_stage: str = ""
    intent_stage: str = ""
    topic_assignment_id: str = ""

class BriefV13(BaseModel):
    brief_id: str = ""
    display_id: str = ""
    title: str = ""
    content_type: str = ""
    target_word_count: int = 0
    persona: str = ""
    buyer_stage: str = ""
    brief_summary: str = ""
    topic_assignment_id: str = ""
    approval_status: str = "pending"
    # ... additional fields

class ContentGenerationInputV13(ContentGenerationInput):
    entry_mode: EntryMode = EntryMode.AUTONOMOUS
    max_topics: int = 6
    manual_prompt: str = ""
    manual_content_type: str = ""
    manual_target_word_count: int = 0
    gap_query_id: str = ""
    brief_id_hint: str = ""
    topic_discovery_id: str = ""
    topic_assignment_ids: List[str] = []
```

### Topic Discovery Models (`topic_discovery.py`)

```python
class SubdomainNode(BaseModel):
    id: str = ""
    parent_id: Optional[str] = None
    name: str = ""
    description: str = ""
    depth: int = 0
    source_provenance: Dict[str, Any] = {}
    confidence: float = 0.0
    children: List["SubdomainNode"] = []
    topic_count: int = 0
    priority_score: float = 0.0
    priority_factors: Dict[str, float] = {}

class TopicAssignment(BaseModel):
    id: str = ""
    subdomain_id: str = ""
    subdomain_name: str = ""
    topic_text: str = ""
    buyer_stage: BuyerStage = BuyerStage.TOFU
    intent_type: IntentType = IntentType.informational
    audience_segment: str = ""
    audience_segment_type: AudienceSegmentType = AudienceSegmentType.individual_persona
    relevance: RelevanceCell = RelevanceCell.relevant
    priority_score: float = 0.0
    status: TopicAssignmentStatus = TopicAssignmentStatus.not_started
    persona_id: str = ""
    persona_name: str = ""
    display_id: str = ""

class TopicDiscoveryManifest(BaseModel):
    slug: str = ""
    effective_slug: str = ""
    company_name: str = ""
    domain_name: str = ""
    status: TopicDiscoveryStatus = TopicDiscoveryStatus.draft
    taxonomy_version: int = 0
    matrix_version: int = 0
    scoring_version: int = 0
    persona_affinity_version: int = 0
```

### Gap Analysis Models (`gap_analysis.py`)

```python
class GapAnalysisInput(BaseModel):
    company_name: str
    domain: str
    company_slug: Optional[str] = None
    product_slug: Optional[str] = None
    queries: Optional[List[str]] = None
    max_crawl_pages: int = 500
    max_crawl_depth: int = 4
    engines: List[str] = ["openai", "claude", "gemini", "perplexity"]
    knowledge_doc_slug: Optional[str] = None

class QueryGap(BaseModel):
    query_id: str = ""
    query: str = ""
    cluster_name: str = ""
    cluster_id: str = ""
    avg_citation_similarity: float = 0.0
    best_company_similarity: float = 0.0
    company_cited: bool = False
    gap: float = 0.0
    classification: str = "no_data"
    content_brief: Optional[Dict[str, Any]] = None
    source_topic_ids: List[str] = []
```

## Inheritance Hierarchies

1. **ContentBlueprint** extends **ContentBrief** — v1.3 blueprint adds sections, territory queries, reading hierarchy, gap context, persona/stage targeting
2. **ContentGenerationInputV13** extends **ContentGenerationInput** — v1.3 adds entry mode, topic discovery integration, manual prompt fields

## Model Validators

| Model | Validator | Purpose |
|-------|-----------|---------|
| `GapAnalysisInput` | `_backfill_knowledge_doc_slug` | Auto-populates `knowledge_doc_slug` from deprecated `knowledge_doc_dir` |
| `SiteAuditInput` | `_derive_company_slug` | Auto-derives `company_slug` from `company_name` |
| `SiteAuditInput` | `_validate_product_slug` | Rejects path-traversal characters in product slug |

## Common Patterns

- **All fields have defaults** — backward compatibility with existing JSON artifacts
- **`model_dump(mode="json")`** — standard serialization pattern
- **`Field(default_factory=list)`** — mutable default fields use factory pattern
- **ISO datetime strings** — some models use `str` for timestamps (not `datetime`) for JSON compatibility
- **Optional fields** — use `Optional[T] = None` pattern consistently
- **`_utcnow()` helper** — shared datetime factory used across model files
