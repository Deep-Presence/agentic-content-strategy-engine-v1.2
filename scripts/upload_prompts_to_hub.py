#!/usr/bin/env python3
"""Upload all system prompts to LangSmith Hub.

Usage:
    python scripts/upload_prompts_to_hub.py           # Upload all prompts
    python scripts/upload_prompts_to_hub.py --dry-run  # Preview without uploading

Requires LANGSMITH_API_KEY env var.
Idempotent — safe to re-run. Updates existing prompts in-place.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Prompt name → (hub_name, module_path, constant_name)
PROMPTS = [
    ("outliner-system", "core.content_engine.prompts.outliner_prompts", "OUTLINER_SYSTEM_PROMPT"),
    ("drafter-system", "core.content_engine.prompts.drafter_prompts", "DRAFTER_SYSTEM_PROMPT"),
    ("drafter-revision", "core.content_engine.prompts.drafter_prompts", "REVISION_SYSTEM_PROMPT"),
    ("enricher-system", "core.content_engine.prompts.enricher_prompts", "ENRICHER_SYSTEM_PROMPT"),
    ("formatter-system", "core.content_engine.prompts.formatter_prompts", "FORMATTER_SYSTEM_PROMPT"),
    ("factual-judge-system", "core.content_engine.prompts.factual_judge_prompts", "FACTUAL_JUDGE_SYSTEM_PROMPT"),
    ("style-judge-system", "core.content_engine.prompts.style_judge_prompts", "STYLE_JUDGE_SYSTEM_PROMPT"),
    ("eeat-judge-system", "core.content_engine.prompts.eeat_judge_prompts", "EEAT_JUDGE_SYSTEM_PROMPT"),
    ("planner-system", "core.content_engine.prompts.planner_prompts", "PLANNER_SYSTEM_PROMPT"),
    ("strategic-planner-system", "core.content_engine.prompts.strategic_planner_prompts", "STRATEGIC_PLANNER_SYSTEM_PROMPT"),
    ("brief-builder-system", "core.content_engine.prompts.brief_builder_prompts", "BRIEF_BUILDER_SYSTEM_PROMPT"),
    ("linker-system", "core.content_engine.prompts.linker_prompts", "LINKER_SYSTEM_PROMPT"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload prompts to LangSmith Hub")
    parser.add_argument("--dry-run", action="store_true", help="Preview without uploading")
    args = parser.parse_args()

    import importlib

    try:
        from langsmith import Client
    except ImportError:
        print("ERROR: langsmith not installed. Run: pip install langsmith")
        sys.exit(1)

    from langchain_core.prompts import ChatPromptTemplate

    from core.config.settings import settings

    if not settings.langsmith_api_key:
        print("ERROR: LANGSMITH_API_KEY not set in .env.local")
        sys.exit(1)

    client_kwargs: dict = {"api_key": settings.langsmith_api_key}
    if settings.langsmith_workspace_id:
        client_kwargs["workspace_id"] = settings.langsmith_workspace_id
    client = Client(**client_kwargs)

    for hub_name, module_path, constant_name in PROMPTS:
        module = importlib.import_module(module_path)
        prompt_text = getattr(module, constant_name)
        char_count = len(prompt_text)

        if args.dry_run:
            print(f"[DRY RUN] Would upload: {hub_name} ({char_count:,} chars from {constant_name})")
            continue

        try:
            prompt_obj = ChatPromptTemplate.from_messages([
                ("system", prompt_text),
            ])
            client.push_prompt(
                hub_name,
                object=prompt_obj,
                description=f"System prompt: {constant_name} from {module_path}",
            )
            print(f"[OK] Uploaded: {hub_name} ({char_count:,} chars)")
        except Exception as exc:
            print(f"[FAIL] {hub_name}: {exc}")

    print(f"\nDone. {'(dry run — nothing uploaded)' if args.dry_run else f'{len(PROMPTS)} prompts uploaded.'}")


if __name__ == "__main__":
    main()
