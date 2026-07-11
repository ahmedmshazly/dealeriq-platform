# Tasks: Hardening & Docs

**Input**: plan.md from `specs/010-hardening-docs/`

## Task list

- [ ] T001 `apps/web/package.json` + `apps/web/playwright.config.ts` (NEW): add `@playwright/test`
      devDependency, install browsers; `baseURL http://localhost:3000`, `webServer` disabled —
      runs against an already-running `make dev` stack, matching every prior phase's
      real-dev-stack verification convention
- [ ] T002 `apps/web/e2e/golden-path.spec.ts` (NEW): login (`sales1@dealeriq.dev`) → create a
      draft order on `/orders` against a real in-stock unit with discount fraction above
      `order_approval_discount_threshold` (0.05) → submit (confirm `pending_approval`) → log out
      → login (`manager1@dealeriq.dev`) → approve (confirm `orders:approve` boundary is real) →
      open `/alerts`, confirm the `discount_approval` alert referencing this specific order (by
      order id in the payload, not just "an alert exists") → acknowledge it, confirm status
      updates
- [ ] T003 `Makefile` MODIFIED: add `make e2e` target (documents the `make dev` prerequisite,
      runs `npx playwright test` in `apps/web`)
- [ ] T004 Run `make e2e` against a real running `make dev` stack; fix whatever real issues it
      finds (selector mismatches, timing, a genuine bug) before it's considered done — matching
      every prior phase's "validate against the real system, not just code review" discipline
- [ ] T005 `scripts/benchmark_api.py` (NEW): authenticates once against a real running API, then
      issues N sequential requests (configurable, default enough for a stable p95) per endpoint
      to `GET /orders`, `GET /customers`, `GET /leads`, `GET /vehicle-units`,
      `GET /dashboards/manager`, `GET /dashboards/sales`; reports p50/p95/mean per endpoint
- [ ] T006 `Makefile` MODIFIED: add `make benchmark` target
- [ ] T007 Run `make benchmark` against the real seeded dev database; record the real p50/p95
      figures for every endpoint against NFR-003's 300ms (CRUD) / 2s (dashboard) targets; any
      miss is documented with the real number, fixed only if the fix is small and obvious,
      otherwise recorded in `docs/backlog.md` with the actual figures
- [ ] T008 `security/dependency-waivers.json` (NEW): committed waiver list —
      `[{id, package, reason, reviewed_by, review_date, re_review_by}]`, seeded empty (or with a
      real currently-reported finding if T011 discovers one with no immediate fix)
- [ ] T009 `scripts/check_dependency_audit.py` (NEW): runs `pip-audit --format json` and
      `npm audit --json`, cross-references every reported id against
      `security/dependency-waivers.json`, exits non-zero listing every real, unwaived finding by
      id and package
- [ ] T010 `.github/workflows/ci.yml` + `Makefile` MODIFIED: replace the current
      `pip-audit ... || true` / `npm audit ... || true` no-ops with real invocations piped
      through `check_dependency_audit.py`; add `make audit` target
- [ ] T011 Verify QA-007 by deliberate demonstration: confirm `make audit` fails on a real or
      synthetic unwaived vulnerability finding; add a waiver entry with a real reason/review date;
      confirm it then passes with that specific finding waived, and would fail again if the
      waiver entry were removed
- [ ] T012 Verify QA-005 (OpenAPI contract-diff) still fails closed: on a throwaway, uncommitted
      change, deliberately break a response schema; confirm the contract-diff CI/make-ci step
      fails with its documented message; revert
- [ ] T013 Verify QA-006 (static quality gates) still fail closed: on a throwaway, uncommitted
      change, deliberately introduce one ruff violation and one eslint violation; confirm both
      quality gates fail; revert
- [ ] T014 `apps/web/package.json` + `apps/web/eslint.config.mjs` MODIFIED: add
      `eslint-plugin-jsx-a11y`'s `recommended` config to the existing eslint config
- [ ] T015 `apps/web/app/**/*.tsx` MODIFIED wherever T014's new rule finds a real, fixable
      violation across the existing ~20 page components; any genuine false positive is suppressed
      individually with an inline `// eslint-disable-next-line jsx-a11y/<rule> -- <reason>`
      comment, never a rule- or file-level blanket disable; rerun to a clean pass
- [ ] T016 `docs/runbooks/jobs-and-alerts.md` (NEW): the analytics job scheduler (the five
      DS-OPS-001 cron jobs and their schedule, `ENABLE_SCHEDULER`, triggering any job on demand
      via `POST /jobs/{name}/run`, reading an `AnalyticsRun` row to tell success/failure/
      still-running, NFR-005's retry-once-with-backoff and last-successful-run-stays-served
      guarantees) and the alert engine (the eight rules total — six FR-061 built-ins plus the two
      customer-analytics rules, dedup-key semantics, role-based notification fan-out,
      `/admin/alert-rules` config, verifying the daily digest via MailHog's own HTTP API)
- [ ] T017 `infra/README.md` (NEW): what's under `infra/` — `docker-compose.yml`'s two services
      (postgres, mailhog), `seed/generate.py` + `ground_truth/` — pointing to
      `docs/runbooks/local-dev.md` for the actual bootstrap/seed/dev walkthrough rather than
      duplicating it
- [ ] T018 Verify SC-006: self-review the new runbook against "could someone unfamiliar with the
      codebase answer, using only this document: which jobs are scheduled and how do I check if
      the latest run succeeded, and why did this specific alert fire"
- [ ] T019 Re-verify `make bootstrap && make seed && make dev` (NFR-007) completes within 15
      minutes on a clean checkout/fresh Postgres volume, per every prior phase's reproducibility
      gate
- [ ] T020 Re-run `make ci` full suite green, including the now-blocking audit gate (T010) and the
      new a11y lint rule (T014/T015)
