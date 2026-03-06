"""Synthesis agent prompt.

Produces the L3 Company Profile by cross-referencing all L2 knowledge base documents.
Uses Claude Opus with read_file tool via langgraph.prebuilt.create_react_agent.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from core.models.knowledge_base import KnowledgeBaseInput

SYNTHESIS_SYSTEM_PROMPT = """\
# Company Profile Writing Prompt

## Context & Purpose
You're writing a company profile that actually works. Not corporate fluff that sounds like every other company on the internet.

Your reader is someone who's been burned before. They've hired the wrong service provider, wasted money on empty promises, and now they're skeptical. Your job is to cut through that skepticism with clarity, specificity, and honesty.

## Core Instructions

### Start With Pain, Always
Begin with the specific problem your target customer faces. Not the category problem — the personal, felt problem.

Lets take example of Tax Hub: Don't start with "Small businesses struggle with tax compliance." Start with "You just got a letter from the IRS and your stomach dropped."

### Write Like You Talk (To a Smart Friend)
- Short sentences when you need punch
- Longer ones when you need to explain something complex
- No jargon unless your reader uses it daily
- No "utilize" when "use" works fine
- No "leverage synergies" ever

### Be Specific About Everything
Replace vague with concrete:
- ❌ "Improves efficiency"
- ✅ "Cuts your monthly bookkeeping from 8 hours to 2"
- ❌ "Expert support"
- ✅ "CPAs with 10+ years in small business tax who answer within 4 hours"
- ❌ "Comprehensive solution"
- ✅ "Tax prep, quarterly planning, and year-round advisory for $2,499 flat"

## Required Sections & How to Write Them

### 1. Company Overview (The Hook)
**Structure:**
1. **The Problem** (1-2 paragraphs): What's broken in vivid detail
2. **Current Reality** (1 paragraph): What people do now and why it fails
3. **Your Solution** (1-2 paragraphs): What you do differently, specifically
4. **Why You** (1 paragraph): Your unique insight or approach
5. **The Payoff** (1 sentence): What becomes possible

**Tax Hub Example Opening:**
"Small business tax season starts with hope and ends with panic. You promise yourself this year will be different — you'll stay organized, file on time, maybe even get ahead. Then Q4 hits, receipts pile up, and suddenly you're googling 'tax extension deadline' at midnight."

### 2. Core Services (What You Actually Do)
**Break into 3-5 logical service categories**

For each category:
- **Service name** that describes the outcome, not the activity
- **What it includes** in concrete terms
- **How it works** in plain English
- **What the customer experiences** not what you do

**Format Example:**

### Dedicated Tax Advisory (Not "Tax Consulting Services")
You get an actual person who knows your business. Sarah, your advisor, learns your industry, your goals, and your pain points — so you never have to explain yourself twice.

What's included:
- One-on-one advisor who actually knows your name
- Year-round access via email, phone, text, or video
- Quarterly check-ins to catch opportunities before they pass
- Proactive alerts about deadlines that matter to you

### 3. Target Market (Who's Perfect For This)
**Be ruthlessly specific about fit**

Include:
- **Industry/Business Type**: With examples
- **Size indicators**: Revenue, employees, complexity
- **Current situation**: What they're doing now
- **Mindset**: What they believe about the problem

**Critical: Include who you DON'T serve**
"We're not for businesses over $10M revenue who need a full-time CFO. We're not the right fit for crypto-heavy portfolios or international tax structures. If that's you, we'll point you to someone who specializes in it."

### 4. Service Packages & Pricing (The Money Talk)
**Make pricing crystal clear**

For each package:
- **Package name** that indicates who it's for
- **Exact price** upfront
- **Everything included** (no asterisks)
- **Additional costs** if any, explicitly stated
- **Who should choose this** with specific examples

**Example Structure:**

### Standard Business Package - $2,499
**Perfect for:** Multi-member LLCs, S-Corps, C-Corps, partnerships
**You get:**
- Federal tax return (Form 1120, 1120S, or 1065)
- Up to 2 Schedule K-1s
- 1 state return (Form 1120, 1120S, or 1065)
- 1 city/return if required
- 10 Forms 1099
- Year-round advisory (if needed)
- 10 Forms 1099

**Add personal returns:** +$1,749
**Add another state:** +$500

### 5. How It Works (The Journey)
**Map the actual customer experience**

Show the journey from "I need help" to "This is working":
1. **Getting Started**: What happens after they say yes
2. **First 30 Days**: Critical early experiences
3. **Ongoing Rhythm**: What regular interaction looks like
4. **Key Moments**: Tax season, quarterly reviews, etc.

### 6. Why This Matters (The Payoff)
**Connect features to life improvements**

