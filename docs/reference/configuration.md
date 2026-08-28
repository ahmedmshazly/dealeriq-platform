# Configuration reference

**Audience:** developers and operators.  
**Last updated:** 2026-07-17  
**Sources:** `.env.example`, `infra/prod.env.example`, `dealeriq_api.core.config.Settings`

Laptop-only secret stash `.deploy-secrets/` is gitignored and **not** used by Compose on EC2 —
production uses `/etc/dealeriq/prod.env`.

## Application (`Settings` / API)

| Variable | Default (dev) | Required | Environments | Notes |
|----------|---------------|----------|--------------|-------|
| `APP_ENV` | `development` | yes | all | `production` rejects insecure JWT/bootstrap defaults |
| `API_HOST` | `0.0.0.0` | no | api | Bind host |
| `API_PORT` | `8000` | no | api | |
| `LOG_LEVEL` | `INFO` | no | api | Structured JSON logs |
| `DATABASE_URL` | local psycopg URL | yes | api/alembic | Must match Postgres service |
| `CORS_ORIGINS` | `http://localhost:3000` | yes | api | Comma-separated |
| `JWT_SECRET_KEY` | insecure placeholder | **prod** | api | ≥32 chars; not the placeholder outside development |
| `JWT_KEY_ID` | `dev-1` | no | api | Key id claim |
| `ACCESS_TOKEN_TTL_MINUTES` | `15` | no | api | |
| `REFRESH_TOKEN_TTL_DAYS` | `7` | no | api | |
| `REFRESH_COOKIE_NAME` | `dealeriq_refresh` | no | api | |
| `LOCKOUT_MAX_ATTEMPTS` | `5` | no | api | |
| `LOCKOUT_WINDOW_MINUTES` | `15` | no | api | |
| `LOCKOUT_DURATION_MINUTES` | `15` | no | api | |
| `BOOTSTRAP_ADMIN_EMAIL` | `admin@dealeriq.dev` | yes | migrate | Seeded by auth migration |
| `BOOTSTRAP_ADMIN_PASSWORD` | `ChangeMe123!` | **prod** | migrate | Forbidden default outside development |
| `ORDER_APPROVAL_DISCOUNT_THRESHOLD` | `0.05` | no | api | Fraction of list price |
| `SMTP_HOST` | `localhost` | no | api | MailHog locally |
| `SMTP_PORT` | `1025` | no | api | |
| `SMTP_FROM_ADDRESS` | `alerts@dealeriq.dev` | no | api | |
| `DEFAULT_MONTHLY_SALES_TARGET` | `150000` | no | api | Sales dashboard target |
| `ENABLE_SCHEDULER` | `false` | no | api | `true` in `make dev` and prod |

## Compose Postgres / MailHog (local)

| Variable | Default | Notes |
|----------|---------|-------|
| `POSTGRES_USER` | `dealeriq` | |
| `POSTGRES_PASSWORD` | `dealeriq` | Local only |
| `POSTGRES_DB` | `dealeriq` | |
| `POSTGRES_PORT` | `5432` | Host port |
| `MAILHOG_SMTP_PORT` | `1025` | |
| `MAILHOG_UI_PORT` | `8025` | UI http://localhost:8025 |

## Production extras

| Variable | Where | Notes |
|----------|-------|-------|
| `API_HOST_PORT` | `infra/prod.env.example` | Published API port on host |
| `DEALERIQ_DATA_ROOT` | prod env | EBS mount root; default `/var/lib/dealeriq` |
| `BACKUP_S3_URI` | `/etc/dealeriq/backup.env` | e.g. `s3://bucket/prod` — not in git |
| `COMPOSE_FILE` / `COMPOSE_ENV_FILE` | backup scripts | Defaults to prod compose + `/etc/dealeriq/prod.env` |

## Web

| Variable | Default | Notes |
|----------|---------|-------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Browser-visible API origin |

## Files

- Local template: [`.env.example`](../../.env.example)
- Prod template: [`infra/prod.env.example`](../../infra/prod.env.example)
- Backup timer env: [`deploy/systemd/backup.env.example`](../../deploy/systemd/backup.env.example)
