# Content Engine Pipeline v1.3 — Implementation Specification

> **Purpose:** This document describes the complete workflow of the revamped Content Engine Pipeline (v1.3) as designed in the Excalidraw architecture diagram. It is intended to serve as the primary planning prompt for Claude Code to implement this pipeline against the existing Deep Presence codebase.
>
> **Relationship to Existing Code:** This is NOT a ground-up rewrite. The existing content engine (`core/content_engine/`) implements a 4-stage pipeline (Planner → Workers → Evaluator → HITL Review). v1.3 retains the same foundational stages but restructures the data flow, adds an additional HITL checkpoint after brief generation, introduces two-phase context loading to solve the context explosion problem, adds a secondary "manual prompt" entry mode, and implements smarter feedback loops with section-level vs. major-direction-change routing. The existing models in `core/models/content_generation.py`, the worker chain in `core/content_engine/workers/`, the evaluator in `core/content_engine/evaluator.py`, and the LangGraph HITL graph in `core/content_engine/graph.py` are all reusable foundations — they need extension, not replacement.

---

## 1. Pipeline Entry Modes

The v1.3 pipeline supports two distinct entry modes that converge into the same downstream workflow. This is a key architectural addition — the current v1.0 pipeline only supports the autonomous mode.

### 1.1 Autonomous Mode (Normal Pipeline)

This is the primary production flow. It begins after the Gap Analysis Pipeline (Pipeline 2) has completed for a company and produced its full output artifacts (`analysis.json`, `gap_report.json`, `generation_spec.json`, `gap_analysis_complete.json`).

The input to the autonomous pipeline is the complete gap analysis output covering all queries (typically 150-200 queries) that were analyzed. The pipeline's first job is to triage this large dataset down to the highest-impact content opportunities before doing any content generation work.

The data flow for autonomous mode is: Gap Analysis Output → Strategic Planner (Agent 1) → HITL Approval of Topics → Brief Builder (Agent 2, one per approved topic) → HITL Approval of Briefs → Phase 2 Content Production → Evaluation → HITL Final Review → Publish.

### 1.2 Manual Prompt Mode

This is an alternative entry point where a human user directly specifies what content to produce, bypassing the autonomous prioritization step entirely. The user provides a heading/prompt describing the content topic, a brief description of what the content should cover, and optionally which query cluster the topic belongs to.

Upon receiving this manual input, the system runs the Gap Analysis Pipeline on just this single user-provided prompt. This produces a focused gap analysis report for that one topic — the same data structures as the full pipeline but scoped to a single query with its competitor exemplars and structural signals.

Because there is no prioritization needed (the human already chose the topic), the manual mode skips the Strategic Planner (Agent 1) and the first HITL checkpoint entirely. It flows directly into the Brief Builder (Agent 2) using the gap analysis results from the single-query run, and then continues through the same Phase 2 pipeline as the autonomous mode.

The data flow for manual mode is: User Prompt → Single-Query Gap Analysis → Brief Builder (Agent 2) → HITL Approval of Brief → Phase 2 Content Production → Evaluation → HITL Final Review → Publish.

The key implementation consideration is that both modes must converge at Agent 2 with the same data contract. Agent 2 should not know or care whether it received its input from the Strategic Planner's selection or from a manual prompt. This means the context extraction and formatting logic must produce identical output shapes regardless of entry mode.

---

## 2. Phase 1: Strategic Prioritization (Autonomous Mode Only)

### 2.1 The Strategic Planner (Orchestrator Agent 1)

The Strategic Planner is the first agent in the autonomous pipeline. Its sole responsibility is triage — deciding which queries, out of all 200 analyzed in the gap report, represent the highest-impact content opportunities that the system should act on first.

**What it receives as input:** The planner receives a lightweight "scorecard" summary of the full gap analysis, NOT the complete analysis data. This is the critical architectural change from v1.0, where the planner received the full gap report, generation spec, analysis JSON, company context, personas, and style guide — often totaling 80-120K tokens of context for a decision that fundamentally only needs a few data points per query.

