"""Domain normalization, slug derivation, and mutable-field allowlists.

Extracted from ``api.auth.store`` so both the JSON-backed and DB-backed
auth services share these pure functions.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple
from urllib.parse import urlparse


# Known multi-part TLDs where the second-level domain is part of the TLD.
_MULTI_PART_TLDS: frozenset[str] = frozenset({
    "co.uk", "co.jp", "co.in", "co.kr", "co.nz", "co.za", "co.id",
    "com.au", "com.br", "com.cn", "com.mx", "com.tw", "com.sg",
    "org.uk", "net.au", "ac.uk", "gov.uk",
})


def normalize_domain(raw: str) -> Tuple[str, Optional[str]]:
    """Normalize a domain to its root form.

    Returns ``(root_domain, subdomain_or_none)``.

    - Strips protocol (http/https), path, trailing slash
    - Strips www (not considered a meaningful subdomain)
    - Extracts root domain vs subdomain
    - Handles multi-part TLDs (.co.uk, .com.au, etc.)
    - Returns lowercase

    Examples::

        "ramp.com"           → ("ramp.com", None)
        "www.ramp.com"       → ("ramp.com", None)
        "app.ramp.com"       → ("ramp.com", "app.ramp.com")
        "https://ramp.com/p" → ("ramp.com", None)
        "app.example.co.uk"  → ("example.co.uk", "app.example.co.uk")
    """
    domain = raw.strip().lower()

    # Strip protocol
    if "://" in domain:
        domain = urlparse(domain).netloc or domain.split("://", 1)[1]

    # Strip path / trailing slash
    domain = domain.split("/")[0]
    # Strip port
    domain = domain.split(":")[0]

    # Strip www
    original = domain
    if domain.startswith("www."):
        domain = domain[4:]

    parts = domain.split(".")

    if len(parts) <= 2:
        # Already a root domain (e.g., ramp.com)
        return domain, None

    # Check for multi-part TLD
    possible_tld = ".".join(parts[-2:])
    if possible_tld in _MULTI_PART_TLDS:
        # e.g., app.example.co.uk → root = example.co.uk
        root = ".".join(parts[-3:])
        if len(parts) > 3:
            return root, domain
        return root, None
    else:
        # e.g., app.ramp.com → root = ramp.com
        root = ".".join(parts[-2:])
        subdomain = domain if domain != root else None
        # Don't return www-stripped as a subdomain
        if subdomain and original.startswith("www."):
            subdomain = None
        return root, subdomain


def derive_slug(name: str) -> str:
    """Derive a URL-safe kebab-case slug from a company name."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# Allowlists for mutable fields — prevents callers from overwriting
# immutable identity fields (id, created_at, slug) via **kwargs.
COMPANY_MUTABLE_FIELDS: frozenset[str] = frozenset({
    "name", "domain", "additional_domains", "industry",
})
PRODUCT_MUTABLE_FIELDS: frozenset[str] = frozenset({
    "name", "domain", "description",
})
USER_MUTABLE_FIELDS: frozenset[str] = frozenset({
    "role", "first_name", "last_name", "is_active",
})
