#!/usr/bin/env python3
"""
Rewrite a copy of company_embeddings.json without the embedding vectors.

Usage:
  python scripts/strip_embeddings_from_json.py
  python scripts/strip_embeddings_from_json.py --input path/to/file.json --output path/to/output.json
"""
import argparse
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--input",
        default=_PROJECT_ROOT / "artifacts/gap_analysis/ramp/company_embeddings.json",
        type=Path,
    )
    p.add_argument(
        "--output",
        default=None,
        type=Path,
        help="Default: <input>_no_embeddings.json",
    )
    args = p.parse_args()

    input_path = args.input.resolve()
    output_path = args.output or input_path.with_stem(
        input_path.stem + "_no_embeddings"
    )

    if not input_path.exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        return 1

    print(f"Reading {input_path}...")
    data = json.loads(input_path.read_text(encoding="utf-8"))

    if not isinstance(data, list):
        print("Error: expected a JSON array", file=sys.stderr)
        return 1

    print(f"Stripping embeddings from {len(data)} items...")
    stripped = []
    for item in data:
        copy = dict(item)
        copy.pop("embedding", None)
        stripped.append(copy)

    print(f"Writing {output_path}...")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(stripped, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Done. Output: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
