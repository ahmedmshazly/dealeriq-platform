# Tasks: Synthetic Data Generator

**Input**: plan.md from `specs/004-synthetic-data/`

## Task list

- [x] T001 `packages/analytics/src/dealeriq_analytics/sbc.py`: ADI/CV² computation + SBC
      classification (ADI=1.32, CV²=0.49 cutoffs)
- [x] T002 Unit tests: `sbc.py` against hand-computed fixtures (a few toy series with known
      ADI/CV² by hand)
- [x] T003 `generator/config.py`: `GeneratorConfig` (seed, branches, segment→SBC-target table,
      n_weeks, models-per-segment)
- [x] T004 `generator/demand.py`: NB-GLM weekly demand simulation (trend + Fourier seasonality +
      promo + branch effect), pure numpy/pandas, deterministic given seed
- [x] T005 Unit tests: determinism (same seed → identical output), `test_generator_sbc_coverage`
      (≥10 series per SBC class using `sbc.py`)
- [x] T006 `generator/leads.py`: lead funnel logit simulation with the documented signed
      coefficients
- [x] T007 Unit test: fit a quick logistic regression on generated leads, confirm every
      coefficient's sign matches the ground truth
- [x] T008 `generator/anomalies.py`: demand-shock injection with near-miss decoys. Pricing-error
      injection deferred to `infra/seed/generate.py` (needs real Order pricing data, which
      doesn't exist in the pure-stats layer) — not yet implemented, added to `docs/backlog.md`;
      see phase report deviation #3.
- [x] T009 Unit test: injected shocks are independently detectable via robust z-score (z in
      5-8 range), decoys don't trivially trigger
- [x] T010 `infra/seed/generate.py`: orchestrator — branches/models/units, demand→order/ledger
      realization, customers, leads, ground-truth JSON export; bulk SQLAlchemy inserts, no HTTP
- [x] T011 Wire `make seed` to run the generator after migrations
- [x] T012 `infra/seed/notebooks/profile.md`: dataset profile report (SBC histogram, volumes,
      funnel conversion by channel, anomaly list) — the "profile notebook" the exit demo asks for
- [x] T013 Run the full generator against the dev DB; verify GEN-001 volumes, SC-002 (SBC
      coverage), SC-003 (sign recovery), SC-004 (anomaly detectability), SC-005 (determinism —
      run twice, diff)
- [x] T014 Re-verify `make bootstrap && make seed && make dev` (NFR-007, now measuring the real
      generator's runtime) and `make ci`
