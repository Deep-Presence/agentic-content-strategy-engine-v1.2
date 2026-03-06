"""Citation Rate Calculator — computes citation frequency from platform responses.

Tracks how often brand domains/URLs appear in AI platform citations.
Also computes average citation rank (lower = better, 1-indexed).

Why citation rate matters:
    Being mentioned is good; being *cited with a link* is significantly
    better for driving referral traffic from AI platforms.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any
from urllib.parse import urlparse

from core.daily_tracker.metrics.base import MetricCalculator


class CitationRateCalculator(MetricCalculator):
    """Computes citation rate: fraction of responses containing citations.

    Input responses must contain:
        - ``mention_analysis.citations`` (list[str]): extracted URLs.
        - ``mention_analysis.citation_rank`` (int | None): position of brand
          in citation list (1-indexed, lower is better).

    Kwargs:
        - ``brand_domains`` (list[str]): domains owned by the brand
          (e.g. ["ramp.com", "blog.ramp.com"]).
        - ``top_n`` (int): how many top URLs to return (default 10).

    Returns:
        dict with ``overall_citation_rate``, ``avg_citation_rank``,
        ``by_domain``, ``top_cited_urls``.
    """

    @property
    def name(self) -> str:
        return "citation_rate"

    async def compute(self, responses: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        """Compute citation metrics from platform responses.

        Args:
            responses: List of response dicts with mention analysis data.
            **kwargs: Optionally ``brand_domains`` (list[str]) and
                ``top_n`` (int, default 10).

        Returns:
            {
                "overall_citation_rate": float,
                "avg_citation_rank": float | None,
                "by_domain": {"ramp.com": float, ...},
                "top_cited_urls": [{"url": str, "count": int}, ...],
            }
        """
        brand_domains: list[str] = kwargs.get("brand_domains", [])
        top_n: int = kwargs.get("top_n", 10)

        if not responses:
            return {
                "overall_citation_rate": 0.0,
                "avg_citation_rank": None,
                "by_domain": {},
                "top_cited_urls": [],
            }

        total_responses = len(responses)
        responses_with_citation = 0
        citation_ranks: list[int] = []
        all_urls: Counter[str] = Counter()
        domain_response_count: dict[str, int] = defaultdict(int)

        for resp in responses:
            analysis = resp.get("mention_analysis", {})
            citations = analysis.get("citations", [])
            citation_rank = analysis.get("citation_rank")

            if citations:
                responses_with_citation += 1

                # Track citation rank when present
                if citation_rank is not None:
                    citation_ranks.append(int(citation_rank))

                # Count URLs and per-domain presence
                domains_seen_this_response: set[str] = set()
                for url in citations:
                    all_urls[url] += 1
                    domain = _extract_domain(url)
                    if domain and domain not in domains_seen_this_response:
                        domain_response_count[domain] += 1
                        domains_seen_this_response.add(domain)

        # Why: citation rate = responses with >=1 citation / total responses.
        overall_rate = responses_with_citation / total_responses if total_responses > 0 else 0.0

        # Why: avg rank is None when no ranks are recorded — better than
        # returning 0 which would imply "best possible rank".
        avg_rank: float | None = None
        if citation_ranks:
            avg_rank = sum(citation_ranks) / len(citation_ranks)

        # Per-domain rates (only for requested brand domains, or all if none specified)
        by_domain: dict[str, float] = {}
        domains_to_report = brand_domains if brand_domains else list(domain_response_count.keys())
        for domain in domains_to_report:
            count = domain_response_count.get(domain, 0)
            by_domain[domain] = count / total_responses if total_responses > 0 else 0.0

        # Top cited URLs
        top_cited = [
            {"url": url, "count": count}
            for url, count in all_urls.most_common(top_n)
        ]

        return {
            "overall_citation_rate": overall_rate,
            "avg_citation_rank": avg_rank,
            "by_domain": by_domain,
            "top_cited_urls": top_cited,
        }


def _extract_domain(url: str) -> str:
    """Extract the domain (hostname) from a URL string.

    Args:
        url: A URL string (e.g. "https://ramp.com/blog/post").

    Returns:
        Domain string (e.g. "ramp.com"), or empty string if parsing fails.
    """
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower() or ""
    except Exception:
        return ""
