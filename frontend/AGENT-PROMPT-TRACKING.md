# Agent — Prompt Tracking Page (v3 — Production)

> **Read CLAUDE.md and brand-system.md first, then this file.** This builds/rebuilds the `/prompt-tracking` page.

---

## Mission

Build the Prompt Tracking page — the page that answers **"What are people asking AI engines, and am I showing up in the answers?"** This is the bridge between queries and AI engine responses. It follows the AirOps Prompts page pattern: a table of tracked prompts with a multi-level side drawer showing answer history, competitor breakdown, and full AI responses.

This page does NOT map to a fixed metric category. It surfaces data from `platform_results/*.jsonl` — the actual AI engine responses with mention/citation analysis.

---

## Files You Own

```
src/app/(dashboard)/prompt-tracking/page.tsx
src/app/(dashboard)/prompt-tracking/_components/
```

**Never touch** shared UI components, other pages, stores, or layout files.

---

## MANDATORY LAYOUT STANDARDS

### Density & Spacing

```
Page-level horizontal padding: max 24px (1.5rem) — NO max-w-7xl or container wrappers
Section gaps: 16px
Card/container internal padding: 12px-16px
Table row height: 40px (NOT 44-48+)
Table cell padding: 6px vertical, 8px horizontal
```

Replace `p-6`/`p-8`/`gap-6`/`gap-8` with `p-3`/`p-4`/`gap-3`/`gap-4`. Remove `max-w-7xl mx-auto`.

### Font Sizes (non-negotiable)

```
Page title: 22px, font-weight 600, Space Grotesk
Page subtitle: 13px, var(--text-secondary)
Table headers: 11px, uppercase, letter-spacing 0.05em, var(--text-secondary)
Table body text: 13px
Prompt text in table: 13px, font-weight 500
Data values (rates, counts): 13px, JetBrains Mono
Topic badges: 11px
Tag pills: 10px
Delta values: 11px, JetBrains Mono
Drawer section headers: 14px, font-weight 600, uppercase
Drawer body text: 13px
Drawer data values: 13px, JetBrains Mono
Tab labels: 13px
Prompt count footer: 11px, var(--text-secondary)
```

### Global Filter Bar (directly below page title, 0 gap)

Full-width toolbar. No rounded corners. No background. Border-bottom only. Height: 44px.

```tsx
<div className="flex items-center gap-3 px-4 py-2 border-b" style={{ borderColor: 'var(--border)' }}>
  <DateRangePicker /> {/* Mar 20, 2026 – Mar 26, 2026 */}
  <div className="h-4 w-px" style={{ background: 'var(--border)' }} />
  <TopicFilter /> {/* All Topics ▾ */}
  <button className="ml-auto text-xs" style={{ color: 'var(--text-secondary)' }}>× Clear</button>
</div>
```

### Sub-navigation Bar (directly below filter bar, 0 gap)

Second toolbar row — tabs on the left, search + actions on the right. Height: 44px. Also `border-b`.

```tsx
<div className="flex items-center px-4 py-2 border-b" style={{ borderColor: 'var(--border)' }}>
  <div className="flex gap-4">
    <button className={activeTab === 'prompt' ? 'text-sm font-semibold' : 'text-sm'}
            style={activeTab === 'prompt' ? { color: 'var(--text-primary)', borderBottom: '2px solid var(--accent)', paddingBottom: '6px' } : { color: 'var(--text-secondary)' }}>
      Prompt
    </button>
    <button className={activeTab === 'topic' ? 'text-sm font-semibold' : 'text-sm'}
            style={activeTab === 'topic' ? { color: 'var(--text-primary)', borderBottom: '2px solid var(--accent)', paddingBottom: '6px' } : { color: 'var(--text-secondary)' }}>
      Topic
    </button>
  </div>
  <div className="ml-auto flex items-center gap-3">
    <div className="relative">
      <input type="text" placeholder="Search prompts..." className="text-xs px-3 py-1.5 rounded"
             style={{ border: '1px solid var(--border)', background: 'transparent', width: '200px' }} />
    </div>
    <button className="text-xs" style={{ color: 'var(--text-secondary)' }}>✏️ Edit Topics</button>
    <button className="text-xs px-3 py-1.5 rounded" style={{ background: 'var(--accent)', color: 'white' }}>+ Add Prompts</button>
  </div>
</div>
```

