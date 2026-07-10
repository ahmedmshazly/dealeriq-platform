# Tasks: Auth & RBAC

**Input**: plan.md from `specs/002-auth-rbac/`

## Task list

- [x] T001 `domain/models/rbac.py`: `Role`, `Permission`, `RolePermission`, `User` SQLAlchemy
      models (typed declarative, ADR-011)
- [x] T002 `domain/models/refresh_token.py`: `RefreshToken` model (hash-only, rotation chain,
      ADR-019)
- [x] T003 `domain/models/audit_log.py`: append-only `AuditLog` model; `domain/audit.py`
      `write_audit_row()` helper
- [x] T004 Alembic migration `0001_auth_rbac`: create all 5 tables + seed 4 roles + permission
      set + role_permission grants + one bootstrap Admin (from env vars, must_change_password)
- [x] T005 `auth/passwords.py`: Argon2id hash/verify per ADR-009 params
- [x] T006 `auth/tokens.py`: JWT encode/decode (PyJWT), refresh-token generation + SHA-256
      hashing, rotation-with-reuse-detection algorithm (ADR-019)
- [x] T007 `auth/dependencies.py`: `get_current_user`, `require_permission(key)` FastAPI
      dependencies; deny-by-default (missing/invalid token → 401, insufficient permission → 403)
- [x] T008 `core/errors.py`: `{error: {code, message, details}}` envelope + exception handlers
- [x] T009 `auth/service.py` + `routes/auth.py`: login (with lockout, FR-005), refresh (rotation +
      reuse detection), logout, logout-all, change-password (FR-006); slowapi rate limit on login;
      plus `GET /auth/me` (added beyond the original plan — see phase report)
- [x] T010 `routes/users.py`: list/create/patch users (`users:view`/`users:manage`)
- [x] T011 `routes/roles.py`, `routes/permissions.py`: list roles, permission matrix
      (`users:view`, `permissions:view`)
- [x] T012 `routes/audit_log.py`: paginated/filterable audit log list (`audit_log:view`, FR-081)
- [x] T013 Wire every mutating route (user create/patch, login success/failure, logout) to write
      an audit row
- [x] T014 Unit tests: password hashing round-trip, JWT encode/decode + expiry, permission-set
      matching logic, refresh-rotation reuse-detection state machine (in isolation, no DB)
- [x] T015 Integration tests (testcontainers-python, ADR-013): login happy path, lockout after 5
      failures/15min, refresh rotation + stolen-token-reuse revokes family, logout/logout-all,
      403 on a Sales user hitting an Admin-only route, audit rows written for the above
- [x] T016 Regenerate `packages/api-client` schema against the new routes; confirm it compiles
- [x] T017 Frontend: `lib/auth-context.tsx` (in-memory access token, login/logout, 401→refresh→
      retry-once), `lib/api.ts` (client wired to the fetch wrapper)
- [x] T018 Frontend: `app/login/page.tsx` translating the Brand Kit "Sign In" mockup (split
      panel, theme toggle, brand art) into Tailwind/React components
- [x] T019 Frontend: `(authenticated)/layout.tsx` (sidebar shell + route guard), `admin/users`,
      `admin/permissions`, `admin/audit-log` pages
- [x] T020 Frontend tests: login page renders + submits; a protected page redirects when
      unauthenticated
- [x] T021 Exit demo: log in as a seeded user of each of the 4 roles, prove a 403 with
      `error.code=="forbidden"` for a non-Admin hitting `POST /users`, show resulting audit rows
      via `GET /audit-log`
- [x] T022 Re-verify `make bootstrap && make seed && make dev` (NFR-007) and `make ci`
