# Feature Specification: Dashboards & Reports

**Feature Branch**: `009-dashboards-reports`

**Created**: 2026-07-11

**Status**: Draft

**Input**: SRS DIQ-SRS-001 v1.0.0 §13 Phase 8 - "FR-050..054, FR-073"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A Manager sees the health of their business at a glance (Priority: P1)

As a Manager, I open a single dashboard and immediately see how this month's sales compare to
what was forecast, which models are selling best and worst, the state of my inventory (aging,
risk), any open anomalies, and any alerts I haven't yet dealt with - without visiting five
different pages.

**Why this priority**: This is the phase's own named exit criterion ("Manager/Sales dashboards
complete") and the SRS's own top-priority requirement (FR-050, P0).

**Independent Test**: Log in as a Manager with real seeded data; confirm the dashboard shows a
real sales-vs-forecast comparison for the current month (with a visible prediction-interval
band), a real top/bottom models list, a real ABC/XYZ + aging summary, real open anomalies, and a
real unacknowledged-alerts count - all sourced from actual data, none fabricated or hardcoded.

**Acceptance Scenarios**:

1. **Given** real orders delivered this month and a succeeded forecast run covering the current
   month, **When** a Manager opens their dashboard, **Then** they see actual sales vs. the
   forecast's point estimate and 80% interval band for the same period (FR-050).
2. **Given** real order history across models, **When** the dashboard loads, **Then** it shows
   the top and bottom performing models by recent sales (FR-050).
3. **Given** Phase 5's persisted inventory intelligence, **When** the dashboard loads, **Then**
   it shows an inventory health summary (ABC/XYZ heatmap, aging buckets) (FR-050).
4. **Given** open anomalies and open alerts a Manager is subscribed to, **When** the dashboard
   loads, **Then** both are visible with real counts/entries, not stale or fabricated (FR-050).

---

### User Story 2 - A Salesperson sees their own pipeline and performance (Priority: P1)

As a Salesperson, I open my dashboard and see my own open leads ranked by how likely they are to
convert, how my sales this month compare to my target, and my own notifications - everything I
need to prioritize my day.

**Why this priority**: The phase's other named exit criterion (Sales dashboard), P0 in the SRS
(FR-051).

**Independent Test**: Log in as a Salesperson with real seeded leads and orders assigned to them;
confirm their dashboard shows only their own open leads ranked by real conversion scores, a real
sales-vs-target comparison for the current month, and their own real notifications - never
another salesperson's data.

**Acceptance Scenarios**:

1. **Given** open leads owned by the current Salesperson with real conversion scores from Phase
   7, **When** they open their dashboard, **Then** the leads are listed ranked highest-probability
   first (FR-051).
2. **Given** real delivered orders by the current Salesperson this month, **When** the dashboard
   loads, **Then** their sales-to-date is compared against a real monthly target (FR-051).
3. **Given** open notifications for the current Salesperson, **When** the dashboard loads,
   **Then** they see their own real notifications, never another user's (FR-051).

---

### User Story 3 - An Analyst can judge whether forecasts are actually working (Priority: P1)

As an Analyst, beyond the champion/challenger comparison already available from training-time
cross-validation, I want to see how forecasts have actually performed against real results after
the fact - a rolling accuracy view - alongside the diagnostics, leaderboard, and anomaly explorer
already available to me, so I can judge model health with real outcomes, not just held-out
validation.

**Why this priority**: FR-073's own requirement (P1) - a genuinely new capability not covered by
any earlier phase, layered onto the workbench earlier phases already built.

**Independent Test**: With multiple months of real forecast history and real actuals available,
confirm the rolling-accuracy view shows a real, computed error metric comparing what was forecast
in past runs against what actually happened, per series, distinct from the existing
cross-validation-based leaderboard metrics.

**Acceptance Scenarios**:

1. **Given** a series with a forecast made in a past run and real actuals that have since
   materialized for those same weeks, **When** an Analyst views that series' rolling-accuracy
   diagnostic, **Then** they see a real, computed out-of-sample accuracy figure (e.g. achieved
   MASE over the last 3 months), not the training-time cross-validation metric already shown
   elsewhere (FR-073).
