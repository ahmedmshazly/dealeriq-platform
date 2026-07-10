/**
 * The generated OpenAPI client (packages/api-client), wired with an auth middleware that
 * attaches the in-memory access token and transparently refreshes-and-retries once on a 401
 * (ADR-014, C-05). This is the ONLY sanctioned way apps/web talks to the API — no bare `fetch`
 * calls to the API elsewhere in this app.
 */
import { createApiClient } from "@dealeriq/api-client";
import type { Middleware } from "openapi-fetch";
import { getAccessToken, setAccessToken } from "./token-store";

const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const api = createApiClient(baseUrl);

// Requests are cloned in onRequest (before their body is consumed by the first fetch attempt)
// so a 401 retry can resend the same body.
const pendingRequestClones = new Map<string, Request>();

let refreshInFlight: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = fetch(`${baseUrl}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
    })
      .then(async (res) => {
        if (!res.ok) {
          setAccessToken(null);
          return false;
        }
        const data: { access_token: string } = await res.json();
        setAccessToken(data.access_token);
        return true;
      })
      .catch(() => {
        setAccessToken(null);
        return false;
      })
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

const authMiddleware: Middleware = {
  onRequest({ request, id }) {
    const token = getAccessToken();
    if (token) {
      request.headers.set("Authorization", `Bearer ${token}`);
    }
    pendingRequestClones.set(id, request.clone());
  },
  async onResponse({ response, id }) {
    if (response.status !== 401) {
      pendingRequestClones.delete(id);
      return undefined;
    }

    const clone = pendingRequestClones.get(id);
    pendingRequestClones.delete(id);
    if (!clone || clone.headers.get("X-Retried")) {
      return undefined;
    }

    const refreshed = await refreshAccessToken();
    if (!refreshed) {
      return undefined;
    }

    const retryRequest = clone.clone();
    retryRequest.headers.set("Authorization", `Bearer ${getAccessToken()}`);
    retryRequest.headers.set("X-Retried", "1");
    return fetch(retryRequest);
  },
};

api.use(authMiddleware);
