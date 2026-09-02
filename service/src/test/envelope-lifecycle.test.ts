/**
 * Frozen acceptance cases A-400 – A-409 · spec/0005, three of them amended by
 * spec/0006 §S4.
 *
 * Sub-item 3 of roadmap/BACKLOG.md item 1: WHAT AN ENVELOPE MAY BECOME. These
 * drive the Durable Object that answers sign.pumasi.ai through its own
 * `fetch()` -- the same entrypoint worker.ts uses -- across every status
 * transition durable.ts actually implements, and across one the product claims
 * and durable.ts does not.
 *
 * THEY CHARACTERIZE. THEY DO NOT ADJUDICATE. When frozen, four assertions here
 * were marked RECORDED, NOT ENDORSED against a spec/0005 §S6 entry, so that red
 * there would mean "someone took the backlog entry" rather than "someone broke
 * the worker". That idiom is spec/0004 §S4's and this file inherits it.
 *
 * AMENDED 2026-08-31 (spec/0006 §S4), in the open, in the same commit as the
 * repair it records. THREE of those four went red on purpose and are now
 * asserted against the guard instead of against its absence: A-404 (cancel),
 * A-406 (a completed envelope accepting a further signature) and A-407
 * (decline). Each carries, at its own header, what it asserted before and what
 * it asserts now. A-409 is UNTOUCHED and still RECORDED, NOT ENDORSED --
 * `expired` is roadmap/BACKLOG.md item 2 and was not this packet's to take.
 *
 * Read spec/0005/SPEC.md §S1 before trusting a green run: this is SQLite, but
 * it is not workerd's SQLite (spec/0004 §S1c), and these are assertions about
 * durable.ts's own logic rather than about Cloudflare's storage engine.
 *
 * Mail is deliberately UNCONFIGURED here. sendMail throws without
 * GMAIL_SA_KEY/MAIL_IMPERSONATE and mailOrLog catches it, so every notifying
 * path below runs to completion offline and writes no invite_sent audit row.
 * The `[mail] send to ... failed` lines in this suite's diagnostics are that,
 * and they are expected.
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { newHarness, cookieValue, Harness } from './support/durable-harness.js';
import { makePdf } from './support/pdf-probe.js';

// ── seeding ─────────────────────────────────────────────────────────────────

let seq = 0;
const uid = (p: string) => `${p}-${(seq += 1).toString(16)}-${Math.random().toString(16).slice(2, 8)}`;

/** Put a live verification code in `auth_codes`, the way issueCode would. */
function seedCode(h: Harness, key: string, code = '123456'): void {
  h.db.prepare(
    `INSERT INTO auth_codes (id, email, code, expires_at, created_at) VALUES (?, ?, ?, ?, ?)`,
  ).run(uid('code'), key, code, new Date(Date.now() + 600_000).toISOString(), new Date().toISOString());
}

/** Sign in through the real email path and hand back the owner's session cookie. */
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

/**
 * An envelope in a chosen status, written straight to the store.
 *
 * Deliberately not built through POST /api/submissions: that route wants a PDF
 * and would drag the creation contract into cases that are about status words. Every
 * TRANSITION below is still driven through fetch(); only the starting position
 * is seeded. Cases that reach successful completion carry a minimal real PDF;
 * spec/0011 removed completion-without-an-artifact as an invalid state.
 */