The scorecard contains two sections. The first is a per-query scorecard for all 200 queries, containing only: the query ID, the query text, the cluster name it belongs to, the numeric gap score (avg_citation_similarity minus best_company_similarity), the company similarity score, the citation similarity score, the classification (significant_gap / gap_to_close / roughly_equal / company_wins), the number of citation exemplars found for that query, and whether a content brief was computed. This amounts to roughly 50 tokens per query. The second section is a per-cluster aggregate summary with: cluster name, query count, average gap, maximum gap, count of queries classified as significant_gap, dominant content type across the cluster, and dominant authority type. This amounts to roughly 60 tokens per cluster.

The total context for all 200 queries plus 10-15 cluster summaries comes to approximately 11K tokens — a 5-6x reduction from the current approach while actually giving the planner visibility into ALL queries rather than a truncated top-50.

The planner also receives a brief company context summary (roughly 500-600 characters — the first paragraph of the company context research artifact, not the full 5000+ word document) and an optional product focus block if this is a product-level run. It explicitly does NOT receive the style guide, persona profiles, generation spec, or any exemplar structural signals — none of these are relevant to the prioritization decision.

**What it produces as output:** The planner outputs a ranked list of top-K content opportunity selections (typically 4-6). Each selection contains: a rank, one or more query IDs (multiple if consolidating related queries), the corresponding query texts, the cluster name, a rationale explaining why this opportunity was chosen over alternatives, a consolidation note (if multiple queries can be addressed by a single content piece), and an estimated impact level.

The planner also produces metadata about its selection strategy — how many total queries it reviewed, which clusters are represented in its selections, and a brief description of its prioritization logic.

**What it does NOT produce:** Unlike the current v1.0 planner, Agent 1 in v1.3 does NOT produce full content briefs. It does not set structural targets, word count ranges, content formats, or key topics. All of that is deferred to Agent 2 (the Brief Builder), which will have access to the full gap analysis detail for the approved queries. This separation is intentional — the planner is a triage agent, not a content architect.

**How to extract the scorecard from existing data:** The scorecard should be extracted from the `analysis.json` output of the gap analysis pipeline. The `AnalysisResult` model (defined in `core/models/gap_analysis.py`) contains a `gaps` field which is a `List[QueryGap]`. Each `QueryGap` already has `query_id`, `query_text`, `cluster_name`, `best_company_similarity`, `avg_citation_similarity`, `gap`, `interpretation`, `top_cited_exemplars` (from which we derive the exemplar count), and `content_brief` (from which we derive the has_brief flag). The cluster summaries can be computed by aggregating the gap data grouped by `cluster_name`, enriched with `dominant_content_type` and `dominant_authority_type` from the `cluster_specs` field of `AnalysisResult`.

For optimal latency, the scorecard extraction should use the database (ORM) path when available. A SQL query selecting only the scorecard columns from the `query_gaps` table, with a `GROUP BY cluster_name` aggregate for the cluster summaries, avoids loading the full 20MB analysis JSON into memory. The existing `GapAnalysisRepository` in `core/repositories/gap_analysis.py` and the `DbGapDataService` in `core/services/db_gap_data.py` provide the data access patterns to build on. When the database is not available (e.g., local development or CLI runs), fall back to loading the JSON file and extracting in Python.

**Model choice and token budget:** The planner should use Claude Sonnet 4.5 (consistent with v1.0). With approximately 11K tokens of input context, this leaves ample room in the 200K context window for the system prompt and output generation.

### 2.2 HITL Checkpoint 1: Topic Approval

After the Strategic Planner produces its ranked selections, the pipeline pauses for human approval. This is a LangGraph `interrupt()` checkpoint following the same pattern used in the research pipeline (`core/research/graphs/company_research.py`).

