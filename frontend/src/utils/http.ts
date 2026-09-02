/**
 * Shared axios instance for all API calls.
 *
 * baseURL is "/api" — in dev this is proxied (see vite.config.ts). In
 * production `/api/*` is answered by the Cloudflare Worker in service/, which
 * also serves this SPA through its ASSETS binding; `wrangler.jsonc`'s
 * `run_worker_first: ["/api/*"]` is what routes those paths past the assets
 * layer. backend/ is a second implementation of the same API and is not what
 * users reach (pumasi/DECISIONS.md Q-018) — so a URL here must name a route
 * the WORKER has. Getting that wrong is what issue #7 was.
 *
 * On a 401 response, we normally hard-redirect to the SPA's own `/login`
 * page, which offers both Entra SSO and email magic-link sign-in. The one
 * exception is the auth store's own `GET /auth/me` probe:
 * that request is *expected* to 401 for a not-yet-authenticated visitor, and
 * we want the router's `beforeEach` guard (not this interceptor) to own the
 * resulting redirect, so it can preserve the originally-requested route as
 * `next`. Callers opt out of the interceptor's redirect by passing
 * `skipAuthRedirect: true` in the request config.
 */
import axios, { type AxiosError } from "axios";

declare module "axios" {
  export interface AxiosRequestConfig {
    /** When true, a 401 response is passed through instead of redirecting to login. */
    skipAuthRedirect?: boolean;
  }
}

export const http = axios.create({
  baseURL: "/api",
});

/**
 * The one way to send a browser to sign in: the SPA's own `/login` page,
 * preserving the target path. It offers both SSO buttons and the emailed
 * code, and every call it makes is a worker route.
 *
 * There used to be a second one beside it, `loginRedirectUrl`, returning a
 * server path that only backend/ answers. The worker replied to it with
 * `{"error":"Endpoint not found"}`, which a signed-out user met as a page
 * (issue #7, spec/0003). One helper, so there is nothing to pick wrongly.
 */
export function loginPageUrl(next: string): string {
  return "/login?next=" + encodeURIComponent(next);
}

http.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401 && !error.config?.skipAuthRedirect) {
      const next = window.location.pathname + window.location.search;
      window.location.href = loginPageUrl(next);
    }
    return Promise.reject(error);
  },
);

/** Human-readable message from an axios error's `detail`, with a generic fallback. */
export function extractError(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const data = err.response?.data as { detail?: unknown; error?: unknown } | undefined;
    if (typeof data?.detail === "string") return data.detail;
    if (typeof data?.error === "string") return data.error;
  }
  return "Something went wrong. Please try again.";
}

/** Like `extractError`, but for requests made with `responseType: "blob"` (the error body is a Blob too). */
export async function extractBlobError(err: unknown): Promise<string> {
  if (axios.isAxiosError(err) && err.response?.data instanceof Blob) {
    try {
      const parsed = JSON.parse(await err.response.data.text()) as { detail?: unknown };
      if (typeof parsed.detail === "string") return parsed.detail;
    } catch {
      // fall through to the generic message
    }
  }
  return extractError(err);
}

export default http;
