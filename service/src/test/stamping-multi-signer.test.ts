/**
 * A second case for `core/stamping.ts`: two signers, four fields of three
 * types, and the audit certificate appended to a document that already has a
 * page. `stamping.test.ts` covers one signer; this covers the multi-signer
 * shape, which is what most envelopes are.
 *
 * RENAMED at spec/0009 from `e2e-workflow.test.ts`, and the old name is the
 * reason this comment exists. It was not an end-to-end test of anything: its
 * imports are `node:test`, `node:assert/strict`, `pdf-lib` and
 * `stampAndCertifyPdf` — identical to `stamping.test.ts` — and it calls no
 * route, starts no worker and touches no store. Nothing about the file's
 * behaviour changed with the name; the assertions below are byte-for-byte
 * what they were. What changed is that a release note reporting `# pass 38`
 * over a suite containing a file called `e2e-workflow` can no longer be
 * read as a claim that anything was driven end to end. roadmap/BACKLOG.md
 * item 2 asked for this in those terms; pumasi/lessons/L-006 is why it is
 * not merely tidiness.
 *
 * The suite's only end-to-end coverage over HTTP remains the Playwright
 * suite, and that one drives `backend/` — not the tree users meet. Stated
 * here so the correction does not leave a reader believing the gap closed.
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { PDFDocument, StandardFonts } from 'pdf-lib';
import { stampAndCertifyPdf } from '../core/stamping.js';

test('stampAndCertifyPdf stamps a two-signer agreement and appends a parseable audit certificate', async () => {
  // 1. Arrange: Create a clean mock PDF contract
  const doc = await PDFDocument.create();
  const page = doc.addPage([612, 792]);
  const font = await doc.embedFont(StandardFonts.HelveticaBold);
  page.drawText('MASTER SERVICES AGREEMENT', { x: 50, y: 720, size: 18, font });
  const originalPdfBytes = await doc.save();

  // 2. Define signers and field coordinates
  const envelopeUid = 'env-e2e-84920';
  const documentTitle = 'Master Services Agreement';
  const signers = [
    {
      id: 'subtr-1',
      name: 'Sarah Connor',
      email: 'sarah@client.com',
      role: 'Client Executive',
      signedAt: '2026-08-30T16:40:00Z',
      ipAddress: '192.0.2.45',
    },
    {
      id: 'subtr-2',
      name: 'Miles Dyson',
      email: 'miles@vendor.com',
      role: 'Lead Architect',
      signedAt: '2026-08-30T16:42:00Z',
      ipAddress: '198.51.100.89',
    },
  ];

  const fields = [
    // Client fields
    {
      id: 'f-1',
      signerId: 'subtr-1',
      type: 'signature' as const,
      page: 1,
      x: 0.1,
      y: 0.75,
      width: 0.35,
      height: 0.06,
    },
    {
      id: 'f-2',
      signerId: 'subtr-1',
      type: 'date' as const,
      page: 1,
      x: 0.5,
      y: 0.75,
      width: 0.2,
      height: 0.04,
      value: '2026-08-30',
    },
    // Vendor fields
    {
      id: 'f-3',
      signerId: 'subtr-2',
      type: 'signature' as const,
      page: 1,
      x: 0.1,
      y: 0.85,
      width: 0.35,
      height: 0.06,
    },
    {
      id: 'f-4',
      signerId: 'subtr-2',
      type: 'checkbox' as const,
      page: 1,
      x: 0.5,
      y: 0.85,
      width: 0.03,
      height: 0.03,
      value: 'true',
    },
  ];

  // 3. Act: Execute pure core stamping engine
  const result = await stampAndCertifyPdf({
    originalPdfBytes,
    fields,
    signers,
    envelopeUid,
    documentTitle,
    completedAt: '2026-08-30T16:42:00Z',
  });

  // 4. Assertions on Result Integrity
  assert.ok(result.stampedPdfBytes.length > originalPdfBytes.length, 'Stamped PDF bytes exist and contain embedded signatures');
  assert.equal(result.pageCount, 2, 'Page count is 2 (original page + appended audit certificate)');
  assert.equal(result.originalHash.length, 64, 'Original hash is 64 hex characters');
  assert.equal(result.completedHash.length, 64, 'Completed hash is 64 hex characters');
  assert.notEqual(result.originalHash, result.completedHash, 'Hashes differ after stamping signatures and certificate');

  // 5. Verification: Load the generated PDF and assert all pages parse cleanly
  const verifiedDoc = await PDFDocument.load(result.stampedPdfBytes);
  assert.equal(verifiedDoc.getPageCount(), 2);
  const certPage = verifiedDoc.getPage(1);
  const { width, height } = certPage.getSize();
  assert.equal(width, 612);
  assert.equal(height, 792);
});
