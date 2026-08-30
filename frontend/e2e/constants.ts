/**
 * Shared constants between playwright.config.ts (which needs to boot the
 * local backend with a matching ADMIN_EMAILS) and sign-flow.spec.ts (which
 * dev-logs-in as these users). Keeping them in one place avoids the two
 * drifting apart.
 */

/** Local uvicorn port used when playwright.config.ts spawns its own webServer (no E2E_BASE_URL set). */
export const E2E_PORT = Number(process.env.E2E_PORT ?? 4300);

export const ADMIN_EMAIL = "e2e-admin@pumasi.ai";
export const EMPLOYEE_EMAIL = "e2e-employee@pumasi.ai";
export const MANAGER_EMAIL = "e2e-manager@pumasi.ai";
