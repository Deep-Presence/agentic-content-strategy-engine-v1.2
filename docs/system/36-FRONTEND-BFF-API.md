# Frontend BFF & API Routes

> **Location:** `frontend/src/app/api/`
> **Owner:** Frontend
> **Dependencies:** Backend API, httpOnly cookies
> **Last Updated:** 2026-04-09

## Overview

The BFF (Backend-for-Frontend) layer consists of Next.js API route handlers that proxy requests to the Python backend. Auth routes manage httpOnly cookies. The catch-all proxy forwards all `/api/v1/*` requests with Bearer token injection. No backend URL or auth token is ever exposed to the browser.

## Route Structure

```
frontend/src/app/api/
├── auth/
│   ├── login/route.ts      ← POST: proxy login, set cookie
│   ├── register/route.ts   ← POST: proxy register, set cookie
│   ├── join/route.ts       ← POST: proxy join (invite), set cookie
│   ├── me/route.ts         ← GET: proxy /auth/me
│   ├── logout/route.ts     ← POST: clear cookie
│   └── invite/route.ts     ← POST: proxy invite creation
├── v1/
│   └── [...path]/route.ts  ← GET/POST/PUT/PATCH/DELETE: catch-all proxy
└── analytics/google/
    └── callback/route.ts   ← GET: OAuth callback (public)
```

## Auth Routes

### Login (`POST /api/auth/login`)
1. Receive `{ email, password }`
2. Proxy to `POST /api/v1/auth/login` (backend)
3. Extract `access_token` from response
4. Set httpOnly `dp_session` cookie via `setSessionCookie(response, token)`
5. Return `{ user, company, session_expires_at }` (no token)

### Register / Join
Same pattern as login — proxy to backend, set cookie, return user/company.

### Logout (`POST /api/auth/logout`)
Clear `dp_session` cookie via `clearSessionCookie(response)`.

### Me (`GET /api/auth/me`)
Read token from cookie, proxy to `GET /api/v1/auth/me` with Bearer header.

## Catch-All Proxy (`/api/v1/[...path]/route.ts`)

- Reads `dp_session` cookie, injects `Authorization: Bearer {token}`
- Forwards query params as-is
- **SSE support:** Streams `text/event-stream` responses (no buffering)
- **401 handling:** Clears session cookie on backend 401
- **Methods:** GET, POST, PUT, PATCH, DELETE

## GA4 OAuth Callback (`/api/analytics/google/callback`)

Public route (no auth required). Receives OAuth code from Google, proxies to backend callback endpoint, redirects to frontend settings page.

## Cookie Configuration

```typescript
{
  name: 'dp_session',
  httpOnly: true,
  secure: process.env.NODE_ENV === 'production',
  sameSite: 'lax',
  maxAge: 86400,  // 24 hours
  path: '/',
}
```
