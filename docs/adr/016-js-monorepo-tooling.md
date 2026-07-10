# ADR-016: JS monorepo tooling — npm workspaces

- Status: Accepted
- Date: 2026-07-10
- Requirement refs: §2.2 (npm prerequisite), §3.2

## Context

The JS side of the monorepo has exactly two packages: `apps/web` and `packages/api-client`. The
SRS's own prerequisites (§2.2) name npm, not pnpm or a specific monorepo tool.

## Decision

Use npm workspaces (root `package.json` with a `workspaces` field) — no Turborepo, no pnpm.

## Consequences

- Matches the SRS's stated npm prerequisite exactly; no extra tool to install or explain in the
  README.
- Turborepo's build-caching value is marginal at two packages; not worth the added config
  surface for this project's size.
- `packages/api-client` is referenced from `apps/web` via a workspace `file:` dependency,
  keeping the generated-client-consumption path (C-05) simple.
