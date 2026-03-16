/**
 * Deep Presence — Theme Configuration
 * ════════════════════════════════════
 * SINGLE SOURCE OF TRUTH for all design tokens.
 *
 * This file is derived from brand-system.md.
 * Tailwind config reads from this. CSS custom properties are generated from this.
 * If you want to rebrand, change THIS file — everything else follows.
 *
 * RULES:
 * - Never hardcode hex values, font names, or spacing values in any component.
 * - Always use CSS variables: var(--token-name) or Tailwind classes mapped here.
 * - Both light and dark modes use visible 1px solid borders on cards/containers.
 * - No glassmorphism on cards. Solid backgrounds + borders only.
 * - Dense UI: 30px buttons, 10-11px labels, 6px table cell padding.
 */

// ─── Color Tokens ────────────────────────────────────────────────────────────

export const colors = {
  light: {
    // Backgrounds — Slate-tinted grays (slight blue undertone)
    bg: '#F8F9FA',
    surface: '#FBFCFD',
    surfaceRaised: '#FFFFFF',
    surfaceOverlay: '#FBFCFD',

    // Borders — visible, Slate-based
    border: '#ECEEF0',
    borderSubtle: '#F1F3F5',
    borderStrong: '#D7DBDF',
    borderControl: '#D7DBDF',

    // Text — Slate.12 → Slate.9
    textPrimary: '#11181C',
    textSecondary: '#687076',
    textTertiary: '#889096',
    textOnAccent: '#FFFFFF',

    // Accent — Deep Presence Teal
    accent: '#5BA4C4',
    accentHover: '#4A93B3',
    accentSubtle: 'rgba(91,164,196,0.08)',

    // Semantic
    success: '#34B27B',
    successSubtle: 'rgba(52,178,123,0.08)',
    warning: '#DC7B18',
    warningSubtle: 'rgba(220,123,24,0.08)',
    error: '#E5484D',
    errorSubtle: 'rgba(229,72,77,0.06)',
    info: '#5BA4C4',
    infoSubtle: 'rgba(91,164,196,0.08)',

    // Brand
    deepVerdigris: '#5BA4C4',
    signalAmber: '#DC7B18',
    signalAmberSubtle: 'rgba(220,123,24,0.1)',

    // Shadows
    shadowSm: '0 1px 2px rgba(0,0,0,0.04)',
    shadowMd: '0 2px 4px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.06)',
    shadowLg: '0 4px 8px rgba(0,0,0,0.04), 0 2px 4px rgba(0,0,0,0.06)',
    shadowFloat: '0 8px 30px rgba(0,0,0,0.08), 0 0 0 1px #ECEEF0',
  },

  dark: {
    // Backgrounds — pure neutral grays (NO blue tint)
    bg: '#171717',
    surface: '#1F1F1F',
    surfaceRaised: '#292929',
    surfaceOverlay: '#242424',

    // Borders — pure gray, visible
    border: '#2E2E2E',
    borderSubtle: '#242424',
    borderStrong: '#3E3E3E',
    borderControl: '#3E3E3E',

    // Text
    textPrimary: '#EDEDED',
    textSecondary: '#A0A0A0',
    textTertiary: '#707070',
    textOnAccent: '#FFFFFF',

    // Accent — lighter teal for dark mode
    accent: '#6CB8D2',
    accentHover: '#7CC8E2',
    accentSubtle: 'rgba(108,184,210,0.1)',

    // Semantic
    success: '#3ECF8E',
    successSubtle: 'rgba(62,207,142,0.12)',
    warning: '#FFB224',
    warningSubtle: 'rgba(255,178,36,0.12)',
    error: '#F87171',
    errorSubtle: 'rgba(248,113,113,0.12)',
    info: '#6CB8D2',
    infoSubtle: 'rgba(108,184,210,0.1)',

    // Brand (same hex, dark mode variants)
    deepVerdigris: '#6CB8D2',
    signalAmber: '#FFB224',
    signalAmberSubtle: 'rgba(255,178,36,0.12)',

    // Shadows
    shadowSm: '0 1px 2px rgba(0,0,0,0.2)',
    shadowMd: '0 2px 8px rgba(0,0,0,0.3)',
    shadowLg: '0 4px 16px rgba(0,0,0,0.4)',
    shadowFloat: '0 8px 30px rgba(0,0,0,0.4), 0 0 0 1px #2E2E2E',
  },
} as const;

// ─── Typography ──────────────────────────────────────────────────────────────

