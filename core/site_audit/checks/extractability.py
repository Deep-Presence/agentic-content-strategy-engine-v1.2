"""AEO content extractability pure functions for the site audit pipeline.

All functions in this module are PURE — no I/O, no network calls, no side effects.
They operate on HTML strings, parsed BeautifulSoup trees, or plain text.

These checks are the DIFFERENTIATOR — traditional SEO tools don't check any of this.
They assess how easily AI engines can extract and reuse page content as answer snippets.

Functions:
    classify_heading_as_question  — Is a heading phrased as a question?
    detect_quick_answer_hook      — Does a question heading have a direct-answer paragraph?
    is_self_contained_paragraph   — Can a paragraph be understood without prior context?
    detect_faq_section            — Does the page have a structured FAQ section?
    detect_definition_opening     — Does the first paragraph define the topic?
    detect_key_takeaways          — Does the page have a key-takeaways section?
    detect_comparison_table       — Does the page have a comparison table?
    detect_numbered_steps         — Does the page have numbered steps?
    detect_toc                    — Does the page have a table of contents?
"""
from __future__ import annotations

import re
from typing import Optional

from bs4 import BeautifulSoup, NavigableString, Tag

# ---------------------------------------------------------------------------
# Question-heading classifier
# ---------------------------------------------------------------------------

# Words that, when at the START of a heading (full-word match), indicate a question.
_QUESTION_START_WORDS: tuple[str, ...] = (
    "what",
    "how",
    "why",
    "when",
    "where",
    "who",
    "which",
    "can",
    "does",
    "is",
    "are",
    "should",
    "will",
    "do",
    "have",
    "has",
    "could",
    "would",
    "might",
    "may",
    "did",
    "was",
    "were",
)

# Core wh-words that can indicate a question heading even WITHOUT a trailing "?",
# provided the heading has >= 4 words.  Auxiliary verbs (is, can, does, etc.)
# require "?" to avoid false positives like "Is your team ready for growth".
_WH_WORDS: frozenset[str] = frozenset({
    "what", "how", "why", "when", "where", "who", "which",
})

# Comparison patterns that appear *within* a heading
_COMPARISON_PATTERNS: tuple[str, ...] = (
    r"\bvs\b",
    r"\bvs\.\b",
    r"\bversus\b",
    r"\bcompared to\b",
    r"\bdifference between\b",
    r"\bpros and cons\b",
    r"\bcomparison\b",
)


def classify_heading_as_question(text: str) -> bool:
    """Determine whether a heading is phrased as a question.

    Rules (applied in order; first match returns True):
    1. Heading ends with ``?`` AND starts with a recognised question word
       (full-word boundary check — "Whoever" is NOT a question).
    2. Heading contains a comparison pattern (vs, versus, compared to,
       difference between, or [as full word between nouns]).

    Purely declarative headings like "Benefits of AEO" or "Understanding Schema"
    always return False.

    Args:
        text: The heading text (no HTML markup).

    Returns:
        True if the heading is a question, False otherwise.
    """
    stripped = text.strip()
    if not stripped:
        return False

    lower = stripped.lower()

    # Rule 1: ends with ? and starts with question word (word boundary)
    if stripped.endswith("?"):
        for word in _QUESTION_START_WORDS:
            # Use \b to ensure full-word match, not prefix match
            if re.match(rf"^{re.escape(word)}\b", lower):
                return True

    # Rule 2: comparison patterns (no trailing ? required)
    for pattern in _COMPARISON_PATTERNS:
        if re.search(pattern, lower):
            return True

    # Rule 3: wh-word headings without trailing "?" — only core wh-words,
    # minimum 4 words to filter fragment headings like "How" or "What Now"
    word_count = len(stripped.split())
    if word_count >= 4:
        for word in _WH_WORDS:
            if re.match(rf"^{re.escape(word)}\b", lower):
                return True

    return False


# ---------------------------------------------------------------------------
# Quick-answer hook detector
# ---------------------------------------------------------------------------


def _get_visible_text(element: Tag) -> str:
    """Extract all text from a BS4 element, stripping tags."""
    return element.get_text(separator=" ", strip=True)


def _count_words(text: str) -> int:
    """Count whitespace-separated words in text."""
    return len(text.split())


