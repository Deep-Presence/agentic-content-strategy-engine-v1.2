from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from langgraph.graph import END, StateGraph

from core.models.reddit_hil import DraftNotification, RedditMonitorInput, RedditThread
from core.config.settings import settings
from core.reddit_hil.reddit_client import fetch_new_threads
from core.reddit_hil.webhooks import send_discord, send_slack


_PROJECT_ROOT = Path(__file__).resolve().parents[2]  # content-strategy-engine/


def _resolve_virtual_path(vpath: str) -> Path:
    """
    Convert DeepAgents-style virtual paths like `/artifacts/...` into actual paths under content-strategy-engine/.
    """
    p = (vpath or "").strip()
    if not p.startswith("/"):
        # treat as already relative to project root
        return (_PROJECT_ROOT / p).resolve()
    return (_PROJECT_ROOT / p.lstrip("/")).resolve()


def _read_text(vpath: str, max_chars: int = 400_000) -> str:
    p = _resolve_virtual_path(vpath)
    if not p.exists():
        raise RuntimeError(f"Artifact not found: {vpath} -> {p}")
    return p.read_text(encoding="utf-8")[:max_chars]


def _ensure_seen_cache_dir() -> Path:
    d = _PROJECT_ROOT / "artifacts" / "_logs" / "reddit_monitor"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _seen_cache_path(company_slug: str) -> Path:
    base = _ensure_seen_cache_dir()
    return base / f"{company_slug}__seen.json"


def _load_seen_ids(company_slug: str) -> List[str]:
    p = _seen_cache_path(company_slug)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(x) for x in data]
        if isinstance(data, dict) and isinstance(data.get("seen_ids"), list):
            return [str(x) for x in data["seen_ids"]]
    except Exception:
        return []
    return []


def _save_seen_ids(company_slug: str, ids: List[str]) -> None:
    p = _seen_cache_path(company_slug)
    unique = sorted(set(str(x) for x in ids))
    payload = {"seen_ids": unique, "updated_at": int(time.time())}
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "you",
    "your",
    "are",
    "was",
    "were",
    "have",
    "has",
    "had",
    "they",
    "them",
    "their",
    "but",
    "not",
    "can",
    "could",
    "should",
    "would",
    "will",
    "just",
    "like",
    "what",
    "how",
    "why",
    "when",
    "where",
    "which",
    "into",
    "out",
    "about",
    "also",
    "more",
    "most",
    "some",
    "any",
    "all",
    "our",
    "we",
    "i",
    "me",
    "my",
    "us",
}


def _extract_persona_keywords(persona_md: str, max_terms: int = 80) -> List[str]:
    """
    Lightweight keyword extraction: focus on ICP sections most relevant to pain/intent.
    """
    # Pull specific sections if present
    targets = [
        "## Pain Points & Blockers",
        "## Buying Triggers",
        "## Messaging Angles",
    ]

    section_texts: List[str] = []
    for header in targets:
        m = re.search(rf"^{re.escape(header)}\s*$([\s\S]*?)(^##\s|\Z)", persona_md, re.MULTILINE)
        if m:
            section_texts.append(m.group(1))

    text = "\n".join(section_texts).strip() or persona_md
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9\-]{2,}", text.lower())
    filtered = [t for t in tokens if len(t) >= 4 and t not in _STOPWORDS]

    # Frequency count
    freq: Dict[str, int] = {}
    for t in filtered:
        freq[t] = freq.get(t, 0) + 1

    # Return top terms by freq, with a small bias toward longer, more specific words.
    ranked = sorted(freq.items(), key=lambda kv: (kv[1], len(kv[0])), reverse=True)
    return [t for t, _ in ranked[:max_terms]]


def _heuristic_score(thread: RedditThread, keywords: List[str]) -> float:
    hay = thread.text_for_matching(max_chars=4000).lower()
    if not hay.strip():
        return 0.0
    hits = 0
    for kw in keywords[:80]:
        if kw in hay:
            hits += 1
    # Normalize by a soft cap so scores are comparable
    return min(1.0, hits / 12.0)


def _prefilter(
    threads: List[RedditThread],
    *,
    max_age_hours: int,
) -> List[RedditThread]:
    now = int(time.time())
    out: List[RedditThread] = []
    for t in threads:
        if t.over_18:
            continue
        if t.stickied:
            continue
        if t.locked:
            continue
        age_s = max(0, now - int(t.created_utc or 0))
        if age_s > max_age_hours * 3600:
            continue
        if len((t.title or "").strip()) < 18:
            continue
        out.append(t)
    return out


