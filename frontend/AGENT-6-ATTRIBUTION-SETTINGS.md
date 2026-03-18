# Agent 6 — Attribution + Settings

> **Read CLAUDE.md first, then this file.** Runs parallel after Agent 1. Lightest scope — execute cleanly.

## Prerequisites Check

```bash
ls src/components/ui/index.ts && ls src/types/index.ts
npm run dev
```

## Files You Own

```
src/app/(dashboard)/attribution/page.tsx
src/app/(dashboard)/attribution/_components/
src/app/(dashboard)/settings/page.tsx
src/app/(dashboard)/settings/_components/
```

---

## Step 1: Attribution Dashboard — Top Metrics + Banner

**Demo banner** at top:
```tsx
<div className="bg-accent-subtle border border-border rounded-md p-3 mb-4 flex items-center justify-between">
  <span className="text-[12px] text-text-secondary">
    Demo data shown. Connect your CRM and analytics to see real attribution.
  </span>
  <a href="/settings?tab=integrations" className="text-[12px] text-accent hover:underline">
    Connect Integrations →
  </a>
</div>
```

**4 KPI cells:** AI-Sourced Traffic: 12,847 (+34%), Demo Requests: 47 (+18%), Pipeline: $284,000 (+52%), Revenue: $89,400 (+41%).

### ✅ Verify: Banner visible. KPIs show numbers with deltas. Click "Connect Integrations" navigates to settings.

---

## Step 2: Attribution Funnel

6-stage horizontal funnel: Citation Impression (48,200) → AI Click-Through (12,847, 26.7%) → Site Visit (8,419, 65.5%) → Engagement (3,210, 38.1%) → Conversion (186, 5.8%) → Revenue ($89,400, $481/conv).

**Example: Funnel Stage Component**
```tsx
function FunnelStage({ name, count, rate, isLast }: { name: string; count: string; rate?: string; isLast?: boolean }) {
  return (
    <div className="flex items-center">
      <div className="bg-surface border border-border rounded-md p-3 text-center min-w-[120px] hover:border-border-strong transition-[border-color] duration-150">
        <div className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-tertiary mb-1">
          {name}
        </div>
        <div className="font-display text-[20px] font-semibold tracking-[-0.02em] text-text-primary">
          {count}
        </div>
        {rate && (
          <div className="text-[10px] text-text-tertiary mt-1">{rate}</div>
        )}
      </div>
      {!isLast && (
        <div className="mx-2 text-text-tertiary">→</div>
      )}
    </div>
  );
}
```

**Platform filter** above funnel: All | ChatGPT | Claude | Perplexity | Google AI Overview | Gemini. Selecting filters ALL numbers.

Platform demo data:
| Platform | Impressions | Click-Throughs | Revenue |
|----------|-------------|----------------|---------|
| ChatGPT | 18,300 | 4,890 | $34,100 |
| Claude | 9,640 | 2,570 | $17,900 |
| Perplexity | 11,200 | 3,010 | $20,800 |
| Google AI Overview | 6,100 | 1,620 | $11,200 |
| Gemini | 2,960 | 757 | $5,400 |

### ✅ Verify: Funnel renders 6 stages with arrows. Select "ChatGPT" filter — numbers change to ChatGPT-only values. Select "All" — numbers return to totals.

---

## Step 3: Content ROI Table + Charts

**ROI table** (sortable, 7 rows of demo data): Title, Citations, AI Sessions, Conversions, Revenue, CPS Predicted, CPS Actual. Click row → expand with platform breakdown.

**Platform bar chart** (Recharts horizontal bars): Revenue per platform, sorted descending. Colors: ChatGPT=accent, Claude=deep-verdigris, Perplexity=signal-amber, Google=success, Gemini=text-tertiary.

**Trend chart** (Recharts ComposedChart): 3 overlaid series over 12 weeks — AI revenue (area, accent), content published (bars), citations gained (dashed line). Dual y-axes.

**Integration status cards** (3 cards): CRM (Not Connected), Analytics (Not Connected), Attribution Pixel (Not Installed). Each with "Connect →" button.

### ✅ Verify: Table sorts on column click. Bar chart renders. Trend chart shows 12-week data with dual axes. Integration cards show "Not Connected" state.

---

## Step 4: Settings — 5 Tabs

Use `TabBar` or simple tab buttons at top. Store active tab in URL: `/settings?tab=team`.

### Tab: Team
Members table (4 rows of demo data). Role selector dropdown. Invite form (email + role + "Send Invite"). Invite code generator with copyable code display.

### Tab: Models & API Keys
4 rows: Research Agent, Writing Agent, Strategy Agent, Image Generation. Model dropdown per row. API key management: add/remove/mask (show sk-...xxxx).

### Tab: Integrations
3 sections: CMS (WordPress, Webflow, Ghost), CRM (Salesforce, HubSpot), Analytics (GA4, Plausible). Each: logo/icon + name + description + status dot + Connect/Disconnect.

### Tab: Billing
Plan card ("Growth — $499/mo"). 3 usage meters (ProgressBar). Plan comparison table (3 columns: Starter/Growth/Enterprise).

### Tab: Notifications
7-8 event rows with Email toggle + In-App toggle per row. "Save Preferences" button.

### ✅ Verify Before Proceeding

Click through all 5 tabs. Team shows member table. Models shows dropdowns. Integrations shows cards. Billing shows meters. Notifications shows toggles. If tabs reset, check URL param persistence.

---

## Troubleshooting

### Platform Filter Doesn't Update Funnel Numbers
**Symptom:** Selecting a platform does nothing.
**Fix:** Store platform filter in state. Each funnel stage and table must read from filtered data, not raw totals. Use `useMemo` to compute filtered metrics.

### Recharts Chart Renders at 0px Height
**Fix:** Wrap every Recharts chart in `<ResponsiveContainer width="100%" height={300}>`. Without this explicit height, Recharts renders nothing.

### Settings Tab State Lost on Back Navigation
**Fix:** Use URL search params: `const [tab, setTab] = useSearchParams()`. Read tab from URL on mount. Update URL on tab change.

### Table Sort Not Working
**Symptom:** Click column header, nothing happens.
**Fix:** Implement sort state: `const [sortKey, setSortKey] = useState('revenue')` + `const [sortDir, setSortDir] = useState<'asc'|'desc'>('desc')`. Sort data with `useMemo` before rendering rows.

### Toggle Switches Don't Persist
**Fix:** For now, store in local component state. Show toast on "Save Preferences" click. Backend persistence comes later.

### Invite Code Not Copyable
**Fix:** Use `navigator.clipboard.writeText(code)` on click. Show toast "Copied to clipboard". Wrap code in `<code className="font-mono text-[12px] bg-surface border border-border rounded-sm px-2 py-1 select-all">`.

---

## Completion Criteria

- [ ] Attribution: demo banner visible at top
- [ ] Funnel: 6 stages with conversion rates
- [ ] Platform filter changes all numbers
- [ ] ROI table: sortable, 7 rows
- [ ] Bar chart: revenue per platform
- [ ] Trend chart: 12-week overlay with dual y-axes
- [ ] Integration cards: "Not Connected" state
- [ ] Settings: all 5 tabs render
- [ ] Team: member table + invite form
- [ ] Models: dropdowns change selection
- [ ] Integrations: connect/disconnect cards
- [ ] Billing: usage meters fill correctly
- [ ] Notifications: toggles work, Save button shows toast
- [ ] `npx tsc --noEmit` — 0 errors
