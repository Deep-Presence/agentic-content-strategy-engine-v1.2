# Skill: LLM Prompt Engineering

> Prompts are the highest-leverage code in this system. A 10-word change to the s2 query gen prompt changes the output of every downstream step. Treat prompt changes like database migrations — plan, test, compare, document.

---

## Prompt Inventory

Every LLM prompt in the codebase and its impact radius:

| Prompt | File | Model | Impact |
|--------|------|-------|--------|
| Query generation (s2) | `core/gap_analysis/steps/s2_generate_queries.py` `_QUERY_GEN_PROMPT` | `gpt-4o` | Changes all 150 queries → affects s3, s4, s5, s6, s8 |
| Query dedup (s2 pass 2) | `s2_generate_queries.py` `_DEDUP_PROMPT` | `gpt-4o` | Filters/reranks queries |
| Report executive summary (s8) | `core/gap_analysis/steps/s8_generate_report.py` `_build_llm_summary_prompt` | `gpt-4o` | Changes executive summary + recommendations in final report |
| Reddit thread draft | `core/reddit_hil/graph.py` `_llm_select_and_draft` | `gemini-3-flash-preview` | Changes Reddit reply drafts |
| Company research agent | `core/research/agents/company_agent.py` | `gemini-3-flash-preview` | Changes company context artifact |
| Persona research agent | `core/research/agents/persona_agent.py` | `gemini-3-flash-preview` | Changes persona artifacts → affects s2 query gen |
| Style guide research agent | `core/research/agents/style_guide_agent.py` | `gemini-3-flash-preview` | Changes writing style → affects Reddit drafts |

---

## Rules for Prompt Changes

### Rule 1: Never Edit a Prompt Without A/B Comparison

Before deploying a prompt change, you MUST compare outputs:

```bash
# 1. Run pipeline with CURRENT prompt, save output
python -c "
from core.gap_analysis.steps.s2_generate_queries import generate_queries
from core.models.gap_analysis import GapAnalysisInput
input_data = GapAnalysisInput(company_name='ramp', domain='ramp.com')
queries_old = generate_queries(input_data)
import json; open('/tmp/queries_old.json','w').write(json.dumps([q.model_dump(mode='json') for q in queries_old], indent=2))
"

# 2. Apply your prompt change

# 3. Run pipeline with NEW prompt, save output
python -c "
# ... same code ...
queries_new = generate_queries(input_data)
import json; open('/tmp/queries_new.json','w').write(json.dumps([q.model_dump(mode='json') for q in queries_new], indent=2))
"

# 4. Compare
diff /tmp/queries_old.json /tmp/queries_new.json | head -100
```

### Rule 2: Document What Changed and Why

Every prompt change gets a decision log entry:

```json
{
  "id": "D{N}",
  "timestamp": "2026-02-15T10:00:00Z",
  "task": "T-v3-X: {task name}",
  "approach": "Modified s2 _QUERY_GEN_PROMPT to {what changed}",
  "rationale": "The old prompt was producing {specific problem}. The new prompt fixes this by {mechanism}.",
  "alternatives_rejected": [
    "Keeping old prompt — {why not}",
    "Changing model instead of prompt — {why not}"
  ],
  "outcome": "A/B comparison showed: {quantified difference}",
  "reversible": true,
  "approved_by": "Aryan"
}
```

### Rule 3: One Change at a Time

Never change the prompt AND the model in the same task. If the output changes, you won't know which caused it.

### Rule 4: Prompt Changes Require Approval

All prompt changes fall under the Decision Protocol. Present the DECISION NEEDED format and wait for Aryan's approval before deploying.

---

## How to Evaluate Prompt Quality

### For s2 (Query Generation)

Good queries should:
- Cover all 9 clusters with balanced distribution
- Match the intent pattern of each cluster (Mechanism queries start with "How does...", Boundary with "What are the risks/limitations...")
- Use category-level language, NOT brand names (except C8 Branded Evaluation and C2 Boundary edge cases)
- Sound like something a real B2B buyer would type
- Be unique — no semantic duplicates

**Evaluation checklist:**
```python
import json
from collections import Counter

queries = json.loads(open("/tmp/queries_new.json").read())

# 1. Cluster coverage
cluster_counts = Counter(q["cluster_name"] for q in queries)
print("Cluster distribution:", dict(cluster_counts))
# Bad: any cluster with 0 or <5% of queries
# Good: all clusters have 8-20% of queries

# 2. Brand name leakage
brand_names = ["ramp", "carta", "brex", "divvy", "navan"]  # your client + competitors
for q in queries:
    text = q["query_text"].lower()
    for brand in brand_names:
        if brand in text and q["cluster_name"] not in ["Branded Evaluation"]:
            print(f"BRAND LEAK: {q['query_text']} in cluster {q['cluster_name']}")

# 3. Uniqueness
texts = [q["query_text"].lower().strip() for q in queries]
dupes = [t for t in texts if texts.count(t) > 1]
print(f"Duplicates: {len(set(dupes))}")
```

