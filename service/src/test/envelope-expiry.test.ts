/**
 * Frozen acceptance cases A-410 – A-416 · spec/0007.
 *
 * roadmap/BACKLOG.md item 1 at `ba1cea7`, option (A): the worker keeps the
 * deadline the SPA asks the sender for. These drive the Durable Object that
 * answers sign.pumasi.ai through its own `fetch()` -- the same entrypoint
 * worker.ts uses -- plus, in A-415, worker.ts itself, which no test in this
 * repository had driven before.
 *
 * WHY A SEPARATE FILE FROM envelope-lifecycle.test.ts. That file holds
 * A-400 – A-409 and A-409 is frozen and is NOT amended by this spec: every one
 * of its assertions is still true after this change, because the sweep is the
 * only writer of `expired` and A-409 never invokes it. spec/0007 §S6 checks
 * that assertion by assertion. So pumasi/DECISIONS.md Q-030 -- may a builder
 * amend a frozen case -- is not reached here and no reading of it is taken.
 *
 * Read spec/0005/SPEC.md §S1 before trusting a green run: this is SQLite, but
 * it is not workerd's SQLite (spec/0004 §S1c), and these are assertions about
 * durable.ts's and worker.ts's own logic rather than about Cloudflare. In
 * particular NOTHING HERE ASSERTS THAT CLOUDFLARE FIRES THE CRON. That is a
 * line in wrangler.jsonc, read by a human and by wrangler, and spec/0007 §S4
 * and the release note both say so rather than letting a green count imply it.
 *
 * Mail is deliberately UNCONFIGURED, as in the sibling suite: sendMail throws
 * without GMAIL_SA_KEY/MAIL_IMPERSONATE and mailOrLog catches it, so the
 * `[mail] send to ... failed` lines in this suite's diagnostics are expected.
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';

import worker, { Env } from '../worker.js';
import { newHarness, cookieValue, Harness } from './support/durable-harness.js';

// ── seeding · the sibling suite's helpers, deliberately re-stated ───────────
//
// envelope-lifecycle.test.ts does not export these and this file does not
// import from it: a frozen case that breaks because a NEIGHBOURING frozen
// case's helper moved is a case that measures the wrong thing. Two small
// copies is the cheaper failure (pumasi/lessons/L-007 cuts the other way for
// RULES; this is a fixture).

let seq = 0;
const uid = (p: string) => `${p}-${(seq += 1).toString(16)}-${Math.random().toString(16).slice(2, 8)}`;

function seedCode(h: Harness, key: string, code = '123456'): void {
  h.db.prepare(
    `INSERT INTO auth_codes (id, email, code, expires_at, created_at) VALUES (?, ?, ?, ?, ?)`,
  ).run(uid('code'), key, code, new Date(Date.now() + 600_000).toISOString(), new Date().toISOString());
}

async function signIn(h: Harness, email: string): Promise<string> {
  seedCode(h, email);
  const res = await h.fetch('/api/auth/login/verify', {
    method: 'POST',
    body: JSON.stringify({ email, code: '123456' }),
  });
  assert.equal(res.status, 200);
  const token = cookieValue(res, 'sign_session');
  assert.ok(token, 'sign-in did not set a sign_session cookie');
  return `sign_session=${token}`;
}

interface SeedSigner { email: string; name?: string; order?: number; status?: string; cc?: boolean }
interface Seeded { id: string; publicUid: string; signers: { id: string; token: string; email: string }[] }

function seedEnvelope(
  h: Harness,
  opts: { owner: string; status?: string; expiresAt?: string | null; signers?: SeedSigner[]; title?: string },
): Seeded {
  const id = uid('sub');
  const publicUid = uid('pub');
  const now = new Date().toISOString();
  h.db.prepare(
    `INSERT INTO submissions (id, public_uid, title, message, created_by, status, expires_at, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
  ).run(id, publicUid, opts.title ?? 'Mutual NDA', null, opts.owner, opts.status ?? 'draft', opts.expiresAt ?? null, now, now);

  const signers = (opts.signers ?? [{ email: 'signer@example.test' }]).map((s, i) => {
    const sid = uid('subtr');
    const token = uid('tok');
    h.db.prepare(
      `INSERT INTO submitters (id, submission_id, name, email, role, signing_order, token, status, is_cc, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    ).run(sid, id, s.name ?? `Signer ${i + 1}`, s.email, 'Signer', s.order ?? i + 1, token, s.status ?? 'pending', s.cc ? 1 : 0, now);
    return { id: sid, token, email: s.email };
  });
  return { id, publicUid, signers };
}

async function signerCookie(h: Harness, s: { id: string; token: string }): Promise<string> {
  seedCode(h, `signer:${s.id}`);
  const res = await h.fetch(`/api/sign/token/${s.token}/verify`, {
    method: 'POST',
    body: JSON.stringify({ code: '123456' }),
  });
  assert.equal(res.status, 200);
  const c = cookieValue(res, 'sign_signer');
  assert.ok(c, 'signer verify did not set a sign_signer cookie');
  return `sign_signer=${c}`;
}

// ── reading back ───────────────────────────────────────────────────────────

const statusOf = (h: Harness, id: string): string | undefined =>
  (h.db.prepare(`SELECT status FROM submissions WHERE id = ?`).get(id) as { status: string } | undefined)?.status;

/** Audit event types for one envelope, sorted -- see the sibling suite on why. */
const events = (h: Harness, id: string): string[] =>
  (h.db.prepare(`SELECT event_type FROM audit_events WHERE submission_id = ?`).all(id) as { event_type: string }[])
    .map((r) => r.event_type).sort();

