# Pipeline 1b: Audience Persona

> **Location:** `core/research/audience_persona/`
> **Owner:** Core
> **Dependencies:** OpenRouter (Gemini), Perplexity, LangGraph, KB pipeline output
> **Dependents:** Pipeline 1c (VSG), Pipeline 4 (Topic Discovery), Pipeline 3 (Content Engine)
> **Last Updated:** 2026-04-09

## Overview

Pipeline 1b is a 2-agent pipeline that discovers and generates detailed audience persona profiles. The Persona Suggester (Gemini Flash) proposes 3-5 personas based on company context, and the Profile Generator (Perplexity deep research) creates deep persona profiles for approved personas. Two HITL checkpoints allow human review of both briefs and generated profiles. Persona embeddings are computed post-generation for use in Topic Discovery affinity scoring.

## Architecture

```
Phase 0: Preflight
  └── Load company_context/{slug}.md + customer reviews + knowledge docs

Phase 1: Persona Suggester (Gemini Flash)
  └── Returns 3-5 PersonaBrief objects

HITL-1: Brief Review
  └── Approve / Modify / Reject per brief + manual additions

Phase 2: Parallel Profile Generators (Perplexity sonar-deep-research)
  └── One generator per approved brief (semaphore-limited)

HITL-2: Profile Review
  └── Approve / Revise / Reject per profile

Phase 3: Finalize
  └── Update manifest, compute embeddings, DB persistence
```

## File Structure

| File | Lines | Purpose |
|------|-------|---------|
| `pipeline.py` | 596 | Main orchestrator |
| `graph.py` | 481 | Two LangGraph HITL graphs |
| `agents.py` | 406 | Suggester + Generator agents |
| `storage.py` | 323 | Versioned storage (PersonaStorage) |
| `persistence.py` | 188 | DB persistence hooks |

## Agents

### Agent 1: Persona Suggester
- **Provider:** OpenRouter (Gemini Flash)
- **Model:** `settings.audience_persona_suggester_model`
- **Input:** Company context + customer reviews + knowledge docs
- **Output:** 3-5 `PersonaBrief` objects (JSON response format)
- **Retry:** If <3 valid briefs, retry once with repair prompt
- **Parsing:** Tolerant JSON extraction (finds first `[` to last `]`)

### Agent 2: Persona Profile Generator
- **Provider:** Perplexity sonar-deep-research
- **Model:** `settings.audience_persona_generator_model`
- **Input:** PersonaBrief + company context + customer reviews + knowledge docs
- **Output:** `PersonaAgentResult` with markdown profile
- **Timeout:** 300s (deep research)
- **Revision support:** `revision_note` appended to prompt for HITL-2 revisions

## HITL Checkpoints

### HITL-1: Brief Review
- **Decisions:** approve_all / partial (per-brief) / reject_all
- **Per-brief:** APPROVE, MODIFY (must keep persona_name), REJECT
- **Manual additions:** User can add briefs with source="manual"
- **Fail-closed:** Unreviewed briefs are rejected

### HITL-2: Profile Review
- **Decisions:** Per-profile APPROVE, REVISE (with feedback note), REJECT
- **Revision:** Re-runs generator with human feedback in prompt
- **Fail-open:** Unreviewed profiles auto-approved (already generated)

## Storage Pattern

```
artifacts/audience_personas/{slug}/
├── _manifest.json              ← PersonaManifest
└── {persona_id}/
    ├── brief.json              ← Original PersonaBrief
    ├── v1.md                   ← Generated profile
    ├── v1.json                 ← Optional structured output
    └── v2.md                   ← Revision (if HITL-2 revise)
```

**PersonaManifest** tracks: personas (Dict[id, PersonaProfileEntry]), last_full_run, kb_synthesis_version.

## Post-Generation

- **Embedding computation:** Background task computes pgvector embeddings for all persona profiles
- **Embeddings used by:** Topic Discovery (persona affinity scoring)

## Configuration

| Setting | Default |
|---------|---------|
| `audience_persona_suggester_model` | `"google/gemini-3-flash-preview"` |
| `audience_persona_generator_model` | `"sonar-deep-research"` |
| `audience_persona_max_concurrent_generators` | `3` |
