import type { paths } from "@dealeriq/api-client";

/** Extracts a route's 200 JSON response type directly from the generated OpenAPI schema, so
 * page components never hand-declare shapes that could drift from the real contract (C-05). */
export type ApiResponse<Path extends keyof paths, Method extends keyof paths[Path]> =
  paths[Path][Method] extends {
    responses: { 200: { content: { "application/json": infer R } } };
  }
    ? R
    : never;
