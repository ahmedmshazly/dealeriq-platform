# Implementation Plan: Constitution & Skeleton

**Branch**: `001-constitution-skeleton` | **Date**: 2026-07-10 | **Spec**: `specs/001-constitution-skeleton/spec.md`

**Input**: Feature specification from `specs/001-constitution-skeleton/spec.md`

## Summary

Stand up the full monorepo skeleton (SRS §3.2) with a working hello-world vertical slice: FastAPI
health endpoint with structured logging, Next.js 15 app shell wired to the Brand Kit tokens, an
installable (empty) analytics package, a generated-client codegen pipeline, Docker Compose
(Postgres 16 + MailHog), a Makefile encoding the full dev lifecycle, and a CI workflow shell -
so every later phase has a working foundation to build on and a reproducibility gate to be
re-verified against.

## Technical Context

**Language/Version**: Python 3.12 (API + analytics), TypeScript 5 / Node 20+ (web + api-client)

**Primary Dependencies**: FastAPI, Uvicorn, SQLAlchemy 2.0, Alembic, Pydantic v2 (API); Next.js
15, React 19, Tailwind CSS, next-themes, lucide-react (web); openapi-typescript + openapi-fetch
(api-client, ADR-012)

**Storage**: PostgreSQL 16 (Docker) - no tables yet this phase, only Alembic wired up and able to
run `upgrade head` against an empty migration chain

**Testing**: pytest (API/analytics smoke tests), Vitest (web smoke test), `make ci` orchestrates
all of them plus ruff/mypy/eslint/tsc

**Target Platform**: Linux/macOS/WSL2 local dev via Docker Compose; CI shell targets
ubuntu-latest (GitHub Actions), not executed remotely at the time (no git remote configured)

**Project Type**: Web application (FastAPI backend + Next.js frontend + Python analytics library
+ generated TS client), per SRS §3.2

**Performance Goals**: N/A at this phase (no real workloads yet); NFR-003/004 apply from Phase 2+

**Constraints**: C-01 (free/local-only), C-02 (stateless auth - not yet implemented but the
skeleton must not preclude it), C-05 (frontend/generated-client-only - codegen pipeline must
exist even against the trivial `/health` schema)

**Scale/Scope**: Infrastructure only - no domain entities this phase

## Constitution Check

*GATE: checked against `docs/constitution.md` v1.0.0.*

- Principle I (Monorepo & Stack Discipline): satisfied by construction - this phase *is* the
  layout.
- Principle II (Free/Local-First): satisfied - only Postgres 16 + MailHog via Compose, no paid
  services.
- Principle IV (Migrations, no auto-create): Alembic is wired up from this phase even though the
  migration chain starts empty; no `Base.metadata.create_all` anywhere.
- Principle VII (Testing bar): a trivial-but-real test exists per package now, establishing the
  pattern later phases fill in; `make ci` must be green before this phase is declared complete.
- Principle IX (Reproducible onboarding): this phase's entire purpose is making this gate exist
  and pass in ≤15 minutes.
- No violations requiring the Complexity Tracking table.

## Project Structure

### Documentation (this feature)

```text
specs/001-constitution-skeleton/
├── plan.md              # this file
├── tasks.md             # task list
└── spec.md              # feature spec
```

(No `research.md`/`data-model.md`/`contracts/` - this phase has no domain research or data model;
those begin meaningfully in Phase 1/2.)

### Source Code (repository root)

```text
apps/
├── api/
│   ├── src/dealeriq_api/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI app factory, health route, logging middleware
│   │   └── core/
│   │       ├── config.py      # pydantic-settings, reads .env
│   │       └── logging.py     # structured JSON logging (NFR-006)
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/          # empty this phase
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── tests/test_health.py
└── web/
    ├── app/
    │   ├── layout.tsx         # next/font, ThemeProvider, tokens.css import
    │   ├── page.tsx           # placeholder home page w/ brand mark
    │   ├── globals.css
    │   └── tokens.css         # copied from Brand Kit
    ├── components/theme-provider.tsx
    ├── public/                # favicon + logo assets from Brand Kit
    ├── tailwind.config.ts
    ├── next.config.ts
    ├── package.json
    └── tests/home.test.tsx

packages/
├── analytics/
│   ├── src/dealeriq_analytics/__init__.py
│   ├── pyproject.toml
│   └── tests/test_smoke.py
└── api-client/
    ├── package.json
    ├── scripts/generate.mjs   # fetches OpenAPI JSON from apps/api, runs openapi-typescript
    └── src/index.ts

infra/
├── docker-compose.yml         # postgres:16, mailhog
└── seed/                      # placeholder README this phase; real generator in Phase 3

.github/workflows/ci.yml
Makefile
pyproject.toml                 # uv workspace root
package.json                   # npm workspaces root
.env.example
.pre-commit-config.yaml        # gitleaks + ruff + eslint hooks
```

**Structure Decision**: exactly SRS §3.2's layout; no options considered or rejected since the
SRS fixes this.

## Complexity Tracking

None - no constitution violations at this phase.
