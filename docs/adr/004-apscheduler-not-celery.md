# ADR-004: APScheduler (not Celery) for local job scheduling

- Status: Accepted
- Date: 2026-07-10
- Requirement refs: SRS §3.4, C-01, C-03, DS-OPS-001..004

## Context

DealerIQ needs scheduled analytics jobs (weekly forecasting, daily inventory/anomaly/scoring
runs, daily digest email) that are idempotent, seed-reproducible, and re-triggerable via HTTP
(C-03) so a future serverless cron (Vercel Cron) can drive them without code changes. Celery
would require a broker (Redis/RabbitMQ) as an additional free-but-operationally-heavier
dependency.

## Decision

Run APScheduler inside the API process (single instance, local mode) to execute jobs on cron
schedules (DS-OPS-001's default schedule), with every job also exposed as
`POST /api/v1/jobs/{name}/run` (admin-only, concurrency-guarded).

## Consequences

- No broker dependency — one fewer moving part in `docker compose up` (supports C-01).
- Jobs must be written as idempotent, HTTP-triggerable functions from day one (DS-OPS-002),
  which naturally satisfies C-03's future-serverless-cron requirement.
- Single-instance scheduling means no built-in horizontal scaling of the scheduler itself; not a
  concern at the stated v1.0 data volumes (§2.4).
- Job failures must be handled explicitly (retry-once-with-backoff, mark run failed, leave
  previous outputs live) since there's no broker-level retry/dead-letter mechanism to lean on
  (NFR-005).