const auditRow = (h: Harness, id: string, type: string): any =>
  h.db.prepare(`SELECT * FROM audit_events WHERE submission_id = ? AND event_type = ?`).get(id, type);

const body = (res: Response) => res.json() as Promise<any>;

const PAST = new Date(Date.now() - 86_400_000).toISOString();
const FUTURE = new Date(Date.now() + 86_400_000).toISOString();

/** Drive the sweep exactly as worker.ts's scheduled() does: through fetch(). */
const sweep = (h: Harness) => h.fetch('/__internal/expire', { method: 'POST' });

// ── A-410 · the sweep expires a past-deadline pending envelope ─────────────

test('A-410 the sweep flips a past-deadline pending envelope to expired, writes one system-authored audit event, and changes nothing else', async () => {
  const h = newHarness();
  const cookie = await signIn(h, 'owner@pumasi.ai');
  const env = seedEnvelope(h, {
    owner: 'owner@pumasi.ai', status: 'pending', expiresAt: PAST,
    signers: [{ email: 'late@example.test' }],
  });
  const before = h.db.prepare(`SELECT * FROM submitters WHERE submission_id = ?`).all(env.id);

  const res = await sweep(h);
  assert.equal(res.status, 200);
  assert.deepEqual(await body(res), { expired: 1 });

  assert.equal(statusOf(h, env.id), 'expired');
  assert.deepEqual(events(h, env.id), ['expired'], 'exactly one audit event, and it is the expiry');

  // The actor is the service, not the sender: nobody did this.
  const row = auditRow(h, env.id, 'expired');
  assert.equal(row.actor_email, 'system@nolizi.com');
  assert.equal(row.actor_name, 'Nolizi Sign Engine');
  assert.equal(JSON.parse(row.details_json).expires_at, PAST);

  // Nothing is completed, nothing is deleted, no signer is touched.
  const after = h.db.prepare(`SELECT * FROM submissions WHERE id = ?`).get(env.id) as any;
  assert.equal(after.completed_at, null);
  assert.equal(after.expires_at, PAST, 'the deadline is kept, not cleared');
  assert.deepEqual(h.db.prepare(`SELECT * FROM submitters WHERE submission_id = ?`).all(env.id), before);

  // And the sender's own two views report it, through the real routes.
  assert.equal((await body(await h.fetch(`/api/submissions/${env.id}`, { cookie }))).status, 'expired');
  assert.equal((await body(await h.fetch('/api/submissions?mine=sent', { cookie })))[0].status, 'expired');
});

// ── A-411 · everything the sweep must leave alone ──────────────────────────

