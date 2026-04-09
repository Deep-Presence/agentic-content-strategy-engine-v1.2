# Core Audit Logging

> **Location:** `core/audit/`
> **Owner:** Core
> **Dependencies:** structlog, `core/db/models/audit_log.py`
> **Dependents:** `api/app.py` (sink setup), auth routes, HITL handlers
> **Last Updated:** 2026-04-09

## Overview

The audit module provides structured, immutable audit logging for security-sensitive events (authentication, HITL decisions, pipeline launches). It uses a dual-mode architecture: all events are logged via structlog (always), and optionally persisted to the `audit_logs` DB table via a pluggable sink pattern. Sensitive data is automatically masked by a structlog processor.

## Architecture

```
log_auth_event() / log_hitl_decision() / log_pipeline_launch()
    │
    ├── structlog.info() ── always (JSON/console log output)
    │
    └── sink.persist() ── optional (DB write via DbAuditSink)
                           NoOpAuditSink (default, no DB)
```

## File Structure

| File | Purpose |
|------|---------|
| `models.py` | `AuditEvent`, `AuditEventType`, `AuditCategory` |
| `logger.py` | Public API: `log_auth_event`, `log_hitl_decision`, `set_sink` |
| `sink.py` | `AuditSinkProtocol`, `NoOpAuditSink`, `DbAuditSink` |
| `masking.py` | `SensitiveDataMasker` — structlog processor |

## Event Types

| Category | Event Types |
|----------|------------|
| AUTH | LOGIN_SUCCESS, LOGIN_FAILED, REGISTER, INVITE_CREATED, INVITE_REDEEMED |
| HITL | HITL_DECISION, HITL_DECISION_REJECTED |
| PIPELINE | PIPELINE_STARTED |

## Sensitive Data Masking

`SensitiveDataMasker` is a structlog processor (inserted last in chain) that recursively redacts:

**Field names** (case-insensitive substring match): password, secret, token, api_key, authorization, credential, invite_code, access_token, refresh_token, private_key, client_secret, webhook_url

**Value patterns** (regex): Anthropic keys (sk-ant-*), OpenAI keys (sk-*), Google keys (AIzaSy*), LangSmith keys (ls*), Perplexity keys (pplx-*), Bearer tokens, JWTs (eyJ*), PBKDF2/bcrypt/argon2 hashes, emails (structured fields only)

**Control character stripping:** Replaces `\n\r\t` with space (log-injection hardening)

## Context Propagation

Events auto-attach `request_id` and `correlation_id` from structlog context (bound by `RequestLoggingMiddleware`). Enables trace linking across request/HITL/pipeline logs.

## Exception Safety

All DB write failures are caught, logged as warnings, and never re-raised. Audit logging never crashes callers.
