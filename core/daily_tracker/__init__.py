"""Daily LLM Visibility Tracker — Pipeline 0.

Monitors brand visibility across AI platforms (ChatGPT, Claude, Gemini,
Perplexity) by running tracked prompts, detecting brand mentions/citations,
and computing deterministic analytics (mention rate, share of voice,
citation rate, trends).

Sub-modules:
    protocols      — ``@runtime_checkable`` Protocol interfaces
    prompt_library — Prompt CRUD + gap-analysis import
    platform_runner — Adapter wrapping gap analysis search engines
    mention_detector — Deterministic brand/competitor mention detection
    analytics_engine — Orchestrates MetricCalculator strategy instances
    orchestrator   — Mediator coordinating the full daily-run lifecycle
    metrics/       — Individual ``MetricCalculator`` strategy implementations
"""
