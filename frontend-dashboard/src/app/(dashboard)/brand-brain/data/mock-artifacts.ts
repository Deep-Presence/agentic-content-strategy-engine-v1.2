import type { Project, Persona, KnowledgeDoc } from '@/types/brand';

// ─── Company Context ────────────────────────────────────────────────────────

export const MOCK_COMPANY_CONTEXT = `# Webflow — Company Context

## Company Overview

Webflow is a visual web development platform that empowers marketing teams and designers to build professional websites without writing code. Founded in 2013 by Vlad Magdalin, Bryant Chou, and Sergie Magdalin, Webflow serves over 3.5 million users from startups to enterprise companies like Zendesk, Dell, and Upwork.

The platform combines a visual design canvas, CMS, hosting, and e-commerce into a single integrated solution. Webflow differentiates through its ability to generate clean, semantic HTML/CSS while providing a designer-friendly visual interface that doesn't sacrifice code quality.

## Market Position

Webflow occupies a unique position at the intersection of design tools and development platforms. Unlike traditional website builders (Wix, Squarespace) that constrain designers within templates, or CMS platforms (WordPress) that require developer involvement for custom designs, Webflow gives designers full creative control while generating production-ready code.

### Key Differentiators

- **Visual-first development:** Design directly in the browser with pixel-perfect control
- **Clean code output:** Generates semantic HTML5 and CSS3, not bloated markup
- **Built-in CMS:** Content management that designers can configure without developers
- **Native hosting:** Fast, globally distributed hosting on AWS infrastructure
- **Interactions & animations:** Complex animations without JavaScript
- **E-commerce:** Full e-commerce capabilities within the visual builder

## Target Market

### Primary Segments

1. **Mid-market B2B SaaS companies** (200-2000 employees) seeking to reduce website development costs and increase marketing agility
2. **Digital agencies** building client websites with faster turnaround
3. **Enterprise marketing teams** wanting self-service website management without IT bottlenecks

### Secondary Segments

4. **Freelance designers** offering website design services
5. **Startups** building their first professional web presence
6. **E-commerce brands** seeking customizable storefronts

## Competitive Landscape

| Competitor | Strength | Weakness vs Webflow |
|-----------|----------|-------------------|
| WordPress | Market share, plugins | Requires developers, security |
| Wix | Ease of use | Template constraints, code quality |
| Squarespace | Design quality | Limited customization |
| Contentful | Headless CMS | No visual builder |
| Framer | Motion design | Limited CMS, newer platform |

## Revenue Model

- **Site Plans:** $14-$212/month per site (hosting + CMS)
- **Workspace Plans:** $19-$49/seat/month (collaboration)
- **Enterprise:** Custom pricing with SSO, SLA, dedicated support
- **E-commerce:** $29-$212/month (transaction fees on lower tiers)

## Brand Voice

Webflow's communication style is **confident but approachable**, **technical but accessible**. They position themselves as empowering creative professionals rather than simplifying for beginners. The tone is professional yet warm, with emphasis on capability and creative freedom.
`;

// ─── ICP Persona ────────────────────────────────────────────────────────────

export const MOCK_PERSONA_ICP = `## Finance Director at Mid-Market B2B SaaS

**Role:** VP/Director of Finance
**Company Size:** 200–2,000 employees
**Industry:** B2B SaaS
**Annual Revenue:** $20M–$200M

---

### Background

A strategic finance leader responsible for evaluating technology investments and ensuring they deliver measurable ROI. Reports to the CFO or CEO and works closely with marketing and IT teams to approve budget allocations for website and digital infrastructure.

Typically holds an MBA or CPA, with 8–15 years of experience in finance roles at technology companies. Comfortable with data analysis and financial modeling, but relies on marketing and IT teams for technical evaluations.

### Key Pain Points

- **Evaluating total cost of ownership** for website platforms — hidden costs in developer time, plugins, security, and ongoing maintenance
- **Justifying website rebuild investment** to the board with clear ROI projections
- **Reducing contractor dependency** for routine website updates that currently require external developers at $150–250/hour
- **Ensuring compliance** (SOC 2, GDPR) in website infrastructure without dedicated security staff
- **Consolidating vendors** — currently paying separately for hosting, CMS, analytics, and design tools

### Decision Criteria

1. **ROI within 12 months** — measurable reduction in development costs and faster time-to-market
2. **Reduced ongoing maintenance costs** — fewer developer hours for content updates and design changes
3. **Self-service capability for marketing team** — reducing internal support tickets and bottlenecks
4. **Enterprise security features** — SOC 2 compliance, SSO, role-based access, audit logs
5. **Predictable pricing** — no usage-based surprises or escalating per-seat costs

### Information Sources

- **G2 and Capterra reviews** for platform comparisons
- **Gartner and Forrester reports** for market analysis
- **CFO peer networks** (CFO Alliance, private Slack communities)
- **LinkedIn thought leadership** from other finance leaders at similar companies
- **Vendor case studies** with quantified ROI metrics

### Buying Journey

1. **Trigger:** Marketing team requests budget for website redesign; current platform creating bottlenecks
2. **Research:** Finance reviews TCO analysis, compares 3–4 platforms, consults with IT
3. **Evaluation:** Requests vendor demos, reviews security documentation, checks references
4. **Decision:** Presents business case to executive team with 3-year cost projection
5. **Approval:** Signs off on annual contract after legal review of terms

### Content Preferences

- **Format:** Data-driven case studies, ROI calculators, TCO comparison guides
- **Length:** 1,500–3,000 words for guides; executive summaries under 500 words
- **Tone:** Professional, metric-focused, no marketing fluff
- **Channels:** Email, LinkedIn, industry publications, vendor webinars
`;

