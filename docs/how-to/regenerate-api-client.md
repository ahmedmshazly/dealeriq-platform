# How-to: regenerate the API client

**Audience:** backend/frontend engineers changing the REST contract.  
**Last updated:** 2026-07-17

The frontend must consume only `@dealeriq/api-client` (constitution Principle VI, ADR-012).
The committed file `packages/api-client/src/schema.d.ts` is the typed contract.

## Steps

1. Start the API (schema served at `/api/v1/openapi.json` in development):

   ```bash
   make dev
   # or: uv run uvicorn dealeriq_api.main:app --port 8000
   ```

2. Regenerate and compile:

   ```bash
   npm run generate:client
   # equivalent:
   NEXT_PUBLIC_API_URL=http://localhost:8000 npm run generate --workspace packages/api-client
   npm run build --workspace packages/api-client
   ```

3. Commit `packages/api-client/src/schema.d.ts` with the API change.

## CI

`make ci` and `.github/workflows/ci.yml` regenerate against a live app and fail on drift
(QA-005). Breaking OpenAPI changes require a deliberate API version bump (not done casually).

## Docs snapshot

To refresh the committed OpenAPI JSON used in documentation:

```bash
make docs-openapi
```

Writes `docs/reference/openapi.json`.
