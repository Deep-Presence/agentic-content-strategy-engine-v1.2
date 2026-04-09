# Pipeline 1c: Voice Style Guide

> **Location:** `core/research/voice_style_guide/`
> **Owner:** Core
> **Dependencies:** LiteLLM (Gemini, Claude), Perplexity, LangGraph, KB + AP pipeline outputs
> **Dependents:** Pipeline 3 (Content Engine — style judge uses voice guide)
> **Last Updated:** 2026-04-09

## Overview

Pipeline 1c is a 3-agent pipeline that discovers influential authors, researches their writing styles, and synthesizes a unified voice style guide for content generation. It uses Gemini Flash with web search for author discovery, Perplexity deep research for author analysis, and Claude Sonnet for voice synthesis. One HITL checkpoint allows human review of discovered authors. The final guide is promoted to `style_guides/{slug}.md` for use by the Content Engine's style judge.

## Architecture

```
Phase 0: Preflight
  └── Load company_context + persona profiles (from AP pipeline)

Phase 1: Author Discovery (Gemini Flash + web search)
  └── Returns 2-3 AuthorBrief objects

HITL-1: Author Review
  └── Approve / Modify / Reject per author (fail-closed)

Phase 2: Parallel Author Research (Perplexity sonar-deep-research)
  └── One researcher per approved author (semaphore-limited, 900s timeout)

Phase 3: Voice Synthesis (Claude Sonnet)
  └── Synthesizes unified voice guide from all research

Phase 4: Finalize
  └── Write guide, promote to style_guides/, DB persistence
```

## File Structure

| File | Lines | Purpose |
|------|-------|---------|
| `pipeline.py` | 520 | Main orchestrator |
| `graph.py` | 297 | LangGraph HITL graph (1 checkpoint) |
| `agents.py` | 700 | Discovery + Research + Synthesis agents |
| `storage.py` | 326 | Versioned storage (VoiceStyleGuideStorage) |
| `persistence.py` | 230 | DB persistence hooks |

## Agents

### Agent 1: Author Discovery
- **Provider:** LiteLLM (Gemini Flash via OpenRouter)
- **Model:** `settings.voice_style_guide_discovery_model`
- **Input:** Company context + persona summaries (capped at 30k chars)
- **Output:** 2-3 `AuthorBrief` objects with `work_persona_mapping`
- **Web search:** Up to 5 uses for real-time author verification
- **Pause turn handling:** Anthropic pause_turn loop (up to 3 iterations)
- **Deduplication:** By author name (case-insensitive, first-wins)
- **Retry:** If <2 valid authors, retry once

### Agent 2: Author Research
- **Provider:** Perplexity sonar-deep-research
- **Timeout:** 900s (15 minutes per author)
- **Input:** AuthorBrief + company context + persona summaries
- **Output:** `AuthorResearchResult` with detailed writing style analysis markdown
- **Concurrency:** Limited by `voice_style_guide_max_concurrent_researchers`

### Agent 3: Voice Synthesis
- **Provider:** LiteLLM (Claude Sonnet via OpenRouter)
- **Model:** `settings.voice_style_guide_synthesis_model`
- **Temperature:** 0.3 (low, deterministic)
- **Max tokens:** 8192
- **Input:** All author research + company context + personas
- **Output:** Final voice style guide markdown

## HITL Checkpoint

### HITL-1: Author Approval
- **Decisions:** approve_all / partial (per-author) / reject_all
- **Per-author:** APPROVE, MODIFY (source="hybrid"), REJECT
- **Fail-closed:** Unreviewed authors rejected
- **No manual additions** (unlike AP HITL-1)

## Storage Pattern

```
artifacts/voice_style_guide/{slug}/
├── _manifest.json              ← VoiceStyleGuideManifest
├── discovery/v1.json           ← Author discovery result
├── {author_id}/
│   ├── brief.json              ← AuthorBrief
│   └── v1.md                   ← Research markdown
└── guide/v1.md                 ← Synthesized guide

Promoted to:
  style_guides/{slug}.md        ← consumed by Content Engine style judge
```

## Upstream Dependencies

| Dependency | Required | Purpose |
|-----------|----------|---------|
| `company_context/{slug}.md` | Yes | Company knowledge context |
| `audience_personas/{slug}/` | Yes | Persona profiles for author matching |

## Configuration

| Setting | Default |
|---------|---------|
| `voice_style_guide_discovery_model` | `"anthropic/claude-sonnet-4-6"` |
| `voice_style_guide_synthesis_model` | `"anthropic/claude-sonnet-4-6"` |
| `voice_style_guide_max_concurrent_researchers` | `3` |

## Comparison with Pipeline 1b (Audience Persona)

| Aspect | Audience Persona | Voice Style Guide |
|--------|-----------------|-------------------|
| Agents | 2 (Suggest + Generate) | 3 (Discover + Research + Synthesize) |
| HITL | 2 checkpoints | 1 checkpoint |
| Upstream | KB pipeline | KB + AP pipelines |
| Research timeout | 300s | 900s |
| Output promotion | Vector embeddings | `style_guides/{slug}.md` |
