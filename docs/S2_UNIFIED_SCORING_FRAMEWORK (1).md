# S2 Unified Hierarchy + Scoring Framework

> Single-call LLM architecture that combines hierarchy construction, subdomain priority scoring, and per-persona affinity scoring into one Phase S2 invocation.

---

## 1. Why Unify Into One Call

The current architecture makes the hierarchy in S2, flattens it in Phase 2.5, then scores each node independently with algorithmic signals. This wastes the hierarchy and underuses the LLM's reasoning.

By folding scoring into the S2 hierarchy call:

- **The LLM reasons about scoring while it's building the hierarchy.** It already has the full picture — company context, persona profiles, deduplicated subdomains — so asking it to also evaluate priority and persona fit is a natural extension, not a bolted-on task.
- **Hierarchy-aware scoring comes for free.** The LLM can reason: "This subdomain is one of 5 under Compliance — and the company's context emphasizes regulatory risk — so the whole cluster is strategically important."
- **Persona affinity gets real reasoning.** Instead of a binary "did Source B mention this persona?" signal, the LLM reasons about *why* a CFO cares about cap table management (board reporting, audit readiness, equity valuation accuracy).
- **We eliminate Phase 2.5 as a separate compute step.** No separate persona affinity artifact. No separate scoring artifact. Everything lives on the taxonomy nodes.
- **We save ~5-15 seconds of embedding computation + scoring loops.** More importantly, we remove an entire artifact versioning surface.

### What We Keep From Algorithmic Scoring

The algorithmic signals that don't require LLM reasoning still run *after* the S2 call as lightweight post-processing:

| Signal | Keep? | Reason |
|--------|-------|--------|
| Source Confidence (how many sources found it) | **Yes — post-process** | Pure provenance counting, LLM doesn't need to do this |
| Content Coverage (site audit match) | **Yes — post-process** | Requires embedding comparison against site audit data the LLM doesn't have |
| Gap Severity (gap analysis alignment) | **Yes — post-process** | Requires embedding comparison against gap analysis data |
| Competitive Density (Source C match) | **Yes — post-process** | Same — embedding-based |
| Persona Breadth (source count) | **Replaced by LLM** | LLM's per-persona affinity is strictly better |

**Final composite = weighted blend of LLM scores + algorithmic signals.** See Section 5.

---

## 2. Scoring Framework

### First-Principles Derivation

When a Deep Presence customer looks at a scored taxonomy, they're asking one question: **"If we invest in producing content in this subdomain, what's the expected return?"**

That return is a function of three factors:

```
Expected Return = P(getting cited) × Value(of being cited) × Feasibility(of producing great content)
```

Every scoring dimension must map cleanly to one of these three factors. If it doesn't, it's either redundant or measuring the wrong thing.

| Factor | Maps to Dimension | Why |
|--------|------------------|-----|
| **Value of being cited** | Strategic Centrality + Conversion Potential | Getting cited for off-brand content is worthless. Getting cited for content that reaches decision-stage buyers is high-value. These two dimensions capture the *business value density* of a citation. |
| **Probability of getting cited** | Citation Opportunity | The gap between demand and supply determines citability. A niche subdomain with zero competition has higher citation probability than a massive topic with 50 incumbents. This is the core AEO/GEO insight — it's not about audience size, it's about content landscape whitespace. |
| **Feasibility of production** | Content Authority | A company with proprietary data and domain expertise produces structurally superior content. Your own research shows structural signals outperform semantic similarity for citation prediction. Authority is the feasibility multiplier. |

**Dimensions we explicitly excluded and why:**

- **Search Volume / Audience Size**: Deep Presence optimizes for AI citation, not SEO traffic. Audience size is a vanity metric in this context. A niche BOFU subdomain with 200 monthly searches but 90% citation probability is worth more than a TOFU topic with 50K searches and 2% citation probability.
- **Content Format Fit**: This is a Pipeline B concern (expansion picks formats per topic assignment). Mixing it into subdomain scoring conflates "what to write about" with "how to write it."
- **Topical Freshness / Trending Score**: Already captured by Citation Opportunity (emerging topics have high whitespace) and supplemented by Source C's deep research agent.
- **Direct Citation Probability**: That's what the CPS model does at the content level. Subdomain scoring is a strategic planning layer; CPS is a content-level prediction layer. The four dimensions here are the strategic inputs that, in aggregate, predict citation probability without replicating what CPS does.

---

### 2A. Subdomain Priority Scoring (LLM-Evaluated)

The LLM evaluates each subdomain on **four dimensions**, each scored 0.0–1.0:

#### Dimension 1: Strategic Centrality (weight: 0.35)

> Maps to: **Value of being cited** — If we get cited in this subdomain, does it build the right brand and attract the right audience?

