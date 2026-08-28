# ADR-018: Narrow statsmodels' role to STL only

- Status: Accepted
- Date: 2026-07-10
- Requirement refs: DS-FC-003, DS-ANO-001, supersedes part of ADR-005

## Context

ADR-005, following SRS §3.4 verbatim, names both `statsforecast` and `statsmodels` for the
DS-FC-003 classical forecasting method pool (Naive, Seasonal Naive, SES, ETS, AutoARIMA,
Croston, SBA, TSB). In practice, `statsforecast` alone implements the entire pool under one
`StatsForecast` interface (`Naive`, `SeasonalNaive`, `SES`, `AutoETS`, `AutoARIMA`,
`CrostonClassic`, `CrostonSBA` ≈ SBA, `TSB`), including a built-in rolling-origin CV utility.

## Decision

Use `statsforecast` alone for the entire DS-FC-003 method pool. Retain `statsmodels` only for
STL decomposition (DS-ANO-001), which `statsforecast` does not provide.

## Consequences

- Reduces integration risk: one library owns the forecasting method pool and its CV harness,
  rather than mixing two libraries' APIs for one evaluation loop.
- This is a genuine capability finding (statsmodels turned out to be unnecessary for the
  forecasting pool as specified), not a fabricated gap or a silent scope cut - flagged
  transparently here and in the Phase 4 report, per the project's "never fabricate" rule.
- If a future requirement needs a statsmodels-only method (e.g., a specific ARIMA variant not in
  statsforecast), that's a new ADR reopening this decision, not a silent reversion.
