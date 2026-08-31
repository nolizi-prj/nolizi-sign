import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";

/**
 * Frozen acceptance case A-006 for spec/0001 — the *rendered* landing page,
 * as a signed-out stranger meets it at `/`.
 *
 * A-001…A-005 (frontend/src/landing-claims.spec.ts) check the source. This
 * one checks what a browser actually paints, because "the page says BETA" was
 * a fact about pixels, not about a file. It reads roadmap/STAGE.md and
 * roadmap/MARKET.md from the checkout at test time — they are not in the
 * Docker image the container serves, but Playwright runs on the runner beside
 * them (see .github/workflows/ci.yaml's e2e job).
 *
 * Goes red when the page renders a stage or a price the repository cannot
 * back — the two defects of roadmap/BACKLOG.md item 1 (a) and (c).
 */

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const read = (rel: string) => fs.readFileSync(path.join(repoRoot, rel), "utf8");

test.describe("A-006 · the public landing page, rendered", () => {
  test("shows the stage roadmap/STAGE.md records, and no other", async ({ page }) => {
    const stage = read("roadmap/STAGE.md").match(/\*\*Current stage:\*\*\s*`([a-z]+)`/)?.[1];
    expect(stage, "roadmap/STAGE.md must state **Current stage:** `<stage>`").toBeTruthy();

    await page.goto("/");
    // The route is public but the guard resolves the session first (see
    // router/index.ts) — a signed-out visitor stays here rather than being
    // handed to /dashboard.
    await expect(page).toHaveURL(/\/$/);

    const badge = page.getByTestId("stage-badge");
    await expect(badge).toBeVisible();
    await expect(badge).toHaveText(new RegExp(`^${stage}\\b`, "i"));

    // No stage word the register does not carry, anywhere on the page — this
    // is the assertion the shipped BETA chip fails.
    const body = (await page.locator("body").innerText()).toLowerCase();
    for (const other of ["alpha", "beta", "launched"].filter((w) => w !== stage)) {
      expect(body, `page renders "${other}" while the register says "${stage}"`).not.toMatch(
        new RegExp(`\\b${other}\\b`),
      );
    }
  });

  test("renders no money figure that roadmap/MARKET.md does not carry", async ({ page }) => {
    const market = read("roadmap/MARKET.md");

    await page.goto("/");
    const table = page.locator("table").first();
    await expect(table).toBeVisible();

    const figures = [...(await table.innerText()).matchAll(/\$\s?\d[\d,]*(?:\.\d{1,2})?/g)].map((m) =>
      m[0].replace(/\s/g, ""),
    );
    expect(figures.length, "the comparison table should still state prices").toBeGreaterThan(0);

    const unbacked = figures.filter((amount) => !market.includes(amount));
    expect(unbacked, `rendered figures absent from roadmap/MARKET.md: ${unbacked.join(", ")}`).toEqual([]);
  });
});
