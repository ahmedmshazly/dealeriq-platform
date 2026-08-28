# DealerIQ Constitution

## Core Principles

### I. Monorepo & Stack Discipline
The project is a single monorepo (`dealeriq/`) with the top-level layout mandated by SRS §3.2
and ADR-001: `apps/api` (FastAPI, Python 3.12), `apps/web` (Next.js 15, TypeScript, App Router),
`packages/analytics` (Python analytics library), `packages/api-client` (generated TS client),
`infra/` (Docker Compose, Dockerfile, seed scripts), `docs/` (SRS, ADRs, Diataxis portal,
runbooks, paper), and `specs/` (planning archive). Internal package layout is refined per ADR-027: API `domain/` splits into
`models/`, `services/`, `alerts/`, `reports/`, and `jobs/`; web feature UI lives under
`apps/web/features/`; host scripts under `scripts/ops/` and `scripts/ci/`. The mandated stack
is FastAPI + PostgreSQL 16 + APScheduler + statsforecast (statsmodels retained only for STL
per ADR-018) + scikit-learn + Recharts. No component of this stack, and no deviation from the
top-level layout, may change without a new ADR under `docs/adr/` justifying the change.
Rationale: this layout and stack were deliberately chosen (ADR-001..008, ADR-018, ADR-027) to
keep the OpenAPI contract, generated client, and analytics boundary coherent; ad-hoc
restructuring breaks that coherence silently.

### II. Free, Local-First, Zero Paid Services (NON-NEGOTIABLE)
Every service required for local development and operation MUST be free/open-source and run
via `docker compose up` (PostgreSQL 16 + MailHog for local SMTP capture), with zero paid
services and zero calls to paid cloud APIs (C-01). The Stage-2 hosted-deployment path
(Vercel + Neon/Supabase + a real SMTP provider) is documented only, in SRS §12.4, and MUST NOT
be implemented against or assumed available during v1.0 development — it is configuration-only
by design and requires no code changes when it happens. Rationale: this is a portfolio and
research artifact that must be reproducible by anyone, on any machine, at zero cost.

### III. Security & RBAC by Default (NON-NEGOTIABLE)
Authorization is deny-by-default and enforced exclusively in the API layer; every endpoint
declares its required permission(s), and requests lacking them return 403 with a
machine-readable error code (FR-010, FR-011) — frontend hiding of controls is cosmetic only,
never a security boundary. Passwords are hashed with Argon2id at or above the SRS minimum
(memory ≥ 64 MiB, iterations ≥ 3; see ADR-009 for exact parameters) and are never logged or
returned (FR-002). Authentication is stateless and token-based (C-02): a short-lived JWT access
token (≤ 15 min) plus a rotating refresh token (≤ 7 days) stored as an httpOnly,
SameSite=Strict cookie (FR-001, NFR-002). Rationale: the API is the sole security boundary in
this architecture; any control that can be bypassed by calling the API directly is not a
control.

### IV. Migrations & Append-Only Data Integrity (NON-NEGOTIABLE)
Schema changes happen exclusively through Alembic migrations, reviewed as PR artifacts — no
ORM auto-create in any environment (ADR-008, DAT-001). Referential integrity is enforced with
foreign-key constraints, and status fields use CHECK constraints or enums, never free-text
(DAT-002). The `stock_movements` and `audit_log` ledgers are append-only: rows are inserted,
never mutated or deleted; current state (e.g., stock level) is always derived from the ledger,
never stored and overwritten directly (DAT-003, FR-021, FR-080). Analytics tables are never
mutated by transactional code, and transactional tables are never mutated by analytics code
(DAT-003). Rationale: append-only ledgers and reviewed migrations are what make the audit trail
and the analytics/transactional boundary trustworthy; any shortcut here corrupts the system's
core evidentiary value.

### V. Analytics Reproducibility & Scientific Integrity (NON-NEGOTIABLE)
Every analytics job execution is idempotent per (job, data-snapshot), safe to re-run, seeded
with a fixed random seed recorded in the run row, versioned by parameters and code version, and
persisted as a row in `analytics_runs` before anything else consumes its output (C-04, FR-070,
DS-OPS-002, DS-OPS-003). Every scheduled job MUST also be triggerable via an authenticated
admin HTTP endpoint (`POST /api/v1/jobs/{name}/run`) with a concurrency guard preventing
double-runs (C-03, FR-072). Seasonal Naive is the mandatory champion floor for forecasting: no
method may be selected as champion for a series unless it beats Seasonal Naive on MASE
(DS-FC-006). The QA-003 scientific validation suite — (a) champion beats Seasonal Naive on
≥60% of intermittent series, (b) the anomaly detector recovers ≥80% of injected anomalies at
≤10% false-positive rate, (c) the lead-scoring model recovers the sign of every ground-truth
coefficient — is CI-blocking from the moment Phase 4 lands, and MUST NEVER be weakened,
skipped, or gamed to pass. If a metric doesn't clear its bar, the generator, method, or
threshold gets fixed; the test does not. Rationale: this project's core claim is that its
analytics are statistically defensible, not just plausible-looking; diluting these gates
destroys the thing the project is actually for.

### VI. API Contract Discipline
OpenAPI 3.1, generated from the FastAPI application, is the single source of truth for the REST
contract (§8). The frontend consumes ONLY the generated TypeScript client (openapi-typescript +
openapi-fetch, ADR-012) — no hand-written `fetch` calls to undocumented endpoints, ever (C-05).
Breaking OpenAPI changes fail CI unless the API version is deliberately bumped (QA-005).
Rationale: this is what keeps the frontend from silently drifting out of sync with what the API
actually does, and is what makes the generated client meaningful as a contract rather than
decoration.

