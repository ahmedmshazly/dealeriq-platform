# Implementation Plan: Alerts & Notifications

**Branch**: `007-alerts-notifications` | **Date**: 2026-07-10 | **Spec**: `specs/007-alerts-notifications/spec.md`

## Summary

An alert-rule evaluation domain service (`apps/api`, not `packages/analytics` - see spec.md's
Assumptions on why this is a DB-reading business-rule layer, not statistical computation) that
runs the six FR-061 rules against Phase 4/5's already-persisted outputs plus one transactional
trigger on order submission; a notification-center API/UI for the in-app surface; a daily digest
job rendering HTML email to the existing MailHog container; an admin UI for rule-parameter
configuration; and APScheduler's first real cron activation (forecast weekly, inventory daily,
digest daily), each schedule entry also triggerable on demand via the existing
`POST /jobs/{name}/run` pattern.

## Technical Context

**Language/Version**: Python 3.12 (`apps/api`), TypeScript/Next.js 15 (`apps/web`) - unchanged.

**Primary Dependencies**: none new for the backend - `smtplib`/`email.mime` (Python stdlib)
render and send the digest, avoiding a templating-library dependency (Jinja2) for what's a
short, single HTML template; `apscheduler` is already present (ADR-004) but only now gets real
`add_job(..., trigger="cron", ...)` registrations instead of just a job-name registry entry.

**Storage**: PostgreSQL 16, three new tables (`alert_rules`, `alerts`, `notifications`) per one
new Alembic migration, per SRS §7's schema verbatim; `alert_rules` seeded with the six built-in
rules and DS-OPS-001's stated default parameters at migration time.

**Testing**: pytest (rule-evaluation logic against hand-constructed DB fixtures for each of the
six conditions, dedup-key non-duplication, lifecycle transitions), testcontainers-python for
integration tests (ADR-013) including a real SMTP round-trip verified against MailHog's own HTTP
API (`GET /api/v2/messages`) rather than mocking the send.

**Target Platform**: unchanged - Docker Compose local dev, single-instance; MailHog
(`infra/docker-compose.yml`) already running for local email capture.

**Project Type**: Web application (existing `apps/api` + `apps/web` + `packages/analytics`
monorepo) - no new top-level project.

**Performance Goals**: rule evaluation over the full seeded dataset (81 Phase 4/5 series, ~15k
orders, ~15k units, 6000 leads) completes in low single-digit seconds - six straightforward
threshold comparisons over already-indexed tables, nothing resembling Phase 4/5's statistical
compute cost.

**Constraints**: NFR-007's 15-minute `make bootstrap && make seed && make dev` budget is
unaffected (alert evaluation and the digest are on-demand/scheduled, not part of bootstrap/seed).
Rule (e)'s evaluation must add negligible latency to the order-submission request (a handful of
indexed queries, no external calls beyond the DB itself).

**Scale/Scope**: six built-in rules, three new tables, ~6 new API endpoints (rules CRUD +
notification center + acknowledge/resolve), two new frontend surfaces (notification center,
admin rule-config page), one new scheduled job registration set (three cron entries).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I (Monorepo & Stack Discipline)**: alert-rule logic lives in `apps/api`'s domain
  layer (a genuine architectural deviation from Phase 4/5's `packages/analytics` placement,
  reasoned and disclosed in spec.md's Assumptions - this is DB-reading business logic, not
  statistical computation); no new top-level package; no new dependencies (stdlib `smtplib`
  only).
- **Principle II (Free, Local-First, Zero Paid Services)**: MailHog (already running) captures
  the digest locally; no third-party email API introduced.
