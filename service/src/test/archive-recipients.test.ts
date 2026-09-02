import { test } from 'node:test';
import assert from 'node:assert/strict';
import { cookieValue, newHarness } from './support/durable-harness.js';

async function signIn(): Promise<{ h: ReturnType<typeof newHarness>; cookie: string }> {
  const h = newHarness();
  const now = new Date();
  h.db.prepare(`INSERT INTO auth_codes (id, email, code, expires_at, created_at) VALUES (?, ?, ?, ?, ?)`)
    .run('code-archive', 'owner@pumasi.ai', '123456', new Date(now.getTime() + 600_000).toISOString(), now.toISOString());
  const response = await h.fetch('/api/auth/login/verify', {
    method: 'POST',
    body: JSON.stringify({ email: 'owner@pumasi.ai', code: '123456', name: 'Owner' }),
  });
  const token = cookieValue(response, 'sign_session');
  assert.ok(token);
  return { h, cookie: `sign_session=${token}` };
}

test('A-980 archive recipients are authenticated, normalized, deduplicated, and persisted', async () => {
  const { h, cookie } = await signIn();
  const unauthenticated = await h.fetch('/api/admin/archive-recipients');
  assert.equal(unauthenticated.status, 401);

  const saved = await h.fetch('/api/admin/archive-recipients', {
    method: 'PUT', cookie,
    body: JSON.stringify({ emails: [' Records@Example.com ', 'records@example.com', 'legal@example.com'] }),
  });
  assert.equal(saved.status, 200);
  assert.deepEqual(await saved.json(), ['records@example.com', 'legal@example.com']);

  const loaded = await h.fetch('/api/admin/archive-recipients', { cookie });
  assert.equal(loaded.status, 200);
  assert.deepEqual(await loaded.json(), ['legal@example.com', 'records@example.com']);
});

test('A-981 archive recipients reject invalid, owner, and oversized lists', async () => {
  const { h, cookie } = await signIn();
  for (const emails of [
    ['not-an-email'],
    ['owner@pumasi.ai'],
    Array.from({ length: 11 }, (_, index) => `archive-${index}@example.com`),
  ]) {
    const response = await h.fetch('/api/admin/archive-recipients', {
      method: 'PUT', cookie, body: JSON.stringify({ emails }),
    });
    assert.equal(response.status, 400);
  }
});
