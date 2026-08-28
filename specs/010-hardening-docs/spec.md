# Feature Specification: Hardening & Docs

**Feature Branch**: `010-hardening-docs`

**Created**: 2026-07-11

**Status**: Draft

**Input**: SRS DIQ-SRS-001 v1.0.0 §13 Phase 9 - "QA-004..007, NFR-003/008, runbooks, README polish"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The system's most important user journey is protected by an automated test (Priority: P1)

As anyone changing the codebase, I want an automated test that walks the single most important
end-to-end journey - logging in, creating an order, having it approved, seeing the resulting
alert appear, and acknowledging it - against the real running application, so a regression in
that journey is caught before it reaches a real dealership.

**Why this priority**: This is the phase's own literal, named exit criterion ("Playwright suite
green," SRS §13) and QA-004's P0 requirement.

**Independent Test**: Run the new end-to-end suite against a freshly seeded dev stack; confirm it
exercises every step of the golden path against the real API and real UI (not mocked), and that
it fails loudly if any step breaks.

**Acceptance Scenarios**:

1. **Given** a freshly seeded database and a running dev stack, **When** the end-to-end suite
   runs, **Then** it logs in as a real user, creates a real order, approves it, confirms a
   resulting alert appears, and acknowledges it - all through the real UI driving the real API
   (QA-004).
2. **Given** the suite passes on a correct build, **When** a real regression is deliberately
   introduced into any step of the golden path, **Then** the suite fails and identifies which
   step broke.

---

### User Story 2 - The system's real-world performance is measured, not assumed (Priority: P1)

As anyone responsible for the system's performance, I want to actually measure API latency and
dashboard load time against realistic data volumes, so performance claims are backed by real
numbers rather than assumption.

**Why this priority**: NFR-003 is a P0 requirement with concrete, checkable numeric targets; no
tooling currently exists to verify them.

**Independent Test**: Run the new benchmarking tooling against the real seeded dev database;
confirm it reports real, reproducible latency figures for representative CRUD endpoints and the
two Phase 8 dashboard endpoints.

**Acceptance Scenarios**:

1. **Given** the real seeded dev database and a running API, **When** the benchmark tool runs
   against a representative sample of CRUD endpoints, **Then** it reports a real p95 latency
   figure per endpoint, computed over a meaningful number of requests (NFR-003).
2. **Given** the same running stack, **When** the benchmark tool measures the Manager and Sales
   dashboard endpoints, **Then** it reports a real load-time figure for each (NFR-003).
3. **Given** a measured figure that misses its target, **When** the report is produced, **Then**
   the miss is disclosed with the real number - never silently rounded or omitted.

---

### User Story 3 - A real vulnerability or leaked secret can't silently reach `main` (Priority: P1)

As anyone maintaining the codebase, I want dependency vulnerabilities and leaked secrets to
actually block a merge, with a documented way to knowingly accept a specific risk rather than
being permanently stuck, so security regressions aren't merely logged and ignored.

**Why this priority**: QA-007 (P1) has known dependency-audit checks already running but
explicitly configured to never fail the build - a check that can't fail is not a gate.

**Independent Test**: Confirm the CI pipeline fails when a genuinely vulnerable dependency (or a
committed secret) is present, and confirm a documented waiver mechanism lets a specific,
justified exception through without disabling the check for everything else.

**Acceptance Scenarios**:

1. **Given** a dependency with a known, unwaived vulnerability at or above the configured
   severity threshold, **When** CI runs, **Then** the build fails (QA-007).
2. **Given** a vulnerability that has been explicitly reviewed and recorded in the waiver list
   with a reason and re-review date, **When** CI runs, **Then** the build does not fail on that
   specific, already-reviewed finding (QA-007).
3. **Given** a secret accidentally committed, **When** CI or a local commit runs, **Then** it is
   blocked (already true today - re-verified, not rebuilt).

---

### User Story 4 - Every existing quality gate is confirmed to actually work (Priority: P2)

As anyone relying on this project's CI to catch mistakes, I want confirmation that the contract
check (a breaking API change fails the build) and the static-quality gates (lint, strict typing,
formatting) genuinely work as claimed, so trust in "CI is green" is warranted rather than assumed.

**Why this priority**: QA-005 and QA-006 already appear fully implemented from prior phases; this
story is deliberately verification-only - confirming existing machinery, not building new.

**Independent Test**: Deliberately introduce a breaking OpenAPI change and a static-quality
violation on a throwaway branch; confirm both are caught, then discard the changes.

