# ADR-010: JWT library - PyJWT

- Status: Accepted
- Date: 2026-07-10
- Requirement refs: FR-001, NFR-002

## Context

The SRS mandates JWT access + refresh tokens with `kid`-based signing-key rotation (NFR-002) but
doesn't pin a library. Candidates: PyJWT, python-jose, Authlib.

## Decision

Use PyJWT for encode/decode and `kid` header handling.

## Consequences

- Smallest, most actively maintained option for pure JWT encode/decode; avoids the larger OAuth
  2.0/OIDC surface area of Authlib and python-jose that this project doesn't need.
- Key rotation is implemented explicitly (a small key-registry keyed by `kid`) rather than relying
  on a library's built-in JWKS-fetching machinery, since there's no external identity provider.