- **Principle III (Security & RBAC by Default)**: `alerts:view`/`alerts:manage` (acknowledge/
  resolve) and `alert-rules:manage` (FR-065's admin config) are new, deny-by-default permission
  keys granted per the SRS role table's intent for an ops/admin-facing feature.
- **Principle IV (Migrations & Append-Only Integrity)**: `alerts`/`notifications` are
  transactional-adjacent operational tables (not analytics tables like Phase 4/5's - they're
  mutated by application code as alerts move through their lifecycle, which is correct and
  expected, not a DAT-003 violation, since DAT-003 is specifically about analytics-vs-
  transactional separation and alerts are neither: they're an operational/notification concern).
  `alert_rules` changes are versioned (FR-065) and audit-logged via the existing `audit_log`
  table, not a new bespoke history mechanism.
- **Principle V (Analytics Reproducibility & Scientific Integrity)**: not applicable to rule
  evaluation itself (no statistical/ML computation here); DS-OPS-002/003 (idempotency, seed
  recording) are already satisfied by Phase 4/5's `AnalyticsRun` lifecycle, which this phase's
  scheduled jobs continue to use unchanged.
- **Principle VII (Testing bar)**: each of the six rules gets a hand-constructed DB-fixture test
  proving it fires exactly when its condition holds and not otherwise, plus a real (not mocked)
  MailHog SMTP round-trip test for the digest.
- **No violations requiring Complexity Tracking.**

## Project Structure

### Documentation (this feature)

```text
specs/007-alerts-notifications/
├── plan.md              # this file
└── tasks.md              # Phase 2 output
```

### Source code

```text
apps/api/src/dealeriq_api/
├── domain/models/
│   └── alerts.py                  # AlertRule, Alert, Notification SQLAlchemy models
├── domain/
│   ├── alert_rules.py              # the six rule-evaluation functions, each reading its
│   │                                # own slice of already-persisted data; open_alert(...)
│   │                                # shared helper enforcing the dedup-key-no-duplicate-open
│   │                                # invariant (FR-062) via a conditional insert
│   ├── alert_job.py                 # orchestration: run all analytics-run-triggered rules
│   │                                # (a)-(d), (f) after forecast/inventory jobs; reuses
│   │                                # AnalyticsRun for its own run-tracking row
│   ├── digest_job.py                 # queries open/new alerts per subscribed user, renders
│   │                                 # HTML, sends via smtplib to MailHog
│   └── order_service.py               # MODIFIED: submit_order calls alert_rules.evaluate_rule_e
│                                       # inline when status -> PENDING_APPROVAL (FR-060's
│                                       # transactional trigger case)
├── jobs/
│   ├── alerts.py                      # job_name="alerts" registry entry (mirrors forecast/
│   │                                   # inventory's exact pattern)
│   └── digest.py                       # job_name="digest" registry entry
├── core/
│   └── scheduler.py                    # NEW: APScheduler BackgroundScheduler instance,
│                                        # started in main.py's lifespan, registers
│                                        # forecast/inventory/alerts/digest on DS-OPS-001's
│                                        # cron schedule (each still individually triggerable
│                                        # via the existing POST /jobs/{name}/run)
├── routes/
│   ├── alerts.py                       # GET /alerts (notification center list + badge
│   │                                   # count), POST /alerts/{id}/acknowledge,
│   │                                   # POST /alerts/{id}/resolve
│   └── alert_rules.py                   # GET/PATCH /alert-rules (FR-065 admin config)
└── schemas/
    └── alerts.py

apps/api/tests/integration/
├── test_alert_rules.py                  # each of the six rules against hand-constructed
│                                         # fixtures; dedup-key non-duplication; rule (e)'s
│                                         # synchronous firing on order submission
└── test_digest_job.py                    # real SMTP send verified against MailHog's
                                           # GET /api/v2/messages HTTP API

apps/api/alembic/versions/
└── <rev>_alerts_notifications.py         # alert_rules, alerts, notifications tables +
                                           # indices; seeds the six built-in alert_rules rows;
                                           # new permissions (alerts:view, alerts:manage,
                                           # alert-rules:manage)

apps/web/app/(authenticated)/
├── alerts/page.tsx                       # notification center: badge count, filterable
│                                         # list, acknowledge/resolve actions
└── admin/alert-rules/page.tsx             # FR-065: edit thresholds/schedule/subscriptions
```

**Structure Decision**: extends the existing three-package monorepo - no new top-level
directories. Unlike Phase 4/5, no new `packages/analytics` module: alert-rule evaluation is
DB-reading business logic (see Constitution Check), so it lives alongside `order_service.py`/
`inventory_service.py` in `apps/api`'s domain layer.

## The six rules (FR-061), each as an independent, testable function

- **(a) stock at/below reorder point**: for each `inventory_intel` row with a non-null
  `reorder_point`, on-hand = count of `vehicle_units` with `status IN (in_stock, reserved)` for
  that `(model_id, branch_id)`; fires when on-hand ≤ `reorder_point`.
- **(b) vehicle aging beyond threshold**: for each `unit_risk` row where `is_aging=true` (Phase
  5 already computed this), fires directly - no new threshold logic, just surfacing Phase 5's
  own flag as an alert.
- **(c) sales anomaly detected**: for each `anomalies` row with `status='new'`, fires with
  severity mapped from the anomaly's own `severity` float (DS-ANO-004's explicit hand-off to
  this rule) - not a second, independently-invented severity scale.
- **(d) forecast indicates stockout within lead time**: for each `(model, branch)` with a
  succeeded Phase 4 forecast, fires when on-hand < the sum of the champion forecast's point
  estimate (`yhat`, not the quantile used for reorder points) over the configured lead-time
  window - a distinct, more urgent signal than (a): even *expected* demand would exhaust current
  stock, not just a dip below the safety-stock-driven reorder point.
- **(e) order discount above approval threshold submitted**: evaluated inline in
  `order_service.submit_order`, not by a scheduled job - fires the instant `fraction >
  settings.order_approval_discount_threshold` (the exact same comparison that sets
  `PENDING_APPROVAL`), inside the same transaction and commit.
- **(f) lead idle > N days**: for each `lead` not in a terminal status (`won`/`lost`), fires when
  `now - last_activity_at` exceeds the configured idle-days threshold. Score-cutoff condition
  deferred to Phase 7 (spec.md Assumptions) - the rule's `params` JSON already has a placeholder
  key for it, so Phase 7 only adds a filter clause, never touches the dedup-key or lifecycle
  machinery.

Every rule shares one `open_alert(rule_key, dedup_key, severity, payload)` helper: a conditional
insert (check no existing row with `rule_key + dedup_key` and `status != 'resolved'` before
inserting) inside the same transaction - the same atomicity pattern Phase 4's FR-072 concurrency
guard already established, reused here for FR-062's "no duplicate open alert" invariant.

## Alert lifecycle & notification fan-out (FR-062, FR-063)

`alerts.status`: `open` → `acknowledged` → `resolved` (enum, `native_enum=False` per the
project's existing convention). `POST /alerts/{id}/acknowledge` and `.../resolve` both write
`acknowledged_by`/`resolved_at`-equivalent fields and reuse `write_audit_row` (the exact same
audit helper `order_service.py` already calls) - no new audit mechanism.

On each `open_alert(...)` call, one `notifications` row is created per user subscribed to that
rule (role-based subscription this phase - a user's role determines which rules they see,
matching FR-063's "delivered per role/subscription" without needing a separate subscription-
management UI beyond what FR-065's admin config already covers). `GET /alerts` joins
`notifications` for the current user to compute the badge count and the filterable list.

## Digest email (FR-064)

`digest_job.py` queries, per user with at least one open or newly-created-since-last-digest
`notifications` row, builds a plain HTML summary (stdlib string templating - the content is a
simple list of alert lines, not complex enough to justify a templating-library dependency), and
sends via `smtplib.SMTP(host, port)` to the MailHog container's SMTP listener (port 1025).
Verified in tests by querying MailHog's own `GET /api/v2/messages` HTTP API (port 8025) - a real
end-to-end send, not a mocked `smtplib.SMTP`.

## Scheduler activation (DS-OPS-001)

`core/scheduler.py` instantiates one `BackgroundScheduler`, started in `main.py`'s FastAPI
lifespan context manager, with `add_job(run_forecast_job, trigger="cron", day_of_week="mon",
hour=2)`, `add_job(run_inventory_job, trigger="cron", hour=3)` (inventory intelligence +
anomaly detection combined, per spec.md's Assumption), `add_job(run_alert_job, trigger="cron",
hour=3, minute=30)`, `add_job(run_digest_job, trigger="cron", hour=7)`. Every job function is
identical to the one `POST /jobs/{name}/run` already calls - a cron firing and an HTTP trigger
are the same function call, just from a different caller, so DS-OPS-002's idempotency guarantee
covers both uniformly.

## Validation sequence (proves the phase works end-to-end)

1. Seed hand-constructed fixtures for each of the six conditions; run the alert job; confirm
   exactly one open alert per condition with the correct rule key, dedup key, and severity
   (SC-001).
2. Submit a high-discount order via the API; confirm rule (e)'s alert exists in the same request:
   no polling, no delay (SC-002).
3. Open the notification center in a real browser; confirm the badge count and filtered list
   render real alerts; acknowledge one and confirm its lifecycle/audit trail (SC-003, SC-004).
4. Run the digest job against seeded alerts; query MailHog's API directly; confirm one HTML
   email per subscribed user with ≥1 alert, zero for users with none (SC-005).
5. Full exit demo: trigger forecast → inventory → alerts → digest in sequence (either via the
   scheduler firing or the on-demand endpoints); confirm the whole chain produces a real email in
   MailHog with zero manual steps beyond the initial triggers (SC-006).