def _get_llm():
    """
    LLM used for final ranking + drafting. Uses Gemini via LangChain.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI

    api_key = settings.google_api_key_reddit_hil or settings.google_api_key_company_deepagent
    if not api_key:
        raise RuntimeError(
            "Missing GOOGLE_API_KEY_REDDIT_HIL (recommended) or GOOGLE_API_KEY_COMPANY_DEEPAGENT (fallback)."
        )
    model_name = settings.google_gemini_model_reddit_hil
    return ChatGoogleGenerativeAI(model=model_name, api_key=api_key)


def _llm_select_and_draft(
    *,
    company_md: str,
    persona_md: str,
    style_md: str,
    candidates: List[Tuple[RedditThread, float]],
    top_k: int,
) -> List[DraftNotification]:
    """
    Single LLM call that:
    - picks the best threads (<= top_k)
    - explains why they match
    - writes drafts following the style guide
    Returns structured DraftNotification objects.
    """
    llm = _get_llm()

    items = []
    for t, hscore in candidates:
        snippet = (t.selftext or "").strip()
        if len(snippet) > 1200:
            snippet = snippet[:1200] + "\u2026"
        items.append(
            {
                "id": t.id,
                "subreddit": t.subreddit,
                "title": t.title,
                "url": str(t.url),
                "created_utc": t.created_utc,
                "score": t.score,
                "num_comments": t.num_comments,
                "heuristic_fit": round(float(hscore), 3),
                "body_snippet": snippet,
            }
        )

    prompt = f"""
You are a Reddit engagement assistant. You MUST NOT post anything to Reddit. You only propose drafts for a human to post manually.

You are given:
- Company Context (markdown)
- ICP Persona (markdown)
- Writing Style Guide (markdown)
- A list of candidate Reddit threads (JSON)

Task:
1) Select up to {top_k} threads that best match the ICP persona's pain points and intent.
2) For each selected thread, produce:
   - fit_score: number 0.0 to 1.0
   - why_match: 2-5 sentences explaining why it matches (no fluff)
   - draft_markdown: a suggested reply in the style guide voice

Draft rules:
- Be genuinely helpful, specific, and grounded in the question.
- Keep it ~120-220 words unless the thread clearly needs more.
- Use 2-4 bullets where helpful.
- No hard sell; soft CTA allowed (e.g., offer a checklist/template).
- Do not claim you have used the product or have personal results.
- Avoid policy-sensitive claims; do not ask for DMs as the first move.
- Do not mention you are an AI.

Output: Return ONLY valid JSON, exactly:
[
  {{
    "thread_id": "\u2026",
    "fit_score": 0.0,
    "why_match": "\u2026",
    "draft_markdown": "\u2026"
  }}
]

Company Context Markdown:
{company_md[:120000]}

ICP Persona Markdown:
{persona_md[:120000]}

Writing Style Guide Markdown:
{style_md[:120000]}

