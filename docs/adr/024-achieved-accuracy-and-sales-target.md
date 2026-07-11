# ADR-024: Achieved-accuracy dedup rule; a single configurable sales target, not per-salesperson quotas

- Status: Accepted
- Date: 2026-07-11
- Requirement refs: FR-050, FR-051, FR-054, FR-073

## Context

FR-073 wants "rolling forecast accuracy" comparing past forecasts to real actuals. Because the
forecast job runs weekly with a 12-week horizon (DS-OPS-001), any given calendar week is
forecast by roughly a dozen different runs at different lead times before it arrives — there is
no single obvious "the forecast for that week." Separately, FR-051 wants a Salesperson's monthly
sales compared "vs. target," but no target/quota concept exists anywhere in the domain, and
building full per-salesperson quota management is a real, unscoped expansion of this phase.

## Decision

1. **Achieved accuracy deduplicates to one `yhat` per (series, week) by taking the *earliest*
   run that forecast it** — the longest genuine lead time, and the strictest honest
   out-of-sample comparison. A later run's forecast for the same week benefits from more recent
   information the earlier run didn't have, so using it would overstate how good the *original*
   forecast actually was.
2. **The achieved-accuracy metric itself is Phase 4's existing, already-validated `mase()`
   function** (`dealeriq_analytics.forecasting.metrics.mase`), reused unchanged — only the
   `(y_true, y_pred)` selection is new. No new pure-analytics function or fixture-validation of
   the formula itself is needed; this phase's own test validates the *selection/alignment* logic
   (which forecasts pair with which actuals), not MASE's math.
3. **"My monthly sales vs. target" (FR-051) uses a single admin-configurable default target**
   (`Settings.default_monthly_sales_target`), applied uniformly to every Salesperson — not a
   per-salesperson quota table. Proper quota management (per-person targets, ramping new hires,
   seasonal adjustment, etc.) is recorded in `docs/backlog.md` as a P2 item.
4. **"Sales this month vs. forecast" (FR-050) needs no target concept at all** — it compares real
   revenue against the sum of the relevant series' own persisted forecast, which already exists.

## Consequences

- Achieved accuracy is fully computed on demand from already-persisted data (no new analytics-run
  lifecycle, no new table) — consistent with this phase's overall "compose, don't recompute"
  posture.
- The earliest-run dedup rule means achieved accuracy is deliberately conservative (closer to "how
  good was our earliest warning" than "how good was our latest, most-informed guess") — disclosed
  here so a future phase revisiting this doesn't mistake it for an oversight.
- A single global sales target is honest about the phase's real scope: it satisfies FR-051's
  literal requirement (a target exists to compare against) without pretending to be a real quota
  system. The backlog entry keeps that gap visible rather than silently forgotten.
