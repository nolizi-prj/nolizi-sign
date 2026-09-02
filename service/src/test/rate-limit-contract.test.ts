import { test } from 'node:test';
import assert from 'node:assert/strict';

import { newHarness } from './support/durable-harness.js';

function seedCode(h: ReturnType<typeof newHarness>, key: string, code = '123456'): void {
  h.db.prepare(`INSERT INTO auth_codes (id, email, code, expires_at, created_at) VALUES (?, ?, ?, ?, ?)`)
    .run(crypto.randomUUID(), key, code, new Date(Date.now() + 600_000).toISOString(), new Date().toISOString());
}

test('A-950 · login verification is limited by both email and source IP and returns Retry-After', async () => {
  const h = newHarness();
  seedCode(h, 'target@example.test');
  const attempt = (email: string, ip: string, code = '000000') => h.fetch('/api/auth/login/verify', {
    method: 'POST',
    headers: { 'cf-connecting-ip': ip },
    body: JSON.stringify({ email, code }),
  });
  for (let i = 0; i < 6; i++) assert.equal((await attempt('target@example.test', '203.0.113.10')).status, 401);
  const targetLocked = await attempt('target@example.test', '203.0.113.11', '123456');
  assert.equal(targetLocked.status, 429, 'rotating IP bypassed the email bucket');
  assert.ok(Number(targetLocked.headers.get('retry-after')) > 0);
  assert.equal((await attempt('another@example.test', '203.0.113.10')).status, 429, 'rotating email bypassed the IP bucket');
  assert.ok(h.db.prepare(`SELECT id FROM auth_codes WHERE email = ?`).get('target@example.test'), 'lockout consumed the valid code');
});

test('A-951 · signer verification has an independent persistent attempt budget', async () => {
  const h = newHarness();
  const now = new Date().toISOString();
  h.db.prepare(`INSERT INTO submissions (id, public_uid, title, created_by, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)`)
    .run('env', 'public', 'Offer', 'owner@example.test', 'pending', now, now);
  h.db.prepare(`INSERT INTO submitters (id, submission_id, name, email, role, token, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`)
    .run('signer', 'env', 'Signer', 'signer@example.test', 'Signer', 'access-token', 'pending', now);
  seedCode(h, 'signer:signer');
  const attempt = (code = '000000') => h.fetch('/api/sign/token/access-token/verify', {
    method: 'POST', headers: { 'cf-connecting-ip': '198.51.100.8' }, body: JSON.stringify({ code }),
  });
  for (let i = 0; i < 6; i++) assert.equal((await attempt()).status, 401);
  assert.equal((await attempt('123456')).status, 429);
  assert.equal((h.db.prepare(`SELECT COUNT(*) AS n FROM signer_sessions`).get() as any).n, 0);
});

test('A-952 · anonymous document-write floods are stopped before upload parsing', async () => {
  const h = newHarness();
  const request = () => h.fetch('/api/submissions/adhoc/merged-document', {
    method: 'POST', headers: { 'cf-connecting-ip': '192.0.2.4' }, body: new FormData(),
  });
  for (let i = 0; i < 30; i++) assert.equal((await request()).status, 401);
  const blocked = await request();
  assert.equal(blocked.status, 429);
  assert.ok(Number(blocked.headers.get('retry-after')) > 0);
});
