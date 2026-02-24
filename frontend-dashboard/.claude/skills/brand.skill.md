# Deep Presence — Brand Specification

> **Every agent MUST read this file and follow it strictly.** This defines the visual identity for the entire application. If tomorrow this file changes, the frontend should update accordingly.

---

## 1. Color System

### Core Palette

```css
:root {
  /* Background */
  --bg-primary: #faf9f5;        /* Anthropic cream — main page background */
  --bg-secondary: #f5f3ee;      /* Slightly darker cream — card hover, subtle sections */
  --bg-tertiary: #efeee8;       /* Used for sidebar, input backgrounds */
  --bg-white: #ffffff;           /* Card backgrounds, elevated surfaces */

  /* Text */
  --text-primary: #141413;       /* Headings, primary content */
  --text-secondary: #4a4840;     /* Body text, descriptions */
  --text-tertiary: #6b6960;      /* Captions, timestamps, muted labels */
  --text-muted: #9a9890;         /* Placeholders, disabled text */
  --text-inverse: #faf9f5;       /* Text on dark/accent backgrounds */

  /* Borders & Dividers */
  --border-default: #e8e6dc;     /* Standard borders */
  --border-subtle: #f0ede6;      /* Very subtle dividers */
  --border-strong: #d4d1c7;      /* Emphasized borders, active states */

  /* Accent: Terracotta (Primary) */
  --accent-primary: #d97757;     /* CTAs, primary actions, links, active states */
  --accent-primary-hover: #c4593a; /* Hover state */
  --accent-primary-light: #fdf3ec; /* Light background for terracotta sections */
  --accent-primary-muted: #f0d5c8; /* Subtle terracotta tint */

  /* Accent: Blue (Secondary) */
  --accent-secondary: #6a9bcc;   /* Intelligence/analysis sections, info states */
  --accent-secondary-hover: #4a7ba8;
  --accent-secondary-light: #edf2f8;
  --accent-secondary-muted: #c5d9ea;

  /* Accent: Green (Tertiary) */
  --accent-tertiary: #788c5d;    /* Success, production/content sections, passing scores */
  --accent-tertiary-hover: #5a6f45;
  --accent-tertiary-light: #eef3ea;
  --accent-tertiary-muted: #c8d4b8;

  /* Semantic Colors */
  --success: #788c5d;            /* Same as tertiary green */
  --warning: #e8926d;            /* Warm orange — thresholds, caution */
  --error: #c44040;              /* Red — failures, rejections */
  --info: #6a9bcc;               /* Same as secondary blue */

  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(20, 20, 19, 0.04);
  --shadow-md: 0 2px 8px rgba(20, 20, 19, 0.06);
  --shadow-lg: 0 4px 16px rgba(20, 20, 19, 0.08);
  --shadow-xl: 0 8px 32px rgba(20, 20, 19, 0.10);

  /* Gray scale (for UI elements, not content) */
  --gray-50: #faf9f7;
  --gray-100: #f5f3ee;
  --gray-200: #efeee8;
  --gray-300: #e8e6dc;
  --gray-400: #d4d1c7;
  --gray-500: #b0aea5;
  --gray-600: #8a8780;
  --gray-700: #6b6960;
  --gray-800: #4a4840;
  --gray-900: #2d2c28;
  --gray-950: #141413;
}
```

### Tailwind Config Extensions

