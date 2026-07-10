# ADR-006: Backend-owned auth (JWT + refresh rotation) over NextAuth

- Status: Accepted
- Date: 2026-07-10
- Requirement refs: SRS §3.4, FR-001..013, C-02

## Context

RBAC (FR-010, FR-011) must be enforced server-side, with the API as the sole security boundary.
NextAuth is designed around the frontend owning session state, which would either duplicate
authorization logic in two places or make the frontend an implicit trust boundary.

## Decision

The FastAPI backend owns authentication end-to-end: issues JWT access tokens and rotating
refresh tokens (ADR-010, ADR-019), and the frontend is a pure consumer of that token pair via
httpOnly cookies — no NextAuth, no frontend-side session logic.

## Consequences

- Every permission check has exactly one implementation, in the API layer — the frontend cannot
  accidentally become a second, divergent authorization boundary.
- Auth is stateless with respect to the API process (C-02), keeping the door open for a
  serverless API deployment later without an auth rearchitecture.
- The frontend must implement its own token-refresh-on-401 client wrapper (see ADR-014) rather
  than getting one for free from a library.
