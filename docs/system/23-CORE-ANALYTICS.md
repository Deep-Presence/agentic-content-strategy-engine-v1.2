# Core Analytics — GA4 Integration

> **Location:** `core/analytics/`
> **Owner:** Core
> **Dependencies:** Google Analytics Data API v1beta, Admin API v1alpha, httpx (OAuth), Fernet encryption
> **Dependents:** `api/routers/analytics.py`, `core/services/analytics_cache.py`, `core/services/content_performance_service.py`, frontend Settings + Content Performance
> **Last Updated:** 2026-04-15

## Overview

The analytics module provides the full GA4 integration: OAuth2 authorization flow, Fernet-encrypted token management with auto-refresh, property selection, traffic + conversion sync with AI referral classification, and per-page aggregation used by the Content Performance page.

Changes since `a9b85f5` (commit `ef06782`, "harden GA4 content performance integration"):

- Hardened `GA4Adapter`: dedicated retry loop for quota errors, explicit translation of Google API exceptions into the module's exception taxonomy, and offline-access validation at token-exchange time.
- Service now short-circuits `sync_data` paths with `GA4AuthError` → sets `AnalyticsSyncStatus.auth_revoked`, rolls back the session, and deactivates the connection.
- `TrafficRow.landing_page_url` is now populated from GA4 `pagePath` (not `landingPage`) for Content Performance — the field name is kept for backward-compatible storage but the semantics are per-page.
- New per-page repository queries power the Content Performance drawer (daily timeseries, source breakdown, AI platform breakdown).

## Architecture

```
OAuth Flow:
  Frontend Settings → authorize URL → Google Consent → /callback → exchange_code
    → Fernet-encrypt tokens → analytics_connections row

Token lifecycle:
  _ensure_fresh_token → check token_expiry <= now + 5min → refresh → persist
    → on failure: AnalyticsSyncStatus.auth_revoked + deactivate

Data Sync:
  sync_data → _ensure_fresh_token → gather(traffic_report, conversion_report)
    → bulk_upsert → mark_ai_referrals (CASE/WHEN batch UPDATE)
    → update_sync_status(success, last_sync_at)

Content Performance reads:
  content_performance_service → GA4TrafficDataRepository.get_per_page_aggregates /
    get_daily_timeseries / get_source_breakdown / get_ai_platform_breakdown
```

## File Structure

| File | Purpose |
|------|---------|
| `service.py` | `GA4AnalyticsService` orchestrator (OAuth, property mgmt, sync) |
| `adapters/ga4.py` | `GA4Adapter` — Google API client (hardened retry + error taxonomy) |
| `models.py` | Domain models: `GA4Property`, `GA4TokenSet`, `TrafficRow`, `ConversionRow`, `SyncResult`, `AnalyticsConnectionInfo` |
| `protocols.py` | `AnalyticsAdapterProtocol` |
| `factory.py` | Adapter factory keyed by `AnalyticsProvider` enum |
| `exceptions.py` | `GA4Error` → `GA4AuthError`, `GA4QuotaError`, `GA4APIError` |

## GA4 Adapter Hardening (`core/analytics/adapters/ga4.py`)

### Constants
`_MAX_RETRIES = 3`, `_RETRY_BASE_SECONDS = 1`, `_DATA_API_MAX_ROWS = 100_000`, `_MAX_PAGINATION_ITERATIONS = 1000` (safety cap — `ga4.py:29-32`).

### OAuth Helpers
- `build_authorization_url(state)` — `access_type=offline`, `prompt=consent` to guarantee a refresh token.
- `exchange_code_for_tokens(code)` — POSTs to `_GOOGLE_TOKEN_URL`. **Raises `GA4AuthError` if Google does not return a `refresh_token`** (`ga4.py:87-92`) — defensive check against offline-access failing.
- `refresh_access_token(refresh_token)` — retains the original refresh token (Google typically does not issue a new one on refresh).
- `revoke_token(token)` — best-effort, never raises.

### Reports
`run_traffic_report()` uses `pagePath` as the primary dimension (not `landingPage`) so Content Performance attributes traffic to the page itself rather than the session origin (`ga4.py:179-263`).

Dimensions: `date`, `pagePath`, `sessionSource`, `sessionMedium`, `sessionCampaignName`.
Metrics: `sessions`, `engagedSessions`, `engagementRate`, `bounceRate`, `averageSessionDuration`, `screenPageViews`, `conversions`, `newUsers`, `totalUsers`.

Pagination loops with `offset += _DATA_API_MAX_ROWS` until `offset >= response.row_count`, bounded by `_MAX_PAGINATION_ITERATIONS` as a safety rail.

### Retry + Error Taxonomy
`_run_report_with_retry()` (`ga4.py:341-366`):
- Exponential backoff on quota errors: 1s, 2s, 4s across 3 attempts.
- `_is_quota_error()` checks `google.api_core.exceptions.ResourceExhausted`.
- `_translate_google_error()` maps: `PermissionDenied`/`Unauthenticated` → `GA4AuthError(403)`, `ResourceExhausted` → `GA4QuotaError(429)`, other `GoogleAPIError` → `GA4APIError(code)`.
- All `google-*` imports are lazy so the module can be imported without the SDK present (for tests / dev boxes).

## Service Layer (`core/analytics/service.py`)

Full method reference lives in [09-CORE-SERVICES.md](09-CORE-SERVICES.md). The analytics-domain behaviour:

### OAuth State Token
`_create_oauth_state()` / `verify_oauth_state()` — HMAC-SHA256 signed state with `company_slug`, `return_url`, `purpose="ga4_oauth"`, `exp` (10 min). Purpose check prevents reuse against other OAuth flows.