```typescript
// tailwind.config.ts — Agent 0 creates this
const config = {
  theme: {
    extend: {
      colors: {
        cream: {
          50: '#fefdfb',
          100: '#faf9f5',
          200: '#f5f3ee',
          300: '#efeee8',
          400: '#e8e6dc',
          500: '#d4d1c7',
          600: '#b0aea5',
          700: '#8a8780',
          800: '#6b6960',
          900: '#4a4840',
          950: '#141413',
        },
        terracotta: {
          50: '#fdf3ec',
          100: '#f9e2d3',
          200: '#f0d5c8',
          300: '#e8a88a',
          400: '#d97757',
          500: '#c4593a',
          600: '#a84830',
          700: '#8c3a28',
          800: '#6e2e20',
          900: '#4a1f15',
        },
        ocean: {
          50: '#edf2f8',
          100: '#d5e1ef',
          200: '#c5d9ea',
          300: '#9abfdb',
          400: '#6a9bcc',
          500: '#4a7ba8',
          600: '#3a6189',
          700: '#2d4b6a',
          800: '#213750',
          900: '#152435',
        },
        sage: {
          50: '#eef3ea',
          100: '#dce6d3',
          200: '#c8d4b8',
          300: '#a3b88e',
          400: '#788c5d',
          500: '#5a6f45',
          600: '#475838',
          700: '#36432b',
          800: '#262f1e',
          900: '#181e13',
        },
      },
      fontFamily: {
        serif: ['"Source Serif 4"', 'Lora', 'Georgia', 'serif'],
        body: ['Lora', 'Georgia', 'serif'],
        sans: [
          'ui-sans-serif', '-apple-system', 'BlinkMacSystemFont',
          '"Segoe UI"', 'Roboto', '"Helvetica Neue"', 'Arial', 'sans-serif'
        ],
        mono: ['"SF Mono"', '"Fira Code"', '"JetBrains Mono"', 'Consolas', 'monospace'],
      },
      fontSize: {
        'display': ['2.25rem', { lineHeight: '2.5rem', letterSpacing: '-0.025em', fontWeight: '600' }],
        'heading-1': ['1.75rem', { lineHeight: '2.25rem', letterSpacing: '-0.02em', fontWeight: '600' }],
        'heading-2': ['1.375rem', { lineHeight: '1.875rem', letterSpacing: '-0.015em', fontWeight: '600' }],
        'heading-3': ['1.125rem', { lineHeight: '1.625rem', letterSpacing: '-0.01em', fontWeight: '600' }],
        'heading-4': ['0.9375rem', { lineHeight: '1.375rem', fontWeight: '600' }],
        'body-lg': ['0.9375rem', { lineHeight: '1.5rem' }],
        'body': ['0.875rem', { lineHeight: '1.375rem' }],
        'body-sm': ['0.8125rem', { lineHeight: '1.25rem' }],
        'caption': ['0.75rem', { lineHeight: '1.125rem' }],
        'micro': ['0.6875rem', { lineHeight: '1rem' }],
      },
      borderRadius: {
        'sm': '4px',
        'DEFAULT': '6px',
        'md': '8px',
        'lg': '12px',
        'xl': '16px',
      },
      spacing: {
        '4.5': '1.125rem',
        '13': '3.25rem',
        '15': '3.75rem',
        '18': '4.5rem',
      },
    },
  },
};
```

---

## 2. Typography

### Font Stack

| Context | Font | Weight | Usage |
|---------|------|--------|-------|
| **Page titles** | Source Serif 4 | 600 (SemiBold) | H1, page headers, display text |
| **Section headings** | Source Serif 4 | 500–600 | H2, H3, card titles |
| **Body text** | Lora | 400 (Regular) | Paragraphs, descriptions, content |
| **Body emphasis** | Lora | 500 (Medium) | Bold body, card labels |
| **UI labels** | System sans-serif | 500 | Buttons, nav items, table headers, badges |
| **Data/numbers** | System sans-serif | 400–600 | Metrics, scores, timestamps, table cells |
| **Code/API** | SF Mono / Fira Code | 400 | API tags, code snippets, monospace |

### Font Loading

Download and self-host Source Serif 4 and Lora as WOFF2 files in `public/fonts/`. Use `@font-face` in `globals.css`:

