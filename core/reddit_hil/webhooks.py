from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

import requests


def _chunk_text(text: str, max_len: int) -> List[str]:
    if max_len <= 0:
        return [text]
    s = text or ""
    chunks: List[str] = []
    while s:
        chunks.append(s[:max_len])
        s = s[max_len:]
    return chunks or [""]


def _safe_str(v: Any, max_len: int) -> str:
    try:
        s = v if isinstance(v, str) else json.dumps(v, default=str)
    except Exception:
        s = str(v)
    if max_len > 0:
        return s[:max_len]
    return s


def send_slack(
    webhook_url: str,
    *,
    thread_url: str,
    thread_title: str,
    subreddit: str,
    why_match: str,
    draft_markdown: str,
    fit_score: Optional[float] = None,
) -> None:
    """
    Send a Slack Incoming Webhook message.
    Uses Blocks for readability. Truncates aggressively to avoid payload failures.
    """
    if not webhook_url:
        raise RuntimeError("Slack webhook URL is empty")

    title = _safe_str(thread_title, 250)
    why = _safe_str(why_match, 800)
    score_txt = f"{fit_score:.2f}" if isinstance(fit_score, (int, float)) else "n/a"

    # Slack block text limits: section text is ~3000 chars; keep margin.
    draft_chunks = _chunk_text(draft_markdown.strip(), 2500)
    blocks: List[Dict[str, Any]] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "High-value Reddit thread found", "emoji": False},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Subreddit:* r/{subreddit}  |  *Fit:* `{score_txt}`\n*Thread:* <{thread_url}|{title}>",
            },
        },
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Why this matches:*\n{why}"}},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": "*Draft reply (copy/paste + tweak):*"}},
    ]

    for i, chunk in enumerate(draft_chunks):
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": chunk or " "},
            }
        )
        if i >= 2:  # cap to 3 chunks to stay conservative
            break

    payload = {"blocks": blocks}
    resp = requests.post(webhook_url, json=payload, timeout=15)
    if resp.status_code >= 300:
        raise RuntimeError(f"Slack webhook failed: {resp.status_code} {resp.text}")


def send_discord(
    webhook_url: str,
    *,
    thread_url: str,
    thread_title: str,
    subreddit: str,
    why_match: str,
    draft_markdown: str,
    fit_score: Optional[float] = None,
) -> None:
    """
    Send a Discord webhook message.
    Discord content limit is ~2000 chars; use chunking.
    """
    if not webhook_url:
        raise RuntimeError("Discord webhook URL is empty")

    title = _safe_str(thread_title, 256)
    why = _safe_str(why_match, 900)
    score_txt = f"{fit_score:.2f}" if isinstance(fit_score, (int, float)) else "n/a"

    header = f"**High-value Reddit thread found**\n**Subreddit:** r/{subreddit} | **Fit:** `{score_txt}`\n**Thread:** {title}\n{thread_url}\n\n**Why this matches:**\n{why}\n\n**Draft reply (copy/paste + tweak):**\n"

    # Keep some room for code fences and header.
    max_body = 1800
    draft = (draft_markdown or "").strip()
    body_chunks = _chunk_text(draft, max_body)

    # First message includes the header + first chunk.
    first = header + "```text\n" + (body_chunks[0] if body_chunks else "") + "\n```"
    messages: List[str] = [first]
    for chunk in body_chunks[1:3]:  # cap to 3 total messages
        messages.append("```text\n" + chunk + "\n```")

    for content in messages:
        payload = {"content": content}
        resp = requests.post(webhook_url, json=payload, timeout=15)
        if resp.status_code >= 300:
            raise RuntimeError(f"Discord webhook failed: {resp.status_code} {resp.text}")
