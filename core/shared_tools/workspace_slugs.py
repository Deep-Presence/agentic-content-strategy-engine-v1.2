"""Workspace slug helpers for the company→workspace transition.

During migration:
  workspace_slug      == legacy company_slug
  effective_slug      == workspace_slug or f"{workspace_slug}__{product_slug}"
"""

from __future__ import annotations


def effective_slug(workspace_slug: str, product_slug: str | None = None) -> str:
    """Build the legacy effective slug used by pipeline artifacts and runs."""
    if product_slug:
        return f"{workspace_slug}__{product_slug}"
    return workspace_slug
