# Runbook: Analytics Jobs & the Alert Engine

Operational reference for the five scheduled analytics jobs and the alert-rule engine that reads
their output. For general local setup, see [`local-dev.md`](./local-dev.md) — this document
covers what happens once the stack is running.

## The five scheduled jobs

`apps/api/src/dealeriq_api/core/scheduler.py` registers five APScheduler cron jobs
(DS-OPS-001), each calling the exact same function the on-demand HTTP trigger below calls:

| Job | Schedule (server local time) | What it does |
|---|---|---|
| `forecast` | Monday 02:00 | Weekly demand forecast per (model, branch) and (segment, branch) series (Phase 4) |
| `inventory` | Daily 03:00 | ABC/XYZ classification, reorder points, survival risk, anomaly detection (Phase 5) |
| `alerts` | Daily 03:30 | Evaluates the seven alert rules against the latest `forecast`/`inventory` output (below) |
| `lead_scoring` | Daily 04:00 | RFM segmentation + calibrated lead-conversion scoring (Phase 7) |
| `digest` | Daily 07:00 | Emails each subscribed user their open-alert summary via MailHog |

Jobs are scheduled in this order deliberately: `alerts` runs after `forecast`/`inventory` so it
always sees same-day analytics output; `digest` runs last so its summary reflects the day's
alerts.

**The scheduler only starts when `ENABLE_SCHEDULER=true`.** It defaults off (see
`core/config.py`'s docstring) because a scheduled job opens its own DB session directly, which
would otherwise hit the live dev database during a test run and bypass the test suite's `get_db`
override. `make dev` is the only place that sets it — a plain `uv run uvicorn ...` (e.g. for
manual API-only testing) does **not** run the scheduler unless you export the variable yourself.

## Triggering a job on demand

Every scheduled job is also triggerable via an authenticated HTTP endpoint (`jobs:trigger`
permission — Admin/Manager), which is what the cron callbacks call internally too:

```
POST /api/v1/jobs/{job_name}/run
```

`job_name` is one of `forecast`, `inventory`, `alerts`, `digest`, `lead_scoring`. This is the
normal way to run a job outside its schedule — after a fresh reseed, to re-check a fix, or to
populate a freshly-seeded dev environment (which starts with zero forecast/inventory/alert
history until something runs a job).

**Concurrency guard (FR-072):** triggering a job that's already `running` (whether started by
cron or another manual trigger) returns `409 Conflict` rather than starting a second, colliding
run.

## Reading job status — the `AnalyticsRun` table

Every job execution — cron or manual — writes one row to `analytics_runs` before doing any real
work, and updates it when it finishes:

```
GET /api/v1/jobs/{job_name}/runs
```

returns every run for that job, newest first. Key fields:

| Field | Meaning |
|---|---|
| `status` | `running`, `succeeded`, or `failed` |
| `started_at` / `finished_at` | `finished_at` is `null` while `status="running"` |
| `metrics` | Job-specific summary on success; on failure, `metrics["error"]` holds the exception message |
| `seed` | The random seed used, for reproducibility |

**Diagnosing a stuck run:** if a row has been `status="running"` far longer than the job
normally takes, the process that was running it likely crashed or was killed without reaching
its `finally` cleanup. Check the API server's logs for the job's start time — a genuinely stuck
row does not resolve itself and will keep returning `409` on every trigger attempt for that job
name until you resolve it directly (or restart with a fresh reseed in a dev environment).

**Diagnosing a failed run:** read `metrics["error"]` on the latest `failed` row — every job
function lets its own exception propagate up to the trigger route, which is what leaves the row
`failed` rather than stuck `running`.

**A failed or missing run never corrupts what's already being served** — every route that reads
job output (dashboards, forecasts, inventory, alerts) explicitly filters to the latest
`status="succeeded"` run, so a failure just means "still serving yesterday's numbers," never a
crash or stale-but-wrong data silently presented as current.