function seedEnvelope(
  h: Harness,
  opts: { owner: string; status?: string; expiresAt?: string | null; signers?: SeedSigner[]; title?: string; pdf?: Uint8Array },
): Seeded {
  const id = uid('sub');
  const publicUid = uid('pub');
  const now = new Date().toISOString();
  h.db.prepare(
    `INSERT INTO submissions (id, public_uid, title, message, created_by, status, expires_at, original_pdf_blob, original_hash, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
  ).run(id, publicUid, opts.title ?? 'Mutual NDA', null, opts.owner, opts.status ?? 'draft', opts.expiresAt ?? null, opts.pdf ?? null, '0'.repeat(64), now, now);

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

/** Verify a signer through the real token route and hand back their signer cookie. */
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

// ── reading back ────────────────────────────────────────────────────────────

const statusOf = (h: Harness, id: string): string | undefined =>
  (h.db.prepare(`SELECT status FROM submissions WHERE id = ?`).get(id) as { status: string } | undefined)?.status;

const signerStatus = (h: Harness, id: string): string | undefined =>
  (h.db.prepare(`SELECT status FROM submitters WHERE id = ?`).get(id) as { status: string } | undefined)?.status;

/**
 * Audit event types for one envelope, sorted -- NOT in insertion order.
 * `audit_events.created_at` is a millisecond ISO string and two events written
 * inside one request can tie, so an order-dependent assertion here would be
 * conditional on timing the test does not control (pumasi/lessons/L-006).
 */
const events = (h: Harness, id: string): string[] =>
  (h.db.prepare(`SELECT event_type FROM audit_events WHERE submission_id = ?`).all(id) as { event_type: string }[])
    .map((r) => r.event_type).sort();

const body = (res: Response) => res.json() as Promise<any>;

// ── A-400 · the reader guard ────────────────────────────────────────────────
//
// Every other case in this file seeds `status` explicitly, so a harness whose
// `submissions`/`submitters` tables carried no DEFAULT -- or that stored the
// word and handed back something else -- would leave all nine of them green
// while the two columns this file is entirely about were never really the
// worker's. This case is the one that reads them from the schema durable.ts
// wrote, and it also proves the envelope surface routes at all.

test('A-400 the schema the worker declares: a submission defaults to draft, a submitter to pending, and the envelope surface routes', async () => {
  const h = newHarness();
  const cookie = await signIn(h, 'owner@pumasi.ai');

  // Name neither status column. durable.ts:190 and :207 supply both.
  const id = uid('sub');
  const now = new Date().toISOString();
  h.db.prepare(
    `INSERT INTO submissions (id, public_uid, title, created_by, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)`,
  ).run(id, uid('pub'), 'Unstated', 'owner@pumasi.ai', now, now);
  const sid = uid('subtr');
  h.db.prepare(
    `INSERT INTO submitters (id, submission_id, name, email, token, created_at) VALUES (?, ?, ?, ?, ?, ?)`,
  ).run(sid, id, 'Signer 1', 'signer@example.test', uid('tok'), now);

  assert.equal(statusOf(h, id), 'draft', 'submissions.status DEFAULT (durable.ts:190)');
  assert.equal(signerStatus(h, sid), 'pending', 'submitters.status DEFAULT (durable.ts:207)');

  // ... and the same two words come back out through fetch(), which is what
  // makes every other case in this file an assertion about durable.ts.
  const got = await body(await h.fetch(`/api/submissions/${id}`, { cookie }));
  assert.equal(got.status, 'draft');
  assert.equal(got.submitters[0].status, 'pending');

  // The owner scope is real: a signed-in stranger does not see it at all.
  const other = await signIn(h, 'stranger@pumasi.ai');
  assert.equal((await h.fetch(`/api/submissions/${id}`, { cookie: other })).status, 404);
});

// ── A-401 · DELETE is draft-only (durable.ts:1210) ──────────────────────────

test('A-401 only a draft can be deleted, and deleting one takes its signers, fields and audit trail with it', async () => {
  const h = newHarness();
  const cookie = await signIn(h, 'owner@pumasi.ai');

  const draft = seedEnvelope(h, { owner: 'owner@pumasi.ai', status: 'draft' });
  h.db.prepare(
    `INSERT INTO submission_fields (id, submission_id, submitter_id, type, page, x, y, width, height, value)
     VALUES (?, ?, ?, 'text', 0, 1, 1, 10, 10, '')`,
  ).run(uid('fld'), draft.id, draft.signers[0].id);
  h.db.prepare(
    `INSERT INTO audit_events (id, submission_id, event_type, actor_email, actor_name, created_at)
     VALUES (?, ?, 'created', ?, ?, ?)`,
  ).run(uid('evt'), draft.id, 'owner@pumasi.ai', 'Owner', new Date().toISOString());

  const del = await h.fetch(`/api/submissions/${draft.id}`, { method: 'DELETE', cookie });
  assert.equal(del.status, 200);
  assert.deepEqual(await body(del), { ok: true });
  assert.equal(statusOf(h, draft.id), undefined);
  const gone = (t: string) =>
    (h.db.prepare(`SELECT count(*) AS n FROM ${t} WHERE submission_id = ?`).get(draft.id) as { n: number }).n;
  assert.equal(gone('submitters'), 0);
  assert.equal(gone('submission_fields'), 0);
  assert.equal(gone('audit_events'), 0);

  // Every other status is refused, by the same message, and survives intact.
  for (const status of ['pending', 'completed', 'cancelled', 'declined']) {
    const env = seedEnvelope(h, { owner: 'owner@pumasi.ai', status });
    const res = await h.fetch(`/api/submissions/${env.id}`, { method: 'DELETE', cookie });
    assert.equal(res.status, 409, `DELETE on ${status}`);
    assert.deepEqual(await body(res), { error: 'Only drafts can be deleted' });
    assert.equal(statusOf(h, env.id), status, `${status} survived the refused DELETE`);
  }
});

// ── A-402 · send: draft → pending once, then a reminder (:1227–:1233) ───────

test('A-402 send moves a draft to pending exactly once; on a pending envelope the same route is a reminder, not a second send', async () => {
  const h = newHarness();
  const cookie = await signIn(h, 'owner@pumasi.ai');
  const env = seedEnvelope(h, { owner: 'owner@pumasi.ai', status: 'draft' });

  const first = await h.fetch(`/api/submissions/${env.id}/send`, { method: 'POST', cookie });
  assert.equal(first.status, 200);
  assert.deepEqual(await body(first), { ok: true });
  assert.equal(statusOf(h, env.id), 'pending');
  assert.deepEqual(events(h, env.id), ['sent']);

  // Same route, same envelope, now pending: still 200, still pending, but the
  // audit trail records `reminded` and gains no second `sent`.
  const second = await h.fetch(`/api/submissions/${env.id}/send`, { method: 'POST', cookie });
  assert.equal(second.status, 200);
  assert.equal(statusOf(h, env.id), 'pending');
  assert.deepEqual(events(h, env.id), ['reminded', 'sent']);

  // /remind is the same branch, not a second implementation.
  const third = await h.fetch(`/api/submissions/${env.id}/remind`, { method: 'POST', cookie });
  assert.equal(third.status, 200);
  assert.equal(statusOf(h, env.id), 'pending');
  assert.deepEqual(events(h, env.id), ['reminded', 'reminded', 'sent']);

  // ... and a draft reached through /remind is SENT, not reminded: the branch
  // keys on the envelope's status, never on the word in the URL.
  const draft2 = seedEnvelope(h, { owner: 'owner@pumasi.ai', status: 'draft' });
  assert.equal((await h.fetch(`/api/submissions/${draft2.id}/remind`, { method: 'POST', cookie })).status, 200);
  assert.equal(statusOf(h, draft2.id), 'pending');
  assert.deepEqual(events(h, draft2.id), ['sent']);
});

// ── A-403 · send refuses every terminal status (:1231) ──────────────────────

test('A-403 a completed, cancelled or declined envelope cannot be sent or reminded, and the refusal writes nothing', async () => {
  const h = newHarness();
  const cookie = await signIn(h, 'owner@pumasi.ai');

  for (const status of ['completed', 'cancelled', 'declined']) {
    for (const action of ['send', 'remind']) {
      const env = seedEnvelope(h, { owner: 'owner@pumasi.ai', status });
      const res = await h.fetch(`/api/submissions/${env.id}/${action}`, { method: 'POST', cookie });
      assert.equal(res.status, 409, `${action} on ${status}`);
      assert.deepEqual(await body(res), { error: 'This envelope is not awaiting signatures' });
      assert.equal(statusOf(h, env.id), status);
      assert.deepEqual(events(h, env.id), [], `${action} on ${status} left an audit event`);
    }
  }
});

// ── A-404 · cancel refuses every terminal status (:1252) ────────────────────
//
// AMENDED 2026-08-31 by spec/0006 §S4, in the open and in the same commit as
// the repair. Frozen 2026-08-31 by spec/0005 as *"cancel has no status guard:
// it overwrites a completed, declined or already-cancelled envelope and audits
// again"*, asserting `again.status === 200`, `statusOf === 'cancelled'` for
// each of the three terminal statuses, and two `cancelled` events on one
// envelope. That was RECORDED, NOT ENDORSED against spec/0005 §S6.1, and going
// red was the documented sign that the backlog entry had been taken. It was.
// The case still covers the same transition; it now asserts the guard.

test('A-404 cancel moves a pending envelope to cancelled once, and refuses a completed, declined or already-cancelled one without writing', async () => {
  const h = newHarness();
  const cookie = await signIn(h, 'owner@pumasi.ai');
  const cancel = (id: string) => h.fetch(`/api/submissions/${id}/cancel`, { method: 'POST', cookie });

  // The ordinary transition, unchanged by the repair.
  const pending = seedEnvelope(h, { owner: 'owner@pumasi.ai', status: 'pending' });
  const res = await cancel(pending.id);
  assert.equal(res.status, 200);
  assert.deepEqual(await body(res), { ok: true });
  assert.equal(statusOf(h, pending.id), 'cancelled');
  assert.deepEqual(events(h, pending.id), ['cancelled']);

  // A draft is cancellable too: `draft` and `pending` are the two statuses the
  // guard lets through, and the shipped Void button is drawn for both.
  const draft = seedEnvelope(h, { owner: 'owner@pumasi.ai', status: 'draft' });
  assert.equal((await cancel(draft.id)).status, 200);
  assert.equal(statusOf(h, draft.id), 'cancelled');

  // A reason rides into details_json when one is given.
  const withReason = seedEnvelope(h, { owner: 'owner@pumasi.ai', status: 'pending' });
  assert.equal((await h.fetch(`/api/submissions/${withReason.id}/cancel`, {
    method: 'POST', cookie, body: JSON.stringify({ reason: 'Wrong counterparty' }),
  })).status, 200);
  assert.equal(
    (h.db.prepare(`SELECT details_json AS d FROM audit_events WHERE submission_id = ?`).get(withReason.id) as { d: string }).d,
    '{"reason":"Wrong counterparty"}',
  );

  // THE REPAIR (durable.ts:1252, spec/0006 §S2a). Where this case previously
  // recorded a 200 and an overwritten terminal status, the three terminal
  // statuses are now refused with 409 -- and the refusal WRITES NOTHING and
  // AUDITS NOTHING, proved by reading the row back and by the audit trail
  // still being empty rather than by inspecting the handler.
  for (const status of ['completed', 'declined', 'cancelled']) {
    const env = seedEnvelope(h, { owner: 'owner@pumasi.ai', status });
    const again = await cancel(env.id);
    assert.equal(again.status, 409, `cancel on ${status} is refused`);
    assert.deepEqual(await body(again), { error: 'This envelope is already closed' });
    assert.equal(statusOf(h, env.id), status, `${status} survived the refused cancel`);
    assert.deepEqual(events(h, env.id), [], `cancel on ${status} left an audit event`);
  }

  // ... and cancelling twice now leaves ONE event on one envelope, which is
  // the same repair seen from the audit trail: this asserted two before.
  const twice = seedEnvelope(h, { owner: 'owner@pumasi.ai', status: 'pending' });
  assert.equal((await cancel(twice.id)).status, 200);
  assert.equal((await cancel(twice.id)).status, 409);
  assert.deepEqual(events(h, twice.id), ['cancelled']);
});

// ── A-405 · resend refuses a signer who is not pending (:1295) ──────────────

test('A-405 resending an invitation is scoped to this envelope and refused for a signer who is not pending', async () => {
  const h = newHarness();
  const cookie = await signIn(h, 'owner@pumasi.ai');
  const env = seedEnvelope(h, {
    owner: 'owner@pumasi.ai',
    status: 'pending',
    signers: [
      { email: 'a@example.test', status: 'pending' },
      { email: 'b@example.test', status: 'signed', order: 2 },
      { email: 'c@example.test', status: 'declined', order: 3 },
    ],
  });
  const other = seedEnvelope(h, { owner: 'owner@pumasi.ai', status: 'pending' });
  const resend = (subId: string, signerId: string) =>
    h.fetch(`/api/submissions/${subId}/submitters/${signerId}/resend`, { method: 'POST', cookie });

  assert.equal((await resend(env.id, env.signers[0].id)).status, 200);

  for (const i of [1, 2]) {
    const res = await resend(env.id, env.signers[i].id);
    assert.equal(res.status, 409);
    // One message for both. A declined signer has not "already finished" in the
    // product's own vocabulary, and the wire says they have; recorded, not
    // adjudicated -- it is a wording observation, not a transition.
    assert.deepEqual(await body(res), { error: 'That signer has already finished' });
  }

  const unknown = await resend(env.id, 'subtr-nosuchsigner');
  assert.equal(unknown.status, 404);
  assert.deepEqual(await body(unknown), { error: 'No such signer' });

  // A real signer, but of a different envelope: 404, not 200. The lookup is
  // scoped by submission_id, so one owner's envelope cannot poke another's.
  const crossed = await resend(env.id, other.signers[0].id);
  assert.equal(crossed.status, 404);
  assert.deepEqual(await body(crossed), { error: 'No such signer' });
});

// ── A-406 · the last outstanding signer completes it, once (:1479, :1452) ──

test('A-406 signing is in order, is once, and the last outstanding non-CC signer completes the envelope -- after which a CC recipient is refused and it completes exactly once', async () => {
  const h = newHarness();
  const pdf = await makePdf(['ORDERED SIGNING AGREEMENT']);
  const env = seedEnvelope(h, {
    owner: 'owner@pumasi.ai',
    status: 'pending',
    pdf,
    signers: [
      { email: 'first@example.test', order: 1 },
      { email: 'second@example.test', order: 2 },
      { email: 'watcher@example.test', order: 3, cc: true },
    ],
  });
  const [first, second, cc] = env.signers;
  const sign = (s: { id: string }, cookie: string) =>
    h.fetch(`/api/sign/${s.id}/complete`, { method: 'POST', cookie, body: JSON.stringify({ values: {}, consent_accepted: true, consent_version: 'pumasi-esign-consent-v1' }) });

  // Out of turn: refused, and nothing is written.
  const secondCookie = await signerCookie(h, second);
  const early = await sign(second, secondCookie);
  assert.equal(early.status, 409);
  assert.deepEqual(await body(early), { error: 'Earlier signers have not finished yet' });
  assert.equal(signerStatus(h, second.id), 'pending');
  assert.equal(statusOf(h, env.id), 'pending');

  // First signer: the envelope stays pending and the response says `signed`.
  const firstCookie = await signerCookie(h, first);
  const one = await sign(first, firstCookie);
  assert.equal(one.status, 200);
  assert.deepEqual(await body(one), { ok: true, status: 'signed' });
  assert.equal(signerStatus(h, first.id), 'signed');
  assert.equal(statusOf(h, env.id), 'pending');

  // Signing twice is refused.
  const twice = await sign(first, firstCookie);
  assert.equal(twice.status, 409);
  assert.deepEqual(await body(twice), { error: 'Already signed' });

  // Last outstanding NON-CC signer: the CC recipient is still `pending` and
  // does not hold the envelope open (durable.ts:1479's `AND is_cc = 0`).
  const two = await sign(second, secondCookie);
  assert.equal(two.status, 200);
  assert.deepEqual(await body(two), { ok: true, status: 'completed' });
  assert.equal(signerStatus(h, cc.id), 'pending');
  assert.equal(statusOf(h, env.id), 'completed');
  const row = h.db.prepare(`SELECT completed_at FROM submissions WHERE id = ?`).get(env.id) as { completed_at: string };
  assert.ok(row.completed_at, 'completed_at was not stamped');
  assert.deepEqual(events(h, env.id), ['completed', 'signed', 'signed', 'signer_verified', 'signer_verified']);

  // The completion is attributed to the engine, not to the last signer.
  const done = h.db.prepare(
    `SELECT actor_email AS e FROM audit_events WHERE submission_id = ? AND event_type = 'completed'`,
  ).get(env.id) as { e: string };
  assert.equal(done.e, 'system@pumasi.ai');

  // THE REPAIR (durable.ts:1452, spec/0006 §S2b). AMENDED 2026-08-31 by
  // spec/0006 §S4. This tail was frozen as RECORDED, NOT ENDORSED against
  // spec/0005 §S6.4 and asserted the opposite of what it asserts now: that the
  // CC recipient's signature was ACCEPTED (200, `{ ok: true, status:
  // 'completed' }`) and that the envelope carried TWO `completed` events
  // because finalize() had run a second time. `completed` is now in complete's
  // dead-envelope guard, so the CC recipient is refused with the same 410 the
  // other two terminal statuses already gave.
  //
  // The cookie is taken and the trail snapshotted BEFORE the attempt, because
  // verifying a signer audits `signer_verified` and that write is not the one
  // under test. What follows proves the refusal wrote nothing at all.
  const ccCookie = await signerCookie(h, cc);
  const trailBefore = events(h, env.id);
  const after = await sign(cc, ccCookie);
  assert.equal(after.status, 410, 'a completed envelope no longer accepts a signature');
  assert.deepEqual(await body(after), { error: 'This envelope is no longer active' });
  assert.equal(statusOf(h, env.id), 'completed', 'the completed envelope was left alone');
  assert.equal(signerStatus(h, cc.id), 'pending', 'the CC recipient was not marked signed');
  assert.deepEqual(events(h, env.id), trailBefore, 'the refused signature wrote an audit event');
  assert.equal(
    events(h, env.id).filter((e) => e === 'completed').length, 1,
    'finalize ran once and the envelope has exactly one completion event',
  );
  const stamp = h.db.prepare(`SELECT completed_at FROM submissions WHERE id = ?`).get(env.id) as { completed_at: string };
  assert.equal(stamp.completed_at, row.completed_at, 'completed_at was re-stamped by a second finalize');
});

// ── A-407 · decline, which now carries complete's three guards (:1513) ──────
//
// AMENDED 2026-08-31 by spec/0006 §S4, in the open and in the same commit as
// the repair. Frozen 2026-08-31 by spec/0005 as *"one decline ends the
// envelope for everyone, and decline has no status guard where complete has
// one"*, asserting RECORDED, NOT ENDORSED against spec/0005 §S6.2 that a
// decline on an already-declined envelope was accepted (200), that a completed
// envelope was overwritten to `declined`, and that a signer whose status was
// `signed` was flipped to `declined`. Red there was the documented sign that
// the backlog entry had been taken. It was. The first half of the case -- one
// decline ending the envelope for everyone -- is unchanged; the asymmetry the
// second half existed to prove is now closed, and the case asserts the close.

test('A-407 one decline ends the envelope for everyone, and decline now carries the same three guards complete has', async () => {
  const h = newHarness();
  const env = seedEnvelope(h, {
    owner: 'owner@pumasi.ai',
    status: 'pending',
    signers: [{ email: 'first@example.test', order: 1 }, { email: 'second@example.test', order: 2 }],
  });
  const [first, second] = env.signers;
  const decline = (s: { id: string }, cookie: string, reason?: string) =>
    h.fetch(`/api/sign/${s.id}/decline`, {
      method: 'POST', cookie, body: JSON.stringify(reason ? { reason } : {}),
    });

  const res = await decline(first, await signerCookie(h, first), 'Terms are wrong');
  assert.equal(res.status, 200);
  assert.equal(signerStatus(h, first.id), 'declined');
  assert.equal(statusOf(h, env.id), 'declined', 'one signer declining ends it for the whole envelope');
  assert.equal(signerStatus(h, second.id), 'pending', 'the other signer is left as-is, not declined');
  assert.equal(
    (h.db.prepare(`SELECT details_json AS d FROM audit_events WHERE submission_id = ? AND event_type = 'declined'`)
      .get(env.id) as { d: string }).d,
    '{"reason":"Terms are wrong"}',
  );

  // complete guards, as it always did: the same dead envelope refuses a signature.
  const secondCookie = await signerCookie(h, second);
  const stopped = await h.fetch(`/api/sign/${second.id}/complete`, {
    method: 'POST', cookie: secondCookie, body: JSON.stringify({ values: {} }),
  });
  assert.equal(stopped.status, 410);
  assert.deepEqual(await body(stopped), { error: 'This envelope is no longer active' });

  // THE REPAIR, guard 1 of 3 -- terminal status (durable.ts:1513, spec/0006
  // §S2c). This asserted 200 and a second flipped signer before. The same
  // envelope that refuses a signature above now refuses the decline as well;
  // the asymmetry this case was frozen to prove is gone. The code differs from
  // complete's 410 by design -- spec/0006 §S2c and INTENT question 3 -- and
  // both mean refused.
  const trailBefore = events(h, env.id);
  const stillDeclines = await decline(second, secondCookie);
  assert.equal(stillDeclines.status, 409, 'decline is refused on a declined envelope');
  assert.deepEqual(await body(stillDeclines), { error: 'This envelope is no longer active' });
  assert.equal(signerStatus(h, second.id), 'pending', 'the refused decline did not touch the signer');
  assert.equal(statusOf(h, env.id), 'declined');
  assert.deepEqual(events(h, env.id), trailBefore, 'the refused decline left an audit event');

  // ... including on a completed envelope, whose terminal status now survives.
  const done = seedEnvelope(h, { owner: 'owner@pumasi.ai', status: 'completed', signers: [{ email: 'x@example.test' }] });
  const doneCookie = await signerCookie(h, done.signers[0]);
  const doneTrail = events(h, done.id);
  const onDone = await decline(done.signers[0], doneCookie);
  assert.equal(onDone.status, 409);
  assert.deepEqual(await body(onDone), { error: 'This envelope is no longer active' });
  assert.equal(statusOf(h, done.id), 'completed', 'a completed envelope was overwritten by a decline');
  assert.equal(signerStatus(h, done.signers[0].id), 'pending');
  assert.deepEqual(events(h, done.id), doneTrail, 'the refused decline audited a declined event');

  // THE REPAIR, guard 2 of 3 -- already signed. A signer whose `signed` was
  // destroyed here before is now refused with complete's own words.
  const signed = seedEnvelope(h, {
    owner: 'owner@pumasi.ai', status: 'pending', signers: [{ email: 'y@example.test', status: 'signed' }],
  });
  const signedCookie = await signerCookie(h, signed.signers[0]);
  const signedTrail = events(h, signed.id);
  const onSigned = await decline(signed.signers[0], signedCookie);
  assert.equal(onSigned.status, 409);
  assert.deepEqual(await body(onSigned), { error: 'Already signed' });
  assert.equal(signerStatus(h, signed.signers[0].id), 'signed', 'a signed signer was flipped to declined');
  assert.equal(statusOf(h, signed.id), 'pending');
  assert.deepEqual(events(h, signed.id), signedTrail, 'the refused decline left an audit event');

  // THE REPAIR, guard 3 of 3 -- signing order. Declining out of turn is
  // refused for the same reason signing out of turn is (A-406).
  const queue = seedEnvelope(h, {
    owner: 'owner@pumasi.ai',
    status: 'pending',
    signers: [{ email: 'a@example.test', order: 1 }, { email: 'b@example.test', order: 2 }],
  });
  const lateCookie = await signerCookie(h, queue.signers[1]);
  const queueTrail = events(h, queue.id);
  const early = await decline(queue.signers[1], lateCookie);
  assert.equal(early.status, 409);
  assert.deepEqual(await body(early), { error: 'Earlier signers have not finished yet' });
  assert.equal(signerStatus(h, queue.signers[1].id), 'pending');
  assert.equal(statusOf(h, queue.id), 'pending');
  assert.deepEqual(events(h, queue.id), queueTrail, 'the refused decline left an audit event');
});

// ── A-408 · the wire word and the column word (:101, :1320, :1411) ──────────

test('A-408 a submitter reports `completed` while its column reads `signed`, and the token view has its own five words', async () => {
  const h = newHarness();
  const cookie = await signIn(h, 'owner@pumasi.ai');
  const env = seedEnvelope(h, {
    owner: 'owner@pumasi.ai',
    status: 'pending',
    signers: [{ email: 'first@example.test', order: 1 }, { email: 'second@example.test', order: 2 }],
  });
  const [first, second] = env.signers;
  const firstCookie = await signerCookie(h, first);
  await h.fetch(`/api/sign/${first.id}/complete`, { method: 'POST', cookie: firstCookie, body: JSON.stringify({ values: {}, consent_accepted: true, consent_version: 'pumasi-esign-consent-v1' }) });

  // outSubmitterStatus (durable.ts:101) rewrites `signed` to `completed` on the
  // way out. So one payload carries the word `completed` for a SUBMITTER whose
  // column says `signed`, beside a SUBMISSION that is still `pending`.
  assert.equal(signerStatus(h, first.id), 'signed');
  const out = await body(await h.fetch(`/api/submissions/${env.id}`, { cookie }));
  assert.equal(out.status, 'pending');
  assert.equal(out.submitters.find((s: any) => s.user.email === 'first@example.test').status, 'completed');
  assert.equal(out.submitters.find((s: any) => s.user.email === 'second@example.test').status, 'pending');

  // The signing session reports the same rewritten word for the signer itself.
  const me = await body(await h.fetch(`/api/sign/${first.id}`, { cookie: firstCookie }));
  assert.equal(me.my_status, 'completed');
  assert.equal(me.submission.status, 'pending');

  // The public token view has a fifth vocabulary of its own (durable.ts:1320),
  // and it is checked in a fixed order: cancelled, then declined, then
  // completed, then already_signed, then open.
  const view = async (token: string) => (await body(await h.fetch(`/api/sign/token/${token}`)))?.status;
  assert.equal(await view(first.token), 'already_signed', 'signed signer, pending envelope');
  assert.equal(await view(second.token), 'open');

  const cases: [string, string | undefined, string][] = [
    ['cancelled', undefined, 'cancelled'],
    ['declined', undefined, 'declined'],
    ['completed', undefined, 'completed'],
    ['pending', 'declined', 'declined'],
    // Precedence, not a new state: a cancelled envelope whose signer declined
    // reports `cancelled`, because cancelled is tested first.
    ['cancelled', 'declined', 'cancelled'],
  ];
  for (const [subStatus, signerState, expected] of cases) {
    const e = seedEnvelope(h, {
      owner: 'owner@pumasi.ai', status: subStatus,
      signers: [{ email: 'z@example.test', status: signerState ?? 'pending' }],
    });
    assert.equal(await view(e.signers[0].token), expected, `${subStatus}/${signerState ?? 'pending'}`);
  }

  // An unknown token is a 404, not an `open` view of nothing.
  assert.equal((await h.fetch('/api/sign/token/nosuchtoken')).status, 404);
});

// ── A-409 · `expired` is claimed by the product and never written ───────────

test('A-409 the worker never writes the `expired` status: a past expires_at transitions nothing and there is no job that could', async () => {
  const h = newHarness();
  const cookie = await signIn(h, 'owner@pumasi.ai');
  const past = new Date(Date.now() - 86_400_000).toISOString();
  const pdf = await makePdf(['PAST-DEADLINE AGREEMENT']);
  const env = seedEnvelope(h, {
    owner: 'owner@pumasi.ai', status: 'pending', expiresAt: past,
    pdf,
    signers: [{ email: 'late@example.test' }],
  });

  // CLAUDE.md names six envelope statuses and `expired` is one of them. In
  // durable.ts the string `expired` occurs exactly twice, both inside the
  // message "Invalid or expired verification code" (:803, :1359). Nothing
  // reads submissions.expires_at to transition anything, so this case records
  // an ABSENCE -- and an absence is only worth testing if it is driven.

  // The deadline is echoed back, so the column is carried, not ignored.
  const out = await body(await h.fetch(`/api/submissions/${env.id}`, { cookie }));
  assert.equal(out.expires_at, past);
  assert.equal(out.status, 'pending', 'a day past its deadline and still pending');

  // Every owner action that touches status leaves it pending, not expired.
  assert.equal((await h.fetch(`/api/submissions/${env.id}/remind`, { method: 'POST', cookie })).status, 200);
  assert.equal(statusOf(h, env.id), 'pending');
  assert.equal((await body(await h.fetch('/api/submissions?mine=sent', { cookie })))[0].status, 'pending');

  // The signer's own two views are `open`, and signing still succeeds and
  // completes: the deadline stops nothing at all.
  assert.equal((await body(await h.fetch(`/api/sign/token/${env.signers[0].token}`))).status, 'open');
  const sc = await signerCookie(h, env.signers[0]);
  assert.equal((await body(await h.fetch(`/api/sign/${env.signers[0].id}`, { cookie: sc }))).submission.expires_at, past);
  const done = await h.fetch(`/api/sign/${env.signers[0].id}/complete`, {
    method: 'POST', cookie: sc, body: JSON.stringify({ values: {}, consent_accepted: true, consent_version: 'pumasi-esign-consent-v1' }),
  });
  assert.equal(done.status, 200);
  assert.deepEqual(await body(done), { ok: true, status: 'completed' });
  assert.equal(statusOf(h, env.id), 'completed', 'an expired envelope completed normally');

  // There is no mechanism that could have expired it. backend/ flips this
  // status from POST /api/jobs/daily; the worker has no such route, no
  // `scheduled` handler and no cron trigger in wrangler.jsonc -- so this is
  // not a job that failed to run, it is a job that does not exist.
  const job = await h.fetch('/api/jobs/daily', { method: 'POST', cookie });
  assert.equal(job.status, 404);
  assert.deepEqual(await body(job), { error: 'Endpoint not found' });

  // RECORDED, NOT ENDORSED -- spec/0005 §S6.3. Red on any assertion above
  // means someone gave the worker an expiry sweep, which is a product decision
  // and a roadmap/BACKLOG.md entry, not a repair that rides in a test packet.
  assert.equal(
    (h.db.prepare(`SELECT count(*) AS n FROM submissions WHERE status = 'expired'`).get() as { n: number }).n,
    0,
    'no submission in this suite ever reached the status the product documents',
  );
});
