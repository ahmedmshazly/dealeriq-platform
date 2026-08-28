# infra

Everything needed to run DealerIQ's local infrastructure and produce its synthetic dataset - no
paid services, nothing that requires an account (Principle II).

## `docker-compose.yml`

Two services, both free/open-source, brought up by `make dev` or `make seed`:

- **`postgres`** (Postgres 16) - the single database for both transactional and analytics
  tables (DAT-003's boundary is enforced in code, not by separate databases). Healthcheck-gated
  so `make seed`'s migration step never races a not-yet-ready server.
- **`mailhog`** - local SMTP capture for the daily alert digest (FR-064). Nothing sent through
  it ever leaves the machine; its web UI and API are at `http://localhost:8025` (SMTP on
  `:1025`). See [`../docs/runbooks/jobs-and-alerts.md`](../docs/runbooks/jobs-and-alerts.md) for
  how to verify a real digest send against it.

Both expose their ports as environment-overridable (`POSTGRES_PORT`, `MAILHOG_SMTP_PORT`,
`MAILHOG_UI_PORT`, ...) - see `.env.example` at the repo root. Data lives in the named
`pgdata` volume; `docker compose -f infra/docker-compose.yml down -v` (or `make down` plus a
manual `-v`) resets it to empty for a from-scratch reseed.

## `Dockerfile`

Production API image (FastAPI + analytics workspace). Build context is the **repo root**:

```bash
docker build -f infra/Dockerfile -t dealeriq-api .
# or via compose:
docker compose -f infra/docker-compose.prod.yml --env-file /etc/dealeriq/prod.env build
```

## `docker-compose.prod.yml`

Production-only stack (API + Postgres, no MailHog). Postgres data is bind-mounted from
`${DEALERIQ_DATA_ROOT:-/var/lib/dealeriq}/pgdata` on a durable EBS volume (ADR-026) - see
[`../docs/runbooks/durability.md`](../docs/runbooks/durability.md). Do not use this file for
local `make dev`.

## `seed/`

The synthetic data generator (GEN-001..006) and its committed ground-truth artifacts. See
[`seed/README.md`](./seed/README.md) for what it generates and how reproducibility works.

## `scripts/`

`ensure-gitleaks.sh` - fetches a pinned gitleaks binary into `.tools/bin/` on `make bootstrap`,
without assuming `apt`/`sudo`/a Go toolchain is available on the dev machine or CI runner
(NFR-007's "works on a clean clone" requirement).

## Full walkthrough

For the actual bootstrap → seed → dev command sequence, see
[`../docs/runbooks/local-dev.md`](../docs/runbooks/local-dev.md) - this file only documents
what's under `infra/` itself, not how to run it end-to-end.