### VII. Testing & Quality Bar (NON-NEGOTIABLE)
Backend domain services, auth, and the alert engine carry ≥80% line coverage with integration
tests run against a real PostgreSQL instance, not mocks (QA-001). Analytics metrics (MASE,
pinball loss, empirical coverage, SBC classification, Croston/SBA outputs) are unit-tested
against hand-computed fixtures or published toy examples BEFORE being wired into any pipeline
(QA-002) — this same discipline extends to the synthetic data generator itself, which must be
empirically validated (e.g., SBC-class coverage) before downstream phases depend on it.
Frontend components are tested with Vitest + React Testing Library, and the golden path
(login → create order → approve → alert appears → acknowledge) is covered by Playwright E2E
(QA-004). Static quality gates — ruff, mypy (strict on domain/analytics), eslint, `tsc --noEmit`,
pre-commit hooks — must be green (QA-006). Tests and linters MUST be green before any phase is
declared complete and before any commit; red tests or failing linters are never carried forward
or committed around.

### VIII. Documentation & Traceability
Every commit and PR description cites the requirement ID(s) it implements (FR-/NFR-/DS-/DAT-/
GEN-/QA-/API-/C-xx), using Conventional Commits. Every architectural decision made beyond the
SRS's own ADR-001..008 is recorded as a new sequentially-numbered ADR under `docs/adr/`. Each
package carries its own README; job/alert runbooks and a CHANGELOG (semantic versioning) are
kept current (NFR-009). Rationale: traceability from code back to a requirement ID is what
makes this project auditable as both an engineering artifact and a portfolio piece.

### IX. Reproducible Onboarding (NON-NEGOTIABLE)
`make bootstrap && make seed && make dev` MUST bring a fresh clone, on any supported machine, to
a fully working, seeded, alerting system in ≤15 minutes (NFR-007). This is re-verified after
every phase — not assumed to still hold because it held once. Rationale: a system that can't be
reproduced quickly from scratch isn't actually reproducible; this is the single cheapest
regression check available and it runs every phase without exception.

### X. Observability & Reliability
Every request is logged as structured JSON including request id, user id, and latency
(NFR-006); every analytics run is traceable end-to-end by its run id. An analytics job failure
MUST NEVER corrupt what dashboards serve — the last successful run's outputs stay live and
visible, and failed jobs retry once with backoff before being marked failed (NFR-005).
Rationale: analytics is a background process users don't directly control; it must fail safely,
visibly, and without silently corrupting what the rest of the system depends on.

## Additional Constraints

- **Secrets**: `.env.example` is committed and kept current with every new variable; `.env` is
  gitignored and never committed; gitleaks scans from Phase 0 onward, not added later.
- **RBAC roles**: exactly four roles in v1.0 — Admin, Manager, Sales, Analyst — deny-by-default,
  with permissions stored as granular strings grouped into roles (not hardcoded per-role
  branches) so custom roles remain possible later (NFR-020).
- **Performance budgets**: p95 API latency <300ms for CRUD endpoints, dashboard initial load
  <2s, and the full weekly forecast job over ≤500 series completes in <10 min, all on ordinary
  laptop hardware (NFR-003, NFR-004).
- **Data volume assumptions**: analytics and UI must perform comfortably at ≤100k orders,
  ≤10k vehicles, ≤50k customers (§2.4) — do not design for scale beyond this without a
  documented reason.
- **Accessibility**: WCAG 2.1 AA intent — keyboard navigable, labeled forms, sufficient
  contrast; every chart has a CSV data-table fallback (NFR-008, FR-053).

## Development Workflow

- **Phase-based delivery**: work proceeds through the SRS §13 phase list (0 → 10) in order,
  never skipped ahead. Each phase is one spec cycle: specify (scope exactly the
  requirement IDs listed for that phase) → plan (follow SRS-fixed decisions —
  ADR table, §7 data model, §8 API outline, DS-OPS-001 schedule — rather than re-deciding them)
  → tasks → implement. A phase is only complete when its stated exit demo
  (§13) actually works, its tests and linters are green, and its docs are updated.
- **Branching**: trunk-based, short-lived feature branches named after the spec feature
  directory (`specs/NNN-phase-name/` → branch `NNN-phase-name`), merged back to `main` with
  `--no-ff` and tagged `phase-N-<name>` on completion.
- **Commits**: Conventional Commits, small and frequent, never force-pushed. PR/commit
  descriptions reference the requirement IDs implemented.
- **Scope discipline**: a phase's stated requirement-ID range in SRS §13 is authoritative even
  where it includes individually P1-tagged items. P1/P2 items outside a phase's stated range are
  recorded in `docs/backlog.md`, not built opportunistically.
- **Ambiguity**: where the SRS underspecifies a threshold or UX detail, the industry-standard
  choice is made, recorded as a new ADR, and flagged in that phase's report — this does not
  block progress. Anything that would contradict the SRS outright, or add a paid/new
  dependency, is flagged instead of silently decided.

## Governance

This constitution supersedes ad-hoc engineering practice for this project. Amendments require
updating this file with a version bump (semantic versioning: MAJOR for incompatible principle
removals/redefinitions, MINOR for new principles or materially expanded guidance, PATCH for
clarifications). Every
plan is checked against these principles before implementation begins; any
complexity or deviation from them must be justified in the relevant ADR under `docs/adr/`, not
merely in code comments or commit messages.

**Version**: 1.0.0 | **Ratified**: 2026-07-10 | **Last Amended**: 2026-07-10
