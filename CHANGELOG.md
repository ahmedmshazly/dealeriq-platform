# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/), versioned per phase until v1.0.0 ships
(Conventional Commits drive the actual commit history — see `git log` for full detail;
NFR-009).

## [Unreleased]

### Phase 3 — Synthetic Data Generator

- `packages/analytics`: SBC demand-pattern classifier (ADI/CV², DS-FC-002 pulled forward); an
  NB-GLM weekly demand simulator (trend + Fourier seasonality + promotions + branch effect)
  spanning all four SBC classes; a lead-funnel logit simulator with a fully signed, sign-
  recoverable coefficient table; demand-shock injection with self-verified detectability
  (independent STL re-decomposition, not just an analytic prediction).
- `infra/seed/generate.py`: bulk-inserts the generated world into Postgres (3 branches, 22
  vehicle models, ~6.4k customers, 15.2k orders with full unit/ledger/order-event trails, 6k
  leads with legal state-machine event paths) and writes GEN-006's ground-truth JSON. Wired to
  `make seed`, runtime ~16.5s.
- `infra/seed/notebooks/profile.md`: a real dataset profile (SBC histogram, order volume by
  segment/branch/payment-type, lead conversion by channel/segment, customer repeat-purchase
  distribution, injected anomaly list) pulled from an actual seeded database.
- Total order volume (~15.2k) deliberately exceeds GEN-001's approximate "~4-8k" estimate — see
  ADR-021 for why reaching ≥10 series in every SBC class requires it, given the NB-GLM's
  zero-probability math under this dataset's fixed 156-week/3-branch/~25-model shape.
- 18 new analytics tests (SBC fixtures, generator determinism/coverage, lead sign-recovery,
  anomaly detectability), all green; 112 backend tests (up from 95), 95% coverage.

### Phase 2 — Core Domain

- `apps/api`: branches, vehicle models/units with an append-only stock-movement ledger
  (receipt/reservation/sale/adjustment, every status change ledgered in the same transaction);
  customers with a non-blocking duplicate-phone/email warning; leads with a state-machine-
  validated funnel (new→contacted→test_drive→negotiating→won/lost); the full order lifecycle
  (draft→submit→pending_approval/approved→delivered/cancelled) with a configurable discount-
  threshold auto-approval, atomic `SELECT...FOR UPDATE` unit reservation, and margin visible
  only to Manager+; the FR-012 owner-or-permission mechanism shared by leads and orders.
- `apps/web`: Inventory, Customers, Leads, and Orders (list + detail/timeline) pages, all
  consuming only the generated API client; sidebar nav extended accordingly.
- 95 backend tests (up from 37), 94% coverage; full order lifecycle (both the auto-approve and
  Manager-approval paths) verified end-to-end in a real browser, including the 403 a Sales user
  gets when attempting to approve their own pending order.

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
