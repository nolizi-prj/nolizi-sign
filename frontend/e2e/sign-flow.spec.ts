import * as fs from "node:fs";
import { type Locator, type Page, expect, test } from "@playwright/test";
import { ADMIN_EMAIL, EMPLOYEE_EMAIL, MANAGER_EMAIL } from "./constants";
import { FIXTURE_PDF, devLogin, waitForPdfRendered } from "./helpers";

/**
 * End-to-end coverage of the whole document-signing flow, driven exactly as
 * a human would through the UI: admin uploads a template, places fields for
 * two roles in the builder, sends it to two dev-bypass users, each signs
 * (drawing on the pad), the dashboard reflects completion, and the signed
 * PDF downloads with the right content-type and a larger size than the
 * original (stamped fields add bytes).
 *
 * Auth: dev-login via `devLogin` (see e2e/helpers.ts) — three different
 * users just means three different browser contexts.
 */

const ORIGINAL_PDF_SIZE = fs.statSync(FIXTURE_PDF).size;

/**
 * Open a Vuetify VSelect/VAutocomplete and pick `optionName`, waiting for
 * the menu to actually open and close so a following combobox interaction
 * doesn't race a still-closing overlay (two simultaneously-open menus can
 * otherwise both match the same option text — see `strict mode violation`
 * if this waiting is skipped).
 *
 * `force: true` on the opening click is required, not just convenient:
 * Vuetify's VSelect renders its accessible <input role="combobox"> with a
 * native `size="1"` attribute, so the input's own hit-testable box is much
 * smaller than the field's visible outline. A plain (non-forced) Playwright
 * click therefore lands on the surrounding `.v-field__input` wrapper and is
 * reported as "intercepting", never actionable, hanging until timeout. Real
 * users don't hit this (their click coordinate is wherever they physically
 * clicked, not a computed element-center), so `force` here matches real
 * usage rather than working around a genuine bug.
 */
async function selectCombobox(page: Page, combobox: Locator, optionName: string): Promise<void> {
  await combobox.click({ force: true });
  await expect(combobox).toHaveAttribute("aria-expanded", "true");

  // Vuetify keeps a closed menu's list mounted in the DOM (only its opacity
  // changes), so a page-wide getByRole('option', ...) can still match a
  // *previous*, already-closed dropdown's items. `aria-controls` on the
  // combobox names this specific open menu's id — scope the option lookup
  // to it so only the currently-open list is considered.
  const menuId = await combobox.getAttribute("aria-controls");
  if (!menuId) throw new Error("combobox is missing aria-controls; can't find its menu");
  await page.locator(`#${menuId}`).getByRole("option", { name: optionName, exact: true }).click();

  await expect(combobox).toHaveAttribute("aria-expanded", "false");
}

/** Add (if not already present) and select `role` as the "Role for new fields", then place one field. */
async function placeRoleField(
  page: Page,
  role: string,
  fieldType: "signature" | "date",
  point: { x: number; y: number },
): Promise<void> {
  const roleAlreadyAdded = (await page.locator(".role-swatch + span", { hasText: role }).count()) > 0;
  if (!roleAlreadyAdded) {
    const roleInput = page.getByRole("textbox", { name: "New role" });
    await roleInput.fill(role);
    await roleInput.press("Enter");
  }

  await selectCombobox(page, page.getByRole("combobox", { name: "Role for new fields" }), role);

  await page.getByRole("button", { name: fieldType, exact: true }).click();
  await page.locator(".placement-catcher").click({ position: point });
}

/** Draw a simple zig-zag stroke across the signature pad's canvas. */
async function drawSignature(page: Page): Promise<void> {
  // On a repeat run against the same (non-reset-between-runs) e2e database,
  // this user may already have an account-level saved signature from a
  // prior run, in which case the dialog opens on a "use saved / redraw"
  // choice screen (SignaturePad.vue's `step === "choose"`) instead of
  // straight into the draw canvas. Redraw to reach the same canvas either way.
  const redrawButton = page.getByRole("dialog").getByRole("button", { name: "Redraw" });
  if (await redrawButton.isVisible().catch(() => false)) {
    await redrawButton.click();
  }

  const canvas = page.locator("canvas.signature-canvas");
  await expect(canvas).toBeVisible();
  const box = await canvas.boundingBox();
  if (!box) throw new Error("signature canvas has no bounding box");

  const points: [number, number][] = [
    [box.x + box.width * 0.1, box.y + box.height * 0.5],
    [box.x + box.width * 0.3, box.y + box.height * 0.2],
    [box.x + box.width * 0.5, box.y + box.height * 0.8],
    [box.x + box.width * 0.7, box.y + box.height * 0.2],
    [box.x + box.width * 0.9, box.y + box.height * 0.5],
  ];

  await page.mouse.move(points[0][0], points[0][1]);
  await page.mouse.down();
  for (const [x, y] of points.slice(1)) {
    await page.mouse.move(x, y, { steps: 5 });
  }
  await page.mouse.up();
}

