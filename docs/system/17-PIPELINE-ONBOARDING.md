# Pipeline 5: Onboarding

> **Location:** `core/onboarding/`
> **Owner:** Core
> **Dependencies:** Pipelines 0, 1a, 1b, 1c, 2, 4
> **Dependents:** `api/routers/onboarding.py`
> **Last Updated:** 2026-04-09

## Overview

Pipeline 5 is a meta-orchestrator that chains six sub-pipelines in three sequential phases to set up a new company. Phase A runs Site Audit + Knowledge Base in parallel. Phase B runs Audience Persona (depends on KB). Phase C runs Voice Style Guide + Gap Analysis + Topic Discovery in parallel (depends on AP). All HITL checkpoints in sub-pipelines are auto-approved.

## Architecture

```
Phase A (Parallel):
  ├── Site Audit (fire-and-forget async task)
  └── Knowledge Base (blocking, awaited)

Phase B (Sequential, depends on KB):
  └── Audience Persona (seeded with KB context)

Phase C (Parallel, depends on AP):
  ├── Voice Style Guide
  ├── Gap Analysis
  └── Topic Discovery
```

## Key Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `run_onboarding_pipeline` | `(input: OnboardingInput, ...) -> OnboardingOutput` | Main entry. Orchestrates all 6 sub-pipelines |
| `_SubPipelineEventProxy` | class | Intercepts terminal SSE events from sub-pipelines |
| `_build_*_input` | 6 functions | Construct input for each sub-pipeline |
| `_run_*_stage` | 6 functions | Execute each sub-pipeline with error handling |

## Output

`OnboardingOutput` with `status` (completed/completed_partial/failed), per-phase results, aggregate execution time.

Each sub-pipeline creates a child `pipeline_run` record in DB for traceability.
