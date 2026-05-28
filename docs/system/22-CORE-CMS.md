# Core CMS Integration

> **Location:** `core/cms/`, `core/services/cms_service.py`, `core/services/cms_cache.py`, `api/routers/cms.py`
> **Owner:** Core
> **Dependencies:** httpx (async HTTP), Fernet encryption, Redis (cache), StorageBackend
> **Dependents:** `api/routers/cms.py`, Content-to-Prompt pipeline, Content Inventory service
> **Last Updated:** 2026-04-24

## Overview

The CMS module provides an adapter pattern for integrating with Content Management Systems. Currently supports WordPress via its REST API, with the architecture designed for future Webflow, Strapi, Ghost, and HubSpot adapters. Credentials are encrypted at rest with Fernet. The module handles the full lifecycle: connection validation, content sync (including content inventory hydration and prompt generation), SEO-enriched publishing (Yoast meta fields), content refresh, stale content detection, and Redis-backed caching with explicit invalidation.

## Architecture

```
CMSAdapterProtocol (runtime-checkable)
        |
        v
WordPressAdapter (concrete)
    +-- validate_connection()
    +-- list_posts() / list_all_posts() / get_post()
    +-- publish_post() / update_post()
    +-- list_categories()
    +-- upload_media()
        |
        v
CMSService (orchestrator)
    +-- connect() -- validate, encrypt, persist, auto-sync
    +-- sync_existing_content() -- pull posts, hydrate inventory, generate prompts
    +-- publish_brief() -- read final.md, convert HTML, publish, record, auto-prompt
    +-- refresh_post() -- update existing CMS post
    +-- get_stale_actions() / queue_stale_for_refresh()
    +-- list_synced_posts() / list_categories()
        |
        v
CMS Cache Layer (core/services/cms_cache.py)
    +-- Categories (1h TTL)
    +-- Connection info (30min TTL)
    +-- Stale actions (30min TTL)
    +-- Synced posts (10min TTL, paginated)
    +-- Bulk invalidation: invalidate_all_cms_caches()
```

## File Structure

| File | Purpose |
|------|---------|
| `core/cms/protocols.py` | `CMSAdapterProtocol` -- runtime-checkable interface |
| `core/cms/models.py` | Pydantic domain models (CMSPost, CMSPostCreate, CMSPostUpdate, CMSConnectionConfig, CMSPublishMetadata, etc.) |
| `core/cms/factory.py` | `create_cms_adapter()` -- adapter factory with provider registry |
| `core/cms/adapters/wordpress.py` | WordPress REST API implementation |
| `core/cms/exceptions.py` | Exception hierarchy: `CMSError` -> `CMSAuthError`, `CMSAPIError`, `CMSNotFoundError`, `CMSRateLimitError`, `CMSConnectionError` |
| `core/services/cms_service.py` | `CMSService` orchestrator -- connection, sync, publish, refresh |
| `core/services/cms_cache.py` | Redis cache helpers -- get/set/invalidate per cache domain |
| `api/routers/cms.py` | 11 REST endpoints with tenant isolation and RBAC |

## Detailed Reference

### WordPress Adapter (`core/cms/adapters/wordpress.py`)

**Auth:** Application Passwords (WordPress 5.6+). The user provides `username` + application password. These are base64-encoded as `username:app_password` and sent as a Basic Auth header.

**Connection validation (`validate_connection()`):**
1. `GET {site_url}/wp-json` -- verifies REST API is accessible. Returns site name, URL, version.
2. `GET {api_base}/users/me?context=edit` -- verifies credentials. Returns display name and capabilities.

Returns `CMSConnectionStatus` with `connected=True/False`, site metadata, and error details on failure.

**SEO Fields (Yoast Integration):**

On **read**, `_parse_post()` extracts SEO data from the `yoast_head_json` field (requested via `_fields=...yoast_head_json`):

| CMSPost Field | Yoast Source |
|---------------|-------------|
| `seo_title` | `yoast_head_json.title` |
| `seo_description` | `yoast_head_json.og_description` |

On **write** (`publish_post()` and `update_post()`), SEO fields are mapped to WordPress post meta:

| CMSPostCreate/Update Field | WP Meta Key |
|---------------------------|-------------|
| `seo_title` | `_yoast_wpseo_title` |
| `seo_description` | `_yoast_wpseo_metadesc` |
| `canonical_url` | `_yoast_wpseo_canonical` |

