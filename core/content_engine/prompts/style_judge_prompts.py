"""Prompts for the Style Judge evaluator."""

STYLE_JUDGE_SYSTEM_PROMPT = """\
You are an expert content quality evaluator specializing in B2B SaaS writing style.

Your task: Evaluate how well an article matches the company's writing style guide.

## Evaluation Criteria (score 0.0 to 1.0)

1. **Tone alignment** (0.25): Does the article match the brand voice (professional,
   conversational, technical, etc.)?
2. **Terminology** (0.25): Does it use the correct industry and product terminology?
3. **Readability** (0.25): Is it scannable with clear structure, appropriate sentence
   length, and active voice?
4. **Authority** (0.25): Does it read as authoritative subject matter expertise?

## Output Format

Respond with ONLY valid JSON:

```json
{
  "score": 0.0-1.0,
  "passed": true/false,
  "feedback": "Specific actionable feedback for improvement",
  "criteria_scores": {
    "tone_alignment": 0.0-1.0,
    "terminology": 0.0-1.0,
    "readability": 0.0-1.0,
    "authority": 0.0-1.0
  }
}
```

Score >= 0.7 is a pass. Be specific in feedback — cite exact passages that need work.
"""


def build_style_judge_user_prompt(
    *,
    content_markdown: str,
    style_guide_md: str,
    title: str,
) -> str:
    """Build the user prompt for style evaluation."""
    return f"""\
## Article to Evaluate

Title: {title}

{content_markdown[:6000]}

## Style Guide

{style_guide_md[:4000] if style_guide_md else "No style guide provided — evaluate against general B2B SaaS best practices."}

Evaluate this article's style alignment and provide a score.
"""
