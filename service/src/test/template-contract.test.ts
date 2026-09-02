/** Frozen acceptance cases A-700–A-703 · spec/0012. */

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { newHarness, cookieValue, Harness } from './support/durable-harness.js';
import { fakeBucket, makePdf } from './support/pdf-probe.js';

let seq = 0;
const uid = (prefix: string) => `${prefix}-${++seq}`;

function seedCode(h: Harness, email: string): void {
  const now = new Date();
  h.db.prepare(`INSERT INTO auth_codes (id, email, code, expires_at, created_at) VALUES (?, ?, ?, ?, ?)`).run(
    uid('code'), email, '123456', new Date(now.getTime() + 600_000).toISOString(), now.toISOString(),
  );
}

async function signIn(h: Harness, email: string, name: string): Promise<string> {
  seedCode(h, email);
  const res = await h.fetch('/api/auth/login/verify', {
    method: 'POST', body: JSON.stringify({ email, name, code: '123456' }),
  });
  assert.equal(res.status, 200);
  const token = cookieValue(res, 'sign_session');
  assert.ok(token);
  return `sign_session=${token}`;
}

async function uploadTemplate(h: Harness, cookie: string, name = 'Master NDA'): Promise<any> {
  const form = new FormData();
  form.set('name', name);
  const pdf = await makePdf(['TEMPLATE SOURCE']);
  form.set('file', new File([new Uint8Array(pdf).buffer], 'source.pdf', { type: 'application/pdf' }));
  const res = await h.fetch('/api/templates', { method: 'POST', cookie, body: form });
  assert.equal(res.status, 201);
  return res.json();
}

test('A-700 · multipart upload, get, PDF, field autosave and archive match the Vue contract', async () => {
  const h = newHarness();
  const owner = await signIn(h, 'owner@pumasi.ai', 'Owner');
  const created = await uploadTemplate(h, owner);
  assert.equal(created.name, 'Master NDA');
  assert.equal(created.page_count, 1);
  assert.equal(created.owner.email, 'owner@pumasi.ai');

  const field = {
    id: 'field-1', type: 'signature', role: 'Client', page: 0,
    x: 0.1, y: 0.2, w: 0.3, h: 0.08, required: true,
  };
  const saved = await h.fetch(`/api/templates/${created.id}/fields`, {
    method: 'PUT', cookie: owner, body: JSON.stringify({ fields: [field], roles: ['Client'] }),
  });
  assert.equal(saved.status, 200);
  assert.deepEqual((await saved.json() as any).roles, ['Client']);
  assert.equal((await h.fetch(`/api/files/template-pdf/${created.id}`, { cookie: owner })).status, 200);

  assert.equal((await h.fetch(`/api/templates/${created.id}/archive`, { method: 'POST', cookie: owner })).status, 200);
  assert.deepEqual(await (await h.fetch('/api/templates', { cookie: owner })).json(), []);
  assert.equal((await h.fetch(`/api/templates/${created.id}`, { cookie: owner })).status, 404);
  const archived = await (await h.fetch('/api/templates?archived=true', { cookie: owner })).json() as any[];
  assert.equal(archived.length, 1);
  assert.equal(archived[0].id, created.id);
  assert.ok(archived[0].archived_at);
  assert.equal((await h.fetch(`/api/templates/${created.id}/unarchive`, { method: 'POST', cookie: owner })).status, 200);
  assert.deepEqual(await (await h.fetch('/api/templates?archived=true', { cookie: owner })).json(), []);
  assert.equal((await (await h.fetch('/api/templates', { cookie: owner })).json() as any[])[0].id, created.id);
});

test('A-701 · a template is visible only to explicitly invited email and remains use-only', async () => {
  const bucket = fakeBucket();
  const h = newHarness({ DOCUMENTS: bucket as any });
  const owner = await signIn(h, 'owner@pumasi.ai', 'Owner');
  const teammate = await signIn(h, 'teammate@pumasi.ai', 'Teammate');
  const stranger = await signIn(h, 'stranger@pumasi.ai', 'Stranger');
  const created = await uploadTemplate(h, owner, 'Shared NDA');
  const shared = await h.fetch(`/api/templates/${created.id}/sharing`, {
    method: 'PUT', cookie: owner, body: JSON.stringify({ emails: ['teammate@pumasi.ai'] }),
  });
  assert.equal(shared.status, 200);

  const visible = await (await h.fetch('/api/templates', { cookie: teammate })).json() as any[];
  assert.equal(visible.length, 1);
  assert.equal(visible[0].owner.email, 'owner@pumasi.ai');
  assert.deepEqual(await (await h.fetch('/api/templates', { cookie: stranger })).json(), []);
  assert.equal((await h.fetch(`/api/templates/${created.id}`, { cookie: stranger })).status, 404);
  assert.equal((await h.fetch(`/api/files/template-pdf/${created.id}`, { cookie: stranger })).status, 404);
  assert.equal((await h.fetch(`/api/templates/${created.id}/fields`, {
    method: 'PUT', cookie: teammate, body: JSON.stringify({ fields: [] }),
  })).status, 403);
  assert.equal((await h.fetch(`/api/templates/${created.id}/archive`, { method: 'POST', cookie: teammate })).status, 403);
  assert.equal((await h.fetch(`/api/templates/${created.id}/sharing`, {
    method: 'PUT', cookie: teammate, body: JSON.stringify({ emails: [] }),
  })).status, 403);

  const copiedRes = await h.fetch(`/api/templates/${created.id}/copy`, { method: 'POST', cookie: teammate });
  assert.equal(copiedRes.status, 201);
  const copied = await copiedRes.json() as any;
  assert.equal(copied.name, 'Copy of Shared NDA');
  assert.equal(copied.shared, false);
  assert.equal(copied.owner.email, 'teammate@pumasi.ai');
  const keys = h.db.prepare(`SELECT pdf_key FROM templates WHERE id IN (?, ?) ORDER BY id`).all(created.id, copied.id) as any[];
  assert.equal(new Set(keys.map((r) => r.pdf_key)).size, 2, 'the copy shares its source R2 key');
});

