# Deep Presence — Brand System Reference

> **This file is the single source of truth for all design implementation.**
> When building any UI for Deep Presence, follow these specifications exactly.
> All values are final — do not improvise colors, fonts, spacing, or component patterns.
> Live reference: https://deploy-beryl-gamma.vercel.app

---

## 1. Design Philosophy

Deep Presence follows a **Supabase-inspired** design system: clean borders, pure grayscale neutrals, visible structure, and consistent border-based hierarchy in both light and dark modes.

### Core Principles

1. **Precision over decoration** — Every element earns its place. No ornamental gradients. If a line exists, it measures something.
2. **Depth over surface** — The brand reveals layers on inspection. First glance: calm. Second glance: the system is deliberate.
3. **Signal over noise** — One idea per surface. When in doubt, remove.

### Key Design Rules

- **Both modes use visible borders**: Cards and containers always have `1px solid var(--border)`. No borderless cards.
- **Light mode**: Uses Slate-tinted grays (slight blue undertone) — `#F8F9FA`, `#FBFCFD`, `#ECEEF0`.
- **Dark mode**: Uses pure neutral grays (no blue tint) — `#171717`, `#1F1F1F`, `#2E2E2E`.
- **Border hover**: Use `--border-strong` on hover for interactive elements.
- **Shadows are minimal**: `--shadow-float` for floating elements only (tooltips, dropdowns, toasts).
- **Dense UI**: 30px button/input heights, 10-11px label fonts, 6px table cell padding.
- **No glassmorphism on cards** — clean solid backgrounds with borders.

---

## 2. Design Tokens (CSS Custom Properties)

Copy this entire block into any project stylesheet. Use `var(--token-name)` everywhere — never hardcode values.

### Light Mode (default)

```css
:root {
  /* Backgrounds — Slate-tinted grays */
  --bg: #F8F9FA;
  --surface: #FBFCFD;
  --surface-raised: #FFFFFF;
  --surface-overlay: #FBFCFD;

  /* Borders — visible, Slate-based */
  --border: #ECEEF0;
  --border-subtle: #F1F3F5;
  --border-strong: #D7DBDF;
  --border-control: #D7DBDF;

  /* Text — Slate.12 → Slate.9 */
  --text-primary: #11181C;
  --text-secondary: #687076;
  --text-tertiary: #889096;
  --text-on-accent: #FFFFFF;

  /* Accent — Deep Presence Teal */
  --accent: #5BA4C4;
  --accent-hover: #4A93B3;
  --accent-subtle: rgba(91,164,196,0.08);

  /* Semantic */
  --success: #34B27B;
  --success-subtle: rgba(52,178,123,0.08);
  --warning: #DC7B18;
  --warning-subtle: rgba(220,123,24,0.08);
  --error: #E5484D;
  --error-subtle: rgba(229,72,77,0.06);
  --info: #5BA4C4;
  --info-subtle: rgba(91,164,196,0.08);

  /* Brand */
  --deep-verdigris: #5BA4C4;
  --signal-amber: #DC7B18;
  --signal-amber-subtle: rgba(220,123,24,0.1);

  /* Radius */
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --radius-xl: 12px;
  --radius-full: 9999px;

  /* Shadows — minimal */
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.04);
  --shadow-md: 0 2px 4px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.06);
  --shadow-lg: 0 4px 8px rgba(0,0,0,0.04), 0 2px 4px rgba(0,0,0,0.06);
  --shadow-float: 0 8px 30px rgba(0,0,0,0.08), 0 0 0 1px #ECEEF0;

  /* Typography */
  --font-display: 'Space Grotesk', sans-serif;
  --font-body: 'Space Grotesk', sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}
```

### Dark Mode

```css
[data-theme="dark"] {
  /* Backgrounds — pure neutral grays */
  --bg: #171717;
  --surface: #1F1F1F;
  --surface-raised: #292929;
  --surface-overlay: #242424;

  /* Borders — pure gray, visible */
  --border: #2E2E2E;
  --border-subtle: #242424;
  --border-strong: #3E3E3E;
  --border-control: #3E3E3E;

  /* Text */
  --text-primary: #EDEDED;
  --text-secondary: #A0A0A0;
  --text-tertiary: #707070;
  --text-on-accent: #FFFFFF;

  /* Accent — lighter teal for dark mode */
  --accent: #6CB8D2;
  --accent-hover: #7CC8E2;
  --accent-subtle: rgba(108,184,210,0.1);

  /* Semantic */
  --success: #3ECF8E;
  --success-subtle: rgba(62,207,142,0.12);
  --warning: #FFB224;
  --warning-subtle: rgba(255,178,36,0.12);
  --error: #F87171;
  --error-subtle: rgba(248,113,113,0.12);
  --info: #6CB8D2;
  --info-subtle: rgba(108,184,210,0.1);

  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.2);
  --shadow-md: 0 2px 8px rgba(0,0,0,0.3);
  --shadow-lg: 0 4px 16px rgba(0,0,0,0.4);
  --shadow-float: 0 8px 30px rgba(0,0,0,0.4), 0 0 0 1px #2E2E2E;
}
```

