# ADR-009: Argon2id parameters

- Status: Accepted
- Date: 2026-07-10
- Requirement refs: FR-002

## Context

FR-002 sets minimums (memory ≥ 64 MiB, iterations ≥ 3) but doesn't pin exact parameters or a
library. This needs a concrete, defensible choice rather than a per-deployment guess.

## Decision

Use `argon2-cffi` with `time_cost=3, memory_cost=65536 KiB (64 MiB), parallelism=4, hash_len=32,
salt_len=16`.

## Consequences

- Meets FR-002's stated minimums exactly, at values consistent with OWASP's current Argon2id
  guidance for interactive login (not a batch/offline workload).
- `parallelism=4` balances login latency against brute-force cost for typical laptop/small-VM
  core counts used in local dev and Stage-2 hosting.
- These constants live in one place (`apps/api/src/dealeriq_api/auth/`) so a future security
  review can bump them without touching call sites.