export const typography = {
  fonts: {
    display: "'Space Grotesk', sans-serif",
    body: "'Space Grotesk', sans-serif",
    mono: "'JetBrains Mono', monospace",
  },

  // Google Fonts URL — load in <head>
  googleFontsUrl:
    'https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap',

  scale: {
    'display-xl': { size: '42px', weight: 600, letterSpacing: '-0.035em', lineHeight: 1.05 },
    'display-l':  { size: '36px', weight: 600, letterSpacing: '-0.025em', lineHeight: 1.1 },
    h1:           { size: '28px', weight: 600, letterSpacing: '-0.02em',  lineHeight: 1.15 },
    h2:           { size: '20px', weight: 600, letterSpacing: '-0.02em',  lineHeight: 1.2 },
    h3:           { size: '14px', weight: 600, letterSpacing: '-0.01em',  lineHeight: 1.3 },
    h4:           { size: '13px', weight: 600, letterSpacing: '0',        lineHeight: 1.35 },
    'body-l':     { size: '15px', weight: 400, letterSpacing: '0',        lineHeight: 1.6 },
    'body-m':     { size: '14px', weight: 400, letterSpacing: '0',        lineHeight: 1.55 },
    'body-s':     { size: '13px', weight: 400, letterSpacing: '0',        lineHeight: 1.5 },
    caption:      { size: '12px', weight: 500, letterSpacing: '+0.02em',  lineHeight: 1.4 },
    overline:     { size: '11px', weight: 500, letterSpacing: '+0.06em',  lineHeight: 1.4 },
    label:        { size: '10px', weight: 500, letterSpacing: '+0.06em',  lineHeight: 1.4 },
    code:         { size: '14px', weight: 400, letterSpacing: '0',        lineHeight: 1.6 },
  },

  rules: {
    maxBodyWidth: '560px',
    fontSmoothing: '-webkit-font-smoothing: antialiased',
    headingsMaxWeight: 600,
    overlineTransform: 'uppercase',
  },
} as const;

// ─── Spacing ─────────────────────────────────────────────────────────────────

export const spacing = {
  base: 4, // px — all spacing is multiples of 4
  scale: {
    1:  '4px',
    2:  '8px',
    3:  '12px',
    4:  '16px',
    6:  '24px',
    8:  '32px',
    10: '40px',
    12: '48px',
    16: '64px',
    20: '80px',
  },
} as const;

// ─── Radii ───────────────────────────────────────────────────────────────────

export const radii = {
  sm:   '4px',
  md:   '6px',
  lg:   '8px',
  xl:   '12px',
  full: '9999px',
} as const;

// ─── Grid ────────────────────────────────────────────────────────────────────

export const grid = {
  maxWidth: '1120px',
  columns: 12,
  gutter: '16px',
  pageMargin: '32px',
  pageMarginMobile: '12px',
} as const;

// ─── Component Tokens ────────────────────────────────────────────────────────

export const components = {
  button: {
    small:   { height: '26px', padding: '0 8px',  fontSize: '11px' },
    default: { height: '30px', padding: '0 12px', fontSize: '12px' },
    large:   { height: '34px', padding: '0 16px', fontSize: '13px' },
  },

  input: {
    height: '30px',
    padding: '0 8px',
    fontSize: '12px',
  },

  card: {
    padding: '14px',
    border: '1px solid var(--border)',
    hoverBorder: 'var(--border-strong)',
  },

  badge: {
    padding: '1px 6px',
    fontSize: '10px',
    fontWeight: 500,
    borderRadius: '9999px',
  },

  table: {
    headerFontSize: '10px',
    headerLetterSpacing: '0.06em',
    headerTextTransform: 'uppercase',
    cellPadding: '6px 10px',
    cellFontSize: '12px',
  },

  sidebar: {
    width: '200px',
    collapsedWidth: '52px',
    navItemFontSize: '11px',
    navItemPadding: '5px 8px',
  },

  topBar: {
    padding: '8px 16px',
  },

  avatar: {
    small:  { size: '22px', fontSize: '8px' },
    medium: { size: '30px', fontSize: '11px' },
    large:  { size: '40px', fontSize: '14px' },
  },

  tooltip: {
    background: 'rgba(17,24,28,0.92)',
    backdropFilter: 'blur(8px)',
    color: '#EDEDED',
    padding: '6px 12px',
    fontSize: '12px',
    fontWeight: 500,
  },

  skeleton: {
    backgroundSize: '800px 100%',
    animationDuration: '1.5s',
  },

  kpiRow: {
    gap: '1px', // creates hairline separators via background color
    cellPadding: '10px 12px',
  },

  toggle: {
    width: '36px',
    height: '20px',
    thumbSize: '16px',
  },

  progressBar: {
    height: '6px',
  },
} as const;

// ─── Motion ──────────────────────────────────────────────────────────────────

