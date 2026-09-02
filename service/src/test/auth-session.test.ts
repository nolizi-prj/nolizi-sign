/**
 * Frozen acceptance cases A-300 – A-308 · spec/0004.
 *
 * The first tests in this repository that construct the Durable Object which
 * answers sign.pumasi.ai and drive it through its own `fetch()` entrypoint.
 * They CHARACTERIZE `establishSession` (durable.ts:655) and the `sign_session`
 * cookie it mints: they record what the deployed tree does today.
 *
 * THEY DO NOT ADJUDICATE. `pumasi/DECISIONS.md` Q-018 asks which of this
 * repository's two backends *is* Pumasi Sign, and the two disagree about who
 * may hold an account. That question is the steward's. A-302 and A-308 mark
 * the assertions that sit on the divergence: red there means somebody
 * answered Q-018, not that somebody broke the worker. See spec/0004 §S4.
 *
 * Read spec/0004/SPEC.md §S1c before trusting a green run: this is SQLite, but
 * it is not workerd's SQLite, and these are assertions about durable.ts's own
 * logic rather than about Cloudflare's storage engine.
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { newHarness, cookieValue, Harness } from './support/durable-harness.js';

/** Put a live verification code in `auth_codes`, the way issueCode would. */
function seedCode(h: Harness, email: string, code = '123456', ttlMs = 10 * 60_000): void {
  h.db.prepare(
    `INSERT INTO auth_codes (id, email, code, expires_at, created_at) VALUES (?, ?, ?, ?, ?)`,
  ).run(
    `code-${Math.random().toString(16).slice(2)}`, email, code,
    new Date(Date.now() + ttlMs).toISOString(), new Date().toISOString(),
  );
}

/** The route that reaches establishSession on the email path (durable.ts:798). */
function verify(h: Harness, email: string, body: Record<string, unknown> = {}): Promise<Response> {
  return h.fetch('/api/auth/login/verify', {
    method: 'POST',
    body: JSON.stringify({ email, code: '123456', ...body }),
  });
}

const count = (h: Harness, table: string): number =>
  (h.db.prepare(`SELECT count(*) AS n FROM ${table}`).get() as { n: number }).n;

/** Sign in cleanly and hand back the session cookie value. */
async function signIn(h: Harness, email: string, body: Record<string, unknown> = {}): Promise<string> {
  seedCode(h, email);
  const res = await verify(h, email, body);
  assert.equal(res.status, 200);
  const token = cookieValue(res, 'sign_session');
  assert.ok(token, 'sign-in did not set a sign_session cookie');
  return token;
}

// ── A-300 · the reader guard ────────────────────────────────────────────────
//
// Every other case here touches at most four tables. A harness that built only
// those would leave all eight green while the object they claim to exercise was
// never really constructed. This is not hypothetical: the first draft of the
// shim routed no-binding statements through node:sqlite's `prepare`, which
// does NOT reject a multi-statement string — it silently keeps the first — and
// the database came up with `users` alone. spec/0004 §S1, and L-006.

test('A-300 the harness constructs the real Durable Object: whole schema, migrations, routing', async () => {
  const h = newHarness();

  const tables = (h.db.prepare(
    `SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name`,
  ).all() as Array<{ name: string }>).map((r) => r.name);

  // Every table durable.ts's initSchema declares.
  for (const expected of [
    'archive_recipients', 'attachments', 'audit_events', 'auth_codes', 'org_branding', 'rate_limit_events', 'recipients', 'sessions',
    'signatures', 'signer_consents', 'signer_sessions', 'submission_documents', 'submission_fields', 'submissions',
    'submitters', 'team_members', 'template_shares', 'templates', 'users',
  ]) {
    assert.ok(tables.includes(expected), `initSchema did not create ${expected}; got ${tables.join(',')}`);
  }
  assert.equal(tables.length, 19, 'the schema is no longer nineteen tables — A-300 must be re-read');

  // The ALTER TABLE migration loop (durable.ts:254) ran too, not just the CREATEs.
  const submitterCols = (h.db.prepare(
    `SELECT name FROM pragma_table_info('submitters')`,
  ).all() as Array<{ name: string }>).map((r) => r.name);
  for (const col of ['recipient_id', 'is_cc', 'last_reminded_at', 'reminder_count']) {
    assert.ok(submitterCols.includes(col), `migration column submitters.${col} is missing`);
  }

  // And the object routes: an unknown path answers with the worker's own body,
  // which is what a user meets today on any path service/ does not serve.
  const res = await h.fetch('/api/definitely-not-a-route');
  assert.equal(res.status, 404);
  assert.deepEqual(await res.json(), { error: 'Endpoint not found' });
});

