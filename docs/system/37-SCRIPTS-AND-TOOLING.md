# Scripts & Tooling

> **Location:** `scripts/`, `Dockerfile`, `docker-compose.yml`, `.github/workflows/`
> **Owner:** DevOps / Full Stack
> **Last Updated:** 2026-04-09

## Overview

CLI scripts for pipeline execution, deployment configuration via Docker, and CI/CD via GitHub Actions.

## Pipeline Scripts

| Script | Purpose |
|--------|---------|
| `run_server.py` | Start FastAPI server (Uvicorn) |
| `run_content_engine.py` | Execute Content Engine pipeline |
| `run_topic_discovery.py` | Run Topic Discovery (Pipeline A or B) |
| `run_td_rescore.py` | Re-run TD Phase 2.5 scoring + persona affinity |
| `run_audience_persona.py` | Generate audience personas |
| `run_kb.py` | Knowledge Base research pipeline |
| `run_gap_analysis.py` | Full Gap Analysis pipeline |
| `run_gap_step.py` | Run individual GA steps |
| `run_voice_style_guide.py` | Voice/style guide generation |
| `run_site_audit.py` | Site audit pipeline |

## Utility Scripts

| Script | Purpose |
|--------|---------|
| `dev.sh` | Development environment setup |
| `kill_port.sh` | Clean up dangling processes |
| `backfill_gap_data.py` | Migrate filesystem JSON to Postgres |
| `migrate_chroma_to_pgvector.py` | One-time ChromaDB → pgvector migration |
| `upload_prompts_to_hub.py` | Push prompts to LangSmith Hub |
| `fake_onboarding_sse.py` | Mock SSE for frontend testing |
| `strip_embeddings_from_json.py` | Clean embeddings from artifacts |

## Docker Configuration

### Dockerfile (Multi-stage)
- **Builder:** Compile Python dependencies
- **Runtime:** slim image + libpq5 + Playwright Chromium
- **Non-root user:** `appuser` (UID/GID)
- **Healthcheck:** `GET /health` every 30s
- **Startup:** Alembic migrations → single-worker Uvicorn on `$PORT`
- **Graceful shutdown:** 30s SIGTERM timeout

### docker-compose.yml
- **db:** pgvector:pg17 (port 5432)
- **redis:** redis:7.4-alpine (port 6379, 256MB max)
- **backend:** Hot-reload, mounted code volumes
- **frontend:** node:20-slim (port 3000)
- **migrate:** One-off Alembic upgrade (profile: migrate)
- **Staging:** Separate db-staging (5433) + redis-staging (6380)

## CI/CD (`.github/workflows/ci.yml`)

| Job | What It Does |
|-----|-------------|
| `backend-test` | Ubuntu + pgvector + Redis → pip install → Alembic → pytest |
| `frontend-build` | Node 20 → type check → npm build |
| `docker-build` | Multi-stage Docker build with cache |

**Triggers:** Push to main, PRs to main/staging

**CI exclusion:** `tests/api/test_hitl_interrupt_resume.py` (HITL tests excluded)
