# ── Stage 1: Builder ─────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Build deps for compiled packages (psycopg2-binary wheels, scipy, numpy)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# --extra-index-url for PyTorch CPU is already in requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime ─────────────────────────────────────────
FROM python:3.12-slim

# Runtime-only system deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python packages from builder
COPY --from=builder /install /usr/local

# Application code
COPY core/ ./core/
COPY api/ ./api/
COPY scripts/ ./scripts/
COPY alembic.ini .

# Artifacts directory (JSON file storage at runtime)
RUN mkdir -p /app/artifacts/_jobs /app/artifacts/_auth /app/artifacts/_logs

# Non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

STOPSIGNAL SIGTERM

# Production: no reload, single worker (accepted constraint per PB-73/77)
CMD ["python", "-m", "uvicorn", "api.app:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--log-config", "/dev/null", \
     "--timeout-graceful-shutdown", "30"]
