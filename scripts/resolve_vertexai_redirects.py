#!/usr/bin/env python3
"""
One-time script: Replace vertexaisearch.cloud.google.com redirect URLs with actual destination URLs.

Vertex AI Search returns wrapper URLs that redirect to the real page. This script follows
redirects and replaces those URLs with the final destination in enriched_citations.json.

Usage:
  python scripts/resolve_vertexai_redirects.py
  python scripts/resolve_vertexai_redirects.py --input path/to/enriched_citations.json --output path/to/output.json
  python scripts/resolve_vertexai_redirects.py --in-place   # Overwrites input file
"""
import argparse
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_INPUT = _PROJECT_ROOT / "artifacts/gap_analysis/ramp/enriched_citations.json"
_VERTEX_DOMAIN = "vertexaisearch.cloud.google.com"


def _is_vertex_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return _VERTEX_DOMAIN in (parsed.netloc or "")
    except Exception:
        return False


def _resolve_url(client: httpx.Client, url: str, timeout: int = 20) -> str | None:
    """Follow redirects and return the final URL, or None on failure."""
    try:
        resp = client.get(url, follow_redirects=True, timeout=timeout)
        if resp.status_code >= 400:
            return None
        final = str(resp.url)
        if final and (final.startswith("http://") or final.startswith("https://")):
            return final
        return None
    except Exception:
        return None


def _domain_from_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc or ""


def main() -> int:
    p = argparse.ArgumentParser(description="Resolve vertexaisearch redirect URLs to actual URLs.")
    p.add_argument("--input", type=Path, default=_DEFAULT_INPUT)
    p.add_argument("--output", type=Path, default=None)
    p.add_argument("--in-place", action="store_true", help="Overwrite input file")
    p.add_argument("--delay", type=float, default=0.3, help="Delay between requests (seconds)")
    p.add_argument("--timeout", type=int, default=20)
    p.add_argument("--limit", type=int, default=None, help="Max URLs to resolve (for testing)")
    args = p.parse_args()

    input_path = args.input.resolve()
    if not input_path.exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        return 1

    output_path = args.output
    if args.in_place:
        output_path = input_path
    elif output_path is None:
        output_path = input_path.with_stem(input_path.stem + "_resolved")

    print(f"Reading {input_path}...")
    data = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        print("Error: expected a JSON array", file=sys.stderr)
        return 1

    # Collect unique vertexaisearch URLs
    vertex_urls: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if url and _is_vertex_url(url):
            vertex_urls.add(url)

    vertex_urls = sorted(vertex_urls)
    if args.limit:
        vertex_urls = vertex_urls[: args.limit]
        print(f"Found {len(vertex_urls)} vertexaisearch URLs to resolve (--limit {args.limit})")
    else:
        print(f"Found {len(vertex_urls)} unique vertexaisearch URLs to resolve")
    if not vertex_urls:
        print("Nothing to do.")
        return 0

    # Resolve each unique URL
    url_map: dict[str, str] = {}
    total = len(vertex_urls)
    with httpx.Client(follow_redirects=True) as client:
        for i, url in enumerate(vertex_urls):
            resolved = _resolve_url(client, url, timeout=args.timeout)
            if resolved and resolved != url and not _is_vertex_url(resolved):
                url_map[url] = resolved
                print(f"  [{i+1}/{total}] {url[:60]}... -> {resolved[:70]}...")
            else:
                print(f"  [{i+1}/{total}] FAILED: {url[:80]}...", file=sys.stderr)
            time.sleep(args.delay)

    print(f"\nResolved {len(url_map)} URLs successfully")

    # Replace URLs and domains in data
    replaced = 0
    for item in data:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if url and url in url_map:
            new_url = url_map[url]
            item["url"] = new_url
            item["domain"] = _domain_from_url(new_url)
            replaced += 1

    print(f"Replaced {replaced} citations in data")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
