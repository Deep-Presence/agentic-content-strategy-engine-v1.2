# Content Generation Engine — Architecture & Implementation Plan

## 1. Design Philosophy

After researching Anthropic's "Building Effective Agents" guide, Langfuse's evaluation framework, and LangGraph's HITL patterns, here's the core principle: **start with the simplest solution that works, and add complexity only when it demonstrably improves outcomes.** Your vision maps well onto a hybrid of two proven Anthropic patterns:

- **Orchestrator-Workers** for the planning → parallel writing stage  
- **Evaluator-Optimizer** for the automated QA loop before human review  

Rather than building a fully autonomous multi-agent system from scratch, we should lean heavily on **deterministic workflows** with LLM calls at well-defined points, reserving true agentic behavior only where flexibility genuinely matters (i.e., the drafting sub-agent).

---

## 2. Architecture Overview — Four Stages

### Stage 1: Strategic Planner (Deterministic Workflow)

**Pattern:** Prompt Chaining (not an agent)  
**Why not an agent?** The planner's job is well-defined: consume fixed inputs (research artifacts + gap analysis), produce a structured content calendar. There's no need for tool use or dynamic decision-making.

**Implementation:**

```
Inputs → Content Strategy LLM Call → Content Calendar → Priority Scorer → Brief Queue
```

**What the planner produces (structured JSON output):**

```python
class ContentBrief(BaseModel):
    brief_id: str
    topic: str
    target_queries: List[str]           # From gap analysis query clusters
    target_cluster: str                  # Which cluster spec to match
    content_format: Literal["long_blog", "short_faq", "pillar_page", "comparison", "how_to"]
    funnel_stage: Literal["awareness", "consideration", "decision", "retention"]
    channel: Literal["blog", "help_center", "landing_page", "resource_hub"]
    priority_score: float                # Computed from gap magnitude × cluster opportunity
    structural_targets: StructuralTargets  # From ClusterContentSpec
    semantic_threshold: float            # Min embedding similarity to achieve
    word_count_range: Tuple[int, int]
    key_angles: List[str]               # Differentiation points from company context
    competitor_exemplars: List[str]      # Top cited URLs from gap analysis
```

**Cost/latency profile:** Single LLM call (Sonnet 4.5), ~30s, ~$0.05-0.10. This is a cheap, predictable step.

**Key design decision:** The planner should NOT use an agent loop. Instead, use a single well-prompted LLM call with structured output (Pydantic model). The gap analysis already provides all the data; the LLM just needs to synthesize a plan. If the output is bad, iterate on the prompt, don't add autonomy.

---

### Stage 2: Orchestrator-Workers (Parallel Content Production)

**Pattern:** Orchestrator-Workers from Anthropic's guide  
**This is where controlled parallelism lives.**

A dispatcher takes the priority-sorted brief queue and fans out N briefs to N independent worker sub-agents. Each worker is a self-contained **prompt chain** (not a free-running agent):

```
Brief → Outliner → Drafter → Fact Enricher → Formatter → Raw Draft
```

**Worker sub-agent internals (prompt chain, NOT an autonomous agent):**

| Step | Model | Purpose | Output |
|------|-------|---------|--------|
| **Outliner** | Sonnet 4.5 | Generate H2/H3 structure, section purposes, target structural signals | Outline JSON |
| **Drafter** | Sonnet 4.5 | Write each section following outline + style guide + company context | Markdown draft |
| **Fact Enricher** | Sonnet 4.5 + web_search | Verify claims, add statistics, cite authoritative sources | Enriched draft |
| **Formatter** | Haiku 4.5 | Apply structural signals (ordered lists, headers, stats formatting) | Final draft |

**Why a prompt chain and not a free agent?** Each step is well-defined with clear inputs and outputs. A free agent would waste tokens deciding what to do next. Prompt chaining gives us predictability and makes each step independently testable and traceable.

**Parallelism strategy:**

```python
async def produce_content_batch(briefs: List[ContentBrief], max_concurrent: int = 3):
    semaphore = asyncio.Semaphore(max_concurrent)
    async def produce_one(brief: ContentBrief):
        async with semaphore:
            return await run_worker_chain(brief)
    return await asyncio.gather(*[produce_one(b) for b in briefs])
```

**Cost/latency profile per article:**
- Outliner: ~15s, ~$0.03
- Drafter: ~60-90s, ~$0.15-0.30 (longest step)
- Fact Enricher: ~30-45s, ~$0.08-0.15
- Formatter: ~10s, ~$0.01 (Haiku)
- **Total per article: ~2-3 min, ~$0.30-0.60**
- **5 articles in parallel (semaphore=5): ~3 min wall-clock, ~$1.50-3.00**

---