// ── A-301 · sign-in mints a session, and that session is what /me accepts ───

test('A-301 verifying an emailed code creates the account, sets sign_session, and /api/auth/me accepts it', async () => {
  const h = newHarness();
  seedCode(h, 'someone@pumasi.ai');

  const res = await verify(h, 'someone@pumasi.ai');
  assert.equal(res.status, 200);
  const body = await res.json() as { ok: boolean; user: { id: string; email: string } };
  assert.equal(body.ok, true);
  assert.equal(body.user.email, 'someone@pumasi.ai');

  assert.equal(count(h, 'users'), 1);
  assert.equal(count(h, 'sessions'), 1);

  const token = cookieValue(res, 'sign_session');
  assert.ok(token);
  const stored = h.db.prepare(`SELECT user_id FROM sessions WHERE token = ?`).get(token) as
    { user_id: string } | undefined;
  assert.ok(stored, 'the cookie names a token with no row in sessions');
  assert.equal(stored.user_id, body.user.id);

  const me = await h.fetch('/api/auth/me', { cookie: `sign_session=${token}` });
  assert.equal(me.status, 200);
  const meBody = await me.json() as { id: string; email: string };
  assert.equal(meBody.id, body.user.id);
  assert.equal(meBody.email, 'someone@pumasi.ai');
});

// ── A-302 · the Q-018 divergence, recorded and not endorsed ─────────────────

test('A-302 establishSession admits a verified email at any domain — recorded, not endorsed (Q-018)', async () => {
  const h = newHarness();
  seedCode(h, 'stranger@example.com');

  const res = await verify(h, 'stranger@example.com');

  // WHAT THIS ASSERTS AND WHAT IT DOES NOT.
  //
  // The worker's establishSession (durable.ts:655) creates an account for any
  // verified email, with no domain gate. backend/ does not: it gates on
  // ALLOWED_EMAIL_DOMAINS (default pumasi.ai) at backend/app/routers/auth.py.
  // Which of the two is Pumasi Sign is pumasi/DECISIONS.md Q-018 — open, and
  // the steward's, not this suite's.
  //
  // So this case RECORDS the deployed rule. It does not claim the rule is
  // right. If a steward answers Q-018 in backend/'s favour and a domain gate
  // arrives here, THIS CASE GOING RED IS THE CORRECT OUTCOME: delete it with
  // the change, and do not treat it as a regression. spec/0004 §S4a.
  assert.equal(res.status, 200);
  const row = h.db.prepare(`SELECT email, provider FROM users`).get() as
    { email: string; provider: string } | undefined;
  assert.ok(row, 'no account was created for a non-pumasi.ai address');
  assert.equal(row.email, 'stranger@example.com');
  assert.equal(row.provider, 'email');
});

// ── A-303 · find-first ──────────────────────────────────────────────────────