| Score Range | Interpretation | Example |
|-------------|---------------|---------|
| 0.8–1.0 | **Core product territory** — directly maps to primary product capabilities or flagship use cases | "Cap Table Management" for Carta |
| 0.6–0.79 | **Adjacent strategic** — closely supports core offering, natural extension of product narrative | "Equity Compensation Planning" for Carta |
| 0.4–0.59 | **Relevant but peripheral** — the company has credibility here, but it's not what they're known for | "Startup Fundraising Mechanics" for Carta |
| 0.2–0.39 | **Tangential** — loosely connected, would require establishing authority from scratch | "General Small Business Finance" for Carta |
| 0.0–0.19 | **Off-brand** — no credible connection to what the company does | "Social Media Marketing" for Carta |

**Reasoning the LLM should apply:**
- Does the company context mention this domain explicitly?
- Could the company's product directly solve problems in this space?
- Would a reader finding this content naturally associate it with the company's brand?

**Weight 0.35 (highest) because:** No amount of citability or authority matters if the subdomain is strategically irrelevant. This is the "should we even be here?" gate.

#### Dimension 2: Citation Opportunity (weight: 0.25)

> Maps to: **Probability of getting cited** — Given the current content landscape, how likely is our client to earn AI citations in this subdomain?

This dimension measures the **gap between demand and supply** — not demand alone. A niche subdomain where the client can become THE cited authority scores higher than a mainstream topic drowning in competition. This is the core AEO/GEO insight: AI answer engines cite the most authoritative source for a given query, so owning a niche is more valuable than competing in a crowded space.

| Score Range | Interpretation |
|-------------|---------------|
| 0.8–1.0 | **High whitespace** — few or no authoritative sources cover this. Whether niche or emerging, the client can become THE cited authority. Classic "own the niche" territory. A narrow BOFU subdomain with zero competition scores here. |
| 0.6–0.79 | **Moderate whitespace** — some content exists but no dominant voice. A strong, well-structured piece can displace incumbents. Emerging trends where early movers win also land here. |
| 0.4–0.59 | **Contested** — several competent sources exist. The client needs a genuinely differentiated angle (proprietary data, unique methodology) to get cited over incumbents. |
| 0.2–0.39 | **Crowded** — many authoritative voices. Citation probability is low unless the client has a radically better asset. High effort, uncertain return. |
| 0.0–0.19 | **Saturated with dominant incumbents** — established authorities that AI engines already cite heavily. Displacing them is near-impossible without extraordinary differentiation. |

**Reasoning the LLM should apply:**
- How many authoritative, well-structured sources already cover this subdomain?
- Is this a space where one definitive piece could *own* the citations, or would it be one voice among many?
- Is this an emerging area where being early means being the default cited source?
- Is this a niche where depth and specificity can beat breadth? (Niche + underserved = high opportunity, not low priority)
- Would the content landscape reward a new entrant, or is incumbency too strong?

**Weight 0.25 because:** Critical for prioritization but gets reality-checked by algorithmic signals in post-processing (content coverage from site audit, competitive density from Source C). The blending step can adjust if the LLM's landscape assessment is off.

#### Dimension 3: Content Authority (weight: 0.20)

> Maps to: **Feasibility of production** — Can the client produce content here that's structurally and semantically superior to what exists?

Citation by AI engines isn't just about topical coverage — structural signals outperform raw semantic similarity. A client with proprietary data, unique product experience, or deep domain expertise can produce content with the structural depth and specificity that AI engines prefer to cite. A client stretching into unfamiliar territory will produce generic content that won't get cited regardless of the opportunity.

| Score Range | Interpretation |
|-------------|---------------|
| 0.8–1.0 | **Natural authority** — the company has proprietary data, direct product experience, or domain-specific expertise that makes their perspective uniquely valuable |
| 0.6–0.79 | **Strong credibility** — the company's team likely has deep knowledge here, even if it's not directly product-related |
| 0.4–0.59 | **Adequate credibility** — could produce competent content but wouldn't be seen as a primary authority |
| 0.2–0.39 | **Stretch** — would need external contributors or heavy research to be credible |
| 0.0–0.19 | **No standing** — publishing here would seem off-brand or opportunistic |

**Reasoning the LLM should apply:**
- Does the company's described team, product, or data give them a unique angle?
- Would their customers expect them to have opinions on this topic?
- Could they bring proprietary insights (product data, customer patterns) that others can't?
- Can they produce structurally rich content (data tables, methodology breakdowns, real examples) rather than surface-level overviews?

**Weight 0.20 because:** It's a multiplier — high authority in a high-opportunity space is the sweet spot. But authority can be built (guest contributors, partnerships, data acquisitions), whereas strategic centrality and citation opportunity are more structural.

#### Dimension 4: Conversion Potential (weight: 0.20)

> Maps to: **Value density per citation** — When someone reads AI-cited content in this subdomain, how close are they to a purchase decision?

