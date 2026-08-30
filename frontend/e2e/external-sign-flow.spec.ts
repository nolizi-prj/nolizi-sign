import * as fs from "node:fs";
import { expect, test } from "@playwright/test";
import { ADMIN_EMAIL } from "./constants";
import { FIXTURE_PDF, devLogin, waitForPdfRendered } from "./helpers";

const FIELDS = [
  { id: "sig1", type: "signature", role: "Signer 1", page: 0, x: 0.1, y: 0.1, w: 0.25, h: 0.06, required: true },
];

async function createExternalEnvelope(context: import("@playwright/test").BrowserContext, title: string) {
  const user = await (
    await context.request.post("/api/users", { data: { email: "ext@vendor.com", name: "Ext Vendor" } })
  ).json();
  const tpl = await (
    await context.request.post("/api/templates", {
      multipart: {
        name: title,
        file: { name: "sample.pdf", mimeType: "application/pdf", buffer: fs.readFileSync(FIXTURE_PDF) },
      },
    })
  ).json();
  await context.request.put(`/api/templates/${tpl.id}/fields`, { data: { fields: FIELDS } });
  const submission = await (
    await context.request.post("/api/submissions", {
      data: { template_id: tpl.id, title, signers: [{ role: "Signer 1", user_id: user.id }] },
    })
  ).json();
  const links = await (await context.request.get(`/api/submissions/${submission.id}/dev-signing-links`)).json();
  return { submission, accessUid: links[0].access_uid as string };
}

/** Fill a Vuetify v-otp-input by typing one digit into each of its six boxes. */
async function fillOtp(page: import("@playwright/test").Page, code: string): Promise<void> {
  const boxes = page.locator(".v-otp-input input");
  for (let i = 0; i < code.length; i++) {
    await boxes.nth(i).fill(code[i]!);
  }
}

test("external signer verifies by code and signs", async ({ browser }) => {
  const admin = await browser.newContext();
  await devLogin(admin, ADMIN_EMAIL, "Admin");
  const { submission, accessUid } = await createExternalEnvelope(admin, "External e2e");

  const signer = await browser.newContext(); // no login
  const page = await signer.newPage();
  await page.goto(`/sign/t/${accessUid}`);
  await expect(page.locator("strong", { hasText: "e***@vendor.com" })).toBeVisible();
  await page.getByRole("button", { name: "Email me a code" }).click();

  // No mailbox in e2e: request a fresh code via the API (DEV_AUTH_BYPASS
  // exposes it as dev_code) — this replaces the one the click just sent.
  const codeRes = await (await signer.request.post(`/api/sign/token/${accessUid}/request-code`)).json();
  // v-otp-input's @finish handler auto-submits verify() once the sixth box
  // is filled (see ExternalSignView.vue), so no explicit "Verify" click is
  // needed here — clicking it too raced the auto-triggered navigation and
  // detached the button mid-click.
  await fillOtp(page, codeRes.dev_code);

  await waitForPdfRendered(page);
  await page.getByRole("button", { name: /click to sign/i }).click();
  // Draw on the signature pad — mirrors sign-flow.spec.ts's drawing steps.
  const canvas = page.locator("canvas.signature-canvas");
  await expect(canvas).toBeVisible();
  const box = (await canvas.boundingBox())!;
  await page.mouse.move(box.x + 30, box.y + 40);
  await page.mouse.down();
  await page.mouse.move(box.x + 160, box.y + 70, { steps: 10 });
  await page.mouse.up();
  await page.getByRole("dialog").getByRole("button", { name: /Save|Adopt/i }).click();

  await page.getByRole("button", { name: "Finish" }).click();
  await page.getByLabel(/legally binding/i).check({ force: true });
  await page.getByRole("button", { name: /sign & finish/i }).click();
  await expect(page.getByText("Thanks — your part is done.")).toBeVisible();
  // Sole signer -> the envelope is complete -> the download link must be
  // reachable via the signer cookie (finding: externals previously had no
  // UI path to the signed PDF, since GET /submissions/{id} is session-only).
  // v-btn with :href renders an <a>, so its accessible role is "link".
  await expect(page.getByRole("link", { name: "Download signed PDF" })).toBeVisible();
  await expect(page.getByText("You can close this window.")).toBeVisible();

  const detail = await (await admin.request.get(`/api/submissions/${submission.id}`)).json();
  expect(detail.status).toBe("completed");
});

test("external signer declines with a reason", async ({ browser }) => {
  const admin = await browser.newContext();
  await devLogin(admin, ADMIN_EMAIL, "Admin");
  const { submission, accessUid } = await createExternalEnvelope(admin, "Decline e2e");

  const signer = await browser.newContext();
  const page = await signer.newPage();
  await page.goto(`/sign/t/${accessUid}`);
  await page.getByRole("button", { name: "Email me a code" }).click();
  const codeRes = await (await signer.request.post(`/api/sign/token/${accessUid}/request-code`)).json();
  await fillOtp(page, codeRes.dev_code);
  await waitForPdfRendered(page);

  await page.getByRole("button", { name: "Decline" }).click();
  await page.getByLabel(/reason/i).fill("Wrong entity");
  await page.getByRole("button", { name: "Decline", exact: true }).last().click();
  await expect(page.getByText("You declined to sign.")).toBeVisible();

  const detail = await (await admin.request.get(`/api/submissions/${submission.id}`)).json();
  expect(detail.status).toBe("declined");
});
