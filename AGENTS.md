# AGENTS.md — Codex Workspace Guide

Read `./_memory/` first on every session.

## Session Boot

On every new session, in this order:

1. Read `_memory/progress.json`
2. Read `_memory/failures.json`
3. Read `_memory/decisions.json`
4. Read `_memory/context.json`
5. Read this `AGENTS.md`

Then decide whether you also need:

- `.codex/skills/memory-discipline/SKILL.md` for memory updates
- `.codex/skills/tdd/SKILL.md` before writing tests
- `.codex/skills/model-changes/SKILL.md` before changing Pydantic models or API schemas
- `.codex/skills/pipeline-testing/SKILL.md` before touching pipeline tests or provider mocks
- `.codex/commands/*.md` for repeatable repo workflows
- `frontend/claude.md` when touching the frontend design system or dashboard flows
- `.claude/sprints/` only as historical reference unless the user explicitly asks you to update Claude-owned planning docs

## Non-Destructive Boundary

- Do not delete, rewrite, or repurpose anything under `.claude/` unless the user explicitly asks.
- Keep Codex-owned workflow files under `.codex/`.
- `_memory/` is shared project memory. Reuse it; do not create a second memory store.

## Project Snapshot

This repo is `content-strategy-engine`, the Deep Presence product that helps B2B companies get cited in AI search results.

Core stack:

- Backend: Python 3.12, asyncio, Pydantic v2, FastAPI, SQLAlchemy, Redis, LangGraph
- Frontend: Next.js 14 App Router, React 18, TypeScript, Tailwind, Zustand
- Storage: PostgreSQL + pgvector, Redis, blob storage

Primary product areas:

- Research artifacts: knowledge base, audience personas, voice style guide
- Gap analysis: multi-step crawl/search/enrich/analyze/report pipeline
- Content engine v1.3: planner, brief builder, workers, evaluator, HITL
- Topic discovery, onboarding, daily tracker, Reddit HIL monitor

## Repo Rules

- All new Pydantic fields need defaults.
- Use `model_dump(mode="json")` when serializing Pydantic models.
- Raw SDK clients stay raw in the pipeline codepaths; do not introduce LangChain wrappers where the repo forbids them.
- `core/` must not import from `api/`.
- `DATABASE_URL` and `REDIS_URL` are required in the current architecture.
- Topic Discovery is DB-first; do not reintroduce filesystem-only hot paths.
- Prefer targeted tests first, then broaden validation based on risk.
- When the repo is dirty, never revert unrelated user changes.

## Working Style

- Start by loading memory and current file context, not by guessing.
- Prefer minimal, high-confidence changes over broad speculative refactors.
- For substantial work, state a short plan before editing.
- Before editing models, contracts, or cross-pipeline flows, check `failures.json` and `decisions.json` for related constraints.
- If a task creates durable new knowledge, update `_memory/` and, if relevant, `.codex/sprints/pending/backlog.md`.

## Codex-Owned Paths

- Commands: `.codex/commands/`
- Skills: `.codex/skills/`
- Sprint notes and backlog: `.codex/sprints/`

Historical Claude planning artifacts remain under `.claude/sprints/`. Treat them as reference material unless asked to sync both systems.
