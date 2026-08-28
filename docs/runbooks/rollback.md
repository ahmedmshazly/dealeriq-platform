# Runbook: rollback

**Audience:** operators.  
**Last updated:** 2026-07-17

## Web (Vercel)

1. Vercel → Project → Deployments → promote previous successful production deployment.
2. Confirm `NEXT_PUBLIC_API_URL` still points at the intended API.

## API image (EC2)

Compose builds `dealeriq-api:latest` from `infra/Dockerfile`.

1. Check out the last known-good git SHA on the host (or rebuild from that SHA).
2. `docker compose -f infra/docker-compose.prod.yml --env-file /etc/dealeriq/prod.env up -d --build`
3. Verify `/api/v1/health` and `/api/v1/ready`.

Prefer **forward fix** when the bad release only affects the web.

## Database migrations

Alembic migrations are **forward-only by default** in this project. Do **not** run
`alembic downgrade` in production unless you have rehearsed the downgrade on a restore of a
recent S3 backup and understand data loss risk.

If a migration is bad:

1. Stop the API (prevent new writes).
2. Restore Postgres from S3 per [durability.md](durability.md) (`DRY_RUN=1` then `CONFIRM=YES`).
3. Redeploy API at the matching schema revision.

## Feature flags

There is no general feature-flag system in v1.0. Mitigation is deploy rollback, scheduler
disable, or alert-rule disable in Admin UI.
