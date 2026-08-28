# Feature Specification: Inventory Intelligence & Anomalies

**Feature Branch**: `006-inventory-anomalies`

**Created**: 2026-07-10

**Status**: Draft

**Input**: SRS DIQ-SRS-001 v1.0.0 §13 Phase 5 - "DS-INV-001..004, DS-ANO-001..004"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A manager can see stock health at a glance (Priority: P1)

As a Manager, I open an inventory intelligence view and see every model classified into the
standard 9-cell ABC/XYZ matrix (revenue contribution × demand variability) as a heatmap, so I
know at a glance which models are high-value-and-predictable versus low-value-and-erratic
without reading a spreadsheet.

**Why this priority**: This is the SRS's own stated exit demo's first half ("ABC/XYZ heatmap")
and the foundational classification everything else in this phase (reorder points, aging
review) is read *through* - a manager scans the heatmap first, then drills into a cell.

**Independent Test**: Open the inventory intelligence page with a fully seeded database; confirm
every vehicle model appears in exactly one of the 9 cells, and the cell counts sum to the total
model count.

**Acceptance Scenarios**:

1. **Given** the seeded dataset's order history, **When** the ABC/XYZ classification runs,
   **Then** every model is assigned exactly one ABC letter (by cumulative revenue share: A = top
   80%, B = next 15%, C = last 5%) and one XYZ letter (by CV of weekly demand: X < 0.5,
   Y 0.5-1.0, Z > 1.0) (DS-INV-001).
2. **Given** the classification result, **When** a Manager opens the heatmap, **Then** each of
   the 9 cells shows its member models and each model links to its own reorder-point and aging
   detail.

---

### User Story 2 - Reorder points come from real forecast uncertainty, not a guess (Priority: P1)

As a Manager, for every model/branch, I see a computed reorder point derived from that series'
own champion forecast (Phase 4) and its uncertainty - not a fixed multiplier of average sales -
so restocking decisions reflect how predictable that specific series actually is.

**Why this priority**: DS-INV-002's core scientific requirement - safety stock must come from
forecast uncertainty. It's P1 because it's the number a Manager actually *acts* on, once they've
used the heatmap (User Story 1) to decide where to look.

**Independent Test**: For a sample model/branch with a Phase 4 champion forecast, compute the
reorder point by hand from that series' quantile forecast and lead-time weeks; compare to the
system's stored value.

**Acceptance Scenarios**:

1. **Given** a model/branch with a Phase 4 champion forecast, **When** the reorder-point job
   runs, **Then** the reorder point equals the sum, over the configured lead-time window, of the
   champion forecast's configurable service-level quantile (default 90% → q=0.9) (DS-INV-002).
2. **Given** a model/branch with no succeeded Phase 4 forecast run yet, **When** the reorder-point
   job runs, **Then** that model/branch is skipped with a clear reason recorded, not silently
   defaulted to zero or a guessed value.

---

### User Story 3 - Aging inventory and its sale probability surface without a report request (Priority: P2)

As a Manager, I see days-on-lot for every in-stock unit, with units past a configurable aging
threshold flagged, and - for a richer read on the worst-aging units - a "probability of sale
within 30 days" estimate so I know which aging units most need a pricing review versus which are
merely slow but still likely to move.

**Why this priority**: DS-INV-003 (simple aging) and DS-INV-004 (survival-curve enrichment) are
both about the same underlying "which units are stuck" question; P2 because it's the second half
of the "what to act on" story, after the classification and reorder numbers (P1) exist.

**Independent Test**: Query a unit whose `acquisition_date` is known; confirm days-on-lot matches
a hand calculation, and confirm it's flagged if past the segment's threshold (default 90 days).

**Acceptance Scenarios**:

1. **Given** an in-stock unit, **When** its days-on-lot is computed, **Then** it equals the
   number of days since `acquisition_date`, and the unit is flagged if that exceeds its segment's
   configurable aging threshold (default 90 days) (DS-INV-003).
2. **Given** enough historical time-to-sale data per segment, **When** the survival analysis
   runs, **Then** a Kaplan-Meier curve is fit per segment and each in-stock unit gets a
   "probability of sale within 30 days" given its current age, with units in the worst decile
   flagged for pricing review (DS-INV-004).

---

### User Story 4 - Injected anomalies get found, and only the real ones (Priority: P1)

As an Analyst, when the anomaly detector runs against the seeded dataset's known-injected demand
shocks and pricing errors, it recovers the great majority of them without also flagging a flood
of ordinary variation as anomalous - so I can trust the detector's output enough to eventually
wire it to alerts (Phase 6), rather than tuning thresholds by eye every time.