---

## 3. Typography

### Font Loading

```html
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
```

### Font Families

| Role | Font | Variable |
|------|------|----------|
| Display / Headlines | Space Grotesk | `--font-display` |
| Body / UI | Space Grotesk | `--font-body` |
| Code / Monospace | JetBrains Mono | `--font-mono` |

**Important**: Both display and body use Space Grotesk. ONE typeface for all non-code text.

### Type Scale

| Token | Size | Weight | Letter-spacing | Line-height | Usage |
|-------|------|--------|----------------|-------------|-------|
| `display-xl` | 42px | 600 | -0.035em | 1.05 | Hero headlines, landing page |
| `display-l` | 36px | 600 | -0.025em | 1.1 | Section heroes |
| `h1` | 28px | 600 | -0.02em | 1.15 | Page titles |
| `h2` | 20px | 600 | -0.02em | 1.2 | Section titles |
| `h3` | 14px | 600 | -0.01em | 1.3 | Subsection titles |
| `h4` | 13px | 600 | 0 | 1.35 | Card titles, label headings |
| `body-l` | 15px | 400 | 0 | 1.6 | Long-form content |
| `body-m` | 14px | 400 | 0 | 1.55 | Standard body text |
| `body-s` | 13px | 400 | 0 | 1.5 | Secondary body text, UI text |
| `caption` | 12px | 500 | +0.02em | 1.4 | Timestamps, metadata |
| `overline` | 11px | 500 | +0.06em | 1.4 | Section labels (UPPERCASE) |
| `label` | 10px | 500 | +0.06em | 1.4 | KPI labels, table headers |
| `code` | 14px | 400 | 0 | 1.6 | Code blocks (JetBrains Mono) |

### Typography Rules

- All headings: `font-family: var(--font-display)` with `font-weight: 600`
- Body text: `font-family: var(--font-body)` with `font-weight: 400`
- Section labels / overlines: uppercase, `letter-spacing: 0.06em`, `font-weight: 500`
- Code: `font-family: var(--font-mono)`
- Max body text width: `560px`
- Headings use negative letter-spacing (tighter), body uses default or positive
- `-webkit-font-smoothing: antialiased` on body

---

## 4. Logo — The Locus

### SVG Mark (canonical source)

```svg
<svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
  <circle cx="24" cy="24" r="3.5" fill="currentColor"/>
  <path d="M 40.17,18.75 A 17,17 0 1 1 11.37,35.38" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/>
  <path d="M 7.83,29.25 A 17,17 0 0 1 36.63,12.62" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/>
</svg>
```

### Logo Anatomy

- **Center dot**: `circle cx="24" cy="24" r="3.5"` filled with `currentColor`
- **Arc A (large)**: Broken circle, sweeps ~270° from upper-right to lower-left
- **Arc B (small)**: Fills the gap, sweeps ~90° from lower-left to upper-right
- **Break axis**: 60°/240° diagonal — creates tension suggesting non-Cartesian geometry
- **Stroke**: width `2`, linecap `round`, fill `none`
- **Color**: Uses `currentColor` — inherits from parent element

### Lockup Formats

**Primary Lockup** (symbol LEFT of text, horizontal):
```html
<div style="display:flex;align-items:center;gap:20px;">
  <svg width="40" height="40" viewBox="0 0 48 48"><!-- Locus SVG --></svg>
  <span style="font-family:var(--font-display);font-size:22px;font-weight:500;letter-spacing:-0.01em;">deep&nbsp; presence</span>
</div>
```

**Compact Lockup** (for nav/headers):
```html
<div style="display:flex;align-items:center;gap:7px;">
  <svg width="16" height="16" viewBox="0 0 48 48"><!-- Locus SVG --></svg>
  <span style="font-family:var(--font-display);font-size:12px;font-weight:600;">deep presence</span>
</div>
```

