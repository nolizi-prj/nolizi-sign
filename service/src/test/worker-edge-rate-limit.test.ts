import { test } from 'node:test';
import assert from 'node:assert/strict';

import worker from '../worker.js';
import { APP_VERSION } from '../version.js';
import { newHarness } from './support/durable-harness.js';

function edgeHarness() {
  const durable = newHarness();
  const env = {
    SIGN_SERVICE: {
      idFromName: () => ({ toString: () => 'main' }),
      get: () => ({ fetch: (req: Request) => durable.service.fetch(req) }),
    },
  } as any;
  return { durable, env };
}

test('A-953 · Worker feedback uses the persistent DO limit before GitHub work', async () => {
  const { env } = edgeHarness();
  const send = () => worker.fetch(new Request('https://sign.example.test/api/feedback', {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'cf-connecting-ip': '203.0.113.50' },
    body: JSON.stringify({ message: 'feedback' }),
  }), env);
  for (let i = 0; i < 5; i++) assert.equal((await send()).status, 500);
  const blocked = await send();
  assert.equal(blocked.status, 429);
  assert.ok(Number(blocked.headers.get('retry-after')) > 0);
});

test('A-955 · authenticated pilot reviewers can submit thirty feedback reports per hour', async () => {
  const { durable, env } = edgeHarness();
  const now = new Date().toISOString();
  durable.db.prepare(`INSERT INTO users (id, email, name, provider, created_at) VALUES (?, ?, ?, ?, ?)`)
    .run('reviewer', 'reviewer@example.test', 'Reviewer', 'email', now);
  durable.db.prepare(`INSERT INTO sessions (token, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)`)
    .run('review-session', 'reviewer', new Date(Date.now() + 86_400_000).toISOString(), now);
  const send = () => worker.fetch(new Request('https://sign.example.test/api/feedback', {
    method: 'POST',
    headers: { 'content-type': 'application/json', cookie: 'sign_session=review-session', 'cf-connecting-ip': '203.0.113.51' },
    body: JSON.stringify({ message: 'pilot feedback' }),
  }), env);
  for (let i = 0; i < 30; i++) assert.equal((await send()).status, 500);
  assert.equal((await send()).status, 429);
});

test('A-954 · standalone conversion is limited even when Graph is not configured', async () => {
  const { env } = edgeHarness();
  const send = () => worker.fetch(new Request('https://sign.example.test/api/convert', {
    method: 'POST', headers: { 'cf-connecting-ip': '198.51.100.50' },
  }), env);
  for (let i = 0; i < 20; i++) assert.equal((await send()).status, 501);
  const blocked = await send();
  assert.equal(blocked.status, 429);
  assert.ok(Number(blocked.headers.get('retry-after')) > 0);
});

test('A-962 · liveness is shallow while readiness verifies Durable Object and R2', async () => {
  const { env } = edgeHarness();
  assert.equal((await worker.fetch(new Request('https://sign.example.test/api/health'), env)).status, 200);
  assert.equal((await worker.fetch(new Request('https://sign.example.test/api/ready'), env)).status, 503);

  let listed = 0;
  env.DOCUMENTS = { async list(options: any) { listed++; assert.equal(options.limit, 1); return { objects: [] }; } };
  const ready = await worker.fetch(new Request('https://sign.example.test/api/ready'), env);
  assert.equal(ready.status, 200);
  assert.deepEqual(await ready.json(), { status: 'ready', service: 'pumasi-sign', version: APP_VERSION });
  assert.equal(listed, 1);
});

test('A-963 · readiness fails closed without exposing dependency details', async () => {
  const { env } = edgeHarness();
  env.DOCUMENTS = { async list() { throw new Error('secret bucket failure'); } };
  const response = await worker.fetch(new Request('https://sign.example.test/api/ready', {
    headers: { 'cf-ray': 'test-ray' },
  }), env);
  assert.equal(response.status, 503);
  assert.deepEqual(await response.json(), {
    status: 'unavailable', service: 'pumasi-sign', request_id: 'test-ray',
  });
});