A citation that reaches 100 decision-stage readers is worth more than one that reaches 10,000 awareness-stage readers. This dimension captures the *economic density* of the audience, not its size. Niche BOFU subdomains score high here — they have narrow audiences but extremely high intent.

| Score Range | Interpretation |
|-------------|---------------|
| 0.8–1.0 | **Direct purchase intent** — readers searching this topic are actively evaluating solutions the company offers. Classic BOFU territory. |
| 0.6–0.79 | **Problem-aware** — readers have the pain point the company solves, even if they're not solution-shopping yet. MOFU with clear conversion path. |
| 0.4–0.59 | **Education-stage** — builds brand awareness with future buyers, but conversion is indirect. TOFU with qualified audience. |
| 0.2–0.39 | **Awareness only** — attracts the right audience but has no clear path to conversion |
| 0.0–0.19 | **Traffic without intent** — might generate pageviews but from non-buyers |

**Reasoning the LLM should apply:**
- If someone reads an article on this topic, would they be a potential customer?
- How many steps removed is this topic from a buying decision?
- Is the audience narrow but high-intent (BOFU niche) or broad but low-intent (TOFU mass)?
- Does this topic align with a specific buyer stage? (Decision-stage topics score highest regardless of audience size)

**Weight 0.20 because:** It's a value multiplier. The interplay between this and Citation Opportunity is where the niche-BOFU dynamic plays out correctly: a niche subdomain scores high on Citation Opportunity (low competition) AND high on Conversion Potential (BOFU audience), so it gets correctly prioritized despite having a small total addressable audience.

#### LLM Composite Priority Score

```
llm_priority = (0.35 × strategic_centrality) + (0.25 × citation_opportunity) + (0.20 × content_authority) + (0.20 × conversion_potential)
```

**Example — niche BOFU subdomain:** "SAFE Note Cap Table Modeling for Bridge Rounds" for Carta:
- strategic_centrality: 0.75 (adjacent strategic — directly product-related)
- citation_opportunity: 0.90 (high whitespace — very few sources cover this specific workflow)
- content_authority: 0.85 (natural authority — Carta has proprietary data on thousands of SAFE conversions)
- conversion_potential: 0.85 (direct purchase intent — someone modeling this is evaluating cap table tools)
- **composite: (0.35 × 0.75) + (0.25 × 0.90) + (0.20 × 0.85) + (0.20 × 0.85) = 0.83**

This correctly prioritizes a narrow, high-value subdomain that the old "Market Opportunity" rubric would have scored 0.0-0.19 ("niche / narrow audience").

This is output per subdomain node in the taxonomy.

---

### 2B. Persona Affinity Scoring (LLM-Evaluated)

For each subdomain, the LLM evaluates affinity for **every persona in the input set**. Each (subdomain, persona) pair gets a score 0.0–1.0 and a one-line rationale.

#### Affinity Rubric

| Score Range | Interpretation |
|-------------|---------------|
| 0.8–1.0 | **Primary stakeholder** — this persona directly owns decisions or outcomes in this subdomain. Content here would be created *for* this persona. |
| 0.6–0.79 | **Strong interest** — this persona is significantly affected by this subdomain even if they don't own it. They'd read and share this content. |
| 0.4–0.59 | **Moderate relevance** — the subdomain touches this persona's world peripherally. They might skim it if it crossed their feed. |
| 0.2–0.39 | **Weak connection** — only tangentially relevant. The persona wouldn't seek this content out. |
| 0.0–0.19 | **Not relevant** — no meaningful connection between this persona's role/needs and this subdomain. |

#### Reasoning Dimensions the LLM Should Consider

For each (subdomain, persona) pair:

1. **Role Alignment**: Does this persona's job function directly involve this subdomain?
2. **Pain Point Match**: Does the persona profile list pain points that this subdomain addresses?
3. **Decision Authority**: Does this persona make buying/adoption decisions related to this subdomain?
4. **Information-Seeking Behavior**: Would this persona actively search for content on this topic as part of their workflow?
5. **Seniority Fit**: Does the depth/complexity of this subdomain match the persona's level (C-suite wants strategic, IC wants tactical)?

#### Output Format

Each taxonomy node includes:

```json
{
  "persona_affinity": [
    {
      "persona_id": "david",
      "score": 0.85,
      "rationale": "CFO directly oversees equity valuation and board reporting on cap table changes"
    },
    {
      "persona_id": "sarah",
      "score": 0.35,
      "rationale": "HR lead touches equity compensation but doesn't own cap table decisions"
    }
  ]
}
```

**This replaces the entire PersonaAffinityIndex artifact.** The affinity data lives directly on the taxonomy nodes.

---

## 3. Output Schema

### S2 LLM Output Structure

The LLM receives the deduplicated subdomain list + company context + persona profiles and returns:

