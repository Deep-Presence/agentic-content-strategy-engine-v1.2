"""Authority feature extractor."""
from __future__ import annotations

import logging
import re
from typing import Dict
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .base import BaseExtractor

logger = logging.getLogger(__name__)


class AuthorityFeatureExtractor(BaseExtractor):
    """Extract authority features from URL and HTML content."""

    def extract(self, content: str) -> Dict[str, object]:
        raise NotImplementedError("Use extract_from_url for authority features.")

    def extract_from_url(self, url: str, html_content: str | None = None) -> Dict[str, object]:
        """Extract authority signals using URL and optional HTML."""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        is_gov_edu = domain.endswith(".gov") or domain.endswith(".edu")
        https_status = parsed.scheme == "https"

        has_about_page = False
        has_contact_info = False
        author_present = False
        has_citations = False
        has_research_refs = False

        if html_content:
            soup = BeautifulSoup(html_content, "html.parser")
            links = [a.get("href", "") for a in soup.find_all("a")]
            has_about_page = any("about" in (link or "").lower() for link in links)
            has_contact_info = any("contact" in (link or "").lower() for link in links)
            text = soup.get_text(" ", strip=True).lower()
            author_present = bool(re.search(r"\bby\s+[a-z]", text)) or bool(
                soup.find(attrs={"itemprop": "author"})
            )
            has_citations = "doi" in text or bool(re.search(r"\[[0-9]+\]", text))
            has_research_refs = any(token in text for token in ["arxiv", "pubmed", "doi.org"])

        # Heuristic domain age and authority proxy
        domain_age_years = 0.0
        domain_authority = 10.0 if is_gov_edu else 1.0

        features = {
            "domain_authority": domain_authority,
            "https_status": https_status,
            "is_gov_edu": is_gov_edu,
            "has_about_page": has_about_page,
            "has_contact_info": has_contact_info,
            "author_present": author_present,
            "has_citations": has_citations,
            "has_research_refs": has_research_refs,
            "domain_age_years": domain_age_years,
        }
        logger.debug(
            "Authority features for %s: https=%s gov_edu=%s",
            domain,
            https_status,
            is_gov_edu,
        )
        return features