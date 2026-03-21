You're right — the code is downstream of the thinking. Let me give you the proper architectural description that addresses all these dimensions.

---

## The Fundamental Architectural Insight

The core problem you're solving is really a **data fan-out and fan-in** problem. You have a single, massive artifact (the gap analysis output — 200 queries, each with exemplars, structural signals, content briefs) and two consumers with radically different appetites. The Strategic Planner needs to scan the *entire* dataset but only cares about a handful of fields per record. The Worker Agent needs the *complete* record but only for a handful of queries. This is the classic wide-and-shallow versus narrow-and-deep access pattern, and the architectural answer is to build a context routing layer that sits between your gap analysis output and your content engine agents, shaping data for each consumer.

Think of it like a database view. You don't change the underlying table — you create purpose-built projections of the same data for different consumers. The gap analysis pipeline writes its full output once, and the context router reads from it twice, extracting different slices each time.

## The Three-Layer Structure

The system should be organized into three conceptual layers, each with a clear responsibility boundary.

**Layer 1: The Scorecard Extractor.** This is a pure data transformation module. It takes the full gap analysis output (whether from JSON or ORM — more on that choice below) and produces a lightweight summary I'd call a "PlannerScorecard." This scorecard contains two things: a per-query record with just the six fields the planner needs (query ID, query text, cluster name, gap score, company similarity, citation similarity, interpretation, plus a couple of data-richness indicators like exemplar count), and a per-cluster aggregate that rolls up gap statistics, counts of significant gaps, and the dominant content/authority types for each cluster. The scorecard extractor's contract is simple: full analysis in, compact scorecard out. It knows nothing about prompts, LLM calls, or agents. It's a pure function.

**Layer 2: The Prompt Formatter.** This layer takes a scorecard (or a full worker context) and renders it into the specific text format that the LLM agent will consume. For the planner, this means rendering the scorecard as markdown tables — a cluster overview table and a per-query table. Tables are significantly more token-efficient than JSON for tabular data because you avoid repeated keys. The formatter for the worker agent is different: it renders the full exemplar data, structural signals, and content brief as structured sections with clear headers. The key modularity principle here is that the formatter is *separate* from the extractor. If you later decide to change from markdown tables to a structured XML format or even a JSON array for the planner, you only change the formatter, not the extraction logic.

**Layer 3: The Context Router.** This is the orchestration-level component that decides *when* to call each extractor and *who* gets what. In the flow from your Excalidraw diagram, the router is invoked twice. The first invocation happens when the content engine pipeline starts: the router calls the scorecard extractor, feeds the result through the planner formatter, and passes it to the Strategic Planner agent. The second invocation happens after HITL approval: the router receives the list of approved query IDs, calls a targeted extractor that pulls full context for *only* those IDs, formats each one for the worker, and dispatches them to the parallel worker agents.

## How This Connects With Your Existing Data Layer

This is where the JSON vs. ORM decision becomes critical, and the answer is actually "both, but differently for each phase."

**For Phase 1 (Scorecard Extraction), use the ORM — this is where it truly shines.** Your `gap_analysis/persistence.py` already persists `QueryGap` records to the database with columns for `query_id`, `query_text`, `cluster_name`, `best_company_similarity`, `avg_citation_similarity`, `gap`, and `classification`. That's almost exactly the scorecard schema. A single SQL query with column selection — essentially a `SELECT query_id, query_text, cluster_name, gap, best_company_similarity, avg_citation_similarity, classification FROM query_gaps WHERE run_id = ?` — gives you the planner's entire input dataset in one database round-trip. The database returns only the columns you asked for, which means you never load the 20MB of exemplar blobs, content brief JSON, or embedding vectors into memory. This is dramatically faster than loading the full `analysis.json` from disk, parsing it, and then discarding 95% of the fields in Python.

For the cluster summaries, you can either pre-compute them during gap analysis persistence (adding a `cluster_summary` table that gets populated in your `persist_s6` function) or compute them at query time with a SQL aggregate: `SELECT cluster_name, AVG(gap), MAX(gap), COUNT(*) FILTER (WHERE classification = 'significant_gap') FROM query_gaps WHERE run_id = ? GROUP BY cluster_name`. The database does this aggregation far more efficiently than loading all 200 records into Python and grouping them yourself.

The existing `db_gap_data.py` service already has repository methods for querying gaps by run — you can add a lightweight `get_scorecard_data(run_id)` method that returns just the columns needed. This connects directly with your `GapAnalysisRepository` pattern.

**For Phase 2 (Worker Full Context), you have two viable paths, and the right choice depends on where you are in the JSON-to-DB migration.**

If you're still primarily on filesystem storage, the worker context loader should read `gap_analysis_complete.json` (your Tier 1 full-fidelity file) but with a critical optimization: don't deserialize the entire file. Instead, use a streaming JSON parser or load the file once at pipeline start and keep it in memory as a dict, then do dictionary lookups by query_id for the approved queries. Since you only need 4-6 queries out of 200, the filtering is trivial.

