import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { type BrowserContext, type Page, expect } from "@playwright/test";

/** The backend test fixture PDF (2 pages) both specs upload. */
export const FIXTURE_PDF = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "..",
  "backend",
  "tests",
  "fixtures",
  "sample.pdf",
);

/**
 * Shared e2e helpers. Auth: DEV_AUTH_BYPASS (see backend/app/routers/auth.py's
 * dev-login route) is used instead of real Entra sign-in.
 * `POST /api/auth/dev-login` sets the session cookie on the calling
 * BrowserContext's cookie jar directly (via `context.request`), so logging in
 * as different users just means different browser contexts.
 */

export async function devLogin(context: BrowserContext, email: string, name: string): Promise<void> {
  const response = await context.request.post("/api/auth/dev-login", { data: { email, name } });
  expect(response.ok(), `dev-login failed for ${email}: ${response.status()}`).toBeTruthy();
}

/** Wait for a PdfPage's canvas to actually be rendered (non-zero canvas size). */
export async function waitForPdfRendered(page: Page): Promise<void> {
  await page.waitForFunction(() => {
    const canvas = document.querySelector(".pdf-page canvas") as HTMLCanvasElement | null;
    return !!canvas && canvas.clientWidth > 0 && canvas.clientHeight > 0;
  });
}