The approval payload presented to the user includes: the ranked list of selected topics with their query texts, cluster names, gap scores, rationales, and consolidation notes. The frontend should render this as a reviewable list where the user can see why each topic was selected and what impact it's expected to have.

The user has three options at this checkpoint. They can approve the selections as-is, in which case the pipeline proceeds to Agent 2 for each approved topic. They can modify the selections — removing topics they don't want, adding topics from the full query list that the planner didn't select, or reordering priorities — and then approve. Or they can reject entirely, which triggers one of two paths: either the pipeline re-runs the Strategic Planner with adjusted parameters or additional guidance from the user (the "retry" path), or the pipeline stops completely if the user decides the gap analysis needs to be re-run first (the "stop" path).

The retry path should allow the user to provide feedback that gets injected into the planner's next attempt — for example, "focus more on the expense-tracking cluster" or "don't select any FAQ-type content, we need long-form guides." This feedback becomes an additional context block in the planner's prompt on the retry run.

---

## 3. Brief Building (Agent 2) — Where Both Modes Converge

### 3.1 The Brief Builder Agent

Agent 2 is the content architect. For each approved topic (from either the autonomous mode's HITL-approved selections or the manual mode's single-query gap analysis), it produces a detailed content blueprint — what the existing codebase calls a `ContentBrief`.

**The critical difference from v1.0:** In the current pipeline, the Strategic Planner produces the briefs directly. In v1.3, brief building is a separate agent that runs AFTER topic approval. This separation exists because brief building requires the full gap analysis detail for its specific queries (exemplar structural signals, content brief targets, citation URLs, snippet text, cluster specs), and loading this detail for all 200 queries upfront would create the same context explosion problem that the scorecard approach solves for the planner.

**What Agent 2 receives as input (the "full context pull"):** For each approved topic, Agent 2 receives the complete `QueryGap` data for that query (or queries, if consolidated) — including all `top_cited_exemplars` with their full `structural_signals` (word count, header count, list item count, stat count, paragraph count, reading level, FAQ section presence, table presence, etc.), the `snippet` text, the `url`, the `authority_type`, and the `similarity` score. It also receives the pre-computed `GapContentBrief` (target word count range, reading level range, paragraph length targets, recommended header count, structural element rates), the `ClusterContentSpec` for the relevant cluster (aggregate structural rates, authority signal distribution, exemplar themes), and the client's `best_company_unit_text` (their current best-matching content for this query, so the agent understands what already exists).

Beyond the gap data, Agent 2 also receives the full company context markdown (not the summary — the complete research artifact), the persona profiles relevant to this topic's cluster, and a reference to the style guide (for format choice, not for writing style application, which happens downstream).

**How to extract the full context for approved queries:** When the topic approval HITL resolves, the pipeline receives a list of approved query IDs. A context extraction function should take the `analysis_json` (or query the database) filtered to only those IDs, pulling the complete `QueryGap` records with their nested `top_cited_exemplars` and joining to the relevant `ClusterContentSpec`. This filtered extraction is the "Phase 2" of the two-phase context loading — it only loads heavy data for the 4-6 approved queries, not all 200.

For database-backed runs, this is a filtered query: `SELECT * FROM query_gaps WHERE run_id = ? AND query_id IN (?)` joined with `query_exemplars` and the relevant `cluster_specs` row. For JSON-backed runs, it's a dictionary lookup filtering the `gaps` list by query_id.

**What Agent 2 produces (processing steps):** Agent 2 performs several analytical steps before producing its output. It determines the optimal content type (guide, FAQ, comparison, how-to, pillar page, etc.) based on the gap data's dominant content type, the query intent, and the cluster patterns. It generates a structured section-by-section outline with keyword-density insights per section. It computes fine-grained structural targets from the exemplar structural signals — the target word count, target paragraph length, header count, list count, whether to include FAQ sections, tables, definition blocks, key takeaways, and so on. It checks for metadata or specific existing content that should be updated rather than created from scratch.