---

## Main Table: Prompt List

| Column | Width | Content |
|--------|-------|---------|
| Prompt | 35% | Full prompt text, single line, `text-ellipsis overflow-hidden whitespace-nowrap`, 13px font-weight 500 |
| Topic | 15% | Colored topic badge pill (max-width 200px, ellipsis if long), 11px |
| Tags | 10% | Tag pills (10px, `border: 1px solid var(--border)`, 2px 6px padding), or "—" if empty |
| Fanouts | 8% | Count with icon "↗ 6", JetBrains Mono 13px |
| Volume | 10% | Mini sparkline (56×14px inline SVG), green stroke, no axes |
| Mention Rate | 11% | Percentage + delta on **single line** with 4px gap: `67.9% +7.1%`. Rate: 13px JetBrains Mono. Delta: 11px JetBrains Mono. Positive: `var(--success)` / `#34B27B`. Negative: `var(--error)` / `#E5484D`. Zero: var(--text-secondary), show as `0.0%` |
| Citation Rate | 11% | Same formatting as Mention Rate |

Row height: 40px. Hover: `var(--accent-subtle)`. Cursor: pointer. All rows clickable → opens Level 1 drawer.

Sortable column headers (click to toggle). Default: sort by Mention Rate descending.

Footer below table: "15 of 15 prompts" — 11px var(--text-secondary), left-aligned.

**Mock data — 15 prompts:**

