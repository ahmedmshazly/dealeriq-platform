#!/usr/bin/env bash
# Restore Compose Postgres from an S3 backup (ADR-026).
#
# Required env:
#   BACKUP_S3_URI   e.g. s3://dealeriq-prod-backups/prod
# Optional env:
#   BACKUP_DAY            YYYY-MM-DD (default: contents of …/postgres/LATEST)
#   DEALERIQ_DATA_ROOT    default /var/lib/dealeriq
#   COMPOSE_FILE          default infra/docker-compose.prod.yml
#   COMPOSE_ENV_FILE      default /etc/dealeriq/prod.env
#   POSTGRES_USER / POSTGRES_DB
#   DRY_RUN=1             download + verify only; do not mutate local data
#   CONFIRM=YES           required unless DRY_RUN=1 (destructive restore)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"

: "${BACKUP_S3_URI:?BACKUP_S3_URI is required (e.g. s3://dealeriq-prod-backups/prod)}"

DEALERIQ_DATA_ROOT="${DEALERIQ_DATA_ROOT:-/var/lib/dealeriq}"
POSTGRES_USER="${POSTGRES_USER:-dealeriq}"
POSTGRES_DB="${POSTGRES_DB:-dealeriq}"
export COMPOSE_FILE="${COMPOSE_FILE:-infra/docker-compose.prod.yml}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-/etc/dealeriq/prod.env}"
DRY_RUN="${DRY_RUN:-0}"
CONFIRM="${CONFIRM:-}"

compose() {
  if [[ -f "${COMPOSE_ENV_FILE}" ]]; then
    docker compose --env-file "${COMPOSE_ENV_FILE}" "$@"
  else
    docker compose "$@"
  fi
}

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "FAIL: required command not found: $1" >&2
    exit 1
  }
}
need docker
need aws
need sha256sum

WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/dealeriq-restore.XXXXXX")"
cleanup() { rm -rf "${WORKDIR}"; }
trap cleanup EXIT

if [[ -z "${BACKUP_DAY:-}" ]]; then
  BACKUP_DAY="$(aws s3 cp "${BACKUP_S3_URI%/}/postgres/LATEST" - 2>/dev/null | tr -d '[:space:]' || true)"
fi
if [[ -z "${BACKUP_DAY}" ]]; then
  echo "FAIL: set BACKUP_DAY=YYYY-MM-DD or ensure ${BACKUP_S3_URI%/}/postgres/LATEST exists" >&2
  exit 1
fi

S3_PREFIX="${BACKUP_S3_URI%/}/postgres/${BACKUP_DAY}"
DUMP_PATH="${WORKDIR}/dealeriq.dump"
MANIFEST_PATH="${WORKDIR}/manifest.json"

echo "restore: day=${BACKUP_DAY} from ${S3_PREFIX}"

aws s3 cp "${S3_PREFIX}/dealeriq.dump" "${DUMP_PATH}" --only-show-errors
aws s3 cp "${S3_PREFIX}/manifest.json" "${MANIFEST_PATH}" --only-show-errors

EXPECTED_SHA="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["dump_sha256"])' "${MANIFEST_PATH}")"
ACTUAL_SHA="$(sha256sum "${DUMP_PATH}" | awk '{print $1}')"
if [[ "${EXPECTED_SHA}" != "${ACTUAL_SHA}" ]]; then
  echo "FAIL: dump sha256 mismatch expected=${EXPECTED_SHA} actual=${ACTUAL_SHA}" >&2
  exit 1
fi
echo "restore: dump sha256 ok (${ACTUAL_SHA})"

if [[ "${DRY_RUN}" == "1" ]]; then
  echo "DRY_RUN: would stop api, pg_restore into ${POSTGRES_DB}"
  echo "DRY_RUN: manifest:"
  cat "${MANIFEST_PATH}"
  exit 0
fi

if [[ "${CONFIRM}" != "YES" ]]; then
  echo "FAIL: restore is destructive. Re-run with CONFIRM=YES (or DRY_RUN=1)." >&2
  exit 1
fi

echo "restore: stop api (keep postgres up for pg_restore)"
compose stop api

echo "restore: drop & recreate database ${POSTGRES_DB}"
# Terminate other connections, then recreate. Superuser inside the container is POSTGRES_USER.
compose exec -T postgres \
  psql -U "${POSTGRES_USER}" -d postgres -v ON_ERROR_STOP=1 <<SQL
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '${POSTGRES_DB}' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS ${POSTGRES_DB};
CREATE DATABASE ${POSTGRES_DB} OWNER ${POSTGRES_USER};
SQL

echo "restore: pg_restore"
# Copy into the container — pg_restore needs a seekable file path, not only stdin.
compose cp "${DUMP_PATH}" "postgres:/tmp/dealeriq.dump"
compose exec -T postgres \
  pg_restore -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" --no-owner --no-acl \
  /tmp/dealeriq.dump
compose exec -T postgres rm -f /tmp/dealeriq.dump

echo "restore: start api (entrypoint runs alembic upgrade head)"
compose up -d api

echo "restore: ok day=${BACKUP_DAY} data_root=${DEALERIQ_DATA_ROOT}"
