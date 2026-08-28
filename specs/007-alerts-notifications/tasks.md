# Tasks: Alerts & Notifications

**Input**: plan.md from `specs/007-alerts-notifications/`

## Task list

- [x] T001 `apps/api/src/dealeriq_api/domain/models/alerts.py`: `AlertRule`, `Alert`,
      `Notification` SQLAlchemy models (schema per SRS §7 verbatim column names); `AlertStatus`
      enum (open/acknowledged/resolved, `native_enum=False` per project convention)
- [x] T002 Alembic migration: `alert_rules`, `alerts`, `notifications` tables + indices
      (`alerts(status, dedup_key)` per DAT-004); seeds the six built-in `alert_rules` rows with
      DS-OPS-001's default parameters; new permissions `alerts:view`, `alerts:manage`,
      `alert-rules:manage` granted per the SRS role table's intent
- [x] T003 `domain/alert_rules.py`: shared `open_alert(rule_key, dedup_key, severity, payload)`
      helper - conditional insert enforcing "no duplicate open alert for the same dedup key"
      (FR-062) inside the same transaction, mirroring FR-072's concurrency-guard pattern; creates
      one `notifications` row per role-subscribed user on each successful open
- [x] T004 `domain/alert_rules.py`: rule (a) stock at/below reorder point - on-hand count from
      `vehicle_units` (in_stock/reserved) vs `inventory_intel.reorder_point`
- [x] T005 `domain/alert_rules.py`: rule (b) vehicle aging beyond threshold - surfaces Phase 5's
      `unit_risk.is_aging` flag directly, one alert per aging unit
- [x] T006 `domain/alert_rules.py`: rule (c) sales anomaly detected - one alert per `status='new'`
      `anomalies` row, severity mapped from DS-ANO's own severity score (DS-ANO-004)
- [x] T007 `domain/alert_rules.py`: rule (d) forecast indicates stockout within lead time -
      on-hand vs the champion forecast's point-estimate sum over the lead-time window (distinct
      from rule (a)'s quantile-based reorder point)
- [x] T008 `domain/alert_rules.py`: rule (f) lead idle > N days - `now - last_activity_at` vs
      configured threshold, excluding won/lost leads; `params` JSON carries a placeholder key for
      Phase 7's score-cutoff addition, not wired yet
- [x] T009 Unit/integration tests: each of rules (a), (b), (c), (d), (f) against a
      hand-constructed DB fixture - fires exactly when its condition holds, never otherwise;
      dedup-key non-duplication (same condition detected twice never opens a second open alert)
- [x] T010 `domain/order_service.py`: MODIFIED - `submit_order` calls rule (e)'s evaluation
      inline when status transitions to `PENDING_APPROVAL`, reusing
      `settings.order_approval_discount_threshold` (the same comparison that already decides
      the approval requirement), inside the same transaction/commit (FR-060's transactional
      trigger case)
- [x] T011 Integration test: submitting a high-discount order opens rule (e)'s alert
      synchronously in the same request (SC-002); a low-discount order opens none
- [x] T012 `domain/alert_job.py`: orchestration - runs rules (a)-(d) and (f) after Phase 4/5's
      analytics runs, creates its own `AnalyticsRun` row (`job_name="alerts"`) for run-tracking,
      skips evaluation entirely if the triggering analytics run itself failed (DS-OPS-002)
- [x] T013 `apps/api/src/dealeriq_api/routes/alerts.py` +
      `apps/api/src/dealeriq_api/schemas/alerts.py`: `GET /alerts` (badge count + filterable
      list, scoped to the current user's role-subscriptions), `POST /alerts/{id}/acknowledge`,
      `POST /alerts/{id}/resolve` - both write actor/timestamp and an audit-log row via the
      existing `write_audit_row` helper
- [x] T014 Integration tests: acknowledge/resolve correctly transition the lifecycle, record the
      actor, and write an audit row; an already-resolved alert can't be re-acknowledged
- [x] T015 `domain/digest_job.py`: queries per-user open/new notifications, renders a plain HTML
      summary (stdlib string templating, no new dependency), sends via `smtplib` to MailHog's
      SMTP listener; zero email for a user with no open/new alerts (FR-064)
- [x] T016 Integration test: run the digest job against seeded alerts, query MailHog's own
      `GET /api/v2/messages` HTTP API directly (real send, not a mocked `smtplib.SMTP`) - one
      email per subscribed user with ≥1 alert, none for users with zero
- [x] T017 `apps/api/src/dealeriq_api/routes/alert_rules.py` +
      corresponding schemas: `GET /alert-rules`, `PATCH /alert-rules/{key}` (FR-065) - Manager/
      Admin only, versions the row and writes an audit-log entry on every change
- [x] T018 Integration test: editing a rule's threshold via `PATCH /alert-rules/{key}` is
      versioned, audit-logged, and the next rule evaluation uses the new parameter
- [x] T019 `apps/api/src/dealeriq_api/jobs/alerts.py` + `jobs/digest.py`: job registry entries
      (`job_name="alerts"`, `job_name="digest"`), added to `routes/jobs.py`'s `KNOWN_JOBS`
      (mirrors forecast/inventory's exact pattern - no new route code needed)
- [x] T020 `apps/api/src/dealeriq_api/core/scheduler.py`: `BackgroundScheduler` instance,
      started in `main.py`'s FastAPI lifespan; registers forecast (weekly Mon 02:00), inventory
      (daily 03:00 - intelligence + anomaly detection combined per spec.md's Assumption), alerts
      (daily 03:30), digest (daily 07:00) on DS-OPS-001's schedule, each calling the exact same
      function `POST /jobs/{name}/run` already calls
- [x] T021 Regenerate `packages/api-client` against the new endpoints
- [x] T022 `apps/web/app/(authenticated)/alerts/page.tsx`: notification center - badge count,
      filterable list (by rule/severity/status), acknowledge/resolve actions, consuming only the
      generated client
- [x] T023 `apps/web/app/(authenticated)/admin/alert-rules/page.tsx`: FR-065 admin config -
      edit thresholds/schedule/subscriptions per rule
- [x] T024 App-shell nav: add an Alerts entry (with live badge count) gated on `alerts:view`,
      and an Alert Rules entry under the admin section gated on `alert-rules:manage`
- [x] T025 Verify SC-001 directly against the real seeded database: manufacture at least one
      real instance of each rule's condition (or confirm one already exists in the seeded data),
      run the alert job, confirm exactly one open alert per condition with the right severity
- [x] T026 Verify SC-006 (the phase's own exit demo) end-to-end: trigger forecast → inventory →
      alerts → digest in sequence, confirm a real email appears in MailHog with zero manual
      steps beyond the initial triggers
- [x] T027 Verify SC-003/SC-004 in a real browser: open the notification center, confirm badge
      count and list render real data, acknowledge and resolve at least one alert
- [x] T028 Re-verify `make bootstrap && make seed && make dev` (NFR-007) and `make ci`
