# ADR-015: Python packaging — uv workspaces

- Status: Accepted
- Date: 2026-07-10
- Requirement refs: NFR-007, §3.2

## Context

`apps/api` and `packages/analytics` are two Python packages that need to share a lockfile and
be installable together for `make bootstrap`. uv is already a required tool
(for the developer tooling); Poetry would be a second, redundant packaging tool.

## Decision

Use uv workspaces (`[tool.uv.workspace]` at the repo root, members `apps/api` and
`packages/analytics`) rather than Poetry.

## Consequences

- One lockfile (`uv.lock`) covers both Python packages, satisfying NFR-007's pinned-dependency
  requirement.
- uv's resolver is fast enough that `make bootstrap` comfortably fits inside the 15-minute
  fresh-machine budget (NFR-007).
- No second Python packaging tool to install, configure, or keep in sync with uv.