It also performs a territory analysis — identifying semantically adjacent topics and queries that the content should reference or link to, helping the downstream drafter build content that naturally connects to the broader topic cluster.

**What Agent 2 outputs (the content blueprint):** The output is a `ContentBrief` (or an extended version of it) that includes everything the downstream Phase 2 workers need. This means: a title, target queries, content format, funnel stage, channel, word count range, full structural targets (all 22+ fields from the expanded `StructuralTargets` model), key topics and angles, competitor exemplar summaries (URLs, structural fingerprints, snippet text), exemplar themes, a section-by-section outline with per-section word count allocations, a reading hierarchy with H1/H2/H3 structure, a must-hit checklist with priority ranking, and a content type recommendation.

This is a significantly richer brief than what the v1.0 planner produces, because Agent 2 has access to the full exemplar intelligence rather than working from a truncated summary.

### 3.2 Parallelism: One Brief = One Worker

A critical architectural note visible in the Excalidraw diagram: when there are multiple approved topics (say 4-6 from the autonomous mode), each topic gets its own Agent 2 instance running as a parallel worker. This follows the existing `asyncio.Semaphore`-based concurrency pattern in `core/content_engine/workers/dispatcher.py`. Each worker independently builds its brief, and the briefs are collected before the next HITL checkpoint.

The dispatcher should control concurrency (default 3 concurrent workers) to manage API rate limits and cost.

### 3.3 HITL Checkpoint 2: Brief Approval

