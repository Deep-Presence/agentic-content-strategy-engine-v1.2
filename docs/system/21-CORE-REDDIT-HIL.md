# Reddit HIL Monitor

> **Location:** `core/reddit_hil/`
> **Owner:** Core
> **Dependencies:** PRAW, LangGraph, Gemini (via OpenRouter), Slack/Discord webhooks
> **Dependents:** `scripts/run_reddit_monitor.py`
> **Last Updated:** 2026-04-09

## Overview

The Reddit HIL (Human-in-the-Loop) monitor watches configured subreddits for relevant discussion threads, drafts contextual replies using Gemini, and sends them to Slack/Discord for human review before posting. It uses a LangGraph pipeline with 7 sequential nodes and a JSON-based dedup cache.

## Architecture

```
_load_artifacts ── Load company context, persona, style guide
    │
_fetch_candidates ── PRAW: fetch newest N threads from subreddits
    │
_dedupe_cache ── Filter against previously notified thread IDs
    │
_rank_filter ── Keyword extraction + heuristic scoring → top-K
    │
_draft_reply ── Gemini LLM: select + draft reply markdown
    │
_notify ── Slack/Discord webhook notifications
    │
Update seen cache
```

## Key Components

### Keyword Extraction
Extracts terms from persona markdown (Pain Points, Buying Triggers, Messaging Angles sections). Top 80 terms by frequency, 4+ chars, excluding 120 stopwords.

### Heuristic Scoring
Counts keyword matches in thread text (max 4000 chars). Normalizes by soft cap (hits/12, capped at 1.0). Sorts by (heuristic_score, reddit_score, num_comments).

### LLM Reply Drafting
Single Gemini call with structured JSON output. Returns: thread selection, fit_score, why_match rationale, draft_markdown.

### Webhook Notifications
- **Slack:** Block-based layout, 2500 char limit per block
- **Discord:** Multi-message format, 2000 char limit per message

### Dedup Cache
JSON file at `artifacts/_logs/reddit_monitor/{slug}__seen.json`. Thread IDs persisted after notification.

## Configuration

| Setting | Default |
|---------|---------|
| `google_gemini_model_reddit_hil` | `google/gemini-3-flash-preview` |
| `slack_webhook_url` | `""` |
| `discord_webhook_url` | `""` |

**Note:** Zero test coverage — no `tests/reddit_hil/` directory exists.
