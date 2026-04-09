# Frontend Components

> **Location:** `frontend/src/components/`
> **Owner:** Frontend
> **Dependencies:** Tailwind CSS, Framer Motion, react-day-picker, lucide-react
> **Last Updated:** 2026-04-09

## Overview

28 shared UI components in `src/components/ui/` plus auth components in `src/components/auth/`. All components use design tokens from `theme.config.ts` via CSS variables — no hardcoded colors.

## Auth Components (`auth/`)

| Component | Purpose |
|-----------|---------|
| `AuthProvider` | Initializes auth state on mount, calls `useAuth().initialize()` |
| `AuthGuard` | Blocks rendering until authenticated, redirects to login |
| `RoleGate` | Shows children only if user has required role |

## UI Components (`ui/`)

### Layout & Navigation
| Component | Purpose |
|-----------|---------|
| `Sidebar` | Main navigation with collapsible state |
| `TopBar` | Header bar with workspace selector + user menu |
| `TabBar` | Horizontal tab navigation |
| `FilterBar` | Page-level filter controls |
| `SearchCommand` | Cmd+K search modal (12 routes) |
| `WorkspaceSelector` | Dropdown for workspace switching |

### Data Display
| Component | Purpose |
|-----------|---------|
| `MetricCard` | KPI card with label, value, trend |
| `KPIRow` | Horizontal row of metric cards |
| `ScoreGauge` | Circular score visualization |
| `Sparkline` | Inline mini chart |
| `ProgressBar` | Horizontal progress indicator |
| `StatusDot` | Colored status indicator |
| `Badge` | Label badge with variants |
| `Avatar` | User avatar with fallback |
| `Skeleton` | Loading placeholder |
| `EmptyState` | No-data placeholder |

### Interactive
| Component | Purpose |
|-----------|---------|
| `Button` | Primary button with variants |
| `Input` | Text input with validation |
| `Toggle` | Switch toggle |
| `Dropdown` | Menu dropdown |
| `Modal` | Dialog overlay |
| `Card` | Container card |
| `Toast` | Notification toast |

### Custom (Built for this project)
| Component | Purpose |
|-----------|---------|
| `DateRangePicker` | Two-month calendar with presets (react-day-picker v9) |
| `BrandLogo` | Favicon fetcher: Google API → Clearbit → Logo.dev |
| `SlideDrawer` | 50vw right drawer with Framer Motion, escape-to-close |
| `LocusLogo` | App logo component |
