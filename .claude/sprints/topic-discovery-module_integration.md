The gap analysis pipeline and then it flows to the content engine module pipeline.# Untitled

## Part 1: The buyer_stage × intent_type → cluster mapping

This is the core translation layer. Topic Discovery uses a 3-stage buyer journey (tofu/mofu/bofu) crossed with 4 intent types (informational/commercial/navigational/transactional). Gap Analysis uses 9 query clusters (C1-C9), each with its own intent pattern and brand name rules. The mapping is many-to-many with weighted preferences.

## Topic Discovery → Gap Analysis Cluster Mapping

When a user selects topics from the Topic Discovery matrix and clicks "Create Content", each `TopicAssignment` must be translated into Gap Analysis queries. This document defines the deterministic mapping from Topic Discovery's `buyer_stage × intent_type` dimensions to Gap Analysis's 9-cluster query taxonomy (C1–C9).

A single TopicAssignment maps to 2–3 clusters (primary + secondary), generating 3–8 queries total per topic. The primary clusters receive 3–5 queries; secondary clusters receive 1–2 queries. This ensures enough citation diversity for meaningful structural fingerprinting in S6.

---

## Dimension Definitions

### Topic Discovery dimensions (input)

| Dimension | Values | Source Model Field |
| --- | --- | --- |
| Buyer Stage | `tofu` (awareness), `mofu` (consideration), `bofu` (decision) | `TopicAssignment.buyer_stage` |
| Intent Type | `informational`, `commercial`, `navigational`, `transactional` | `TopicAssignment.intent_type` |
| Subdomain | Free text (e.g., "Month-End Close Acceleration") | `TopicAssignment.subdomain_name` |
| Audience | Free text (e.g., "CFO", "AP Manager") | `TopicAssignment.audience_segment` |
| Topic Text | Production-ready title | `TopicAssignment.topic_text` |

### Gap Analysis clusters (output)

| Cluster ID | Cluster Name | Intent Pattern | Brand Name Policy |
| --- | --- | --- | --- |
| C1 | Mechanism | "How does X technology work?" | NO brand names |
| C2 | Boundary | "Where does X not work?" | Permitted for known product limitations only |
| C3 | Category Comparison | "X vs Y (categories, not brands)" | NO brand names |
| C4 | Decision Criteria | "What to evaluate when choosing X?" | NO brand names |
| C5 | Definition | "What is X?" | NO brand names |
| C6 | Problem/Awareness | "Why is X a problem?" | NO brand names |
| C7 | Best-of/Consideration | "Best X for Y use case" | NO brand names |
| C8 | Branded Evaluation | "Competitor-name alternatives" | REQUIRED (brand names) |
| C9 | Feature Verification | "Does X support Y?" | NO brand names |

---

## The Mapping Table

### Cell 1: TOFU × Informational

- **Description:** Early-stage buyer educating themselves on the problem space
- **Primary clusters:** C5 (Definition), C6 (Problem/Awareness)
- **Secondary clusters:** C1 (Mechanism)
- **Queries per topic:** 5–8
- **Brand rule:** No brand names anywhere

**Query patterns:**

- C5: "What is [subdomain concept]?"
- C5: "What does [subdomain term] mean in [industry]?"
- C6: "How can I solve [pain point from persona]?"
- C6: "Why does [problem] happen in [context]?"
- C1: "How does [approach/technology] work?"

**Example (subdomain: "Accounts Payable Automation", audience: "AP Manager"):**

- C5: "What is automated accounts payable and why does it matter for growing companies?"
- C5: "What does three-way matching mean in accounts payable?"
- C6: "How can I reduce the time my team spends on manual invoice processing?"
- C6: "Why do AP teams still struggle with duplicate payments?"
- C1: "How does AI-powered invoice matching work in modern AP systems?"

---

### Cell 2: TOFU × Commercial

- **Description:** Early-stage buyer starting to explore solution categories
- **Primary clusters:** C7 (Best-of/Consideration)
- **Secondary clusters:** C6 (Problem/Awareness)
- **Queries per topic:** 3–5
- **Brand rule:** No brand names anywhere

**Query patterns:**

- C7: "Best [category] tools for [audience-specific use case]"
- C7: "Top [category] solutions for [industry/company-size] in [year]"
- C6: "What problems does [category] solve for [audience]?"

**Example (subdomain: "Spend Management", audience: "CFO"):**

- C7: "Best spend management tools for growing startups 2026"
- C7: "Top corporate expense management platforms for mid-market companies"
- C6: "What visibility problems does spend management software solve for finance leaders?"

---

