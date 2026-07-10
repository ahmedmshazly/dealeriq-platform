# DealerIQ

A dealership intelligence platform: automated demand forecasting, inventory optimization,
anomaly detection, customer/lead analytics, and rule-based alerting, layered on top of a
role-based sales-and-inventory system of record for automotive dealerships.

The authoritative specification is [`docs/srs/DealerIQ-SRS.md`](docs/srs/DealerIQ-SRS.md)
(DIQ-SRS-001 v1.0.0). This repository is being built phase-by-phase against that SRS using see
[`specs/`](specs/) for each phase's `spec.md` / `plan.md` / `tasks.md`, and
[`CHANGELOG.md`](CHANGELOG.md) for what's actually landed, phase by phase.

## Stack

FastAPI (Python 3.12) · Next.js 15 (TypeScript, App Router) · PostgreSQL 16 · APScheduler ·
statsforecast/statsmodels/scikit-learn · Recharts. Free/open-source only — everything runs
locally via Docker Compose (Postgres + MailHog), zero paid services (see
[`docs/adr/`](docs/adr/) for every architecture decision and its rationale).

## Repository layout

```
apps/api/            FastAPI backend (REST API, auth, RBAC, job scheduler, alert engine)
apps/web/             Next.js frontend (dashboards, operational screens, admin console)
packages/analytics/   Python analytics library (forecasting, inventory, anomalies, scoring)
packages/api-client/  Generated TypeScript client (single source of truth: the OpenAPI schema)
infra/                Docker Compose (Postgres 16 + MailHog), synthetic data generator
docs/                 SRS, ADRs, runbooks, backlog, research paper
specs/                Feature specs/plans/tasks, one per delivery phase
```

## Getting started

```bash
make bootstrap && make seed && make dev
```

See [`docs/runbooks/local-dev.md`](docs/runbooks/local-dev.md) for the full guide (prereqs,
troubleshooting, regenerating the API client, resetting the database).

## Project governance

[`docs/constitution.md`](docs/constitution.md) encodes this project's
non-negotiable engineering principles, derived from the SRS. Every ADR beyond the SRS's own
ADR-001..008 lives in [`docs/adr/`](docs/adr/). P1/P2 items deliberately deferred out of a
phase's scope are tracked in [`docs/backlog.md`](docs/backlog.md).
