# Pipeline 4: Topic Discovery

> **Location:** `core/topic_discovery/`
> **Owner:** Core
> **Dependencies:** OpenRouter (Claude, Perplexity), pgvector, LangGraph
> **Dependents:** Pipeline 3 (Content Engine), Content Studio (frontend Planner page)
> **Last Updated:** 2026-04-09

## Overview

Pipeline 4 is a multi-source topic discovery and scoring system consisting of two sub-pipelines. **Pipeline A (Discovery)** generates subdomains from 4 independent perspectives, deduplicates via embedding similarity, builds a taxonomy hierarchy, and scores each node on 4 dimensions with persona affinity. **Pipeline B (Expansion)** takes approved subdomains and expands them into concrete topic assignments across buyer stages, intent types, and personas, with cannibalization detection against existing content. Total: ~9,664 lines of code.

## Architecture

```
PIPELINE A: DISCOVERY
─────────────────────
Phase 0: Preflight (load company context, personas)
    │
Phase 1 (S1): Multi-Source Generation
    ├── Source A: Company Brainstorm (iterative, 1-4 rounds)
    ├── Source B: Persona Brainstorm (iterative, persona-driven)
    ├── Source C: Competitive Landscape (Perplexity deep research)
    └── Source D: Adversarial Diversity (5 specialist lenses)
    │
    Deduplication (embedding similarity, threshold 0.85)
    │
Phase 2 (S2): Unified Scoring
    │   Single LLM call: hierarchy + 4-dim scoring + persona affinity
    │
HITL-1: Taxonomy Review (approve / modify tree / retry)
    │
Phase 2.5: Source Confidence Blending
    │
Output: Scored Taxonomy + PersonaAffinityIndex

PIPELINE B: EXPANSION
─────────────────────
Phase 3 (S3): Subdomain Expansion
    │   Per-subdomain: relevance pruning + topic generation (2-5 per cell)
    │   Cannibalization detection via pgvector
    │
HITL-2: Matrix Review (approve / modify assignments)
    │
Output: TopicAssignmentMatrix → Content Engine
```

## File Structure

| File | Lines | Purpose |
|------|-------|---------|
| `pipeline.py` | 1,455 | Main orchestrator (Pipeline A + B) |
| `agents.py` | 1,941 | All agent functions (S1-S3) |
| `db_ops.py` | 1,295 | Async Postgres I/O |
| `graph.py` | 719 | LangGraph HITL (2 checkpoints) |
| `scoring.py` | 626 | Priority scoring + persona affinity |
| `persistence.py` | 624 | DB hooks for pipeline artifacts |
| `storage.py` | 393 | JSON/filesystem helpers |
| `display_id.py` | 135 | Human-readable ID generation |
| `prompts/` (10 files) | 2,454 | All prompt templates |

## Multi-Source Generation (S1)

### 4 Sources

| Source | Perspective | Method | Model | Rounds |
|--------|------------|--------|-------|--------|
| **A** | Company brainstorm | Iterative expansion | Claude Sonnet | 1-4 |
| **B** | Persona needs | Iterative, persona-driven | Claude Sonnet | 1-4 |
| **C** | Competitive landscape | Single deep research call | Perplexity sonar-deep-research | 1 |
| **D** | Adversarial diversity | 5 specialist lenses | Claude Sonnet | 1 per lens |

**Source D specialist lenses:** Regulatory compliance, Enterprise procurement, Accessibility advocacy, Customer success, Security & risk analysis.

### Coverage Metrics (Capture-Recapture)

Per-source: **Chao1 estimator** (`S_obs + f1^2/2f2`) for unseen species richness, **Good-Turing sample coverage** (`1 - f1/N`).

Between-source: **Lincoln-Petersen** pairwise estimates.

Target: 95% aggregate sample coverage.

### Deduplication

Embedding-based clustering (cosine similarity >= 0.85). Merges persona_ids + pain_points from absorbed duplicates into canonical candidates.

## Scoring System (S2 — Unified)

Single LLM call (Claude Sonnet) computes hierarchy + 4-dimension scoring + persona affinity simultaneously.

### 4 Priority Dimensions

| Dimension | Weight | What It Measures |
|-----------|--------|-----------------|
| Strategic Centrality | 0.35 | Value of being cited (core vs peripheral) |
| Citation Opportunity | 0.25 | Probability of getting cited (whitespace vs saturated) |
| Content Authority | 0.20 | Feasibility of production (proprietary data, expertise) |
| Conversion Potential | 0.20 | Value density per citation (buyer proximity) |

**Composite:** `0.35*centrality + 0.25*opportunity + 0.20*authority + 0.20*conversion`

### Source Confidence Blending (Phase 2.5)

After HITL-1, blends LLM composite with cross-source signal:
- `blended_score = 0.75 * llm_composite + 0.25 * source_confidence`
- Source confidence: 0.25 (1 source) to 1.0 (all 4 sources)

### Persona Affinity

Per-node, per-persona score (0.0-1.0). During expansion (Phase 3), algorithmic adjustments:
- Direct persona match: +0.2
- Role-based buyer stage boost (executives +0.1 for BOFU, practitioners +0.1 for TOFU)

## HITL Checkpoints

### HITL-1: Taxonomy Review
User can: approve, modify (add/delete/rename/reparent nodes), retry (max 2). Edits applied to tree, recomputes depths and sort order.

### HITL-2: Matrix Review
User can: approve, modify (adjust priority, remove, add assignments).

## Expansion (S3)

Per-subdomain, single LLM call generates 2-5 topic assignments per relevant `buyer_stage x intent_type x persona` cell. Self-pruning: LLM skips irrelevant combinations.

### Cannibalization Detection

Each assignment compared against content inventory via pgvector similarity:
- 0.80-0.90 similarity: moderate penalty (0-20% reduction)
- 0.90+ similarity: strong penalty (20-35% reduction)
- Results enriched on assignment metadata

## Display ID System

Company-scoped human-readable IDs (e.g., "WE-042"):
- Prefix: company initials or first 2 letters
- Counter: `SELECT FOR UPDATE` serialized allocation
- Backfilled after every bulk write

## DB Persistence (db_ops.py)

All async Postgres I/O: manifest, taxonomy trees, subdomain nodes, source results, scored lists, persona affinity, topic assignments. Idempotent operations with delete + re-insert patterns.

## Configuration

| Setting | Default |
|---------|---------|
| `topic_discovery_brainstorm_model` | `anthropic/claude-sonnet-4-6` |
| `topic_discovery_dedup_model` | `anthropic/claude-haiku-4-5` |
| `topic_discovery_source_c_model` | `perplexity/sonar-deep-research` |
| `topic_discovery_unified_s2_model` | `anthropic/claude-sonnet-4-6` |
| `topic_discovery_dedup_threshold` | 0.85 |
| `topic_discovery_max_expansion_rounds` | 4 |
| `topic_discovery_max_concurrent_sources` | 4 |
| `td_cannibalization_threshold` | 0.80 |

## Integration with Content Engine

Topic assignments flow to Content Engine via orchestration:
- TD HITL-2 approved assignments → topic_assignment_ids in ContentGenerationInputV13
- Display IDs persist throughout lifecycle: TD → Planner → GA → CE → Content Studio → Published