```typescript
const PROMPTS = [
  { id: "p1", text: "Lovable vs Bolt.new comparison", topic: "AI App Builder Evaluation", topicColor: "#5BA4C4", tags: ["branded", "comparison"], queryFanouts: 7, mentionRate: 0.679, mentionDelta: 0.071, citationRate: 0.893, citationDelta: 0.036, volume: [30,32,35,33,38,40,42] },
  { id: "p2", text: "Best AI app builder for startups", topic: "AI App Builder Evaluation", topicColor: "#5BA4C4", tags: ["branded"], queryFanouts: 14, mentionRate: 0.536, mentionDelta: 0.143, citationRate: 0.643, citationDelta: 0.107, volume: [25,28,32,35,38,42,45] },
  { id: "p3", text: "Can AI build a full-stack web application?", topic: "Vibe Coding & Prompt-to-App", topicColor: "#34B27B", tags: [], queryFanouts: 10, mentionRate: 0.464, mentionDelta: 0.107, citationRate: 0.571, citationDelta: 0.071, volume: [35,38,42,40,45,48,50] },
  { id: "p4", text: "AI app builder for non-technical founders", topic: "AI App Builder Evaluation", topicColor: "#5BA4C4", tags: ["persona"], queryFanouts: 8, mentionRate: 0.393, mentionDelta: 0.071, citationRate: 0.500, citationDelta: 0.107, volume: [15,18,20,22,25,28,30] },
  { id: "p5", text: "What is the best AI phone agent for healthcare?", topic: "Clinic & Patient Admin Automation", topicColor: "#DC7B18", tags: [], queryFanouts: 6, mentionRate: 0.333, mentionDelta: -0.131, citationRate: 0.481, citationDelta: -0.090, volume: [20,18,22,19,15,14,12] },
  { id: "p6", text: "How to deploy AI-generated app to production", topic: "Deployment & DevOps", topicColor: "#8B7EC8", tags: [], queryFanouts: 15, mentionRate: 0.321, mentionDelta: 0.071, citationRate: 0.821, citationDelta: 0.143, volume: [18,20,22,25,28,30,32] },
  { id: "p7", text: "Prompt-to-app platform comparison 2026", topic: "AI App Builder Evaluation", topicColor: "#5BA4C4", tags: ["comparison"], queryFanouts: 14, mentionRate: 0.286, mentionDelta: -0.071, citationRate: 0.679, citationDelta: 0.143, volume: [22,25,28,24,30,28,26] },
  { id: "p8", text: "How does an AI phone assistant work for clinics?", topic: "Clinic & Patient Admin Automation", topicColor: "#DC7B18", tags: [], queryFanouts: 6, mentionRate: 0.250, mentionDelta: 0.036, citationRate: 0.821, citationDelta: -0.036, volume: [12,15,18,14,16,20,22] },
  { id: "p9", text: "Can AI answer patient phone calls?", topic: "Clinic & Patient Admin Automation", topicColor: "#DC7B18", tags: [], queryFanouts: 10, mentionRate: 0.214, mentionDelta: -0.036, citationRate: 0.821, citationDelta: -0.036, volume: [8,10,12,15,14,11,9] },
  { id: "p10", text: "What is vibe coding?", topic: "Vibe Coding & Prompt-to-App", topicColor: "#34B27B", tags: ["definition"], queryFanouts: 12, mentionRate: 0.179, mentionDelta: 0.036, citationRate: 0.214, citationDelta: -0.036, volume: [40,45,50,48,55,60,58] },
  { id: "p11", text: "AI app builder with database integration", topic: "Feature Evaluation", topicColor: "#DC7B18", tags: ["feature"], queryFanouts: 9, mentionRate: 0.179, mentionDelta: -0.036, citationRate: 0.214, citationDelta: -0.036, volume: [10,12,14,12,15,13,11] },
  { id: "p12", text: "AI app builder security features", topic: "Security & Compliance", topicColor: "#E5484D", tags: ["security"], queryFanouts: 8, mentionRate: 0.107, mentionDelta: 0.000, citationRate: 0.036, citationDelta: 0.036, volume: [5,6,4,7,8,6,5] },
  { id: "p13", text: "RBAC in AI-generated applications", topic: "Security & Compliance", topicColor: "#E5484D", tags: ["security", "enterprise"], queryFanouts: 6, mentionRate: 0.036, mentionDelta: 0.036, citationRate: 0.000, citationDelta: 0.000, volume: [2,3,2,4,3,2,3] },
  { id: "p14", text: "SOC 2 compliance for AI development platforms", topic: "Security & Compliance", topicColor: "#E5484D", tags: ["enterprise", "compliance"], queryFanouts: 5, mentionRate: 0.000, mentionDelta: 0.000, citationRate: 0.000, citationDelta: 0.000, volume: [1,2,1,2,3,2,1] },
  { id: "p15", text: "Leading AI assistant companies compared", topic: "AI App Builder Evaluation", topicColor: "#5BA4C4", tags: ["comparison"], queryFanouts: 14, mentionRate: 0.000, mentionDelta: 0.000, citationRate: 0.000, citationDelta: 0.000, volume: [8,10,12,11,14,12,10] },
];
```

---

## Side Drawer — Level 1: Prompt Detail (50% viewport width)

Opens on any table row click. Slides from right. Backdrop: `rgba(0,0,0,0.15)`. Close button: top-right, 32px hit target.

**Drawer header:**

```
PROMPT
"What is the best AI phone agent for healthcare?"

Related Keyword: medical answering service software  •  Category Related

[Persona ▾]  [🌐 United States]  [📅 Mar 20 – Mar 26]
```

Prompt text: 16px font-weight 600. Related keyword: 12px var(--text-secondary). Filter pills: 11px, `border: 1px solid var(--border)`, 24px height.

---

### Section A: Mention Rate by Competitor (two-column layout)

**Left column: Position + Brand Leaderboard**

Position indicator: **32px JetBrains Mono, font-weight 700** (e.g., "1st"), colored with var(--accent) if 1st-2nd, var(--text-primary) if 3rd+. Delta below in 12px (e.g., "+1.6%").

Brand leaderboard table:

| Rank | Brand | Mentions | Rate |
|------|-------|----------|------|

