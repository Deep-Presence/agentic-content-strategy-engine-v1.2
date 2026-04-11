# Core CMS Integration

> **Location:** `core/cms/`
> **Owner:** Core
> **Dependencies:** httpx (async HTTP), Fernet encryption
> **Dependents:** `core/services/cms_service.py`, `api/routers/cms.py`
> **Last Updated:** 2026-04-09

## Overview

The CMS module provides an adapter pattern for integrating with Content Management Systems. Currently supports WordPress via its REST API, with the architecture designed for future Webflow, Strapi, Ghost, and HubSpot adapters. Credentials are encrypted at rest with Fernet.

## Architecture

```
CMSAdapterProtocol (runtime-checkable)
        │
        ▼
WordPressAdapter (concrete)
    ├── validate_connection()
    ├── list_posts() / get_post()
    ├── publish_post() / update_post()
    ├── list_categories()
    └── upload_media()
```

## File Structure

| File | Purpose |
|------|---------|
| `protocols.py` | `CMSAdapterProtocol` — runtime-checkable interface |
| `models.py` | Pydantic domain models (CMSPost, CMSPostCreate, CMSConnectionConfig) |
| `factory.py` | `create_cms_adapter()` — adapter factory with provider registry |
| `adapters/wordpress.py` | WordPress REST API implementation |
| `exceptions.py` | Exception hierarchy (CMSError → Auth/API/NotFound/RateLimit/Connection) |

## WordPress Adapter

- **Auth:** Application Passwords (WP 5.6+), Basic Auth header
- **Validation:** GET `/wp-json` + GET `/wp-json/wp/v2/users/me`
- **Category resolution:** Auto-creates missing categories (max 5 per call)
- **Yoast SEO:** Maps seo_title/description to WP meta fields
- **Pagination:** Capped at 5,000 posts (50 pages x 100/page)
- **HTTP client:** httpx.AsyncClient, 30s timeout, follow_redirects=True

## Integration Points

The `CMSService` orchestrator (in `core/services/cms_service.py`) coordinates:
1. Connection lifecycle (validate, encrypt credentials, persist to DB)
2. Post sync (pull existing posts into local index)
3. Content publish (Content Engine brief → CMS via adapter)
4. Post refresh (update existing CMS post with new content)
