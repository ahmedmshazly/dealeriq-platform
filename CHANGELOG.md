# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/), versioned per phase until v1.0.0 ships
(Conventional Commits drive the actual commit history — see `git log` for full detail;
NFR-009).

## [Unreleased]

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
