import test from 'node:test';
import assert from 'node:assert/strict';
import { PDFDocument, StandardFonts } from 'pdf-lib';
import { stampAndCertifyPdf } from '../core/stamping.js';
import { makePdf, readPdf } from './support/pdf-probe.js';

test('stampAndCertifyPdf stamps fields and appends cryptographic audit certificate', async () => {
  // 1. Create a blank test PDF document
  const originalDoc = await PDFDocument.create();
  const page = originalDoc.addPage([612, 792]);
  const font = await originalDoc.embedFont(StandardFonts.Helvetica);
  page.drawText('Sample Independent Contractor Agreement', { x: 50, y: 700, size: 16, font });
  const originalPdfBytes = await originalDoc.save();

  // 2. Define signers and placed fields
  const signers = [
    {
      id: 'signer-1',
      name: 'Alice Johnson',
      email: 'alice@example.com',
      role: 'Contractor',
      signedAt: '2026-08-30T16:30:00Z',
      ipAddress: '192.0.2.1',
    },
    {
      id: 'signer-2',
      name: 'Bob Smith',
      email: 'bob@example.com',
      role: 'Client',
      signedAt: '2026-08-30T16:35:00Z',
      ipAddress: '198.51.100.4',
    },
  ];

  const fields = [
    {
      id: 'f-1',
      signerId: 'signer-1',
      type: 'signature' as const,
      page: 1,
      x: 0.1,
      y: 0.7,
      width: 0.3,
      height: 0.05,
    },
    {
      id: 'f-2',
      signerId: 'signer-1',
      type: 'date' as const,
      page: 1,
      x: 0.5,
      y: 0.7,
      width: 0.2,
      height: 0.04,
      value: '2026-08-30',
    },
    {
      id: 'f-3',
      signerId: 'signer-2',
      type: 'checkbox' as const,
      page: 1,
      x: 0.1,
      y: 0.8,
      width: 0.03,
      height: 0.03,
      value: 'true',
    },
  ];

  // 3. Run pure stamping function
  const result = await stampAndCertifyPdf({
    originalPdfBytes,
    fields,
    signers,
    envelopeUid: 'env-test-9921',
    documentTitle: 'Independent Contractor Agreement',
    completedAt: '2026-08-30T16:35:00Z',
  });

  // 4. Assertions
  assert.ok(result.stampedPdfBytes.length > originalPdfBytes.length, 'Stamped PDF bytes generated');
  assert.equal(result.pageCount, 2, 'Page count is 2 (original 1 page + 1 certificate page)');
  assert.equal(result.originalHash.length, 64, 'Original hash is 64 hex characters');
  assert.equal(result.completedHash.length, 64, 'Completed hash is 64 hex characters');
  assert.notEqual(result.originalHash, result.completedHash, 'Hashes differ after stamping');

  // Verify the resulting PDF can be loaded cleanly
  const verifiedDoc = await PDFDocument.load(result.stampedPdfBytes);
  assert.equal(verifiedDoc.getPageCount(), 2);
});

test('stampAndCertifyPdf affixes the public envelope ID to every executed document page', async () => {
  const envelopeUid = '7f41cc1b0b2440e59f4d447372cd0ec8';
  const originalPdfBytes = await makePdf(['EMPLOYMENT OFFER', 'OFFER TERMS']);
  const benefitPdfBytes = await makePdf(['BENEFIT SUMMARY']);

  const result = await stampAndCertifyPdf({
    originalPdfBytes,
    fields: [],
    signers: [],
    envelopeUid,
    documentTitle: 'Employment package',
    completedAt: '2026-09-02T12:30:00Z',
    attachments: [{
      filename: 'benefits.pdf',
      contentType: 'application/pdf',
      bytes: benefitPdfBytes,
    }],
  });

  const probe = await readPdf(result.stampedPdfBytes);
  const expected = `Nolizi Sign Envelope ID: ${envelopeUid}`;

  assert.equal(probe.pageCount, 4, 'three document pages plus the certificate');
  for (const [index, page] of probe.pages.slice(0, -1).entries()) {
    assert.ok(page.includes(expected), `executed document page ${index + 1} carries the envelope ID`);
  }
  assert.equal(
    probe.pages.at(-1)?.filter((text) => text.includes(envelopeUid)).length,
    1,
    'the certificate retains its own canonical Envelope ID line without a duplicate page stamp',
  );
});
