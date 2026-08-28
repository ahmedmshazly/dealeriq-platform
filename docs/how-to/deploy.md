# How-to: deploy

**Audience:** operators.  
**Last updated:** 2026-07-17

Production topology is **EC2 (API + Postgres via Compose) + Vercel (Next.js)** with S3
backups (ADR-026).

Follow these runbooks in order:

1. [production-deploy.md](../runbooks/production-deploy.md) — host bootstrap, env, compose up,
   Vercel env
2. [durability.md](../runbooks/durability.md) — EBS bind-mount + nightly S3 backup timer
3. [rollback.md](../runbooks/rollback.md) — if a release misbehaves
4. [incident-response.md](../runbooks/incident-response.md) — outage playbooks

Local-only path remains `make bootstrap && make seed && make dev` —
[local-dev.md](../runbooks/local-dev.md).