2. **Given** multiple series with rolling accuracy computed, **When** an Analyst views the
   leaderboard, **Then** they can distinguish which series' forecasts are actually panning out
   from which aren't (FR-073).

---

### User Story 4 - Anyone can export a chart or its data (Priority: P2)

As any dashboard user, I can export a chart I'm looking at as an image, and its underlying data
as a spreadsheet-readable file, so I can drop it into a slide deck or analyze it further myself.

**Why this priority**: P2 in the SRS (FR-053) - a real, useful convenience layered on top of
User Stories 1-3's charts, not required for any of them to be independently valuable.

**Independent Test**: With any dashboard chart on screen, trigger its export controls; confirm a
real PNG image downloads matching what's on screen, and a real CSV file downloads containing the
chart's underlying data points.

**Acceptance Scenarios**:

1. **Given** any chart on a dashboard or the analyst workbench, **When** a user exports it as an
   image, **Then** a real PNG file downloads (FR-053).
2. **Given** the same chart, **When** a user exports its data, **Then** a real CSV file downloads
   containing the chart's actual underlying data points (FR-053).

---

### User Story 5 - Anyone can review last month's performance in one place (Priority: P2)

As any dashboard user, I can open a monthly report summarizing last month's sales, margin,
forecast accuracy achieved, and alert statistics, so I don't have to reconstruct the month from
several different views.

**Why this priority**: P2 in the SRS (FR-054) - depends on User Story 3's rolling-accuracy
computation and is a summary/convenience layer, not required for the phase's own named exit
criterion.

**Independent Test**: With a full prior month of real seeded data, open the monthly report;
confirm it shows real sales and margin totals for that month, a real forecast-accuracy figure
for that month, and real alert statistics - all computed, not fabricated placeholders.

**Acceptance Scenarios**:

1. **Given** a completed prior month of real orders, **When** any user opens the monthly report,
   **Then** they see real sales and margin totals for that month (FR-054).
2. **Given** the same month's forecast and actual data, **When** the report loads, **Then** it
   shows the real forecast accuracy achieved for that month (FR-054, reusing User Story 3's
   computation).
3. **Given** the same month's alert history, **When** the report loads, **Then** it shows real
   alert statistics (counts by rule/severity) for that month (FR-054).

### Edge Cases

- What happens for a Manager/Salesperson dashboard when no succeeded forecast run exists yet
  (a brand-new environment)? The sales-vs-forecast/rolling-accuracy sections show a clear
  "no forecast data yet" state, never a fabricated number or a crash.
- What happens for a Salesperson with zero open leads or zero orders this month? Their dashboard
  shows an honest empty state ("no open leads" / "$0 this month"), not an error.
- What happens to the monthly report for the current, still-in-progress month? The report is
  scoped to *completed* prior months only - the current month's data is incomplete by definition,
  so showing it as "the month's totals" would be misleading; the report always defaults to the
  most recently completed calendar month.
- What happens to "my monthly sales vs. target" if no target has been configured? A single
  admin-configurable default target applies to every salesperson this phase (see Assumptions) -
  never a missing/undefined comparison.
- What happens to the rolling-accuracy diagnostic for a series with no forecast old enough to
  have real actuals yet (a newly-onboarded series)? It shows "not enough history yet" rather than
  computing an error metric over zero or misleading data.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-050**: A Manager dashboard SHALL show: sales this month vs. forecast (with prediction
  interval band), top/bottom models, an inventory health summary (ABC/XYZ heatmap, aging
  buckets), open anomalies, and unacknowledged alerts.
- **FR-051**: A Sales dashboard SHALL show: the current Salesperson's own open leads ranked by
  conversion score, their monthly sales vs. target, and their own notifications.
- **FR-052**: An Analyst workbench SHALL show: per-series forecast diagnostics (actuals, fitted,
  forecast fan chart), a benchmark leaderboard (method × metric), an anomaly explorer (series
  with flagged points), and model-run history.
