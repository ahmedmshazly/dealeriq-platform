# infra/seed

`generate.py` is the GEN-001..006 orchestrator (T010): it runs the statistical generator in
`packages/analytics/src/dealeriq_analytics/generator/` and bulk-inserts the result into Postgres
via SQLAlchemy Core - branches, ~22 vehicle models, ~12 users, ~6.4k customers, ~15.2k orders
(full unit/ledger/order-event trails), ~6k leads with legal state-machine event paths, and
injected/near-miss anomalies. Wired to `make seed` (runs after Alembic migrations).

`ground_truth/` (GEN-006, committed - small JSON, not gitignored) holds the generator's own
parameters and injected labels: `generator_config.json`, `series_params.json`,
`lead_coefficients.json`, `anomalies.json`. The scientific validation tests (QA-003) and the
paper (Phase 10) read these directly.

`notebooks/profile.md` (T012) is a real dataset profile - SBC class histogram, order volume by
segment/branch, lead funnel conversion by channel/segment, customer repeat-purchase distribution,
injected anomaly list - generated from an actual `make seed` run against the local dev DB, not
estimated.

Deterministic given `GeneratorConfig`'s seed (42 by default): re-running against a freshly-reset
DB reproduces byte-identical output (GEN-001, SC-005).

## Dev seed logins

See [`docs/runbooks/local-dev.md`](../../docs/runbooks/local-dev.md) for the full role table.
Quick reference (dev only): Admin `admin@dealeriq.dev` / `ChangeMe123!`; seeded Manager/Sales/Analyst
users use `SeedUser123!`.