### Cell 3: MOFU × Informational

- **Description:** Buyer evaluating how specific approaches work and where they fail
- **Primary clusters:** C1 (Mechanism), C2 (Boundary)
- **Secondary clusters:** C4 (Decision Criteria)
- **Queries per topic:** 5–8
- **Brand rule:** No brand names (C2 permits brand only for documented product limitations)

**Query patterns:**

- C1: "How does [specific technology/approach] work?"
- C1: "What is the process for [specific workflow] in [category]?"
- C2: "What are the limitations of [approach]?"
- C2: "Where does [category] not work well?"
- C4: "What should I evaluate when choosing [category]?"

**Example (subdomain: "Month-End Close Acceleration", audience: "CFO"):**

- C1: "How does automated reconciliation work in month-end close processes?"
- C1: "What is continuous close and how does it differ from traditional month-end?"
- C2: "What are the limitations of automating financial close for multi-entity companies?"
- C2: "Where does close automation break down for companies with complex intercompany transactions?"
- C4: "What factors matter most when evaluating financial close automation tools?"

---

### Cell 4: MOFU × Commercial

- **Description:** Buyer actively comparing solution categories and approaches
- **Primary clusters:** C3 (Category Comparison), C7 (Best-of/Consideration)
- **Secondary clusters:** C4 (Decision Criteria)
- **Queries per topic:** 4–7
- **Brand rule:** No brand names anywhere

**Query patterns:**

- C3: "[Approach A] vs [Approach B] for [use case]"
- C3: "How does [category A] compare to [category B]?"
- C7: "Best [category] for [specific persona need]"
- C7: "Best [category] for [company-size/industry]"
- C4: "How to choose between [approach A] and [approach B]"

**Example (subdomain: "Corporate Card Programs", audience: "VP Finance"):**

- C3: "Corporate cards vs traditional expense reimbursement for remote teams"
- C3: "How does virtual card management compare to physical corporate card programs?"
- C7: "Best corporate card programs for companies with 200-500 employees"
- C7: "Best virtual card platforms for managing SaaS subscriptions"
- C4: "How to choose between charge cards and credit cards for corporate spending"

---

### Cell 5: BOFU × Commercial

- **Description:** Buyer evaluating specific vendors and making final selection criteria
- **Primary clusters:** C8 (Branded Evaluation), C4 (Decision Criteria)
- **Secondary clusters:** C3 (Category Comparison)
- **Queries per topic:** 4–6
- **Brand rule:** Brand names REQUIRED for C8, excluded from C4 and C3

**Query patterns:**

- C8: "[Brand A] vs [Brand B] vs [Brand C]"
- C8: "[Brand] alternatives for [use case]"
- C4: "What to look for in a [category] contract"
- C4: "What questions to ask [category] vendors before signing"
- C3: "How do modern [category A] compare to legacy [category B]?"

**Example (subdomain: "Equity Management", audience: "VP Legal"):**

- C8: "Carta vs Pulley vs Shareworks for Series C equity management"
- C8: "Carta alternatives for international cap table management"
- C4: "What to look for when evaluating equity management platform contracts"
- C4: "What compliance certifications should a cap table provider have?"
- C3: "How does purpose-built equity software compare to spreadsheet-based cap table management?"

---

### Cell 6: BOFU × Transactional

- **Description:** Buyer verifying specific features before purchase decision
- **Primary clusters:** C9 (Feature Verification), C8 (Branded Evaluation)
- **Secondary clusters:** (none)
- **Queries per topic:** 3–5
- **Brand rule:** C9 uses category-level (no brands), C8 requires brands

**Query patterns:**

- C9: "Does [category] typically support [specific feature]?"
- C9: "Can [category] handle [specific use case]?"
- C9: "Do [category] tools integrate with [specific system]?"
- C8: "[Brand A] vs [Brand B] [specific feature comparison]"

**Example (subdomain: "AP Automation Integrations", audience: "IT Director"):**

- C9: "Does AP automation software typically integrate with NetSuite and SAP?"
- C9: "Can accounts payable platforms handle multi-currency invoice processing?"
- C9: "Do AP automation tools support OCR for handwritten invoices?"
- C8: "Tipalti vs Bill.com integration capabilities for ERP systems"

---

## Excluded Combinations