### Stage 3: Evaluator-Optimizer Loop (Automated QA)

**Pattern:** Evaluator-Optimizer from Anthropic's guide  
**This is where the real quality happens.**

Each draft goes through a battery of automated evaluations. If it fails, it loops back to the drafter with specific feedback. Max 2 revision cycles (to cap costs).

**Evaluation dimensions (run in parallel for speed):**

#### A. Structural Signals Check (Deterministic — no LLM needed)
```python
class StructuralEval(BaseModel):
    header_count: int
    paragraph_count: int
    list_item_count: int
    stat_count: int            # regex for numbers + % patterns
    citation_count: int
    word_count: int
    claims_per_paragraph: float
    
    def passes(self, targets: StructuralTargets) -> bool:
        # Compare against ClusterContentSpec thresholds
```
**Cost:** Zero (pure code). **Latency:** <1s.

#### B. Semantic Proximity Test (Embedding comparison)
Embed the draft, compare against the target query cluster centroid. The draft should achieve at minimum the `min_similarity_threshold` from the cluster spec.
```python
draft_embedding = embed(draft_text)
similarity = cosine_similarity(draft_embedding, cluster_centroid)
passes = similarity >= brief.semantic_threshold
```
**Cost:** ~$0.001 per embedding call. **Latency:** ~2s.

#### C. Style & Brand Alignment (LLM-as-Judge)
A separate LLM call evaluates the draft against the style guide:
- Tone match (1-5 scale)
- Voice consistency  
- Jargon appropriateness for target persona
- CTA alignment with funnel stage

**Prompt pattern:** Provide the style guide + draft, ask for structured score + specific feedback.
**Cost:** ~$0.03 (Haiku). **Latency:** ~5s.

#### D. Factual Grounding Check (LLM-as-Judge)
Evaluates whether claims in the draft are grounded in company context or cited sources, not hallucinated.
**Cost:** ~$0.05 (Sonnet). **Latency:** ~10s.

**Gate logic:**
```python
if all_evals_pass:
    send_to_human_review(draft)
elif revision_count < MAX_REVISIONS (2):
    feedback = compile_eval_feedback(eval_results)
    revised_draft = await revise_draft(draft, feedback, brief)
    # Re-evaluate
else:
    flag_for_manual_intervention(draft, eval_results)
```

**Total eval cost per draft:** ~$0.10-0.15  
**With 1 revision cycle:** ~$0.50-0.80 additional (re-drafting + re-eval)

---

### Stage 4: Human-in-the-Loop (LangGraph interrupt)

**Pattern:** LangGraph's `interrupt()` mechanism — the graph pauses, persists state, waits for human input.

**Three human actions:**

| Action | Effect |
|--------|--------|
| **Approve** | Draft proceeds to CMS publish |
| **Edit with Comment** | Human edits text + adds feedback note → revised draft re-enters eval loop at Stage 3 |
| **Reject** | Draft is discarded with reason → logged for planner feedback |

**Implementation with LangGraph:**

```python
from langgraph.types import interrupt, Command

def human_review_node(state: ContentState) -> Command:
    decision = interrupt({
        "draft": state["final_draft"],
        "eval_scores": state["eval_results"],
        "brief": state["brief"],
        "action_options": ["approve", "edit", "reject"]
    })
    
    if decision["action"] == "approve":
        return Command(goto="publish_to_cms")
    elif decision["action"] == "edit":
        return Command(
            goto="evaluator_loop",
            update={"draft": decision["edited_draft"], "human_notes": decision["notes"]}
        )
    else:  # reject
        return Command(goto="log_rejection")
```

**Key design principle from Elastic's HITL guide:** HITL interventions should be *reactive* and *meaningful* — not a rubber-stamp checkpoint on every workflow. The automated eval loop in Stage 3 should catch 80%+ of issues, so the human reviewer is making high-value decisions, not catching typos.

**Dashboard requirements:**
- Side-by-side: Brief spec vs. Draft
- Eval scores with visual indicators (pass/fail per dimension)
- Inline editing with comment threading
- Batch review mode (review multiple drafts in queue)

---

## 3. Tracing & Observability with Langfuse

Based on Langfuse's latest agent evaluation framework (November 2025 launch), here's the tracing plan:

### Trace Hierarchy

