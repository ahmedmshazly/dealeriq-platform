# Implementation Plan: Dashboards & Reports

**Branch**: `009-dashboards-reports` | **Date**: 2026-07-11 | **Spec**: `specs/009-dashboards-reports/spec.md`

## Summary

A Manager dashboard and a Sales dashboard (both new, aggregating already-persisted Phase 2/4/5/6/7
data behind two new endpoints), a genuinely new "achieved accuracy" diagnostic (FR-073) reusing
Phase 4's existing `mase()` metric against real historical forecasts vs. real actuals, a monthly
report view, and reusable CSV/PNG chart-export utilities wired into this phase's new charts. The
Analyst workbench (FR-052) is largely already delivered by Phase 4/5's `/analytics`,
`/analytics/[seriesKey]`, and `/inventory-intel` pages - this phase's contribution there is the
achieved-accuracy diagnostic plus light cross-linking.

## Technical Context

**Language/Version**: Python 3.12 (`apps/api`, `packages/analytics`), TypeScript/Next.js 15
(`apps/web`) - unchanged.

**Primary Dependencies**: none new. Achieved accuracy reuses
`dealeriq_analytics.forecasting.metrics.mase` (Phase 4) directly rather than adding a new pure
function - the metric itself is unchanged; only what's compared (real historical forecasts vs.
real actuals, instead of CV folds) is new. Chart export uses the browser's native SVG→canvas
`toBlob` (no new npm dependency) for PNG, and a plain string-join blob download for CSV.

**Storage**: PostgreSQL 16. No new tables - achieved accuracy is computed on demand from
already-persisted `Forecast`/order data (spec.md's Assumptions: not a new analytics-run
lifecycle); the monthly sales target is a single `Settings`-level configurable constant
(`default_monthly_sales_target`), matching the existing
`order_approval_discount_threshold`-style config pattern, not a new table - proper
per-salesperson quota management is backlogged (P2). One migration: two new permission keys
(`dashboard:view_manager`, `dashboard:view_sales`).

