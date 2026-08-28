/**
 * The access token lives in memory only - never localStorage/sessionStorage, to limit XSS
 * exposure (ADR-014). This module is the single source of truth both the React auth context
 * and the non-React API-client middleware read/write, so the middleware can always attach the
 * latest token without needing to be a React component itself.
 */

let accessToken: string | null = null;
type Listener = (token: string | null) => void;
const listeners = new Set<Listener>();

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
  for (const listener of listeners) listener(token);
}

export function subscribeToAccessToken(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