```json
{
  "taxonomy": {
    "root_nodes": [
      {
        "name": "Equity Management",
        "description": "Content related to equity ownership, cap tables, and equity compensation",
        "children": [
          {
            "name": "Cap Table Management",
            "description": "Best practices for maintaining accurate cap tables, handling transactions, and reporting",
            "children": [],

            "priority_scoring": {
              "strategic_centrality": 0.92,
              "citation_opportunity": 0.75,
              "content_authority": 0.95,
              "conversion_potential": 0.85,
              "composite": 0.87,
              "scoring_rationale": "Core product capability — Carta's primary differentiator. Moderate whitespace (some guides exist but none with proprietary data depth). Company has unique data on cap table patterns across thousands of startups. Readers are direct prospective customers."
            },

            "persona_affinity": [
              {
                "persona_id": "david",
                "score": 0.90,
                "rationale": "CFO directly manages cap table accuracy for board reporting and fundraising"
              },
              {
                "persona_id": "sarah",
                "score": 0.40,
                "rationale": "HR lead interacts with equity grants but doesn't own cap table operations"
              },
              {
                "persona_id": "mike",
                "score": 0.75,
                "rationale": "Startup founder actively manages cap table during fundraising rounds"
              }
            ]
          }
        ],

        "priority_scoring": {
          "strategic_centrality": 0.90,
          "citation_opportunity": 0.65,
          "content_authority": 0.92,
          "conversion_potential": 0.80,
          "composite": 0.83,
          "scoring_rationale": "Parent category spanning Carta's core product domain. Contested at category level (many equity management guides exist) but subcategories have whitespace."
        },

        "persona_affinity": [
          {
            "persona_id": "david",
            "score": 0.88,
            "rationale": "CFO is the primary decision-maker for equity management tooling"
          },
          {
            "persona_id": "sarah",
            "score": 0.55,
            "rationale": "HR lead manages equity compensation programs under this umbrella"
          },
          {
            "persona_id": "mike",
            "score": 0.80,
            "rationale": "Founder cares deeply about equity management at company level"
          }
        ]
      }
    ],
    "coverage_score": 0.87,
    "total_subdomains": 45,
    "max_depth": 2
  }
}
```

### Key Design Decisions in the Schema

1. **Scores on every node, including parents.** Parent categories get their own scores — they're useful for category-level prioritization in the UI and for Pipeline B's expansion-status grouping.

2. **Persona affinity is a list on each node.** Not a separate artifact. Every node carries its full persona breakdown. This means one read of the taxonomy gives you everything — no join against a separate affinity index.

3. **`scoring_rationale` is a single string, not per-dimension.** This saves tokens while still giving the human reviewer enough context to understand the score. The individual dimension scores (strategic_centrality, citation_opportunity, etc.) are the structured data; the rationale is the qualitative summary.

4. **`composite` is computed by the LLM using the formula.** We verify it post-hoc in Python (re-apply the weights to the 4 dimension scores) and overwrite if it doesn't match. This catches any arithmetic errors the LLM might make.

---

## 4. The Prompt

### System Prompt

