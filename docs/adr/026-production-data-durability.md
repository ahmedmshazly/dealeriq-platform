# ADR-026: Production data durability — EBS bind-mount + S3 backups

- Status: Accepted
- Date: 2026-07-16
- Requirement refs: ADR-003 (Postgres), ops / Stage-2 hosting
- Supplements: ADR-003

## Context

Production runs Postgres inside `infra/docker-compose.prod.yml` on a single EC2
host. A Docker named volume on the instance root disk is lost if the instance is
terminated (`DeleteOnTermination=true` by default) or if an operator runs
`docker compose down -v`. There were no off-box backup scripts.

ADR-003 noted a future swap to managed free-tier Postgres (Neon/Supabase). For
the current showcase host we keep Compose Postgres and make the data survive
instance replace without that migration.

The API stores no uploads/blobs on local disk — durability is Postgres-only.

## Decision

1. **Runtime unchanged:** Compose `postgres` remains the live store (ADR-003).
2. **Production hosts** bind-mount
   `${DEALERIQ_DATA_ROOT:-/var/lib/dealeriq}/pgdata` from a **dedicated EBS
   volume** with **DeleteOnTermination = false**.
3. **Off-box recovery:** nightly `scripts/backup-to-s3.sh` uploads a custom-format
   `pg_dump` (+ sha256 manifest) to a versioned S3 bucket, authenticated by an
   **EC2 instance IAM role**. Restore via `scripts/restore-from-s3.sh`
   (`DRY_RUN=1` / `CONFIRM=YES`).
4. **Dev/CI** keep named volumes in `infra/docker-compose.yml` alone (`make dev`
   unchanged).

## Alternatives considered

- **Amazon RDS / Neon / Supabase** — managed backups/PITR; deferred. Revisit if
  backup ops become a burden or horizontal scale requires it. Would supersede
  Compose Postgres.
- **EBS snapshots alone** — useful defense-in-depth but slower/less portable than
  logical dumps; optional owner add-on, not the primary documented path.

## Consequences

- Prod bring-up still uses `infra/docker-compose.prod.yml`; operators must
  provision EBS + S3 + IAM once (`docs/runbooks/durability.md`).
- Terminating EC2 keeps the data volume; if the volume is also lost, restore
  from S3.
- ADR-003's "Stage-2 = managed Postgres" consequence is deferred, not revoked —
  this ADR is the interim ops path for the single-EC2 showcase.