test('A-303 a second sign-in reuses the account and does not refresh its name or provider', async () => {
  const h = newHarness();
  await signIn(h, 'repeat@pumasi.ai', { name: 'First Name' });

  seedCode(h, 'repeat@pumasi.ai');
  const second = await verify(h, 'repeat@pumasi.ai', { name: 'Totally Different' });
  assert.equal(second.status, 200);

  assert.equal(count(h, 'users'), 1, 'a second sign-in created a second account');
  const row = h.db.prepare(`SELECT name, provider FROM users`).get() as
    { name: string; provider: string };
  // Find-first: the row that exists wins, and the newer sign-in's display name
  // is discarded. Characterization — see spec/0004 §S2c.
  assert.equal(row.name, 'First Name');
  assert.equal(row.provider, 'email');

  assert.equal(count(h, 'sessions'), 2, 'the second sign-in did not mint its own session');
  assert.equal(count(h, 'org_branding'), 1, 'a workspace was created twice for one account');
});

// ── A-304 · case normalisation ──────────────────────────────────────────────

test('A-304 the address is lower-cased before the code check and the account lookup', async () => {
  const h = newHarness();
  seedCode(h, 'mixed@pumasi.ai');

  const res = await verify(h, 'MiXeD@Pumasi.AI');
  assert.equal(res.status, 200, 'mixed-case input did not match a code issued lower-cased');

  assert.equal(count(h, 'users'), 1);
  const row = h.db.prepare(`SELECT email FROM users`).get() as { email: string };
  assert.equal(row.email, 'mixed@pumasi.ai');
});

// ── A-305 · the display name ────────────────────────────────────────────────

test('A-305 the display name comes from the body verbatim, or is derived from the local part', async () => {
  const derived = newHarness();
  seedCode(derived, 'first.last@pumasi.ai');
  await verify(derived, 'first.last@pumasi.ai');
  assert.equal(
    (derived.db.prepare(`SELECT name FROM users`).get() as { name: string }).name,
    'First Last',
  );

  const given = newHarness();
  seedCode(given, 'given@pumasi.ai');
  await verify(given, 'given@pumasi.ai', { name: '  Padded Name  ' });
  // Verbatim: untrimmed and uncapped on this path, where the OAuth path one
  // branch above caps at 120 characters (durable.ts:769). Recorded here and
  // proposed as a backlog entry in spec/0004 §S6 — not repaired in a test
  // packet.
  assert.equal(
    (given.db.prepare(`SELECT name FROM users`).get() as { name: string }).name,
    '  Padded Name  ',
  );
});

// ── A-306 · what the cookie admits ──────────────────────────────────────────

test('A-306 the sign_session cookie admits a live token and nothing else', async () => {
  const h = newHarness();
  const token = await signIn(h, 'gate@pumasi.ai');

  const anonymous = await h.fetch('/api/auth/me');
  assert.equal(anonymous.status, 401);
  assert.deepEqual(await anonymous.json(), { error: 'Not signed in' });

  const unknown = await h.fetch('/api/auth/me', { cookie: 'sign_session=not-a-real-token' });
  assert.equal(unknown.status, 401);

  assert.equal((await h.fetch('/api/auth/me', { cookie: `sign_session=${token}` })).status, 200);

  // Expiry is enforced on read, from the stored expires_at.
  h.db.prepare(`UPDATE sessions SET expires_at = ? WHERE token = ?`)
    .run(new Date(Date.now() - 1000).toISOString(), token);
  const expired = await h.fetch('/api/auth/me', { cookie: `sign_session=${token}` });
  assert.equal(expired.status, 401);

  // Sign out drops the presented token and clears the cookie.
  const fresh = newHarness();
  const live = await signIn(fresh, 'out@pumasi.ai');
  const out = await fresh.fetch('/api/auth/logout', { method: 'POST', cookie: `sign_session=${live}` });
  assert.equal(out.status, 200);
  assert.equal(cookieValue(out, 'sign_session'), '');
  assert.equal(count(fresh, 'sessions'), 0);
  assert.equal((await fresh.fetch('/api/auth/me', { cookie: `sign_session=${live}` })).status, 401);
});

// ── A-307 · account creation sits behind the code check ─────────────────────