```css
@font-face {
  font-family: 'Source Serif 4';
  src: url('/fonts/SourceSerif4-Regular.woff2') format('woff2');
  font-weight: 400;
  font-style: normal;
  font-display: swap;
}
@font-face {
  font-family: 'Source Serif 4';
  src: url('/fonts/SourceSerif4-Medium.woff2') format('woff2');
  font-weight: 500;
  font-style: normal;
  font-display: swap;
}
@font-face {
  font-family: 'Source Serif 4';
  src: url('/fonts/SourceSerif4-SemiBold.woff2') format('woff2');
  font-weight: 600;
  font-style: normal;
  font-display: swap;
}
@font-face {
  font-family: 'Lora';
  src: url('/fonts/Lora-Regular.woff2') format('woff2');
  font-weight: 400;
  font-style: normal;
  font-display: swap;
}
@font-face {
  font-family: 'Lora';
  src: url('/fonts/Lora-Medium.woff2') format('woff2');
  font-weight: 500;
  font-style: normal;
  font-display: swap;
}
@font-face {
  font-family: 'Lora';
  src: url('/fonts/Lora-SemiBold.woff2') format('woff2');
  font-weight: 600;
  font-style: normal;
  font-display: swap;
}
```

**IMPORTANT:** Use Google Fonts CDN as fallback during development if self-hosting is slow:
```html
<link href="https://fonts.googleapis.com/css2?family=Lora:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,500;8..60,600&display=swap" rel="stylesheet">
```

---

## 3. Component Styling Rules

### Cards

```
- Background: white (#ffffff)
- Border: 1px solid var(--border-default) (#e8e6dc)
- Border radius: 8px (rounded-md)
- Shadow: var(--shadow-sm) default, var(--shadow-md) on hover
- Padding: 16px (p-4) for standard, 20px (p-5) for large
- Accent border: Optional 3px left border in accent color for categorization
```

### Buttons

```
Primary:    bg-terracotta-400, text-white, hover:bg-terracotta-500, rounded-md
Secondary:  bg-white, border border-cream-400, text-cream-900, hover:bg-cream-200, rounded-md
Ghost:      bg-transparent, text-cream-700, hover:bg-cream-200, rounded-md
Danger:     bg-error/10, text-error, hover:bg-error/20, rounded-md
Size sm:    px-3 py-1.5 text-body-sm
Size md:    px-4 py-2 text-body
Size lg:    px-5 py-2.5 text-body-lg
```

### Badges / Tags

```
Default:    bg-cream-300, text-cream-800, px-2 py-0.5, rounded, text-caption, font-sans
Terracotta: bg-terracotta-50, text-terracotta-500, border border-terracotta-200
Blue:       bg-ocean-50, text-ocean-500, border border-ocean-200
Green:      bg-sage-50, text-sage-500, border border-sage-200
Warning:    bg-warning/10, text-warning
Error:      bg-error/10, text-error
```

### Sidebar Navigation

```
- Width: 240px (w-60)
- Background: var(--bg-tertiary) (#efeee8)
- Border-right: 1px solid var(--border-default)
- Nav items: font-sans, text-body-sm, font-medium
- Active item: bg-cream-100, text-terracotta-400, font-semibold
- Hover: bg-cream-200
- Icons: 18px, Lucide React, same color as text
- Section labels: text-micro, uppercase, letter-spacing: 1.5px, text-cream-600
```

### Tables

```
- Header: bg-cream-200, text-cream-800, font-sans, text-caption, font-semibold, uppercase
- Rows: bg-white, hover:bg-cream-100
- Border: 1px solid var(--border-subtle) between rows
- Cell padding: px-4 py-3
- Numbers: font-sans, tabular-nums, text-right
```

### Input Fields

```
- Background: white
- Border: 1px solid var(--border-default), focus:border-terracotta-400
- Border radius: 6px
- Padding: px-3 py-2
- Font: font-body, text-body
- Placeholder: text-cream-600
- Focus ring: ring-2 ring-terracotta-400/20
```

### Score/Metric Display

