# Implementation Plan: Synthetic Data Generator

**Branch**: `004-synthetic-data` | **Date**: 2026-07-10 | **Spec**: `specs/004-synthetic-data/spec.md`

## Summary

A two-layer generator: pure statistical simulation (`packages/analytics`, no DB dependency,
independently testable/runnable) producing in-memory series and ground truth, plus a seed-time
orchestrator (`infra/seed/`) that bulk-inserts the simulated world into Postgres and writes the
ground-truth JSON artifacts GEN-006 requires.

## Series sizing (why 25 models × 3 branches × 156 weeks isn't arbitrary)

25 models × 3 branches = 75 (model,branch) series; 156 weeks gives
`floor((156-52-12)/4)+1 = 24` rolling-CV folds per series once Phase 4 needs them (DS-FC-004) -
comfortably under NFR-004's 500-series bound.

## Demand model (GEN-002)

Per (model *m*, branch *b*, week *t*):

```
log μ(m,b,t) = β0(m) + β_trend(m)·(t/156)
             + Σ_{k=1,2} [γ_k·cos(2πkt/52) + δ_k·sin(2πkt/52)]
             + β_promo·1[promo week]
             + branch_effect(b)
Y(m,b,t) ~ NegativeBinomial(mean=μ(m,b,t), dispersion=α(m))
```

`branch_effect`: A=1.0 (flagship), B≈0.8, C≈0.6 (linear scale). `β_trend ~ N(0, 0.15)` over the
horizon. Fourier amplitudes `~N(0, 0.15)` (±20-30% seasonal swing - real but modest, so Seasonal
Naive stays a genuinely competitive floor once DS-FC-006 is exercised in Phase 4, not a
strawman). 8-15 promo windows/model, 1-3 weeks, `β_promo~Uniform(0.3,0.8)` - unflagged expected
bumps, explicitly distinct from GEN-004's injected anomalies.

Per-segment `(μ0, α)` targets, with ±25% per-model jitter so models within a segment aren't
clones. The table below is the **empirically calibrated** version (not the original a priori
guess): ADI/CV² classification turned out to be far more sensitive to μ0 than expected, and the
μ0 bands that reliably reach smooth/erratic are materially more expensive in order-volume terms
than intermittent/lumpy's - see `docs/adr/021-synthetic-demand-volume-vs-sbc-coverage.md` for the
full calibration trace and the resulting, deliberate departure from GEN-001's ~4-8k estimate
(actual: ~15.1k orders at seed=42). Model counts are imbalanced across segments for the same
reason (more economy/sedan models to buy enough independent draws in the expensive bands):

| Segment | Target SBC class | Models | μ0 (units/wk/branch) | dispersion α |
|---|---|---|---|---|
| Economy/Compact | Smooth | 7 | 1.65-1.85 | 0.02-0.05 |
| Sedan/Mid-size | Erratic | 6 | 3.2-3.6 | 0.85-1.0 |
| SUV/Truck | Intermittent | 3 | 0.3-0.5 | 0.2-0.35 |
| Luxury/Sports | Lumpy | 3 | 0.35-0.5 | 12-20 |
| Commercial/Van | Mixed | 3 | 0.15-0.5 | 0.5-2.0 |

`packages/analytics/src/dealeriq_analytics/sbc.py` implements ADI/CV² + classification
(ADI=1.32, CV²=0.49 cutoffs) - the DS-FC-002 algorithm, pulled forward now (see spec
Assumptions) purely to validate this table actually produces the required spread, via
`test_generator_sbc_coverage` (≥10 series/class) before Phase 4 begins. At seed=42 this yields
smooth=13, erratic=10, intermittent=28, lumpy=15 across 66 series (22 models × 3 branches).

## Order/inventory realization

The demand draw *is* the order ledger, not a separate approximation: for each (model,branch,
week) with `Y(m,b,t) = n` draws, the generator receives `n` fresh vehicle units that week
(acquisition_cost = `list_price * Uniform(0.75, 0.85)`, i.e. realistic margin headroom) and
immediately realizes `n` completed orders against them, each written directly in `delivered`
status with backdated `order_events`/`stock_movements` rows spread across that week's days. This
is what makes DS-FC-001's later "construct weekly demand series from the order ledger" recover
the same series the NB-GLM actually drew, not a lossy proxy of it. Every order's customer is
drawn from the customer pool (~70% chance of an existing customer making a repeat purchase, ~30%
a new one) - this produces the realistic repeat-customer skew RFM segmentation (Phase 7) needs.

## Lead funnel (GEN-003)