// ─── Secondary Persona ──────────────────────────────────────────────────────

export const MOCK_PERSONA_SECONDARY = `## Marketing Operations Manager

**Role:** Marketing Ops Manager / Senior Marketing Manager
**Company Size:** 100–1,000 employees
**Industry:** B2B SaaS / Technology
**Reports to:** VP of Marketing or CMO

---

### Background

A hands-on marketing professional who manages the website as a core marketing channel. Responsible for campaign landing pages, blog publishing, SEO optimization, and conversion rate improvements. Works at the intersection of marketing strategy and technical execution.

Typically has 4–8 years of marketing experience with growing technical skills. Comfortable in tools like HubSpot, Google Analytics, and Figma, but doesn't write production code. Increasingly frustrated by the gap between what they design and what developers actually build.

### Key Pain Points

- **Developer bottleneck:** 2–4 week wait times for simple landing page changes
- **Design-to-dev gap:** Designs look different after developer implementation
- **Content velocity:** Can't publish fast enough to keep up with demand
- **A/B testing limitations:** Current platform makes experimentation difficult
- **Tool sprawl:** Managing separate tools for design, CMS, hosting, and analytics

### Decision Criteria

1. **Speed to publish** — ability to create and launch pages without developer support
2. **Design fidelity** — what you see is what you get, no compromises
3. **SEO capabilities** — built-in meta tags, structured data, performance optimization
4. **Integration ecosystem** — works with existing MarTech stack (HubSpot, Segment, GA4)
5. **Team collaboration** — multiple editors with review workflows

### Content Preferences

- **Format:** How-to tutorials, template galleries, comparison articles, video walkthroughs
- **Length:** 800–2,000 words; scannable with subheadings and screenshots
- **Tone:** Practical, empowering, solution-oriented
- **Channels:** YouTube, Twitter/X, Slack communities, product blogs
`;

// ─── Style Guide ────────────────────────────────────────────────────────────

