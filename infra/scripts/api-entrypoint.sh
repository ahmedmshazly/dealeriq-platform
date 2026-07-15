#!/bin/sh
set -eu

echo "==> Waiting for Postgres..."
# DATABASE_URL looks like postgresql+psycopg://user:pass@host:5432/db
# Strip the SQLAlchemy driver suffix for a simple TCP wait via Python.
python - <<'PY'
import os, socket, time, urllib.parse
url = os.environ.get("DATABASE_URL", "")
# postgresql+psycopg://... → postgresql://...
url = url.replace("postgresql+psycopg://", "postgresql://", 1)
parsed = urllib.parse.urlparse(url)
host = parsed.hostname or "postgres"
port = parsed.port or 5432
deadline = time.time() + 120
while time.time() < deadline:
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"Postgres reachable at {host}:{port}")
            break
    except OSError:
        time.sleep(1)
else:
    raise SystemExit(f"Postgres not reachable at {host}:{port} within 120s")
PY

echo "==> Running Alembic migrations"
alembic upgrade head

echo "==> Starting API"
exec "$@"