```
You are an expert B2B content strategist specializing in AI citation optimization (AEO/GEO). You will organize content subdomains into a hierarchical taxonomy and evaluate each subdomain for business priority and audience relevance.

CONTEXT: The company wants to produce content that gets cited by AI answer engines (ChatGPT, Perplexity, Claude, Gemini). AI engines cite the most authoritative, structurally rich source for a given query — not the most popular one. This means niche subdomains with low competition can be MORE valuable than mainstream topics with high traffic, because citation probability is higher when fewer authoritative sources exist.

You will receive:
1. A company context document describing the business, products, market position, and competitive landscape
2. Audience persona profiles describing the target buyer personas
3. A deduplicated list of content subdomain candidates

Your job is to:
A) Organize the subdomains into a clean hierarchical taxonomy (categories → subdomains)
B) Score each subdomain for business priority across 4 dimensions
C) Score each subdomain's relevance to each persona

TAXONOMY RULES:
- Create 5-12 top-level categories that represent distinct content pillars
- Each category should contain 3-15 subdomains
- Maximum depth: 2 levels (category → subdomain). Do NOT create deeper nesting.
- Every input subdomain MUST appear in the output taxonomy. Do not drop any.
- Categories are organizational — they group related subdomains. They are NOT new subdomains.
- Category names should be broad and intuitive (e.g., "Security & Compliance", "Data Infrastructure")
- If a subdomain doesn't fit cleanly into any category, create a "Cross-Cutting Topics" or similar catch-all. Avoid forcing bad fits.
- Merge any remaining near-duplicates you notice (candidates that slipped past dedup with different names but identical meaning). When merging, keep the more descriptive name.

PRIORITY SCORING RULES:
Score each node (both categories and leaf subdomains) on 4 dimensions, each 0.0-1.0. The underlying model is:

  Expected Return = P(getting cited) × Value(of being cited) × Feasibility(of producing great content)

The 4 dimensions map to this model:

1. strategic_centrality (weight 0.35) → VALUE OF BEING CITED
   If the company gets cited in this subdomain, does it build the right brand and attract the right audience?
   - 0.8-1.0 = Core product territory (directly maps to primary capabilities)
   - 0.6-0.79 = Adjacent strategic (closely supports core offering)
   - 0.4-0.59 = Relevant but peripheral (company has some credibility)
   - 0.2-0.39 = Tangential (loosely connected)
   - 0.0-0.19 = Off-brand (no credible connection)
   Ask: Does the company context mention this? Could their product solve problems here? Would readers associate this content with their brand?

2. citation_opportunity (weight 0.25) → PROBABILITY OF GETTING CITED
   Given the current content landscape, how likely is the client to earn AI citations here?
   This measures the GAP between demand and supply — not demand alone. A niche subdomain with zero competition scores HIGHER than a mainstream topic with 50 incumbents.
   - 0.8-1.0 = High whitespace (few/no authoritative sources — whether niche or emerging, client can become THE cited authority)
   - 0.6-0.79 = Moderate whitespace (some content but no dominant voice — early movers win)
   - 0.4-0.59 = Contested (several competent sources — needs differentiated angle to get cited)
   - 0.2-0.39 = Crowded (many authoritative voices — low citation probability)
   - 0.0-0.19 = Saturated with dominant incumbents (established authorities AI engines already cite — near-impossible to displace)
   CRITICAL: Do NOT penalize niche/narrow subdomains. A narrow BOFU subdomain with zero competition is HIGH opportunity (0.8+), not low. Score based on whitespace and citability, NOT audience size.
   Ask: How many authoritative sources cover this? Could one definitive piece own the citations? Is depth + specificity an advantage here?

3. content_authority (weight 0.20) → FEASIBILITY OF PRODUCTION
   Can the company produce structurally superior, expert-level content here?
   - 0.8-1.0 = Natural authority (proprietary data, direct product experience, unique expertise)
   - 0.6-0.79 = Strong credibility (deep team knowledge)
   - 0.4-0.59 = Adequate credibility (competent but not primary authority)
   - 0.2-0.39 = Stretch (needs external contributors)
   - 0.0-0.19 = No standing (off-brand or opportunistic)
   Ask: Does the company have proprietary data or unique angles? Can they produce content with structural depth (data tables, methodology, real examples) vs. surface-level overviews?

4. conversion_potential (weight 0.20) → VALUE DENSITY PER CITATION
   When someone reads AI-cited content here, how close are they to a purchase decision?
   A citation reaching 100 decision-stage readers is worth more than one reaching 10,000 awareness-stage readers. Score economic density, not audience size.
   - 0.8-1.0 = Direct purchase intent (BOFU — actively evaluating solutions)
   - 0.6-0.79 = Problem-aware (MOFU — has the pain point, not yet solution-shopping)
   - 0.4-0.59 = Education-stage (TOFU — future buyers, indirect conversion)
   - 0.2-0.39 = Awareness only (right audience, no clear conversion path)
   - 0.0-0.19 = Traffic without intent (pageviews from non-buyers)
   Ask: Would readers be potential customers? How many steps from a buying decision? Is the audience narrow-but-high-intent or broad-but-low-intent?

Compute composite: (0.35 × strategic_centrality) + (0.25 × citation_opportunity) + (0.20 × content_authority) + (0.20 × conversion_potential)

Write a 1-2 sentence scoring_rationale summarizing WHY this subdomain scored the way it did. Focus on the most decisive factor.

PERSONA AFFINITY RULES:
For each node, evaluate relevance to EVERY persona provided. Score each (subdomain, persona) pair 0.0-1.0:

- 0.8-1.0 = Primary stakeholder (persona directly owns decisions/outcomes here)
- 0.6-0.79 = Strong interest (persona significantly affected)
- 0.4-0.59 = Moderate relevance (touches persona's world peripherally)
- 0.2-0.39 = Weak connection (tangentially relevant)
- 0.0-0.19 = Not relevant

Consider: role alignment, pain point match, decision authority, information-seeking behavior, and seniority fit (C-suite wants strategic, IC wants tactical).

Write a brief rationale (under 15 words) for each persona affinity score.

OUTPUT FORMAT:
Return ONLY valid JSON matching this structure. No markdown, no commentary, no backticks.
{
  "taxonomy": {
    "root_nodes": [
      {
        "name": "<category name>",
        "description": "<1-2 sentence category description>",
        "priority_scoring": {
          "strategic_centrality": <float>,
          "citation_opportunity": <float>,
          "content_authority": <float>,
          "conversion_potential": <float>,
          "composite": <float>,
          "scoring_rationale": "<1-2 sentences>"
        },
        "persona_affinity": [
          {"persona_id": "<id>", "score": <float>, "rationale": "<under 15 words>"}
        ],
        "children": [
          {
            "name": "<subdomain name>",
            "description": "<1-2 sentence subdomain description>",
            "priority_scoring": { ... same structure ... },
            "persona_affinity": [ ... same structure ... ],
            "children": []
          }
        ]
      }
    ],
    "total_subdomains": <int>,
    "max_depth": <int>,
    "merged_subdomains": [
      {"kept": "<name kept>", "absorbed": "<name merged into kept>", "reason": "<why>"}
    ]
  }
}

QUALITY CHECKS:
- Every input subdomain must appear in output (or in merged_subdomains as absorbed)
- total_subdomains = count of all leaf nodes (not categories)
- Persona affinity arrays must have exactly one entry per persona provided
- Composite scores must match the weighted formula
- No duplicate subdomain names across the entire tree
```