```typescript
const COMPETITOR_LEADERBOARD = [
  { rank: 1, domain: "lovable.dev", name: "Lovable", isYou: true, mentions: 6, rate: 0.21, delta: 0.016 },
  { rank: 2, domain: "bolt.new", name: "Bolt.new", isYou: false, mentions: 4, rate: 0.14, delta: -0.005 },
  { rank: 3, domain: "cursor.com", name: "Cursor", isYou: false, mentions: 2, rate: 0.07, delta: 0.001 },
  { rank: 4, domain: "replit.com", name: "Replit", isYou: false, mentions: 1, rate: 0.04, delta: 0.000 },
  { rank: 5, domain: "v0.dev", name: "V0.dev", isYou: false, mentions: 1, rate: 0.04, delta: -0.011 },
];
```

Your row: `background: var(--accent-subtle)`, `[YOU]` badge in teal next to name. Real favicons (16px) for all brands.

**Right column: Mention Rate by Platform**

Vertical stack. Each platform: real favicon (16px) + name (12px) + rate right-aligned (13px JetBrains Mono). Behind each rate, a subtle progress bar (4px height, var(--accent) fill proportional to rate).

```typescript
const PLATFORM_RATES = [
  { platform: "ChatGPT", domain: "openai.com", rate: 0.00 },
  { platform: "Gemini", domain: "gemini.google.com", rate: 0.00 },
  { platform: "Perplexity", domain: "perplexity.ai", rate: 0.00 },
  { platform: "Google AI Mode", domain: "google.com", rate: 0.86 },
  { platform: "Claude", domain: "anthropic.com", rate: 0.14 },
];
```

---

### Section B: Query Fanouts

Section header: "QUERY FANOUTS (6)" — 11px uppercase, var(--text-secondary).

Table with two columns: Query text (12px, var(--text-primary)) | Observations (right-aligned, 12px JetBrains Mono).

```typescript
const QUERY_FANOUTS = [
  { query: "Can AI answer patient phone calls healthcare AI answering", observations: 3 },
  { query: "AI phone answering for patient calls healthcare what solutions", observations: 1 },
  { query: "AI answering phone calls for patients healthcare call handling", observations: 1 },
  { query: "AI answering patient calls medical office virtual assistant", observations: 1 },
  { query: "best AI phone assistant for medical clinics 2026", observations: 2 },
  { query: "automated phone answering service for healthcare providers", observations: 1 },
];
```

---

### Section C: Answer History

Grouped by date with collapsible sections. Date headers: 12px font-weight 600, subtle background (`var(--surface)` or `rgba(0,0,0,0.02)`), collapse/expand chevron on the left.

Within each date, rows:

| Date | Persona | Platform | Answer Preview | Cited | Ment. | Competitors |
|------|---------|----------|----------------|-------|-------|-------------|

- Date: "Mar 26, 2026" (only on date header, not repeated per row)
- Persona: user icon (12px) + "Default" (12px)
- Platform: real favicon (14px) + platform name (12px)
- Answer Preview: 12px, var(--text-secondary), max 1 line, `text-ellipsis overflow-hidden whitespace-nowrap`
- Cited: ✓ (green `#34B27B`) or ✗ (gray `var(--text-secondary)`) — 12px
- Mentioned: same ✓/✗ pattern
- Competitors: 14px favicons stacked horizontally with -2px overlap margin (GitHub contributor avatar style)

Each answer row: `cursor-pointer`, hover `var(--accent-subtle)`. Click → opens Level 2.

**Generate 7 days × 4 platforms = 28 answer rows** with realistic answer preview text:

```typescript
const PLATFORMS = ["ChatGPT", "Claude", "Perplexity", "Google AI Mode"];
const PLATFORM_DOMAINS = { "ChatGPT": "openai.com", "Claude": "anthropic.com", "Perplexity": "perplexity.ai", "Google AI Mode": "google.com" };

const ANSWER_PREVIEWS = [
  "Yes — AI can answer patient phone calls, and this capabilit...",
  "Yes, AI can answer patient phone calls effectively. Platform...",
  "Based on current research, AI phone assistants for clinics h...",
  "Yes, AI can effectively answer patient phone calls. Modern A...",
];

// Generate 7 days (Mar 20-26, 2026), each with 4 platform responses
const generateAnswerHistory = () => {
  const history = [];
  for (let day = 26; day >= 20; day--) {
    const dateStr = `Mar ${day}, 2026`;
    PLATFORMS.forEach((platform, idx) => {
      history.push({
        id: `answer-${day}-${idx}`,
        date: dateStr,
        persona: "Default",
        platform,
        platformDomain: PLATFORM_DOMAINS[platform],
        preview: ANSWER_PREVIEWS[idx],
        cited: Math.random() > 0.4,
        mentioned: Math.random() > 0.3,
        competitors: ["bolt.new", "cursor.com", "replit.com"].slice(0, Math.floor(Math.random() * 3) + 1),
      });
    });
  }
  return history;
};
```

