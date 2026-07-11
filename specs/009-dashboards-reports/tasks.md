# Tasks: Dashboards & Reports

**Input**: plan.md from `specs/009-dashboards-reports/`

## Task list

- [x] T001 Alembic migration: seed `dashboard:view_manager` (admin/manager),
      `dashboard:view_sales` (admin/manager/sales) permissions — no new tables; verified via
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
      from the plan's `tests/unit/` — this needs a live DB via `get_series_actuals`, so it
      belongs alongside every other domain-layer test in `tests/integration/`, not the DB-free
      `tests/unit/`): a hand-computed 53-week fixture (the minimum for `mase()`'s season-52
      denominator to be non-empty) — two runs forecasting the same 4 weeks with different yhats
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
      own per-user scoping, leads+scores ranked by probability) plus T003/T005 — no internal HTTP
      round-trips. Sanity-checked against the real seeded database (28 real ranked open leads for
      a real salesperson, real $820,812.22 this-month sales, real top models); discovered the
      forecast/inventory/alerts/digest pipeline hadn't been re-run since Phase 7's reseed —
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
- [x] T012 Regenerate `packages/api-client` against the new endpoints — `tsc --noEmit` clean
- [ ] T013 `apps/web/lib/chart-export.ts`: `exportChartAsPng(svgElement)` (SVG→canvas→
      `toBlob`, no new dependency) and `downloadCsv(filename, rows)` (`Blob`/
      `URL.createObjectURL`) — reusable, no chart-specific coupling
- [ ] T014 `apps/web/app/(authenticated)/dashboard/page.tsx` REWRITTEN: role-branches on
      `user?.role_key` (matching `app-shell.tsx`'s existing convention) — admin/manager renders
      the Manager dashboard (sales-vs-forecast chart with interval band + export controls,
      top/bottom models, inventory health summary, open anomalies, unacknowledged alerts);
      sales renders the Sales dashboard (my leads ranked by score, my sales vs. target, my
      notifications); analyst links into the existing `/analytics` workbench
- [ ] T015 `apps/web/app/(authenticated)/analytics/[seriesKey]/page.tsx` MODIFIED: adds the
      achieved-accuracy diagnostic (FR-073) alongside the existing fan chart, with export
      controls wired to T013
- [ ] T016 `apps/web/app/(authenticated)/reports/page.tsx` (NEW): monthly report view with a
      month picker defaulting to the most recently completed month; nav entry added to
      `app-shell.tsx`
- [ ] T017 Verify SC-001 directly against the real seeded database: Manager dashboard shows real
      sales-vs-forecast, top/bottom models, inventory health, open anomalies, unacknowledged
      alerts — zero fabricated values
- [ ] T018 Verify SC-002 directly against the real seeded database with two real salespeople:
      each one's Sales dashboard shows only their own leads/sales/notifications
- [ ] T019 Verify SC-003 directly against the real seeded database: the achieved-accuracy figure
      for a series with old-enough forecast history is a real, distinct number from the
      training-time CV metrics already shown on the leaderboard
- [ ] T020 Verify SC-004 in a real browser: export a real chart as PNG and as CSV, confirm both
      downloads are correct
- [ ] T021 Verify SC-005 directly against the real seeded database: the monthly report for a
      completed month matches an independent hand computation of sales/margin/accuracy/alerts
- [ ] T022 Verify SC-006 (the phase's own exit demo) in a real browser: log in as a Manager and
      as a Salesperson, confirm both dashboards render fully populated with zero manual steps
      beyond logging in
- [ ] T023 Re-verify `make bootstrap && make seed && make dev` (NFR-007) and `make ci`
