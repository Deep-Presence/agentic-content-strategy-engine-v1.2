"""Prompts for the Factual Judge evaluator."""

FACTUAL_JUDGE_SYSTEM_PROMPT = """\
You are an expert fact-checking evaluator. Your task is to evaluate the factual
accuracy and grounding of a B2B SaaS article.

## Evaluation Criteria (score 0.0 to 1.0)

1. **Claim accuracy** (0.30): Are factual claims correct and verifiable?
2. **Source quality** (0.25): Are sources cited? Are they authoritative?
3. **Recency** (0.20): Are statistics and data current (within 2 years)?
4. **Completeness** (0.25): Are key claims backed by evidence? Any unsupported assertions?

## Output Format

Respond with ONLY valid JSON:

```json
{
  "score": 0.0-1.0,
  "passed": true/false,
  "feedback": "Specific feedback on factual issues found",
  "criteria_scores": {
    "claim_accuracy": 0.0-1.0,
    "source_quality": 0.0-1.0,
    "recency": 0.0-1.0,
    "completeness": 0.0-1.0
  },
  "flagged_claims": [
    {"claim": "the claim text", "issue": "what's wrong with it"}
  ]
}
```

Score >= 0.7 is a pass. Be specific — cite exact claims that are problematic.
"""


def build_factual_judge_user_prompt(
    *,
    content_markdown: str,
    title: str,
    company_name: str,
    domain: str,
    key_topics: list[str],
) -> str:
    """Build the user prompt for factual evaluation."""
    topics_str = ", ".join(key_topics) if key_topics else "the article's topics"

    return f"""\
## Article to Evaluate

Title: {title}
Company: {company_name} ({domain})
Topics: {topics_str}

{content_markdown}

Evaluate the factual accuracy and grounding of this article.
Flag any unsupported claims, outdated statistics, or questionable assertions.
"""


# ---------------------------------------------------------------------------
# Hub getter (opt-in via settings.langsmith_use_hub)
# ---------------------------------------------------------------------------

_HUB_NAME = "deep-presence/factual-judge-system"


def get_factual_judge_system_prompt() -> str:
    """Get factual judge system prompt from Hub or local fallback."""
    from core.content_engine.prompt_registry import get_prompt

    return get_prompt(_HUB_NAME, FACTUAL_JUDGE_SYSTEM_PROMPT)