test("admin builds a template, sends it, both signers sign, and the completed PDF downloads", async ({ browser }) => {
  test.setTimeout(120_000);

  const adminContext = await browser.newContext();
  const employeeContext = await browser.newContext();
  const managerContext = await browser.newContext();

  await devLogin(adminContext, ADMIN_EMAIL, "E2E Admin");
  await devLogin(employeeContext, EMPLOYEE_EMAIL, "E2E Employee");
  await devLogin(managerContext, MANAGER_EMAIL, "E2E Manager");

  const admin = await adminContext.newPage();
  const employee = await employeeContext.newPage();
  const manager = await managerContext.newPage();

  const submissionTitle = `E2E Sign Flow ${Date.now()}`;

  await test.step("admin uploads a template", async () => {
    // Templates live on their own page now (top-nav "Templates").
    await admin.goto("/templates");
    await admin.getByRole("button", { name: "New template" }).click();
    await admin.getByLabel("Name").fill(submissionTitle);
    await admin.locator('input[type="file"]').setInputFiles(FIXTURE_PDF);
    // Scoped to the dialog: the dashboard's empty-state CTA ("Create your
    // first template") would otherwise also match the substring "Create".
    await admin.getByRole("dialog").getByRole("button", { name: "Create", exact: true }).click();
    await expect(admin).toHaveURL(/\/templates\/\d+\/build/);
    await expect(admin.getByRole("heading", { name: submissionTitle })).toBeVisible();
    await waitForPdfRendered(admin);
  });

  await test.step("admin places signature+date fields for Employee and a signature field for Manager", async () => {
    await placeRoleField(admin, "Employee", "signature", { x: 100, y: 120 });
    await placeRoleField(admin, "Employee", "date", { x: 100, y: 220 });

    // The builder autosaves (no Save button): the last edit debounces into
    // a PUT /templates/{id}/fields. Register the response wait before the
    // final placement so the save it triggers is deterministically caught.
    const finalSave = admin.waitForResponse(
      (r) => r.url().includes("/fields") && r.request().method() === "PUT" && r.ok(),
    );
    await placeRoleField(admin, "Manager", "signature", { x: 100, y: 320 });
    await finalSave;
    await expect(admin.getByText("All changes saved")).toBeVisible();
  });

  await test.step("admin sends the submission to both dev signers", async () => {
    await admin.getByRole("button", { name: "Send", exact: true }).click();
    await expect(admin).toHaveURL(/\/send\//);

    // Signer labels now read "Employee · signs 2 fields" — match by prefix.
    await selectCombobox(
      admin,
      admin.getByRole("combobox", { name: /^Employee/ }),
      `E2E Employee (${EMPLOYEE_EMAIL})`,
    );
    await selectCombobox(
      admin,
      admin.getByRole("combobox", { name: /^Manager/ }),
      `E2E Manager (${MANAGER_EMAIL})`,
    );

    await admin.getByRole("button", { name: "Continue", exact: true }).click();
    await admin.getByRole("button", { name: "Send envelope", exact: true }).click();
    await expect(admin.getByText(/Envelope sent/)).toBeVisible();
    // Success lands on the new envelope's detail page.
    await expect(admin).toHaveURL(/\/envelopes\/\d+/);
    await expect(admin.getByText("Signers · any order")).toBeVisible();
  });

  /** Open the signing page from the dashboard queue card, sign, review, consent, finish. */
  async function signAsUser(page: Page): Promise<void> {
    await page.goto("/");
    await page
      .locator(".queue-card", { hasText: submissionTitle })
      .getByRole("link", { name: "Review & sign" })
      .click();
    await expect(page).toHaveURL(/\/sign\//);

    await page.getByRole("button", { name: "Click to sign" }).click();
    await drawSignature(page);
    await page.getByRole("dialog").getByRole("button", { name: /Save|Adopt/i }).click();

    // Finish opens the review-and-consent dialog; completion requires the
    // explicit e-signature consent checkbox.
    await page.getByRole("button", { name: "Finish" }).click();
    const review = page.getByRole("dialog");
    await expect(review.getByText("Review before signing")).toBeVisible();
    await review.getByRole("checkbox").check({ force: true });
    await review.getByRole("button", { name: "Sign & finish" }).click();
    await expect(page.getByText("Thanks")).toBeVisible();
  }

  await test.step("employee signs their signature and date fields", async () => {
    await signAsUser(employee);
  });

  await test.step("manager signs their signature field", async () => {
    await signAsUser(manager);
  });

  await test.step("dashboard shows the submission completed, and the signed PDF downloads correctly", async () => {
    await admin.goto("/");
    // The envelope browser defaults to Inbox; the admin sent this envelope
    // without signing it, so it lives in the Sent view.
    await admin
      .getByRole("navigation", { name: "Envelope views" })
      .getByText("Sent", { exact: true })
      .click();
    const sentRow = admin.getByRole("row", { name: new RegExp(submissionTitle) });
    await expect(sentRow.getByText("Completed", { exact: true })).toBeVisible({ timeout: 15_000 });

    const submissionsResponse = await adminContext.request.get("/api/submissions?mine=sent");
    expect(submissionsResponse.ok()).toBeTruthy();
    const submissions = (await submissionsResponse.json()) as { id: number; title: string; status: string }[];
    const submission = submissions.find((s) => s.title === submissionTitle);
    expect(submission, "submission not found in admin's sent list").toBeTruthy();
    expect(submission?.status).toBe("completed");

    const pdfResponse = await adminContext.request.get(`/api/files/signed-pdf/${submission?.id}`);
    expect(pdfResponse.ok()).toBeTruthy();
    expect(pdfResponse.headers()["content-type"]).toBe("application/pdf");
    const pdfBody = await pdfResponse.body();
    expect(pdfBody.length).toBeGreaterThan(ORIGINAL_PDF_SIZE);

    // The signature certificate is a separate artifact (issue #15).
    const certResponse = await adminContext.request.get(`/api/files/certificate/${submission?.id}`);
    expect(certResponse.ok()).toBeTruthy();
    expect(certResponse.headers()["content-type"]).toBe("application/pdf");
  });

  await adminContext.close();
  await employeeContext.close();
  await managerContext.close();
});
