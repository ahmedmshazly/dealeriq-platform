# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/), versioned per phase until v1.0.0 ships
(Conventional Commits drive the actual commit history — see `git log` for full detail;
NFR-009).

## [Unreleased]

### Phase 1 — Auth & RBAC

- `apps/api`: email+password login issuing a JWT access token (15 min) and a rotating opaque
  refresh token (7 days, httpOnly/SameSite=Strict/Secure-in-prod cookie) with reuse detection
  that revokes the whole token family (ADR-019); Argon2id password hashing (ADR-009); account
  lockout after 5 failed logins within 15 minutes with admin unlock; forced password-change flag
  for admin-created accounts; deny-by-default `require_permission()` dependency on every route;
  4 roles / granular permission-string matrix seeded by migration (`0001_auth_rbac`) along with a
  bootstrap Admin account; append-only audit log with a filterable `GET /audit-log`.
- `apps/web`: login page (Brand Kit "Sign In" mockup translated to Tailwind/React), forced
  change-password flow, an in-memory-access-token auth context with transparent
  refresh-and-retry-once on 401 (ADR-014), an authenticated app shell with a role-driven sidebar,
  and admin pages for users/permissions/audit-log — all consuming only the generated API client.
- 37 backend tests (pytest, testcontainers-python Postgres per ADR-013) at 96% coverage; 8
  frontend tests (Vitest + RTL); full flow manually verified end-to-end in a real browser
  (login → forced password change → dashboard → RBAC-gated admin pages → logout).
- Added `GET /api/v1/auth/me` (not in the original plan) so the frontend can know who's logged
  in without decoding the JWT client-side.

### Phase 0 — Constitution & Skeleton

- Initialized the monorepo layout (SRS §3.2): `apps/api` (FastAPI), `apps/web` (Next.js 15),
  `packages/analytics`, `packages/api-client`, `infra/`, `docs/`.
- Ratified the project constitution (`docs/constitution.md` v1.0.0) and recorded
  ADR-001..020.
- Stood up a working hello-world vertical slice: `GET /api/v1/health`, structured JSON request
  logging (NFR-006), a Next.js home page consuming it and rendering the DealerIQ brand mark,
  Alembic wired to an empty migration chain, and a real end-to-end OpenAPI → TypeScript client
  codegen pipeline (C-05, ADR-012).
- Docker Compose (Postgres 16 + MailHog), a `Makefile` (`bootstrap`/`seed`/`dev`/`ci`/`test`/
  `lint`/`down`/`migrate`), gitleaks secret scanning (pre-commit + CI), and a GitHub Actions CI
  workflow shell.
