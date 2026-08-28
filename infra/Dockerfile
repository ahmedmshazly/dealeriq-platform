# DealerIQ API - production image (FastAPI + analytics workspace).
# Build from repo root: docker build -f infra/Dockerfile -t dealeriq-api .

FROM python:3.12-slim-bookworm AS base

COPY --from=ghcr.io/astral-sh/uv:0.7.12 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Dependency layer (workspace metadata only)
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY packages/analytics/pyproject.toml packages/analytics/pyproject.toml

# Placeholder package trees so uv can resolve workspace members before full COPY
RUN mkdir -p apps/api/src/dealeriq_api packages/analytics/src/dealeriq_analytics \
    && touch apps/api/src/dealeriq_api/__init__.py packages/analytics/src/dealeriq_analytics/__init__.py

RUN uv sync --frozen --no-dev --package dealeriq-api

# Application source
COPY apps/api apps/api
COPY packages/analytics packages/analytics
COPY infra/scripts/api-entrypoint.sh /usr/local/bin/api-entrypoint.sh
RUN chmod +x /usr/local/bin/api-entrypoint.sh \
    && uv sync --frozen --no-dev --package dealeriq-api

WORKDIR /app/apps/api
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/v1/health || exit 1

ENTRYPOINT ["/usr/local/bin/api-entrypoint.sh"]
CMD ["uvicorn", "dealeriq_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
