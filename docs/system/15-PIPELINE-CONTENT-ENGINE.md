# Pipeline 3: Content Engine v1.3

> **Location:** `core/content_engine/`
> **Owner:** Core
> **Dependencies:** LiteLLM (via OpenRouter), LangGraph, pgvector
> **Dependents:** `api/routers/content_v13.py`, Content Studio (frontend), CMS publish
> **Last Updated:** 2026-04-09

## Overview

Pipeline 3 v1.3 is a 6-stage async content generation pipeline that produces AI-citation-optimized articles. It features a Strategic Planner for topic triage, Brief Builder for content architecture, a 4-worker chain (Outliner -> Drafter -> Linker -> Formatter), a 5-dimension evaluator loop with revision cycles, and 3 HITL checkpoints. All LLM calls route through OpenRouter. The pipeline produces ~10,000 lines of production code.

## Architecture

```
AUTONOMOUS MODE:                          MANUAL MODE:
Entry Router                              Entry Router
    │                                         │
Stage 1: Strategic Planner                    │ (skip)
    │    (Agent 1: topic triage)              │
    ▼                                         │
HITL-1: Topic Approval                        │
    │                                         │
Stage 2: Brief Builder                   Stage 2: Brief Builder
    │    (Agent 2: content architecture)      │
    ▼                                         ▼
HITL-2: Brief Approval (per-brief)       HITL-2: Brief Approval
    │                                         │
Stage 3: Workers (4-step chain)          Stage 3: Workers
    │    Outliner → Drafter →                 │
    │    Linker → Formatter                   │
    ▼                                         ▼
Stage 4: Evaluator Loop                  Stage 4: Evaluator Loop
    │    5 dimensions, max 2 cycles           │
    ▼                                         ▼
HITL-3: Content Review (per-piece)       HITL-3: Content Review
    │                                         │
Publish                                  Publish
```

## File Structure

| Directory | File | Lines | Purpose |
|-----------|------|-------|---------|
| root | `pipeline_v13.py` | 2,753 | Main 6-stage orchestrator |
| root | `strategic_planner.py` | 136 | Agent 1: topic triage |
| root | `brief_builder.py` | 271 | Agent 2: content architecture |
| root | `context_router.py` | 498 | 2-phase context extraction |
| root | `graph_v13.py` | 532 | 3 LangGraph HITL state machines |
| root | `llm_client.py` | 199 | Unified OpenRouter LLM interface |
| root | `state_redis.py` | 592 | Redis-backed pipeline state |
| workers | `dispatcher.py` | 540 | Parallel worker orchestration |
| workers | `outliner.py` | 130 | Worker 1: structure design |
| workers | `drafter.py` | 272 | Worker 2: content generation |
| workers | `linker.py` | 197 | Worker 3: link + stat resolution |
| workers | `formatter.py` | 156 | Worker 4: style polish |
| evaluator | `loop.py` | 564 | Evaluator orchestration + revision |
| evaluator | `structural.py` | 482 | Structural quality checks (no LLM) |
| evaluator | `semantic.py` | 145 | Semantic alignment evaluation |
| evaluator | `style_judge.py` | 144 | Style guide compliance |
| evaluator | `factual_judge.py` | 147 | Factual accuracy verification |
| evaluator | `eeat_judge.py` | 162 | E-E-A-T dimension (v1.3 new) |
| prompts | 11 files | 1,853 | System + user prompts |

## Stages

### Stage 0: Entry Router
Routes based on `entry_mode`: AUTONOMOUS (from gap analysis) or MANUAL (user prompt).

### Stage 1: Strategic Planner (Agent 1)
**Model:** Claude Sonnet 4.6. Receives lightweight scorecard (~11K tokens) from context_router Phase 1. Selects top-K topics (default 6) based on gap magnitude, exemplar richness, and cluster diversity.

### Stage 2: Brief Builder (Agent 2)
**Model:** Claude Sonnet 4.6. Receives full WorkerQueryContext per approved topic from context_router Phase 2. Produces `ContentBlueprint` with sections, 22 structural targets, gap reasoning, tone/voice guidance.

### Stage 3: Content Workers (4-step chain)
Per-brief, runs in series. Multiple briefs run in parallel (semaphore-limited).

| Worker | Model | Input | Output |
|--------|-------|-------|--------|
| Outliner | Claude Sonnet | Blueprint | Section-by-section outline with word counts |
| Drafter | Claude Sonnet | Outline + brief + style guide | Markdown with placeholders |
| Linker | Perplexity sonar-pro | Draft + site pages | Resolved links + stats |
| Formatter | Claude Haiku | Enriched draft + style guide | Polished markdown |

### Stage 4: Evaluator Loop
5 independent evaluation dimensions run in parallel:

| Dimension | Model | Pass Threshold | What It Checks |
|-----------|-------|---------------|----------------|
| Structural | None (sync) | Configurable | Word count, headers, lists, stats, FAQ, tables |
| Semantic | Claude Sonnet | 0.5 | Query intent alignment |
| Style | Claude Haiku | 0.7 | Style guide compliance |
| Factual | Claude Sonnet | 0.7 | Claim accuracy, flagged claims |
| E-E-A-T | Claude Sonnet | 0.6 | Experience, Expertise, Authority, Trust |

**Revision routing:** `PASS` (all passed), `SECTION_LEVEL` (targeted fixes via drafter + fact checker), `MAJOR_CHANGE` (semantic < 0.5, escalate to human).

Max revision cycles: configurable per content format (default 2).

### Stage 5: Final Review (HITL-3)
Human reviews content with evaluation summary. Options: approve, edit (with notes), reject.

## 3 HITL Checkpoints

All use LangGraph `interrupt()` + `Command(resume=...)` pattern with Redis checkpointing.

| Checkpoint | After | Decisions | On Reject |
|-----------|-------|-----------|-----------|
| HITL-1 | Strategic Planner | approve / modify ranks / retry / reject | Abort pipeline |
| HITL-2 | Brief Builder (per-brief) | approve / feedback / reject | Skip brief |
| HITL-3 | Evaluator (per-piece) | approve / edit / reject | Mark as rejected |

## State Management

**Redis Hash:** `pipeline_state:{effective_slug}`
- Per-brief status tracking (e.g., `"brief-001" → "drafting"`)
- Task ID mapping (`__tid:brief-001 → task-uuid`)
- GA-phase cards for topic assignments in gap analysis

**File-based:** `pipeline_state.json` (dual-write with Redis)

## Context Router (Two-Phase)

**Phase 1 (Scorecard):** Lightweight ~11K token summary for topic triage. 200 queries with gap scores.

**Phase 2 (Full Context):** Complete exemplar data for only approved topics (4-6 out of 200). Natural HITL boundary between phases.

## LLM Client

Unified `llm_call()` function routing all calls through OpenRouter with jittered exponential backoff retry, cost tracking, and model prefix validation.

## Configuration

| Setting | Default |
|---------|---------|
| `content_engine_v13_planner_model` | `anthropic/claude-sonnet-4-6` |
| `content_engine_v13_worker_model` | `anthropic/claude-sonnet-4-6` |
| `content_engine_v13_formatter_model` | `anthropic/claude-haiku-4-5` |
| `content_engine_v13_fact_enricher_model` | `perplexity/sonar-pro` |
| `content_engine_v13_linker_model` | `perplexity/sonar-pro` |
| `content_engine_v13_eeat_judge_model` | `anthropic/claude-sonnet-4-6` |
| `content_engine_v13_max_topics` | 6 |
| `content_engine_v13_max_concurrent_workers` | 3 |