### User Prompt Builder

```python
def build_s2_user_prompt(
    company_context: str,
    persona_profiles: list[tuple[str, str]],  # [(persona_id, profile_markdown), ...]
    deduped_subdomains: list[str],  # flat list of subdomain names post-dedup
    domain: str,
) -> str:
    """Build the user message for the unified S2 call."""

    # Format persona block
    persona_block = ""
    persona_ids = []
    for pid, profile_md in persona_profiles:
        persona_ids.append(pid)
        # Truncate to first 600 words to avoid context bloat
        truncated = " ".join(profile_md.split()[:600])
        persona_block += f"\n### Persona: {pid}\n{truncated}\n"

    # Format subdomain list
    subdomain_list = "\n".join(f"- {name}" for name in deduped_subdomains)

    return f"""## Company Context

{company_context}

---

## Audience Personas

Evaluate affinity for these persona IDs: {json.dumps(persona_ids)}

{persona_block}

---

## Deduplicated Subdomain Candidates ({len(deduped_subdomains)} total)

These have been generated from multiple sources (company brainstorm, persona brainstorm, competitor research, adversarial gap-finding) and deduplicated via embedding clustering. Organize them into a taxonomy, score each one, and evaluate persona affinity.

Domain: {domain}

{subdomain_list}
"""
```

---

## 5. Post-Processing: Blending LLM + Algorithmic Signals

After the S2 LLM call returns, we run a lightweight post-processing step. This is NOT a separate LLM call — it's pure Python.

### Step 1: Parse & Validate LLM Output

```python
def validate_s2_output(llm_output: dict, input_subdomains: list[str], persona_ids: list[str]) -> list[str]:
    """Validate the LLM output and return list of warnings."""
    warnings = []

    # 1. Check all input subdomains are accounted for
    output_names = extract_all_leaf_names(llm_output["taxonomy"]["root_nodes"])
    merged_absorbed = {m["absorbed"].lower() for m in llm_output["taxonomy"].get("merged_subdomains", [])}
    for name in input_subdomains:
        if name.lower() not in output_names and name.lower() not in merged_absorbed:
            warnings.append(f"Subdomain dropped: {name}")

    # 2. Verify persona affinity completeness
    for node in walk_all_nodes(llm_output["taxonomy"]["root_nodes"]):
        affinity_pids = {a["persona_id"] for a in node.get("persona_affinity", [])}
        for pid in persona_ids:
            if pid not in affinity_pids:
                warnings.append(f"Missing persona {pid} affinity on node {node['name']}")

    # 3. Verify composite scores
    for node in walk_all_nodes(llm_output["taxonomy"]["root_nodes"]):
        ps = node["priority_scoring"]
        expected = (
            0.35 * ps["strategic_centrality"]
            + 0.25 * ps["citation_opportunity"]
            + 0.20 * ps["content_authority"]
            + 0.20 * ps["conversion_potential"]
        )
        if abs(ps["composite"] - expected) > 0.02:
            ps["composite"] = round(expected, 4)  # Fix silently
            warnings.append(f"Corrected composite for {node['name']}: {ps['composite']}")

    return warnings
```

### Step 2: Blend With Algorithmic Signals

The LLM's `composite` score becomes one signal in the final priority score. Algorithmic signals that need external data (site audit, gap analysis) are computed separately and blended.

```python
def compute_final_priority(
    llm_composite: float,
    source_confidence: float,            # from source_provenance — always available
    content_coverage: float | None,      # from site audit — may be None
    gap_severity: float | None,          # from gap analysis — may be None
    competitive_density: float | None,   # from Source C research — may be None
) -> float:
    """Blend LLM reasoning with algorithmic signals."""

    signals = {
        "llm_composite":       (llm_composite, 0.45),
        "source_confidence":   (source_confidence, 0.15),
        "content_coverage":    (content_coverage, 0.15),
        "gap_severity":        (gap_severity, 0.15),
        "competitive_density": (competitive_density, 0.10),
    }

    # Filter out unavailable signals, renormalize weights
    available = {k: v for k, v in signals.items() if v[0] is not None}
    total_weight = sum(w for _, w in available.values())
    
    final = sum((score * weight / total_weight) for score, weight in available.values())
    return round(final, 4)
```