**Why this priority**: This is the SRS's own stated exit demo's second half ("injected anomalies
detected") and the direct, scientifically-checkable deliverable of DS-ANO-001..004 - the
detector's whole value proposition is verifiable-or-not against Phase 3's ground truth, so it's
P1 alongside the reorder-point story.

**Independent Test**: Run the anomaly detector against the seeded dataset; compare its flagged
points against Phase 3's persisted ground-truth shock/near-miss records and Phase 3's injected
pricing errors; compute recovery rate and false-positive rate directly.

**Acceptance Scenarios**:

1. **Given** the seeded dataset's weekly series (sales per branch/segment, average discount,
   average margin), **When** the anomaly detector runs, **Then** each series is STL-decomposed
   (`robust=False` - see Assumptions) and residuals scored by robust z-score; `|z| > 3.5` flags
   an anomaly with severity scaled by `|z|` (DS-ANO-001).
2. **Given** a series with enough history, **When** a point is flagged by the z-score test,
   **Then** the generalized ESD test also runs and both scores are persisted, regardless of
   whether ESD confirms (DS-ANO-002).
3. **Given** the order ledger, **When** transaction-level checks run, **Then** any order whose
   negotiated price is below `list_price - k·σ(historical discounts for that model)` is flagged
   (k configurable, default 3) (DS-ANO-003).
4. **Given** any flagged anomaly, **When** it is persisted, **Then** it records series/entity
   identifier, timestamp, observed vs. expected value, score, detection method, and run id, in a
   form Phase 6's alert engine can consume without this phase building that engine (DS-ANO-004).
5. **Given** Phase 3's persisted ground-truth injected shocks and pricing errors, **When** the
   detector's output is compared against them, **Then** it recovers at least 80% of injected
   anomalies at no more than a 10% false-positive rate (QA-003b - see Assumptions).

### Edge Cases

- What happens for a series too short or too degenerate (near-zero variance) for a stable STL
  fit? Phase 3's own generator already hit and solved this exact problem (`MIN_STABLE_MAD` floor,
  documented in `generator/anomalies.py`) - the real detector reuses the same floor and skips
  (not crashes on, not silently zero-scores) series whose residual MAD falls below it, recording
  why.
- What happens when a model/branch has zero order history (a brand-new model just added)? ABC/XYZ
  classification excludes it from the ranked matrix (zero revenue contribution, undefined CV)
  rather than forcing it into a spurious cell; it's surfaced separately as "insufficient history."
- What happens when the configured aging threshold or discount-anomaly `k` is changed after
  anomalies/flags already exist? Existing persisted anomaly/flag rows are not retroactively
  recomputed; the new threshold applies from the next run onward (consistent with how Phase 4
  treats forecasts as versioned per run, not mutated in place).
- What happens if DS-INV-002's reorder-point job runs before Phase 4's forecast job has ever
  succeeded for a given series? That model/branch is skipped with a recorded reason (see User
  Story 2, Acceptance Scenario 2) - reorder points are never silently backed by a stale or
  fabricated forecast.

## Requirements *(mandatory)*

- **DS-INV-001**: ABC classification ranks models by cumulative revenue share (A: top 80%, B:
  next 15%, C: last 5%); XYZ classification buckets by CV of weekly demand (X < 0.5, Y 0.5-1.0,
  Z > 1.0); the two combine into the standard 9-cell ABC/XYZ matrix.
- **DS-INV-002**: Reorder point per model/branch = the champion forecast's (Phase 4) configurable
  service-level quantile (default 90% → q=0.9) of lead-time demand, summed over the lead-time
  window - safety stock derives from forecast uncertainty, not a fixed multiplier.
- **DS-INV-003**: Days-on-lot tracked per unit; a configurable-per-segment aging alert threshold
  (default 90 days).
- **DS-INV-004**: A Kaplan-Meier survival curve of time-to-sale, fit per segment; each in-stock
  unit gets a "probability of sale within 30 days" given its current age; units in the worst
  decile flagged for pricing review.
- **DS-ANO-001**: For each monitored series (weekly sales per branch/segment, average discount,
  average margin), STL decomposition (`robust=False`) with residuals scored by robust
  (median/MAD) z-score; `|z| > 3.5` flags an anomaly with severity scaled by `|z|`.
