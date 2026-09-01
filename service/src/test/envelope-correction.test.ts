/**
 * Frozen acceptance cases A-417 – A-419 · spec/0008.
 *
 * roadmap/BACKLOG.md item 1 at `3edd06f`: the envelope-settings dialog
 * silently deletes the sender's message to signers. These drive the Durable
 * Object that answers sign.pumasi.ai through its own `fetch()` -- the same
 * entrypoint worker.ts uses -- over the PATCH route the two correction
 * dialogs share.
 *
 * WHY A SEPARATE FILE FROM envelope-expiry.test.ts. That file holds
 * A-410 – A-416, it is frozen under spec/0007, and A-416 covers the SAME
 * route for a different property. Nothing here amends it: A-416's own
 * assertion that a settings-only PATCH does not blank the TITLE is exactly
 * the assertion this spec generalises to the message, and it still passes
 * unchanged. spec/0008 §S6 checks that assertion by assertion, so
 * pumasi/DECISIONS.md Q-030 -- may a builder amend a frozen case -- is not
 * reached here and no reading of it is taken.
 *
 * Read spec/0005/SPEC.md §S1 before trusting a green run: this is SQLite, but
 * it is not workerd's SQLite (spec/0004 §S1c), and these are assertions about
 * durable.ts's own logic rather than about Cloudflare. And a green count here
 * says NOTHING about sign.pumasi.ai, which serves a build made before any of
 * this -- pumasi/DECISIONS.md Q-018 default part (c), and spec/0008 §S8.
 *
 * Mail is deliberately UNCONFIGURED, as in the sibling suites: sendMail throws
 * without GMAIL_SA_KEY/MAIL_IMPERSONATE and mailOrLog catches it, so any
 * `[mail] send to ... failed` lines in this suite's diagnostics are expected.
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { newHarness, cookieValue, Harness } from './support/durable-harness.js';

// ── seeding · the sibling suites' helpers, deliberately re-stated ───────────
//
// Neither sibling exports these and this file does not import from them: a
// frozen case that breaks because a NEIGHBOURING frozen case's helper moved is
// a case that measures the wrong thing. Three small copies is the cheaper
// failure (pumasi/lessons/L-007 cuts the other way for RULES; this is a
// fixture). The one difference from envelope-expiry.test.ts's copy is that
// this one can seed a `message`, which is the whole subject here.

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

interface Seeded { id: string; publicUid: string; signers: { id: string; token: string; email: string }[] }

function seedEnvelope(
  h: Harness,
  opts: {
    owner: string; status?: string; title?: string; message?: string | null;
    expiresAt?: string | null; signers?: { email: string; name?: string }[];
  },
): Seeded {
  const id = uid('sub');
  const publicUid = uid('pub');
  const now = new Date().toISOString();
  h.db.prepare(
    `INSERT INTO submissions (id, public_uid, title, message, created_by, status, expires_at, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
  ).run(
    id, publicUid, opts.title ?? 'Mutual NDA', opts.message ?? null, opts.owner,
    opts.status ?? 'pending', opts.expiresAt ?? null, now, now,
  );

  const signers = (opts.signers ?? [{ email: 'signer@example.test' }]).map((s, i) => {
    const sid = uid('subtr');
    const token = uid('tok');
    h.db.prepare(
      `INSERT INTO submitters (id, submission_id, name, email, role, signing_order, token, status, is_cc, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    ).run(sid, id, s.name ?? `Signer ${i + 1}`, s.email, 'Signer', i + 1, token, 'pending', 0, now);
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

const body = (res: Response) => res.json() as Promise<any>;

/** The stored row, not the response body -- what actually survived the write. */
const stored = (h: Harness, id: string): any =>
  h.db.prepare(`SELECT * FROM submissions WHERE id = ?`).get(id);

const auditRow = (h: Harness, id: string, type: string): any =>
  h.db.prepare(`SELECT * FROM audit_events WHERE submission_id = ? AND event_type = ?`).get(id, type);

/** The `changed` list on the LATEST `corrected` row, sorted, or undefined. */
function lastChanged(h: Harness, id: string): string[] | undefined {
  // `rowid`, not `created_at`: audit ids are random UUIDs (durable.ts:302) and
  // several PATCHes in one test land in the same millisecond, so neither column
  // orders these deterministically. rowid is insertion order.
  const row = h.db.prepare(
    `SELECT details_json FROM audit_events WHERE submission_id = ? AND event_type = 'corrected'
     ORDER BY rowid DESC LIMIT 1`,
  ).get(id) as { details_json: string | null } | undefined;
  const changed = row?.details_json ? JSON.parse(row.details_json).changed : undefined;
  return changed ? changed.slice().sort() : undefined;
}

