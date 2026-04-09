# Frontend Dashboard Pages

> **Location:** `frontend/src/app/(dashboard)/`
> **Owner:** Frontend
> **Dependencies:** API client, Zustand stores, UI components
> **Last Updated:** 2026-04-09

## Overview

12 dashboard pages under the `(dashboard)` route group, sharing a common layout with sidebar + topbar. Each page follows a pattern of `_lib/` (types, API, parsers), `_hooks/` (data fetching), and `_components/` (page-specific UI).

## Page Inventory

| Route | Page Name | Backend Pipeline | Key Components |
|-------|-----------|-----------------|----------------|
| `/` | Brand Presence | KB + Daily Tracker | KPI cards, presence score chart, competitive leaderboard, platform intelligence |
| `/analytics` | Citation Intelligence | Daily Tracker | Citation URLs table, platform tabs, momentum chart, detail drawer |
| `/competitive-position` | Competitive Position | Gap Analysis | SOV hero, cluster cards, head-to-head, landscape grid |
| `/prompt-tracking` | Prompt Tracking | Daily Tracker | Prompt detail drawer, answer history, mention rates, fanouts |
| `/content-performance` | Content Performance | Content Engine + GA4 | Content table, CPS scatter, lifecycle distribution, velocity |
| `/technical-readiness` | Technical SEO Audit | Site Audit | 9 components: bot access, crawl activity, dimensions, gaps, fixes, snippet readiness |
| `/embedding-lab` | Deep Embedding Lab | Gap Analysis | 14 components: territory map (D3), knowledge graph, cluster scorecard, gap intelligence |
| `/planner` | Content Planner | Topic Discovery | Cluster explorer, custom topic modal, detail drawer, priority queue |
| `/content-studio` | Content Studio | Content Engine | Kanban board (ColumnBoard), BlockNote editor, left/right sidebars, content cards |
| `/artifacts` | Brand Hub | KB + VSG + AP + Gap | 13 components: markdown renderer, persona detail, version history, upload modal |
| `/attribution` | Attribution & Revenue | Demo (no backend) | Attribution funnel, conversion path, ROI table, revenue donut |
| `/settings` | Settings | Auth + CMS + GA4 | 7 tabs: team, billing, integrations (WordPress + GA4), models, notifications, profile |

## Data Integration Status

| Page | Data Source | Status |
|------|------------|--------|
| Brand Presence | Mock data | Pending API integration |
| Analytics | Mock data | Pending |
| Competitive Position | Real API (gap_data) | Integrated |
| Prompt Tracking | Real API (daily_tracker) | Integrated |
| Content Performance | Real API (content_performance) | Integrated |
| Technical Readiness | Real API (site_audit) | Integrated |
| Embedding Lab | Real API (gap_data) | Integrated |
| Planner | Real API (topic_discovery) | Integrated |
| Content Studio | Real API (content_data) + SSE | Integrated |
| Brand Hub | Real API (artifacts, KB, AP, VSG) | Integrated |
| Attribution | Mock data | Demo only |
| Settings | Real API (auth, CMS, GA4) | Team + Integrations integrated |

## Common Page Pattern

```
page/
├── page.tsx                    ← Server component (minimal)
├── _components/                ← Page-specific components
│   ├── PageClient.tsx          ← Client component (main logic)
│   └── FeatureComponent.tsx
├── _hooks/                     ← Data fetching hooks
│   └── usePageData.ts
└── _lib/                       ← Types, API calls, parsers
    ├── types.ts
    ├── api.ts
    └── parsers.ts
```
