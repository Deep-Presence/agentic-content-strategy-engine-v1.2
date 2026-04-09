# Core Orchestration

> **Location:** `core/orchestration/`
> **Owner:** Core
> **Dependencies:** Pipelines 2, 3, 4, Redis, DB
> **Dependents:** `api/routers/content_v13.py`, `api/routers/topic_discovery.py`
> **Last Updated:** 2026-04-09

## Overview

The orchestration module provides the TD -> Content Engine pipeline, chaining Topic Discovery assignments through topic-scoped Gap Analysis into Content Generation. It supports three entry patterns: combined (atomic), GA-only (Phase 1), and CE-only (Phase 2), enabling concurrent admin review without blocking content production.

## Architecture

```
TopicAssignment IDs (from HITL-2 approval)
    │
    ▼ Preflight (validate context, personas, matrix)
    │
Phase 1: Topic-Scoped Gap Analysis
    │   → Reuses S1 embeddings from base GA run
    │   → topic-specific queries via S2
    │   → S3-S8 with scoped queries
    │
    ▼ Write GA-phase cards to Redis (ta-* keys)
    │   → Content Studio shows real-time progress
    │
Phase 2: Content Engine (TOPIC_DISCOVERY mode)
    │   → Uses pre-computed analysis.json
    │   → Per-query content pieces tagged by topic_assignment_id
    │
    ▼ Cleanup GA-phase cards, update DB statuses
```

## Three Entry Patterns

| Pattern | Function | Use Case |
|---------|----------|----------|
| Combined | `run_td_to_content_pipeline()` | GA + CE as one atomic task |
| GA-only | `run_td_gap_analysis_only()` | Phase 1 only, user reviews before Phase 2 |
| CE-only | `run_td_content_production_only()` | Phase 2 from pre-computed GA |

## Status Machine

```
not_started → approved → in_gap_analysis → gap_analysis_complete → in_content_production → content_produced
```

## Redis GA-Phase Cards

During gap analysis, Redis stores `ta-{uuid}` keys in `pipeline_state:{slug}` hash. These appear as cards in Content Studio's kanban board, showing real-time GA progress. On graduation to CE, ta-* keys are cleaned up and briefs take over.

## Failure Recovery

CE failure reverts both ta-* Redis keys and DB status to `gap_analysis_complete`, allowing retry.