- **FR-053**: All dashboard charts SHALL be exportable as PNG, and their underlying data as CSV.
- **FR-054**: A monthly report view SHALL summarize sales, margin, forecast accuracy achieved
  (last month's forecast vs. actual), and alert statistics.
- **FR-073**: The system SHALL compute rolling forecast accuracy (e.g. last-3-month MASE per
  series) and display method leaderboards distinguishing champion (training-time) performance
  from actually-achieved (rolling, out-of-sample) performance per series.

### Key Entities

*(names describe the concepts introduced; exact schema is a planning-phase decision.)*

- **Achieved accuracy record**: a computed (not stored ground-truth) figure per series per
  evaluation window - how a past forecast's point estimates compared to the actuals that
  materialized after the forecast was made, distinct from the training-time cross-validation
  metrics Phase 4 already persists.
- **Monthly sales target**: the single configurable figure a Salesperson's monthly sales are
  compared against this phase (see Assumptions on scope).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A Manager can see their business's current-month sales-vs-forecast position, model
  performance ranking, inventory health, open anomalies, and unacknowledged alerts within a
  single page load, with zero fabricated or placeholder values against real seeded data.
- **SC-002**: A Salesperson can see only their own open leads (ranked by real conversion score),
  their own monthly sales vs. target, and their own notifications - verified that another
  salesperson's data never leaks into their view.
- **SC-003**: An Analyst can distinguish, per series, training-time (cross-validation) accuracy
  from actually-achieved (rolling, out-of-sample) accuracy, both backed by real computation
  against real historical forecasts and actuals.
- **SC-004**: Any dashboard chart can be exported as a real PNG matching what's on screen, and its
  data as a real, correctly-populated CSV.
- **SC-005**: The monthly report, opened for a completed prior month with real data, shows real
  sales, margin, forecast-accuracy, and alert-statistics figures for that month - verified against
  independently hand-computed totals from the same underlying data.
- **SC-006**: The phase's own exit demo - a Manager and a Salesperson can each open their
  respective dashboard and see it fully populated with real data, with zero manual steps beyond
  logging in.

## Assumptions

- **FR-052 (Analyst workbench) is satisfied primarily by prior-phase work.** Phase 4 already
  built a forecast leaderboard with pattern-class filtering and model-run history
  (`/analytics`), and a per-series actuals/forecast/interval-band fan chart
  (`/analytics/[seriesKey]`); Phase 5 already built a filterable anomaly explorer
  (`/inventory-intel`). This phase's own contribution to FR-052 is FR-073's genuinely new
  rolling/achieved-accuracy diagnostic, added into that same workbench area, plus light
  cross-linking between the existing pages so they read as one coherent workbench rather than
  three separately-discovered routes. This is a scope-narrowing observation, not a shortcut:
  every part of FR-052's literal wording is met, just mostly by work already delivered.
- **"Sales this month vs. forecast" (FR-050) needs no new "target" concept** - it compares real
  delivered-order revenue this month against the sum of the relevant series' already-persisted
  forecast point estimates (and interval band) for the same weeks, both already available from
  Phase 2 (orders) and Phase 4 (forecasts).
- **"My monthly sales vs. target" (FR-051) introduces the simplest viable target concept**: a
  single admin-configurable default monthly sales figure applied uniformly to every Salesperson,
  not a full per-salesperson quota-management system (which would be a genuine, unscoped
  expansion - no such concept exists anywhere in the domain today). Proper per-salesperson quota
  management is recorded as a P2 backlog item, the same pattern used for prior phases' own scope
  traps (e.g. FR-034, FR-082).
- **Rolling/achieved accuracy (FR-073) is computed on demand from already-persisted data** (past
  `Forecast` rows plus real actuals reconstructed the same way Phase 4's fan chart already does),
  not as a new standalone scheduled job - it reads history that already exists rather than
  requiring a new analytics-run lifecycle of its own.
- **The monthly report (FR-054) always defaults to the most recently fully-completed calendar
  month** - the current, in-progress month is never presented as "the month's totals," since its
  data is necessarily incomplete.
- **CSV/PNG export (FR-053) is built once as reusable utility code** and wired into every chart
  introduced or touched by this phase; retrofitting it onto every chart from every earlier phase
  is not required for this phase's own exit criteria, though the utility itself is written
  generically enough to be reused there later without rework.
