# packages/api-client — DealerIQ API Client

TypeScript client generated from `apps/api`'s OpenAPI 3.1 schema (`openapi-typescript` +
`openapi-fetch`, ADR-012). This is the **only** sanctioned way `apps/web` talks to the API
(C-05) — every request is typed by path + method directly from the schema, so calling an
undocumented endpoint isn't possible through this client.

## Regenerating

Requires the API running and reachable (defaults to `NEXT_PUBLIC_API_URL` /
`http://localhost:8000`):

```bash
npm run generate --workspace packages/api-client   # writes src/schema.d.ts
npm run build --workspace packages/api-client       # tsc --noEmit
```

`src/schema.d.ts` is committed. CI regenerates it against a freshly-started API instance and
fails the build if it drifts from the committed version, unless the API's version is
deliberately bumped (QA-005). Step-by-step: [`docs/how-to/regenerate-api-client.md`](../../docs/how-to/regenerate-api-client.md).

## Usage

```ts
import { createApiClient } from "@dealeriq/api-client";

const api = createApiClient(process.env.NEXT_PUBLIC_API_URL!);
const { data, error } = await api.GET("/api/v1/health");
```