### Token Freshness
`_ensure_fresh_token()` (`service.py:472-506`) — refreshes when `token_expiry <= now + 5min` (`_TOKEN_REFRESH_BUFFER_SECONDS = 300`). On `GA4AuthError` marks connection `AnalyticsSyncStatus.auth_revoked` and deactivates.

### Sync Pipeline
`sync_data()` (`service.py:292-459`):

1. `update_sync_status(in_progress)`.
2. `_ensure_fresh_token()`.
3. `asyncio.gather(run_traffic_report, run_conversion_report, return_exceptions=True)` — partial failure tolerated.
4. **Auth errors short-circuit**: `if isinstance(results[i], GA4AuthError): raise results[i]` — caught by outer handler which sets `auth_revoked` and deactivates.
5. Bulk upsert via repos.
6. `mark_ai_referrals()` on both repos, summed into `ai_referrals_tagged`.
7. `update_sync_status(success, last_sync_at=now)`.

### AI Referral Classification
`_parse_ai_referral_sources(raw)` parses `AI_REFERRAL_SOURCES` setting into `{"chatgpt.com": "openai", "claude.ai": "anthropic", ...}`.

## Repository Layer

Three repositories. Full reference in [03-CORE-DB.md](03-CORE-DB.md).

### `mark_ai_referrals()` — Batch CASE/WHEN Update
`GA4TrafficDataRepository.mark_ai_referrals(connection_id, source_platform_map)` (`analytics_repo.py:321-374`) — single UPDATE that tags AI-platform referrals in one round-trip using `CASE/WHEN` for `ai_platform` assignment and `OR` for the `WHERE` clause. Only touches rows where `is_ai_referral=False` (idempotent on re-sync). `ilike` so `chatgpt.com` matches subdomains. Same shape on `GA4ConversionEventRepository`.

### Per-Page Aggregation Queries (Content Performance wiring)
Added by commit `ef06782`:

- `get_per_page_aggregates(company_id, start, end)` — group by `landing_page_url`, sum sessions / pageviews / AI-tagged sessions.
- `get_daily_timeseries(company_id, landing_page_url, start, end)` — daily rollup with AI session split.
- `get_source_breakdown(company_id, landing_page_url, start, end)` — per-source session table.
- `get_ai_platform_breakdown(company_id, landing_page_url, start, end)` — filtered to `is_ai_referral=True`.

## Domain Models (`core/analytics/models.py`)

| Model | Key fields / notes |
|-------|--------------------|
| `GA4Property` | `property_id`, `display_name`, `account_id`, `timezone`, `currency_code` |
| `GA4TokenSet` | internal only — `access_token`, `refresh_token`, `token_expiry`, `scopes` |
| `TrafficRow` | `landing_page_url` is the legacy field name now carrying GA4 `pagePath` values |
| `ConversionRow` | date/event_name/landing_page_url/source/medium + counts |
| `SyncResult` | `traffic_rows_synced`, `conversion_rows_synced`, `ai_referrals_tagged`, `errors` |
| `AnalyticsConnectionInfo` | public-facing connection status (no secrets) |

## API Surface

8 endpoints under `/api/v1/analytics/google`. Full reference in [28-API-ROUTERS.md](28-API-ROUTERS.md).

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/authorize` | Returns signed state + Google consent URL |
| GET | `/callback` | **Public** — exchanges code, stores tokens, redirects to frontend |
| GET | `/connection` | Cached `AnalyticsConnectionInfo` |
| DELETE | `/connection` | Revoke tokens, deactivate; `purge_data=true` also deletes traffic + conversion rows |
| GET | `/properties` | Lists GA4 properties, cached 1h |
| POST | `/select-property` | Stores selected `ga4_property_id` |
| POST | `/sync` | Manual sync trigger |
| POST | `/sync-all` | Cron endpoint — syncs every active connection |

## Redis Caching

- **Connection info**: 30 min TTL. Invalidated on connect, disconnect, select_property.
- **Properties list**: 1 h TTL. Invalidated on connect, disconnect.
- **Content Performance tables**: 5 min TTL. Invalidated after CMS publish/refresh.

## Error Handling

- Token exchange without `refresh_token` → `GA4AuthError("offline access may not have been granted")`.
- Sync quota failures → exponential backoff (3 attempts), then `GA4QuotaError`.
- Auth failures during refresh or reports → `AnalyticsSyncStatus.auth_revoked` + `deactivate()`.
- Conversion and traffic reports run in parallel with `return_exceptions=True`; non-auth errors only populate `SyncResult.errors`.

## Configuration

| Setting | Default |
|---------|---------|
| `google_oauth_client_id` | `None` |
| `google_oauth_client_secret` | `None` |
| `google_oauth_redirect_uri` | `https://app.deeppresence.ai/api/v1/analytics/google/callback` |
| `ga4_sync_lookback_days` | 7 |
| `ai_referral_sources` | `"chatgpt.com:openai,claude.ai:anthropic,perplexity.ai:perplexity,gemini.google.com:google,copilot.microsoft.com:microsoft"` |

## Testing

| Test file | Purpose |
|-----------|---------|
| `tests/analytics/test_adapter.py` | Token exchange, refresh, retry/quota, error translation |
| `tests/analytics/test_repository_sql.py` | `mark_ai_referrals` CASE/WHEN, bulk upsert, per-page queries |
| `tests/analytics/test_service.py` | OAuth state roundtrip, sync partial failure, auth-revoked path |

## Related Commits

- `ef06782` — harden GA4 content performance integration
- Earlier GA4 AI-referral and OAuth work documented in `_memory/decisions.json`