test('A-411 the sweep leaves alone a future deadline, no deadline, a malformed deadline, a draft, and every terminal status', async () => {
  const h = newHarness();
  await signIn(h, 'owner@pumasi.ai');
  const mk = (status: string, expiresAt: string | null) =>
    seedEnvelope(h, { owner: 'owner@pumasi.ai', status, expiresAt, signers: [{ email: 's@example.test' }] });

  const untouched: { why: string; env: Seeded; status: string }[] = [
    { why: 'deadline in the future', env: mk('pending', FUTURE), status: 'pending' },
    { why: 'no deadline at all', env: mk('pending', null), status: 'pending' },
    // Stored TEXT is compared lexicographically. A value that is not an
    // ISO-8601 date must not be expired on an accidental string comparison:
    // durable.ts:1032 stores whatever a multipart client sent, unvalidated.
    { why: 'malformed deadline', env: mk('pending', 'yesterday'), status: 'pending' },
    { why: 'a truncated non-ISO deadline', env: mk('pending', '2026'), status: 'pending' },
    // A draft was never sent to anyone; expiring it takes a document away from
    // a sender who is still writing it. spec/0007 §S2d.
    { why: 'a draft, past its deadline', env: mk('draft', PAST), status: 'draft' },
    { why: 'completed, past its deadline', env: mk('completed', PAST), status: 'completed' },
    { why: 'cancelled, past its deadline', env: mk('cancelled', PAST), status: 'cancelled' },
    { why: 'declined, past its deadline', env: mk('declined', PAST), status: 'declined' },
  ];

  const res = await sweep(h);
  assert.equal(res.status, 200);
  assert.deepEqual(await body(res), { expired: 0 }, 'the sweep expired something it should not have');

  for (const u of untouched) {
    assert.equal(statusOf(h, u.env.id), u.status, `${u.why}: status moved`);
    assert.deepEqual(events(h, u.env.id), [], `${u.why}: the sweep wrote an audit row`);
  }
});

// ── A-412 · an expired envelope refuses a TOKEN LINK, end to end ───────────

test('A-412 an expired envelope refuses the signing link: the token view says expired, request-code is 410, and a session opened before the sweep cannot complete', async () => {
  const h = newHarness();
  const env = seedEnvelope(h, {
    owner: 'owner@pumasi.ai', status: 'pending', expiresAt: PAST,
    signers: [{ email: 'late@example.test' }],
  });
  const signer = env.signers[0];

  // The signer gets in BEFORE the sweep -- an already-authorized session, not
  // a fresh one, because that is the case a status guard could miss.
  const sc = await signerCookie(h, signer);
  assert.equal((await body(await h.fetch(`/api/sign/token/${signer.token}`))).status, 'open');

  assert.deepEqual(await body(await sweep(h)), { expired: 1 });

  // The baseline is snapshotted rather than written out: getting in legitimately
  // audits `signer_verified` (durable.ts:1382), and a literal list here would be
  // asserting the setup rather than the refusal.
  const auditedBefore = events(h, env.id);
  assert.deepEqual(auditedBefore, ['expired', 'signer_verified']);

  // 1. The token landing page.
  assert.equal((await body(await h.fetch(`/api/sign/token/${signer.token}`))).status, 'expired');

  // 2. Asking for a code sends no mail and writes no audit row: spec/0007
  //    §S0.3 says this change sends no mail, and a verification code for a
  //    dead envelope would be mail.
  const code = await h.fetch(`/api/sign/token/${signer.token}/request-code`, { method: 'POST' });
  assert.equal(code.status, 410);
  assert.deepEqual(await body(code), { error: 'This envelope is no longer active.' });
  assert.deepEqual(events(h, env.id), auditedBefore);

  // 3. The signing session itself. The GET still answers -- the signer is
  //    entitled to see why -- and carries the status the SPA blocks on.
  const view = await body(await h.fetch(`/api/sign/${signer.id}`, { cookie: sc }));
  assert.equal(view.submission.status, 'expired');
  assert.equal(view.submission.expires_at, PAST);

  // 4. And the write is refused, with complete's terminal code.
  const done = await h.fetch(`/api/sign/${signer.id}/complete`, {
    method: 'POST', cookie: sc, body: JSON.stringify({ values: {} }),
  });
  assert.equal(done.status, 410);
  assert.deepEqual(await body(done), { error: 'This envelope is no longer active' });
  assert.equal(statusOf(h, env.id), 'expired', 'the refusal changed nothing');
  assert.deepEqual(events(h, env.id), auditedBefore, 'the refusal audited something');
});

// ── A-413 · isTerminal covers `expired` ────────────────────────────────────

