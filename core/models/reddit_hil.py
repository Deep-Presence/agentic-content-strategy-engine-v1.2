from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl


class RedditMonitorInput(BaseModel):
    """
    Inputs for the Reddit Human-in-the-Loop monitor.

    Artifacts:
    - company_context_path: /artifacts/company_context/<company_slug>.md
    - icp_persona_path: /artifacts/personas/<company_slug>__persona-icp.md
    - style_guide_path: /artifacts/style_guides/<company_slug>.md
    """

    company_name: str
    company_slug: str = Field(
        ...,
        description="Lowercase, dash-separated. Used for defaults + cache paths.",
    )
    workspace_id: str = Field(
        default="",
        description="Workspace id used for BYOK model resolution.",
    )
    workspace_slug: str = Field(
        default="",
        description="Workspace slug used for BYOK model resolution.",
    )

    # Artifact paths (DeepAgents/FilesystemBackend virtual paths)
    company_context_path: str
    icp_persona_path: str
    style_guide_path: str

    # Reddit scan configuration
    subreddits: List[str] = Field(default_factory=lambda: ["marketing"])
    max_threads_per_subreddit: int = Field(default=25, ge=1, le=250)
    max_age_hours: int = Field(default=72, ge=1, le=24 * 30)

    # Ranking/filtering
    shortlist_k: int = Field(default=15, ge=1, le=100)
    top_k: int = Field(default=3, ge=1, le=10)

    # Notifications
    send_slack: bool = True
    send_discord: bool = True

    # Safety/behavior controls
    dry_run: bool = Field(
        default=False,
        description="If True, do everything except sending webhooks.",
    )


class RedditThread(BaseModel):
    id: str
    subreddit: str
    title: str
    url: HttpUrl
    created_utc: int
    score: int = 0
    num_comments: int = 0
    is_self: bool = True
    selftext: Optional[str] = None
    author: Optional[str] = None
    locked: Optional[bool] = None
    stickied: Optional[bool] = None
    over_18: Optional[bool] = None

    def text_for_matching(self, max_chars: int = 4000) -> str:
        body = (self.selftext or "").strip()
        combined = f"{self.title}\n\n{body}".strip()
        return combined[:max_chars]


class DraftNotification(BaseModel):
    thread: RedditThread
    fit_score: float = Field(default=0.0, ge=0.0, le=1.0)
    why_match: str
    draft_markdown: str
    metadata: Dict[str, str] = Field(default_factory=dict)

