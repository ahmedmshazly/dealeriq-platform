# Implementation Plan: Auth & RBAC

**Branch**: `002-auth-rbac` | **Date**: 2026-07-10 | **Spec**: `specs/002-auth-rbac/spec.md`

## Summary

Implement email+password authentication (Argon2id, ADR-009), JWT access + rotating refresh
tokens with reuse detection (ADR-010, ADR-019), deny-by-default permission checking enforced as
a FastAPI dependency on every route, the four roles and a granular permission matrix seeded by
migration, account lockout and forced-password-change, and an append-only audit log with a
basic browse/filter endpoint and admin UI page.

## Gap-fill note: FR-081 has no assigned phase in the SRS

SRS §13's phase table lists FR-080 under Phase 1 ("audit basics") but never assigns FR-081
(browse/filter/export the audit log) or FR-082 (settings console) to any phase, even though both
are listed as P0/P1 in §5.9. This is a genuine SRS gap, not a design choice to second-guess.
Per the constitution's ambiguity-resolution rule (industry-standard choice, recorded, flagged —
not blocked on): FR-081 is folded into Phase 1, because an audit log that can only be written and
never read fails this phase's own exit demo ("audit rows visible"). FR-082 (settings console) has
no such dependency on this phase and is deferred to `docs/backlog.md` with a note to assign it a
phase when Phase 6 (alert rule configuration) or Phase 9 (hardening) makes a natural home for it
clearer.

## Technical Context

**Language/Version**: Python 3.12 (API), TypeScript 5 (web)

**Primary Dependencies**: argon2-cffi (ADR-009), PyJWT (ADR-010), slowapi (ADR-020),
SQLAlchemy 2.0 + Alembic (ADR-011), testcontainers-python for integration tests (ADR-013)

**Storage**: PostgreSQL — first real tables (`roles`, `permissions`, `role_permissions`, `users`,
`refresh_tokens`, `audit_log`)

**Testing**: pytest unit tests (password hashing, JWT encode/decode, permission-matching logic)
+ pytest integration tests against a testcontainers-provisioned Postgres (login, lockout,
refresh rotation/reuse-detection, RBAC 403s, audit rows) + Vitest/RTL for the login page and
auth-aware layout

**Target Platform**: same as Phase 0

**Project Type**: web application (unchanged)

**Performance Goals**: p95 <300ms on auth endpoints at this phase's trivial data volumes
(NFR-003 applies fully starting here)

**Constraints**: C-02 (stateless auth — access token is a self-contained JWT, no server-side
session store); API-003 (rate limit auth endpoints, 10/min/IP, via slowapi)

**Scale/Scope**: 4 roles, a permission set sized for what exists through Phase 2 (not
speculatively large)

## Constitution Check

- Principle III (Security & RBAC by Default): this phase *is* that principle's first real
  implementation — deny-by-default dependency, Argon2id, stateless JWT + rotating refresh.
- Principle IV (Migrations & append-only integrity): `audit_log` is append-only from its first
  row; all six new tables via one reviewed Alembic migration, no autogenerate blind-trust.
- Principle VII (Testing bar): ≥80% coverage target on `auth/` and the new `domain/` models;
  integration tests hit real Postgres via testcontainers, not mocks.
- No violations requiring Complexity Tracking.

## Permission set seeded this phase

Kept to exactly what's needed through the resources that exist by end of Phase 2, per the
constitution's "granular strings, not large speculative sets" extensibility principle (NFR-020):

| Permission key | Admin | Manager | Sales | Analyst |
|---|---|---|---|---|
| `users:view` | ✓ | ✓ | | |
| `users:manage` | ✓ | | | |
| `permissions:view` | ✓ | | | |
| `audit_log:view` | ✓ | | | |

(Phase 2 adds `inventory:*`, `orders:*`, `leads:*`, `customers:*` permission keys to this same
table via a new migration — not created speculatively now.)

## API endpoints (this phase)

- `POST /api/v1/auth/login` — rate-limited 10/min/IP (API-003)
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `POST /api/v1/auth/logout-all`
- `POST /api/v1/auth/change-password` — satisfies FR-006's forced-change flow
- `GET /api/v1/users` — `users:view`
- `POST /api/v1/users` — `users:manage`
- `PATCH /api/v1/users/{id}` — `users:manage` (deactivate/reactivate/reassign role/unlock)
- `GET /api/v1/roles` — `users:view`
- `GET /api/v1/permissions/matrix` — `permissions:view`
- `GET /api/v1/audit-log` — `audit_log:view`, paginated, filterable by actor/action/entity_type/
  date range (API-001)

## Access/refresh token strategy

Access token: returned in the `POST /auth/login` / `POST /auth/refresh` JSON response body (not
a cookie) — the frontend keeps it in memory only (never localStorage, to limit XSS exposure) and
attaches it as `Authorization: Bearer <token>`. Claims: `sub` (user id), `role` (role key), `exp`,
`jti` (NFR-002). Refresh token: opaque random value, httpOnly + SameSite=Strict + Secure cookie
(name `dealeriq_refresh`); only its SHA-256 hash is persisted (ADR-019). SameSite=Strict is the
CSRF mitigation called for by NFR-001 — no separate CSRF token scheme is needed because the
refresh cookie is never sent on a cross-site request, and the access token is never in a cookie
at all (nothing for a CSRF attack to piggyback on).

## Project Structure

```text
apps/api/src/dealeriq_api/
├── auth/
│   ├── __init__.py
│   ├── passwords.py        # Argon2id hash/verify (ADR-009)
│   ├── tokens.py           # JWT encode/decode, refresh-token generation/hashing (ADR-010/019)
│   ├── dependencies.py      # get_current_user, require_permission()
│   ├── schemas.py            # Pydantic request/response models
│   └── service.py            # login/refresh/logout/logout-all/change-password logic
├── domain/
│   ├── models/
│   │   ├── rbac.py          # Role, Permission, RolePermission, User
│   │   ├── refresh_token.py
│   │   └── audit_log.py
│   └── audit.py              # write_audit_row() helper used across the app
├── routes/
│   ├── auth.py
│   ├── users.py
│   ├── roles.py
│   ├── permissions.py
│   └── audit_log.py
└── core/
    └── errors.py              # error envelope + 403/401 exception handlers

apps/api/alembic/versions/
└── 0001_auth_rbac.py          # roles, permissions, role_permissions, users, refresh_tokens,
                                # audit_log + seed data (4 roles, permission set, role grants,
                                # one bootstrap Admin from env vars)

apps/web/
├── app/
│   ├── login/page.tsx          # Brand Kit "Sign In" mockup, translated to Tailwind/React
│   ├── (authenticated)/layout.tsx   # sidebar shell, requires a session
│   ├── (authenticated)/admin/users/page.tsx
│   ├── (authenticated)/admin/permissions/page.tsx
│   └── (authenticated)/admin/audit-log/page.tsx
├── lib/
│   ├── auth-context.tsx        # in-memory access token, login/logout, auto-refresh-on-401
│   └── api.ts                    # createApiClient wired to auth-context's fetch wrapper
└── tests/
    └── login.test.tsx
```

## Complexity Tracking

None.