**Acceptance Scenarios**:

1. **Given** a deliberately introduced breaking change to an API response shape, **When** the
   contract-check step runs, **Then** it fails with a clear message (QA-005).
2. **Given** a deliberately introduced ruff/mypy/eslint/tsc violation, **When** the relevant
   quality gate runs, **Then** it fails (QA-006).

---

### User Story 5 - The application is usable with a keyboard and a screen reader (Priority: P2)

As a user relying on assistive technology, I want the application's forms, controls, and chart
data to be genuinely operable without a mouse and correctly announced by a screen reader, so the
system is usable by everyone, not just sighted mouse users.

**Why this priority**: NFR-008 (P0 in the SRS) currently has no automated enforcement - violations
could be introduced by any future change and go unnoticed.

**Independent Test**: Run the new accessibility lint rule across the full frontend codebase;
confirm it surfaces real violations (if any exist) and that fixing them is verified by rerunning
the same lint rule to a clean pass.

**Acceptance Scenarios**:

1. **Given** the full set of existing page components, **When** the new accessibility lint rule
   runs, **Then** every real violation it finds is either fixed or explicitly, individually
   suppressed with a documented reason - never globally disabled (NFR-008).
2. **Given** a chart with an underlying dataset, **When** a user without access to the visual
   chart needs that data, **Then** a documented, accessible path to the same data exists
   (NFR-008).

---

### User Story 6 - An operator can diagnose a stuck job or a misbehaving alert without reading source code (Priority: P2)

As whoever is on call for this system, I want a runbook describing the analytics job scheduler
and the alert engine's real operational behavior - what each cron job does, how to tell a run
succeeded or failed, how alert rules and dedup work, how to verify the digest email - so I can
diagnose a real incident without first reading the implementation.

**Why this priority**: NFR-009 (P0) explicitly calls out "runbook for jobs/alerts" as distinct
from the general-purpose local-dev setup runbook that already exists.

**Independent Test**: Hand the new runbook to someone unfamiliar with the codebase; confirm they
can, using only the document, explain what each scheduled job does, how to check whether the
latest run succeeded, and how to verify an alert fired and its digest email was sent.

**Acceptance Scenarios**:

1. **Given** the new runbook and a real running dev stack, **When** a reader follows it, **Then**
   they can identify which analytics jobs are scheduled, when, and how to check the status of the
   most recent run of each (NFR-009).
2. **Given** the same runbook, **When** a reader wants to understand why a specific alert did or
   didn't fire, **Then** the runbook explains the rule/dedup-key model well enough to answer that
   without reading `alert_rules.py` (NFR-009).

### Edge Cases

- What happens when the Playwright golden-path test hits a real transient failure (e.g. a slow
  seed/migration on a cold dev stack) rather than a real regression? The suite retries a bounded
  number of times before failing, matching standard E2E-flake-tolerance practice, and a genuine
  failure still fails the build.
- What happens when a new dependency vulnerability appears after the waiver list was last
  reviewed, for a CVE with no available fix? It is recorded in the waiver file with a reason and
  a re-review date, not silently ignored and not left permanently blocking every unrelated commit.
- What happens when the accessibility lint rule finds a violation that has no immediate correct
  fix (e.g. a genuinely decorative third-party icon with no accessible-name convention)? It is
  suppressed individually, inline, with a one-line comment explaining why - never a blanket
  rule-level disable.
- What happens if a benchmarked endpoint's p95 exceeds its NFR-003 target? The real number is
  reported and documented as a finding; a fix is applied only if it is small and obvious,
  otherwise it is recorded in the backlog with the actual measured figure, not silently dropped.

## Requirements *(mandatory)*

### Functional Requirements

- **QA-004**: The system SHALL have an automated end-to-end test covering the golden path (login
  → create order → approve → alert appears → acknowledge) that runs against the real application,
  not mocks.
- **QA-005**: The build SHALL fail when the generated API client drifts from the actual API
  contract without an accompanying acknowledgment of the change (re-verification of existing
  machinery; see Assumptions).
- **QA-006**: The build SHALL fail on any static-quality violation (lint, strict typing,
  formatting) across both the API and the web app (re-verification of existing machinery; see
  Assumptions).
- **QA-007**: The build SHALL fail on a dependency vulnerability at or above a defined severity
  threshold, or a detected secret, unless the specific finding has been explicitly waived with a
  documented reason.