export const motion = {
  buttonHover:   { duration: '120ms', easing: 'ease-out' },
  buttonPress:   { duration: '60ms',  easing: 'ease-in' },
  dropdownOpen:  { duration: '200ms', easing: 'cubic-bezier(0.16, 1, 0.3, 1)' },
  dropdownClose: { duration: '150ms', easing: 'cubic-bezier(0.7, 0, 0.84, 0)' },
  modalOpen:     { duration: '300ms', easing: 'cubic-bezier(0.16, 1, 0.3, 1)' },
  tooltipShow:   { duration: '100ms', delay: '150ms', easing: 'ease-out' },
  chartDraw:     { duration: '300ms', easing: 'ease-out' },
  rowHover:      { duration: '100ms', easing: 'ease-out' },
  borderColor:   { duration: '150ms', easing: 'ease-out' },
} as const;

// ─── Locus Logo ──────────────────────────────────────────────────────────────

export const logo = {
  svg: `<svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
  <circle cx="24" cy="24" r="3.5" fill="currentColor"/>
  <path d="M 40.17,18.75 A 17,17 0 1 1 11.37,35.38" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/>
  <path d="M 7.83,29.25 A 17,17 0 0 1 36.63,12.62" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/>
</svg>`,

  wordmark: {
    text: 'deep\u00A0\u00A0presence', // two non-breaking spaces between words
    fontFamily: 'var(--font-display)',
    fontWeight: 500,
    letterSpacing: '-0.01em',
    textTransform: 'lowercase' as const,
  },

  lockup: {
    primary: { symbolSize: 40, fontSize: '22px', gap: '20px' },
    compact: { symbolSize: 16, fontSize: '12px', gap: '7px', fontWeight: 600 },
  },

  favicon: {
    light: { bg: '#20536C', icon: '#FFFFFF' },
    dark:  { bg: '#161618', icon: '#5BA4C4' },
    size: '32px',
    borderRadius: '6px',
    strokeWidth: 2.5,
  },

  animation: {
    dotIn:    { duration: '0.5s', easing: 'cubic-bezier(0.16, 1, 0.3, 1)' },
    arc1Draw: { duration: '0.8s', easing: 'cubic-bezier(0.16, 1, 0.3, 1)', delay: '0.3s' },
    arc2Draw: { duration: '0.8s', easing: 'cubic-bezier(0.16, 1, 0.3, 1)', delay: '0.5s' },
    pulse:    { duration: '3s',   easing: 'ease-in-out', delay: '1.2s', iterations: 'infinite' },
  },
} as const;

// ─── Iconography ─────────────────────────────────────────────────────────────

export const icons = {
  grid: '24px',
  sidebarGrid: '13px',
  strokeWidth: 1.5,
  strokeLinecap: 'round' as const,
  fill: 'none' as const,
} as const;

// ─── Patterns (Marketing) ────────────────────────────────────────────────────

export const patterns = {
  gradientMesh: {
    dark: `radial-gradient(ellipse 60% 50% at 30% 40%, rgba(91,164,196,0.35) 0%, transparent 70%),
           radial-gradient(ellipse 50% 60% at 70% 60%, rgba(6,182,212,0.25) 0%, transparent 70%),
           radial-gradient(ellipse 40% 40% at 50% 50%, rgba(96,165,250,0.15) 0%, transparent 60%)`,
    light: `radial-gradient(ellipse 60% 50% at 25% 50%, rgba(91,164,196,0.08) 0%, transparent 70%),
            radial-gradient(ellipse 50% 60% at 75% 50%, rgba(6,182,212,0.06) 0%, transparent 70%)`,
  },
  dotGrid: {
    image: 'radial-gradient(circle, var(--text-tertiary) 0.5px, transparent 0.5px)',
    size: '24px 24px',
    opacity: 0.15,
  },
  photography: {
    filter: 'saturate(0.3) contrast(1.1)',
    overlay: 'rgba(91,164,196,0.12)',
    blendMode: 'multiply' as const,
  },
} as const;

// ─── Gradients (Marketing ONLY — never in product UI) ────────────────────────

export const gradients = {
  depth:  'linear-gradient(135deg, #4A93B3 0%, #6CB8D2 100%)',
  abyss:  'linear-gradient(135deg, #171717 0%, #5BA4C4 100%)',
  signal: 'linear-gradient(135deg, #5BA4C4 0%, #6CB8D2 100%)',
} as const;

// ─── CSS Variable Generator ──────────────────────────────────────────────────

/**
 * Generates CSS custom property declarations for a given mode.
 * Use in global stylesheet or Tailwind CSS plugin.
 *
 * Usage:
 *   const lightVars = generateCSSVariables('light');
 *   const darkVars = generateCSSVariables('dark');
 */
