# Tasks: Constitution & Skeleton

**Input**: plan.md from `specs/001-constitution-skeleton/`

## Task list

- [x] T001 Root workspace files: `pyproject.toml` (uv workspace, ADR-015), root `package.json`
      (npm workspaces, ADR-016), `.env.example`, `.pre-commit-config.yaml` (gitleaks + ruff +
      eslint)
- [x] T002 `apps/api`: FastAPI app factory (`main.py`), `core/config.py` (pydantic-settings),
      `core/logging.py` (structured JSON logging, NFR-006), `GET /api/v1/health`
- [x] T003 `apps/api`: Alembic wired up (`alembic.ini`, `env.py`, empty `versions/`), `alembic
      upgrade head` runs cleanly against an empty chain
- [x] T004 `apps/api`: `pyproject.toml` (deps: fastapi, uvicorn, sqlalchemy, alembic, pydantic-
      settings, argon2-cffi, pyjwt, slowapi — pinned per ADR-009/010/020 for later phases even
      though unused yet), ruff+mypy config, pytest smoke test for `/health`
- [x] T005 `packages/analytics`: installable package skeleton, pyproject.toml, one smoke test
- [x] T006 `packages/api-client`: `scripts/generate.mjs` (fetch OpenAPI JSON from a running API,
      run openapi-typescript), `package.json`, placeholder `src/index.ts` exporting the
      openapi-fetch client factory
- [x] T007 `apps/web`: Next.js 15 app (App Router, TS) scaffolded; `tokens.css` copied verbatim
      from Brand Kit into `app/tokens.css`; `tailwind.config.ts` ported from Brand Kit snippet
      (colors/radius/shadow via CSS vars, stock breakpoints + named maxWidth tokens per plan);
      `next/font/google` for Inter + JetBrains Mono; `next-themes` ThemeProvider
      (`attribute="data-theme"`, `defaultTheme="light"`)
- [x] T008 `apps/web`: placeholder home page rendering the DealerIQ lockup mark + a short
      "system online" status fetched from `/api/v1/health` through a minimal typed fetch (will be
      replaced by the generated client once real endpoints exist)
- [x] T009 `apps/web`: Vitest + RTL smoke test for the home page
- [x] T010 `infra/docker-compose.yml`: postgres:16 + mailhog services, named volumes,
      healthchecks
- [x] T011 `Makefile`: `bootstrap`, `seed`, `dev`, `ci`, `test`, `lint` targets
- [x] T012 `.github/workflows/ci.yml`: lint → typecheck → unit tests → build web → generate+
      compile api-client, invoking the same Makefile targets
- [x] T013 Copy Brand Kit logo/favicon assets into `apps/web/public/`
- [x] T014 Run `make bootstrap && make seed && make dev`, time it, verify SC-001..004
- [x] T015 Run `make ci` locally, fix any failures
- [x] T016 Write `docs/runbooks/local-dev.md` (how to bring the stack up/down, where logs are,
      how to reset the DB)
