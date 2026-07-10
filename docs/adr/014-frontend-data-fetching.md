# ADR-014: Frontend data fetching — TanStack Query over the generated client

- Status: Accepted
- Date: 2026-07-10
- Requirement refs: C-05, FR-001, FR-040..045, FR-060..066

## Context

C-05 requires all data access to go through the generated OpenAPI client. The app is
mutation-heavy (approve/deliver/cancel orders, acknowledge/resolve alerts, transition leads),
and auth uses an httpOnly-cookie refresh-token pattern (ADR-006) rather than a bearer token the
frontend can freely inspect.

## Decision

Use TanStack Query, wrapping the generated client's typed functions, called from Client
Components — not SWR, not RSC-only data fetching.

## Consequences

- TanStack Query's mutation/invalidation APIs directly fit this app's approve-then-refetch,
  acknowledge-then-refetch workflows better than SWR's revalidation-focused model.
- A single client-side fetch wrapper attaches the access token, catches 401s, calls
  `/auth/refresh`, and retries the original request — this lives in one place
  (`apps/web/lib/api-client.ts`) rather than being threaded through Server Components.
- Server Components are still used for initial page shells/layout, but any data that can change
  from user action goes through a Client Component + TanStack Query hook.