If you've migrated to the database, the worker context loader should query `query_gaps` joined with `query_exemplars` and `cluster_specs`, filtered by the approved query IDs. This is where the ORM earns its keep for the second time — the join between `query_gaps` and `query_exemplars` is exactly the kind of operation that a relational database handles natively, and the `WHERE query_gap_id IN (...)` filter ensures you only load exemplar data for the approved queries, not all 200 × 5 = 1000 exemplar rows.

**The hybrid pattern for the transition period** is to have the scorecard extractor accept a data source interface — either a dict (loaded from JSON) or a repository instance (querying the DB). This way your pipeline code says "give me the scorecard for run X" and the underlying implementation can be swapped between JSON and ORM without changing the extraction logic or the prompt formatting. Your existing codebase already has a pattern for this in how `gap_data_service.py` abstracts between filesystem-based and DB-based data retrieval.

## Modularity and Boundary Design

The key modularity principle is that each of these three layers should live in its own module and communicate through well-defined data models, not raw dicts. Here's how I'd map it to your existing directory structure.

The scorecard extractor and worker context extractor should live together in a single module within `core/content_engine/`, because they're both "read from gap analysis, project for content engine consumers." Think of it as the content engine's data access layer for gap analysis artifacts. It imports from `core/models/gap_analysis.py` (to understand the input shapes like `QueryGap`, `ClusterContentSpec`, `AnalysisResult`) and defines its own lightweight output models (the scorecard and worker context structures) that are internal to the content engine.

The prompt formatter functions should live alongside the existing prompt modules in `core/content_engine/prompts/`. The planner's scorecard formatter goes near the planner prompts. The worker's full-context formatter goes near the worker prompts. Each formatter takes the typed output from the extractor and produces a string — that's its entire job.

The context router — the orchestration logic that calls extractors and formatters at the right times — should be called from the pipeline itself (`core/content_engine/pipeline.py`), specifically in the `run_content_generation` function. Right now, your pipeline loads all gap analysis data at the top and passes it everywhere. The router changes this to a lazy loading pattern: load the scorecard at Stage 1, then load full context for approved queries only at Stage 2. The pipeline function becomes the integration point.

The critical boundary to maintain is that the scorecard extractor and the worker context extractor should **never import from the prompts layer or the pipeline layer**. They're pure data transformations. Similarly, the formatters should never import from the data access layer — they receive already-extracted data and render it. This separation means you can test each piece independently: test the extractor with a fixture `analysis_json`, test the formatter with a fixture scorecard, test the router with mock extractors.

## Latency Considerations

There are three latency dimensions to think about here.

**Data loading latency.** This is where the JSON vs. ORM choice has the biggest impact. Loading a 20MB `analysis.json` from disk, parsing it into a Python dict, and then iterating over 200 gap entries takes measurable time — potentially 1-2 seconds depending on I/O. A targeted SQL query that returns only the 6 scorecard columns for 200 rows finishes in single-digit milliseconds. For Phase 2, loading full context for 5 queries from the database with a filtered join is also sub-100ms, whereas filtering a 20MB dict in Python is slower because you've already paid the full deserialization cost. If you're serious about latency, the database path wins decisively for both phases.

**LLM input latency.** Token count directly impacts LLM response time. A 13K-token input to the planner will return significantly faster than a 70K-token input. With Sonnet 4.5, the time-to-first-token scales roughly linearly with input length for large contexts. So the scorecard approach doesn't just save you money per call — it makes the planner respond faster, which matters for the user experience because this call happens before the first HITL checkpoint.

**Pipeline-level latency.** The two-phase loading adds a small amount of orchestration complexity (an extra data access call after HITL approval), but it removes a much larger source of waste: the current pipeline loads everything upfront whether or not the worker will need it. If the human rejects the planner's selections and asks for a re-plan, the current approach has already loaded all the exemplar data for nothing. The two-phase approach only pays the cost of full context loading after approval, which means rejected/retried planning cycles are cheap.

## What About the Manual Prompt Path?

Your Excalidraw diagram shows a second pipeline variant — the "Manual Prompt based content engine" where a human enters a topic directly instead of using the autonomous planner. In this path, the gap analysis runs on just the user's single prompt rather than 200 queries. The context routing architecture still applies here, but Phase 1 is trivially small (1 query, so the scorecard is just one row) and Phase 2 is essentially the full pipeline for that single query. The beauty of having the scorecard extractor and worker context extractor as separate functions is that they work identically whether you pass them an analysis with 200 queries or 1 — the logic is the same, the volume is different. So the manual path can reuse the exact same modules without any special-casing.

## Summarizing the Design Principles

The whole architecture rests on three principles. First, **each agent gets exactly the context it needs** — no more, no less. The planner gets a scannable summary for triage; the worker gets deep detail for blueprint construction. Second, **the HITL boundary is your natural context loading boundary** — you defer expensive data loading until after human approval, which saves both tokens and compute on rejected cycles. Third, **the data access layer is independent of the prompt layer** — extraction and formatting are separate concerns, which means you can change your data storage (JSON to ORM) or your prompt format (tables to structured XML) independently without cascading changes.

This design lets the Strategic Planner see all 200 queries clearly in roughly 11K tokens instead of struggling with a truncated, noisy 70K-token dump, which is exactly what your Excalidraw diagram intends — a sharp, focused triage agent that hands off to deep-context workers after human approval.