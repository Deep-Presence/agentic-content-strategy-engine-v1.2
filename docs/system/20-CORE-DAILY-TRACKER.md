# Daily Tracker — Platform Monitoring

> **Location:** `core/daily_tracker/`
> **Owner:** Core
> **Dependencies:** Gap Analysis engines (OpenAI, Claude, Gemini, Perplexity), DB
> **Dependents:** `api/routers/daily_tracker.py`, frontend Analytics page
> **Last Updated:** 2026-04-09

## Overview

The Daily Tracker monitors a company's AI visibility by running tracked prompts across 4 AI platforms (OpenAI, Claude, Gemini, Perplexity), detecting brand/competitor mentions in responses, extracting citation URLs, and computing visibility metrics. It uses a Mediator pattern where the orchestrator coordinates platform runner, mention detector, and analytics engine without direct coupling.

## Architecture

```
DailyTrackerOrchestrator (Mediator)
    │
    ├── PlatformRunnerService
    │   └── 4 SearchEngine adapters (from gap_analysis/engines/)
    │
    ├── MentionDetector
    │   └── Regex-based brand/competitor/URL detection
    │
    └── AnalyticsService
        └── 4 MetricCalculator strategies
            ├── MentionRate (fraction of responses with brand mention)
            ├── CitationRate (fraction with citations + avg rank)
            ├── ShareOfVoice (brand vs competitor mentions)
            └── Trend (mention rate over time)
```

## Key Functions

### Orchestrator

```python
async def execute_daily_run(
    company_id, prompt_ids=None, engines=None, brand=None,
    competitors=None, concurrency=6, run_id=None
) -> DailyRunResult
```

### Platform Runner
Adapts `core/gap_analysis/engines/` (OpenAI, Claude, Gemini, Perplexity) for prompt execution. Asyncio semaphore for concurrency. Per-engine errors never crash the run.

### Mention Detector (deterministic, no LLM)
- **Brand mentions:** Case-insensitive word-boundary regex, returns count
- **Competitor mentions:** Per-competitor count dict
- **Citation extraction:** URL regex, returns list
- **Citation rank:** 1-indexed position of first brand-domain URL

### Analytics Metrics

| Metric | Formula | Output |
|--------|---------|--------|
| Mention Rate | responses_with_mention / total_responses | Overall + per-engine breakdown |
| Citation Rate | responses_with_citations / total | Rate + avg rank + top URLs |
| Share of Voice | brand_mentions / (brand + competitor mentions) | Per-entity percentages |
| Trend | Daily aggregation of mention rate | 30-day data points |

## Integration with Fanout Generation

Prompts support fanout expansion: a parent prompt generates child variants via LLM (Claude Sonnet). Fanout queries tracked via `parent_prompt_id` self-referencing FK. Analytics aggregation maps fanout responses back to parent prompts.

## Configuration

| Setting | Default |
|---------|---------|
| `daily_tracker_fanout_model` | `anthropic/claude-sonnet-4-6` |
| `daily_tracker_fanout_target_count` | 15 |
| `daily_tracker_fanout_temperature` | 0.3 |
| `daily_tracker_response_retention_days` | 30 |
