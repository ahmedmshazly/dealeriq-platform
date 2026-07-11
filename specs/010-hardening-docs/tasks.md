# Tasks: Hardening & Docs

**Input**: plan.md from `specs/010-hardening-docs/`

## Task list

- [x] T001 `apps/web/package.json` + `apps/web/playwright.config.ts` (NEW): add `@playwright/test`
      devDependency, install browsers; `baseURL http://localhost:3000`, `webServer` disabled —
      runs against an already-running `make dev` stack, matching every prior phase's
      real-dev-stack verification convention. Chromium launches without `--with-deps` (no sudo
      available in this environment) — verified with a standalone smoke script before writing
      the real suite.
- [x] T002 `apps/web/e2e/golden-path.spec.ts` (NEW): login (`sales1@dealeriq.dev`) → create a
      draft order on `/orders` against a real in-stock unit with a flat $6,000 discount (safely
      above `order_approval_discount_threshold`=0.05 for every seeded model's list price) →
      submit (confirm `pending_approval`) → log out → login (`manager1@dealeriq.dev`) → approve
      (confirm `orders:approve` boundary is real) → open `/alerts` filtered to `open`, confirm
      the topmost row is the `discount_approval` alert this submission caused (alerts are always
      returned newest-first and this alert type is only ever created synchronously by an order
      submission, so no scheduled job can race ahead of it) → acknowledge it, confirm status
      updates. Real bug found and fixed during T004: the initial "match by rule text" locator
      for the post-acknowledge assertion was ambiguous against the ~13 pre-existing open
      `discount_approval` alerts in the seeded DB, and re-locating "first open row" after
      acknowledging grabbed a *different* still-open alert (the acknowledged one disappears from
      the open-filtered view) — fixed by capturing the row's unique Created timestamp before
      acknowledging and re-locating by that timestamp under the "All" filter afterward.
- [x] T003 `Makefile` MODIFIED: add `make e2e` target (documents the `make dev` prerequisite,
      runs `npx playwright test` in `apps/web`)
- [x] T004 Ran `make e2e` (via a manually-started dev-stack instance, since this machine has a
      pre-existing unrelated process on the standard :8000 — see Phase 8's own reproducibility
      gate for the same finding) against the real seeded database: passed twice in a row
      (~15-18s each, confirming it's safely re-runnable — it creates its own order every run).
      Deliberately broke the Approve step (`orders:approve` → a nonexistent permission key),
      restarted the API, reran the suite: it failed at exactly that step
      (`expect(statusBadge).toHaveText("approved")`, actual `"pending_approval"`) — proving a
      real regression is actually caught, not just a happy-path smoke test. Reverted (confirmed
      via `git diff`, zero diff) and reran to green (SC-001, SC-002).
- [x] T005 `scripts/benchmark_api.py` (NEW): authenticates once against a real running API, then
      issues N sequential requests (configurable, default enough for a stable p95) per endpoint
      to `GET /orders`, `GET /customers`, `GET /leads`, `GET /vehicle-units`,
      `GET /dashboards/manager`, `GET /dashboards/sales`; reports p50/p95/mean per endpoint
- [x] T006 `Makefile` MODIFIED: add `make benchmark` target
- [x] T007 Ran the benchmark against the real seeded dev database (n=50/endpoint). **Found a
      real NFR-003 miss and fixed it**: `GET /vehicle-units` measured p95=734ms (target 300ms) —
      `domain/inventory_service.py`'s `list_vehicle_units` loaded every one of the real ~15,438
      seeded units into Python on *every* call regardless of filters, then sorted and paginated
      in Python. Since `days_on_lot` is plain date arithmetic
      (`(date.today() - acquisition_date).days`), pushed filtering (including the
      `min_days_on_lot`/`max_days_on_lot` bounds), ordering, and pagination into SQL — a small,
      obvious fix per spec.md's Assumptions. Re-benchmarked after the fix: p95 dropped to
      29.3ms. Every other endpoint already met its target on the first run (`/orders` 158ms,
      `/customers` 17.9ms, `/leads` 22.7ms, `/dashboards/manager` 63.9ms, `/dashboards/sales`
      23.1ms — all well under their respective 300ms/2000ms targets). Existing inventory tests
      (`test_inventory_flow.py`, `test_inventory.py`) re-verified passing unchanged; `mypy
      --strict` clean.
- [x] T008 `security/dependency-waivers.json` (NEW): committed waiver list —
      `[{id, package, reason, reviewed_by, review_date, re_review_by}]`. Real `pip-audit` scan:
      0 findings across 121 packages. Real `npm audit`: 6 real GHSA findings, all seeded here
      with individually-verified reasons — 5 are Vite/esbuild/Vitest dev-server-only attack
      surfaces this project never exercises (no `vitest --ui`, no direct Vite dev server; Vitest
      just uses Vite/esbuild as a test-transform pipeline), needing a vitest 2.x→4.x major bump
      to clear; the 6th (`GHSA-qx2v-qp2m-jg93`, postcss XSS) is vendored *inside* Next.js
      15.5.20's own `node_modules/next/node_modules/postcss` — verified an npm `overrides`
      entry does NOT remove it (Node resolves Next's own nested copy first from within Next's
      own code) and produces an invalid dependency tree for zero actual fix, so this is
      genuinely not a "small, obvious" fix; waiting on an upstream Next.js patch. All six waived
      with a 60-90 day re-review date.
- [x] T009 `scripts/check_dependency_audit.py` (NEW): runs `pip-audit --format json` and
      `npm audit --json` itself via subprocess, cross-references every reported id (pip-audit's
      own vuln id; npm's GHSA id extracted from each advisory's `url`) against
      `security/dependency-waivers.json`, exits non-zero listing every real, unwaived finding by
      id and package
- [x] T010 `.github/workflows/ci.yml` + `Makefile` MODIFIED: replaced the
      `pip-audit ... || true` / `npm audit ... || true` no-ops with one real
      `check_dependency_audit.py` invocation; added `make audit`, and added it as a prerequisite
      of `make ci` (`ci: lint test audit`)
- [x] T011 Verified QA-007 by deliberate demonstration: removed one real waiver entry
      (`GHSA-5xrq-8626-4rwp`) from the file — `make audit` correctly failed, listing exactly that
      finding as unwaived (exit 1). Restored the entry — passed again (exit 0), listing all 6
      findings as waived with their real re-review dates.
- [x] T012 Verified QA-005 (OpenAPI contract-diff) still fails closed: on a throwaway,
      uncommitted change, added a field to `AchievedAccuracyResponse`, regenerated the client
      against a real live server — `git diff --exit-code packages/api-client/src/schema.d.ts`
      correctly failed (exit 1), showing exactly the new field. Reverted and regenerated again —
      clean, zero diff.
- [x] T013 Verified QA-006 (static quality gates): ruff — a deliberate unused import correctly
      failed (`F401`); reverted. eslint — **found and fixed a real gap**: a deliberate unused
      variable was only a *warning*, and `eslint .` has no `--max-warnings` flag, so it exited
      `0` — the "must be green" lint gate silently passed a real violation. Confirmed zero
      pre-existing warnings across the full `apps/web` tree (safe to tighten), added
      `--max-warnings 0` to the `lint` script, and re-verified: the same deliberate violation now
      correctly fails the build. Reverted the violation; the tightened gate itself is a real,
      permanent fix (not reverted).
- [x] T014 `apps/web/package.json` + `apps/web/eslint.config.mjs` MODIFIED: add
      `eslint-plugin-jsx-a11y`'s `recommended` config to the existing eslint config. Real gotcha:
      `next/core-web-vitals` already registers the `jsx-a11y` plugin itself (a `Cannot redefine
      plugin` error on first attempt) — fixed by spreading only `flatConfigs.recommended.rules`
      rather than the whole flat-config object.
- [x] T015 Ran the new rule: 5 real violations, all `jsx-a11y/label-has-associated-control`
      (admin/users, change-password ×2, login ×2) — every flagged `<label>` genuinely wraps a
      real `<input>`, but through the codebase's `<Input>` wrapper component, which the rule
      can't see through by default (a static-analysis gap, not an actual accessibility defect).
      Fixed with the rule's own `controlComponents: ["Input"]` option (`eslint.config.mjs`) —
      the correct, documented way to teach the rule about custom form-control wrappers — rather
      than touching 5 call sites individually. Zero violations after. Also found and fixed a
      real config conflict this surfaced: `apps/web/e2e/golden-path.spec.ts` (T002) was being
      collected by Vitest too (`vitest.config.ts` had no `exclude`), failing on Playwright's
      `test` global — added an `exclude` for `**/e2e/**`. Re-verified: `tsc --noEmit`, `next
      build` (20 routes), and `vitest run` (8/8) all clean.
- [x] T016 `docs/runbooks/jobs-and-alerts.md` (NEW): the analytics job scheduler (the five
      DS-OPS-001 cron jobs and their schedule, `ENABLE_SCHEDULER`, triggering any job on demand
      via `POST /jobs/{name}/run`, reading an `AnalyticsRun` row to tell success/failure/
      still-running) and the alert engine (all seven real rule keys — six FR-061 built-ins plus
      `lead_score_drift`, FR-074 — dedup-key semantics, role-based notification fan-out,
      `/admin/alert-rules` config, verifying the daily digest via MailHog's own HTTP API). **A
      real, disclosed gap found while writing this**: NFR-005's "retried once with backoff" half
      is not actually implemented anywhere (verified directly against `routes/jobs.py` and
      `scheduler.py` — a failed job just stays `failed`) — the other half ("last successful run
      stays served") *is* real and correctly implemented. Documented the true current behavior
      honestly rather than the aspirational one, and added the gap to `docs/backlog.md` (P0,
      needs its own design, out of scope for a docs/tooling phase).
- [x] T017 `infra/README.md` (NEW): what's under `infra/` — `docker-compose.yml`'s two services
      (postgres, mailhog), `scripts/ensure-gitleaks.sh` — pointing to the pre-existing
      `infra/seed/README.md` for the generator (already covers it) and
      `docs/runbooks/local-dev.md` for the actual bootstrap/seed/dev walkthrough, rather than
      duplicating either.
- [x] T018 Verified SC-006: the runbook directly answers both required questions — "which jobs
      are scheduled and how do I check the latest run" (the schedule table + "Reading job
      status" section, including how to diagnose a stuck vs. failed run) and "why did this
      alert fire" (the seven-rule table + dedup-key/fan-out explanation) — without needing to
      read `alert_rules.py` or `scheduler.py`.
- [x] T019 Re-verified `make bootstrap && make seed && make dev` (NFR-007): full clean-volume
      cycle (`docker compose down -v` → `up -d` → `make bootstrap` → `make seed`, migrating
      through all 10 revisions including Phase 8's `d4e5f6a7b8c9` with no errors → dev stack
      live and login+dashboard smoke-tested) completed in **152 seconds**, well inside the
      15-minute budget. Port `:8000` is still occupied by the same pre-existing, unrelated
      `edubridge_api` process this machine had running from before this phase (see Phase 8's own
      reproducibility gate for the same finding) — verified via the identical
      `uvicorn --reload` / `next dev` commands on alternate ports, exactly as every prior phase
      on this machine has done.
- [x] T020 Re-ran `make ci` against the freshly-reseeded database from T019: **fully green**.
      ruff clean, `ruff format --check` (165 files), `mypy --strict` (108 source files), eslint
      `--max-warnings 0` clean, `tsc --noEmit` clean, **245 pytest tests passed** (94% line
      coverage, 18m53s — testcontainers Postgres), vitest 8/8, the now-blocking audit gate
      passing with all 6 real findings correctly waived, `next build` (20 routes), and API-client
      regeneration against a live server producing a **zero-diff** `schema.d.ts`.
