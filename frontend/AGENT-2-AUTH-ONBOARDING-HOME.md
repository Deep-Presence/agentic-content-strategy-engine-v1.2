# Agent 2 — Auth + Onboarding + Home

> **Read CLAUDE.md first, then this file.** Runs parallel after Agent 1.

## Prerequisites Check

Before starting, verify Agent 1 is complete:
```bash
ls src/components/ui/index.ts    # Should list file
ls src/types/index.ts            # Should list file
ls src/app/\(dashboard\)/layout.tsx  # Dashboard shell exists
npm run dev                      # Starts without errors
```
If any check fails, Agent 1 isn't done. Wait.

## Files You Own

```
src/app/(auth)/login/page.tsx
src/app/(auth)/register/page.tsx
src/app/(auth)/join/page.tsx
src/app/onboarding/page.tsx
src/app/onboarding/_components/
src/app/(dashboard)/page.tsx              ← Home
src/app/(dashboard)/_components/home/
```

**Never touch:** `src/components/ui/`, `src/lib/`, `src/types/`, `src/stores/`, or any other agent's routes.

---

## Step 1: Auth Pages — Split-Screen Layout

**Layout:** Left (50%) = form on `var(--bg)`. Right (50%) = brand visual.

**Brand visual (right panel):**
- Background: `#171717`
- Gradient mesh: `radial-gradient(ellipse 60% 50% at 30% 40%, rgba(91,164,196,0.35) 0%, transparent 70%), radial-gradient(ellipse 50% 60% at 70% 60%, rgba(6,182,212,0.25) 0%, transparent 70%), radial-gradient(ellipse 40% 40% at 50% 50%, rgba(96,165,250,0.15) 0%, transparent 60%)`
- `<LocusLogo variant="symbol" size={80} animated />` centered
- Tagline below: "See where you stand." — `color: #A0A0A0`, 14px

**Form panel (left):** Compact Locus lockup top-left, form centered vertically.

**`/login`:** Email + Password + "Sign In" button + links to Register and Join.
**`/register`:** Company Name, Website Domain, Full Name, Email, Password + "Create Account" → redirects to `/onboarding`.
**`/join`:** Invite Code → verify → pre-fill company → Full Name, Email, Password → "Join Team" → redirects to `/`.

### Example: Login Form Output

```tsx
<div className="flex min-h-screen">
  {/* Left: Form */}
  <div className="w-1/2 bg-bg flex flex-col justify-center px-16">
    <LocusLogo variant="compact" className="mb-12" />
    <h1 className="font-display text-[28px] font-semibold tracking-[-0.02em] text-text-primary mb-2">
      Sign in
    </h1>
    <p className="text-[13px] text-text-secondary mb-8">
      Enter your credentials to access your workspace.
    </p>
    <div className="space-y-3 max-w-[340px]">
      <Input label="Email" type="email" placeholder="you@company.com" />
      <Input label="Password" type="password" />
      <Button variant="primary" className="w-full mt-4">Sign In</Button>
    </div>
  </div>
  {/* Right: Brand Visual */}
  <div className="w-1/2 relative" style={{ background: '#171717' }}>
    {/* gradient mesh + animated Locus */}
  </div>
</div>
```

### ✅ Verify Before Proceeding

Visit `/login`, `/register`, `/join`. Each should show split-screen with form left, dark brand visual right. Locus should animate on the right panel. If the right panel is blank, check the gradient CSS and LocusLogo import.

---

## Step 2: Onboarding — 4-Screen State Machine

Use `useState` to track active screen (1-4). Framer Motion `AnimatePresence` for transitions.

**Screen 1 — Input:** 4 fields (Company Name pre-filled, Website URL, Industry dropdown, Target Audience textarea) + "Begin Analysis →"

**Screen 2 — Prep Briefing:** 6 deliverable cards stagger-reveal (150ms between each via Framer Motion). Cards: Site Audit, Knowledge Base, Gap Analysis, Topic Discovery, Voice Style Guide, Audience Personas. Each: lucide icon + title + 1-line description + time badge. "Start Pipeline →" button.

