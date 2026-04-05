"""URL normalization for content inventory dedup.

This is intentionally MORE aggressive than the site audit's ``normalize_url``
in ``core/site_audit/steps/s1_discover.py`` which preserves query params for
crawl dedup.  The content inventory version strips query params, forces HTTPS,
and strips ``www.`` so that the same page discovered via different sources
(crawl, CMS, CSV) deduplicates to a single record.
"""
from __future__ import annotations

from urllib.parse import urlparse, urlunparse


def normalize_url(url: str) -> str:
    """Normalize a URL for cross-source dedup in content inventory.

    Rules:
        1. Lowercase scheme and host
        2. Strip fragment (#...)
        3. Strip ALL query parameters (?...)
        4. Remove trailing slash (unless path is just "/")
        5. Force https scheme
        6. Strip www. prefix from host

    Examples::

        >>> normalize_url("HTTP://WWW.Example.Com/Blog/Post/?utm_source=x#section")
        'https://example.com/blog/post'

        >>> normalize_url("https://example.com/")
        'https://example.com'

        >>> normalize_url("http://www.example.com:8080/page")
        'https://example.com:8080/page'
    """
    if not url or not url.strip():
        return url

    url = url.strip()

    # Ensure there's a scheme so urlparse doesn't treat host as path
    url_lower = url.lower()
    if not url_lower.startswith(("http://", "https://", "//")):
        url = "https://" + url

    try:
        parsed = urlparse(url)

        # Lowercase scheme and host
        scheme = parsed.scheme.lower() if parsed.scheme else "https"
        netloc = parsed.netloc.lower()

        # Force https
        if scheme in ("http", ""):
            scheme = "https"

        # Strip www. prefix (preserve port if present)
        if netloc.startswith("www."):
            netloc = netloc[4:]

        # Rebuild with no fragment and no query
        normalized = parsed._replace(
            scheme=scheme,
            netloc=netloc,
            fragment="",
            query="",
        )
        result = urlunparse(normalized)

        # Remove trailing slash (unless path is empty — i.e., just scheme://host)
        if result.endswith("/") and urlparse(result).path != "":
            result = result.rstrip("/")

        return result
    except Exception:
        return url


def extract_url_path(url: str) -> str:
    """Extract and normalize the path component from a full URL.

    Used to match ``content_inventory.url_normalized`` (full URL) against
    ``ga4_traffic_data.landing_page_url`` (path-only from GA4's
    ``landingPage`` dimension).

    Returns lowercase path with trailing slash stripped (unless root ``/``).

    Examples::

        >>> extract_url_path("https://example.com/Blog/Post")
        '/blog/post'

        >>> extract_url_path("https://example.com/")
        '/'

        >>> extract_url_path("/already-a-path/")
        '/already-a-path'

        >>> extract_url_path("")
        '/'
    """
    if not url or not url.strip():
        return "/"

    url = url.strip()

    try:
        parsed = urlparse(url)
        path = parsed.path.lower()

        if not path:
            return "/"

        # Strip trailing slash unless root
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")

        return path
    except Exception:
        return "/"