Simulated independently from the order/demand realization above (some leads convert into the
sales the demand series already accounts for; most don't - real dealership funnels are lossy).
`logit(P(won)) = γ0 + γ_channel[source] + γ_budget·budget_band + γ_segment[model_segment] +
γ_days·days_since_creation + γ_interactions·interaction_count + γ_rfm·customer_rfm_score +
γ_season`, with these exact signed coefficients stored in
`infra/seed/ground_truth/lead_coefficients.json` and used to actually draw each lead's outcome:

`referral +0.8, walk-in +0.3, web-form 0.0 (baseline), phone -0.2, social-ad -0.5;
days_since_creation -0.02/day; interaction_count +0.25/interaction; customer_rfm_score
+0.3/quintile; economy-segment +0.4 vs luxury baseline`. QA-003c (Phase 7) only needs sign
recovery, which is what this table is deliberately structured to make checkable.

## Anomaly injection (GEN-004)

`infra/seed/ground_truth/anomalies.json`, one entry per injected point:
`{series_key, week_start, type, magnitude_multiplier, expected_value, injected_value}`.

- 15-25 demand shocks: the week's NB-GLM draw is overridden with a ×4-8 spike or a near-zero
  drop, sized so the implied robust z-score (median/MAD over that series' STL residuals) lands
  in the 5-8 range - comfortably past DS-ANO-001's 3.5 threshold, not a coin-flip detection.
- 10-20 pricing errors: an order's `negotiated_price` is forced below
  `list_price - 5·σ(historical discounts for that model)` (k_inject=5 vs the detector's default
  k=3, DS-ANO-003).
- A handful of deliberate near-miss points (implied z≈2-3) are left as natural, unflagged
  variance - without these the false-positive half of QA-003b (Phase 5) is vacuous.

`test_anomalies_are_independently_detectable` (a throwaway-style validation, kept as a real test)
computes robust z-scores itself and confirms every injected shock clears the target range -
GEN-004 validated now, not assumed.

## GEN-006 ground truth artifacts

`infra/seed/ground_truth/`: `generator_config.json` (seed + all parameters above),
`series_params.json` (per-(model,branch) `β0, β_trend, γ_k, δ_k, branch_effect, α, target_sbc_
class`), `lead_coefficients.json`, `anomalies.json`. All committed to the repo (small JSON, not
gitignored) - the paper (Phase 10) and QA-003 tests read these directly.

## Project Structure

```text
packages/analytics/src/dealeriq_analytics/
├── sbc.py                      # ADI/CV² + classification (DS-FC-002 pull-forward)
└── generator/
    ├── __init__.py
    ├── config.py                # GeneratorConfig dataclass: seed, dims, segment table
    ├── demand.py                 # NB-GLM simulation, pure numpy/pandas, no DB
    ├── leads.py                   # lead funnel simulation, ground-truth coefficients
    └── anomalies.py                # anomaly injection given a demand dataframe

infra/seed/
├── generate.py                  # orchestrator: calls dealeriq_analytics.generator, writes DB
│                                  # + ground_truth/ via SQLAlchemy models imported from
│                                  # dealeriq_api (bulk inserts, no HTTP/service-layer calls)
├── ground_truth/                # GEN-006 output (committed)
└── notebooks/profile.md          # GEN's required "profile notebook" — a markdown report
                                   # (no Jupyter dependency) summarizing the generated dataset:
                                   # SBC class histogram, volume counts, lead funnel conversion
                                   # rates by channel, anomaly list

packages/analytics/tests/
├── test_sbc.py                   # ADI/CV² against hand-computed fixtures (QA-002)
├── test_demand_generator.py       # determinism + test_generator_sbc_coverage
├── test_lead_generator.py          # sign recovery via a quick logistic fit
└── test_anomaly_injection.py        # injected shocks are independently detectable
```

`make seed` gains a step (after migrations) invoking `infra/seed/generate.py`; the existing
`make bootstrap && make seed && make dev` command sequence is unchanged from the user's
perspective - it just takes longer and produces a full dataset instead of an empty schema.

## Constitution Check

- Principle V (Analytics Reproducibility & Scientific Integrity): the generator's own
  determinism (GEN-001) and the SBC-coverage/sign-recovery/anomaly-detectability validations
  are exactly this principle applied to the generator itself, per the working rule extending
  "validate metrics before wiring into pipelines" to the generator.
- Principle VII (Testing bar): every generator component (SBC classifier, demand simulation,
  lead funnel, anomaly injection) is unit-tested against hand-computed or independently-derived
  expectations before being trusted as ground truth for later phases.
- No violations requiring Complexity Tracking.

## Complexity Tracking

None.