**Wordmark**: `deep  presence` (two spaces between words)
**Font**: Space Grotesk, 500 weight, letter-spacing -0.01em
**Case**: All lowercase

### Lockup Rules

- Symbol is ALWAYS to the LEFT of text. Never above, never centered, never right.
- Dark background: text color `#EDEDED`
- Light background: text color `var(--text-primary)`

### Favicon

- Background: `#20536C` (deep verdigris) for light theme, `#161618` for dark theme
- Icon: white (#FFFFFF) for light, `#5BA4C4` for dark, stroke-width `2.5`
- Container: 32x32px, border-radius 6px

### Clearspace

- Minimum clearspace on all sides = **0.5x** the height of the symbol
- Minimum digital size: Symbol 24px, Lockup 120px wide, Wordmark 80px wide

---

## 5. Color System

### Grayscale Architecture

- **Light mode** uses Slate-tinted grays (Radix Slate scale): `#FBFCFD` → `#F8F9FA` → `#ECEEF0` → `#D7DBDF` → `#889096` → `#11181C`
- **Dark mode** uses pure neutral grays (Radix Gray scale): `#171717` → `#1F1F1F` → `#2E2E2E` → `#3E3E3E` → `#707070` → `#EDEDED`
- This is the Supabase pattern: Slate for light (slight blue tint for warmth), pure Gray for dark (no tint)

### Color Pairing Rules (WCAG)

| Foreground | Background | Ratio | Level |
|-----------|-----------|-------|-------|
| `#11181C` | `#F8F9FA` | 17.4:1 | AAA |
| `#EDEDED` | `#171717` | 15.9:1 | AAA |
| `#FFFFFF` | `#5BA4C4` | 3.0:1 | AA (large) |
| `#687076` | `#F8F9FA` | 5.1:1 | AA |
| `#A0A0A0` | `#171717` | 7.6:1 | AAA |

### Gradient System (marketing only — NEVER in product UI)

```css
/* Depth — accent dark to accent light */
background: linear-gradient(135deg, #4A93B3 0%, #6CB8D2 100%);

/* Abyss — dark base to accent */
background: linear-gradient(135deg, #171717 0%, #5BA4C4 100%);

/* Signal — accent to accent light */
background: linear-gradient(135deg, #5BA4C4 0%, #6CB8D2 100%);
```

### Color Usage Rules

- `--accent` (#5BA4C4 light / #6CB8D2 dark) is the primary interactive color
- `--text-primary` for headings and important text
- `--text-secondary` for body text and descriptions
- `--text-tertiary` for metadata, timestamps, labels
- Semantic colors (`--success`, `--warning`, `--error`) ONLY for status indication
- `--surface` for panel/card backgrounds
- `--surface-raised` for elevated containers (dropdowns, modals)
- Never use raw hex values in code — always use `var(--token)`
- Gradients are for marketing/editorial ONLY, never product UI

---

## 6. Spacing

Base unit: **4px**

| Token | Value | Common usage |
|-------|-------|------|
| `--space-1` | 4px | Tight gaps, icon padding |
| `--space-2` | 8px | Button icon gap, compact list items |
| `--space-3` | 12px | Form field gaps, card padding |
| `--space-4` | 16px | Standard gaps, grid gutters |
| `--space-6` | 24px | Section internal padding |
| `--space-8` | 32px | Subsection gaps |
| `--space-10` | 40px | Section padding |
| `--space-12` | 48px | Page margins |
| `--space-16` | 64px | Section vertical spacing |
| `--space-20` | 80px | Large section spacing |

### Grid System

- **Max width**: 1120px
- **Columns**: 12
- **Gutter**: 16px
- **Page margin**: 32px (12px on mobile)
- Common column spans: 3 (quarter), 4 (third), 6 (half), 12 (full)

---

## 7. Components

### General Rule: Visible Borders in Both Modes

All cards and containers use `1px solid var(--border)` borders in both light and dark mode:
```css
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  transition: border-color 0.15s ease-out;
}
.card:hover { border-color: var(--border-strong); }
```

### Buttons

```css
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 30px;
  padding: 0 12px;
  border-radius: var(--radius-sm); /* 4px */
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.12s ease-out;
  border: none;
}
```

| Variant | Background | Text | Border |
|---------|-----------|------|--------|
| Primary | `var(--accent)` | `var(--text-on-accent)` | none |
| Secondary | transparent | `var(--text-primary)` | `1px solid var(--border)` |
| Ghost | transparent | `var(--text-secondary)` | none |
| Destructive | `var(--error)` | `#FFFFFF` | none |

| Size | Height | Padding | Font-size |
|------|--------|---------|-----------|
| Small | 26px | 0 8px | 11px |
| Default | 30px | 0 12px | 12px |
| Large | 34px | 0 16px | 13px |

Hover states:
- Primary: `background: var(--accent-hover)`
- Secondary: `border-color: var(--border-strong); background: var(--surface)`
- Ghost: `background: var(--surface); color: var(--text-primary)`

### Inputs

```css
input {
  height: 30px;
  padding: 0 8px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--surface);
  font-family: var(--font-body);
  font-size: 12px;
  color: var(--text-primary);
  outline: none;
  transition: border-color 0.12s ease-out;
}
input:hover { border-color: var(--border-strong); }
input:focus {
  border-color: var(--accent);
  border-width: 2px;
  background: var(--surface-raised);
  box-shadow: 0 0 0 3px var(--accent-subtle);
}
input::placeholder { color: var(--text-tertiary); }
```

### Cards

```css
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px;
  transition: border-color 0.15s ease-out;
}
.card:hover { border-color: var(--border-strong); }
```

Card states:
- **Default**: bordered in both modes
- **Selected**: `border-color: var(--accent)`, `background: var(--accent-subtle)`
- **Empty**: `border-style: dashed`

### KPI / Metric Card

```html
<div class="card">
  <p class="overline">LABEL TEXT</p>     <!-- 9-10px, 500, uppercase, 0.06em, --text-tertiary -->
  <div style="display:flex;align-items:baseline;gap:6px;">
    <p class="metric">84.2%</p>           <!-- font-display, 20px, 600, -0.02em -->
    <p class="delta positive">+12.4%</p>  <!-- 10px, 500, --success or --error -->
  </div>
</div>
```

For KPI rows (like dashboard):
```css
.kpi-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 1fr;
  gap: 1px;
  background: var(--border); /* creates hairline separators */
  border-radius: var(--radius-sm);
  overflow: hidden;
}
.kpi-row > .kpi-cell { background: var(--bg); padding: 10px 12px; }
```

### Badges / Status Tags

```css
.badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 1px 6px;
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: 500;
}
```

| Status | Background | Text |
|--------|-----------|------|
| Success / Cited | `var(--success-subtle)` | `var(--success)` |
| Warning / At risk | `var(--warning-subtle)` | `var(--warning)` |
| Error / Not cited | `var(--error-subtle)` | `var(--error)` |
| Info / Tracking | `var(--info-subtle)` | `var(--info)` |
| Neutral / Draft | `var(--surface)` | `var(--text-secondary)` |

### Toggle Switch

```css
.toggle-track {
  width: 36px; height: 20px; border-radius: 10px;
  background: var(--border); /* off state */
  position: relative; cursor: pointer;
  transition: background 0.2s;
}
.toggle-track.active { background: var(--accent); }
.toggle-thumb {
  width: 16px; height: 16px; border-radius: 50%;
  background: white; position: absolute; top: 2px; left: 2px;
  transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  box-shadow: 0 1px 3px rgba(0,0,0,0.15);
}
.toggle-track.active .toggle-thumb { transform: translateX(16px); }
```

### Progress Bar

```css
.progress-track {
  width: 100%; height: 6px;
  background: var(--surface);
  border-radius: 3px; overflow: hidden;
}
.progress-fill {
  height: 100%; border-radius: 3px;
  background: var(--accent);
  transition: width 0.6s cubic-bezier(0.16, 1, 0.3, 1);
}
```

### Tooltip

```css
.tooltip {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 50%; transform: translateX(-50%);
  background: rgba(17,24,28,0.92);
  backdrop-filter: blur(8px);
  color: #EDEDED;
  padding: 6px 12px;
  border-radius: var(--radius-md);
  font-size: 12px; font-weight: 500;
  white-space: nowrap;
  box-shadow: var(--shadow-float);
}
```

### Toast

```css
.toast {
  display: flex; align-items: flex-start; gap: 8px;
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--surface);
  box-shadow: var(--shadow-float);
  max-width: 320px;
}
.toast-success { border-color: var(--success); }
.toast-error { border-color: var(--error); }
```

### Avatar

```css
.avatar {
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: 50%;
  font-weight: 600;
  font-family: var(--font-display);
  background: var(--accent-subtle);
  color: var(--accent);
}
```

| Size | Dimensions | Font-size |
|------|-----------|-----------|
| Small | 22x22px | 8px |
| Medium | 30x30px | 11px |
| Large | 40x40px | 14px |

### Skeleton Loader

```css
.skeleton {
  background: linear-gradient(90deg, var(--surface) 25%, var(--border-subtle) 50%, var(--surface) 75%);
  background-size: 800px 100%;
  animation: shimmer 1.5s infinite linear;
  border-radius: var(--radius-sm);
}
@keyframes shimmer {
  0% { background-position: -400px 0; }
  100% { background-position: 400px 0; }
}
```

### Data Table

```css
table { width: 100%; border-collapse: collapse; }
th {
  font-size: 10px; font-weight: 500;
  letter-spacing: 0.06em; text-transform: uppercase;
  color: var(--text-tertiary); text-align: left;
  padding: 6px 10px;
  border-bottom: 1px solid var(--border);
  background: transparent;
}
td {
  padding: 6px 10px;
  border-bottom: 1px solid var(--border-subtle);
  font-size: 12px;
}
tr:hover td { background: var(--accent-subtle); }
```

### Slide Drawer (50% Viewport)

Used by 5 pages (Citation Intel, Competitive Position, Prompt Tracking, Content Performance, Technical Readiness) for row-detail panels. Import from `@/components/ui`.

```
- Width: 50vw (customizable via `width` prop)
- Slides from right via Framer Motion (x: 100% → 0, 250ms, ease [0.32, 0.72, 0, 1])
- Overlay: bg-black/20 (content stays visible but dimmed)
- Background: var(--surface)
- Left border: 1px solid var(--border)
- Shadow: var(--shadow-float) — the ONE place shadows are allowed on panels
- Header padding: 20px 24px (px-6 py-5)
- Content padding: 24px (px-6 py-6), own scroll context
- Close button: 30px, ghost variant, top-right
- Escape key closes drawer
- Body scroll locked while open
- Drawer title: 16px, font-weight 600
- Drawer subtitle: 13px, text-secondary
```

### Date Range Picker

Calendar-based date range selector for all analytics page filter bars. Import from `@/components/ui`. Built with react-day-picker v9 + date-fns v4.

```
- Trigger: 32px height, border-border, Calendar icon + display text + clear (X) / chevron
- Active trigger: border-accent, bg-accent-subtle
- Popover: bg-surface-raised, border-border, shadow-float
- Left sidebar: presets list (Last 7d, 30d, 90d, This month, This quarter)
- Right panel: two-month DayPicker calendar side by side
- Selected range: bg-accent text-on-accent (start/end), bg-accent-subtle (middle)
- Preset labels: 10px uppercase tracking-[0.06em] text-tertiary header
- Calendar weekday headers: 10px uppercase tracking-[0.04em] text-tertiary
- Day cells: 12px, 36x36px hit area
- Today: font-semibold
- Close: click outside or Escape
```

### Brand Logo

Real favicon fetcher for external brand/platform logos. Import from `@/components/ui`. Used everywhere a brand name appears.

```
- Primary source: Google Favicon API (https://www.google.com/s2/favicons?domain={domain}&sz={size*2})
- Fallback 1: Clearbit (https://logo.clearbit.com/{domain})
- Fallback 2: Logo.dev (https://img.logo.dev/{domain})
- Last resort: text initials in bg-accent-subtle circle (ONLY if all APIs fail)
- Size: 20px default, renders at 2x for retina
- Border-radius: var(--radius-sm) (4px)
- Loading: lazy
- DO NOT use crossOrigin="anonymous" — causes CORS failures
```

---

## 8. Product UI Patterns

### Dashboard Layout

```
┌────────────┬───────────────────────────────────────┐
│            │  Top bar (13px title + search)        │
│  Sidebar   ├───────┬───────┬───────┬──────────────┤
│  (200px)   │  KPI  │  KPI  │  KPI  │    KPI       │
│            ├───────┴───────┴───────┴──────────────┤
│  11px nav  │  Area Chart (SVG, 180px height)      │
│  items     ├──────────────────────────────────────┤
│            │  Dense table with inline sparklines  │
└────────────┴──────────────────────────────────────┘
```

- Sidebar: `width: 200px; background: var(--surface);` — border between sidebar and main content `border-left: 1px solid var(--border)`
- Nav items: `font-size: 11px; padding: 5px 8px;` — active item gets `background: var(--accent-subtle); color: var(--accent);`
- Top bar: `padding: 8px 16px; border-bottom: 1px solid var(--border);`
- Dashboard outer container: `border: 1px solid var(--border); border-radius: var(--radius-md);`
- KPIs: Use gap-separated cells (see KPI pattern above)
- Main content: `padding: 12px 16px;`

### SVG Area Chart

```html
<svg viewBox="0 0 500 130" preserveAspectRatio="none" style="width:100%;height:calc(100% - 40px);">
  <!-- Grid lines -->
  <line x1="0" y1="0" x2="500" y2="0" stroke="var(--border-subtle)" stroke-width="0.5"/>
  <line x1="0" y1="43.3" x2="500" y2="43.3" stroke="var(--border-subtle)" stroke-width="0.5"/>

  <!-- Area fill with gradient -->
  <defs>
    <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="var(--accent)" stop-opacity="0.15"/>
      <stop offset="100%" stop-color="var(--accent)" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <path d="M0,91 ... L500,130 L0,130Z" fill="url(#areaGrad)"/>
  <path d="M0,91 ..." fill="none" stroke="var(--accent)" stroke-width="1.5"/>

  <!-- Competitor comparison (dashed) -->
  <path d="..." fill="none" stroke="var(--text-tertiary)" stroke-width="1" stroke-dasharray="4 3" opacity="0.5"/>
</svg>
```

### Inline Sparkline Charts

```html
<svg width="60" height="16" viewBox="0 0 60 16">
  <polyline points="0,14 8,13 16,12 24,10 32,8 40,6 48,4 56,2 60,1"
    fill="none" stroke="var(--accent)" stroke-width="1.2" stroke-linecap="round"/>
</svg>
```

- Upward: `stroke="var(--success)"`, Downward: `stroke="var(--error)"`, Flat: `stroke="var(--text-tertiary)"`

### Queries List View (Dense Rows)

```css
.query-row {
  display: flex;
  align-items: center;
  padding: 6px 12px;
  border-bottom: 1px solid var(--border-subtle);
  cursor: pointer;
  transition: background 0.1s;
}
.query-row:hover { background: var(--surface); }
```

### Kanban Board

```css
.board { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 10px; }
.board-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 10px;
}
.board-card:hover { border-color: var(--border-strong); }
```

Column dot colors: Draft = `--text-tertiary`, Scoring = `--accent`, Optimizing = `--warning`, Published = `--success`

---

## 9. Motion

### Timing Reference

| Interaction | Duration | Easing |
|-------------|----------|--------|
| Button hover | 120ms | ease-out |
| Button press | 60ms | ease-in |
| Dropdown open | 200ms | cubic-bezier(0.16, 1, 0.3, 1) |
| Dropdown close | 150ms | cubic-bezier(0.7, 0, 0.84, 0) |
| Modal open | 300ms | cubic-bezier(0.16, 1, 0.3, 1) |
| Tooltip show | 150ms delay + 100ms | ease-out |
| Chart first draw | 300ms fade-in | ease-out |
| Row hover | 100ms | ease-out |
| Border color | 150ms | ease-out |

### Micro-Interaction Patterns

**Card/button hover**: `border-color: var(--border-strong)` — border darkens on hover
**Input focus ring**: `border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-subtle);`

---

## 10. Patterns

### Pattern A — Coordinate Linework

Repeated broken-circle motif. Editorial/blog headers.

### Pattern B — Embedding Field

Scattered dots connected by proximity lines. Generated via JavaScript.
- 50 random dots, connection threshold 120px
- Accent cluster: 4 dots near center, color `var(--accent)`

### Pattern C — Grid Overlay (Dot Grid)

```css
background-image: radial-gradient(circle, var(--text-tertiary) 0.5px, transparent 0.5px);
background-size: 24px 24px;
opacity: 0.15;
```

---

## 11. Iconography

| Property | Value |
|----------|-------|
| Grid | 24 x 24px (13px for sidebar) |
| Stroke width | 1.5px |
| Stroke cap | Round |
| Color | `currentColor` |
| Fill | `none` (stroke only) |

---

## 12. Photography & Imagery

```css
.brand-photo { filter: saturate(0.3) contrast(1.1); }
.brand-photo-overlay::after {
  content: '';
  position: absolute; inset: 0;
  background: rgba(91, 164, 196, 0.12);
  mix-blend-mode: multiply;
}
```

- **Preferred**: Abstract, geometric, data visualizations, topographic
- **Avoid**: Generic stock photos, AI-generated faces

---

## 13. Brand Voice & Copy

### Taglines (approved)

| # | Tagline | Context |
|---|---------|---------|
| 01 | See where you stand. | Primary |
| 02 | Measure the invisible. | Campaigns |
| 03 | Presence is measurable. | Investor |
| 04 | The geometry of being found. | Editorial |
| 05 | Know before you publish. | Product |
| 06 | Your position in the answer. | Explainer |
| 07 | Where citations begin. | About |
| 08 | Clarity before the click. | Ads |
| 09 | Depth over volume. | Content |
| 10 | Built for the answer layer. | Developer |

### Brand Adjectives

**Use**: Precise, Calm, Considered, Authoritative, Deep, Measured
**Never**: Flashy, Aggressive, Trendy, Playful, Busy, Loud

---

## 14. Do's and Don'ts

### DO

- Use CSS custom properties for all colors, spacing, radii
- Use Space Grotesk for everything except code
- Use visible `1px solid var(--border)` borders on all cards and containers
- Use `--border-strong` on hover for interactive elements
- Keep everything dense (30px buttons, 6px table padding, 10px label fonts)
- Use Slate-tinted grays (#F8F9FA, #ECEEF0) in light mode
- Use pure neutral grays (#171717, #2E2E2E) in dark mode
- Use inline SVG for charts (area charts, sparklines, scatter plots)
- Place logo symbol to the LEFT of wordmark text

### DON'T

- Hardcode hex color values — always use `var(--token)`
- Use shadows for visual hierarchy (except `--shadow-float` for floating elements)
- Use gradients in product UI (marketing only)
- Mix font families (only Space Grotesk + JetBrains Mono)
- Use decorative elements that don't serve a purpose
- Make text bolder than 600 weight
- Use rounded corners larger than 12px (except pills at 9999px)
- Stack the logo symbol above the wordmark text
- Use stock photography or AI-generated imagery
- Use rgba for borders — use solid hex values from the token system
- Use blue-tinted grays in dark mode (dark mode is pure neutral gray)

---

## 15. Marketing Asset Kit

### Poster Templates

Six poster variants are defined:

| # | Name | Background | Text Color | Notes |
|---|------|------------|------------|-------|
| 1 | The Statement | `var(--surface)` (light) | `var(--text-primary)` | Large headline, Locus mark + wordmark footer |
| 2 | Dark | `#171717` | `#EDEDED` | Dark background, muted `#707070` footer |
| 3 | Accent | `#5BA4C4` | `#F8F9FA` | Solid accent bg, white text, `rgba(255,255,255,0.4)` footer |
| 4 | Signal Amber | `#171717` | `#DC7B18` (headline) | Dark bg, amber accent headline, editorial feel |
| 5 | Data | `var(--surface)` | `var(--text-primary)` | Bar chart visualization + headline |
| 6 | Split Comparison | `var(--surface)` | `var(--text-primary)` | Before/After split layout with center divider |

**Poster structure:**
```
┌─────────────────────┐
│ [Brand mark / label] │  ← top: logo or overline
│                     │
│                     │
│  Headline text      │  ← bottom-aligned, Space Grotesk 500
│  28-32px            │
│                     │
│ logo    domain.com  │  ← footer: logo left, URL right
└─────────────────────┘
```

- Aspect ratio: ~3:4 (portrait)
- Footer: `font-size: 10px`, `font-weight: 500`
- All posters include Locus inline SVG mark at footer

### Hero Headlines

Two variants — light and dark:

| Variant | Background | Headline Color | Subhead Color | Button |
|---------|-----------|----------------|---------------|--------|
| Light | `var(--surface)` | `var(--text-primary)` | `var(--text-secondary)` | `.btn-primary` default |
| Dark | `#171717` | `#EDEDED` | `#A0A0A0` | `background: #6CB8D2; color: #171717` |

- Headline: `font-size: 40px; font-weight: 500; letter-spacing: -0.02em; line-height: 1.1`
- Subhead: `font-size: 16px; line-height: 1.5`
- Max-width for subhead: `480px`

### Social Templates

**Quote Card (Light):**
- Background: `var(--surface)`, border: `1px solid var(--border)`
- Quote: `font-size: 22px; font-weight: 500; letter-spacing: -0.01em`
- Source: `font-size: 12px; color: var(--text-tertiary)`
- Footer: Locus mark + "deep presence" left, URL right

**Metric Card (Dark):**
- Background: `#171717`, border: `1px solid #2E2E2E`
- Overline: `font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; color: #707070`
- Metric: `font-size: 56px; font-weight: 500; color: #EDEDED; letter-spacing: -0.03em`
- Description: `font-size: 14px; color: #A0A0A0`

Both cards: aspect-ratio `1.91/1` (Twitter/OG card ratio), padding `32px`.

### Business Card

**Front:**
- Background: `var(--surface)`, border: `1px solid var(--border)`
- Top: Locus mark (20px) + "deep  presence" wordmark
- Bottom: Name (`15px; font-weight: 500`), Title (`11px; color: var(--text-tertiary)`), Contact info (`10px; color: var(--text-secondary)`)
- Aspect ratio: `1.75/1`

**Back:**
- Background: `#171717`, border: `1px solid #2E2E2E`
- Centered Locus mark at 48px, fill `#EDEDED`

### Email Header

- Header bar: `background: #171717; padding: 24px 32px`
- Logo: Locus mark (20px) + wordmark in `#EDEDED`
- Right-aligned label: `font-size: 11px; color: #707070`
- Body: standard padding `32px`, white/surface background
- Stats row: Surface background with `var(--radius-sm)`, flex layout with gap `24px`
- Stat labels: `10px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-tertiary)`
- Stat values: `24px; font-weight: 500; font-family: var(--font-display)`
- Max-width: `600px`

### Presentation Slide

- Aspect ratio: `16/9`
- Background: `#171717`, border: `1px solid #2E2E2E`
- Radial gradient overlay: `radial-gradient(ellipse 50% 50% at 80% 50%, rgba(91,164,196,0.2) 0%, transparent 70%)`
- Top-left: Locus mark (16px) + "deep presence" in `#707070`
- Center-bottom: Headline (`32px; font-weight: 500; color: #EDEDED; letter-spacing: -0.02em`)
- Subhead: `14px; color: #A0A0A0; max-width: 400px`
- Footer: `deeppresence.com` left, `Confidential` right, both `10px; color: #707070`

---

## 16. Locus Animation

The Locus mark has a three-stage draw-on animation:

```css
/* Stage 1: Center dot fades in and scales up */
@keyframes locusDotsIn {
  0% { opacity: 0; transform: scale(0); transform-origin: center; }
  100% { opacity: 1; transform: scale(1); transform-origin: center; }
}

/* Stage 2: Arc strokes draw on via stroke-dashoffset */
@keyframes locusArcDraw {
  0% { stroke-dashoffset: 120; opacity: 0.2; }
  10% { opacity: 1; }
  100% { stroke-dashoffset: 0; opacity: 1; }
}

/* Stage 3: Subtle pulse on the center dot */
@keyframes locusPulse {
  0%, 100% { transform: scale(1); transform-origin: center; }
  50% { transform: scale(1.2); transform-origin: center; }
}
```

**Timing:**
- `.locus-dot`: `locusDotsIn 0.5s cubic-bezier(0.16,1,0.3,1) forwards`
- `.locus-arc-1`: `locusArcDraw 0.8s cubic-bezier(0.16,1,0.3,1) 0.3s forwards` + requires `stroke-dasharray: 120; stroke-dashoffset: 120`
- `.locus-arc-2`: same as arc-1 but with `0.5s` delay
- `.locus-dot` after draw: `locusPulse 3s ease-in-out 1.2s infinite`

**Usage:** Add class `.locus-animated` to the SVG to trigger the animation. Remove and re-add the class to replay.

---

## 17. Pattern System (Gradient Mesh)

Pattern D (Radial Gradient Mesh) uses brand-teal gradients for marketing backgrounds:

**Dark variant:**
```css
background: radial-gradient(ellipse 60% 50% at 30% 40%, rgba(91,164,196,0.35) 0%, transparent 70%),
            radial-gradient(ellipse 50% 60% at 70% 60%, rgba(6,182,212,0.25) 0%, transparent 70%),
            radial-gradient(ellipse 40% 40% at 50% 50%, rgba(96,165,250,0.15) 0%, transparent 60%);
```

**Light variant:**
```css
background: radial-gradient(ellipse 60% 50% at 25% 50%, rgba(91,164,196,0.08) 0%, transparent 70%),
            radial-gradient(ellipse 50% 60% at 75% 50%, rgba(6,182,212,0.06) 0%, transparent 70%);
```

**Photography treatment overlay:**
```css
filter: saturate(0.3) contrast(1.1);
/* Plus accent overlay: */
background: rgba(91,164,196,0.12);
```