**Screen 3 — Pipeline Running:**
- Progress bar 0→100% over ~60 seconds
- Phase chips: 6 phases, active pulses with `var(--accent)`
- Live research feed: scrolling container, simulated events every 1-3 seconds (use `setInterval`). 20+ messages like: "Crawling lovable.dev... 847 pages discovered", "Querying 4 AI platforms across 99 queries...", "Analyzing 1,816 citations..."
- Stats counters animating: Pages 0→847, Citations 0→1816, Topics 0→99, Clusters 0→9
- Section checklist: gold checkmarks appear at ~10s, ~20s, ~35s, ~45s, ~52s, ~58s

**Screen 4 — Complete:**
- Animated Locus logo (large)
- 2×2 metric grid: "AI Presence Score: 38.7/100", "99 queries tracked", "1,816 citations analyzed", "9 content clusters"
- "Enter Home →" → navigates to `/`

### ✅ Verify Before Proceeding

Go to `/onboarding`. Click through all 4 screens. Screen 3 should run for ~60 seconds with visible animations. Stats should count up. Checkmarks should appear in sequence. Screen 4 should show metrics and link to Home. If animations are janky, check Framer Motion imports and `AnimatePresence` mode.

---

## Step 3: Home Command Center

**Active Agent Tasks:** Cards for running content jobs. Click → `/content`.
**HITL Reviews Pending:** "X briefs awaiting review", "X articles awaiting review" with amber badges.
**Outcomes Strip:** 4 KPI cells — Published, Cited, Citations, SOV%.
**Recent Activity Feed:** Timestamped event list.
**Empty State:** If no data → Locus icon + "Welcome to Deep Presence" + "Begin Analysis →" button → `/onboarding`.

### ✅ Verify Before Proceeding

Visit `/`. Should show the Home page with all sections. Empty state should show if onboarding hasn't run. Click "Begin Analysis" — should navigate to `/onboarding`.

---

## Troubleshooting

### Split-Screen Layout Breaks on Mobile
**Fix:** Add responsive breakpoint: `md:w-1/2 w-full`. Hide brand visual panel below md. This is a desktop-first app, but it shouldn't crash on narrow screens.

### Onboarding Timer Doesn't Clear on Unmount
**Symptom:** Console warnings about state updates on unmounted components.
**Fix:** Use `useEffect` cleanup: `return () => { clearInterval(timerRef.current); clearTimeout(timeoutRef.current); }`.

### Form Inputs Don't Match Brand Style
**Symptom:** Default browser input styling showing through.
**Fix:** Ensure you're using the shared `<Input>` component from `@/components/ui`, not native `<input>`. The shared component has all brand tokens built in.

### Framer Motion Page Transitions Flash
**Symptom:** Content flashes white/disappears during screen transitions.
**Fix:** Wrap screens in `AnimatePresence mode="wait"` and ensure each screen has a unique `key` prop. Add `initial`, `animate`, and `exit` props to each screen's motion.div.

### Locus Animation Doesn't Play on Right Panel
**Symptom:** Static Locus logo, no animation.
**Fix:** The right panel uses dark background, so LocusLogo color needs to be set explicitly: `<LocusLogo className="text-[#EDEDED]" animated />`. Without this, `currentColor` inherits the wrong color.

---

## Completion Criteria

- [ ] All 3 auth pages render with correct split-screen layout
- [ ] Brand visual panel shows gradient mesh + animated Locus
- [ ] Register → redirects to `/onboarding`
- [ ] All 4 onboarding screens transition smoothly
- [ ] Pipeline simulation runs ~60 seconds with live feed
- [ ] Stats count up, checkmarks appear in sequence
- [ ] Home page shows all 4 sections
- [ ] Empty state renders when no data
- [ ] Light mode default, dark mode works
- [ ] No hardcoded colors, all cards have borders
- [ ] `npx tsc --noEmit` — 0 errors in your files