test('A-413 an expired envelope refuses what a completed one refuses: decline 409, cancel 409, send/remind 409, and none of the three writes', async () => {
  const h = newHarness();
  const cookie = await signIn(h, 'owner@pumasi.ai');
  const env = seedEnvelope(h, {
    owner: 'owner@pumasi.ai', status: 'pending', expiresAt: PAST,
    signers: [{ email: 'late@example.test' }],
  });
  const signer = env.signers[0];
  const sc = await signerCookie(h, signer);
  assert.deepEqual(await body(await sweep(h)), { expired: 1 });
  // Snapshotted, not written out: getting in legitimately audits
  // `signer_verified`, and a literal list would assert the setup.
  const auditedBefore = events(h, env.id);

  const dec = await h.fetch(`/api/sign/${signer.id}/decline`, {
    method: 'POST', cookie: sc, body: JSON.stringify({ reason: 'too late' }),
  });
  assert.equal(dec.status, 409);
  assert.deepEqual(await body(dec), { error: 'This envelope is no longer active' });

  const can = await h.fetch(`/api/submissions/${env.id}/cancel`, { method: 'POST', cookie, body: '{}' });
  assert.equal(can.status, 409);
  assert.deepEqual(await body(can), { error: 'This envelope is already closed' });

  for (const action of ['send', 'remind']) {
    const res = await h.fetch(`/api/submissions/${env.id}/${action}`, { method: 'POST', cookie });
    assert.equal(res.status, 409, `${action} on an expired envelope`);
    assert.deepEqual(await body(res), { error: 'This envelope is not awaiting signatures' });
  }

  assert.equal(statusOf(h, env.id), 'expired');
  assert.deepEqual(events(h, env.id), auditedBefore, 'a refusal wrote an audit row');
  assert.equal(
    (h.db.prepare(`SELECT status FROM submitters WHERE id = ?`).get(signer.id) as any).status,
    'pending',
    'the refused decline still marked the signer',
  );
});

// ── A-414 · idempotent, and not on the public API surface ──────────────────

test('A-414 running the sweep twice expires nothing the second time, and the sweep is not reachable through the public /api/ surface', async () => {
  const h = newHarness();
  const cookie = await signIn(h, 'owner@pumasi.ai');
  const env = seedEnvelope(h, {
    owner: 'owner@pumasi.ai', status: 'pending', expiresAt: PAST,
    signers: [{ email: 'late@example.test' }],
  });

  assert.deepEqual(await body(await sweep(h)), { expired: 1 });
  assert.deepEqual(await body(await sweep(h)), { expired: 0 }, 'the sweep expired an already-expired envelope');
  assert.deepEqual(events(h, env.id), ['expired'], 'the second sweep wrote a second audit event');

  // worker.ts forwards EVERY /api/* path to this object, so a sweep route
  // under /api/ would be reachable by anyone who guessed it. spec/0007 §S2c.
  for (const p of ['/api/jobs/daily', '/api/__internal/expire', '/api/internal/expire']) {
    const res = await h.fetch(p, { method: 'POST', cookie });
    assert.equal(res.status, 404, `${p} answered something other than 404`);
    assert.deepEqual(await body(res), { error: 'Endpoint not found' });
  }
  assert.equal(statusOf(h, env.id), 'expired');
});

// ── A-415 · worker.ts: one Durable Object, one constant, one closed door ───
//
// spec/0007 §S0.2's whole answer to "how does the sweep enumerate Durable
// Objects" is THERE IS EXACTLY ONE AND BOTH PATHS RESOLVE THE SAME CONSTANT.
// A spec that asserts that in prose and not in a test has asserted nothing.

interface Resolved { names: string[]; requests: { url: string; method: string }[] }

function recordingEnv(respond: (req: Request) => Response): { env: Env; seen: Resolved } {
  const seen: Resolved = { names: [], requests: [] };
  const env = {
    SIGN_SERVICE: {
      idFromName(name: string) { seen.names.push(name); return { name } as unknown as DurableObjectId; },
      get(_id: unknown) {
        return {
          fetch: async (req: Request) => {
            seen.requests.push({ url: req.url, method: req.method });
            return respond(req);
          },
        } as unknown as DurableObjectStub;
      },
    } as unknown as DurableObjectNamespace,
  } as Env;
  return { env, seen };
}

const ok = () => Response.json({ expired: 0 });

