# Feature Specification: Synthetic Data Generator

**Feature Branch**: `004-synthetic-data`

**Created**: 2026-07-10

**Status**: Draft

**Input**: SRS DIQ-SRS-001 v1.0.0 §13 Phase 3 — "GEN-001..006"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A statistically realistic, reproducible dataset (Priority: P1)

As anyone running `make seed`, I get a deterministic (same seed → same data), 3-year, 3-branch,
25-model dataset whose weekly demand genuinely spans all four Syntetos–Boylan–Croston demand
patterns — not because a downstream classifier is told to output that answer, but because the
underlying generative process was designed to produce it.

**Why this priority**: Every later analytics phase (4, 5, 7) is validated against this dataset;
if the generator doesn't actually span smooth/erratic/intermittent/lumpy, DS-FC-006 and QA-003a
become unfalsifiable.

**Independent Test**: Run the generator with a fixed seed twice; byte-identical output. Compute
ADI/CV² per (model,branch) series; confirm ≥10 series land in each of the 4 SBC classes.

**Acceptance Scenarios**:

1. **Given** a fixed seed, **When** the generator runs twice, **Then** every generated table's
   contents are identical (GEN-001).
2. **Given** the generated order ledger, **When** aggregated into weekly (model,branch) demand
   series, **Then** ADI/CV² classification (ADI=1.32, CV²=0.49 cutoffs) finds series in all four
   SBC classes, ≥10 series each (GEN-002).

---

### User Story 2 - A lead funnel with known, recoverable ground truth (Priority: P1)

As a future consumer of DS-CUST-003 (Phase 7), I need leads whose won/lost outcome is driven by
a real logistic relationship with documented, signed coefficients — so a correctly-implemented
lead-scoring model can be shown to recover those signs (QA-003c).

**Independent Test**: Fit a plain logistic regression on the generated leads' features against
their outcome; confirm every coefficient's sign matches `ground_truth/lead_coefficients.json`.

**Acceptance Scenarios**:

1. **Given** the generated leads, **When** `source_channel=referral` vs `social_ad`, **Then**
   referral leads have a higher empirical win rate, consistent with the stored positive/negative
   coefficients (GEN-003).

---

### User Story 3 - Labeled anomalies a detector can be graded against (Priority: P1)

As a future consumer of DS-ANO (Phase 5), I need known-timestamp demand shocks and pricing
errors injected into otherwise-normal data, plus enough decoy noise that a detector can't pass
QA-003b by simply flagging everything.

**Independent Test**: Every entry in `ground_truth/anomalies.json` corresponds to a real,
identifiable deviation in the generated data at the stated week/order.

**Acceptance Scenarios**:

1. **Given** an injected demand shock, **When** computing a robust z-score on that series' STL
   residuals, **Then** the shock's implied z clears 3.5 by a comfortable margin (target 5-8) —
   validated now with a throwaway script, not left to Phase 5 to discover it doesn't (GEN-004).

### Edge Cases

- What happens when a (model,branch) series' demand parameters produce zero total sales across
  all 156 weeks? → per-model jitter is bounded so this doesn't happen in practice, and the SBC
  coverage test would fail loudly if it did — treated as a generator bug, not tolerated silently.
- What happens if two orders would need the same vehicle unit? → the generator receives a unit
  immediately before "selling" it within the same simulated week — there is always exactly one
  unit per generated order, never a shared/double-booked unit (mirrors the real uniqueness
  constraint FR-042 enforces at runtime).

## Requirements *(mandatory)*

- **GEN-001**: 3 branches, ~25 vehicle models across 5 segments, 156 weeks of history, ~4-8k
  orders, ~6-10k customers/leads, fully deterministic given a seed.
- **GEN-002**: weekly demand per (model,branch) drawn from a Negative Binomial GLM (trend +
  annual Fourier seasonality + promotion effects + branch effect); dispersion tuned per segment
  so generated series span all four SBC classes.
- **GEN-003**: lead funnels simulated with per-channel conversion propensities; ground-truth
  coefficients stored for later validation.
- **GEN-004**: labeled anomalies (demand shocks, pricing errors) injected at known timestamps.
- **GEN-005** *(P1, backlogged per existing `docs/backlog.md` entry)*: persona-driven discount
  variation — not built this phase.
- **GEN-006**: generator parameters and injected ground truth exported to
  `infra/seed/ground_truth/`.

### Key Entities

No new domain tables — the generator populates the existing Phase 2 schema (branches,
vehicle_models, vehicle_units, stock_movements, customers, leads, lead_events, orders,
order_events) and writes ground-truth artifacts as JSON files, not database tables (they're
inputs to future test suites, not application data).

## Success Criteria *(mandatory)*

- **SC-001**: `make seed` (full generator) completes in a reasonable local-dev time budget and
  produces the volumes in GEN-001, subject to the documented order-volume deviation in
  `docs/adr/021-synthetic-demand-volume-vs-sbc-coverage.md` (SC-002's four-class coverage is
  prioritized over GEN-001's approximate order count; actual ~15.1k orders vs. the ~4-8k
  estimate).
- **SC-002**: `test_generator_sbc_coverage` passes: ≥10 series per SBC class.
- **SC-003**: A hand-fit logistic regression on generated leads recovers every ground-truth
  coefficient's sign.
- **SC-004**: Every injected anomaly is independently confirmed present in the generated data by
  a throwaway validation script (not just asserted by the generator's own bookkeeping).
- **SC-005**: Re-running the generator with the same seed produces byte-identical output.

## Assumptions

- The generator writes directly to the transactional tables via bulk inserts, bypassing the
  Phase 1/2 API/service layer, since it is a one-time seed-time data-loading operation (like a
  fixture loader), not a runtime analytics job — DAT-003's separation is about protecting
  transactional data from *runtime* analytics jobs and vice versa, not about how the initial
  dataset is loaded. Every row still matches the exact schema/constraints those tables enforce.
- SBC classification (ADI/CV² computation, the DS-FC-002 algorithm) is implemented now, in
  `packages/analytics`, as a minimal, well-tested, reusable utility — a deliberate pull-forward
  from Phase 4, since GEN-002 cannot be validated without it. No forecasting methods or CV
  harness are pulled forward; those remain Phase 4 scope.
