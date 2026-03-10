#!/bin/bash
# scripts/codex/context.sh — Shared project context for all Codex calls
# Sourced by plan-review.sh, code-review.sh, sprint-review.sh, architecture.sh

CODEX_TIMEOUT=120

PROJECT_CONTEXT="
PROJECT: content-strategy-engine (Deep Presence)
PURPOSE: B2B platform helping companies get cited in AI search results (AEO)
STACK: Python 3.12, asyncio, Pydantic v2, FastAPI, LangGraph, raw LLM SDK clients
PIPELINES:
  1. Research Artifacts — LangGraph agents (Gemini+Perplexity) produce company context, personas, style guides with HITL approval
  2. Gap Analysis — 8-step data pipeline: crawl→queries→search 4 AI platforms→enrich→embed→analyze→visualize→report
  3. Content Generation — 4-stage: Planner(Sonnet)→Workers(parallel)→Evaluator(4-dim quality gate)→HITL Review
  API: FastAPI REST with SSE streaming, HITL approval endpoints, JSON-backed TaskStore

KEY RULES:
  - All new Pydantic fields MUST have defaults (backward compat with existing JSON artifacts)
  - Raw SDK clients only — no LangChain wrappers in gap analysis or content engine
  - model_dump(mode='json') for all serialization (HttpUrl objects break without it)
  - ThreadPoolExecutor(max_workers=1) for all DeepAgents agent.invoke() calls
  - Embedding dimension: 1536 (text-embedding-3-small)
  - Each pipeline step independently recoverable via skip_steps

MODELS: 20+ Pydantic v2 models in core/models/gap_analysis.py, 15+ in content_generation.py
TESTS: 351 tests all passing (126 API, 57 content engine, rest gap analysis + shared tools)
TECH DEBT: Zero tests for research pipeline and Reddit HIL, no structured logging, TaskStore is JSON-only
"

run_codex() {
    local prompt="$1"
    timeout "$CODEX_TIMEOUT" codex --exec "$prompt" 2>&1
    local exit_code=$?
    if [ $exit_code -eq 124 ]; then
        echo "⚠️  Codex timed out after ${CODEX_TIMEOUT}s. Proceeding without review."
        echo "   Log this in _memory/failures.json and retry at /review stage."
    fi
    return $exit_code
}
