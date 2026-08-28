# How-to: trigger analytics jobs

**Audience:** Admins / operators verifying pipelines.  
**Last updated:** 2026-07-17

Scheduled jobs run when `ENABLE_SCHEDULER=true` (set by `make dev` and production). Every job
is also triggerable on demand (constitution Principle V, FR-072).

## Via HTTP

Requires permission `jobs:trigger` (Admin).

```bash
# After login, use the access token from /api/v1/auth/login
curl -X POST "http://localhost:8000/api/v1/jobs/forecast/run" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

Known job names (see `dealeriq_api/jobs/` registry): `forecast`, `inventory`, `alerts`,
`digest`, `lead_scoring` (exact keys match `JOB_NAME` constants).

List recent runs with `jobs:view`:

```bash
curl "http://localhost:8000/api/v1/jobs/runs" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

## Concurrency

A second run of the same job while one is `RUNNING` is rejected (concurrency guard in
`domain/jobs/job_lifecycle.py`).

## Local verification of digests / alerts

See [runbooks/jobs-and-alerts.md](../runbooks/jobs-and-alerts.md) (MailHog at
http://localhost:8025).
