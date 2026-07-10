# Feature Specification: Alerts & Notifications

**Feature Branch**: `007-alerts-notifications`

**Created**: 2026-07-10

**Status**: Draft

**Input**: SRS DIQ-SRS-001 v1.0.0 §13 Phase 6 — "FR-060..065, DS-OPS-001..003"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The six built-in rules fire automatically, with no manual action (Priority: P1)

As a Manager, when Phase 4/5's nightly analytics runs finish (or the moment a risky order is
submitted), the system evaluates every built-in rule against the fresh data and opens alerts for
whatever actually crossed a threshold — I never have to remember to go look.

**Why this priority**: This is the entire point of the phase — an alert rule engine that doesn't
fire automatically isn't one. Everything else (notification center, digest, admin config) exists
to surface or tune what this story produces.

**Independent Test**: Seed data with a known reorder-point breach, an aging unit, a persisted
anomaly, and a stockout-risk forecast; run the nightly job sequence; confirm one open alert per
condition, each with the right rule key and severity, and confirm submitting a high-discount
order opens rule (e)'s alert synchronously, in the same request, not on the next scheduled run.

**Acceptance Scenarios**:

1. **Given** a (model, branch) whose current on-hand stock is at or below Phase 5's persisted
   reorder point, **When** the inventory job's alert evaluation runs, **Then** an open alert for
   rule (a) exists for that series, deduplicated so a second run with the same condition doesn't
   open a duplicate (FR-061a, FR-062).
2. **Given** a unit flagged `is_aging=true` by Phase 5, **When** alert rules evaluate, **Then** an
   open alert for rule (b) exists for that unit (FR-061b).
