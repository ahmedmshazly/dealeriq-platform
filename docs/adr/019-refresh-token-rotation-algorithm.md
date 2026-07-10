# ADR-019: Refresh-token rotation with reuse detection

- Status: Accepted
- Date: 2026-07-10
- Requirement refs: FR-001, FR-003, §7 (`refresh_tokens.replaced_by`)

## Context

The data model already includes a `replaced_by` column on `refresh_tokens`, implying rotation,
but the SRS doesn't spell out the exact algorithm.

## Decision

Store only a SHA-256 hash of each refresh token (never the raw token) in `refresh_tokens`.
On every use: verify the hash, issue a new refresh token, set the old row's `replaced_by` to the
new token's id, and mark the old row consumed. If a token that is already revoked or already
replaced is presented again (indicating token theft/replay), revoke the entire token family
(walk `replaced_by` links back to the family root and mark all descendants revoked) and force
re-authentication.

## Consequences

- A stolen-and-reused refresh token is detected on its first reuse, not silently accepted,
  satisfying the security intent behind FR-001/FR-003 even though the SRS text doesn't spell out
  reuse detection explicitly.
- Raw refresh tokens are never persisted, so a database read alone cannot be used to mint new
  sessions.
- "Sign out all sessions" (FR-003) is simply: revoke every token family belonging to the user.