export const MOCK_STYLE_GUIDE = `# Webflow Content Style Guide

## Voice & Tone

### Brand Voice Attributes

| Attribute | Description | Example |
|-----------|-------------|---------|
| **Confident** | We know our product and market. No hedging or apologizing. | "Webflow gives you complete control" not "Webflow can help you possibly control..." |
| **Empowering** | Focus on what the reader can achieve, not what we do. | "Build any layout you can imagine" not "We offer flexible layout tools" |
| **Clear** | Technical accuracy without jargon overload. | "Clean HTML and CSS" not "leveraging semantic markup paradigms" |
| **Professional** | Respectful of the reader's intelligence and time. | Skip unnecessary adjectives and filler words |

### Tone Variations by Content Type

- **Blog posts:** Conversational, educational, slightly informal
- **Product pages:** Confident, benefit-focused, concise
- **Documentation:** Precise, step-by-step, neutral
- **Case studies:** Story-driven, data-backed, professional
- **Social media:** Energetic, direct, community-oriented

---

## Writing Principles

### 1. Lead with the Benefit

Always start with what the reader gains, not what the product does.

> **Do:** "Launch campaigns 3x faster with visual page building"
> **Don't:** "Our visual page builder has drag-and-drop functionality"

### 2. Be Specific

Replace vague claims with concrete details.

> **Do:** "Generate clean, semantic HTML5 and CSS3"
> **Don't:** "Create high-quality code"

### 3. Respect the Reader's Time

Every sentence should earn its place. Cut filler words, redundant phrases, and unnecessary qualifiers.

**Words to avoid:**
- "Simply" / "just" / "easily" (minimizes effort)
- "Revolutionary" / "game-changing" (overused)
- "Leverage" / "utilize" (use "use" instead)
- "Best-in-class" / "world-class" (unsubstantiated)
- "Synergy" / "paradigm" (corporate jargon)

### 4. Use Active Voice

Active voice is more direct and engaging.

> **Do:** "Marketing teams publish pages without developers"
> **Don't:** "Pages can be published by marketing teams without developer involvement"

### 5. Write Scannable Content

Use headers, bullet points, and short paragraphs. Most readers scan before they read.

- **Paragraphs:** 2–4 sentences maximum
- **Headers:** Every 150–300 words
- **Bullet lists:** For 3+ related items
- **Bold text:** For key terms on first use

---

## Formatting Standards

### Headers

- **H1:** Page title only, one per page, title case
- **H2:** Major sections, title case
- **H3:** Subsections, sentence case
- **H4:** Detail sections (rare), sentence case

### Numbers & Data

- Spell out one through nine; use numerals for 10+
- Always use numerals with units: 3x, 5%, $29/month
- Use commas for thousands: 10,000 not 10000
- Percentage: "50%" not "fifty percent"

### Links

- Use descriptive link text, never "click here"
- External links open in new tab
- Link to the most specific page possible

### Punctuation

- **Oxford comma:** Always (red, white, and blue)
- **Em dashes:** Use sparingly for emphasis — like this
- **Exclamation marks:** Maximum one per article
- **Ellipses:** Avoid in professional content

---

## SEO Guidelines

### Meta Titles

- Format: \`Primary Keyword — Secondary Context | Webflow\`
- Length: 50–60 characters
- Include primary keyword in first 30 characters

### Meta Descriptions

- Length: 140–155 characters
- Include primary keyword naturally
- End with a value proposition or CTA
- Write as a complete sentence

### Content Structure for AI Discovery

- Answer the core question in the first 100 words
- Use structured data (FAQ schema, HowTo schema) where applicable
- Include entity-rich descriptions (names, dates, specific metrics)
- Provide definitive answers rather than hedged statements
- Use comparison tables for competitive queries

---

## Content Types & Specifications

| Type | Word Count | Reading Level | Key Elements |
|------|-----------|---------------|--------------|
| Blog Post | 1,200–2,500 | Grade 8–10 | Intro hook, 3–5 sections, CTA |
| Guide | 2,500–5,000 | Grade 9–11 | Table of contents, step-by-step, visuals |
| Case Study | 1,000–2,000 | Grade 10–12 | Challenge, solution, results with metrics |
| Landing Page | 300–800 | Grade 7–9 | Hero, benefits, social proof, CTA |
| Comparison | 1,500–3,000 | Grade 8–10 | Feature table, pros/cons, recommendation |
`;

// ─── Mock Projects ──────────────────────────────────────────────────────────