Candidate threads (JSON):
{json.dumps(items, ensure_ascii=False)}
""".strip()

    res = llm.invoke(prompt)
    content = getattr(res, "content", None) if res is not None else None
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("LLM returned empty content for select+draft")

    try:
        parsed = json.loads(content)
    except Exception as e:
        raise RuntimeError(f"LLM did not return valid JSON: {e}\nRaw: {content[:5000]}") from e

    by_id = {t.id: t for t, _ in candidates}
    out: List[DraftNotification] = []
    if not isinstance(parsed, list):
        raise RuntimeError("LLM output JSON was not a list")
    for row in parsed[:top_k]:
        if not isinstance(row, dict):
            continue
        tid = str(row.get("thread_id") or "").strip()
        thread = by_id.get(tid)
        if not thread:
            continue
        fit_score = row.get("fit_score")
        why = str(row.get("why_match") or "").strip()
        draft = str(row.get("draft_markdown") or "").strip()
        if not (why and draft):
            continue
        try:
            fs = float(fit_score)
        except Exception:
            fs = 0.0
        fs = max(0.0, min(1.0, fs))
        out.append(
            DraftNotification(
                thread=thread,
                fit_score=fs,
                why_match=why,
                draft_markdown=draft,
                metadata={},
            )
        )
    return out


# -----------------------
# LangGraph nodes
# -----------------------


def _load_artifacts(state: Dict[str, Any]) -> Dict[str, Any]:
    inp: RedditMonitorInput = state["input"]
    company_md = _read_text(inp.company_context_path)
    persona_md = _read_text(inp.icp_persona_path)
    style_md = _read_text(inp.style_guide_path)
    return {**state, "company_md": company_md, "persona_md": persona_md, "style_md": style_md}


def _fetch_candidates(state: Dict[str, Any]) -> Dict[str, Any]:
    inp: RedditMonitorInput = state["input"]
    all_threads: List[RedditThread] = []
    for sr in inp.subreddits:
        threads = fetch_new_threads(sr, limit=inp.max_threads_per_subreddit, include_selftext=True)
        all_threads.extend(threads)
    return {**state, "candidates": all_threads}


def _dedupe_cache(state: Dict[str, Any]) -> Dict[str, Any]:
    inp: RedditMonitorInput = state["input"]
    seen = set(_load_seen_ids(inp.company_slug))
    threads: List[RedditThread] = state.get("candidates") or []
    unique: List[RedditThread] = []
    for t in threads:
        if t.id in seen:
            continue
        unique.append(t)
    return {**state, "seen_ids": list(seen), "candidates": unique}


def _rank_filter(state: Dict[str, Any]) -> Dict[str, Any]:
    inp: RedditMonitorInput = state["input"]
    persona_md: str = state.get("persona_md") or ""
    keywords = _extract_persona_keywords(persona_md)

    threads: List[RedditThread] = state.get("candidates") or []
    threads = _prefilter(threads, max_age_hours=inp.max_age_hours)

    scored: List[Tuple[RedditThread, float]] = [(t, _heuristic_score(t, keywords)) for t in threads]
    scored.sort(key=lambda x: (x[1], x[0].score, x[0].num_comments), reverse=True)
    shortlisted = scored[: inp.shortlist_k]
    return {**state, "shortlisted": shortlisted}


def _draft_reply(state: Dict[str, Any]) -> Dict[str, Any]:
    inp: RedditMonitorInput = state["input"]
    company_md: str = state.get("company_md") or ""
    persona_md: str = state.get("persona_md") or ""
    style_md: str = state.get("style_md") or ""
    shortlisted: List[Tuple[RedditThread, float]] = state.get("shortlisted") or []

    drafts = _llm_select_and_draft(
        company_md=company_md,
        persona_md=persona_md,
        style_md=style_md,
        candidates=shortlisted,
        top_k=inp.top_k,
    )
    return {**state, "drafts": drafts}


def _notify(state: Dict[str, Any]) -> Dict[str, Any]:
    inp: RedditMonitorInput = state["input"]
    drafts: List[DraftNotification] = state.get("drafts") or []

    slack_url = settings.slack_webhook_url
    discord_url = settings.discord_webhook_url

    notified_ids: List[str] = []
    errors: List[str] = []

    for dn in drafts:
        t = dn.thread
        try:
            if inp.dry_run:
                notified_ids.append(t.id)
                continue
            if inp.send_slack:
                send_slack(
                    slack_url,
                    thread_url=str(t.url),
                    thread_title=t.title,
                    subreddit=t.subreddit,
                    why_match=dn.why_match,
                    draft_markdown=dn.draft_markdown,
                    fit_score=dn.fit_score,
                )
            if inp.send_discord:
                send_discord(
                    discord_url,
                    thread_url=str(t.url),
                    thread_title=t.title,
                    subreddit=t.subreddit,
                    why_match=dn.why_match,
                    draft_markdown=dn.draft_markdown,
                    fit_score=dn.fit_score,
                )
            notified_ids.append(t.id)
        except Exception as e:
            errors.append(f"{t.id}: {e}")

    # Persist cache so we don't re-notify the same threads on reruns.
    try:
        existing = set(_load_seen_ids(inp.company_slug))
        merged = list(existing.union(set(notified_ids)))
        _save_seen_ids(inp.company_slug, merged)
    except Exception as e:
        errors.append(f"cache_write_failed: {e}")

    return {**state, "notified_ids": notified_ids, "notify_errors": errors}


def build_graph():
    graph = StateGraph(dict)
    graph.add_node("load_artifacts", _load_artifacts)
    graph.add_node("fetch_candidates", _fetch_candidates)
    graph.add_node("dedupe_cache", _dedupe_cache)
    graph.add_node("rank_filter", _rank_filter)
    graph.add_node("draft_reply", _draft_reply)
    graph.add_node("notify", _notify)

    graph.set_entry_point("load_artifacts")
    graph.add_edge("load_artifacts", "fetch_candidates")
    graph.add_edge("fetch_candidates", "dedupe_cache")
    graph.add_edge("dedupe_cache", "rank_filter")
    graph.add_edge("rank_filter", "draft_reply")
    graph.add_edge("draft_reply", "notify")
    graph.add_edge("notify", END)
    return graph.compile()