test('A-702 · a shared template can create an envelope for another sender', async () => {
  const h = newHarness();
  const owner = await signIn(h, 'owner@pumasi.ai', 'Owner');
  const teammate = await signIn(h, 'teammate@pumasi.ai', 'Teammate');
  const created = await uploadTemplate(h, owner, 'Sendable NDA');
  await h.fetch(`/api/templates/${created.id}/fields`, {
    method: 'PUT', cookie: owner,
    body: JSON.stringify({ fields: [{ id: 'f1', type: 'signature', role: 'Client', page: 0, x: .1, y: .2, w: .3, h: .1, required: true }], roles: ['Client'] }),
  });
  await h.fetch(`/api/templates/${created.id}/sharing`, { method: 'PUT', cookie: owner, body: JSON.stringify({ emails: ['teammate@pumasi.ai'] }) });
  const recipient = await (await h.fetch('/api/users', {
    method: 'POST', cookie: teammate, body: JSON.stringify({ email: 'client@example.test', name: 'Client Person' }),
  })).json() as any;
  const sent = await h.fetch('/api/submissions', {
    method: 'POST', cookie: teammate,
    body: JSON.stringify({ template_id: created.id, title: 'Client NDA', draft: true, signers: [{ role: 'Client', user_id: recipient.id }] }),
  });
  assert.equal(sent.status, 201);
  const envelope = await sent.json() as any;
  assert.equal(envelope.status, 'draft');
  assert.match(envelope.public_uid, /^[0-9A-F]{8}-[0-9A-F]{4}-4[0-9A-F]{3}-[89AB][0-9A-F]{3}-[0-9A-F]{12}$/);

  await h.fetch(`/api/templates/${created.id}/sharing`, { method: 'PUT', cookie: owner, body: JSON.stringify({ emails: [] }) });
  assert.deepEqual(await (await h.fetch('/api/templates', { cookie: teammate })).json(), []);
  assert.equal((await h.fetch('/api/submissions', {
    method: 'POST', cookie: teammate,
    body: JSON.stringify({ template_id: created.id, title: 'No longer allowed', draft: true, signers: [{ role: 'Client', user_id: recipient.id }] }),
  })).status, 404);
});

test('A-703 · save-as-template copies document and fields into generic ordered roles', async () => {
  const bucket = fakeBucket();
  const h = newHarness({ DOCUMENTS: bucket as any });
  const owner = await signIn(h, 'owner@pumasi.ai', 'Owner');
  const id = 'sub-save-template';
  const now = new Date().toISOString();
  const pdf = await makePdf(['SIGNED WORKFLOW']);
  bucket.objects.set('originals/source.pdf', { data: pdf, contentType: 'application/pdf' });
  h.db.prepare(`INSERT INTO submissions (id, public_uid, title, created_by, status, original_pdf_key, page_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'completed', ?, 1, ?, ?)`).run(id, 'public-save', 'Reusable Deal', 'owner@pumasi.ai', 'originals/source.pdf', now, now);
  h.db.prepare(`INSERT INTO submitters (id, submission_id, name, email, role, signing_order, token, status, is_cc, created_at)
                VALUES ('s1', ?, 'Alice', 'alice@example.test', 'buyer', 1, 'tok1', 'signed', 0, ?)`).run(id, now);
  h.db.prepare(`INSERT INTO submitters (id, submission_id, name, email, role, signing_order, token, status, is_cc, created_at)
                VALUES ('s2', ?, 'Bob', 'bob@example.test', 'seller', 2, 'tok2', 'signed', 0, ?)`).run(id, now);
  h.db.prepare(`INSERT INTO submission_fields (id, submission_id, submitter_id, type, page, x, y, width, height, required, field_role)
                VALUES ('f1', ?, 's1', 'signature', 0, .1, .2, .3, .1, 1, 'buyer')`).run(id);
  const saved = await h.fetch(`/api/submissions/${id}/save-as-template`, { method: 'POST', cookie: owner });
  assert.equal(saved.status, 201);
  const template = await saved.json() as any;
  assert.equal(template.name, 'Reusable Deal');
  assert.deepEqual(template.roles, ['Signer 1', 'Signer 2']);
  assert.equal(template.fields[0].role, 'Signer 1');
  const source = h.db.prepare(`SELECT original_pdf_key FROM submissions WHERE id = ?`).get(id) as any;
  const copy = h.db.prepare(`SELECT pdf_key FROM templates WHERE id = ?`).get(template.id) as any;
  assert.notEqual(copy.pdf_key, source.original_pdf_key);
});