### For s8 (Report Generation)

Good reports should:
- Have a non-empty executive summary
- Have 5 specific recommendations (not generic advice)
- Reference actual cluster names and gap scores from the analysis
- Not hallucinate data points not in the analysis

**Evaluation checklist:**
```python
report = json.loads(open("artifacts/gap_analysis/ramp/gap_report.json").read())

# 1. Executive summary exists and is substantive
summary = report.get("executive_summary", "")
assert len(summary) > 100, "Executive summary too short"
assert "ramp" in summary.lower() or "expense" in summary.lower(), "Summary not specific to client"

# 2. Recommendations reference real clusters
clusters_in_analysis = {g["cluster_name"] for g in report.get("gaps", [])}
for rec in report.get("recommendations", []):
    cluster = rec.get("target_cluster", "")
    assert cluster in clusters_in_analysis, f"Recommendation targets unknown cluster: {cluster}"

# 3. No all-zero stats
prox = report.get("proximity_stats", {})
assert prox.get("citation_similarity_mean", 0) > 0, "Stats are all zero"
```

---

## Good vs Bad Prompt Patterns

### Query Generation (s2)

**BAD — Vague instruction, no structure:**
```
Generate search queries for {company_name}. 
Make them relevant to B2B buyers.
```
Problems: No cluster taxonomy, no brand rules, no persona context, LLM invents its own structure.

**GOOD — Current prompt pattern (abbreviated):**
```
You are a search behavior expert for B2B buyers. Generate realistic search queries 
that a real person in this role would type into Google, Gemini, Claude, ChatGPT, or Perplexity.

PERSONA (condensed): {persona_condensed}
COMPANY: {company details}
QUERY CLUSTER TAXONOMY: {clusters_with_citation_behavior}

Return JSON only, no prose. Format: {exact schema}

Constraints:
- Total queries <= {max_queries}
- Cover all clusters with balanced coverage
- Each query must be unique and actionable

CRITICAL — Brand / Company Name Usage Rules:
{explicit rules per cluster}
```
Why it works: Specific role, structured input, exact output schema, explicit constraints, guardrails for known failure modes (brand leakage).

### Report Summary (s8)

**BAD — Asking LLM to generate the whole report:**
```
Here is the analysis data. Write a comprehensive gap analysis report.
```
Problems: LLM hallucinates stats, invents data points, structures it however it wants, can't be validated.

**GOOD — Current pattern: programmatic report + LLM for summary only:**
```
Given the analysis data below, produce:
1. An executive summary (4-6 sentences)
2. Top 5 prioritized content recommendations, each with:
   - A specific content piece title idea
   - Target cluster name
   - Key structural signals to match
   - Expected impact reasoning (1-2 sentences)

Return JSON only: {exact schema}

ANALYSIS DATA: {computed data, not raw}
```
Why it works: LLM only does what it's good at (synthesis, writing). All numerical data comes from code. Output is JSON-validated. Scope is narrow and auditable.

---

## Prompt Change Template

When proposing a prompt change, use this template in the plan:

```
PROMPT CHANGE PROPOSAL:

LOCATION: {file}:{variable_name}
CURRENT BEHAVIOR: {what the prompt currently produces}
PROBLEM: {specific failure mode — with example output}
PROPOSED CHANGE: {exact diff — old text → new text}
EXPECTED BEHAVIOR: {what the prompt should produce instead}

A/B TEST PLAN:
1. Run with current prompt → save output to /tmp/{step}_before.json
2. Apply change
3. Run with new prompt → save output to /tmp/{step}_after.json
4. Compare using evaluation checklist above
5. Present comparison to Aryan

ROLLBACK: Revert the prompt string (no other changes needed)
```

---

## Common Prompt Failure Modes in This Codebase

1. **Brand name leakage** — The s2 prompt has extensive brand rules, but LLMs still sneak brand names into Feature Verification (C9) queries. Fix: add more explicit negative examples.

2. **JSON extraction failures** — Both s2 and s8 use `_extract_json()` to pull JSON from LLM output. LLMs sometimes return markdown-wrapped JSON (```json ... ```) or extra prose before/after. The regex handler covers most cases but can fail on nested braces.

3. **Empty recommendations** — s8 LLM sometimes returns empty or generic recommendations when the analysis data is thin. Fix: give the LLM more context (top gap briefs, not just summary stats).

4. **Inconsistent cluster names** — If the s2 prompt doesn't match the taxonomy file exactly, queries get assigned to non-existent clusters. Always interpolate cluster names from `_load_taxonomy()`, never hardcode.

5. **Token overflow** — The s2 prompt with full persona + taxonomy + brand rules can exceed context windows for smaller models. Monitor prompt token count and truncate persona if needed.