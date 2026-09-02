/** Frozen acceptance cases A-800–A-802 · spec/0013. */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { PDFDocument } from 'pdf-lib';

import { newHarness, cookieValue, Harness } from './support/durable-harness.js';
import { fakeBucket, makePdf } from './support/pdf-probe.js';

let seq = 0;
const uid = (p: string) => `${p}-${++seq}`;

function seedCode(h: Harness, key: string): void {
  const now = new Date();
  h.db.prepare(`INSERT INTO auth_codes (id, email, code, expires_at, created_at) VALUES (?, ?, '123456', ?, ?)`).run(
    uid('code'), key, new Date(now.getTime() + 600_000).toISOString(), now.toISOString(),
  );
}

async function ownerCookie(h: Harness): Promise<string> {
  seedCode(h, 'owner@pumasi.ai');
  const res = await h.fetch('/api/auth/login/verify', { method: 'POST', body: JSON.stringify({ email: 'owner@pumasi.ai', code: '123456' }) });
  const token = cookieValue(res, 'sign_session');
  assert.ok(token);
  return `sign_session=${token}`;
}

async function signerCookie(h: Harness, id: string, token: string): Promise<string> {
  seedCode(h, `signer:${id}`);
  const res = await h.fetch(`/api/sign/token/${token}/verify`, { method: 'POST', body: JSON.stringify({ code: '123456' }) });
  const cookie = cookieValue(res, 'sign_signer');
  assert.ok(cookie);
  return `sign_signer=${cookie}`;
}

async function seedEnvelope(h: Harness, bucket: ReturnType<typeof fakeBucket>, twoSigners = false): Promise<any> {
  const now = new Date().toISOString();
  const pdf = await makePdf(['AGREEMENT WITH PROOF']);
  bucket.objects.set('originals/attachment-source.pdf', { data: pdf, contentType: 'application/pdf' });
  h.db.prepare(`INSERT INTO submissions (id, public_uid, title, created_by, status, original_pdf_key, page_count, created_at, updated_at)
                VALUES ('sub-att', 'public-att', 'Proof Agreement', 'owner@pumasi.ai', 'pending', 'originals/attachment-source.pdf', 1, ?, ?)`).run(now, now);
  const signers = twoSigners
    ? [{ id: 's1', email: 'one@example.test', token: 'token-one', order: 1 }, { id: 's2', email: 'two@example.test', token: 'token-two', order: 1 }]
    : [{ id: 's1', email: 'one@example.test', token: 'token-one', order: 1 }];
  for (const signer of signers) {
    h.db.prepare(`INSERT INTO submitters (id, submission_id, name, email, role, signing_order, token, status, is_cc, created_at)
                  VALUES (?, 'sub-att', ?, ?, 'Signer', ?, ?, 'pending', 0, ?)`).run(signer.id, signer.id, signer.email, signer.order, signer.token, now);
    h.db.prepare(`INSERT INTO submission_fields (id, submission_id, submitter_id, type, page, x, y, width, height, required)
                  VALUES (?, 'sub-att', ?, 'attachment', 0, .1, .2, .5, .08, 1)`).run(`field-${signer.id}`, signer.id);
  }
  return signers;
}

async function upload(h: Harness, signerId: string, cookie: string, bytes: Uint8Array, name = 'proof.pdf'): Promise<Response> {
  const form = new FormData();
  form.set('file', new File([new Uint8Array(bytes).buffer], name, { type: 'text/plain' }));
  return h.fetch(`/api/sign/${signerId}/attachment`, { method: 'POST', cookie, body: form });
}

test('A-800 · signer PDF upload is bound, stamped by filename, appended before the certificate, and downloadable', async () => {
  const bucket = fakeBucket();
  const h = newHarness({ DOCUMENTS: bucket as any });
  const owner = await ownerCookie(h);
  const [signer] = await seedEnvelope(h, bucket);
  const signerSession = await signerCookie(h, signer.id, signer.token);
  const proof = await makePdf(['SUPPORTING PROOF']);
  const uploaded = await upload(h, signer.id, signerSession, proof);
  assert.equal(uploaded.status, 201);
  const attachment = await uploaded.json() as any;

  const completed = await h.fetch(`/api/sign/${signer.id}/complete`, {
    method: 'POST', cookie: signerSession,
    body: JSON.stringify({ values: { [`field-${signer.id}`]: attachment.attachment_id }, consent_accepted: true, consent_version: 'pumasi-esign-consent-v1' }),
  });
  assert.equal(completed.status, 200);
  const stored = bucket.objects.get('completed/sub-att.pdf');
  assert.ok(stored);
  assert.equal((await PDFDocument.load(stored.data)).getPageCount(), 3, 'agreement + proof + certificate');
  assert.equal((await h.fetch(`/api/files/attachment/${attachment.attachment_id}`, { cookie: owner })).status, 200);
  assert.equal((await h.fetch(`/api/files/attachment/${attachment.attachment_id}`, { cookie: signerSession })).status, 200);
});

test('A-801 · an attachment cannot cross submitters and unsupported bytes are rejected', async () => {
  const bucket = fakeBucket();
  const h = newHarness({ DOCUMENTS: bucket as any });
  await ownerCookie(h);
  const [one, two] = await seedEnvelope(h, bucket, true);
  const oneCookie = await signerCookie(h, one.id, one.token);
  const twoCookie = await signerCookie(h, two.id, two.token);
  assert.equal((await upload(h, one.id, oneCookie, new TextEncoder().encode('not a document'), 'fake.pdf')).status, 422);
  const valid = await upload(h, one.id, oneCookie, await makePdf(['PRIVATE PROOF']));
  const attachment = await valid.json() as any;
  const crossed = await h.fetch(`/api/sign/${two.id}/complete`, {
    method: 'POST', cookie: twoCookie,
    body: JSON.stringify({ values: { [`field-${two.id}`]: attachment.attachment_id }, consent_accepted: true, consent_version: 'pumasi-esign-consent-v1' }),
  });
  assert.equal(crossed.status, 422);
  assert.deepEqual(await crossed.json(), { error: `field field-${two.id}: attachment not found or not yours` });
});