**Typical scenario (no site audit, no gap analysis, Source C active):**

| Signal | Weight (raw) | Weight (renormalized) |
|--------|-------------|----------------------|
| llm_composite | 0.45 | 0.643 |
| source_confidence | 0.15 | 0.214 |
| competitive_density | 0.10 | 0.143 |
| **Total** | **0.70** | **1.00** |

**Full-data scenario (all signals available):**

All weights as listed. The LLM's judgment dominates at 0.45 but is reality-checked by structural signals.

### Step 3: Backfill Into Taxonomy

```python
def backfill_final_scores(taxonomy: TaxonomyTree, final_scores: dict[str, float]):
    """Write final blended scores back onto taxonomy nodes."""
    for node in walk_all_nodes(taxonomy.root_nodes):
        node.priority_score = final_scores.get(node.id, node.priority_scoring.composite)
        # Keep the LLM's dimension breakdown and rationale intact
        # priority_score is the final blended score
        # priority_scoring.composite is the LLM-only score
```

After this, the taxonomy artifact has everything:
- `priority_score` → final blended score (LLM + algorithmic)
- `priority_scoring` → LLM's 4-dimension breakdown + rationale  
- `persona_affinity` → LLM's per-persona scores + rationales
- `source_provenance` → carried forward from dedup (used for source_confidence signal)

**No separate scoring artifact. No separate persona affinity artifact.** One taxonomy, fully scored.

---

## 6. Updated Pydantic Models

```python
class PriorityScoring(BaseModel):
    """LLM-evaluated priority dimensions for a subdomain."""
    strategic_centrality: float = Field(ge=0.0, le=1.0)
    citation_opportunity: float = Field(ge=0.0, le=1.0)
    content_authority: float = Field(ge=0.0, le=1.0)
    conversion_potential: float = Field(ge=0.0, le=1.0)
    composite: float = Field(ge=0.0, le=1.0)
    scoring_rationale: str = ""


class PersonaAffinityEntry(BaseModel):
    """One (persona, subdomain) affinity evaluation."""
    persona_id: str
    score: float = Field(ge=0.0, le=1.0)
    rationale: str = ""


class SubdomainNode(BaseModel):
    """Taxonomy node with integrated scoring."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str = ""
    depth: int = 0
    source_provenance: dict[str, bool] = Field(default_factory=dict)
    confidence: float = 0.0

    # --- NEW: LLM-evaluated scoring ---
    priority_scoring: PriorityScoring | None = None
    persona_affinity: list[PersonaAffinityEntry] = Field(default_factory=list)

    # --- Final blended score (LLM + algorithmic) ---
    priority_score: float = 0.0

    # --- Expansion tracking (Pipeline B) ---
    expansion_status: str = "not_expanded"

    children: list["SubdomainNode"] = Field(default_factory=list)


class MergedSubdomain(BaseModel):
    """Record of a merge the LLM performed during hierarchy construction."""
    kept: str
    absorbed: str
    reason: str


class TaxonomyTree(BaseModel):
    root_nodes: list[SubdomainNode] = Field(default_factory=list)
    coverage_score: float = 0.0
    total_subdomains: int = 0
    max_depth: int = 0
    merged_subdomains: list[MergedSubdomain] = Field(default_factory=list)
```

---

## 7. Token Budget Analysis

### Input Tokens

| Component | Est. Tokens | Notes |
|-----------|-------------|-------|
| System prompt | ~1,200 | The framework + rubric + output schema |
| Company context | ~3,000–8,000 | Varies; cap at 10K words |
| Persona profiles (3 personas × 600 words) | ~2,400 | Truncated to 600 words each |
| Persona profiles (5 personas × 600 words) | ~4,000 | Scales linearly |
| Subdomain list (80 subdomains) | ~800 | Just names, ~10 tokens each |
| Subdomain list (120 subdomains) | ~1,200 | Upper bound |
| **Total input (3 personas)** | **~7,500–13,000** | Well within 200K context |
| **Total input (5 personas)** | **~9,000–15,000** | Still comfortable |

### Output Tokens

| Component | Est. Tokens per Node | Nodes | Total |
|-----------|---------------------|-------|-------|
| Node structure (name, desc, children) | ~40 | 90 (10 categories + 80 leaves) | ~3,600 |
| Priority scoring (4 floats + composite + rationale) | ~60 | 90 | ~5,400 |
| Persona affinity (3 personas × ~25 tokens) | ~75 | 90 | ~6,750 |
| Persona affinity (5 personas × ~25 tokens) | ~125 | 90 | ~11,250 |
| Merged subdomains | ~100 | 1 (list) | ~100 |
| **Total output (3 personas, 80 subdomains)** | | | **~16,000** |
| **Total output (5 personas, 80 subdomains)** | | | **~20,500** |
| **Total output (5 personas, 120 subdomains)** | | | **~28,000** |

