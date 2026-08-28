import createClient from "openapi-fetch";
import type { paths } from "./schema.js";

export type { paths };

/**
 * Typed API client factory (C-05 / ADR-012 / ADR-014). Every request is typed against the
 * generated `paths` from apps/api's OpenAPI schema - there is no way to call an undocumented
 * endpoint through this client, by construction.
 */
export function createApiClient(baseUrl: string) {
  return createClient<paths>({ baseUrl, credentials: "include" });
}

export type ApiClient = ReturnType<typeof createApiClient>;
