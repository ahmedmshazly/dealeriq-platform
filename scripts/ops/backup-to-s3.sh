#!/usr/bin/env bash
# Off-box backup of Compose Postgres to S3 (ADR-026).
# Intended for the production EC2 host (systemd timer or manual). Exits non-zero
# on any failure so the timer unit can surface a failed run.
#
# Required env:
#   BACKUP_S3_URI   e.g. s3://dealeriq-prod-backups/prod
# Optional env:
#   DEALERIQ_DATA_ROOT   default /var/lib/dealeriq
#   COMPOSE_FILE         default infra/docker-compose.prod.yml
#   COMPOSE_ENV_FILE     default /etc/dealeriq/prod.env (passed as --env-file if present)
#   POSTGRES_USER / POSTGRES_DB  (match prod.env; defaults dealeriq)
#   DRY_RUN=1            print actions without uploading
#
# Auth: prefer an EC2 instance IAM role. Do not put long-lived AWS keys in git.
# Blobs: the API stores no uploads on disk - DB-only backup is sufficient.
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

compose() {
  if [[ -f "${COMPOSE_ENV_FILE}" ]]; then
    docker compose --env-file "${COMPOSE_ENV_FILE}" "$@"
  else
    docker compose "$@"
  fi
}

STAMP="$(date -u +%Y-%m-%dT%H%M%SZ)"
DAY="$(date -u +%Y-%m-%d)"
WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/dealeriq-backup.XXXXXX")"
cleanup() { rm -rf "${WORKDIR}"; }
trap cleanup EXIT

DUMP_PATH="${WORKDIR}/dealeriq.dump"
MANIFEST_PATH="${WORKDIR}/manifest.json"
S3_PREFIX="${BACKUP_S3_URI%/}/postgres/${DAY}"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "FAIL: required command not found: $1" >&2
    exit 1
  }
}
need docker
need aws
need sha256sum
need hostname

echo "backup: compose=${COMPOSE_FILE} data_root=${DEALERIQ_DATA_ROOT} → ${BACKUP_S3_URI}"

if ! compose ps --status running --services 2>/dev/null | grep -qx postgres; then
  echo "FAIL: postgres service is not running (compose file: ${COMPOSE_FILE})" >&2
  compose ps >&2 || true
  exit 1
fi

echo "backup: pg_dump -Fc ..."
compose exec -T postgres \
  pg_dump -U "${POSTGRES_USER}" -Fc --no-owner --no-acl "${POSTGRES_DB}" \
  >"${DUMP_PATH}"

DUMP_SHA="$(sha256sum "${DUMP_PATH}" | awk '{print $1}')"
DUMP_BYTES="$(wc -c <"${DUMP_PATH}" | tr -d ' ')"

HOSTNAME_VAL="$(hostname -f 2>/dev/null || hostname)"
cat >"${MANIFEST_PATH}" <<EOF
{
  "schema_version": 1,
  "created_at": "${STAMP}",
  "hostname": "${HOSTNAME_VAL}",
  "compose_file": "${COMPOSE_FILE}",
  "postgres_db": "${POSTGRES_DB}",
  "dump_format": "custom",
  "dump_sha256": "${DUMP_SHA}",
  "dump_bytes": ${DUMP_BYTES},
  "dealeriq_data_root": "${DEALERIQ_DATA_ROOT}",
  "s3_postgres_prefix": "${S3_PREFIX}"
}
EOF

if [[ "${DRY_RUN}" == "1" ]]; then
  echo "DRY_RUN: would upload ${DUMP_PATH} (${DUMP_BYTES} bytes, sha256=${DUMP_SHA})"
  echo "DRY_RUN: would upload ${MANIFEST_PATH}"
  cat "${MANIFEST_PATH}"
  exit 0
fi

echo "backup: upload dump + manifest → ${S3_PREFIX}/"
aws s3 cp "${DUMP_PATH}" "${S3_PREFIX}/dealeriq.dump" --only-show-errors
aws s3 cp "${MANIFEST_PATH}" "${S3_PREFIX}/manifest.json" --only-show-errors

# Convenience pointer for restore-from-s3.sh (latest successful day).
echo "${DAY}" | aws s3 cp - "${BACKUP_S3_URI%/}/postgres/LATEST" --only-show-errors

echo "backup: ok day=${DAY} dump_sha256=${DUMP_SHA} bytes=${DUMP_BYTES}"
