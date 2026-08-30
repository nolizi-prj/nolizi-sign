import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, devices } from "@playwright/test";
import { ADMIN_EMAIL, E2E_PORT } from "./e2e/constants";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * E2E stack orchestration.
 *
 * Local runs (default): Playwright's `webServer` boots a plain `uvicorn`
 * process directly against `backend/`, serving the already-built
 * `frontend/dist` (run `npm run build` first — see backend/app/main.py's
 * conditional SPA mount) with `DEV_AUTH_BYPASS=1` and a dedicated Postgres
 * database (a second database in the same `sign-test-pg` container backend
 * tests use — see backend/tests/conftest.py — created once with
 * `docker exec sign-test-pg psql -U postgres -c "CREATE DATABASE pumasi_sign_e2e"`).
 * `DATA_DIR` is a fresh temp directory, never the production/dev volume.
 *
 * CI: the e2e job builds the Docker image and runs the real container (see
 * .github/workflows/ci.yaml), so there's nothing for Playwright to spawn;
 * set `E2E_BASE_URL` to point at that container instead and `webServer` is
 * skipped entirely.
 */

const backendDir = path.resolve(__dirname, "..", "backend");
const externalBaseURL = process.env.E2E_BASE_URL;
const baseURL = externalBaseURL ?? `http://127.0.0.1:${E2E_PORT}`;

/** Prefer backend/.venv's interpreter (matches local dev setup); fall back to whatever's on PATH. */
function resolvePython(): string {
  const venvPython =
    process.platform === "win32"
      ? path.join(backendDir, ".venv", "Scripts", "python.exe")
      : path.join(backendDir, ".venv", "bin", "python");
  return fs.existsSync(venvPython) ? venvPython : process.platform === "win32" ? "python" : "python3";
}

const dataDir = path.join(os.tmpdir(), "pumasi-sign-e2e-data");
const databaseUrl =
  process.env.E2E_DATABASE_URL ?? "postgresql+psycopg://postgres:postgres@localhost:5433/pumasi_sign_e2e";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  timeout: 60_000,
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: externalBaseURL
    ? undefined
    : {
        command:
          `"${resolvePython()}" -m alembic upgrade head && ` +
          `"${resolvePython()}" -m uvicorn app.main:app --host 127.0.0.1 --port ${E2E_PORT}`,
        cwd: backendDir,
        url: `${baseURL}/api/health`,
        reuseExistingServer: !process.env.CI,
        timeout: 60_000,
        env: {
          DEV_AUTH_BYPASS: "1",
          DATABASE_URL: databaseUrl,
          DATA_DIR: dataDir,
          ADMIN_EMAILS: ADMIN_EMAIL,
          APP_BASE_URL: baseURL,
          SESSION_SECRET: "e2e-local-session-secret",
        },
      },
});