3. **Given** a persisted `Anomaly` row from Phase 5's detector, **When** alert rules evaluate,
   **Then** an open alert for rule (c) exists whose severity derives from the anomaly's own
   DS-ANO severity score, not a separately-invented one (FR-061c, DS-ANO-004's stated hand-off).
4. **Given** a series whose Phase 4 forecast implies on-hand stock runs out before the
   configured lead time elapses, **When** alert rules evaluate, **Then** an open alert for rule
   (d) exists (FR-061d).
5. **Given** an order submission whose discount fraction exceeds the approval threshold,
   **When** the order is submitted, **Then** rule (e)'s alert opens in that same request — not
   waiting for any scheduled job — reusing the exact threshold `order_service.py` already checks
   for the manager-approval requirement, so the two can never disagree (FR-061e, FR-060's
   "transactional trigger" case).
6. **Given** a lead whose `last_activity_at` is older than the configured idle threshold,
   **When** alert rules evaluate, **Then** an open alert for rule (f) exists (FR-061f, scoped to
   the idle-days condition only this phase — see Assumptions on the score-cutoff half).
7. **Given** an alert's dedup key already has an open alert, **When** the same condition is
   detected again on a later run, **Then** no second alert opens — the existing one simply
   persists open (FR-062).

---

### User Story 2 - Alerts are visible and actionable without leaving the app (Priority: P1)

As any subscribed user, I see a badge count of open alerts relevant to me, can filter the list,
and can acknowledge or resolve one with an audit trail of who did it and when.

**Why this priority**: Alerts that only exist in a database table help no one — this is the
minimum surface for a human to act on User Story 1's output. P1 alongside it because the exit
demo explicitly names "alerts" as a visible step, not just a backend computation.

**Independent Test**: With open alerts seeded, load the notification center as a subscribed
user; confirm the badge count matches, filtering works, and acknowledging one records the actor
and moves it through open → acknowledged → resolved without a page reload losing state.

**Acceptance Scenarios**:

1. **Given** open alerts exist for roles/subscriptions a user belongs to, **When** they open the
   in-app notification center, **Then** they see a badge count and a filterable list (FR-063).
2. **Given** an open alert, **When** a permitted user acknowledges it, **Then** its lifecycle
   moves to `acknowledged` with the actor and timestamp recorded, and later to `resolved` on
   explicit action — never skipping a state (FR-062).

---

### User Story 3 - A daily digest reaches subscribed users without anyone triggering it (Priority: P1)

As a subscribed Manager, I receive one daily email summarizing new/open alerts, rendered as
readable HTML, without doing anything to request it.

**Why this priority**: The SRS's own exit demo for this phase ends at "digest in MailHog" — this
is the phase's final, most externally-visible deliverable, built on top of User Stories 1-2's
data.

**Independent Test**: With open/new alerts seeded, run the digest job; open MailHog's web UI;
confirm one HTML email per subscribed user summarizing their alerts, with no manual step between
seeding data and the email appearing.

**Acceptance Scenarios**:

1. **Given** open or newly-opened alerts exist, **When** the daily digest job runs, **Then**
   each subscribed user receives one rendered-HTML email in MailHog summarizing their alerts
   (FR-064).
2. **Given** a user with zero open/new alerts, **When** the digest runs, **Then** they receive no
   email (an empty digest is not sent) — a reasonable default matching "summarize new/open
   alerts," not a promise every subscriber gets mail every day.

---

### User Story 4 - Rule parameters are configurable without a code change (Priority: P2)

As a Manager or Admin, I can adjust a rule's thresholds, its schedule, and who's subscribed to
it, and my changes are audit-logged and versioned.

**Why this priority**: P2 — the six rules ship with sensible defaults (User Story 1) and are
independently valuable without this; this story is about tuning them over time; is not part of
the exit demo's literal wording.

**Independent Test**: As a Manager, change rule (a)'s reorder-point rule to a different service
level via the admin UI; confirm the change is audit-logged with a new version, and the next
evaluation run uses the new parameter.

**Acceptance Scenarios**:

1. **Given** a Manager or Admin, **When** they edit a rule's threshold/schedule/subscriptions in
   the admin UI, **Then** the change is saved, versioned, and recorded in the audit log (FR-065).

### Edge Cases

- What happens if the same underlying condition would fire two DIFFERENT rules (e.g., a unit is
  both aging AND flagged by a sales anomaly)? Each rule has its own dedup key namespace
  (`rule_key + entity`), so both alerts open independently — they are not the same condition,
  and a Manager needs to know about both.
- What happens if an analytics run itself fails (Phase 4/5's `AnalyticsRun.status=failed`)?
  Alert evaluation for that run's rules is skipped entirely for that cycle — evaluating rules
  against a failed run's partial or absent data would produce meaningless or missing alerts, not
  a safe default (DS-OPS-002: "partial failures mark the run failed and leave previous outputs
  live" — the previous cycle's still-open alerts remain open, nothing new fires from the failed
  run).
- What happens to an open alert if the underlying condition resolves on its own (stock
  replenished, unit sold) before anyone acknowledges it? Out of scope for auto-resolution this
  phase — alerts only move through their lifecycle via explicit user action (acknowledge/
  resolve), matching FR-062's literal wording; auto-resolution is a reasonable P2/P3 enhancement
  not required by any requirement ID in this phase's scope.
- What happens to rule (f) once Phase 7 ships real lead scores? This phase's rule (f) evaluates
  idle-days only; Phase 7 adding the score-cutoff condition is an additive filter on the same
  rule, not a rework of the alert engine (see Assumptions).

## Requirements *(mandatory)*

- **FR-060**: Alert rules evaluate automatically after each relevant analytics run (forecast,
  inventory) and on transactional triggers (order submission) — no manual action ever required.
- **FR-061**: Six built-in rules ship: (a) stock at/below reorder point, (b) vehicle aging beyond
  threshold days-on-lot, (c) sales anomaly detected (severity from DS-ANO scoring), (d) forecast
  indicates stockout within lead time, (e) order discount above approval threshold submitted,
  (f) lead idle > N days (score-cutoff half deferred to Phase 7 — see Assumptions).
- **FR-062**: Every alert has severity (info/warning/critical), a deduplication key (no duplicate
  *open* alert for the same key), a lifecycle (open → acknowledged → resolved), and an audit of
  who acknowledged it and when.
- **FR-063**: Alerts surface in an in-app notification center — badge count, filterable list,
  delivered per role/subscription.
- **FR-064**: A daily email digest summarizes new/open alerts per subscribed user, rendered HTML,
  captured by MailHog locally (no paid email service).
- **FR-065**: Managers/Admins configure rule parameters (thresholds, schedules, subscriptions) in
  an admin UI; changes are audit-logged and versioned.
- **DS-OPS-001**: Default schedule — forecasting weekly (Mon 02:00), inventory intelligence +
  anomaly detection daily (03:00 — see Assumptions on why these share one slot), digest email
  daily (07:00). All configurable. (Lead scoring's 04:00 slot is a placeholder pending Phase 7 —
  see Assumptions.)
- **DS-OPS-002**: Jobs are idempotent per (job, data-snapshot) and safe to re-run; a partial
  failure marks that run `failed` and leaves the previous run's outputs live (already true of
  Phase 4/5's run lifecycle; this phase extends the same guarantee to rule evaluation and the
  digest job).
- **DS-OPS-003**: All stochastic steps accept a seed recorded in the run row (already satisfied
  by Phase 4/5's `AnalyticsRun.seed` column; this phase's jobs have no stochastic steps of their
  own, so this ID is satisfied by inheritance, not new code).

### Key Entities

*(names match SRS §7's schema verbatim, per the established Phase 4/5 convention.)*

- **alert_rules**: one row per built-in (or future custom) rule — key, params (JSON: thresholds,
  lead-time weeks, idle-days, etc.), severity, enabled flag, version, `updated_by`. Six seeded
  rows for rules (a)-(f) at migration time, with the SRS's own stated defaults.
- **alerts**: one row per fired alert instance — rule key, dedup key, severity, payload (JSON:
  whatever the rule needs to render a human-readable message), lifecycle status, who
  acknowledged/resolved it and when.
- **notifications**: one row per (user, alert, channel) — read/unread state for the in-app
  center, emailed-at timestamp for the digest, so a user's per-channel delivery state is tracked
  independently of the alert's own lifecycle.

## Success Criteria *(mandatory)*

- **SC-001**: All six built-in rules are seeded and independently verifiable: given a
  hand-constructed condition for each rule, the corresponding alert opens with the right
  severity and dedup key, and a repeat of the same condition never opens a second open alert.
- **SC-002**: Rule (e) fires synchronously within the same order-submission request — verified
  by submitting a high-discount order via the API and confirming the alert exists immediately in
  the response's own transaction, not after a delay.
- **SC-003**: The in-app notification center renders a real badge count and a real, filterable
  alert list from actual seeded alerts — verified in a real browser.
- **SC-004**: Acknowledging and resolving an alert correctly transitions its lifecycle and
  records the actor/timestamp — no skipped states, verified against the database directly.
- **SC-005**: The daily digest job, run against seeded open/new alerts, produces one rendered-
  HTML email per subscribed user with at least one alert, visible in MailHog's own web UI — zero
  emails for a user with none.
- **SC-006**: End-to-end (the phase's own exit demo): trigger the forecast job, then the
  inventory job, confirm alerts open from their outputs, then run the digest job and confirm the
  email appears in MailHog — all without any manual step beyond the initial triggers.

## Assumptions

- **Rule (f)'s "score above cutoff" half is deferred to Phase 7**, since DS-CUST lead scoring
  (the model that would produce that score) doesn't exist yet — Phase 7's own SRS phase-table
  scope is `DS-CUST-001..005, FR-032/033, FR-074`. This phase implements rule (f) as "lead idle
  > N days" only; Phase 7 adds the score-cutoff as an additional filter on the same rule
  definition (a new `params` key, not a new rule or a rework of the evaluation engine), matching
  how DS-INV-005/DS-FC-008/009 were deferred in earlier phases without blocking their phase's
  exit.
- **Inventory intelligence and anomaly detection share one scheduled slot (03:00), not
  DS-OPS-001's literal two slots (03:00 inventory / 03:30 anomaly detection)**, because Phase 5
  already built them as a single combined job (`job_name="inventory"`) that writes
  `inventory_intel`/`unit_risk`/`anomalies` together in one run, sharing the same loaded
  orders/units data. Splitting them into two scheduled jobs now would mean loading and joining
  the same tables twice for no functional benefit — a reasoned, disclosed deviation from the
  SRS's literal schedule, not an oversight.
- **Lead scoring's 04:00 schedule slot is configured but not activated** — `alert_rules`/the
  scheduler config can reference it, but no job registration exists until Phase 7 ships
  `dealeriq_api.jobs.lead_scoring` (mirroring how Phase 4 and 5 each registered only their own
  job, never a placeholder for a future one's actual logic).
- **Rule (e) is evaluated inline inside `order_service.py`'s existing submit-order flow**,
  reusing `Settings.order_approval_discount_threshold` (the same value that already decides
  auto-approval vs. manager-approval-required) rather than a second, independently-configured
  threshold — so the alert and the approval requirement can never drift apart. This is a
  deliberate architectural choice: rule (e) is the one FR-061 rule NOT driven by an analytics
  run, and FR-060 explicitly names "transactional triggers" as the other firing path.
- **APScheduler (ADR-004, already SRS-fixed, referenced but not activated in Phases 4-5) gets
  its first real cron registrations this phase** — `BackgroundScheduler` starts alongside the API
  process with the forecast/inventory/digest jobs registered on DS-OPS-001's schedule, each
  still individually triggerable on demand via the existing `POST /jobs/{job_name}/run` (a
  scheduled firing and an on-demand HTTP trigger both funnel through the same run function and
  the same FR-072 concurrency guard).
- **The digest email is rendered server-side and delivered via SMTP to the existing MailHog
  container** (`infra/docker-compose.yml`, already running for local dev) — no third-party email
  API, consistent with the constitution's zero-paid-services principle.
- **Alert-rule evaluation lives entirely in `apps/api`'s domain layer, not
  `packages/analytics`** — unlike Phases 4-5's forecasting/anomaly-detection logic (genuine
  statistical computation over numpy/pandas series, naturally DB-free and fixture-testable),
  evaluating rules (a)-(f) is inherently a set of DB reads against already-computed
  `inventory_intel`/`unit_risk`/`anomalies`/`forecasts` rows compared to configured thresholds —
  there is no meaningful DB-free "pure" version of "is this row's value below that row's value."
  This follows the existing `order_service.py`/`inventory_service.py` domain-service precedent
  from Phase 2, not a new architectural pattern.