def detect_quick_answer_hook(
    heading_element: Tag,
    soup: BeautifulSoup,
    config: Optional["AuditConfig"] = None,
) -> bool:
    """Check whether a question heading is followed by a direct-answer paragraph.

    After a question heading, search up to 5 siblings for ``<p>`` elements
    (including ``<p>`` nested inside ``<div>``/``<section>``/``<article>``
    containers).  The paragraph word count must fall within
    ``[config.aeo_quick_answer_min_words, config.aeo_quick_answer_max_words]``
    (default 15–150).

    The search stops at the next heading element (h1–h6) to prevent matching
    unrelated paragraphs in subsequent sections.

    Args:
        heading_element: The BS4 Tag element for the heading (h1–h6).
        soup: The full page BeautifulSoup tree (not used directly but kept for
            API consistency with other detectors).
        config: Optional AuditConfig for word count range.  When ``None``,
            uses the module-level default.

    Returns:
        True if a qualifying answer paragraph was found, False otherwise.
    """
    if config is None:
        from core.site_audit.config import DEFAULT_AUDIT_CONFIG
        config = DEFAULT_AUDIT_CONFIG

    min_words = config.aeo_quick_answer_min_words
    max_words = config.aeo_quick_answer_max_words

    _HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})

    sibling_count = 0
    current = heading_element.next_sibling

    while current is not None and sibling_count < 5:
        # Skip pure whitespace text nodes
        if isinstance(current, NavigableString):
            if current.strip():
                sibling_count += 1
            current = current.next_sibling
            continue

        if not isinstance(current, Tag):
            current = current.next_sibling
            continue

        tag_name = current.name.lower() if current.name else ""

        # Stop at next heading (bounded search — Codex F-13)
        if tag_name in _HEADING_TAGS:
            return False

        # Skip non-content tags
        if tag_name in ("img", "figure", "picture", "script", "style", "noscript"):
            current = current.next_sibling
            continue

        if tag_name == "p":
            text = _get_visible_text(current)
            word_count = _count_words(text)
            if min_words <= word_count <= max_words:
                return True
            # Don't stop at first non-matching <p> — continue searching
            sibling_count += 1
            current = current.next_sibling
            continue

        if tag_name in ("div", "section", "article"):
            # Search ALL <p> elements inside this container
            for inner_p in current.find_all("p"):
                if isinstance(inner_p, Tag):
                    text = _get_visible_text(inner_p)
                    word_count = _count_words(text)
                    if min_words <= word_count <= max_words:
                        return True
            sibling_count += 1
            current = current.next_sibling
            continue

        sibling_count += 1
        current = current.next_sibling

    return False


# ---------------------------------------------------------------------------
# Self-contained paragraph detector
# ---------------------------------------------------------------------------

# Continuity markers that indicate a paragraph depends on prior context.
_CONTINUITY_MARKERS: tuple[str, ...] = (
    "however",
    "additionally",
    "furthermore",
    "moreover",
    "in addition",
    "as mentioned",
    "as noted",
    "as discussed",
    "that said",
    "on the other hand",
    "meanwhile",
    "nevertheless",
    "consequently",
    "therefore",
)


def is_self_contained_paragraph(text: str) -> bool:
    """Determine whether a paragraph is suitable for AI extraction in isolation.

    A paragraph is self-contained if:
    - It contains 20–80 words.
    - It does NOT start with a continuity marker (case-insensitive).

    Continuity markers (e.g. "However", "Additionally") indicate the paragraph
    builds on prior content and cannot be understood in isolation.

    Args:
        text: Plain text content of the paragraph (no HTML markup).

    Returns:
        True if the paragraph is self-contained, False otherwise.
    """
    stripped = text.strip()
    if not stripped:
        return False

    word_count = _count_words(stripped)
    if not (20 <= word_count <= 80):
        return False

    lower = stripped.lower()
    for marker in _CONTINUITY_MARKERS:
        # Check if the paragraph STARTS with the marker (with optional leading punct)
        if re.match(rf"^{re.escape(marker)}\b", lower):
            return False

    return True


# ---------------------------------------------------------------------------
# Content pattern detectors
# ---------------------------------------------------------------------------