test('A-415 scheduled() reaches the same single Durable Object the request path reaches, throws when the sweep fails, and the internal path is closed to the internet', async () => {
  // 1. The request path and the scheduled path resolve the SAME name.
  const a = recordingEnv(ok);
  await worker.fetch(new Request('https://sign.pumasi.ai/api/submissions'), a.env);
  const fromRequest = a.seen.names;

  const b = recordingEnv(ok);
  await worker.scheduled(
    {} as unknown as ScheduledController,
    b.env,
    { waitUntil() {}, passThroughOnException() {} } as unknown as ExecutionContext,
  );
  const fromSchedule = b.seen.names;

  assert.deepEqual(fromRequest, ['pumasi-sign-main']);
  assert.deepEqual(
    fromSchedule, fromRequest,
    'the sweep addresses a different Durable Object than the one every envelope lives in',
  );

  // 2. It POSTs the sweep, and it does so to the internal path.
  assert.equal(b.seen.requests.length, 1);
  assert.equal(b.seen.requests[0].method, 'POST');
  assert.equal(new URL(b.seen.requests[0].url).pathname, '/__internal/expire');

  // 3. A sweep that fails must not report success. A `scheduled` handler that
  //    swallows a failure is a cron reporting green having expired nothing --
  //    pumasi/lessons/L-006 at infrastructure scale.
  const c = recordingEnv(() => Response.json({ error: 'Internal error' }, { status: 500 }));
  await assert.rejects(
    () => worker.scheduled(
      {} as unknown as ScheduledController,
      c.env,
      { waitUntil() {}, passThroughOnException() {} } as unknown as ExecutionContext,
    ),
    /500/,
  );

  // 4. The door. An inbound request to the internal path is refused by
  //    worker.ts before any binding is touched -- proved by a binding that
  //    throws if it is read at all.
  const exploding = { get SIGN_SERVICE(): never { throw new Error('SIGN_SERVICE was touched'); } } as unknown as Env;
  for (const m of ['GET', 'POST']) {
    const res = await worker.fetch(new Request('https://sign.pumasi.ai/__internal/expire', { method: m }), exploding);
    assert.equal(res.status, 404, `${m} /__internal/expire`);
    assert.deepEqual(await body(res), { error: 'Not found' });
  }
  // Including the CORS pre-flight, so nothing about the path is observable.
  assert.equal(
    (await worker.fetch(new Request('https://sign.pumasi.ai/__internal/expire', { method: 'OPTIONS' }), exploding)).status,
    404,
  );
});

// ── A-416 · the deadline can still be corrected while the envelope is live ─

test('A-416 correcting an envelope saves the expiry and reminder settings the dialog sends, audits what changed, refuses them on a terminal envelope, and a deadline moved into the future survives the sweep', async () => {
  const h = newHarness();
  const cookie = await signIn(h, 'owner@pumasi.ai');
  const env = seedEnvelope(h, {
    owner: 'owner@pumasi.ai', status: 'pending', expiresAt: PAST,
    signers: [{ email: 'late@example.test' }],
  });

  // EnvelopeDetailView.vue:428 sends exactly this shape and the worker
  // discarded all three of these fields. spec/0007 §S1d.
  const res = await h.fetch(`/api/submissions/${env.id}`, {
    method: 'PATCH', cookie,
    body: JSON.stringify({ expires_at: FUTURE, reminders_enabled: false, reminder_interval_days: 7 }),
  });
  assert.equal(res.status, 200);
  const out = await body(res);
  assert.equal(out.expires_at, FUTURE);
  assert.equal(out.reminders_enabled, false);
  assert.equal(out.reminder_interval_days, 7);
  assert.equal(out.title, 'Mutual NDA', 'PATCH without a title blanked the title');

  // EnvelopeDetailView.vue:608 renders `detail.changed` and had never been sent one.
  const corrected = auditRow(h, env.id, 'corrected');
  assert.deepEqual(
    JSON.parse(corrected.details_json).changed.slice().sort(),
    ['expiration date', 'reminder interval', 'reminders'],
  );

  // The whole point: the extended deadline is honoured by the sweep.
  assert.deepEqual(await body(await sweep(h)), { expired: 0 });
  assert.equal(statusOf(h, env.id), 'pending');

  // Once it IS terminal, the three settings are refused -- the pencil that
  // sends them is not drawn then (EnvelopeDetailView.vue:64), and reviving a
  // finished envelope by extending its deadline is spec/0007 §S5's "not built".
  h.db.prepare(`UPDATE submissions SET expires_at = ? WHERE id = ?`).run(PAST, env.id);
  assert.deepEqual(await body(await sweep(h)), { expired: 1 });
  const late = await h.fetch(`/api/submissions/${env.id}`, {
    method: 'PATCH', cookie, body: JSON.stringify({ expires_at: FUTURE }),
  });
  assert.equal(late.status, 409);
  assert.deepEqual(await body(late), { error: 'This envelope is already closed' });
  assert.equal(
    (h.db.prepare(`SELECT expires_at FROM submissions WHERE id = ?`).get(env.id) as any).expires_at,
    PAST,
    'the refused correction changed the deadline anyway',
  );
  assert.equal(statusOf(h, env.id), 'expired');
});