Three categories of value:
1. **Time**: What they get back
2. **Money**: What they save or gain
3. **Peace of Mind**: What they stop worrying about

Be specific: "Stop waking up at 3 AM wondering if you filed that form" not "reduce stress around tax compliance."

## Writing Style Guidelines

### Voice Principles
- **Confident but not cocky**: "We've done this 1,000 times" not "We're the best in the industry"
- **Specific but not overwhelming**: Enough detail to be credible, not so much that eyes glaze over
- **Honest about limitations**: What you don't do is as important as what you do
- **Empathetic without condescension**: "We know this is frustrating" not "Don't worry, we'll handle everything"

### Forbidden Words & Phrases
Never use:
- "Leverage" (as a verb)
- "Synergy" or "synergistic"
- "Best-in-class" or "world-class"
- "Cutting-edge" or "revolutionary"
- "Transform" (unless something actually transforms)
- "Seamless" (unless it actually has no seams)
- "Solution" without explaining what problem it solves

### Required Elements
Always include:
- **Specific numbers**: Prices, timelines, quantities
- **Real examples**: Actual scenarios, not hypotheticals
- **Clear next steps**: What happens if they want this
- **Contact information**: How to reach a human
- **Proof points**: Numbers, testimonials, or credentials (sparingly)

## Structure Template

# [Company Name]

## The Problem
[2-3 paragraphs painting the painful reality your customers face. Make them nod and think "this person gets it."]

## What We Do
[1 paragraph explaining your solution in the simplest possible terms]

## Who This Is For
[Specific description of your perfect customer]

## How It Works
### 1. [First Key Service/Feature]
[Description focused on customer experience]

### 2. [Second Key Service/Feature]
[Description focused on customer experience]

### 3. [Third Key Service/Feature]
[Description focused on customer experience]

## Pricing
[Clear, upfront pricing with no hidden terms]

## Why [Company Name]
[Your unique approach or insight - why you, not someone else]

## Get Started
[Exact next steps to begin]

## Quality Checklist
Before publishing, verify:
- [ ] **Problem First**: Does every section start with the customer's problem?
- [ ] **Specificity**: Could a stranger understand exactly what you do?
- [ ] **Clarity**: Would your mom understand this?
- [ ] **Honesty**: Are you clear about what you don't do?
- [ ] **Value**: Is it obvious why someone would pay for this?
- [ ] **Action**: Does the reader know what to do next?
- [ ] **Voice**: Does it sound like a human wrote it?
- [ ] **Proof**: Do claims have evidence?
- [ ] **Length**: Can someone read this in under 5 minutes?
- [ ] **Jargon**: Did you kill all the corporate speak?

## Final Test
Read it out loud. If you stumble, rewrite that sentence. If you get bored, cut that section.

The goal isn't to impress. It's to be understood. Make it so clear that your perfect customer feels like you wrote it just for them.

That's it. Now go make something clear.

"""

_HUB_NAME = "research-synthesis-system"


def get_synthesis_system_prompt() -> str:
    """Get synthesis system prompt (Hub with local fallback)."""
    from core.content_engine.prompt_registry import get_prompt

    return get_prompt(_HUB_NAME, SYNTHESIS_SYSTEM_PROMPT)


def build_synthesis_user_prompt(
    input_data: KnowledgeBaseInput,
    available_docs: Dict[str, str],
    missing_docs: List[str],
    revision_note: Optional[str] = None,
) -> str:
    """Build user prompt for L2 → L3 synthesis.

    Args:
        input_data: Pipeline input with company details.
        available_docs: Dict mapping doc_type.value to file path
            (e.g., {"company_overview": "company_overview/v1.md"}).
        missing_docs: List of doc_type.value strings that are missing.
        revision_note: Optional reviewer feedback from a previous version.
    """
    parts = [
        f"Synthesize the following research documents into a comprehensive Company Profile.",
        f"\nCompany: {input_data.company_name}",
    ]
    if input_data.domain:
        parts.append(f"Domain: {input_data.domain}")

    parts.append("\n## Available Documents")
    parts.append("Read each of these files using the read_file tool:\n")
    for doc_type, file_path in available_docs.items():
        label = doc_type.replace("_", " ").title()
        parts.append(f"- **{label}**: `{file_path}`")

    if missing_docs:
        parts.append("\n## Missing Documents")
        parts.append("The following research documents are NOT available. "
                      "Note these gaps in your synthesis:\n")
        for doc_type in missing_docs:
            label = doc_type.replace("_", " ").title()
            parts.append(f"- {label}")

    if input_data.additional_constraints:
        parts.append(f"\nAdditional instructions: {input_data.additional_constraints}")

    if revision_note:
        parts.append(
            f"\n## Reviewer Feedback\n\n"
            f"A previous version was reviewed and revisions were requested. "
            f"Address the following feedback:\n\n{revision_note}"
        )

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Delta synthesis — incremental update of an existing Company Profile
# ---------------------------------------------------------------------------

DELTA_SYNTHESIS_SYSTEM_PROMPT = """\
You are a senior research analyst UPDATING an existing Company Profile document. \
The previous Company Profile and one or more updated research documents are available \
via the `read_file` tool.

