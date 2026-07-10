#!/usr/bin/env bash
# Fetches a pinned gitleaks binary into .tools/bin/ if not already present.
# Avoids assuming apt/sudo/Go-toolchain access on the dev machine or CI runner,
# so `make bootstrap` stays self-contained (NFR-007).
set -euo pipefail

GITLEAKS_VERSION="8.30.1"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TOOLS_BIN="$REPO_ROOT/.tools/bin"
TARGET="$TOOLS_BIN/gitleaks"

if [ -x "$TARGET" ] && "$TARGET" version 2>/dev/null | grep -q "$GITLEAKS_VERSION"; then
  echo "[ensure-gitleaks] gitleaks $GITLEAKS_VERSION already present at $TARGET"
  exit 0
fi

if command -v gitleaks >/dev/null 2>&1 && gitleaks version 2>/dev/null | grep -q "$GITLEAKS_VERSION"; then
  echo "[ensure-gitleaks] gitleaks $GITLEAKS_VERSION already on PATH, skipping download"
  mkdir -p "$TOOLS_BIN"
  ln -sf "$(command -v gitleaks)" "$TARGET"
  exit 0
fi

OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"
case "$ARCH" in
  x86_64) ARCH="x64" ;;
  aarch64|arm64) ARCH="arm64" ;;
  *) echo "[ensure-gitleaks] Unsupported arch: $ARCH" >&2; exit 1 ;;
esac

ASSET="gitleaks_${GITLEAKS_VERSION}_${OS}_${ARCH}.tar.gz"
URL="https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/${ASSET}"

mkdir -p "$TOOLS_BIN"
echo "[ensure-gitleaks] Downloading $URL"
curl -sL "$URL" -o /tmp/gitleaks.tar.gz
tar -xzf /tmp/gitleaks.tar.gz -C "$TOOLS_BIN" gitleaks
chmod +x "$TARGET"
rm -f /tmp/gitleaks.tar.gz
echo "[ensure-gitleaks] Installed gitleaks $GITLEAKS_VERSION to $TARGET"