These are sent as `payload["meta"] = {"_yoast_wpseo_title": ..., ...}`. Only non-empty fields are included.

**Category resolution (`_resolve_category_ids()`):**
- Maps category names to WordPress category IDs.
- Auto-creates missing categories via `POST /categories`.
- Capped at `_MAX_NEW_CATEGORIES_PER_CALL = 5` new categories per publish to prevent unbounded API calls.
- Logs WARNING when cap is reached with count of skipped categories.

**Tag resolution (`_resolve_tag_ids()`):**
- Maps tag names to WordPress tag IDs via `GET /tags` then `POST /tags` for missing.
- No creation cap (tags are lower-stakes than categories).

**Pagination:**
- `list_all_posts()`: Paginates through all posts for initial sync. Capped at `_MAX_PAGINATION_PAGES = 50` pages (50 x 100 = 5,000 posts).
- Returns `(posts, truncated)` tuple. Logs WARNING when truncated.
- `list_posts()`: Single page with optional `after` and `modified_after` date filters. Orders by `modified DESC`.

**Post parsing (`_parse_post()`):**
- Normalizes WP REST API response into `CMSPost`.
- Word count: `len(content_html.split())`.
- Raw metadata preserved in `raw_metadata` field.

**Datetime parsing (`_parse_dt()`):**
- Uses `datetime.fromisoformat()`. Returns `None` on invalid input.
- WordPress may return naive datetimes (no timezone info) -- see timezone handling below.

**HTTP client:** `httpx.AsyncClient`, 30s timeout, `follow_redirects=True`. Optional `_transport` parameter for test injection.

### Pydantic Models (`core/cms/models.py`)

All fields have defaults for backward compatibility.

| Model | Purpose |
|-------|---------|
| `CMSConnectionConfig` | Credentials: provider, site_url, api_key, username, extra |
| `CMSConnectionStatus` | Validation result: connected, site_name, capabilities, error |
| `CMSPost` | Normalized post: cms_id, title, slug, content_html, seo_title, seo_description, word_count, raw_metadata |
| `CMSPostCreate` | Publish payload: title, content_html, seo_title, seo_description, canonical_url, categories, tags, published_at |
| `CMSPostUpdate` | Refresh payload: only non-None fields sent (partial update) |
| `CMSPublishMetadata` | UI-provided SEO/publish metadata: slug, meta_title, meta_description, canonical_url, schema_markup, tags |
| `CMSCategory` | Category: cms_id, name, slug, parent_id, post_count |
| `CMSMediaUpload` / `CMSMediaResult` | Media upload payload and result |

Enums (`CMSPostStatus`, `CMSProvider`) are defined in `core/db/enums` and re-exported from `models.py`.

### CMS Service (`core/services/cms_service.py`)

**NOT a Protocol -> JsonService -> DbService pattern.** This is a standalone orchestrator (similar to `DailyTrackerOrchestrator`) that coordinates between the CMS adapter, database repositories, and StorageBackend.

**Constructor dependencies:**

| Parameter | Type | Purpose |
|-----------|------|---------|
| `connection_repo` | `CMSConnectionRepository` | Connection CRUD |
| `publish_repo` | `CMSPublishRecordRepository` | Publish audit trail |
| `synced_post_repo` | `CMSSyncedPostRepository` | Synced post index |
| `storage` | `StorageBackend` | Read `final.md` for publish |
| `fernet_key` | `str` | Credential encryption/decryption |
| `content_repo` | `ContentRepository | None` | Update content piece status on publish |
| `inventory_service` | `Any | None` | Content inventory hydration on sync/publish |
| `company_repo` | `CompanyRepository | None` | Resolve company name for auto-prompts |
| `content_to_prompt_orchestrator` | `Any | None` | Auto-prompt generation on publish |

#### Connect Flow (`connect()`)

1. Creates `CMSConnectionConfig` and adapter.
2. Validates connection via adapter.
3. Encrypts credentials via Fernet.
4. **Upserts** connection: updates existing row in-place (preserves FK references from publish_records and synced_posts) or creates new. This avoids the deactivate+insert pattern that violates the unique `(company_id, tenant_id)` constraint (Codex F8).

#### Auto-Sync on First Connect

