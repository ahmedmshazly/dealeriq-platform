# ADR-025: Conformal prediction intervals for the four DS-FC-003 methods with no native interval estimator

- Status: Accepted
- Date: 2026-07-12
- Requirement refs: DS-FC-003, DS-FC-004, DS-OPS-004

## Context

Building Phase 10's benchmark harness surfaced a real, previously-undetected bug in the
already-shipped, already-tested forecasting pipeline (`packages/analytics/forecasting/`,
live since Phase 4): `SimpleExponentialSmoothingOptimized`, `CrostonClassic`, `CrostonSBA`, and
`TSB` - four of DS-FC-003's eight required methods, and specifically the intermittent-demand-
specific ones this whole project's forecasting story is built around - have no native
parametric prediction-interval method in `statsforecast`. Calling `StatsForecast.cross_
validation(..., level=[80])` on any of them raises immediately ("You must pass
`prediction_intervals` to compute them").

`cv.py::run_cross_validation`'s per-method loop already wraps each method's `cross_validation`
call in a `try/except Exception: continue`, deliberately so one method's failure can't take down
the other seven's results (the surrounding comment calls whole-pool failure "rare"). In practice
this silently swallowed the exception for these four methods on *every single run*, meaning the
champion-selection pool has been missing SES/Croston/SBA/TSB entirely - on every series, in
every forecast job run, since Phase 4 shipped. Because the failure was silent (no log, no
error surfaced), nothing caught it: not QA-003(a)'s own CI-blocking validation (which only
checks that *whichever* champion is selected beats Seasonal Naive - a pool missing four methods
can still satisfy that bar), not manual testing, not four subsequent phases' worth of real-data
verification. It was found only because Phase 10's benchmark harness inspected the raw
per-method output directly and noticed only 4 of 8 expected method names present.

## Decision

Pass `statsforecast.utils.ConformalIntervals(h=<forecast horizon>, n_windows=2)` - the
library's own model-agnostic conformal interval estimator, using its own default calibration
window count - to the four affected models' constructors in `methods.py::build_method_pool`.
`n_windows=2` (rather than a larger, more-calibrated value) is a deliberate, disclosed default,
matching this project's existing "reasonable default, not a tuned hyperparameter" treatment of
TSB's own `alpha_d`/`alpha_p` constants - increasing it is a legitimate future tuning knob, not
a correctness requirement. `build_method_pool` now takes an explicit `horizon: int` parameter
(both call sites - `cv.py` and `champion.py`'s champion-refit step - already have `HORIZON` in
scope) rather than hardcoding it, so the CV harness and the benchmark harness can never drift
out of sync on what horizon the conformal calibration targets.

The existing `try/except Exception: continue` in `cv.py` is left in place - its documented
purpose (an individual model's per-run failure shouldn't lose every other method's results) is
sound; the problem was a systematic root cause hiding behind it, not the resilience mechanism
itself.

## Consequences

- Every forecast job run from this point forward genuinely evaluates all eight DS-FC-003
  methods, not four - the champion-selection pool DS-FC-006 describes is now what actually
  runs, not a silently-narrowed subset.
- Every persisted forecast/metric from before this fix (Phases 4-9's own verification runs, any
  real seeded-database forecast run) was computed against an incomplete method pool. This ADR
  documents the gap; no historical data is retroactively "corrected" - the next real forecast
  job run (already required after every reseed, per this project's own established
  reproducibility discipline) picks up the fix naturally.
- This is a strong argument for QA-003-style scientific validation to also assert *which*
  methods were actually evaluated, not just properties of whichever champion was selected -
  recorded as a P1 backlog item (`docs/backlog.md`) rather than built as part of this
  bug-fix phase, since it's a genuinely separate, additive testing improvement.
- Runtime impact is real but small: conformal interval calibration adds extra fit calls for the
  four affected methods per CV fold. Phase 10's own benchmark run timing (documented in its
  phase report) is the first real measurement of the corrected pipeline's full-pool runtime.