---

## Side Drawer — Level 2: Individual Answer Detail

Replaces Level 1 content in the same drawer. Shows "← Back" link at top (12px, var(--text-secondary), `cursor-pointer`, hover underline).

**Header:**

```
← Back

PROMPT
"Leading AI assistant companies compared"

[● ChatGPT]  [Perplexity]  [Google AI Mode]  [Gemini]    ← platform tabs

🧑 Default  •  🌐 United States  •  📅 Mar 26, 2026
```

Platform tabs: real favicon (14px) + name (12px). Selected tab: accent bottom border (2px `var(--accent)`), font-weight 600. Inactive: no border, var(--text-secondary). Switching tabs shows the answer from that platform for the same prompt/date.

**Brand Status Line:**

```
✅ Lovable is mentioned    ✗ Lovable is not cited
```

13px. ✅ green background-tinted pill, ✗ gray. Prominent placement directly below platform tabs.

**Mentions Section:**

Horizontal list of brand pills. Each pill: `border: 1px solid var(--border)`, 28px height, 11px text, favicon (12px) + brand name. If brand is the tracked brand, add a green ✓ checkmark inside the pill.

```typescript
const MENTIONS = [
  { domain: "lovable.dev", name: "Lovable", checked: true },
  { domain: "heidihealth.com", name: "Heidi Health", checked: false },
];
```

**Citations Section:**

Same pill style as mentions. Shows all URLs cited in this answer, each with domain favicon + domain name.

```typescript
const CITATIONS = [
  "lovable.dev", "lovable.dev", "heidihealth.com", "lovable.dev", "lovable.dev",
  "bookedsolid.com", "flow-lyne.com", "lovable.dev", "clincos.com", "heyheron.com",
  "dialora.com", "facebook.com", "youtube.com", "intouchnow.com", "myaifrontdesk.com",
];
```

**Full Answer Section:**

The complete AI engine response. Rendered in a card: `border: 1px solid var(--border)`, 16px padding.

Text: 13px, `line-height: 1.6`.

**Brand highlighting:** wherever "Lovable" appears in the text:
```css
background: rgba(108, 184, 210, 0.15);
font-weight: 600;
padding: 1px 4px;
border-radius: 2px;
```

Generate ~200 words of realistic AI response text. Example for "Can AI answer patient phone calls?":

```typescript
const MOCK_ANSWER = `Yes, AI can effectively answer patient phone calls. Modern AI assistants like **Lovable** handle a wide range of patient interactions:

Scheduling: Book, reschedule, or cancel appointments
Refills: Process prescription refill requests
Information: Answer FAQs about office hours, locations, providers
Triage: Basic symptom assessment with protocol-based routing

**Lovable** uses a specialized healthcare language model that understands medical terminology and clinic-specific contexts. The platform integrates with 50+ EHR systems and maintains SOC 2 Type II and HIPAA compliance. **Lovable** reports 94% patient satisfaction across its network of 4,000+ clinics.

Other notable platforms in this space include Heidi Health for documentation-focused workflows and MyAIFrontDesk for after-hours coverage. However, **Lovable** remains the most comprehensive solution for end-to-end patient phone management.

Key considerations when choosing an AI phone assistant:
- Integration depth with your existing EHR/PM system
- HIPAA compliance and data handling policies
- Customization for specialty-specific protocols
- Handoff quality when human intervention is needed`;
```

---

## Topic View

When "Topic" tab is selected, the table groups prompts by topic.

Each topic: collapsible section with colored left border (2px, using `topicColor`).

Section header: topic badge (colored pill) + "4 prompts" count + avg mention rate + avg citation rate. 12px, with expand/collapse chevron.

