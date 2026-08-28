# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| `main` (v1.x) | Yes |

This repository is primarily a portfolio / research artifact with optional showcase hosting.
Treat production deployments as operator-owned.

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security-sensitive reports.

Email the maintainer listed in the SRS author field / GitHub profile with:

- Description and impact
- Reproduction steps or PoC (non-destructive)
- Affected commit SHA or release

You should receive an acknowledgement within a reasonable time. Coordinated disclosure is
appreciated.

## Operational expectations

- No production secrets in git (`.env`, `.deploy-secrets/`, `/etc/dealeriq/*.env` on hosts).
- Gitleaks runs in pre-commit and CI.
- Dependency vulnerabilities are gated by `scripts/ci/check_dependency_audit.py` with explicit
  waivers in `security/dependency-waivers.json` (include `review_date` / `re_review_by`).
- Authorization is deny-by-default in the API — see `docs/explanation/security-model.md`.

## Safe harbor

Good-faith research that does not degrade availability, access other users' data beyond a
test account you control, or exfiltrate secrets is welcome under coordinated disclosure.