**Testing**: pytest for the achieved-accuracy computation (hand-computed fixture: known past
forecasts vs. known actuals → a known MASE, mirroring Phase 4's own `mase()` fixture test) and
the sales-aggregation queries; testcontainers-python integration tests (ADR-013) for the two new
dashboard endpoints and the monthly report endpoint, each verified against hand-constructed DB
fixtures.

**Target Platform**: unchanged - Docker Compose local dev, single-instance.

**Project Type**: Web application (existing `apps/api` + `apps/web` + `packages/analytics`
monorepo) - no new top-level project.

**Performance Goals**: dashboard aggregate endpoints compose ~5 already-indexed queries each;
expected well under a second against the seeded dataset's scale, consistent with every other
read-path endpoint in the system.

**Constraints**: NFR-007's 15-minute `make bootstrap && make seed && make dev` budget is
unaffected (nothing here runs at bootstrap/seed time). The Manager/Sales dashboards must never
show another user's or another salesperson's data - enforced server-side, not just hidden client-
side, matching the project's established "server enforces, client hides cosmetically" convention.

**Scale/Scope**: two new aggregate dashboard endpoints, one new achieved-accuracy endpoint, one
new monthly-report endpoint, one migration (two permission keys), two new frontend pages
(dashboard rewritten with role branching, a new reports page), reusable export utilities wired
into this phase's new charts.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I (Monorepo & Stack Discipline)**: achieved-accuracy computation reuses Phase 4's
  existing `packages/analytics` `mase()` function directly (DB-free, already-tested) - no new
  pure-analytics module needed since the metric itself doesn't change, only its inputs. All
  aggregation/orchestration lives in `apps/api`'s domain layer, matching Phase 6's precedent for
  DB-reading composition logic that isn't itself statistical computation. No new dependencies.
- **Principle II (Free, Local-First, Zero Paid Services)**: PNG/CSV export uses only browser-
  native APIs (`canvas.toBlob`, `Blob`/`URL.createObjectURL`) - no third-party export service.
- **Principle III (Security & RBAC by Default)**: two new deny-by-default permission keys
  (`dashboard:view_manager`: admin/manager; `dashboard:view_sales`: admin/manager/sales), matching
  the SRS role table's evident intent; the Sales dashboard's "my" data is scoped server-side by
  `current_user.id`, never a client-supplied parameter - the same ownership-scoping pattern
  `routes/alerts.py` already established for per-user notification scoping.
- **Principle IV (Migrations & Append-Only Data Integrity)**: no new tables; the one migration
  only seeds two permission rows, matching Phase 6/7's permission-seeding-only migration
  precedent where no new domain tables were needed.
- **Principle V (Analytics Reproducibility & Scientific Integrity)**: achieved accuracy reuses
  an already-validated metric (`mase()`, hand-computed-fixture-tested in Phase 4) against real
  historical data - this phase's own test validates the *selection/alignment* of which forecasts
  and actuals get compared, not the metric formula itself (already proven).
- **Principle VII (Testing bar)**: achieved-accuracy alignment logic gets a hand-constructed
  fixture test (known past `Forecast` rows + known actuals → a known MASE) before being wired
  into any route; both new dashboard endpoints and the monthly report get real-DB-fixture
  integration tests, including an explicit "another user's data never leaks in" assertion for the
  Sales dashboard.
- **No violations requiring Complexity Tracking.**

## Project Structure

### Documentation (this feature)

```text
specs/009-dashboards-reports/
├── spec.md
├── plan.md              # this file
└── tasks.md              # Phase 2 output
```

### Source code

```text
apps/api/src/dealeriq_api/
├── domain/
│   ├── achieved_accuracy.py        # NEW: for a series, selects which past Forecast rows are
│   │                                # now "out of sample" (their week_start has passed),
│   │                                # dedups one yhat per week (earliest covering run, for the
│   │                                # longest genuine lead time), reconstructs real actuals via
│   │                                # forecast_job.get_series_actuals, calls
│   │                                # dealeriq_analytics.forecasting.metrics.mase
│   ├── dashboard_service.py         # NEW: manager_dashboard(db, as_of) and
│   │                                # sales_dashboard(db, user_id, as_of) - each composes
│   │                                # several already-existing service/query functions into one
│   │                                # aggregate payload
│   ├── sales_summary.py              # NEW: monthly delivered-order revenue/margin by branch and
│   │                                 # by salesperson (delivery date from OrderEvent
│   │                                 # to_status="delivered", matching the existing timeline
│   │                                 # convention - Order itself has no delivered_at column);
│   │                                 # top/bottom models by recent revenue
│   └── monthly_report.py              # NEW: composes sales_summary + achieved_accuracy +
│                                       # alert-statistics for one completed calendar month
├── routes/
│   ├── dashboards.py                  # NEW: GET /dashboards/manager, GET /dashboards/sales
│   └── reports.py                      # NEW: GET /reports/monthly?month=YYYY-MM
├── schemas/
│   ├── dashboards.py                   # NEW response models
│   └── reports.py                       # NEW response models
└── core/
    └── config.py                        # MODIFIED: + default_monthly_sales_target: float

apps/api/alembic/versions/
└── <rev>_dashboard_permissions.py       # seeds dashboard:view_manager, dashboard:view_sales

apps/api/tests/
├── unit/test_achieved_accuracy.py        # hand-computed fixture: known past forecasts + known
│                                          # actuals -> a known MASE
└── integration/
    ├── test_dashboards.py                 # manager dashboard against real fixtures; sales
    │                                       # dashboard scoped correctly (another salesperson's
    │                                       # leads/orders never appear)
    └── test_monthly_report.py              # real fixtures for a completed month -> hand-checked
                                             # sales/margin/accuracy/alert totals

apps/web/
├── lib/
│   └── chart-export.ts                    # NEW: exportChartAsPng(svgRef), downloadCsv(filename,
│                                           # rows) - reusable, wired into this phase's new charts
└── app/(authenticated)/
    ├── dashboard/page.tsx                  # REWRITTEN: role-branches (admin/manager -> Manager
    │                                       # dashboard; sales -> Sales dashboard; analyst ->
    │                                       # links into the existing /analytics workbench)
    ├── analytics/[seriesKey]/page.tsx       # MODIFIED: adds the achieved-accuracy diagnostic
    │                                        # alongside the existing fan chart
    └── reports/page.tsx                     # NEW: monthly report view, month picker defaulting
                                              # to the most recently completed month
```

**Structure Decision**: extends the existing three-package monorepo - no new top-level
directories. `dashboard/page.tsx` stays a single route with role branching (matching how
`app-shell.tsx` already role-branches nav items), not three separate URLs.

## Achieved accuracy (FR-073, feeding FR-052 and FR-054)

For a series, gather every `Forecast` row (across all succeeded forecast runs) whose
`week_start` has already passed as of `as_of`. A given future week is typically forecast by
several weekly runs at different lead times before it arrives (DS-OPS-001: forecasting runs
weekly, each with a 12-week horizon) - deduplicate to one `yhat` per week by taking the
**earliest** run that forecast it, the longest genuine lead time and the strictest honest
"out-of-sample" comparison (using a later, closer-to-the-event run's forecast for the same week
would partly benefit from hindsight the earlier run didn't have). Reconstruct real actuals for
those same weeks via `forecast_job.get_series_actuals`. Feed `(y_true, y_pred)` plus the series'
full historical demand (as `y_train`, for `mase()`'s scaling denominator - the exact same role it
already plays in Phase 4's CV) into the existing, already-validated `mase()` function. Default
evaluation window: 12 weeks (~3 months, FR-073's own example) for the Analyst workbench view;
the monthly report (FR-054) narrows this to the single most recently completed calendar month.

A series with no forecast old enough to have real actuals yet returns `None` (spec.md's Edge
Cases: "not enough history yet," never a fabricated number).

## Manager dashboard (FR-050)

`dashboard_service.manager_dashboard(db, as_of)` composes:
- **Sales vs. forecast**: sum of delivered-order revenue this month (by branch,
  `sales_summary.monthly_sales_by_branch`) vs. the sum of the relevant `(model, branch)` series'
  persisted forecast `yhat`/`yhat_lo80`/`yhat_hi80` for this month's weeks (from the latest
  succeeded forecast run) - reusing Phase 4's persisted output directly, no new "target" needed
  (spec.md's Assumptions).
- **Top/bottom models**: `sales_summary.top_bottom_models` - ranked by recent delivered revenue.
- **Inventory health**: reuses the existing `GET /inventory/abc-xyz` and
  `GET /inventory/units?aging_only=true` service functions directly (called in-process, not via
  an internal HTTP round-trip).
- **Open anomalies / unacknowledged alerts**: reuses the existing anomaly/alert query functions,
  scoped exactly as their own routes already scope them (role-subscribed notifications for
  alerts, matching Phase 6's fan-out).

## Sales dashboard (FR-051)

`dashboard_service.sales_dashboard(db, user_id, as_of)` composes:
- **My open leads ranked by conversion score**: reuses `lead_service.list_leads(owner_id=user_id)`
  plus the same `LeadScore` enrichment `routes/leads.py` already does, sorted by
  `conversion_probability` descending (the existing `GET /leads` route sorts by
  `last_activity_at`; this dashboard-specific composition sorts by score instead, since FR-051
  explicitly wants "ranked by conversion score").
- **My monthly sales vs. target**: `sales_summary.monthly_sales_by_salesperson(user_id)` vs.
  `settings.default_monthly_sales_target`.
- **My notifications**: reuses the exact same per-user-scoped query `GET /alerts` already uses.

Ownership scoping (`user_id` always from `current_user`, never a request parameter) is the one
security-critical property this endpoint must never regress - directly tested (SC-002).

## CSV/PNG export (FR-053)

`lib/chart-export.ts`: `exportChartAsPng(svgElement)` serializes the on-screen Recharts SVG,
draws it to an offscreen `<canvas>`, and downloads via `canvas.toBlob`; `downloadCsv(filename,
rows)` joins an array of records into a CSV string and downloads via a `Blob`/
`URL.createObjectURL` anchor click - both pure client-side, no new dependency. Wired into the
Manager dashboard's sales-vs-forecast chart and the achieved-accuracy diagnostic added to
`/analytics/[seriesKey]` this phase (spec.md's Assumptions: retrofitting every earlier chart is
not required for this phase's own exit criteria).

## Monthly report (FR-054)

`monthly_report.py` composes, for one completed calendar month (`?month=YYYY-MM`, defaulting to
the most recently completed month): `sales_summary`'s revenue/margin totals for that month,
`achieved_accuracy`'s per-series figures narrowed to that month's weeks, and alert
counts-by-rule/severity for that month (a straightforward `Alert` query filtered by
`created_at`). Requesting the current, in-progress month is rejected with a clear message
(spec.md's Edge Cases), not silently showing incomplete data as final.

## Validation sequence (proves the phase works end-to-end)

1. Seed hand-constructed fixtures (delivered orders this month, a succeeded forecast run, open
   anomalies, open alerts); confirm the Manager dashboard endpoint returns all five sections with
   real, correctly-computed values (SC-001).
2. Seed two salespeople's leads/orders/notifications; confirm each one's Sales dashboard shows
   only their own data, ranked correctly by score (SC-002).
3. Seed a past forecast run old enough to have real actuals for some of its weeks; confirm the
   achieved-accuracy diagnostic returns a real, hand-checkable MASE, distinct from the
   training-time CV metrics already shown (SC-003).
4. Export a real chart as PNG and CSV in a real browser; confirm both downloads are real and
   correct (SC-004).
5. Seed a full completed prior month's data; confirm the monthly report's totals match an
   independent hand computation (SC-005).
6. Full exit demo: log in as a Manager and as a Salesperson in a real browser; confirm both
   dashboards render fully populated with zero manual steps beyond logging in (SC-006).