def detect_faq_section(soup: BeautifulSoup) -> bool:
    """Detect whether the page contains a structured FAQ section.

    Detection rules (any one sufficient):
    1. A heading (h2–h4) contains "FAQ" or "Frequently Asked Questions".
    2. Page contains ``<dl>`` definition list elements.
    3. Page has 3+ repetitions of the pattern: question heading followed by
       answer paragraph.

    Args:
        soup: Parsed BeautifulSoup tree of the page.

    Returns:
        True if a FAQ section is detected.
    """
    # Rule 1: FAQ heading
    for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        heading_text = heading.get_text(strip=True).lower()
        if "faq" in heading_text or "frequently asked questions" in heading_text:
            return True

    # Rule 2: definition lists
    if soup.find("dl"):
        return True

    # Rule 3: question heading + answer pattern (3+ repetitions)
    question_answer_count = 0
    for heading in soup.find_all(["h2", "h3", "h4"]):
        heading_text = heading.get_text(strip=True)
        if classify_heading_as_question(heading_text):
            # Check if immediately followed by a paragraph
            next_sibling = heading.find_next_sibling(["p", "div"])
            if next_sibling:
                question_answer_count += 1
                if question_answer_count >= 3:
                    return True

    return False


# Continuation words after "is/are" that indicate a genuine definition.
# We match articles, demonstratives, quantifiers, and definitional adverbs.
# This rejects bare adjective predicates like "The company is great".
_DEFINITIONAL_CONTINUATIONS = re.compile(
    r"^(?:"
    r"a|an|the|"                              # articles
    r"defined|known|considered|described|"     # definitional verbs
    r"one|any|not|when|where|what|how|"        # quantifiers/relatives
    r"essentially|basically|generally|"        # adverbs of definition
    r"typically|commonly|often|primarily|"     # frequency adverbs (definitional)
    r"specifically|usually|simply|"            # more adverbs
    r"used|designed|built|meant|intended"      # purpose verbs (passive)
    r")\s",
    re.IGNORECASE,
)


def detect_definition_opening(text: str) -> bool:
    """Detect whether the first paragraph opens with a definition of the topic.

    Matches patterns like:
    - "{Topic} is a/the/defined as ..."
    - "{Topic} are ..."  (with definitional continuation)
    - "{Topic} refers to ..."

    After matching an ``is/are`` verb, the word that follows must be an article
    or definitional frame (``a``, ``an``, ``the``, ``defined``, ``known``, etc.)
    to avoid false positives like "The company is great".

    ``refers to`` is inherently definitional and needs no continuation check.

    Paragraphs starting with continuity markers (e.g. "However, AEO is...")
    or non-topic starters (pronouns, possessives, existential "there")
    do NOT qualify as definition openings.

    Args:
        text: Plain text of the FIRST paragraph on the page.

    Returns:
        True if the paragraph opens with a definition pattern.
    """
    stripped = text.strip()
    if not stripped:
        return False

    # Reject if starts with a continuity marker
    lower = stripped.lower()
    for marker in _CONTINUITY_MARKERS:
        if re.match(rf"^{re.escape(marker)}\b", lower):
            return False

    # Reject non-topic starters: pronouns, possessives, existential "there".
    # A real definition opening uses the topic noun/name directly.
    if re.match(
        r"^(?:there|it|our|we|you|they|my|your|his|her|its)\b",
        lower,
    ):
        return False

    # Match: <topic (1–5 words)> is/are/refers to ...
    patterns: list[tuple[str, str]] = [
        (r"^\S+(?:\s+\S+){0,4}\s+(?:is|are)\s+", "is_are"),
        (r"^\S+(?:\s+\S+){0,4}\s+refers\s+to\s+", "refers_to"),
    ]
    for pattern, kind in patterns:
        m = re.match(pattern, stripped, re.IGNORECASE)
        if m:
            if kind == "refers_to":
                return True  # "refers to" is inherently definitional
            # For is/are: require a definitional continuation word or
            # a hyphenated compound term (e.g. "machine-readable").
            remainder = stripped[m.end():]
            if _DEFINITIONAL_CONTINUATIONS.match(remainder):
                return True
            # Hyphenated compound terms are typically technical/definitional
            first_word = remainder.split()[0] if remainder.split() else ""
            if "-" in first_word and len(first_word) > 3:
                return True

    return False


def detect_key_takeaways(soup: BeautifulSoup) -> bool:
    """Detect whether the page has a key-takeaways or summary section.

    Looks for a heading containing one of: "Key Takeaways", "Key Points",
    "Summary", "TL;DR" — followed by a list (``<ul>`` or ``<ol>``).

    Args:
        soup: Parsed BeautifulSoup tree of the page.

    Returns:
        True if a key-takeaways section is detected.
    """
    takeaway_keywords = ("key takeaways", "key points", "summary", "tl;dr", "tldr")

    for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        heading_text = heading.get_text(strip=True).lower()
        if any(kw in heading_text for kw in takeaway_keywords):
            # Look for a list immediately after the heading
            next_element = heading.find_next_sibling(["ul", "ol", "p", "div"])
            if next_element:
                if next_element.name in ("ul", "ol"):
                    return True
                # Container div/p — look inside it
                inner_list = next_element.find(["ul", "ol"])
                if inner_list:
                    return True

    return False


