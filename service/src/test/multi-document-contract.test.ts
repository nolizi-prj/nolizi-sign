import { test } from 'node:test';
import assert from 'node:assert/strict';

import { newHarness } from './support/durable-harness.js';
import { makePdf, readPdf } from './support/pdf-probe.js';

const blobPart = (bytes: Uint8Array): ArrayBuffer =>
  bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;

function ownerSession(h: ReturnType<typeof newHarness>): string {
  const now = new Date().toISOString();
  const token = 'owner-session';
  h.db.prepare(`INSERT INTO users (id, email, name, provider, created_at) VALUES (?, ?, ?, ?, ?)`)
    .run('owner', 'owner@example.test', 'Owner', 'email', now);
  h.db.prepare(`INSERT INTO sessions (token, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)`)
    .run(token, 'owner', new Date(Date.now() + 86_400_000).toISOString(), now);
  h.db.prepare(`INSERT INTO recipients (id, owner_email, email, name, created_at) VALUES (?, ?, ?, ?, ?)`)
    .run('recipient', 'owner@example.test', 'signer@example.test', 'Signer', now);
  return `sign_session=${token}`;
}

test('A-900 · one envelope preserves multiple document names, page ranges, and selected order', async () => {
  const h = newHarness();
  const cookie = ownerSession(h);
  const offer = await makePdf(['EMPLOYMENT OFFER']);
  const benefits = await makePdf(['BENEFITS PAGE 1', 'BENEFITS PAGE 2']);
  const form = new FormData();
  form.append('documents', new File([blobPart(benefits)], 'Benefits.pdf', { type: 'application/pdf' }));
  form.append('documents', new File([blobPart(offer)], 'Offer.pdf', { type: 'application/pdf' }));
  form.append('title', 'Employment package');
  form.append('signers_json', JSON.stringify([{ user_id: 'recipient', role: 'Employee', order: 0 }]));
  form.append('fields_json', '[]');

  const created = await h.fetch('/api/submissions/adhoc', { method: 'POST', body: form, cookie });
  assert.equal(created.status, 201, await created.clone().text());
  const envelope = await created.json() as any;

  const list = await h.fetch(`/api/submissions/${envelope.id}/documents`, { cookie });
  assert.equal(list.status, 200);
  const documents = await list.json() as any[];
  assert.deepEqual(documents.map((d) => [d.filename, d.order, d.page_count, d.page_start]), [
    ['Benefits.pdf', 0, 2, 0],
    ['Offer.pdf', 1, 1, 2],
  ]);

  const preview = await h.fetch(`/api/files/document-preview/${envelope.id}`, { cookie });
  assert.equal(preview.status, 200);
  assert.deepEqual((await readPdf(new Uint8Array(await preview.arrayBuffer()))).pages.map((page) => page.join('')), [
    'BENEFITS PAGE 1', 'BENEFITS PAGE 2', 'EMPLOYMENT OFFER',
  ]);

  const download = await h.fetch(`/api/files/submission-document/${documents[1].id}`, { cookie });
  assert.equal(download.status, 200);
  assert.match(download.headers.get('content-disposition') || '', /Offer\.pdf/);
  assert.deepEqual((await readPdf(new Uint8Array(await download.arrayBuffer()))).pages.map((page) => page.join('')), ['EMPLOYMENT OFFER']);
});

test('A-901 · document downloads remain private to envelope participants', async () => {
  const h = newHarness();
  const cookie = ownerSession(h);
  const form = new FormData();
  form.append('documents', new File([blobPart(await makePdf(['PRIVATE']))], 'Private.pdf', { type: 'application/pdf' }));
  form.append('signers_json', JSON.stringify([{ user_id: 'recipient', role: 'Signer', order: 0 }]));
  form.append('fields_json', '[]');
  const envelope = await (await h.fetch('/api/submissions/adhoc', { method: 'POST', body: form, cookie })).json() as any;
  const document = h.db.prepare(`SELECT id FROM submission_documents WHERE submission_id = ?`).get(envelope.id) as any;
  assert.equal((await h.fetch(`/api/files/submission-document/${document.id}`)).status, 404);
});