- **NFR-003**: The system's real p95 API latency for representative CRUD endpoints, and real load
  time for the Manager/Sales dashboards, SHALL be measured against real data and reported.
- **NFR-008**: The web app SHALL be enforceably checked for baseline accessibility (labeled
  controls, keyboard operability, sufficient contrast) via automated lint, and chart data SHALL
  have a documented accessible path independent of the visual chart.
- **NFR-009 (runbook + README scope only)**: A runbook SHALL document the analytics job scheduler
  and alert engine's operational behavior; every package under active development SHALL have a
  README describing its purpose and how to work on it.

### Key Entities

*(names describe the concepts introduced; exact schema is a planning-phase decision.)*

- **Vulnerability waiver record**: an accepted, time-bounded exception to the dependency-audit
  gate for one specific finding - a CVE/advisory identifier, a reason, and a re-review date.
- **Benchmark report**: a real, reproducible measurement of latency for a defined set of
  endpoints at a defined data volume - not a one-off number, but something re-runnable on demand.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The end-to-end golden-path suite runs against a real dev stack and passes,
  end-to-end, with zero manual steps beyond starting the stack.
- **SC-002**: A real, deliberately-introduced regression in any golden-path step is caught by the
  suite, verified by actually introducing one, observing the failure, and reverting it.
- **SC-003**: Real p95 latency figures exist for a representative set of CRUD endpoints and both
  Phase 8 dashboard endpoints, measured against the real seeded database, not estimated.
- **SC-004**: A genuinely vulnerable dependency or a committed secret blocks the build; a
  reviewed, waived finding does not - both verified by deliberate demonstration.
- **SC-005**: The accessibility lint rule runs clean (zero unaddressed violations) across the
  full frontend codebase.
- **SC-006**: A reader unfamiliar with the codebase can answer, using only the new runbook,
  "which jobs are scheduled and how do I check if the latest run succeeded" and "why did this
  alert fire."
- **SC-007**: The phase's own exit criterion - the Playwright suite is green, and a full
  `make bootstrap && make seed && make dev` cycle on a clean checkout completes and produces a
  working system within 15 minutes.

## Assumptions

- **QA-005 and QA-006 are already substantially implemented** by every prior phase's `make
  lint`/`make ci` and CI pipeline (OpenAPI contract-diff check, ruff/mypy/eslint/tsc, pre-commit
  hooks). This phase's work on them is deliberately verification-only (User Story 4) - confirming
  they fail closed as claimed - not building new machinery. QA-005's "unless version bumped"
  clause is interpreted as "unless the regenerated contract is reviewed and committed alongside
  the change" - the generated client is consumed only within this monorepo, never published
  externally, so a separate version-bump mechanism would add process without adding safety.
- **QA-007's dependency audit already runs in CI but is currently non-blocking** (`pip-audit`,
  `npm audit` both piped through a non-failing path). This phase makes them build-blocking and
  adds a waiver file - it does not introduce a new scanning tool.
- **NFR-003 is a measurement and disclosure task, not a performance-optimization phase.** If a
  real measurement misses its target, the finding is documented (with the real number) and fixed
  only when the fix is small and obvious; a larger fix is deferred to the backlog with the actual
  figures attached, not silently absorbed into an open-ended optimization effort.
- **NFR-008's "charts have data-table fallbacks" clause is satisfied by CSV export** (Phase 8's
  `chart-export.ts`, already wired to every dashboard/analytics chart) as the accessible path to
  chart data, on the basis that a downloadable, machine-readable data file is a stronger
  accessibility guarantee than an in-DOM fallback table that must itself be kept in sync with the
  chart. This is a documented choice, not a silent default.
- **NFR-009's runbook scope is narrow**: a new `docs/runbooks/jobs-and-alerts.md` for the
  scheduler/alert-engine operational surface specifically, since `docs/runbooks/local-dev.md`
  already covers general setup. README "polish" means filling the one real gap
  (`infra/README.md`, which doesn't exist) and touching existing package READMEs only if a
  specific, real gap is found in them - not a wholesale rewrite.
- **NFR-007's "15-min fresh-machine setup" is already built and re-verified every phase** (most
  recently in Phase 8's own reproducibility gate); this phase re-confirms it as part of its own
  exit demo rather than building anything new for it.
- **QA-004's E2E scope is exactly the one golden path named in the requirement's own text**
  (login → create order → approve → alert appears → acknowledge) - not a broader E2E suite
  covering every page or user story from every prior phase, which QA-004 does not ask for.