The API router (`cms.py:connect_cms`) detects first-time connects (`conn.last_sync_at is None`) and automatically launches a `cms_sync` background task. This populates the content inventory immediately without requiring a separate sync click.

```
Connect (first time) -> validate -> persist -> auto-sync task -> content inventory hydration
```

#### Sync Flow (`sync_existing_content()`)

1. Fetches all published posts via `adapter.list_all_posts()`.
2. Fetches all categories and builds `cms_id -> name` map.
3. For each post:
   - **Timezone-aware comparison:** If `modified_at` is naive (no tzinfo), applies `replace(tzinfo=timezone.utc)` before comparing against the stale threshold. This fixes incorrect staleness calculations for WordPress sites returning naive datetimes.
   - Determines staleness (threshold: `STALE_THRESHOLD_DAYS = 30`).
   - Resolves category IDs to names.
   - Sanitizes `content_preview`: strips HTML tags, truncates to 500 chars.
   - Upserts into `cms_synced_posts` table.
4. **Content inventory hydration** (non-blocking, savepoint-isolated):
   - Calls `inventory_service.ingest_from_cms_sync()` to create/update content inventory pages.
   - Links synced posts to inventory IDs via `batch_link_inventory_ids()`.
   - Runs in a nested savepoint (`begin_nested()`) so DB errors don't poison the session.
5. Updates connection sync metadata (`last_sync_at`, `sync_post_count`).

#### Publish Flow (`publish_brief()`)

1. Reads `final.md` from StorageBackend at `content/{effective_slug}/content/{brief_id}/final.md`.
2. Extracts title (first H1), normalizes publish metadata, generates slug.
3. Converts markdown to HTML (via `markdown` library with tables/fenced_code/toc/attr_list extensions; falls back to minimal conversion if library unavailable).
4. Publishes via adapter with SEO fields mapped to Yoast meta.
5. **Cache invalidation:** If categories were specified, invalidates category cache via `invalidate_categories(site_url)`.
6. Records in `cms_publish_records` table.
7. Updates content piece status to `published` with `published_url` and publish metadata merged into `evaluation_results`.
8. Registers with content inventory via `register_published_content()`.
9. **Auto-prompt generation chain:** If inventory item was created successfully, calls `_auto_generate_prompts_for_published_page()`:
   - Resolves company display name via `company_repo.get_by_slug()`.
   - Calls `content_to_prompt_orchestrator.run_for_pages()` with `auto_approve=True` and `k=6`.
   - Best-effort: logged and swallowed on failure.

```
Publish -> HTML convert -> CMS create -> record -> content piece update
   -> inventory register -> auto-prompt generation
```

#### Content Refresh Flow (`refresh_post()`)

1. Reads updated `final.md`.
2. Converts to HTML.
3. Updates existing CMS post via `adapter.update_post()` (only title and content_html).
4. Records refresh in publish records table.
5. Updates content piece status to `published`.

#### Stale Content Management

**`get_stale_actions()`:** Returns stale posts as action cards for the Home dashboard. Redis-cached (30min TTL). Each card includes: title, URL, staleness_days, description, queued_for_refresh flag.

**`queue_stale_for_refresh()`:** Marks a stale post as queued and creates a Triage tile in Content Studio:
1. Verifies post exists and belongs to the requesting company (tenant isolation -- same error for not-found and wrong-tenant to prevent information leakage, Codex F2).
2. Generates `brief_id = refresh-{uuid[:8]}`.
3. Creates `ContentPieceModel` row with `status=planned` (appears in Kanban Triage column).
4. Does NOT trigger any Content Engine pipeline run.

#### Caching Strategy

All list and read endpoints pass through Redis cache (via `core/services/cms_cache.py`):

| Cache | Key Pattern | TTL | Invalidated By |
|-------|-------------|-----|----------------|
| Categories | `cache:cms:categories:{site_url}` | 1h | `publish_brief()` (if categories specified), `invalidate_categories()` |
| Connection info | `cache:cms:{slug}:connection:{tenant}` | 30min | `connect()`, `disconnect()` |
| Stale actions | `cache:cms:{slug}:stale` | 30min | `queue_stale_for_refresh()` (via `invalidate_all_cms_caches()`) |
| Synced posts | `cache:cms:{slug}:posts:stale={bool}:limit={int}:offset={int}` | 10min | `invalidate_all_cms_caches()` |

