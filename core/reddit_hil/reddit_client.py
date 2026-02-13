from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from core.models.reddit_hil import RedditThread
from core.config.settings import settings


@dataclass(frozen=True)
class RedditAuthConfig:
    client_id: str
    client_secret: str
    user_agent: str


def _get_auth_config() -> RedditAuthConfig:
    client_id = settings.reddit_client_id
    client_secret = settings.reddit_client_secret
    user_agent = settings.reddit_user_agent

    missing: List[str] = []
    if not client_id:
        missing.append("REDDIT_CLIENT_ID")
    if not client_secret:
        missing.append("REDDIT_CLIENT_SECRET")
    if not user_agent:
        missing.append("REDDIT_USER_AGENT")

    if missing:
        raise RuntimeError(f"Missing required env var(s): {', '.join(missing)}")

    return RedditAuthConfig(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
    )


def _get_praw():
    try:
        import praw  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "praw is not installed. Install it (e.g., `pip install praw`)."
        ) from e
    return praw


def _get_reddit_readonly():
    """
    Return a PRAW Reddit client that is guaranteed to be read-only.

    We intentionally do NOT support refresh tokens / username-password auth in V1.
    """
    praw = _get_praw()
    cfg = _get_auth_config()
    reddit = praw.Reddit(
        client_id=cfg.client_id,
        client_secret=cfg.client_secret,
        user_agent=cfg.user_agent,
        # No username/password/refresh_token => read-only app access.
    )

    # Safety: ensure we never accidentally run in a logged-in mode.
    # PRAW sets .read_only True when no auth grants are present.
    if not getattr(reddit, "read_only", False):
        raise RuntimeError(
            "Reddit client is not in read-only mode. "
            "Refusing to proceed to avoid any possibility of posting."
        )
    return reddit


def fetch_new_threads(
    subreddit: str,
    limit: int = 25,
    *,
    include_selftext: bool = True,
) -> List[RedditThread]:
    """
    Fetch newest threads from a subreddit via the official Reddit API (PRAW).

    Read-only by construction.
    """
    sr = subreddit.strip()
    sr = sr[2:] if sr.lower().startswith("r/") else sr
    reddit = _get_reddit_readonly()
    listing = reddit.subreddit(sr).new(limit=limit)

    threads: List[RedditThread] = []
    for sub in listing:
        try:
            author = None
            try:
                author = sub.author.name if sub.author else None
            except Exception:
                author = None

            selftext: Optional[str] = None
            if include_selftext and getattr(sub, "is_self", False):
                selftext = (getattr(sub, "selftext", None) or None)  # type: ignore[assignment]

            threads.append(
                RedditThread(
                    id=str(getattr(sub, "id")),
                    subreddit=str(getattr(getattr(sub, "subreddit", None), "display_name", sr)),
                    title=str(getattr(sub, "title", "")),
                    url=str(getattr(sub, "url", "")),
                    created_utc=int(getattr(sub, "created_utc", 0)),
                    score=int(getattr(sub, "score", 0)),
                    num_comments=int(getattr(sub, "num_comments", 0)),
                    is_self=bool(getattr(sub, "is_self", True)),
                    selftext=selftext,
                    author=author,
                    locked=getattr(sub, "locked", None),
                    stickied=getattr(sub, "stickied", None),
                    over_18=getattr(sub, "over_18", None),
                )
            )
        except Exception:
            # Be resilient: skip malformed entries rather than failing the whole run.
            continue

    return threads