def detect_comparison_table(soup: BeautifulSoup) -> bool:
    """Detect whether the page contains a comparison table.

    A comparison table must have:
    - 3 or more rows.
    - 2 or more columns.
    - A header row that suggests comparison (contains comparison-like terms OR
      multiple column headers each representing a different entity/option).

    Args:
        soup: Parsed BeautifulSoup tree of the page.

    Returns:
        True if a comparison table is detected.
    """
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        if len(rows) < 3:
            continue

        # Check column count in first row
        first_row = rows[0]
        cells = first_row.find_all(["th", "td"])
        if len(cells) < 2:
            continue

        # Check if first row looks like a comparison header
        header_text = " ".join(c.get_text(strip=True).lower() for c in cells)
        comparison_terms = ("vs", "versus", "plan", "feature", "option", "tier", "price")
        if any(term in header_text for term in comparison_terms):
            return True

        # Multiple header columns each containing substantial different text
        header_texts = [c.get_text(strip=True) for c in cells if c.name == "th"]
        if len(header_texts) >= 2 and all(t for t in header_texts):
            return True

    return False


def detect_numbered_steps(soup: BeautifulSoup) -> bool:
    """Detect whether the page contains numbered step instructions.

    Detection rules (any one sufficient):
    1. An ``<ol>`` element with 3 or more ``<li>`` items.
    2. Headings matching the pattern "Step N:" (N is a digit), appearing 2+ times.

    Args:
        soup: Parsed BeautifulSoup tree of the page.

    Returns:
        True if numbered steps are detected.
    """
    # Rule 1: ordered list with 3+ items
    for ol in soup.find_all("ol"):
        items = ol.find_all("li", recursive=False)
        if len(items) >= 3:
            return True
        # Also count nested li if no direct children
        items = ol.find_all("li")
        if len(items) >= 3:
            return True

    # Rule 2: headings with "Step N:" pattern
    step_heading_pattern = re.compile(r"^step\s+\d+", re.IGNORECASE)
    step_heading_count = 0
    for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        heading_text = heading.get_text(strip=True)
        if step_heading_pattern.match(heading_text):
            step_heading_count += 1
            if step_heading_count >= 2:
                return True

    return False


def detect_toc(soup: BeautifulSoup) -> bool:
    """Detect whether the page has a table of contents.

    Detection rules (any one sufficient):
    1. An element with ``id`` or ``class`` containing "toc",
       "table-of-contents", or "contents".
    2. A ``<nav>`` element near the top of the body containing a list of
       internal anchor links (``<a href="#...">``) with 3+ entries.

    Args:
        soup: Parsed BeautifulSoup tree of the page.

    Returns:
        True if a table of contents is detected.
    """
    # Rule 1: CSS selector for id/class substrings — replaces O(n) scan.
    # Catches "toc", "post-toc", "toc-wrapper", "wp-table-of-contents", etc.
    # The `i` flag ensures case-insensitive matching (CSS Selectors Level 4,
    # supported by soupsieve ≥2.0 which BeautifulSoup 4 uses internally).
    _toc_selector = (
        '[id*="toc" i], [class*="toc" i], '
        '[id*="table-of-contents" i], [class*="table-of-contents" i], '
        '[id*="table_of_contents" i], [class*="table_of_contents" i], '
        '[id*="contents" i], [class*="contents" i]'
    )
    if soup.select_one(_toc_selector):
        return True

    # Rule 2: nav element with internal anchor links near the top
    body = soup.find("body") or soup
    nav_elements = body.find_all("nav")
    for nav in nav_elements:
        internal_links = nav.find_all("a", href=re.compile(r"^#"))
        if len(internal_links) >= 3:
            return True

    # Also look for a list of internal anchor links near the top of the page
    # (within the first 500 chars of body text position)
    top_elements = []
    if body:
        for child in body.children:
            if isinstance(child, Tag):
                top_elements.append(child)
                if len(top_elements) >= 5:
                    break

    for elem in top_elements:
        internal_links = elem.find_all("a", href=re.compile(r"^#"))
        if len(internal_links) >= 3:
            return True

    return False