Expanding shows the same table rows (same columns, same formatting). Click behavior identical — same Level 1 and Level 2 drawers.

```typescript
// Group prompts by topic, compute averages
const topicGroups = PROMPTS.reduce((acc, prompt) => {
  if (!acc[prompt.topic]) {
    acc[prompt.topic] = { prompts: [], color: prompt.topicColor };
  }
  acc[prompt.topic].prompts.push(prompt);
  return acc;
}, {});
```

---

## Brand System Rules

- CSS variables for all colors — never hardcode hex for UI elements
- 1px borders on all cards/containers — no borderless cards, no shadows, no gradients
- JetBrains Mono for ALL data values (rates, counts, percentages, scores)
- Space Grotesk for ALL text (labels, descriptions, headers)
- Real brand logos via `https://www.google.com/s2/favicons?domain={domain}&sz={size}` — never colored circles with initials
- Do NOT set `crossOrigin="anonymous"` on favicon images
- Supports light + dark mode via CSS variables

---

## Verification

```bash
npm run dev      # page loads at /prompt-tracking
npx tsc --noEmit # 0 errors
```

1. Page padding tight — 24px max horizontal, 16px sections, no floating whitespace
2. Filter bar: full-width toolbar, no rounded corners, border-bottom, 44px
3. Sub-nav bar: tabs left, search + actions right, also full-width toolbar, border-bottom
4. Table: 15 rows, 40px height, compact, all 7 columns present
5. Mention/Citation rates: percentage + delta on single line, correctly colored
6. Volume sparklines: rendering inline in each row (56×14px)
7. Topic badges: colored pills, 11px, truncated if long
8. Level 1 drawer: 50% width, position badge at 32px, competitor leaderboard with favicons
9. Level 1 drawer: platform rates with subtle progress bars, query fanouts section, answer history grouped by date
10. Answer history: 28 rows (7 days × 4 platforms), collapsible date groups, competitor favicon stack
11. Level 2 drawer: platform tabs with favicons, brand status indicators, mentions/citations pills
12. Level 2 drawer: full answer text with brand name highlighting (teal background)
13. Topic view: grouped sections with colored left border, collapsible, averages in header
14. Search input: filters prompt text in real-time
15. All favicons loading — check Network tab for 404s
16. Works in both light and dark mode
17. `npm run build` — succeeds

---

## Completion Criteria

- [ ] Page loads at `/prompt-tracking` with no console errors
- [ ] Filter bar: full-width toolbar with date + topic filters
- [ ] Sub-nav: Prompt/Topic tabs + search + Edit Topics + Add Prompts
- [ ] Prompt table: 15 rows, all 7 columns, 40px row height
- [ ] Rates formatted as `67.9% +7.1%` on single line with correct delta colors
- [ ] Volume sparklines render inline (56×14px)
- [ ] Sorting works on all column headers
- [ ] Level 1 drawer opens on row click — 50% width
- [ ] Level 1: Position badge (32px), competitor leaderboard (5 brands with favicons)
- [ ] Level 1: Platform mention rates with progress bars (5 platforms with favicons)
- [ ] Level 1: Query fanouts section with observation counts
- [ ] Level 1: Answer history — 28 rows grouped by 7 dates, collapsible
- [ ] Level 2 opens on answer row click — replaces Level 1 with back button
- [ ] Level 2: Platform tabs with favicons, switching shows different platform answer
- [ ] Level 2: Brand status indicators (✅ mentioned / ✗ not cited)
- [ ] Level 2: Mentions and citations as pills with favicons
- [ ] Level 2: Full answer text (~200 words) with brand name highlighting
- [ ] Topic view: grouped by topic with colored left borders, collapsible, computed averages
- [ ] Search filters prompts by text
- [ ] Footer shows "15 of 15 prompts"
- [ ] All real favicons loading (platforms + competitors)
- [ ] Brand system compliant: CSS vars, 1px borders, correct fonts, real logos
- [ ] Density: no section gap > 16px, no card padding > 16px
- [ ] `npx tsc --noEmit` — 0 errors
- [ ] `npm run build` — succeeds