`invalidate_all_cms_caches(slug)` uses `cache_delete_pattern(redis, f"cache:cms:{slug}:*")` via `scan_iter()` for efficient bulk deletion.

All cache operations run via `asyncio.to_thread()` (sync Redis calls from async handlers).

### API Router (`api/routers/cms.py`)

**Prefix:** `/api/v1/cms`

11 endpoints with tenant isolation (company_slug from auth state) and RBAC:

| # | Method | Path | Auth | Description |
|---|--------|------|------|-------------|
| 1 | `POST` | `/connect` | member/superuser | Connect CMS + auto-sync on first connect |
| 2 | `GET` | `/connection` | any auth | Get connection info (Redis-cached) |
| 3 | `DELETE` | `/connection` | member/superuser | Soft-deactivate connection |
| 4 | `POST` | `/sync` | member/superuser | Re-sync content (background task, 202) |
| 5 | `GET` | `/synced-posts` | any auth | List synced posts (paginated, Redis-cached) |
| 6 | `GET` | `/stale-actions` | any auth | Stale content cards for Home dashboard |
| 7 | `POST` | `/stale-to-triage` | member/superuser | Queue stale post for refresh |
| 8 | `POST` | `/publish` | member/superuser | Publish brief to CMS |
| 9 | `POST` | `/refresh/{cms_post_id}` | member/superuser | Update existing CMS post |
| 10 | `GET` | `/publish-history` | any auth | Publish/refresh audit trail |
| 11 | `GET` | `/categories` | any auth | CMS categories (Redis-cached) |

**Error mapping (`_handle_cms_error()`):**

| CMS Exception | HTTP Status |
|---------------|-------------|
| `CMSNotFoundError` | 404 |
| `CMSAuthError` | 401 |
| `CMSRateLimitError` | 429 |
| `CMSConnectionError` | 502 |
| `CMSError` (base) | 400 |

**Cache invalidation after writes:**
- `connect()`: invalidates connection info cache.
- `disconnect()`: invalidates connection info cache.
- `stale_to_triage()`: invalidates all CMS caches for the company.
- `publish()`: invalidates all GA4 caches (`invalidate_all_ga4_caches`).
- `refresh()`: invalidates all GA4 caches.

**Background sync task:** The `/sync` endpoint creates a `cms_sync` task via TaskStore and launches `run_cms_sync_task()` as a background `asyncio.create_task()`.

## Integration Points

| Component | Interaction |
|-----------|-------------|
| `core/services/content_inventory_service.py` | `ingest_from_cms_sync()` on sync, `register_published_content()` on publish |
| Content-to-Prompt pipeline | `_auto_generate_prompts_for_published_page()` on publish (auto_approve=True, k=6) |
| `core/db/repositories/cms_repo.py` | `CMSConnectionRepository`, `CMSPublishRecordRepository`, `CMSSyncedPostRepository` |
| `core/db/repositories/content_repo.py` | Update content piece status to `published` on publish/refresh |
| `core/storage/` | `StorageBackend.read()` for `final.md` |
| Redis cache layer | `core/services/cms_cache.py` -- categories, connection, stale, posts caches |
| GA4 analytics cache | Invalidated after publish/refresh (`invalidate_all_ga4_caches`) |

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `cms_fernet_key` | `None` | Fernet encryption key for CMS credentials |

## Error Handling

- **Connection validation failure:** Returns `CMSConnectionStatus` with `connected=False` and error message. No credentials stored.
- **Credential encryption/decryption:** Uses Fernet symmetric encryption. Invalid key or corrupted data raises `InvalidToken`.
- **Content inventory hydration failure:** Logged as WARNING, sync continues without inventory. Savepoint-isolated (`begin_nested()`).
- **Auto-prompt generation failure:** Logged as WARNING, publish result still returned. Best-effort.
- **WordPress API errors:** Mapped to typed exceptions via `_handle_cms_error()`.
- **Markdown library unavailable:** Falls back to minimal HTML conversion (H1-H3, paragraph wrapping, HTML escaping).
- **Timezone-naive datetimes from CMS:** `replace(tzinfo=timezone.utc)` applied before staleness comparison. Prevents incorrect stale flags.
- **Pagination cap reached:** Logged as WARNING, returns `truncated=True` in sync result.
