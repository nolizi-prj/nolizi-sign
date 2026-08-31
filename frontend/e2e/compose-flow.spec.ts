import * as fs from "node:fs";
import { expect, test } from "@playwright/test";
import { ADMIN_EMAIL, EMPLOYEE_EMAIL } from "./constants";
import { FIXTURE_PDF, devLogin, waitForPdfRendered } from "./helpers";

/**
 * The send wizard's one-off (ad-hoc) path, specifically adding a signer who
 * has never logged in by typing their email: the signer picker offers only
 * already-provisioned users, so someone new must be creatable from a typed
 * address (backed by POST /api/users) — the recipient then shows up under a
 * placeholder name derived from the email's local part.
 */

test("admin sends a one-off envelope to a signer added by typing a new email", async ({ browser }) => {
  const adminContext = await browser.newContext();
  await devLogin(adminContext, ADMIN_EMAIL, "E2E Admin");
  const admin = await adminContext.newPage();

  // Unique per run: the e2e database persists between local runs, and this
  // test is only meaningful when the typed email belongs to nobody yet.
  const stamp = Date.now();
  const newSignerEmail = `e2e-newsigner-${stamp}@pumasi.ai`;
  const derivedName = `E2E Newsigner ${stamp}`;

  await test.step("start a one-off envelope and upload a PDF", async () => {
    await admin.goto("/");
    await admin.getByRole("link", { name: "New envelope" }).click();
    await expect(admin).toHaveURL(/\/send/);

    // Scoped to the ad-hoc upload: the dashboard's hidden hero-dropzone input
    // is a single-file input and can still be in the DOM as /send mounts, so an
    // unscoped input[type="file"] binds whichever won the race.
    await admin.locator('.adhoc-file-input input[type="file"]').setInputFiles(FIXTURE_PDF);
    await admin.getByLabel("Title").fill(`E2E Compose ${stamp}`);
    await admin.getByRole("button", { name: "Continue", exact: true }).click();
  });

  await test.step("type a brand-new email into the signer picker", async () => {
    const signerBox = admin.getByRole("combobox", { name: "Signer 1" });
    await signerBox.click({ force: true });
    await signerBox.fill(newSignerEmail);
    await signerBox.press("Enter");

    // Unknown emails never create a signer silently anymore: the explicit
    // add-signer dialog opens, prefilled with the typed email (name is
    // optional for Pumasi addresses), and only Confirm provisions them.
    const dialog = admin.getByRole("dialog");
    await expect(dialog.getByLabel("Email")).toHaveValue(newSignerEmail);
    await dialog.getByRole("button", { name: "Add signer" }).click();

    // The picker resolves the confirmed email to the provisioned placeholder name.
    await expect(signerBox).toHaveValue(new RegExp(derivedName));
    // Still exactly one signer row: a double combobox commit (Enter +
    // menu-close) must not create a second recipient.
    await expect(admin.locator(".signer-row")).toHaveCount(1);

    await admin.getByRole("button", { name: "Continue", exact: true }).click();
  });

  await test.step("place a signature field for them", async () => {
    await waitForPdfRendered(admin);
    await admin.getByRole("button", { name: "signature", exact: true }).click();
    await admin.locator(".placement-catcher").click({ position: { x: 100, y: 120 } });

    // The placed field box is labeled with the person's name, not signer-1.
    await expect(admin.locator(".field-label", { hasText: derivedName })).toBeVisible();

    await admin.getByRole("button", { name: "Continue", exact: true }).click();
  });

  await test.step("review shows the new signer, and the envelope sends", async () => {
    await expect(admin.getByText(derivedName).first()).toBeVisible();
    await admin.getByRole("button", { name: "Send envelope", exact: true }).click();
    await expect(admin.getByText(/Envelope sent/)).toBeVisible();
    await expect(admin).toHaveURL(/\/envelopes\/\d+/);
  });

  await adminContext.close();
});

test("admin sends a one-off envelope built from multiple files merged in order", async ({ browser }) => {
  const adminContext = await browser.newContext();
  await devLogin(adminContext, ADMIN_EMAIL, "E2E Admin");
  // Ensure the employee user exists before it's typed into the signer picker:
  // known emails resolve directly, unknown ones open the add-signer dialog,
  // and this test wants the known-email path regardless of spec ordering.
  const employeeContext = await browser.newContext();
  await devLogin(employeeContext, EMPLOYEE_EMAIL, "E2E Employee");
  await employeeContext.close();
  const admin = await adminContext.newPage();

  const stamp = Date.now();
  const pdfBuffer = fs.readFileSync(FIXTURE_PDF);

  await test.step("upload two PDFs; the title comes from the first file's name", async () => {
    await admin.goto("/");
    await admin.getByRole("link", { name: "New envelope" }).click();

    await admin.locator('.adhoc-file-input input[type="file"]').setInputFiles([
      { name: `contract-a-${stamp}.pdf`, mimeType: "application/pdf", buffer: pdfBuffer },
      { name: `appendix-b-${stamp}.pdf`, mimeType: "application/pdf", buffer: pdfBuffer },
    ]);

    // Auto-generated envelope name from the first file, still editable.
    await expect(admin.getByLabel("Title")).toHaveValue(`contract-a-${stamp}`);
    await admin.getByRole("button", { name: "Continue", exact: true }).click();
  });

  await test.step("pick a signer and reach placement on the merged document", async () => {
    const signerBox = admin.getByRole("combobox", { name: "Signer 1" });
    await signerBox.click({ force: true });
    await signerBox.fill(EMPLOYEE_EMAIL);
    await signerBox.press("Enter");
    await expect(signerBox).toHaveValue(/E2E Employee|e2e-employee/);
    await admin.getByRole("button", { name: "Continue", exact: true }).click();

    // sample.pdf has 2 pages; two copies merged → 4 pages.
    await waitForPdfRendered(admin);
    await expect(admin.getByText("Page 1 of 4")).toBeVisible();
  });

  await test.step("place a field and send", async () => {
    await admin.getByRole("button", { name: "signature", exact: true }).click();
    await admin.locator(".placement-catcher").click({ position: { x: 100, y: 120 } });
    await admin.getByRole("button", { name: "Continue", exact: true }).click();
    await admin.getByRole("button", { name: "Send envelope", exact: true }).click();
    await expect(admin.getByText(/Envelope sent/)).toBeVisible();
    await expect(admin).toHaveURL(/\/envelopes\/\d+/);
  });

  await adminContext.close();
});