> **Known gap (tracked in `docs/backlog.md`):** NFR-005 also calls for jobs to retry once with
> backoff on failure. That part is **not implemented** — a failed job stays `failed` until you
> either trigger it again manually or wait for its next scheduled run. Don't assume a transient
> failure self-heals.

## The alert engine

`apps/api/src/dealeriq_api/domain/alert_rules.py` evaluates seven rules, seeded by migration
into `alert_rules` (six from FR-061, plus `lead_score_drift` from FR-074):

| Rule key | Fires when | Trigger |
|---|---|---|
| `stock_reorder` | A model/branch's on-hand stock is at or below its computed reorder point | `alerts` job, reads latest `inventory` run |
| `unit_aging` | A unit has been on the lot longer than its threshold | `alerts` job |
| `sales_anomaly` | The anomaly detector flags a series (severity from its own score) | `alerts` job, reads latest `inventory` run |
| `forecast_stockout` | Forecasted demand implies a stockout within the reorder lead time | `alerts` job, reads latest `forecast` run |
| `discount_approval` | An order is submitted with a discount above `order_approval_discount_threshold` | **Synchronous** — inside `order_service.submit_order`'s own transaction, not the `alerts` job |
| `lead_idle` | A lead has had no activity for `idle_days_threshold` days (optionally gated by `score_cutoff`) | `alerts` job, reads latest `lead_scoring` run |
| `lead_score_drift` | PSI drift on a lead-scoring run's monitored features exceeds `psi_threshold` | `lead_scoring` job itself, not `alerts` |

**`discount_approval` is the one rule that fires immediately, not on the next `alerts` run** —
reusing the exact same discount-fraction comparison that already decided the order needs
Manager approval, so the alert and the approval requirement can never drift apart. This is also
what `apps/web/e2e/golden-path.spec.ts` (QA-004) exercises to get a real alert without waiting
for a scheduled job.

**Configuration:** `GET`/`PATCH /api/v1/alert-rules` (Admin/Manager, `/admin/alert-rules` in the
UI) — editing `enabled`, `severity`, or `params` (e.g. `idle_days_threshold`) is versioned and
audit-logged.

**Dedup:** every rule evaluation calls `open_alert(rule_key, dedup_key, ...)`, which is a
conditional insert — if an alert with the same `(rule_key, dedup_key)` already exists and isn't
`resolved`, nothing new is created (FR-062). This is why re-running the `alerts` job repeatedly
against unchanged data doesn't produce duplicate alerts; it's the expected, common case, not an
error.

**Notification fan-out:** each `alert_rules` row has a `subscribed_roles` param (e.g.
`discount_approval` → `["admin", "manager"]`). When an alert opens, one `Notification` row is
written per user whose role is in that list — this is what scopes `GET /api/v1/alerts` to "only
alerts I'm actually subscribed to," and what the Manager/Sales dashboards' "unacknowledged
alerts" counts read.

**Lifecycle:** `open` → `acknowledged` (`POST /alerts/{id}/acknowledge`) → `resolved`
(`POST /alerts/{id}/resolve`). Only a resolved alert is excluded from the dedup check above —
re-triggering the same condition after acknowledging (but not resolving) will not open a
duplicate.

## Verifying the daily digest via MailHog

`digest_job.py` sends one HTML email per user with open/acknowledged notifications, via stdlib
`smtplib` to the MailHog container `docker-compose.yml` already runs. To verify a real send
without checking a real inbox:

```
GET http://localhost:8025/api/v2/messages
```

(MailHog's own UI is also at `http://localhost:8025`.) Each entry is a real captured SMTP
message — check the recipient and rendered HTML body directly, the same way
`apps/api/tests/integration/test_digest_job.py` and Phase 6's own exit demo verified it. MailHog
never delivers anywhere external; it's a local-only SMTP capture tool (Principle II — zero paid
services).
