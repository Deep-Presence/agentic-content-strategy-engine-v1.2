# Frontend Auth & Onboarding

> **Location:** `frontend/src/app/(auth)/`, `frontend/src/app/onboarding/`
> **Owner:** Frontend
> **Dependencies:** BFF proxy, auth store, useAuth hook
> **Last Updated:** 2026-04-09

## Overview

Auth pages (login, register, join) use a separate layout without sidebar. The onboarding flow guides new users through company setup. All auth state managed via Zustand store with httpOnly cookie — token never in client state.

## Auth Pages (`(auth)/`)

| Route | Page | Purpose |
|-------|------|---------|
| `/login` | Login | Email + password → `authApi.login()` → cookie set by BFF |
| `/register` | Register | Name + email + password + company → `authApi.register()` |
| `/join` | Join | Invite code redemption → `authApi.join()` |

**Layout:** `(auth)/layout.tsx` — no sidebar, centered card layout.

**Redirect logic:** Middleware redirects authenticated users away from auth pages to `/`.

## Auth Flow

```
1. User submits credentials on /login
2. Client calls authApi.login({ email, password })
3. BFF POST /api/auth/login proxies to backend
4. Backend returns { access_token, user, company }
5. BFF sets httpOnly dp_session cookie (24h)
6. BFF returns { user, company, session_expires_at } (no token)
7. Client stores user/company in Zustand auth store
8. Redirect to / (or ?redirect= target)
```

## Cross-Tab Sync

`BroadcastChannel('dp-auth')` posts 'login'/'logout' messages. Other tabs react by re-initializing auth state or redirecting to login.

## Onboarding (`onboarding/`)

4-step setup wizard for new companies:
1. Company details
2. Product configuration
3. Persona setup (optional seed data)
4. Launch pipelines (KB → AP → VSG → GA → TD)

Uses SSE streaming via `useStreamToken` hook to show real-time pipeline progress.