- **DS-ANO-002**: For series with sufficient history, the generalized ESD test confirms (or
  doesn't) z-score-flagged points to reduce false positives; both scores are stored regardless
  of outcome.
- **DS-ANO-003**: Transaction-level checks flag orders with negotiated price below
  `list_price - k·σ(historical discounts for that model)`, k configurable (default 3).
- **DS-ANO-004**: Every anomaly persists series/entity, timestamp, observed vs. expected, score,
  method, and run id - in a form Phase 6's alert rule FR-061(c) can consume directly, without
  this phase building the alert engine itself.
- **QA-003(b)**: Scientific validation, CI-blocking from this phase onward - the anomaly detector
  recovers ≥80% of Phase 3's injected anomalies at ≤10% false-positive rate.

*(DS-INV-005, P2, is backlogged per `docs/backlog.md` - Cox proportional-hazards pricing
guidance is an explicit stretch beyond the Kaplan-Meier curve DS-INV-004 already ships.)*

### Key Entities

*(names below match the SRS §7 schema verbatim, since - as with Phase 4's `AnalyticsRun` etc. -
these are the actual table names, not paraphrases.)*

- **inventory_intel**: one row per (run, model, branch) - ABC letter, XYZ letter, reorder point,
  safety stock, service level used. Versioned per run like Phase 4's `series_profiles`, so
  historical classifications remain self-describing if cutoffs ever change.
- **unit_risk**: one row per (run, unit) - days-on-lot at run time, and (when DS-INV-004 has
  enough history) its 30-day sale probability and worst-decile risk flag.
- **anomalies**: one row per detected anomaly - run id, scope (series-level vs. transaction-level),
  series/entity key, observed value, expected value, score, method, severity, status. The
  Phase-6-consumable record DS-ANO-004 requires.

## Success Criteria *(mandatory)*

- **SC-001**: Every vehicle model with order history is classified into exactly one of the 9
  ABC/XYZ cells, viewable as a heatmap.
- **SC-002**: For every model/branch with a succeeded Phase 4 forecast, a reorder point exists
  and is traceable to the specific forecast run and quantile that produced it.
- **SC-003**: Every in-stock unit has a computed days-on-lot value; units past threshold are
  visibly flagged.
- **SC-004 (QA-003b)**: The anomaly detector recovers ≥80% of Phase 3's injected demand-shock and
  pricing-error ground truth at ≤10% false-positive rate - CI-blocking from this phase forward,
  the same standing QA-003 gives QA-003(a) in Phase 4.
- **SC-005**: The inventory intelligence workbench's ABC/XYZ heatmap and anomaly list render real
  data from the latest successful run - verified in a real browser, not just via API response
  shape.

## Assumptions

- **QA-003(b) is in scope for this phase even though the SRS's Phase 5 table row lists only
  DS-INV/DS-ANO IDs, not "QA-003(b)" explicitly** - the same judgment call Phase 4's own table
  row made explicit for QA-003(a). QA-003 as a whole is P0 and stated as "CI fails if these
  regress" for all three sub-parts; part (b) only becomes buildable once its subject (the
  anomaly detector) exists, which is this phase. Phase 3's generator (`generator/anomalies.py`)
  was explicitly built with this in mind - it persists near-miss points and injected-shock
  ground truth with a docstring naming "Phase 5's false-positive-rate check (QA-003b)" as their
  consumer. Shipping DS-ANO-001 without wiring its own mandated scientific gate would repeat the
  exact gap caught and fixed in Phase 4 (T023).
- The anomaly detector's STL call uses `robust=False`, matching Phase 3's own empirically-verified
  finding (`generator/anomalies.py`'s module
  docstring) that `robust=True` degenerates (near-zero MAD) on this dataset's 156-week/52-week-
  seasonal shape - this is a property of the (STL, period=52, 3-cycle) combination, not specific
  to the generator, so the real detector would hit the identical degeneracy otherwise.
- DS-INV-002's reorder point depends on Phase 4's persisted champion forecasts
  (`forecasts`/`forecast_metrics` from the latest succeeded `analytics_runs` row) rather than
  computing its own separate demand forecast - reusing the already-validated champion, not
  building a second forecasting path.
- Ground truth for QA-003(b) comes from Phase 3's `infra/seed/generate.py`-persisted anomaly
  records (demand shocks via `inject_demand_shocks`, pricing errors via
  `_inject_pricing_errors`) plus the near-miss catalog (`find_near_miss_points`) already written
  specifically to give a false-positive check real "should NOT flag" cases - this phase reads
  that existing ground truth rather than re-deriving or re-injecting it.
- DS-ANO-004's persistence format is designed for Phase 6 to consume (series/entity key,
  timestamp, score, method, run id, severity) but this phase does not implement rule evaluation,
  deduplication, or notification delivery - those are explicitly FR-060..065/DS-OPS-001..003,
  Phase 6's scope.
- Following Phase 4's established pattern: the classification/reorder-point/anomaly-detection
  pipeline lives in `packages/analytics` (pure computation), orchestrated by a thin `apps/api`
  job (`domain/inventory_job.py` or similar) that reads from Postgres, invokes the pipeline, and
  writes results - reusing the `AnalyticsRun` run-tracking table Phase 4 already built (FR-070)
  rather than inventing a parallel mechanism.