export const MOCK_PROJECTS: Project[] = [
  {
    id: 'proj-enterprise',
    name: 'Webflow Enterprise',
    slug: 'webflow-enterprise',
    description: 'Enterprise positioning, security messaging, and IT buyer enablement content.',
    personas: [
      {
        id: 'ent-icp-1',
        name: 'IT Director at Enterprise',
        type: 'icp',
        content: `## IT Director at Enterprise Company

**Role:** Director of IT / VP of Engineering
**Company Size:** 2,000–10,000 employees
**Industry:** Enterprise Software / Financial Services

---

### Background

Responsible for evaluating and approving technology platforms across the organization. Focuses on security, scalability, and vendor reliability. Reports to the CTO and manages a team of 10–30 engineers and IT professionals.

### Key Pain Points

- **Security & compliance requirements:** SOC 2 Type II, GDPR, CCPA compliance are non-negotiable
- **Vendor consolidation pressure:** Board pushing to reduce number of tools and vendors
- **Shadow IT concerns:** Marketing teams adopting tools without IT review
- **Scalability requirements:** Platform must handle enterprise traffic and multi-site architectures
- **Integration complexity:** Must work with existing SSO, CDN, and monitoring stack

### Decision Criteria

1. Enterprise-grade security (SSO, RBAC, audit logs)
2. 99.99% uptime SLA with dedicated support
3. Custom hosting / CDN configuration options
4. API-first architecture for custom integrations
5. SOC 2 Type II certification`,
      },
      {
        id: 'ent-icp-2',
        name: 'Enterprise Marketing VP',
        type: 'secondary',
        content: `## Enterprise Marketing VP

**Role:** VP of Marketing
**Company Size:** 2,000–10,000 employees

---

### Background

Senior marketing leader responsible for the company's digital presence and brand. Manages a team of 15–40 marketing professionals including web, content, and design specialists. Evaluates platforms based on team productivity and brand consistency.

### Key Pain Points

- **Brand consistency at scale:** Multiple teams and regions creating content with varying quality
- **Approval workflows:** Need structured review processes for regulated content
- **Multi-site management:** Managing 5–20 microsites alongside the main website
- **Performance metrics:** Demonstrating marketing's contribution to revenue pipeline

### Decision Criteria

1. Design system enforcement and brand guardrails
2. Role-based publishing workflows with approval chains
3. Multi-site architecture with shared component libraries
4. Analytics integration for attribution modeling
5. Localization support for global teams`,
      },
    ],
    style_guide: MOCK_STYLE_GUIDE,
    knowledge_docs: [
      {
        id: 'ent-doc-1',
        title: 'Enterprise Security Whitepaper',
        type: 'product_context',
        content: 'Webflow Enterprise security architecture overview including SOC 2 Type II compliance, data encryption, and access controls.',
      },
      {
        id: 'ent-doc-2',
        title: 'Enterprise Case Study — Zendesk',
        type: 'other',
        content: 'How Zendesk migrated 200+ pages to Webflow Enterprise, reducing page load time by 40% and developer dependency by 80%.',
      },
      {
        id: 'ent-doc-3',
        title: 'Enterprise Pricing & ROI Model',
        type: 'product_context',
        content: 'Enterprise pricing tiers, volume discounts, and ROI calculation methodology for sales enablement.',
      },
    ],
    created_at: '2026-01-28T10:00:00Z',
  },
  {
    id: 'proj-designer',
    name: 'Webflow Designer',
    slug: 'webflow-designer',
    description: 'Content targeting freelance designers and creative agencies adopting Webflow.',
    personas: [
      {
        id: 'des-icp-1',
        name: 'Freelance Web Designer',
        type: 'icp',
        content: `## Freelance Web Designer

**Role:** Independent Web Designer / Creative Director
**Experience:** 3–10 years
**Annual Revenue:** $80K–$250K

---

### Background

A skilled visual designer transitioning from static design tools (Figma, Photoshop) to web development. Builds client websites as a primary income source and seeks tools that allow direct design-to-production workflows without coding.

### Key Pain Points

- **Code handoff friction:** Designs get "lost in translation" during development
- **Scope creep:** Clients requesting changes that require developer involvement
- **Pricing pressure:** Competing with lower-cost WordPress developers
- **Portfolio limitations:** Current platform doesn't showcase design skills effectively
- **Recurring revenue:** Wants to offer hosting/maintenance for predictable income

### Decision Criteria

1. Pixel-perfect design control without code
2. Client handoff and CMS editor capabilities
3. White-label hosting for client billing
4. Template marketplace for starting points
5. Community and learning resources`,
      },
    ],
    knowledge_docs: [
      {
        id: 'des-doc-1',
        title: 'Designer Community Insights',
        type: 'other',
        content: 'Research on designer community preferences, common workflows, and tool adoption patterns from 2025 survey.',
      },
    ],
    created_at: '2026-02-05T14:30:00Z',
  },
];

// ─── Mock Research Runs ─────────────────────────────────────────────────────

export interface MockResearchRun {
  run_id: string;
  pipeline: string;
  company_slug: string;
  current_step: string;
  status: string;
  created_at: string;
  completed_at: string;
  approved: boolean;
}

export const MOCK_RESEARCH_RUNS: MockResearchRun[] = [
  {
    run_id: 'run-sg-20260216',
    pipeline: 'research',
    company_slug: 'Webflow',
    current_step: 'Style Guide',
    status: 'completed',
    created_at: '2026-02-16T09:00:00Z',
    completed_at: '2026-02-16T09:42:00Z',
    approved: true,
  },
  {
    run_id: 'run-persona-20260215',
    pipeline: 'research',
    company_slug: 'Webflow',
    current_step: 'Persona',
    status: 'completed',
    created_at: '2026-02-15T14:00:00Z',
    completed_at: '2026-02-15T14:35:00Z',
    approved: true,
  },
  {
    run_id: 'run-ctx-20260215',
    pipeline: 'research',
    company_slug: 'Webflow',
    current_step: 'Company Context',
    status: 'completed',
    created_at: '2026-02-15T10:00:00Z',
    completed_at: '2026-02-15T10:28:00Z',
    approved: true,
  },
];
