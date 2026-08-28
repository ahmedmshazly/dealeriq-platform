# ADR-021: Synthetic demand volume vs. SBC-class-coverage tradeoff

- Status: Accepted
- Date: 2026-07-10
- Requirement refs: GEN-001, GEN-002

## Context

GEN-001 says the generator SHALL produce "~4-8k orders" across 3 branches, ~25 vehicle models,
156 weeks. GEN-002 says weekly demand SHALL be drawn from an NB-GLM with "dispersion tuned so
generated series span all four SBC demand classes (smooth→lumpy)". `spec.md`'s own operational
reading of GEN-002 (SC-002) requires ≥10 series in each of the four classes, so that Phase 4's
champion-vs-Seasonal-Naive validation (QA-003a) has a statistically meaningful sample within
every demand pattern, not just 1-2 anecdotal series per class.

Empirical calibration (packages/analytics tmp scripts, NB2 parameterization `r=1/α`,
`p=r/(r+μ)`, classified via the real `sbc.classify()` against ADI=1.32/CV²=0.49) established that
ADI/CV² classification is far more sensitive to the base rate μ₀ than dispersion α alone:

- **Smooth** (ADI<1.32, CV²<0.49) needs P(zero) below ~24%, which floors μ₀ at ~1.7-1.8 even at
  near-zero dispersion (the Poisson limit already requires μ>1.42 for e^-μ<0.24).
- **Erratic** (ADI<1.32, CV²≥0.49) needs both frequent nonzero weeks *and* high nonzero-value
  variance simultaneously - empirically this only reliably resolves in a narrow μ₀≈3.2-4.2,
  α≈0.85-1.0 band; lower μ₀ at any α tested instead lands in *lumpy* (ADI creeps ≥1.32 once
  P(zero) rises, even though CV² is already high).
- Intermittent and lumpy, by contrast, are cheap: μ₀≈0.3-0.5 with α tuned per class gives ≥90%
  reliable classification.

Given the SRS-fixed structure (3 branches, 156 weeks, ~25 models across 5 segments), and that
per-model volume ≈ `μ₀ × 156 weeks × Σ(branch_effect)`, getting ≥10 series into *both* the smooth
and erratic bands (the two structurally expensive classes) costs roughly 13-15k units on its own,
2-4× GEN-001's upper bound, regardless of how model counts are redistributed across segments
(tested down to the minimum model counts that still clear the ≥10 floor; see phase report). Model
counts were already rebalanced away from their SRS-inspired starting point (5 models/segment) to
favor economy/sedan (the smooth/erratic segments) over suv/luxury/commercial (the already-cheap
intermittent/lumpy segments), which is the main lever that exists within the fixed structure.

## Decision

Prioritize GEN-002's SHALL (robust four-class SBC coverage, ≥10 series/class) over GEN-001's
approximate ("~") volume figure. Final calibrated config: economy 7 models (μ₀ 1.65-1.85, target
smooth), sedan 6 models (μ₀ 3.2-3.6, target erratic), suv_truck/luxury/commercial 3 models each
(μ₀ 0.15-0.5, cheap - intermittent/lumpy/mixed) - 22 models total (SRS says "~25"), 66 series.
Deterministic result at seed=42: **15,147 total orders**, smooth=13, erratic=10, intermittent=28,
lumpy=15 - all four classes clear the ≥10 floor with margin.

This is a deliberate, evidence-based departure from GEN-001's "~4-8k" figure, not a bug: the
tension was verified mathematically (NB zero-probability floors) and empirically (grid search
across model counts, branch-effect spreads, and μ₀/α bands - see phase report
`03-synthetic-data.md` for the calibration trace) to be structural under the SRS-fixed generator
shape, not a symptom of under-tuning.

## Consequences

- Total order volume (~15.1k) is documented honestly in the phase report and profile notebook as
  a deviation from GEN-001, with the reasoning above - not silently absorbed.
- Downstream phases (4-8) that consume the order ledger (forecasting CV folds, inventory
  turnover, dashboards) get a larger dataset than originally scoped; this is a size increase, not
  a schema or behavior change, so no other requirement is put at risk by it.
- If a future need arises to hit GEN-001's volume more precisely (e.g., demo-day performance on
  low-spec hardware), the documented lever is lowering SC-002's ≥10 threshold (unblocking cheaper
  μ₀ bands for smooth/erratic) - that threshold is this project's own invention, not SRS text, so
  it is the correct dial to turn first, before ever reducing GEN-002's four-class coverage.