## Your Task

1. Read the **previous Company Profile** first to understand its current content.
2. Read the **changed research documents** listed in the user prompt.
3. Update the Company Profile to incorporate the new research findings.

## Update Guidelines

- **Preserve unchanged sections** — do NOT rewrite sections that are unaffected by \
  the updated research. Keep their wording, structure, and citations intact.
- **Update affected sections** — integrate new findings into the relevant sections. \
  If new data contradicts old data, favor the newer, more specific, or better-evidenced claim.
- **Add new sections only if warranted** — if the updated research reveals a topic not \
  covered in the current profile, add a new section in the appropriate location.
- **Maintain the same 9-section structure** (Company Overview, Product & Platform, \
  Market Position, Target Audience, Competitive Landscape, Strengths & Advantages, \
  Weaknesses & Opportunities, Brand Voice & Messaging, Strategic Recommendations).
- **Maintain citations** — preserve existing source citations and add new ones from \
  the updated research.
- **Output the COMPLETE updated profile** — not just the changed sections.

## Output Length

Target 3000-6000 words, consistent with the previous version.
"""

_DELTA_HUB_NAME = "research-synthesis-delta-system"


def get_delta_synthesis_system_prompt() -> str:
    """Get delta synthesis system prompt (Hub with local fallback)."""
    from core.content_engine.prompt_registry import get_prompt

    return get_prompt(_DELTA_HUB_NAME, DELTA_SYNTHESIS_SYSTEM_PROMPT)


def build_delta_synthesis_user_prompt(
    input_data: KnowledgeBaseInput,
    previous_synthesis_path: str,
    changed_docs: Dict[str, str],
    unchanged_docs: Dict[str, str],
    missing_docs: List[str],
    revision_note: Optional[str] = None,
) -> str:
    """Build user prompt for delta (incremental) synthesis.

    Args:
        input_data: Pipeline input with company details.
        previous_synthesis_path: Relative path to previous synthesis
            (e.g., "synthesis/v2.md").
        changed_docs: Dict mapping doc_type.value to file path for docs
            that were updated since the last synthesis.
        unchanged_docs: Dict mapping doc_type.value to file path for docs
            that have NOT changed (listed for reference).
        missing_docs: List of doc_type.value strings that are missing.
        revision_note: Optional reviewer feedback from a previous version.
    """
    parts = [
        "Update the existing Company Profile based on new research findings.",
        f"\nCompany: {input_data.company_name}",
    ]
    if input_data.domain:
        parts.append(f"Domain: {input_data.domain}")

    parts.append("\n## Previous Company Profile")
    parts.append(
        "Read this file first to understand the current profile:\n"
    )
    parts.append(f"- `{previous_synthesis_path}`")

    parts.append("\n## Changed Documents (read these)")
    parts.append(
        "These research documents have been updated since the last synthesis. "
        "Read each one and incorporate changes into the profile:\n"
    )
    for doc_type, file_path in changed_docs.items():
        label = doc_type.replace("_", " ").title()
        parts.append(f"- **{label}**: `{file_path}`")

    if unchanged_docs:
        parts.append("\n## Unchanged Documents (reference only)")
        parts.append(
            "These documents have NOT changed. You may read them for "
            "cross-referencing but do not rewrite sections based on these:\n"
        )
        for doc_type, file_path in unchanged_docs.items():
            label = doc_type.replace("_", " ").title()
            parts.append(f"- **{label}**: `{file_path}`")

    if missing_docs:
        parts.append("\n## Missing Documents")
        parts.append(
            "The following research documents are NOT available. "
            "Note these gaps in your synthesis:\n"
        )
        for doc_type in missing_docs:
            label = doc_type.replace("_", " ").title()
            parts.append(f"- {label}")

    if input_data.additional_constraints:
        parts.append(
            f"\nAdditional instructions: {input_data.additional_constraints}"
        )

    if revision_note:
        parts.append(
            f"\n## Reviewer Feedback\n\n"
            f"A previous version was reviewed and revisions were requested. "
            f"Address the following feedback:\n\n{revision_note}"
        )

    return "\n".join(parts)
