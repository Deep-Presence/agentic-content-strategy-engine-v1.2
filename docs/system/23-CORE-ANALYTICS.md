# Core Analytics — GA4 Integration

> **Location:** `core/analytics/`
> **Owner:** Core
> **Dependencies:** Google Analytics Data API, Google OAuth2, Fernet encryption
> **Dependents:** `api/routers/analytics.py`, `core/services/analytics_cache.py`, frontend Settings
> **Last Updated:** 2026-04-09

## Overview

The analytics module provides full Google Analytics 4 (GA4) integration: OAuth2 authorization flow, token management with Fernet encryption, property selection, traffic/conversion data sync, and AI referral classification. The service classifies traffic from AI platforms (ChatGPT, Claude, Perplexity, Gemini, Copilot) as AI referrals for visibility tracking.

## Architecture

```
OAuth Flow:
  Frontend Settings → authorize URL → Google Consent → callback → exchange code → encrypt tokens → store

Data Sync:
  Cron/Manual trigger → ensure fresh token → parallel reports → bulk upsert → AI referral classification

Token Management:
  Fernet encryption at rest → 5-min refresh buffer → auto-refresh → auth_revoked fallback
```

## File Structure

| File | Purpose |
|------|---------|
| `service.py` | `GA4AnalyticsService` — orchestrator |
| `adapters/ga4.py` | `GA4Adapter` — Google API implementation |
| `models.py` | Domain models (GA4Property, GA4TokenSet, TrafficRow, SyncResult) |
| `protocols.py` | `AnalyticsAdapterProtocol` |
| `factory.py` | Adapter factory |
| `exceptions.py` | GA4Error → AuthError, QuotaError, APIError |

## OAuth Flow

1. **Generate URL:** HMAC-SHA256 signed state token with company_slug, return_url, 10-min expiry
2. **Callback:** Verify state signature + expiry, exchange code for tokens
3. **Store:** Fernet-encrypt access_token + refresh_token, persist to `analytics_connections` table
4. **Refresh:** Auto-refresh when token_expiry <= now + 5min; on failure, mark `auth_revoked`

## Data Sync

**Parallel reports** (traffic + conversions) via `asyncio.gather` with partial-failure tolerance.

**Traffic dimensions:** date, landingPage, sessionSource, sessionMedium, sessionCampaignName
**Traffic metrics:** sessions, engagedSessions, engagementRate, bounceRate, avgSessionDuration, screenPageViews, conversions, newUsers, totalUsers

**AI Referral Classification:**
Maps source domains to AI platforms:
- chatgpt.com → openai
- claude.ai → anthropic
- perplexity.ai → perplexity
- gemini.google.com → google
- copilot.microsoft.com → microsoft

Bulk UPDATE via `traffic_repo.mark_ai_referrals()` with CASE/WHEN per source domain.

## Configuration

| Setting | Default |
|---------|---------|
| `google_oauth_client_id` | `None` |
| `google_oauth_client_secret` | `None` |
| `google_oauth_redirect_uri` | `"https://app.deeppresence.ai/api/v1/analytics/google/callback"` |
| `ga4_sync_lookback_days` | 7 |
| `ai_referral_sources` | Comma-separated domain→platform mapping |

## Caching

Redis cache helpers in `core/services/analytics_cache.py`:
- Connection: 30min TTL
- Properties: 1hr TTL
- Performance tables: 5min TTL
- Velocity metrics: 10min TTL