test('A-307 no code, no account: a wrong, expired or foreign code creates nothing, and a good one is single-use', async () => {
  const wrong = newHarness();
  seedCode(wrong, 'wrong@pumasi.ai');
  assert.equal((await verify(wrong, 'wrong@pumasi.ai', { code: '999999' })).status, 401);
  assert.equal(count(wrong, 'users'), 0, 'a failed verification created an account');
  assert.equal(count(wrong, 'sessions'), 0);

  const stale = newHarness();
  seedCode(stale, 'stale@pumasi.ai', '123456', -1000);
  assert.equal((await verify(stale, 'stale@pumasi.ai')).status, 401);
  assert.equal(count(stale, 'users'), 0, 'an expired code created an account');

  // A code is bound to the address it was issued for.
  const foreign = newHarness();
  seedCode(foreign, 'victim@pumasi.ai');
  assert.equal((await verify(foreign, 'attacker@pumasi.ai')).status, 401);
  assert.equal(count(foreign, 'users'), 0, 'a code issued for another address created an account');

  // And it is spent on use.
  const once = newHarness();
  seedCode(once, 'once@pumasi.ai');
  assert.equal((await verify(once, 'once@pumasi.ai')).status, 200);
  assert.equal((await verify(once, 'once@pumasi.ai')).status, 401, 'the code was replayable');
  assert.equal(count(once, 'users'), 1);
});

// ── A-308 · the cookie's shape, session lifetime, and the reported identity ──

test('A-308 cookie attributes, sessions that are neither rotated nor reaped, and the identity /me reports', async () => {
  const h = newHarness();
  seedCode(h, 'shape@pumasi.ai');
  const res = await verify(h, 'shape@pumasi.ai');

  const raw = res.headers.getSetCookie().find((c) => c.startsWith('sign_session='));
  assert.ok(raw, 'no sign_session cookie was set');
  const token = cookieValue(res, 'sign_session')!;
  assert.match(token, /^[0-9a-f]{64}$/, 'the session token is not 32 random bytes in hex');
  for (const attr of ['Path=/', 'HttpOnly', 'Secure', 'SameSite=Lax', 'Max-Age=2592000']) {
    assert.ok(raw.includes(attr), `the session cookie is missing ${attr}: ${raw}`);
  }

  // Not rotated: a cookie minted before a later sign-in stays valid.
  seedCode(h, 'shape@pumasi.ai');
  const again = await verify(h, 'shape@pumasi.ai');
  const newer = cookieValue(again, 'sign_session');
  assert.notEqual(newer, token);
  assert.equal((await h.fetch('/api/auth/me', { cookie: `sign_session=${token}` })).status, 200,
    'the older session was invalidated — behaviour changed, re-read spec/0004 §S2i');

  // Not reaped: rejecting an expired session does not delete its row.
  h.db.prepare(`UPDATE sessions SET expires_at = ? WHERE token = ?`)
    .run(new Date(Date.now() - 1000).toISOString(), token);
  assert.equal((await h.fetch('/api/auth/me', { cookie: `sign_session=${token}` })).status, 401);
  assert.equal(count(h, 'sessions'), 2, 'an expired session row was reaped — re-read spec/0004 §S2i');

  // WHAT THIS LAST BLOCK ASSERTS AND WHAT IT DOES NOT.
  //
  // The worker reports is_admin/can_send true and is_external false for every
  // A standalone verified account owns its workspace. Membership can later
  // replace role/admin capability without changing the user's identity.
  const me = await h.fetch('/api/auth/me', { cookie: `sign_session=${newer}` });
  assert.equal(me.status, 200);
  assert.deepEqual(
    await me.json(),
    {
      id: (h.db.prepare(`SELECT id FROM users`).get() as { id: string }).id,
      email: 'shape@pumasi.ai',
      name: 'Shape',
      is_admin: true,
      is_external: false,
      can_send: true,
      role: 'owner',
      provider: 'email',
    },
  );
});