After Agent 2 produces the content blueprint(s), the pipeline pauses again for human review. This is a new HITL checkpoint that does not exist in v1.0 (where the planner's briefs go directly to the content workers without human review).

The approval payload should present the complete brief in a readable format — the title, outline, structural targets, exemplar references, and must-hit checklist. The frontend should render this as an interactive brief review interface where the user can see each section, its target word count, and what competitor content it's competing against.

The user's options at this checkpoint are: approve the brief as-is (proceed to Phase 2 content production), provide feedback/modifications to the brief (which Agent 2 incorporates before re-presenting), or reject the brief entirely (which either triggers a re-run of Agent 2 with different parameters or stops the pipeline for that topic).

Any user feedback provided during brief review should be captured and forwarded as an additional input to Phase 2. This is important because the user might approve the brief but add notes like "emphasize the ROI angle more in section 3" or "don't use competitor names directly." These notes should reach the drafter as supplementary instructions.

---

## 4. Phase 2: Content Production

Phase 2 is the content writing, enrichment, and evaluation pipeline. It is structurally similar to the existing v1.0 Stages 2-3-4, but with important refinements to the feedback loops and context routing.

### 4.1 Phase 2 Inputs

For each approved brief, Phase 2 receives a well-defined input bundle consisting of: the approved content blueprint from Agent 2 (with all structural targets, outline, and exemplar intelligence), the gap analysis research data for the specific queries targeted by this brief, the company context, audience persona, brand context (voice, tone, E-E-A-T signals) from the Pipeline 1 research artifacts, and any user feedback from the brief review HITL (if provided).

The important context routing principle here is that each Phase 2 sub-agent gets exactly what it needs and nothing more. The drafter gets the outline, style guide (in full — no truncation), structural targets, and exemplar themes. The fact enricher gets the draft, key topics, and domain context. The formatter gets the enriched content, style guide, and structural targets. This is the "context routing instead of context dumping" principle — each stage receives a purpose-shaped view of the data.

### 4.2 The Drafter Agent

The drafter writes the full article based on the approved brief and outline. It receives the section-by-section outline with per-section word count allocations, the full style guide (not truncated), the structural targets, and exemplar themes that indicate what semantic territory the content should cover.

For longer content (pillar pages, 2500-4000 words), the drafter should use a two-pass approach: section-by-section drafting (one LLM call per 2-3 sections to maintain quality) followed by a coherence pass (one call to ensure transitions and narrative flow). This prevents the quality degradation that occurs when a single LLM call tries to produce 4000 words at once.

The drafter's output is a complete markdown article draft, saved as `draft.md` in the brief's artifact directory.

### 4.3 The Fact Enricher Agent

The fact enricher web-grounds the draft with real citations, statistics, and external references. It also adds internal linking (links to other content on the client's site) and external linking (authoritative third-party sources). This agent uses Perplexity sonar-pro for web-grounded fact verification and citation discovery.

The enricher's output is the enriched markdown, saved as `enriched.md`.

### 4.4 The LLM-as-Judge Evaluator (with E-E-A-T Model)

The evaluator runs a multi-dimensional quality gate on the enriched content. The v1.3 evaluator extends the existing 4-dimension evaluation with explicit E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness) scoring, which is critical for AI citation optimization.

The evaluation dimensions are: structural compliance (deterministic regex-based checks against the brief's structural targets), semantic alignment (embedding similarity between the content and the target query embeddings), style compliance (LLM-as-judge evaluating alignment with the company's writing style guide), factual accuracy (LLM-as-judge evaluating claim grounding and citation quality), and E-E-A-T signals (evaluating whether the content demonstrates the authority signals that AI platforms look for when selecting sources to cite).

The evaluator produces a pass/fail decision with per-dimension scores and specific feedback for any failing dimensions.

### 4.5 Feedback Loops (Critical v1.3 Addition)

The Excalidraw diagram shows two distinct feedback loops, which is a significant refinement over v1.0's single undifferentiated revision loop.

**Loop 1: Section-Level Edits.** When the evaluator identifies issues that are localized to specific sections — a section that's too short, missing a required structural element, has a style violation, or contains a factual inaccuracy — the feedback routes back to the drafter/enricher/formatter for targeted revision. The key difference from v1.0 is that this loop should identify WHICH sections need revision and WHAT specifically needs to change, rather than sending the entire article back for a full rewrite. The revision should be scoped: if only structural checks failed, route to the formatter for restructuring (cheaper and faster than re-drafting). If only style failed, route to a style-specific revision pass. If only factual issues, re-run the enricher with specific claims to verify. Only if semantic alignment fails (fundamental content mismatch) should the drafter re-engage.

This section-level edit loop runs up to `max_revision_cycles` times (default 2, potentially higher for pillar pages).

**Loop 2: Major Direction Change.** When the evaluator identifies issues that indicate a fundamental problem with the content's direction — the content is semantically off-target, the brief was misconceived, or the user's feedback from the final HITL review indicates the entire approach needs rethinking — the feedback routes all the way back to Agent 2 (the Brief Builder) for a new brief. This is a much more expensive loop and should only trigger when section-level edits cannot fix the problem. The Excalidraw diagram shows this as a long arrow going back from the evaluation/HITL stage to the beginning of the orchestrator-workers zone.

In practice, a major direction change is most likely triggered by the human reviewer at the final HITL checkpoint, not by the automated evaluator. The automated evaluator handles section-level issues; the human handles strategic-level course corrections.

### 4.6 HITL Checkpoint 3: Final Content Review

After the content passes the evaluator (or exhausts its revision cycles and gets flagged for human review), it reaches the final HITL checkpoint. This follows the same LangGraph pattern as the existing `core/content_engine/graph.py` — presenting the content for approve / edit / reject decisions.

On approval, the content is finalized and written to `final.md` — ready for publishing. On edit, the human's editor notes are captured and the content loops back for revision (section-level edits). On reject, the content is discarded, and depending on the rejection reason, the pipeline may trigger a major direction change loop back to Agent 2.

After passing this final checkpoint, the content moves to the Publish stage — which in the current system means writing the final artifact to disk. Future versions may integrate with CMS publishing APIs.

---

## 5. Data Model and Storage Considerations

### 5.1 New Models Needed

The v1.3 pipeline introduces several new data structures that should be defined in `core/models/content_generation.py` (or a new module if the file grows too large).

A `PlannerScorecard` model to represent the lightweight Phase 1 scorecard sent to the Strategic Planner. This contains a list of `QueryScorecard` records (one per query with the 8-9 scorecard fields) and a list of `ClusterSummary` records (one per cluster with aggregate statistics).

A `TopicSelection` model to represent the Strategic Planner's output — a ranked selection with query IDs, rationale, consolidation notes, and estimated impact.

A `WorkerQueryContext` model to represent the full Phase 2 context for a single approved query — the complete `QueryGap` data, exemplar details, content brief, and cluster spec.

The existing `ContentBrief` model should be extended (or a `ContentBlueprint` subclass created) to carry the richer output that Agent 2 produces — the full section-level outline with per-section word count allocations, the expanded structural targets, and the exemplar intelligence.

### 5.2 Storage Path for Each Phase

For Phase 1 (scorecard extraction), prefer the database (ORM) path when available. The scorecard columns map directly to existing columns in the `query_gaps` table. A lightweight repository method that selects only the needed columns avoids loading exemplar blobs. Fall back to JSON when the database isn't available.

For Phase 2 (full context extraction), the database path is also preferred — a filtered join of `query_gaps`, `query_exemplars`, and `cluster_specs` scoped to the approved query IDs. The JSON fallback loads `gap_analysis_complete.json` and filters by query_id in Python.

For artifact persistence during content production, continue using the existing filesystem-based artifact storage (`artifacts/content/{slug}/content/brief-{N}/`). Each brief directory should contain all intermediate artifacts: `outline.json`, `draft.md`, `enriched.md`, `formatted.md`, `eval_history.json`, `final.md`. This is unchanged from v1.0.

### 5.3 HITL State Persistence

Each of the three HITL checkpoints needs to persist its state so the pipeline can be resumed after human review. The existing LangGraph checkpoint pattern (used in `core/research/graphs/`) handles this. The key addition is that the brief review HITL (Checkpoint 2) is new and needs its own state schema — capturing the brief, the user's feedback, and the approval decision.

The API layer (`api/routes/`) needs new endpoints for each HITL checkpoint: one for topic approval (presenting the planner's selections and accepting approve/modify/reject), one for brief approval (presenting Agent 2's blueprint and accepting approve/feedback/reject), and the existing content review endpoint for final approval.

---

## 6. Module Structure and Boundaries

### 6.1 New Modules

The implementation should introduce the following new modules within the existing `core/content_engine/` directory.

A `context_router.py` module that contains the scorecard extraction logic, the full context extraction logic, and the prompt formatting functions for both phases. This module imports from `core/models/gap_analysis.py` (to understand input shapes) and defines its own lightweight output models (scorecards, worker contexts). It does NOT import from the prompts layer or the pipeline layer — it's a pure data transformation module.

A `strategic_planner.py` module (or rename the existing `planner.py`) that implements the v1.3 Strategic Planner agent — receiving a scorecard, calling the LLM, parsing the topic selections. The existing `planner.py` can be refactored: the current brief-generating logic moves to Agent 2, and the planner becomes a focused triage agent.

A `brief_builder.py` module that implements Agent 2 — receiving full query context, analyzing exemplars, and producing detailed content blueprints. This is the new module that takes over the "content architecture" responsibility from the planner.

Updated prompt modules in `core/content_engine/prompts/` — a `strategic_planner_prompts.py` for the triage-focused planner system/user prompts, and a `brief_builder_prompts.py` for Agent 2's prompts.

A `graph_v13.py` module (or extension of the existing `graph.py`) that implements the LangGraph state machine for the full v1.3 flow with three HITL checkpoints. Alternatively, three separate sub-graphs (topic approval, brief approval, content review) that the pipeline orchestrator composes.

### 6.2 Modified Modules

The `pipeline.py` top-level orchestrator needs significant restructuring. The current 4-stage linear flow becomes: Stage 0 (entry mode routing) → Stage 1 (Strategic Planner + HITL, autonomous mode only) → Stage 2 (Brief Builder + HITL) → Stage 3 (Content Workers) → Stage 4 (Evaluator with dual feedback loops) → Stage 5 (Final HITL Review) → Publish.

The `workers/dispatcher.py` needs to be updated to use Agent 2's richer briefs as input. The individual worker modules (outliner, drafter, enricher, formatter) need prompt updates to leverage the expanded structural targets and exemplar intelligence, but their core structure remains the same.

The `evaluator.py` needs the E-E-A-T dimension added and the feedback routing logic that distinguishes section-level edits from major direction changes.

### 6.3 Dependency Flow

The critical boundary to maintain is that data extraction modules (context_router) never import from prompt modules or pipeline modules. Prompt formatting modules never import from data access modules. The pipeline orchestrator is the integration layer that calls both. This enables independent testing of each layer.

The dependency graph should be: `pipeline.py` → imports → `context_router.py`, `strategic_planner.py`, `brief_builder.py`, `workers/dispatcher.py`, `evaluator.py`, `graph.py`. Each of those imports from `core/models/` for data shapes and `core/content_engine/prompts/` for LLM prompt construction. Nothing in `core/content_engine/` imports from `api/` — the API layer wraps the core, never the other way around.

---

## 7. Differences from v1.0 — Summary

For quick reference, here is a condensed summary of what changes between the current v1.0 pipeline and the v1.3 pipeline described in this document.

The Strategic Planner changes from "produces full content briefs from the entire gap analysis" to "performs triage on a lightweight scorecard and selects top-K topics." The data it receives shrinks from approximately 80-120K tokens to approximately 11K tokens.

A new agent (Agent 2, the Brief Builder) is introduced between the planner and the content workers. It receives full gap analysis detail for ONLY the approved queries and produces richer briefs than the v1.0 planner could.

Two new HITL checkpoints are added: one after topic selection (Checkpoint 1) and one after brief generation (Checkpoint 2), in addition to the existing final content review (Checkpoint 3). The v1.0 pipeline has only the final review.

The feedback loop from the evaluator is split into two paths: section-level edits (targeted revision of specific sections, routing to the appropriate sub-agent) and major direction changes (full re-brief, routing back to Agent 2).

A manual prompt entry mode is added, allowing users to bypass the autonomous planner and directly specify content topics, with the system running a single-query gap analysis before proceeding to Agent 2.

Context routing replaces context dumping — each agent receives exactly the data it needs, shaped specifically for its task, rather than receiving the entire analysis plus all research artifacts.

---

## 8. Implementation Priority

The recommended implementation order, based on dependencies and the principle of delivering value incrementally, is as follows.

First, implement the context routing layer (`context_router.py`) with the scorecard extractor and the full context extractor. These are pure data transformations with no LLM dependencies, so they're easy to test with fixture data. Write comprehensive tests using existing gap analysis fixture files.

Second, implement the refactored Strategic Planner that consumes scorecards instead of full analysis data. This can be tested against the existing planner by comparing topic selections — the triage quality should be equal or better with the scorecard input because the planner can now see all 200 queries instead of a truncated top-50.

Third, implement Agent 2 (the Brief Builder) as a new module. This is the most complex new agent and the one that most directly impacts output quality.

Fourth, add the two new HITL checkpoints (topic approval and brief approval) to the LangGraph graph.

Fifth, update the pipeline orchestrator to compose all stages with the new flow.

Sixth, add the manual prompt entry mode as an alternative pipeline entry point.

Seventh, refine the feedback loops in the evaluator to distinguish section-level edits from major direction changes.