const NOTE = 'Please sign by Friday — this replaces the draft I sent Tuesday.';
const FUTURE = new Date(Date.now() + 86_400_000).toISOString();

/** Exactly the body EnvelopeDetailView.vue:428 sends. Nothing else, ever. */
const SETTINGS_PATCH = {
  expires_at: FUTURE,
  reminders_enabled: false,
  reminder_interval_days: 7,
};

// ── A-417 · the defect · a settings-only PATCH must not touch the message ──

test('A-417 a settings-only PATCH leaves the sender\'s message to signers exactly as it was, on the stored row, in the response and on the recipient\'s own view -- and audits the settings only', async () => {
  const h = newHarness();
  const cookie = await signIn(h, 'owner@pumasi.ai');
  const env = seedEnvelope(h, {
    owner: 'owner@pumasi.ai', status: 'pending', title: 'Mutual NDA', message: NOTE,
    signers: [{ email: 'signer@example.test' }],
  });

  assert.equal(stored(h, env.id).message, NOTE, 'the fixture did not seed a message');

  // EnvelopeDetailView.vue:428 sends these three and NOT `message`. Before
  // this spec that omission wrote NULL over the note and the dialog closed on
  // "Envelope settings updated." spec/0008 §S1.
  const res = await h.fetch(`/api/submissions/${env.id}`, {
    method: 'PATCH', cookie, body: JSON.stringify(SETTINGS_PATCH),
  });
  assert.equal(res.status, 200);

  // 1. The stored row -- the thing the old code overwrote.
  const row = stored(h, env.id);
  assert.equal(row.message, NOTE, 'a settings-only PATCH deleted the sender\'s message');
  assert.equal(row.title, 'Mutual NDA', 'a settings-only PATCH blanked the title');

  // 2. The response the dialog reloads from, so the SPA never shows it gone.
  assert.equal((await body(res)).message, NOTE);

  // 3. The settings the PATCH was actually about still land -- this must not
  //    be a fix that works by ignoring the body. spec/0007 §S1d.
  assert.equal(row.expires_at, FUTURE);
  assert.equal(row.reminders_enabled, 0);
  assert.equal(row.reminder_interval_days, 7);

  // 4. And the point of the message: the recipient still reads it. This is
  //    what makes the defect data loss rather than a display bug.
  const signer = env.signers[0];
  const sc = await signerCookie(h, signer);
  const view = await body(await h.fetch(`/api/sign/${signer.id}`, { cookie: sc }));
  assert.equal(view.submission.message, NOTE);

  // 5. The history names the three settings and does NOT claim a title or a
  //    message change, because there was none. spec/0008 §S3.
  assert.deepEqual(lastChanged(h, env.id), ['expiration date', 'reminder interval', 'reminders']);
});

// ── A-418 · its pair · an explicit null still clears it ────────────────────

test('A-418 the correct-details dialog still sets, replaces and clears the message: an explicit null clears it, a string replaces it, and each is named in the history', async () => {
  const h = newHarness();
  const cookie = await signIn(h, 'owner@pumasi.ai');
  const env = seedEnvelope(h, {
    owner: 'owner@pumasi.ai', status: 'pending', title: 'Mutual NDA', message: NOTE,
  });
  const patch = (b: unknown) => h.fetch(`/api/submissions/${env.id}`, {
    method: 'PATCH', cookie, body: JSON.stringify(b),
  });

  // 1. `message: null` is what EnvelopeDetailView.vue:380 sends when the
  //    sender empties the box (`message: message || null`). It must still
  //    mean CLEAR IT -- the fix distinguishes absent from present-and-null,
  //    it does not make the message unremovable. spec/0008 §S2.
  assert.equal((await patch({ title: 'Mutual NDA', message: null })).status, 200);
  assert.equal(stored(h, env.id).message, null, 'an explicit null failed to clear the message');
  assert.deepEqual(lastChanged(h, env.id), ['message'], 'the history did not name the clearing');

  // 2. And a string sets one on an envelope that has none.
  assert.equal((await patch({ title: 'Mutual NDA', message: NOTE })).status, 200);
  assert.equal(stored(h, env.id).message, NOTE);
  assert.deepEqual(lastChanged(h, env.id), ['message']);

  // 3. An empty string is a value, not an absence: `String('')` is stored, and
  //    the SPA never sends one (it sends `|| null`). Pinned so a later `||`
  //    creeping into the worker changes a measured behaviour rather than an
  //    assumed one.
  assert.equal((await patch({ message: '' })).status, 200);
  assert.equal(stored(h, env.id).message, '');

  // 4. Truncation is unchanged at 2000 characters.
  const long = 'x'.repeat(2500);
  assert.equal((await patch({ message: long })).status, 200);
  assert.equal(stored(h, env.id).message, long.slice(0, 2000));

  // 5. A PATCH that changes neither writes a `corrected` row with no `changed`
  //    key at all, rather than an empty list -- the history line falls back to
  //    "Corrected by X" (EnvelopeDetailView.vue:610).
  //
  //    THE BODY SHAPE HERE IS THE POINT and is pinned deliberately: both keys
  //    are PRESENT and carry the values already stored, which is exactly what
  //    EnvelopeDetailView.vue:380 sends when a sender opens the dialog and
  //    saves without editing. Omitting the keys instead would leave this case
  //    green under a presence-keyed audit list too, and it would then be
  //    measuring nothing (pumasi/lessons/L-006). Raised by glm's spec review,
  //    reviews/20260831-214423-spec-glm.md §2. spec/0008 §S3.
  const before = stored(h, env.id);
  assert.equal((await patch({ title: before.title, message: before.message })).status, 200);
  assert.equal(lastChanged(h, env.id), undefined, 'a no-op correction claimed a change');
});

