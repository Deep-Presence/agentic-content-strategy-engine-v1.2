# Frontend Overview

> **Location:** `frontend/`
> **Owner:** Frontend
> **Dependencies:** Next.js 14, React 18, TypeScript, Tailwind CSS, Zustand
> **Dependents:** Users (browser)
> **Last Updated:** 2026-04-09

## Overview

The frontend is a Next.js 14 (App Router) dashboard with 12 pages, BFF proxy authentication, 5 Zustand stores, and 28 shared UI components. It uses a Backend-for-Frontend pattern where no backend URL or auth token is ever exposed to the browser — all proxied through Next.js API routes with httpOnly cookies.

## Architecture

```
Browser ──[httpOnly dp_session cookie]──► Next.js BFF
                                              │
                    ┌─────────────────────────┼─────────────────┐
                    ▼                         ▼                 ▼
              /api/auth/*              /api/v1/[...path]   Middleware
              (6 auth handlers)        (catch-all proxy)   (CSP + auth redirect)
                    │                         │
                    ▼                         ▼
              Set/clear cookie         Inject Bearer header
                    │                         │
                    └─────────────────────────┼─────────────────┘
                                              ▼
                                    FastAPI Backend :8000
```

## BFF Proxy Pattern

- **Auth routes** (`/api/auth/`): Login, register, join, me, logout, invite. Extract token from backend response, set httpOnly cookie, return user/company without token.
- **Catch-all proxy** (`/api/v1/[...path]/route.ts`): Read token from cookie, inject `Authorization: Bearer` header, forward to `BACKEND_URL`. Streams SSE responses. Clears cookie on 401.
- **Middleware** (`middleware.ts`): Per-request CSP nonce, cookie expiry validation, auth redirects.

## State Management (5 Zustand Stores)

| Store | State | Key Methods |
|-------|-------|-------------|
| `auth` | user, company, sessionExpiresAt | login, register, join, logout, initialize |
| `theme` | mode (light/dark) | toggle |
| `sidebar` | collapsed | toggle |
| `workspace` | workspaces, activeId, companyName | setActiveWorkspace, addWorkspace |
| `notifications` | items, unreadCount | add, markRead, markAllRead |

**Cross-tab sync:** `BroadcastChannel` for login/logout events.

## Hooks

| Hook | Purpose |
|------|---------|
| `useAuth` | Primary auth interface: isAuthenticated, hasRole(), companySlug, login/logout |
| `useStreamToken` | Acquire short-lived SSE stream token |

## API Client (`lib/api-client.ts`)

All calls same-origin (no token injection needed — cookie sent automatically):
- `api.get<T>()`, `api.post<T>()`, `api.put<T>()`, `api.patch<T>()`, `api.del<T>()`
- `api.getText()` for non-JSON responses
- `authApi.login()`, `.register()`, `.join()`, `.me()`, `.logout()`, `.invite()`
- `createSSEConnection(taskId, streamToken, onEvent, onError)` for EventSource
- Single-flight 401 handler prevents logout spam

## Design System

- **Fonts:** Space Grotesk (display) + JetBrains Mono (data/code)
- **Accent:** Deep Teal (#5BA4C4 light / #6CB8D2 dark)
- **Tokens:** All in `theme.config.ts` → CSS variables → Tailwind
- **Rules:** No hardcoded colors, visible 1px borders, max font-weight 600, no gradients

## 28 UI Components

Core: Avatar, Badge, Button, Card, Dropdown, EmptyState, Input, Modal, Toggle, ProgressBar, Skeleton, StatusDot, Toast

Custom: LocusLogo, WorkspaceSelector, Sidebar, TopBar, TabBar, FilterBar, MetricCard, KPIRow, ScoreGauge, Sparkline, SearchCommand, DateRangePicker, BrandLogo, SlideDrawer