test('A-803 · attachment filenames are normalized and cannot disguise their verified type', async () => {
  const bucket = fakeBucket();
  const h = newHarness({ DOCUMENTS: bucket as any });
  await ownerCookie(h);
  const [signer] = await seedEnvelope(h, bucket);
  const signerSession = await signerCookie(h, signer.id, signer.token);
  const pdf = await makePdf(['SAFE CONTENT']);

  const disguised = await upload(h, signer.id, signerSession, pdf, 'invoice.pdf.exe');
  assert.equal(disguised.status, 422);
  assert.match((await disguised.json() as any).error, /must end in \.pdf/);

  const normalized = await upload(h, signer.id, signerSession, pdf, '  ../Offer\u0000   Letter.PDF  ');
  assert.equal(normalized.status, 201);
  assert.equal((await normalized.json() as any).filename, 'Offer Letter.pdf');
});

test('A-802 · an unrelated account cannot retrieve a signer attachment', async () => {
  const bucket = fakeBucket();
  const h = newHarness({ DOCUMENTS: bucket as any });
  await ownerCookie(h);
  const [signer] = await seedEnvelope(h, bucket);
  const signerSession = await signerCookie(h, signer.id, signer.token);
  const valid = await upload(h, signer.id, signerSession, await makePdf(['PRIVATE PROOF']));
  const attachment = await valid.json() as any;
  seedCode(h, 'stranger@pumasi.ai');
  const login = await h.fetch('/api/auth/login/verify', { method: 'POST', body: JSON.stringify({ email: 'stranger@pumasi.ai', code: '123456' }) });
  const token = cookieValue(login, 'sign_session');
  assert.ok(token);
  assert.equal((await h.fetch(`/api/files/attachment/${attachment.attachment_id}`, { cookie: `sign_session=${token}` })).status, 404);
});

test('A-960 · completion requires current consent and stores the reviewed-document evidence', async () => {
  const bucket = fakeBucket();
  const h = newHarness({ DOCUMENTS: bucket as any });
  await ownerCookie(h);
  const [signer] = await seedEnvelope(h, bucket);
  h.db.prepare(`UPDATE submission_fields SET required = 0 WHERE submission_id = 'sub-att'`).run();
  const cookie = await signerCookie(h, signer.id, signer.token);
  const endpoint = `/api/sign/${signer.id}/complete`;
  const refused = await h.fetch(endpoint, { method: 'POST', cookie, body: JSON.stringify({ values: {} }) });
  assert.equal(refused.status, 422);
  assert.equal((h.db.prepare(`SELECT status FROM submitters WHERE id = ?`).get(signer.id) as any).status, 'pending');
  assert.equal((h.db.prepare(`SELECT COUNT(*) AS n FROM signer_consents`).get() as any).n, 0);

  const done = await h.fetch(endpoint, {
    method: 'POST', cookie,
    headers: { 'cf-connecting-ip': '203.0.113.90', 'user-agent': 'EvidenceTest/1.0' },
    body: JSON.stringify({ values: {}, consent_accepted: true, consent_version: 'pumasi-esign-consent-v1' }),
  });
  assert.equal(done.status, 200, await done.clone().text());
  const consent = h.db.prepare(`SELECT * FROM signer_consents WHERE submitter_id = ?`).get(signer.id) as any;
  assert.equal(consent.disclosure_version, 'pumasi-esign-consent-v1');
  assert.equal(consent.ip_address, '203.0.113.90');
  assert.equal(consent.user_agent, 'EvidenceTest/1.0');
  assert.match(consent.reviewed_document_hash, /^[a-f0-9]{64}$/);
  assert.deepEqual(JSON.parse(consent.document_manifest_json).map((d: any) => d.filename), ['Proof Agreement.pdf']);
});

test('A-961 · the certificate is a separate authorized one-page PDF with its own recorded hash', async () => {
  const bucket = fakeBucket();
  const h = newHarness({ DOCUMENTS: bucket as any });
  const owner = await ownerCookie(h);
  const [signer] = await seedEnvelope(h, bucket);
  h.db.prepare(`UPDATE submission_fields SET required = 0 WHERE submission_id = 'sub-att'`).run();
  const cookie = await signerCookie(h, signer.id, signer.token);
  const done = await h.fetch(`/api/sign/${signer.id}/complete`, {
    method: 'POST', cookie,
    body: JSON.stringify({ values: {}, consent_accepted: true, consent_version: 'pumasi-esign-consent-v1' }),
  });
  assert.equal(done.status, 200);
  const certificate = await h.fetch('/api/files/certificate/sub-att', { cookie: owner });
  assert.equal(certificate.status, 200);
  assert.match(certificate.headers.get('content-disposition') || '', /certificate/);
  const bytes = new Uint8Array(await certificate.arrayBuffer());
  assert.equal((await PDFDocument.load(bytes)).getPageCount(), 1);
  const completedEvent = h.db.prepare(`SELECT details_json FROM audit_events WHERE submission_id = ? AND event_type = 'completed'`).get('sub-att') as any;
  assert.match(JSON.parse(completedEvent.details_json).certificateHash, /^[a-f0-9]{64}$/);
  assert.equal((await h.fetch('/api/files/certificate/sub-att')).status, 404);
});
