---
title: Onboarding
description: Bootstrap, seed, first login, and a role tour of DealerIQ.
last-verified: 2026-07-17
---

# Onboarding

**Audience:** new contributors and reviewers.  
**Last updated:** 2026-07-17

## 1. Prerequisites

git, Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 20+, npm, Docker + Docker Compose.

## 2. Bootstrap and run

```bash
git clone <repo-url> dealeriq && cd dealeriq
make bootstrap    # uv + npm deps, pre-commit, .env from .env.example
make seed         # Postgres + MailHog, Alembic, synthetic data
make dev          # API :8000 + web :3000
```

Open http://localhost:3000 and http://localhost:8000/api/v1/docs.

Full troubleshooting: [runbooks/local-dev.md](../runbooks/local-dev.md).

## 3. Sign in

Dev seed accounts (never production):

| Role | Email | Password |
|------|-------|----------|
| Admin | `admin@dealeriq.dev` | `ChangeMe123!` |
| Manager | `manager1@dealeriq.dev` | `SeedUser123!` |
| Sales | `sales1@dealeriq.dev` | `SeedUser123!` |
| Analyst | `analyst1@dealeriq.dev` | `SeedUser123!` |

Admin’s first login forces a password change.

## 4. Role tour (10 minutes)

1. **Admin** — `/admin/users`, `/admin/permissions`, `/admin/audit-log`, `/admin/alert-rules`;
   trigger jobs from the admin surface / API (`jobs:trigger`).
2. **Manager** — Manager dashboard, order approvals, margin-visible inventory/orders, alerts.
3. **Sales** — Sales dashboard, create leads/orders; UI hides peer controls (API is the real gate).
4. **Analyst** — Forecasts, inventory intelligence, anomalies, customer analytics (read-heavy).

Permission details: [reference/permissions.md](../reference/permissions.md).

## 5. How the repo is organized

| Path | What |
|------|------|
| `apps/api` | FastAPI — sole security boundary |
| `apps/web` | Next.js 15 App Router + `features/` |
| `packages/analytics` | Forecasting, inventory intel, scoring |
| `packages/api-client` | Generated OpenAPI TypeScript client |
| `infra/` | Compose, Dockerfile, seed generator |
| `docs/` | This portal |
| `specs/` | Planning archive |

See [explanation/architecture.md](../explanation/architecture.md).

## 6. Quality bar before you push

```bash
make lint && make test
# optional parity with CI:
make ci
```

Contribution workflow: [`CONTRIBUTING.md`](../../CONTRIBUTING.md).