```
Citability Score:
  - Large display: font-serif, text-display, font-semibold
  - Color coded: 
    - 0-49%:  text-error (#c44040)
    - 50-79%: text-warning (#e8926d)  
    - 80%+:   text-sage-400 (#788c5d)
  - Background: matching light tint
  
SPA Score:
  - Similar treatment with terracotta accent
  
Pipeline Progress:
  - Track: bg-cream-300
  - Fill: bg-terracotta-400 (animated)
  - Completed step: bg-sage-400
```

---

## 4. Layout Principles

### Page Structure

```
┌─────────────────────────────────────────────────┐
│ Top Bar (h-14, border-b)                        │
├──────────┬──────────────────────────────────────┤
│ Sidebar  │ Main Content                          │
│ (w-60)   │ ┌──────────────────────────────────┐ │
│          │ │ Page Header                       │ │
│ Navigation│ │ (title, description, actions)     │ │
│          │ ├──────────────────────────────────┤ │
│          │ │ Content Area                      │ │
│          │ │ (max-w-7xl mx-auto px-6 py-6)    │ │
│          │ │                                   │ │
│          │ └──────────────────────────────────┘ │
└──────────┴──────────────────────────────────────┘
```

### Spacing Scale

```
Section gap:      32px (space-y-8)
Card gap:         16px (gap-4)
Inner card gap:   12px (space-y-3)
Label to content: 8px (space-y-2)
Inline gap:       8px (gap-2)
Tight gap:        4px (gap-1)
```

### Grid System

```
Dashboard widgets:  grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4
Two-column layout:  grid grid-cols-1 lg:grid-cols-3 gap-6 (1/3 + 2/3 split)
Full-width:         max-w-7xl mx-auto
Kanban columns:     flex gap-4 overflow-x-auto (each column min-w-[300px])
```

---

## 5. Interaction Patterns

### Transitions

```css
/* Standard transition for all interactive elements */
transition: all 150ms cubic-bezier(0.4, 0, 0.2, 1);

/* Card hover */
hover: translateY(-1px), shadow-md

/* Button press */
active: scale(0.98)

/* Page transitions */
Use Next.js loading.tsx with skeleton components
```

### Loading States

- Use `Skeleton` component (Agent 0 provides) matching the shape of content
- Pulse animation: `animate-pulse` with cream-300 background
- Never show a blank screen — always show layout + skeletons

### Empty States

- Centered illustration area (use Lucide icon, 48px, text-cream-500)
- Descriptive text in text-cream-700
- CTA button in primary style
- Example: "No gap analysis runs yet. Run your first analysis →"

### Toast Notifications

- Position: bottom-right
- Duration: 4 seconds
- Types: success (sage), error (red), warning (warning orange), info (ocean blue)

---

## 6. Phase Color Mapping

Each platform section has a color identity. Use consistently:

| Section | Primary Color | Light BG | Badge Style |
|---------|--------------|----------|-------------|
| Command Center | `terracotta-400` | `terracotta-50` | Terracotta badge |
| Deep Signal Analysis | `ocean-400` | `ocean-50` | Blue badge |
| Deep Embedding Lab | `ocean-400` | `ocean-50` | Blue badge |
| Content Pipeline | `sage-400` | `sage-50` | Green badge |
| Brand Brain | `terracotta-400` | `terracotta-50` | Terracotta badge |
| Settings | `cream-600` | `cream-200` | Gray badge |

---

## 7. Do NOT

- ❌ Use dark mode or dark backgrounds
- ❌ Use Inter, Roboto, Arial, or generic sans-serif fonts for headings
- ❌ Use purple or neon accent colors
- ❌ Use rounded-full on cards (only on avatars and circular elements)
- ❌ Use gradients on backgrounds (flat, warm, cream tones only)
- ❌ Use shadows heavier than shadow-lg
- ❌ Use pure white (#ffffff) as page background (always cream #faf9f5)
- ❌ Use emoji in navigation or section headers (use Lucide icons instead)
- ❌ Make dense data tables use serif fonts (use font-sans for data-heavy views)
- ❌ Create any component that conflicts with the shared `components/ui/` design system
