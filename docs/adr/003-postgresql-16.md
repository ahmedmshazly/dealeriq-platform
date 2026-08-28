# ADR-003: PostgreSQL 16

- Status: Accepted
- Date: 2026-07-10
- Requirement refs: SRS §3.4, C-01

## Context

The system needs a relational store for transactional data (orders, inventory ledgers,
customers) and analytics outputs (forecasts, anomalies, scores), with window-function support
for time-series SQL (weekly demand aggregation, rolling calculations) and zero licensing cost.

## Decision

Use PostgreSQL 16, run locally via Docker Compose, as the sole datastore.

## Consequences

- Continuity with the domain (the 2022 predecessor was also Postgres-backed).
- Window functions support the SQL-side of demand-series construction (DS-FC-001) without a
  separate OLAP engine.
- Free and open-source, satisfying C-01.
- Stage-2 hosting (§12.4) swaps to a managed free-tier Postgres (Neon/Supabase) with unchanged
  Alembic migrations - no code changes required.