```
Session: content_batch_{batch_id}
  └─ Trace: plan_{batch_id}           [Stage 1: Planner]
  │    └─ Generation: strategy_llm_call
  │    └─ Span: priority_scoring
  │
  └─ Trace: produce_{brief_id}         [Stage 2: Worker]
  │    └─ Span: outliner
  │    │    └─ Generation: outline_llm_call
  │    └─ Span: drafter  
  │    │    └─ Generation: draft_llm_call
  │    └─ Span: fact_enricher
  │    │    └─ Generation: enrichment_llm_call
  │    │    └─ Span: web_search_calls
  │    └─ Span: formatter
  │         └─ Generation: format_llm_call
  │
  └─ Trace: evaluate_{brief_id}        [Stage 3: Evaluator]
  │    └─ Span: structural_check       (score attached)
  │    └─ Span: semantic_proximity     (score attached)
  │    └─ Generation: style_judge      (score attached)
  │    └─ Generation: factual_judge    (score attached)
  │    └─ Span: revision_cycle_{n}     (if revision needed)
  │
  └─ Trace: review_{brief_id}          [Stage 4: Human Review]
       └─ Span: human_decision         (user_feedback score)
```

### Scores to Track in Langfuse

| Score Name | Type | Source | Level |
|------------|------|--------|-------|
| `structural_pass` | Boolean | Code | Trace |
| `semantic_similarity` | Numeric (0-1) | Embedding | Trace |
| `style_alignment` | Numeric (1-5) | LLM-as-Judge | Trace |
| `factual_grounding` | Numeric (1-5) | LLM-as-Judge | Trace |
| `revision_count` | Numeric (0-2) | Code | Trace |
| `human_decision` | Categorical (approve/edit/reject) | User Feedback | Trace |
| `total_cost` | Numeric ($) | Langfuse auto | Session |
| `total_latency` | Numeric (s) | Langfuse auto | Session |

### Instrumentation Pattern (Python)

```python
from langfuse import observe, get_client

@observe(name="draft_content")
async def run_worker_chain(brief: ContentBrief) -> Draft:
    langfuse = get_client()
    langfuse.update_current_trace(
        metadata={"brief_id": brief.brief_id, "cluster": brief.target_cluster},
        tags=["content_generation", brief.content_format]
    )
    
    outline = await generate_outline(brief)
    draft = await write_draft(outline, brief)
    enriched = await enrich_facts(draft, brief)
    formatted = await format_draft(enriched, brief)
    return formatted

@observe(name="outliner")
async def generate_outline(brief: ContentBrief) -> Outline:
    # LLM call automatically traced as a generation
    ...
```

### Evaluation Datasets in Langfuse

Following Langfuse's 3-phase evaluation approach:

**Phase 1 (Now):** Manual trace inspection — look at 20-30 traces, identify failure patterns.

**Phase 2 (After first batch):** Build a "gold standard" dataset:
```python
langfuse.create_dataset(
    name="content_quality_benchmark",
    description="Curated brief→draft pairs with human quality scores",
    metadata={"version": "v1", "date": "2026-02"}
)
```

**Phase 3 (Scaling):** Automated offline evaluation — run new prompt versions against the benchmark dataset, compare scores across experiments.

---

## 4. Cost & Latency Estimates

### Per-Article Budget

| Stage | LLM Calls | Cost | Latency |
|-------|-----------|------|---------|
| Planning (amortized) | 1 (shared across batch) | ~$0.01 | ~1s |
| Outliner | 1 × Sonnet | ~$0.03 | ~15s |
| Drafter | 1 × Sonnet | ~$0.15-0.30 | ~60-90s |
| Fact Enricher | 1 × Sonnet + search | ~$0.08-0.15 | ~30-45s |
| Formatter | 1 × Haiku | ~$0.01 | ~10s |
| Eval: Style Judge | 1 × Haiku | ~$0.03 | ~5s |
| Eval: Factual Judge | 1 × Sonnet | ~$0.05 | ~10s |
| Eval: Embeddings | 2 API calls | ~$0.002 | ~2s |
| **Total (no revision)** | **~7 calls** | **~$0.35-0.60** | **~2-3 min** |
| **With 1 revision** | **~12 calls** | **~$0.70-1.20** | **~4-5 min** |

### Batch Economics (10 articles)

| Scenario | Parallel Workers | Wall-Clock | Total Cost |
|----------|-----------------|------------|------------|
| Sequential | 1 | ~30-50 min | $3.50-6.00 |
| Moderate parallel | 3 | ~12-18 min | $3.50-6.00 |
| Aggressive parallel | 5 | ~8-12 min | $3.50-6.00 |

The parallelism doesn't change cost — it reduces wall-clock time. Rate limits are the real bottleneck. With 3-5 concurrent workers, you'll stay well within standard API rate limits.

---

## 5. What to Build vs. What to Avoid

### Build This

1. **Deterministic planner** (prompt chain, not an agent) — structured JSON output
2. **Worker prompt chains** with clear step boundaries — each step independently testable  
3. **Parallel dispatch** with asyncio semaphore — control concurrency
4. **Automated eval battery** — mix of code checks + LLM-as-judge
5. **LangGraph workflow** with interrupt at human review — state persisted to PostgreSQL
6. **Langfuse instrumentation** from day one — every LLM call traced with scores
7. **Pydantic models** for every intermediate artifact — type safety across the pipeline