test('A-902 · sender safely replaces the ordered set before signing and the old documents disappear', async () => {
  const h = newHarness();
  const cookie = ownerSession(h);
  const create = new FormData();
  create.append('documents', new File([blobPart(await makePdf(['OLD']))], 'Old.pdf', { type: 'application/pdf' }));
  create.append('title', 'Replace me');
  create.append('signers_json', JSON.stringify([{ user_id: 'recipient', role: 'Signer', order: 0 }]));
  create.append('fields_json', '[]');
  const created = await h.fetch('/api/submissions/adhoc', { method: 'POST', body: create, cookie });
  const envelope = await created.json() as any;
  const oldDocument = h.db.prepare(`SELECT id FROM submission_documents WHERE submission_id = ?`).get(envelope.id) as any;

  const replacement = new FormData();
  replacement.append('documents', new File([blobPart(await makePdf(['BENEFITS']))], 'Benefits.pdf', { type: 'application/pdf' }));
  replacement.append('documents', new File([blobPart(await makePdf(['OFFER']))], 'Offer.pdf', { type: 'application/pdf' }));
  const replaced = await h.fetch(`/api/submissions/${envelope.id}/replace-document`, {
    method: 'POST', body: replacement, cookie,
  });
  assert.equal(replaced.status, 200, await replaced.clone().text());
  assert.equal((await h.fetch(`/api/files/submission-document/${oldDocument.id}`, { cookie })).status, 404);
  const manifest = await (await h.fetch(`/api/submissions/${envelope.id}/documents`, { cookie })).json() as any[];
  assert.deepEqual(manifest.map((d) => d.filename), ['Benefits.pdf', 'Offer.pdf']);
  const preview = await h.fetch(`/api/files/document-preview/${envelope.id}`, { cookie });
  assert.deepEqual((await readPdf(new Uint8Array(await preview.arrayBuffer()))).pages.map((page) => page.join('')), ['BENEFITS', 'OFFER']);
  const event = h.db.prepare(`SELECT details_json FROM audit_events WHERE submission_id = ? AND event_type = 'document_replaced'`).get(envelope.id) as any;
  assert.deepEqual(JSON.parse(event.details_json).documents, ['Benefits.pdf', 'Offer.pdf']);

  const copied = await h.fetch(`/api/submissions/${envelope.id}/copy`, { method: 'POST', cookie });
  assert.equal(copied.status, 201);
  const copy = await copied.json() as any;
  const copyManifest = await (await h.fetch(`/api/submissions/${copy.id}/documents`, { cookie })).json() as any[];
  assert.deepEqual(copyManifest.map((d) => d.filename), ['Benefits.pdf', 'Offer.pdf']);
});

test('A-903 · replacement is refused after any signer finishes and when it strands placed fields', async () => {
  const h = newHarness();
  const cookie = ownerSession(h);
  const create = new FormData();
  create.append('documents', new File([blobPart(await makePdf(['ONE', 'TWO']))], 'TwoPages.pdf', { type: 'application/pdf' }));
  create.append('signers_json', JSON.stringify([{ user_id: 'recipient', role: 'Signer', order: 0 }]));
  create.append('fields_json', JSON.stringify([{ id: 'field', role: 'Signer', type: 'signature', page: 1, x: .1, y: .1, w: .2, h: .1 }]));
  const envelope = await (await h.fetch('/api/submissions/adhoc', { method: 'POST', body: create, cookie })).json() as any;
  const onePage = () => {
    const form = new FormData();
    form.append('documents', new File([blobPart(new Uint8Array())], 'placeholder.pdf', { type: 'application/pdf' }));
    return form;
  };
  const short = new FormData();
  short.append('documents', new File([blobPart(await makePdf(['ONE']))], 'OnePage.pdf', { type: 'application/pdf' }));
  assert.equal((await h.fetch(`/api/submissions/${envelope.id}/replace-document`, { method: 'POST', body: short, cookie })).status, 422);
  assert.equal((h.db.prepare(`SELECT filename FROM submission_documents WHERE submission_id = ?`).get(envelope.id) as any).filename, 'TwoPages.pdf');

  h.db.prepare(`UPDATE submitters SET status = 'signed' WHERE submission_id = ?`).run(envelope.id);
  assert.equal((await h.fetch(`/api/submissions/${envelope.id}/replace-document`, { method: 'POST', body: onePage(), cookie })).status, 409);
});

test('A-904 · TXT and CSV normalize locally and participate in an ordered envelope', async () => {
  const h = newHarness();
  const cookie = ownerSession(h);
  const form = new FormData();
  form.append('documents', new File(['EMPLOYMENT TERMS\nSalary and start date'], 'Terms.txt', { type: 'text/plain' }));
  form.append('documents', new File(['Benefit,Selection\nMedical,Yes'], 'Benefits.csv', { type: 'text/csv' }));
  form.append('signers_json', JSON.stringify([{ user_id: 'recipient', role: 'Signer', order: 0 }]));
  form.append('fields_json', '[]');
  const created = await h.fetch('/api/submissions/adhoc', { method: 'POST', body: form, cookie });
  assert.equal(created.status, 201, await created.clone().text());
  const envelope = await created.json() as any;
  const manifest = await (await h.fetch(`/api/submissions/${envelope.id}/documents`, { cookie })).json() as any[];
  assert.deepEqual(manifest.map((d) => [d.filename, d.page_count]), [['Terms.txt', 1], ['Benefits.csv', 1]]);
  const preview = await h.fetch(`/api/files/document-preview/${envelope.id}`, { cookie });
  const pdf = await readPdf(new Uint8Array(await preview.arrayBuffer()));
  assert.match(pdf.pages[0].join(' '), /EMPLOYMENT TERMS/);
  assert.match(pdf.pages[1].join(' '), /Benefit,Selection/);
});