### Model Recommendation

| Subdomains | Personas | Output Tokens | Model | Est. Latency | Est. Cost |
|-----------|----------|---------------|-------|-------------|-----------|
| ≤80 | ≤3 | ~16K | Sonnet 4.6 | 25-40s | ~$0.12 |
| ≤80 | 4-5 | ~20K | Sonnet 4.6 | 35-50s | ~$0.16 |
| 80-120 | 4-5 | ~28K | Sonnet 4.6 | 45-65s | ~$0.22 |
| >120 | >5 | >30K | Consider splitting | — | — |

**Sonnet 4.6 is the right choice here.** Opus is overkill for structured scoring; Haiku is too weak for nuanced business reasoning. The call stays under 60 seconds in the vast majority of cases.

### Splitting Strategy for Large Taxonomies

If the subdomain count exceeds ~120 or persona count exceeds 5, split into two calls:

**Call 1**: Hierarchy construction + priority scoring (no persona affinity)  
**Call 2**: Persona affinity only (receives the taxonomy from Call 1, evaluates persona scores)

This keeps each call under 20K output tokens. Call 2 can even run on Haiku since it's doing simpler per-pair evaluation with the structure already established.

---

## 8. Pipeline Integration — What Changes

### Files Modified

| File | Change |
|------|--------|
| `agents.py` | Replace `run_hierarchy_construction()` with `run_unified_hierarchy_and_scoring()` |
| `prompts/hierarchy_construction.py` | Replace with `prompts/unified_s2.py` containing the new system + user prompt builders |
| `pipeline.py` (Pipeline A) | Remove Phase 2.5 scoring calls. S2 output already has scores. Add post-processing blend step. |
| `scoring.py` | Keep `_score_source_confidence()`, `_score_content_coverage()`, `_score_gap_severity()`, `_score_competitive_density()`. Remove `compute_subdomain_scores()` and `compute_persona_affinity_index()`. Add `compute_final_priority()` (the blending function). |
| `models/topic_discovery.py` | Add `PriorityScoring`, `PersonaAffinityEntry`. Update `SubdomainNode`. Remove `PersonaAffinityIndex`, `ScoredSubdomainList`. |
| `storage.py` | Remove `write_persona_affinity()`, `read_persona_affinity()`, `write_scoring()`, `read_scoring()`. Scoring + affinity now live on taxonomy nodes. |
| `pipeline.py` (Pipeline B preflight) | Read persona affinity from taxonomy nodes directly instead of loading separate artifact. |
| API schemas | Update `/scored-subdomains` and `/personas` endpoints to read from taxonomy. |

### Files Removed (or deprecated)

| Artifact | Status |
|----------|--------|
| `scoring/v1.json` | **Removed** — scores live on taxonomy nodes |
| `persona_affinity/v1.json` | **Removed** — affinity lives on taxonomy nodes |

### Migration

For existing taxonomies that don't have the new fields, add a fallback in the API layer:

```python
def get_scored_subdomains(taxonomy: TaxonomyTree) -> list[dict]:
    """Extract scored subdomain list from taxonomy for API compatibility."""
    return [
        {
            "subdomain_id": node.id,
            "name": node.name,
            "composite_score": node.priority_score,
            "llm_scoring": node.priority_scoring.model_dump() if node.priority_scoring else None,
            "persona_affinity": [a.model_dump() for a in node.persona_affinity],
            "rank": idx + 1,
        }
        for idx, node in enumerate(
            sorted(walk_leaf_nodes(taxonomy.root_nodes), key=lambda n: n.priority_score, reverse=True)
        )
    ]
```

---

## 9. Revised Pipeline A Timing

| Phase | Duration | LLM Calls | Notes |
|-------|----------|-----------|-------|
| Phase 0: Preflight | ~5s | 0 | Load context, personas |
| S1: Source A (4 rounds) | ~90s | ~4-5 | Parallel with B+C |
| S1: Source B (4 rounds) | ~90s | ~4-5 | Parallel with A+C |
| S1: Source C (deep research) | ~60-90s | ~3-4 | Parallel with A+B |
| S1: Source D (adversarial) | ~30s | ~2 | Sequential after A+B+C |
| S2: Dedup + Coverage | ~15s | 0 | Embedding + stats |
| **S2: Unified hierarchy + scoring** | **~40-60s** | **1** | **The new call** |
| Post-processing: blend | ~3s | 0 | Source confidence + available algorithmic signals |
| HITL-1 | user time | 0 | Human reviews |
| **Total Pipeline A** | **~4-5 min** | **~15-18** | **Down from ~15-20 + Phase 2.5** |

Pipeline B unchanged (~1-3 min for 5-10 subdomains).

**Total end-to-end: ~5-8 minutes excluding HITL wait time.** Well within your 10-15 minute budget.
