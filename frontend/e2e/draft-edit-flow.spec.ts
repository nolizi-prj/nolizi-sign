import { type Page, expect, test } from "@playwright/test";
import { ADMIN_EMAIL } from "./constants";
import { FIXTURE_PDF, devLogin, waitForPdfRendered } from "./helpers";

/**
 * Draft re-entry, end to end: an admin composes a one-off envelope, saves it
 * as a draft instead of sending, reopens it from the draft banner's "Edit
 * draft" button (route /send/draft/:draftId), changes the title, and sends
 * from the wizard. Saving/sending an edited draft is "recreate-on-save" (see
 * SendView.vue's `send()`): a brand-new envelope id is created and the old
 * draft row is deleted, so this also asserts the old id is gone (404, and
 * absent from the Drafts view) and the new one reaches "In progress", then
 * signs it — the admin is the sole signer — to confirm the replacement
 * envelope is fully functional, not just a database row.
 */

/** Draw a simple zig-zag stroke across the signature pad's canvas — copied
 *  from sign-flow.spec.ts's `drawSignature` (not exported there). */
async function drawSignature(page: Page): Promise<void> {
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

test("draft can be edited in the wizard and then sent", async ({ browser }) => {
  test.setTimeout(120_000);

  const adminContext = await browser.newContext();
  await devLogin(adminContext, ADMIN_EMAIL, "E2E Admin");
  const admin = await adminContext.newPage();

  const stamp = Date.now();
  const draftTitle = `E2E Draft ${stamp}`;
  // Stamped: the e2e DB persists across local runs, and title-based
  // absence assertions below would match leftovers from an earlier run.
  const editedTitle = `Edited draft e2e ${stamp}`;

  let draftId = "";

  await test.step("compose a one-off envelope to self and save as draft", async () => {
    await admin.goto("/");
    await admin.getByRole("link", { name: "New envelope" }).click();
    await expect(admin).toHaveURL(/\/send$/);

    await admin.locator('.adhoc-file-input input[type="file"]').setInputFiles(FIXTURE_PDF);
    await admin.getByLabel("Title").fill(draftTitle);
    await admin.getByRole("button", { name: "Continue", exact: true }).click();

    const signerBox = admin.getByRole("combobox", { name: "Signer 1" });
    await signerBox.click({ force: true });
    await signerBox.fill(ADMIN_EMAIL);
    await signerBox.press("Enter");
    await expect(signerBox).toHaveValue(/E2E Admin|e2e-admin/);
    await admin.getByRole("button", { name: "Continue", exact: true }).click();

    await waitForPdfRendered(admin);
    await admin.getByRole("button", { name: "signature", exact: true }).click();
    await admin.locator(".placement-catcher").click({ position: { x: 100, y: 120 } });
    // A checkbox field alongside the signature: regression coverage for the
    // signing view crash where textValid() assumed every field value was a
    // string and called .trim() on a checkbox's boolean value.
    await admin.getByRole("button", { name: "checkbox", exact: true }).click();
    await admin.locator(".placement-catcher").click({ position: { x: 100, y: 200 } });
    await admin.getByRole("button", { name: "Continue", exact: true }).click();

    await admin.getByRole("button", { name: "Save as draft", exact: true }).click();
    await expect(admin.getByText("Draft saved")).toBeVisible();
    await expect(admin).toHaveURL(/\/envelopes\/\d+/);
    draftId = admin.url().match(/\/envelopes\/(\d+)/)?.[1] ?? "";
    expect(draftId, "draft id parsed from the post-save URL").not.toBe("");
  });

  await test.step("the envelope detail page shows the draft banner", async () => {
    await expect(admin.getByText("This envelope is a draft")).toBeVisible();
    // A v-btn bound with `:to` renders an <a> — accessible role "link", not "button".
    await expect(admin.getByRole("link", { name: "Edit draft" })).toBeVisible();
    await expect(admin.getByRole("button", { name: "Send now" })).toBeVisible();
    await expect(admin.getByRole("button", { name: "Delete" })).toBeVisible();
  });

  await test.step("Edit draft opens the wizard prefilled at /send/draft/:id", async () => {
    await admin.getByRole("link", { name: "Edit draft" }).click();
    await expect(admin).toHaveURL(new RegExp(`/send/draft/${draftId}$`));
    await expect(admin.getByLabel("Title")).toHaveValue(draftTitle);
  });

  let newId = "";

  await test.step("edit the title and advance to review, then send", async () => {
    await admin.getByLabel("Title").fill(editedTitle);
    // Step 1 -> 2 (signers, prefilled) -> 3 (fields, prefilled) -> review.
    await admin.getByRole("button", { name: "Continue", exact: true }).click();
    await admin.getByRole("button", { name: "Continue", exact: true }).click();
    await admin.getByRole("button", { name: "Continue", exact: true }).click();

    await expect(admin.getByText(editedTitle).first()).toBeVisible();
    await admin.getByRole("button", { name: "Send envelope", exact: true }).click();
    await expect(admin.getByText(/Envelope sent/)).toBeVisible();
    await expect(admin).toHaveURL(/\/envelopes\/\d+/);

    newId = admin.url().match(/\/envelopes\/(\d+)/)?.[1] ?? "";
    expect(newId, "new envelope id parsed from the post-send URL").not.toBe("");
    expect(newId).not.toBe(draftId);
  });

  await test.step("the new envelope shows In progress with the edited title", async () => {
    await expect(admin.getByRole("heading", { name: editedTitle })).toBeVisible();
    await expect(admin.getByText("In progress", { exact: true })).toBeVisible();
  });

  await test.step("the old draft id is gone: 404 from the API, absent from the Drafts view", async () => {
    const res = await adminContext.request.get(`/api/submissions/${draftId}`);
    expect(res.status()).toBe(404);

    await admin.goto("/");
    await admin.getByRole("navigation", { name: "Envelope views" }).getByText("Drafts", { exact: true }).click();
    // Scoped to the browser table, not the whole page: the dashboard's
    // separate "waiting for your signature" queue card also shows this
    // envelope (by its new id, now pending — admin is its sole signer),
    // under the same edited title, which would otherwise false-positive.
    const draftsTable = admin.locator(".browser-content");
    await expect(draftsTable.getByText(draftTitle)).toHaveCount(0);
    await expect(draftsTable.getByText(editedTitle)).toHaveCount(0);
  });

  await test.step("sign the new envelope as the sole (self) signer", async () => {
    const detail = await (await adminContext.request.get(`/api/submissions/${newId}`)).json();
    const me = detail.submitters.find(
      (s: { user: { email: string }; is_cc: boolean }) =>
        !s.is_cc && s.user.email.toLowerCase() === ADMIN_EMAIL.toLowerCase(),
    );
    expect(me, "admin's own submitter row on the new envelope").toBeTruthy();

    await admin.goto(`/sign/${me.id}`);
    await expect(admin).toHaveURL(/\/sign\//);
    await waitForPdfRendered(admin);

    await admin.getByRole("button", { name: "Click to sign" }).click();
    await drawSignature(admin);
    await admin.getByRole("dialog").getByRole("button", { name: /Adopt/i }).click();
    // The signature dialog's closing overlay can still cover the page for a
    // beat (CI hit this): wait it out, then check WITHOUT force so Playwright
    // waits until the input actually receives the click — a forced click can
    // land on the overlay/dock and silently change nothing.
    await expect(admin.getByRole("dialog")).toBeHidden();

    // The checkbox field placed above: check it (it's optional, but check
    // it anyway to exercise the boolean value path through textValid()).
    const docCheckbox = admin.getByRole("checkbox", { name: "Checkbox field" });
    await docCheckbox.scrollIntoViewIfNeeded();
    await docCheckbox.check();
    await expect(docCheckbox).toBeChecked();

    await admin.getByRole("button", { name: "Preview & finish" }).click();
    await expect(admin.getByText("Final document preview")).toBeVisible();
    await admin.getByLabel(/electronic records|legally binding/i).check({ force: true });
    await admin.getByRole("button", { name: "Sign & finish" }).click();
    await expect(admin.getByText("Thanks")).toBeVisible();

    const completed = await (await adminContext.request.get(`/api/submissions/${newId}`)).json();
    expect(completed.status).toBe("completed");
  });

  await test.step("Copy from the browser row's three-dots menu opens the wizard on a new draft", async () => {
    await admin.goto("/");
    await admin.getByRole("navigation", { name: "Envelope views" }).getByText("Sent", { exact: true }).click();
    const row = admin.locator(".browser-content tr", { hasText: editedTitle }).first();
    await row.getByRole("button", { name: `More actions for ${editedTitle}` }).click();
    // Vuetify renders the open v-menu in an overlay outside the table DOM.
    await admin.locator(".v-overlay--active").getByText("Copy", { exact: true }).click();

    await expect(admin.getByText(/Copy created as a draft/)).toBeVisible();
    await expect(admin).toHaveURL(/\/send\/draft\/\d+$/);
    const copyDraftId = admin.url().match(/\/send\/draft\/(\d+)/)?.[1] ?? "";
    expect(copyDraftId, "copy draft id parsed from the wizard URL").not.toBe("");
    expect(copyDraftId).not.toBe(newId);
    // The wizard is hydrated from the copy, not blank.
    await expect(admin.getByLabel("Title")).toHaveValue(editedTitle);

    // Tidy up: the copy is an unsent draft this test won't send — delete it
    // so reruns against a persistent local e2e DB don't accumulate rows.
    const del = await adminContext.request.delete(`/api/submissions/${copyDraftId}`);
    expect(del.ok()).toBeTruthy();
  });

  await adminContext.close();
});
