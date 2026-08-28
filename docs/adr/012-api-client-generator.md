# ADR-012: API client generator - openapi-typescript + openapi-fetch

- Status: Accepted
- Date: 2026-07-10
- Requirement refs: C-05, §3.2, QA-005

## Context

SRS §3.2 names both `openapi-typescript` and `orval` as options for generating the TypeScript
client. C-05 requires the frontend to consume only this generated client.

## Decision

Use `openapi-typescript` (pure type generation) paired with `openapi-fetch` (a tiny typed
fetch wrapper) rather than orval.

## Consequences

- Smallest config surface and fastest CI codegen step - no mock-server generation or
  multi-client-target flexibility that this single-frontend project doesn't need.
- `openapi-fetch` types every request/response by path+method directly from the OpenAPI schema,
  which is what makes C-05 enforceable in practice (an undocumented endpoint literally isn't
  callable through the generated client).
- If a future requirement needs orval's extra features (e.g., generated React Query hooks,
  MSW mocks), that's a new ADR, not a silent swap.
