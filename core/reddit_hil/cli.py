from __future__ import annotations

import argparse
import json
import logging
from typing import List, Optional

from core.reddit_hil.graph import build_graph
from core.models.reddit_hil import RedditMonitorInput

logger = logging.getLogger(__name__)


def _split_csv(v: Optional[str]) -> List[str]:
    if not v:
        return []
    parts = [p.strip() for p in v.split(",")]
    return [p for p in parts if p]


def main() -> None:
    ap = argparse.ArgumentParser(description="Run Reddit Human-in-the-Loop monitor (read-only).")
    ap.add_argument("--company-name", required=True)
    ap.add_argument("--company-slug", required=True)
    ap.add_argument("--workspace-id", default="", help="Workspace id for BYOK model resolution.")
    ap.add_argument("--workspace-slug", default="", help="Workspace slug for BYOK model resolution.")
    ap.add_argument(
        "--company-context-path",
        default=None,
        help="DeepAgents-style path like /artifacts/company_context/<slug>.md",
    )
    ap.add_argument(
        "--icp-persona-path",
        default=None,
        help="DeepAgents-style path like /artifacts/personas/<slug>__persona-icp.md",
    )
    ap.add_argument(
        "--style-guide-path",
        default=None,
        help="DeepAgents-style path like /artifacts/style_guides/<slug>.md",
    )
    ap.add_argument("--subreddits", default="marketing", help="Comma-separated list, e.g. marketing,startups")
    ap.add_argument("--max-threads", type=int, default=25)
    ap.add_argument("--max-age-hours", type=int, default=72)
    ap.add_argument("--shortlist-k", type=int, default=15)
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true", help="Do everything except sending webhooks.")
    ap.add_argument("--no-slack", action="store_true")
    ap.add_argument("--no-discord", action="store_true")

    args = ap.parse_args()

    slug = args.company_slug
    company_context_path = args.company_context_path or f"/artifacts/company_context/{slug}.md"
    icp_persona_path = args.icp_persona_path or f"/artifacts/personas/{slug}__persona-icp.md"
    style_guide_path = args.style_guide_path or f"/artifacts/style_guides/{slug}.md"

    inp = RedditMonitorInput(
        company_name=args.company_name,
        company_slug=slug,
        workspace_id=args.workspace_id,
        workspace_slug=args.workspace_slug or slug,
        company_context_path=company_context_path,
        icp_persona_path=icp_persona_path,
        style_guide_path=style_guide_path,
        subreddits=_split_csv(args.subreddits) or ["marketing"],
        max_threads_per_subreddit=args.max_threads,
        max_age_hours=args.max_age_hours,
        shortlist_k=args.shortlist_k,
        top_k=args.top_k,
        dry_run=bool(args.dry_run),
        send_slack=not bool(args.no_slack),
        send_discord=not bool(args.no_discord),
    )

    app = build_graph()
    result = app.invoke({"input": inp})

    drafts = result.get("drafts") or []
    notified = result.get("notified_ids") or []
    errors = result.get("notify_errors") or []

    summary = {
        "draft_count": len(drafts),
        "notified_ids": notified,
        "notify_errors": errors,
    }
    logger.info(
        "Reddit HIL Monitor complete: drafts=%d notified=%d errors=%d",
        len(drafts), len(notified), len(errors),
    )
    if errors:
        for e in errors:
            logger.warning("Notify error: %s", e)
    logger.info("run_summary: %s", json.dumps(summary, indent=2))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
