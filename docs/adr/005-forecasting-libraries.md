# ADR-005: statsforecast for classical forecasting methods

- Status: Accepted (narrowed by ADR-018)
- Date: 2026-07-10
- Requirement refs: SRS §3.4, DS-FC-003

## Context

The forecasting method pool (DS-FC-003) requires Naive, Seasonal Naive, SES, ETS (automatic),
AutoARIMA, Croston, SBA, and TSB, evaluated uniformly under rolling-origin CV (DS-FC-004).

## Decision

Use Nixtla's `statsforecast` as the primary forecasting library, retaining `statsmodels`
alongside it as originally scoped.

## Consequences

- `statsforecast` implements the full DS-FC-003 method pool under one `StatsForecast` interface
  with a built-in rolling-origin CV utility, and is fast enough to comfortably clear NFR-004
  (≤500 series, <10 min).
- During Phase 4 implementation it became clear `statsmodels` is not actually needed for any
  method in the pool - see ADR-018, which narrows this decision to reduce two-library
  integration risk without changing the method pool itself.