export function generateCSSVariables(mode: 'light' | 'dark'): Record<string, string> {
  const c = colors[mode];
  return {
    '--bg': c.bg,
    '--surface': c.surface,
    '--surface-raised': c.surfaceRaised,
    '--surface-overlay': c.surfaceOverlay,
    '--border': c.border,
    '--border-subtle': c.borderSubtle,
    '--border-strong': c.borderStrong,
    '--border-control': c.borderControl,
    '--text-primary': c.textPrimary,
    '--text-secondary': c.textSecondary,
    '--text-tertiary': c.textTertiary,
    '--text-on-accent': c.textOnAccent,
    '--accent': c.accent,
    '--accent-hover': c.accentHover,
    '--accent-subtle': c.accentSubtle,
    '--success': c.success,
    '--success-subtle': c.successSubtle,
    '--warning': c.warning,
    '--warning-subtle': c.warningSubtle,
    '--error': c.error,
    '--error-subtle': c.errorSubtle,
    '--info': c.info,
    '--info-subtle': c.infoSubtle,
    '--deep-verdigris': c.deepVerdigris,
    '--signal-amber': c.signalAmber,
    '--shadow-sm': c.shadowSm,
    '--shadow-md': c.shadowMd,
    '--shadow-lg': c.shadowLg,
    '--shadow-float': c.shadowFloat,
    '--font-display': typography.fonts.display,
    '--font-body': typography.fonts.body,
    '--font-mono': typography.fonts.mono,
    '--radius-sm': radii.sm,
    '--radius-md': radii.md,
    '--radius-lg': radii.lg,
    '--radius-xl': radii.xl,
    '--radius-full': radii.full,
    ...Object.fromEntries(
      Object.entries(spacing.scale).map(([k, v]) => [`--space-${k}`, v])
    ),
  };
}

// ─── Tailwind Extend Helper ──────────────────────────────────────────────────

/**
 * Returns an object suitable for spreading into tailwind.config.ts theme.extend.
 * Maps brand tokens into Tailwind utility classes.
 */
export function getTailwindExtend() {
  return {
    colors: {
      bg: 'var(--bg)',
      surface: 'var(--surface)',
      'surface-raised': 'var(--surface-raised)',
      'surface-overlay': 'var(--surface-overlay)',
      border: 'var(--border)',
      'border-subtle': 'var(--border-subtle)',
      'border-strong': 'var(--border-strong)',
      'border-control': 'var(--border-control)',
      'text-primary': 'var(--text-primary)',
      'text-secondary': 'var(--text-secondary)',
      'text-tertiary': 'var(--text-tertiary)',
      'text-on-accent': 'var(--text-on-accent)',
      accent: {
        DEFAULT: 'var(--accent)',
        hover: 'var(--accent-hover)',
        subtle: 'var(--accent-subtle)',
      },
      success: {
        DEFAULT: 'var(--success)',
        subtle: 'var(--success-subtle)',
      },
      warning: {
        DEFAULT: 'var(--warning)',
        subtle: 'var(--warning-subtle)',
      },
      error: {
        DEFAULT: 'var(--error)',
        subtle: 'var(--error-subtle)',
      },
      info: {
        DEFAULT: 'var(--info)',
        subtle: 'var(--info-subtle)',
      },
      'deep-verdigris': 'var(--deep-verdigris)',
      'signal-amber': 'var(--signal-amber)',
    },
    fontFamily: {
      display: ['Space Grotesk', 'sans-serif'],
      body: ['Space Grotesk', 'sans-serif'],
      mono: ['JetBrains Mono', 'monospace'],
    },
    borderRadius: {
      sm: radii.sm,
      md: radii.md,
      lg: radii.lg,
      xl: radii.xl,
      full: radii.full,
    },
    boxShadow: {
      sm: 'var(--shadow-sm)',
      md: 'var(--shadow-md)',
      lg: 'var(--shadow-lg)',
      float: 'var(--shadow-float)',
    },
    spacing: Object.fromEntries(
      Object.entries(spacing.scale).map(([k, v]) => [`sp-${k}`, v])
    ),
    maxWidth: {
      body: typography.rules.maxBodyWidth,
      grid: grid.maxWidth,
    },
  };
}

// ─── Full Theme Export ───────────────────────────────────────────────────────

const theme = {
  colors,
  typography,
  spacing,
  radii,
  grid,
  components,
  motion,
  logo,
  icons,
  patterns,
  gradients,
  generateCSSVariables,
  getTailwindExtend,
} as const;

export default theme;