# Feature Specification: Customer Analytics

**Feature Branch**: `008-customer-analytics-rfm`

**Created**: 2026-07-11

**Status**: Draft

**Input**: SRS DIQ-SRS-001 v1.0.0 §13 Phase 7 - "DS-CUST-001..005, FR-032/033, FR-074"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every customer is segmented by purchase behavior (Priority: P1)

As a Manager, I can open any customer's detail page and see which behavioral segment they fall
into (Champion, At-Risk, Hibernating, etc.) and their purchase history, so I know at a glance
whether this is a customer worth prioritizing or one who's drifting away.

**Why this priority**: RFM segmentation is the simpler, foundational half of this phase's
analytics - it requires no model training, has no cold-start problem, and everything else
(lead scoring's customer-RFM feature, the customer detail page) either consumes it or displays
it. It can ship and be independently valuable before lead scoring exists.

**Independent Test**: Run the customer-analytics job against seeded order history; open a
customer detail page for a customer with several recent, high-value orders and one for a
customer with no orders in over a year; confirm the segments and purchase history shown are
correct and clearly different.

**Acceptance Scenarios**:

1. **Given** a customer with recent, frequent, high-value orders, **When** the RFM job runs,
   **Then** their computed segment is a "good" one (e.g. Champion/Loyal), visible on their
   customer detail page (DS-CUST-001, FR-033).
2. **Given** a customer with old, infrequent, or low-value order history, **When** the RFM job
   runs, **Then** their segment reflects that (e.g. At-Risk/Hibernating) (DS-CUST-001).
3. **Given** a customer with zero orders, **When** the RFM job runs, **Then** they receive a
   defined "New"/"No purchase history" segment rather than an error or a fabricated score
   (edge case, see Assumptions).
4. **Given** any customer, **When** their detail page loads, **Then** their full order/purchase
   history is listed alongside their segment (FR-033).

---

### User Story 2 - Every open lead shows a calibrated conversion score with an explanation (Priority: P1)

As a Salesperson, I see a probability-of-winning score on each of my open leads, and can see the
top reasons driving that score, so I know which leads deserve my attention first and can explain
my prioritization to a manager.

**Why this priority**: This is the phase's own named exit demo ("calibrated lead scores with
explanations in UI") - the single most externally visible deliverable of the phase, and the
reason RFM (User Story 1) is a prerequisite (it's one of the model's own input features).

**Independent Test**: Run the lead-scoring job against seeded leads with known outcomes; open the
leads list; confirm every open lead shows a probability, that probability is well-calibrated
against actual historical win rates in aggregate, and that clicking/expanding a lead's score
reveals its top 3 contributing features in plain language.

**Acceptance Scenarios**:

1. **Given** an open lead, **When** the lead-scoring job has run at least once, **Then** the
   lead's list-page row shows its conversion probability (DS-CUST-002, FR-032).
2. **Given** a lead's displayed score, **When** a user expands its detail, **Then** the top 3
   features contributing to that score are shown in a human-readable form (not raw coefficients)
   (DS-CUST-004).
3. **Given** the full population of scored, resolved (won/lost) historical leads, **When** scores
   are grouped into probability buckets, **Then** each bucket's actual win rate is close to its
   predicted probability - the model is calibrated, not just rank-ordered (DS-CUST-003).
4. **Given** a lead that has not yet been scored (job hasn't run since it was created), **When**
   its row is displayed, **Then** it shows a clear "not yet scored" state rather than a stale or
   fabricated number (existing UI behavior, confirmed still correct this phase).

---

### User Story 3 - The score-driven idle-lead alert becomes fully real (Priority: P2)

As a Manager, the existing "lead idle" alert (built in Phase 6 as idle-days-only) now also
considers the lead's conversion score, so I'm only alerted about idle leads that were actually
promising - not every lead that's gone quiet regardless of how likely it ever was to convert.

**Why this priority**: P2 - an additive refinement of an alert rule that already works and
already fires without it (Phase 6 shipped idle-days-only deliberately, documented as deferred to
this phase). Not part of the phase's own named exit demo, but explicitly promised as this phase's
follow-through.

**Independent Test**: Configure a non-null score cutoff on the `lead_idle` rule; seed one idle
lead with a high score and one idle lead with a low score; run alert evaluation; confirm only the
high-score lead's alert opens.

**Acceptance Scenarios**:

1. **Given** the `lead_idle` rule's `score_cutoff` param is configured (non-null), **When** alert
   evaluation runs, **Then** only idle leads whose conversion score is at or above the cutoff open
   an alert (FR-061f completion).
2. **Given** `score_cutoff` is left unconfigured (null), **When** alert evaluation runs, **Then**
   the rule behaves exactly as it did in Phase 6 - idle-days only, no score filter applied (no
   regression for dealers who don't configure it).

---

### User Story 4 - Model quality is monitored, not just deployed once (Priority: P2)

As an Admin, if the population of leads coming in starts looking meaningfully different from what
the model was trained on, I get warned automatically instead of silently trusting a stale model.

**Why this priority**: P2 - a monitoring/operational safety net on top of User Story 2's model,
not required for the model to be useful on day one, but required by this phase's own requirement
scope (FR-074) and consistent with the project's established "never silently trust an unmonitored
model" posture from Phase 4/5's own run-tracking discipline.

**Independent Test**: Feed the drift check a scoring population whose feature distribution has
shifted substantially from the training reference; confirm a warning alert opens; feed it an
unchanged population; confirm no alert opens.

**Acceptance Scenarios**:

1. **Given** the lead-scoring job's current input feature distribution has drifted from the
   model's training-time reference distribution beyond the defined threshold, **When** the job
   runs, **Then** a warning-severity alert opens (FR-074).
2. **Given** the current feature distribution is consistent with the training reference, **When**
   the job runs, **Then** no drift alert opens.

### Edge Cases

- What happens to RFM segmentation for a customer with zero completed orders? They receive an
  explicit "New" segment (not Champion/At-Risk/etc., and not an error) - RFM is fundamentally
  undefined without at least one transaction, so a distinct segment name is the honest answer,
  not a fabricated quintile score.
- What happens to lead scoring for a lead whose model-of-interest, channel, or budget band is
  missing/unrecognized data? The scoring job SHALL still produce a score using the model's
  defined handling for missing/unseen categorical levels (a reference/baseline level), never
  skip the lead or crash the run.
- What happens if the lead-scoring job runs before enough historical won/lost leads exist to
  train a model at all (e.g. a brand new, just-seeded environment)? The job records a failed or
  skipped run with a clear reason in its metrics (consistent with DS-OPS-002) rather than
  producing a meaningless model; existing leads keep showing "not yet scored."
- What happens to a lead's score once it transitions to won/lost? It keeps its last-computed
  score for historical/audit display; scoring only continues to matter operationally for open
  leads, but past scores are not deleted.
- What happens if a Manager sets `lead_idle`'s `score_cutoff` to a value no lead can satisfy
  (e.g. above 1.0 is rejected by validation, but a very high in-range value is allowed)? The rule
  simply fires less often or never - a valid, intentional configuration outcome, not an error.

## Requirements *(mandatory)*

### Functional Requirements

- **DS-CUST-001**: Every customer SHALL be scored on Recency, Frequency, and Monetary quintiles
  and mapped to a named behavioral segment using standard RFM practice.
- **DS-CUST-002**: A lead-conversion model SHALL predict the probability of winning for every open
  lead, using features drawn from the lead's own record, its customer's RFM segment, its
  associated vehicle model's segment, and time-based signals (recency of creation, seasonality).
- **DS-CUST-003**: The baseline model SHALL be a regularized logistic regression; scores shown to
  users MUST be calibrated (i.e., a lead scored 70% should convert roughly 70% of the time in
  aggregate), verified by reporting discrimination (ROC-AUC, PR-AUC) and calibration (reliability
  curve, Brier score) metrics for every model-training run. A more complex challenger model MAY
  be evaluated and promoted only if it demonstrably outperforms the baseline on a held-out,
  time-based validation split - this is optional and not required for the phase to be complete.
- **DS-CUST-004**: Every displayed lead score SHALL be accompanied by its top 3 contributing
  factors, expressed in a form a non-technical user can understand.
- **DS-CUST-005**: Model training SHALL use a temporal (time-based) train/validation split - no
  future leads leaking into the training set - and SHALL handle any class imbalance between
  won/lost outcomes via training-time weighting, never by altering the validation set's true
  composition.
- **FR-032**: Each open lead SHALL display its current conversion probability score and score
  explanation (top contributing features) once scoring has run.
- **FR-033**: Customer detail pages SHALL display RFM segment membership and purchase history.
- **FR-074**: Data drift SHALL be monitored for the lead-scoring model via a population stability
  measure on input features; a substantial drift (beyond a defined threshold) SHALL raise a
  warning-severity alert.

### Key Entities

*(names describe the concepts introduced; exact schema is a planning-phase decision.)*

- **Customer RFM profile**: one computed record per customer per analytics run - recency/
  frequency/monetary quintile scores and the named segment they map to.
- **Lead score**: one computed record per open lead per analytics run - conversion probability,
  the model version/run that produced it, and its top-3 contributing factors.
- **Lead-scoring model run**: the trained model artifact and its evaluation metrics (ROC-AUC,
  PR-AUC, calibration) for one training cycle, tracked the same way every prior phase's analytics
  runs are tracked (job name, parameters, data snapshot bounds, seed, status, metrics).
- **Drift check result**: the population-stability comparison between the current scoring
  population and the model's training-time reference, produced alongside each scoring run.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every customer in the seeded database has a computed RFM segment, independently
  verifiable by hand-picking a known high-value repeat customer and a known dormant customer and
  confirming their segments are correct and distinguishable.
- **SC-002**: Every open lead in the seeded database has a conversion probability and a top-3
  explanation visible in the UI, with zero leads showing a stale or fabricated score.
- **SC-003**: When historical (already won/lost) leads are grouped into score deciles, actual win
  rate per decile tracks predicted probability closely - the model is demonstrably calibrated,
  not just rank-ordered, verified against real seeded data (not only a synthetic fixture).
- **SC-004**: The `lead_idle` alert rule, once a score cutoff is configured, only fires for idle
  leads meeting both the idle-days and score conditions - verified against real seeded data.
- **SC-005**: A deliberately drifted scoring population triggers a warning alert; an undrifted one
  does not - verified with both a real and a synthetic/injected drift scenario.
- **SC-006**: The phase's own exit demo - a user opens the leads list and sees calibrated
  conversion scores with explanations, with zero manual steps beyond the initial job triggers.

## Assumptions

- **RFM segment names use a standard, documented five-segment mapping** (e.g. Champions / Loyal
  Customers / At-Risk / Hibernating / New), since the SRS gives illustrative examples
  ("Champions, At-Risk, Hibernating") rather than an exact table - recorded as an ADR at planning
  time, following the same "pick an industry-standard convention and document it" approach used
  for Phase 5's ABC/XYZ cutoffs and Kaplan-Meier censoring choice.
- **Lead interaction-count, as a model feature, is derived from the existing lead status-history
  audit trail** (the count of recorded status transitions for a lead), since no dedicated
  interaction/touch-log table exists in the schema and this phase does not add one - a real,
  already-available proxy rather than a new persisted concept invented for this phase alone.
- **The gradient-boosted challenger model (DS-CUST-003's "MAY be promoted") is optional for this
  phase's completion.** The P0 requirement is a calibrated logistic-regression baseline; the
  challenger is explicitly a "MAY," and if building and fairly evaluating it would risk the
  phase's P0 scope, it is deferred to `docs/backlog.md` as a P1/P2 follow-up rather than blocking
  this phase's exit.
- **FR-074's drift monitoring is evaluated as part of the lead-scoring job itself**, not a
  separately-scheduled job - the population being checked for drift is exactly the population
  that job just scored, so checking it inline (and opening its own alert, reusing the alert
  lifecycle machinery Phase 6 already built) avoids inventing a second, redundant schedule entry
  for the same underlying data.
- **Rule (f)'s (`lead_idle`) score-cutoff completion is additive, not a rework** - Phase 6 already
  built the rule's dedup-key/lifecycle/idle-days logic and left `score_cutoff` as a `None`
  placeholder specifically so this phase could complete it without touching anything else about
  how the rule fires or how alerts are managed.
- **Model training here fits directly against the persisted seeded database** (real leads/
  customers/orders), not the Phase 3 seed generator's own in-memory ground-truth simulation -
  that simulation's coefficients and sign-recovery were already validated independently in Phase
  3. This phase's own scientific-validation gate is a fresh calibration/discrimination check
  against real, persisted data, matching the precedent QA-003(b) set in Phase 5 (validate against
  real seeded data, not only a synthetic fixture) - full detail is a planning-phase decision.
- **Lead scoring's DS-OPS-001 04:00 daily schedule slot is activated this phase**, alongside the
  four cron jobs Phase 6 already registered - the placeholder Phase 6 left unfilled in its own
  scheduler configuration.