The following `buyer_stage × intent_type` combinations produce no useful queries and should be skipped (matching Topic Discovery's own relevance filtering logic):

| Combination | Reason |
| --- | --- |
| TOFU × Transactional | Awareness-stage buyers are not ready to transact |
| TOFU × Navigational | Awareness-stage buyers are not searching for specific brands |
| MOFU × Navigational | Consideration-stage navigational queries are too brand-specific |
| MOFU × Transactional | Consideration-stage buyers are evaluating, not purchasing |
| BOFU × Informational | Decision-stage buyers don't need basic educational content |
| BOFU × Navigational | Navigational queries (e.g., "X login") have no content strategy value |

These combinations should already be marked `irrelevant` by Topic Discovery's relevance filtering in S3. If any slip through, the mapping function returns an empty query list.

---

## Query Generation Constraints

### Per-topic constraints (inherited from standard S2)

- Each query must be unique and phrased as a real buyer would type it
- Queries use natural language, not keyword strings
- Generic category terms instead of brand names (except C8)
- Each query tagged with: `cluster_id`, `cluster_name`, `buyer_stage`, `persona_tag`, `source_topic_id`

### Cross-topic constraints (applied during dedup pass)

- Cosine similarity threshold: 0.85 (same as standard S2)
- If two topics generate semantically identical queries, the duplicate is dropped and the surviving query inherits both `source_topic_id` values
- Maximum total queries = 8 × N topics (before dedup)

### Subdomain grounding

- Every query must be grounded in the topic's subdomain, not the company's full category
- Example: If subdomain is "Month-End Close Acceleration", queries should be about financial close processes, NOT about the company's entire product category
- The `subdomain_name` replaces the generic `company_category` in the query generation prompt

### Audience scoping

- The `audience_segment` from the TopicAssignment is used as the persona lens for query generation
- This replaces the generic ICP persona tag in standard S2
- Queries should reflect how this specific audience would phrase their search

---

## Summary: Query Count Budget

| Cell | Primary Clusters | Secondary Clusters | Queries/Topic | Use Case |
| --- | --- | --- | --- | --- |
| TOFU × Informational | C5, C6 | C1 | 5–8 | Educational content, definitions |
| TOFU × Commercial | C7 | C6 | 3–5 | Listicles, "best of" roundups |
| MOFU × Informational | C1, C2 | C4 | 5–8 | Deep dives, how-it-works, limitations |
| MOFU × Commercial | C3, C7 | C4 | 4–7 | Comparison guides, evaluation guides |
| BOFU × Commercial | C8, C4 | C3 | 4–6 | Vendor comparisons, buying guides |
| BOFU × Transactional | C9, C8 | — | 3–5 | Feature verification, final comparison |

**Typical run:** 5 selected topics × ~5 queries each = ~25 queries → ~100 platform searches (4 engines) → structural fingerprint in 3-5 minutes.

The key insight in this mapping: a single `TopicAssignment` with `buyer_stage=mofu` and `intent_type=commercial` doesn't map to one cluster — it maps to C3 (Category Comparison) AND C7 (Best-of) as primary targets, with C4 (Decision Criteria) as secondary. This means a single topic generates 4-7 queries spread across 2-3 clusters, giving the gap analysis enough diversity to produce meaningful structural intelligence.

## The modified S2: `generate_queries_from_topics()`

This is the biggest code change. Instead of the current 3-pass approach (seed from full taxonomy → dedup → coverage validation), the TD-scoped S2 uses a 2-pass approach:

**Pass 1: Topic-scoped query generation.** For each selected `TopicAssignment`, the function determines the primary and secondary clusters from the mapping table, then calls the LLM with a topic-scoped prompt. The critical difference from generic S2 is that the prompt is anchored to a specific subdomain, audience segment, and topic angle — not the entire company's category.

Here's what the prompt structure looks like conceptually:

`For this specific topic:
  Title: "How Mid-Market CFOs Can Cut Month-End Close from 15 Days to 5"
  Subdomain: Month-End Close Acceleration
  Audience: CFO at mid-market companies
  Buyer stage: MOFU (consideration)
  Intent: informational

Generate 5-8 search queries a real buyer would type into ChatGPT/Claude/Perplexity.
Focus on these cluster patterns:
  PRIMARY: C1 (Mechanism) — "How does X work?"
  PRIMARY: C2 (Boundary) — "What are the limitations of X?"
  SECONDARY: C4 (Decision Criteria) — "What to evaluate when choosing X?"

Brand name rules: [inherited from cluster taxonomy]
Company context: [condensed company context]
Persona context: [matched persona for this audience_segment]`

Each generated query is tagged with its source `topic_assignment_id`, enabling the downstream pipeline to group results back to the original topic.

**Pass 2: Cross-topic semantic deduplication.** This reuses the existing `_deduplicate_queries()` function with the same 0.85 cosine similarity threshold, but deduplication happens across the full query set (not per-cluster). If two topics in the same subdomain generate near-identical queries, the duplicate is dropped and the surviving query inherits both topic IDs.

**What's different from generic S2:**

The generic S2 generates ~150 queries across all 9 clusters with balanced coverage. The TD-scoped S2 generates 4-8 queries per topic × N topics, producing 20-60 total queries, concentrated in the 2-3 clusters relevant to each topic's buyer stage and intent. There's no Pass 3 (coverage validation) because we don't need balanced coverage across all clusters — we only need coverage for the specific clusters relevant to the selected topics. S1 (embed company assets) is either skipped entirely (using cached data from a prior gap analysis run) or runs normally if no prior run exists.

**The query count per topic varies by mapping cell:**

TOFU × informational produces more queries (5-8) because it maps to two primary clusters (C5 and C6) that have broad query patterns. BOFU × transactional produces fewer (3-5) because C9 queries are highly specific feature verification questions. This matches real buyer behavior — early-stage research is broader, late-stage research is narrower.

## S3-S6: Unchanged but scoped

Steps 3 through 6 run identically to the standard gap analysis. The only difference is the input query set is smaller and more focused, which means faster execution (20-60 queries vs 150) and lower API costs. The structural fingerprinting in S6 produces per-query `GapContentBrief` and per-cluster `ClusterContentSpec` exactly as before.

## Modified S8: Per-topic aggregation

Standard S8 produces a single gap report and generation spec for the entire analysis. For TD-scoped runs, S8 additionally groups results by source `topic_assignment_id` to produce per-topic structural intelligence. Each topic gets its own `WorkerQueryContext` containing the full exemplar data, structural signals, and cluster spec for the queries generated from that topic.

## Part 3: Content Engine entry mode

The v1.3 pipeline currently supports two entry modes: `AUTONOMOUS` (from gap analysis) and `MANUAL` (user-provided prompt). The integration adds a third: `TOPIC_DISCOVERY`.

python

`class EntryMode(str, Enum):
    AUTONOMOUS = "autonomous"       # Full: GA → Planner → Brief Builder
    MANUAL = "manual"               # User prompt → inline context → workers
    TOPIC_DISCOVERY = "topic_discovery"  # TD → scoped GA → skip Planner → Brief Builder`

In `TOPIC_DISCOVERY` mode, the pipeline changes are:

**Stage 0 (Context Router):** Instead of `extract_scorecard()` for the full analysis, it calls a new `extract_topic_contexts()` that returns a `WorkerQueryContext` per selected topic, grouped by `topic_assignment_id`.

**Stage 1 (Strategic Planner): SKIPPED.** The user already selected the topics in the Topic Discovery HITL-2 matrix approval. There's no need for the planner to re-triage. The `TopicSelection` objects are constructed directly from the `TopicAssignment` data.

**Stage 2 (Brief Builder): Runs normally.** The Brief Builder receives per-topic `WorkerQueryContext` with full exemplar structural signals, exactly as it does in `AUTONOMOUS` mode. This is where the structural intelligence from the scoped gap analysis flows into the content blueprint — word count ranges, FAQ rates, paragraph lengths, self-contained ratios, all derived from what AI platforms actually cite for those specific queries.

**Stages 3-5 (Workers, Evaluator, HITL): Unchanged.** The drafter receives structural targets calibrated by real citation data, the evaluator checks against those empirical targets, and the HITL gates work as before.

## Why this design works

The fundamental insight: Topic Discovery and Gap Analysis answer different questions, and both answers are needed. Topic Discovery says "write about month-end close acceleration for mid-market CFOs at the consideration stage." Gap Analysis says "for queries about month-end close acceleration, the content that AI platforms cite averages 2,100 words, includes FAQ sections 73% of the time, uses 4-6 headers with H2/H3 hierarchy, references 3+ statistics, and maintains self-contained paragraphs of ~55 words." The content engine needs both to produce content that fills the right gap in the right structural format.

Skipping gap analysis would mean the Brief Builder has no exemplar data to compute structural targets. The drafter would fall back to hardcoded defaults. The structural evaluator would check against generic thresholds instead of empirically calibrated ones. You'd be writing content that follows generic AEO best practices (the PDF you attached) rather than content structurally calibrated to what actually gets cited for those specific queries on those specific platforms. That's the difference between "generally good AEO content" and "content specifically engineered to get cited for this query."

The scoped gap analysis approach is also efficient — 20-60 queries instead of 150 means roughly 3x less API cost and 2-3x faster execution for S3 (the most expensive step). And S1 can reuse cached company embeddings, so there's no redundant crawling.