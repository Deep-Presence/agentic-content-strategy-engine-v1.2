# Pipeline 1a: Knowledge Base Research

> **Location:** `core/research/knowledge_base/`
> **Owner:** Core
> **Dependencies:** Perplexity, Anthropic SDK, LangGraph, OpenRouter, `core/research/tools/`, `core/research/prompts/`
> **Dependents:** Pipelines 1b, 1c, 3, 4 (downstream consumers of company context)
> **Last Updated:** 2026-04-09

## Overview

Pipeline 1a is a 6-agent research DAG that builds a comprehensive company knowledge base. It uses Perplexity deep research for web intelligence gathering, Anthropic Claude for brand perception analysis with real-time web search, and Claude Opus for synthesis. The pipeline has 3 HITL checkpoints and supports 4 execution modes: `full`, `refresh`, `single`, and `express`. The final synthesis is promoted to `company_context/{slug}.md` and consumed by all downstream pipelines.

## Architecture

```
Phase 1 (Parallel)              Phase 2 (Sequential)        Phase 3 (Parallel)
─────────────────              ──────────────────          ──────────────────
Agent 1: Company Overview ──┐
                             ├─► Agent 3: Competitor ──┐
Agent 2: Customer Reviews ──┘    Scanner               │
                                                        ├─► HITL-1 (review)
                                                        │
                                                        ├─► Agent 4: Weakness
                                                        │    Analysis
                                                        ├─► Agent 5: Brand
                                                        │    Perception
                                                        ├─► HITL-2 (review)
                                                        │
                                                        └─► Agent 6: Synthesis
                                                             ├─► HITL-3 (review)
                                                             └─► Promote to
                                                                 company_context/
```

## File Structure

| File | Lines | Purpose |
|------|-------|---------|
| `pipeline.py` | 1160 | Main orchestrator DAG |
| `agents.py` | 642 | 6 agent implementations |
| `graph.py` | 305 | LangGraph HITL graphs (3 checkpoints) |
| `storage.py` | 521 | Versioned artifact management (KBStorage) |
| `persistence.py` | 231 | DB persistence hooks |
| `extraction.py` | 193 | Competitor JSON extraction (Pass 2) |
| `tools.py` | 75 | Synthesis agent file-reading tool |

## 6 Agents

| Agent | Doc Type | Provider | Model | Input | Timeout |
|-------|----------|----------|-------|-------|---------|
| 1 | `company_overview` | Perplexity (OpenRouter) | sonar-deep-research | Company name, domain | 300s |
| 2 | `customer_reviews` | Perplexity (OpenRouter) | sonar-deep-research | Company name, domain | 300s |
| 3 | `competitor_registry` | Perplexity (OpenRouter) | sonar-deep-research | Company + overview_md | 300s |
| 4 | `weakness_analysis` | Perplexity (OpenRouter) | sonar-deep-research | Company + overview + competitors | 300s |
| 5 | `brand_perception` | Anthropic SDK | claude-sonnet-4-6 | Company + all 4 upstream docs | 300s |
| 6 | `synthesis` | LangGraph (OpenRouter) | claude-opus-4-6 | 3-5 L2 docs via read_file tool | 600s |

**Agent 5 (Brand Perception)** is unique — uses Anthropic's native `web_search_20250305` tool for real-time search. Handles `pause_turn` loops (up to 5 iterations).

**Agent 6 (Synthesis)** uses `create_react_agent` with a `read_file` tool backed by `StorageBackend`. Requires minimum 3 of 5 L2 docs. Supports delta synthesis for refresh mode.

## HITL Checkpoints

### HITL-1: Phase 1+2 Doc Review (after Agents 1-3)
- Reviews: company_overview, customer_reviews, competitor_registry
- Decisions: approve / revise (with per-doc notes) / reject
- Revision: re-runs flagged agents with revision notes in prompt

### HITL-2: Phase 3 Doc Review (after Agents 4-5)
- Reviews: weakness_analysis, brand_perception
- Same decision model as HITL-1

### HITL-3: Synthesis Review (after Agent 6)
- Reviews: synthesis document (first 2000 chars preview)
- Decisions: approve / revise (single note) / reject
- Approved synthesis promoted to `company_context/{slug}.md`

All checkpoints use LangGraph `interrupt()` + `Command(resume=...)` pattern. Auto-approve available via `auto_approve_checkpoints: [1, 2, 3]`.

## Execution Modes

| Mode | Trigger | Agents | HITL | Synthesis |
|------|---------|--------|------|-----------|
| **full** | No refresh_docs | All 6 | All 3 | Full synthesis |
| **refresh** | 2+ refresh_docs | Specified only | For changed docs | Delta synthesis |
| **single** | 1 refresh_doc | One agent only | None | None |
| **express** | express_mode=True | All 6 (concurrent) | Merged HITL | Fast synthesis |

**Delta synthesis** (refresh mode): Reads previous synthesis + only changed docs. Prompt instructs Claude to refine rather than rewrite.

## Storage Pattern

```
artifacts/knowledge_base/{slug}/
├── _manifest.json          ← KBManifest (versions, staleness, dependencies)
├── company_overview/v1.md
├── customer_reviews/v1.md
├── competitor_registry/v1.md, v1.json  ← JSON sidecar (structured competitors)
├── weakness_analysis/v1.md
├── brand_perception/v1.md
└── synthesis/v1.md, v2.md, ...

Promoted to:
  company_context/{slug}.md  ← consumed by all downstream pipelines
```

**KBStorage** handles versioning, manifest updates, staleness tracking, and promotion.

## Staleness System

| Doc Type | Staleness Threshold |
|----------|-------------------|
| company_overview | 90 days |
| customer_reviews | 30 days |
| competitor_registry | 90 days |
| weakness_analysis | 60 days |
| brand_perception | 45 days |

**Dependency graph** for staleness propagation:
- `competitor_registry` depends on `company_overview`
- `weakness_analysis` depends on `company_overview` + `competitor_registry`
- `brand_perception` depends on `company_overview` + `customer_reviews` + `competitor_registry`

When an upstream doc is refreshed, all downstream docs are marked stale.

## Competitor Extraction (Pass 2)

After Agent 3 produces markdown, a Claude Haiku call extracts structured JSON (`CompetitorRegistryStructured`) with categories: direct, mindshare, niche, emerging competitors + feature comparison + market map. This JSON sidecar is used by the Daily Tracker for competitor mention detection.

## Configuration

| Setting | Default |
|---------|---------|
| `research_kb_company_overview_model` | `"sonar-deep-research"` |
| `research_kb_customer_reviews_model` | `"sonar-deep-research"` |
| `research_kb_competitor_scanner_model` | `"sonar-deep-research"` |
| `research_kb_competitor_extractor_model` | `"anthropic/claude-haiku-4-5"` |
| `research_kb_weakness_analyst_model` | `"sonar-deep-research"` |
| `research_kb_brand_perception_model` | `"claude-sonnet-4-6"` |
| `research_kb_synthesis_model` | `"anthropic/claude-opus-4-6"` |

## Entry Point

```python
async def run_knowledge_base_pipeline(
    input_data: KnowledgeBaseInput,
    *,
    task_id=None, task_store=None, event_bus=None,
    artifacts_root=None, session_factory=None,
    run_id=None, company_id=None, langsmith_project=None,
) -> KnowledgeBaseOutput
```