// ── A-419 · the title, generalised from A-416, and the terminal guard ──────

test('A-419 a title change is named in the history alongside the message, and neither is refused on a terminal envelope -- the 409 still belongs to the settings alone', async () => {
  const h = newHarness();
  const cookie = await signIn(h, 'owner@pumasi.ai');
  const env = seedEnvelope(h, {
    owner: 'owner@pumasi.ai', status: 'pending', title: 'Mutual NDA', message: NOTE,
  });
  const patch = (b: unknown) => h.fetch(`/api/submissions/${env.id}`, {
    method: 'PATCH', cookie, body: JSON.stringify(b),
  });

  // Both at once, which is what EnvelopeDetailView.vue:380 always sends.
  assert.equal((await patch({ title: 'Mutual NDA (rev 2)', message: 'Signed copy attached.' })).status, 200);
  assert.deepEqual(lastChanged(h, env.id), ['message', 'title']);

  // Title alone, message untouched because the body never mentioned it.
  assert.equal((await patch({ title: 'Mutual NDA (rev 3)' })).status, 200);
  assert.deepEqual(lastChanged(h, env.id), ['title']);
  assert.equal(stored(h, env.id).message, 'Signed copy attached.');

  // A title long enough to be truncated IS a change, and says so.
  assert.equal((await patch({ title: 'y'.repeat(250) })).status, 200);
  assert.equal(stored(h, env.id).title, 'y'.repeat(200));
  assert.deepEqual(lastChanged(h, env.id), ['title']);

  // A body carrying a settings field AND content together, on a LIVE
  // envelope: the two lists are per-field and must not interfere. Neither
  // dialog sends this shape -- their bodies are disjoint -- so it arises only
  // for a direct API caller, and glm's spec review asked for it as a handover
  // line rather than a case. It is a case, because it is three lines.
  assert.equal(
    (await patch({ message: 'Combined body.', reminder_interval_days: 14 })).status, 200,
  );
  assert.equal(stored(h, env.id).message, 'Combined body.');
  assert.equal(stored(h, env.id).reminder_interval_days, 14);
  assert.equal(stored(h, env.id).title, 'y'.repeat(200), 'an unmentioned title moved');
  assert.deepEqual(lastChanged(h, env.id), ['message', 'reminder interval']);

  // The 409 guard stays keyed on the SETTINGS fields. spec/0007 §S3d said in
  // terms that "a body with no settings field is unaffected: title and message
  // keep the behaviour they had, on every status"; widening the audit list must
  // not quietly widen the refusal with it. spec/0008 §S3.
  h.db.prepare(`UPDATE submissions SET status = 'completed' WHERE id = ?`).run(env.id);
  assert.equal((await patch({ title: 'Post-completion correction', message: 'Still allowed.' })).status, 200);
  assert.equal(stored(h, env.id).title, 'Post-completion correction');
  assert.equal(stored(h, env.id).message, 'Still allowed.');

  // ...and a settings field on the same terminal envelope is still refused,
  // and still writes nothing, including no audit row for the attempt.
  const auditedBefore = auditRow(h, env.id, 'corrected');
  const late = await patch({ title: 'Should not land', expires_at: FUTURE });
  assert.equal(late.status, 409);
  assert.deepEqual(await body(late), { error: 'This envelope is already closed' });
  assert.equal(stored(h, env.id).title, 'Post-completion correction', 'the refused correction wrote the title anyway');
  assert.equal(stored(h, env.id).expires_at, null);
  assert.deepEqual(lastChanged(h, env.id), ['message', 'title'], 'the refused correction audited something');
  assert.ok(auditedBefore, 'fixture: expected a prior corrected row to compare against');
});