### Avoid This

1. **Don't build a "meta-agent" that decides what pattern to use** — this adds latency and cost with no benefit. Your workflow is predictable enough to hardcode.
2. **Don't give workers internet access for "research"** — the gap analysis already provides the competitive intelligence. Web search in the enricher should be limited to fact verification only.
3. **Don't build an elaborate revision agent** — cap at 2 revision cycles. If it can't pass after 2 revisions, the brief is bad, not the draft. Flag for human intervention.
4. **Don't use CrewAI/AutoGen/multi-agent frameworks** — they add abstraction without value for this use case. Raw LangGraph + asyncio gives you full control and debuggability.
5. **Don't batch human review** — let humans review one at a time as drafts complete. The interrupt mechanism naturally supports this.

---

## 6. Implementation Sequence

### Sprint 1: Foundation (Week 1-2)
- [ ] Define all Pydantic models (ContentBrief, Outline, Draft, EvalResult)
- [ ] Build the Strategic Planner as a single LLM call with structured output
- [ ] Set up Langfuse project + basic instrumentation decorator
- [ ] Write the structural eval (pure Python, no LLM)

### Sprint 2: Worker Chain (Week 3-4)
- [ ] Build Outliner step with tests
- [ ] Build Drafter step with style guide injection
- [ ] Build Fact Enricher with limited web search
- [ ] Build Formatter step (Haiku)
- [ ] Wire up the 4-step chain with Langfuse tracing

### Sprint 3: Eval Loop + HITL (Week 5-6)
- [ ] Build semantic proximity eval
- [ ] Build LLM-as-judge evals (style + factual)
- [ ] Implement evaluator-optimizer loop with max 2 revisions
- [ ] Build LangGraph workflow with interrupt for human review
- [ ] Build minimal review dashboard (or integrate with existing UI)

### Sprint 4: Integration + Polish (Week 7-8)
- [ ] End-to-end pipeline: gap analysis output → content generation → human review
- [ ] Parallel dispatch with rate limiting
- [ ] CMS publish integration
- [ ] Langfuse dashboard setup (cost tracking, quality metrics)
- [ ] Build first evaluation dataset from human review decisions

---

## 7. Model Selection Strategy

| Task | Recommended Model | Rationale |
|------|------------------|-----------|
| Strategic Planning | Sonnet 4.5 | Structured reasoning, cost-efficient |
| Outline Generation | Sonnet 4.5 | Needs understanding of structural signals |
| Content Drafting | Sonnet 4.5 | Best quality/cost ratio for long-form writing |
| Fact Enrichment | Sonnet 4.5 + web_search | Needs grounding capability |
| Formatting | Haiku 4.5 | Simple transformation, speed matters |
| Style Evaluation | Haiku 4.5 | Scoring task, doesn't need deep reasoning |
| Factual Evaluation | Sonnet 4.5 | Needs to reason about claim validity |
| Revision Feedback | Sonnet 4.5 | Needs to synthesize multiple eval failures |

**Routing pattern:** Use Haiku for fast, cheap scoring tasks. Use Sonnet for anything requiring reasoning or long-form generation. Reserve Opus for potential future use in the planner if Sonnet's strategic planning proves insufficient.

---

## 8. Key Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM-as-judge disagrees with human | Eval loop false passes/fails | Build calibration dataset from first 50 human reviews |
| Drafter ignores structural targets | Content doesn't match citation patterns | Include exemplar snippets from gap analysis in drafter prompt |
| Revision loop doesn't converge | Infinite cost on bad briefs | Hard cap at 2 revisions + flag for human |
| Rate limits at scale | Pipeline stalls | Semaphore-controlled concurrency + exponential backoff |
| Style drift across articles | Inconsistent brand voice | Include 2-3 approved exemplar articles in every drafter prompt |

---

## 9. References

- [Anthropic: Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents) — Orchestrator-Workers + Evaluator-Optimizer patterns
- [Anthropic: Effective Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — Managing finite context windows
- [Anthropic: Writing Tools for Agents](https://www.anthropic.com/engineering/writing-tools-for-agents) — Tool evaluation best practices
- [Langfuse: Agent Evaluation Guide](https://langfuse.com/guides/cookbook/example_pydantic_ai_mcp_agent_evaluation) — 3-phase eval approach
- [Langfuse: Systematic Evaluation](https://langfuse.com/blog/2025-11-06-experiment-interpretation) — Experiment interpretation framework
- [LangGraph: Human-in-the-Loop](https://docs.langchain.com/oss/python/langchain/human-in-the-loop) — interrupt/resume patterns
