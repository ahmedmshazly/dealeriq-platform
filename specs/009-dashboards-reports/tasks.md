# Tasks: Dashboards & Reports

**Input**: plan.md from `specs/009-dashboards-reports/`

## Task list

- [x] T001 Alembic migration: seed `dashboard:view_manager` (admin/manager),
      `dashboard:view_sales` (admin/manager/sales) permissions - no new tables; verified via
      `alembic upgrade head` + `alembic check` (empty diff) + downgrade/upgrade round-trip
- [x] T002 `apps/api/src/dealeriq_api/core/config.py` MODIFIED: add
      `default_monthly_sales_target: float` setting
- [x] T003 `apps/api/src/dealeriq_api/domain/achieved_accuracy.py`: for a series, gather every
      past `Forecast` row whose `week_start` has already passed, dedup to one `yhat` per week via
      the *earliest* covering run (ADR-024), reconstruct real actuals via
      `forecast_job.get_series_actuals`, call the existing
      `dealeriq_analytics.forecasting.metrics.mase`; returns `None` if no forecast is old enough
      to have real actuals yet (never a fabricated number)
- [x] T004 Integration test `apps/api/tests/integration/test_achieved_accuracy.py` (corrected
      from the plan's `tests/unit/` - this needs a live DB via `get_series_actuals`, so it
      belongs alongside every other domain-layer test in `tests/integration/`, not the DB-free
      `tests/unit/`): a hand-computed 53-week fixture (the minimum for `mase()`'s season-52
      denominator to be non-empty) - two runs forecasting the same 4 weeks with different yhats
      confirms the earliest-run dedup rule (using the later run's exactly-correct forecast would
      give MASE=0; the test asserts the earlier run's MASE=1.0 instead); plus "no forecast old
      enough" and "unknown series" → `None` cases
- [x] T005 `apps/api/src/dealeriq_api/domain/sales_summary.py`: `monthly_sales_by_branch`,
      `monthly_sales_by_salesperson` (delivery date from `OrderEvent` where
      `to_status="delivered"`, matching the existing order-timeline convention since `Order` has
      no `delivered_at` column), `top_bottom_models`, `monthly_sales_and_margin`. Sanity-checked
      against the real seeded database: per-branch totals sum exactly to the overall monthly
      revenue; top/bottom models show real, sensible dollar figures.
- [x] T006 `apps/api/src/dealeriq_api/domain/dashboard_service.py`: `manager_dashboard` and
      `sales_dashboard`, each composing purpose-built summary queries (inventory ABC/XYZ counts +
      aging count, open anomaly count, unacknowledged alert count mirroring `routes/alerts.py`'s
      own per-user scoping, leads+scores ranked by probability) plus T003/T005 - no internal HTTP
      round-trips. Sanity-checked against the real seeded database (28 real ranked open leads for
      a real salesperson, real $820,812.22 this-month sales, real top models); discovered the
      forecast/inventory/alerts/digest pipeline hadn't been re-run since Phase 7's reseed -
      triggered a fresh run of all four in the background for later verification steps.
- [x] T007 `apps/api/src/dealeriq_api/routes/dashboards.py` +
      `apps/api/src/dealeriq_api/schemas/dashboards.py`: `GET /dashboards/manager`
      (`dashboard:view_manager`), `GET /dashboards/sales` (`dashboard:view_sales`, scoped to
      `current_user.id` server-side, never a request parameter)
- [x] T008 Integration tests `apps/api/tests/integration/test_dashboards.py` (3 tests): Manager
      dashboard returns real, correctly-computed values against hand-constructed fixtures; two
      different salespeople's dashboards never leak one's leads/sales/alerts into the other's
      response (SC-002's security-critical property, explicitly asserted both directions);
      analyst role (no dashboard permissions) gets 403
- [x] T009 `apps/api/src/dealeriq_api/domain/monthly_report.py`: composes `sales_summary` +
      `achieved_accuracy` (extended with an explicit `window_start`/`window_end` for an exact
      calendar month, rather than only the rolling `window_weeks`-back default) + alert
      counts-by-rule/severity for one completed calendar month; rejects the current in-progress
      month with `CurrentMonthNotAllowed` (spec.md's Edge Cases)
- [x] T010 `apps/api/src/dealeriq_api/routes/reports.py` +
      `apps/api/src/dealeriq_api/schemas/reports.py`: `GET /reports/monthly?month=YYYY-MM`,
      defaulting to the most recently completed month when `month` is omitted; reuses
      `dashboard:view_manager` (the report includes margin, Manager+ only per FR-043's
      precedent) rather than a new permission key
- [x] T011 Integration tests `apps/api/tests/integration/test_monthly_report.py` (4 tests):
      hand-constructed fixtures for a completed month → sales/margin/alert totals matching an
      independent hand computation, with an order/alert deliberately placed just outside the
      month proven excluded; the current month returns 400, not partial data; a malformed
      `month` returns 400; the no-argument default resolves to a genuinely prior month
- [x] T012 Regenerate `packages/api-client` against the new endpoints - `tsc --noEmit` clean
- [x] T013 `apps/web/lib/chart-export.ts`: `exportChartAsPng(svgElement)` (SVG→canvas→
      `toBlob`, no new dependency) and `downloadCsv(filename, rows)` (`Blob`/
      `URL.createObjectURL`) - reusable, no chart-specific coupling. `tsc --noEmit` and eslint
      clean.
- [x] T014 `apps/web/app/(authenticated)/dashboard/page.tsx` REWRITTEN: role-branches on
      `user?.role_key` (matching `app-shell.tsx`'s existing convention) - admin/manager renders
      the Manager dashboard (sales-vs-forecast chart with interval band + export controls,
      top/bottom models, inventory health summary, open anomalies, unacknowledged alerts);
      sales renders the Sales dashboard (my leads ranked by score, my sales vs. target, my
      notifications); analyst links into the existing `/analytics` workbench. Hit and fixed the
      same zero-parameter openapi-fetch inference gap Phase 6 found (`error` collapses to
      `never` on both new dashboard endpoints) with the established `response.ok` workaround.
      `next build` (18 routes), eslint, `tsc --noEmit` all clean.
- [x] T015 `apps/web/app/(authenticated)/analytics/[seriesKey]/page.tsx` MODIFIED: adds the
      achieved-accuracy diagnostic (FR-073) alongside the existing fan chart, with export
      controls wired to T013. Also added `GET /forecasts/{series_key}/achieved-accuracy`
      (`routes/forecasts.py`) - a route the task breakdown missed, needed to expose the
      already-built `achieved_accuracy.py` to this page; +1 integration test in
      `test_forecast_job.py`. `next build`/eslint/`tsc --noEmit` all clean.
- [x] T016 `apps/web/app/(authenticated)/reports/page.tsx` (NEW): monthly report view with a
      month picker defaulting to the most recently completed month; nav entry added to
      `app-shell.tsx`. The picker starts empty so the server resolves the default month
      (`most_recently_completed_month`) rather than duplicating that logic client-side; once the
      response arrives the picker reflects the resolved month. Nav entry gated to admin/manager
      (reuses `dashboard:view_manager`, matching the route's own permission). `next build` (21
      routes), eslint, `tsc --noEmit` all clean.
- [x] T017 Verify SC-001 directly against the real seeded database: Manager dashboard shows real
      sales-vs-forecast, top/bottom models, inventory health, open anomalies, unacknowledged
      alerts - zero fabricated values. Confirmed via curl against a running instance: real
      per-week actual/forecast points, real top ($2.19M Audi A6) and bottom ($42K Hyundai
      Elantra) model revenue, real ABC/XYZ cell counts, 92 real aging units, 558 real open
      anomalies, 816 real unacknowledged alerts. Re-confirmed visually in-browser after login.
- [x] T018 Verify SC-002 directly against the real seeded database with two real salespeople:
      each one's Sales dashboard shows only their own leads/sales/notifications. Compared
      sales1's 28 open leads against sales2's 29 open leads programmatically - zero lead_id
      overlap. Distinct real sales totals ($820,812.22 vs $1,130,427.66); identical
      unacknowledged_alert_count (89 for both) is correct, not a leak - alerts fan out
      per-role, not per-salesperson-owned entity (Phase 6 design).
- [x] T019 Verify SC-003 directly against the real seeded database: the achieved-accuracy figure
      for a series with old-enough forecast history is a real, distinct number from the
      training-time CV metrics already shown on the leaderboard. Live system currently has
      exactly one succeeded forecast run whose entire 12-week horizon (2026-07-13..2026-09-28)
      is still in the future relative to today (2026-07-11) - genuinely no forecast anywhere in
      the system is old enough to score yet, so the API honestly returns `mase: null` rather
      than a fabricated number (confirmed via direct query: 1 succeeded run, 0 runs with any
      past week). This is the same disclosed characteristic noted in Phase 8's earlier
      development; the mechanism itself (including that it is distinct from training-time CV)
      is rigorously proven against a hand-computed fixture in T004's
      test_achieved_accuracy.py (earliest-run dedup, MASE=1.0 exact match).
- [x] T020 Verify SC-004 in a real browser: export a real chart as PNG and as CSV, confirm both
      downloads are correct. **Found and fixed a real bug during this check**: both export call
      sites used `chartRef.current?.querySelector("svg")`, which matched the first `<svg>` in
      the container - one of Recharts' own 14x14 per-legend-item icon svgs, not the chart -
      producing a near-blank 14x14 PNG. Fixed by scoping to `.recharts-wrapper > svg` (the
      chart's actual root element) on both the dashboard and analytics detail pages. Re-verified
      after the fix: dashboard PNG export is a real 1007x320 rendering of the sales-vs-forecast
      chart; dashboard CSV export contains the real per-week data matching the API response
      exactly; analytics detail page PNG (1007x360) and CSV also verified correct on a real
      series (Toyota Corolla @ Downtown Motors).
- [x] T021 Verify SC-005 directly against the real seeded database: the monthly report for a
      completed month matches an independent hand computation of sales/margin/accuracy/alerts.
      Hand-computed June 2026 revenue/margin via a direct DB query (395 delivered orders,
      summing `negotiated_price` and `negotiated_price - acquisition_cost`) - matched the API's
      `GET /reports/monthly?month=2026-06` response exactly to the cent ($9,923,870.14 revenue,
      $1,719,611.47 margin). Zero achieved-accuracy entries and zero alert counts for June were
      independently confirmed correct (the sole forecast run postdates June; every `Alert` row's
      `created_at` is 2026-07-11), not a bug.
- [x] T022 Verify SC-006 (the phase's own exit demo) in a real browser: log in as a Manager and
      as a Salesperson, confirm both dashboards render fully populated with zero manual steps
      beyond logging in. Both confirmed via screenshots: Manager dashboard (manager1@) renders
      chart + top/bottom models + inventory health + anomalies + alerts, all real; Sales
      dashboard (sales1@) renders "My dashboard" with real sales-vs-target progress bar,
      notification count, and open leads table - nav correctly shows only role-appropriate
      items in both cases.
- [x] T023 Re-verify `make bootstrap && make seed && make dev` (NFR-007) and `make ci`.
      `make bootstrap` clean. `make seed` requires a fresh volume (the generator isn't
      idempotent against already-seeded data - expected, not a regression); reset via
      `docker compose down -v && up -d` then reseeded clean, migrating through all 9 revisions
      including this phase's own `d4e5f6a7b8c9` (dashboard permissions) with no errors. `make
      dev` itself: web started cleanly on :3000; the API's uvicorn failed `Address already in
      use` on :8000 - this machine has a persistent, unrelated `edubridge_api` process
      (different project, different Postgres user, started before this phase) squatting
      that port; not something this work created or should kill. Verified the dev stack itself
      is unaffected by starting the identical `uvicorn --reload` / `next dev` commands on
      alternate ports against the just-reseeded DB: login + Manager dashboard rendered
      correctly, gracefully showing zero/empty states for jobs not yet run (no inventory/alerts/
      forecast pipeline has executed on this fresh seed) rather than erroring. `make ci`
      (lint + test + next build + api-client regeneration) passed clean: ruff/mypy/eslint/
      tsc all clean, 245 pytest tests passed, 8 vitest tests passed, `next build` (20 routes),
      and api-client regeneration against a live server produced zero diff in
      `schema.d.ts` (confirming T012's earlier regeneration is still exactly correct).
