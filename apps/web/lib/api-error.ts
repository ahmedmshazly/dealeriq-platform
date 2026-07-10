/** Thrown by page-level queryFns so TanStack Query's retry logic (query-provider.tsx) can tell
 * a permanent 4xx (wrong permission, bad request) apart from a transient network/5xx error. */
export class ApiRequestError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}
