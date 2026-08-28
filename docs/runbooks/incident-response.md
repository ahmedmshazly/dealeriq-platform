# Runbook: incident response

**Audience:** on-call / operators.  
**Last updated:** 2026-07-17

## Severity quick guide

| Level | Examples | First actions |
|-------|----------|---------------|
| SEV-1 | API unreachable, data loss risk | Check EC2/Docker, restore readiness, communicate |
| SEV-2 | Web blank but API up; auth outage | Vercel status, CORS, JWT secret mismatch |
| SEV-3 | Single job failing; email digest quiet | Logs, re-trigger job, MailHog/SMTP |

## API down (EC2)

1. SSH to host; `docker compose -f infra/docker-compose.prod.yml --env-file /etc/dealeriq/prod.env ps`
2. `docker compose ... logs api --tail=200`
3. Health: `curl -sf http://127.0.0.1:8000/api/v1/health`
4. If Postgres unhealthy: check EBS mount (`DEALERIQ_DATA_ROOT`), disk space
5. Restart: `docker compose ... up -d --build`
6. If data corruption suspected: **stop writes**, follow [durability.md](durability.md) restore
   with `DRY_RUN=1` first

## Web down (Vercel)

1. Confirm API health from your network / CORS origin
2. Check Vercel deployment status and `NEXT_PUBLIC_API_URL`
3. Rollback via Vercel dashboard (see [rollback.md](rollback.md))

## Auth failures after deploy

1. Confirm `JWT_SECRET_KEY` / `JWT_KEY_ID` unchanged unless intentional rotation
2. Confirm `CORS_ORIGINS` includes the exact Vercel URL
3. Cookie issues: SameSite/HTTPS requirements on production domains

## Bad analytics / alert storm

1. Disable scheduler temporarily (`ENABLE_SCHEDULER=false` + recreate API container) if needed
2. Inspect latest `analytics_runs` / alerts tables
3. Fix rule params in Admin alert-rules UI
4. Re-enable scheduler

## Communications

Record start time, impact, mitigating steps, and follow-up issues. Link ADR/runbook updates if
process gaps appear.
