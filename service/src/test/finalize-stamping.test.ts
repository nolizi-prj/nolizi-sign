/**
 * Frozen acceptance cases A-600 – A-609 · spec/0010; A-608 amended and A-610
 * added by spec/0011.
 *
 * Residual A of roadmap/BACKLOG.md item 2: `finalize()`'s STAMPING BRANCH --
 * `durable.ts:1770`-`:1793`, the only uncovered path that produces the artefact
 * VALUE.md C1 promises. These drive the Durable Object that answers
 * sign.pumasi.ai through its own `fetch()` -- the same entrypoint worker.ts
 * uses -- from a sender signing in to the executed PDF coming back down
 * `GET /api/files/signed-pdf/:id`, and then READ THE PDF.
 *
 * WHY READING IT IS THE POINT. The two cases that touched stamping before this
 * file (`stamping.test.ts`, `stamping-multi-signer.test.ts`) assert SHAPE: the
 * result is longer than the input, it has two pages, two hashes differ. That
 * trio survives almost any mutation of WHAT is stamped -- the wrong signer's
 * name on every line, the document's own text dropped, a field stamped onto
 * the wrong page. spec/0010 §S7a is the mutation table that measures exactly
 * that rather than asserting it.
 *
 * THEY CHARACTERIZE. THEY DO NOT ADJUDICATE. A-607's two observations remain
 * RECORDED, NOT ENDORSED. A-608 was amended by spec/0011 when its strand was
 * taken. Red at A-607
 * means "someone took the backlog entry", not "someone broke the worker". The
 * idiom is spec/0004 §S4's, by way of spec/0005 A-409 and spec/0009 A-502.
 *
 * Read spec/0010 §S1 before trusting a green run. This is SQLite, but it is not
 * workerd's SQLite (spec/0004 §S1c); the R2 binding is an in-memory stand-in
 * (support/pdf-probe.ts) and evidence here is about `storage/r2.ts` and
 * `durable.ts`, not about Cloudflare; and the deployed bundle is not this tree
 * (BACKLOG.md item 1, pumasi/DECISIONS.md Q-012).
 *
 * Mail is deliberately UNCONFIGURED. sendMail throws without
 * GMAIL_SA_KEY/MAIL_IMPERSONATE and mailOrLog catches it, so every notifying
 * path runs to completion offline. The `[mail] send to ... failed` lines in
 * this suite's diagnostics are that, and they are expected.
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';

import { newHarness, cookieValue, Harness } from './support/durable-harness.js';
import { FakeBucket, TINY_PNG_DATA_URL, fakeBucket, makePdf, readPdf } from './support/pdf-probe.js';

// ── seeding ─────────────────────────────────────────────────────────────────

let seq = 0;
const uid = (p: string) => `${p}-${(seq += 1).toString(16)}-${Math.random().toString(16).slice(2, 8)}`;

const sha256 = (bytes: Uint8Array): string => createHash('sha256').update(bytes).digest('hex');

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

interface SeedSigner { email: string; name: string; role?: string; order?: number; cc?: boolean }

interface SeedField {
  /** Index into the `signers` array this field belongs to. */
  signer: number;
  type: 'signature' | 'initials' | 'name' | 'date' | 'text' | 'checkbox' | 'label';
  /** 0-BASED, as the web contract stores it. finalize() adds one. */
  page?: number;
  x?: number; y?: number; w?: number; h?: number;
  required?: boolean;
  defaultValue?: string;
}

interface Seeded {
  id: string;
  publicUid: string;
  title: string;
  originalPdf: Uint8Array | null;
  originalHash: string | null;
  signers: { id: string; token: string; email: string; name: string }[];
  fields: { id: string; type: string; signer: number }[];
}

/**
 * A `pending` envelope carrying a REAL PDF, its signers and its fields.
 *
 * Deliberately not built through POST /api/submissions: the wizard's own
 * creation route is a separate strand of residual A and dragging it in would
 * make a red here ambiguous between two subjects. Every transition below --
 * verify, signature upload, complete, finalize, download -- is driven through
 * `fetch()`; only the starting position is seeded, which is
 * envelope-lifecycle.test.ts's convention and reason.
 *
 * `pdf: null` with `key` set is A-608's position: the record points at a
 * document the store does not hold.
 */
function seedEnvelope(
  h: Harness,
  opts: {
    owner: string;
    title?: string;
    pdf?: Uint8Array | null;
    /** When set, the PDF lives in R2 under this key rather than in the blob column. */
    key?: string | null;
    bucket?: FakeBucket;
    signers: SeedSigner[];
    fields: SeedField[];
    pageCount?: number;
  },
): Seeded {
  const id = uid('sub');
  const publicUid = uid('pub');
  const title = opts.title ?? 'Mutual NDA';
  const now = new Date().toISOString();
  const pdf = opts.pdf ?? null;
  const key = opts.key ?? null;

  if (key && pdf && opts.bucket) {
    opts.bucket.objects.set(key, { data: pdf, contentType: 'application/pdf' });
  }

  h.db.prepare(
    `INSERT INTO submissions (id, public_uid, title, message, created_by, status,
                              original_pdf_blob, original_pdf_key, original_hash, page_count, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?)`,
  ).run(id, publicUid, title, null, opts.owner, key ? null : pdf, key, pdf ? sha256(pdf) : '0'.repeat(64), opts.pageCount ?? 1, now, now);

  const signers = opts.signers.map((s, i) => {
    const sid = uid('subtr');
    const token = uid('tok');
    h.db.prepare(
      `INSERT INTO submitters (id, submission_id, name, email, role, signing_order, token, status, is_cc, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)`,
    ).run(sid, id, s.name, s.email, s.role ?? 'Signer', s.order ?? i + 1, token, s.cc ? 1 : 0, now);
    return { id: sid, token, email: s.email, name: s.name };
  });

  const fields = opts.fields.map((f) => {
    const fid = uid('fld');
    h.db.prepare(
      `INSERT INTO submission_fields (id, submission_id, submitter_id, type, page, x, y, width, height,
                                      value, required, default_value)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?)`,
    ).run(
      fid, id, signers[f.signer].id, f.type, f.page ?? 0,
      f.x ?? 0.1, f.y ?? 0.2, f.w ?? 0.4, f.h ?? 0.05,
      f.required === false ? 0 : 1, f.defaultValue ?? null,
    );
    return { id: fid, type: f.type, signer: f.signer };
  });

  return {
    id, publicUid, title,
    originalPdf: pdf,
    originalHash: pdf ? sha256(pdf) : null,
    signers, fields,
  };
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

/** Upload a drawn signature through the real route; returns its id. */
async function uploadSignature(h: Harness, submitterId: string, cookie: string): Promise<string> {
  const res = await h.fetch(`/api/sign/${submitterId}/signature`, {
    method: 'POST', cookie,
    body: JSON.stringify({ image: TINY_PNG_DATA_URL }),
  });
  assert.equal(res.status, 200);
  const body = await res.json() as { signature_id: string };
  assert.ok(body.signature_id, 'signature upload returned no id');
  return body.signature_id;
}

/** POST /api/sign/:id/complete, with the request metadata the certificate quotes. */
async function complete(
  h: Harness,
  submitterId: string,
  cookie: string,
  values: Record<string, unknown>,
  meta: { ip?: string; userAgent?: string } = {},
): Promise<Response> {
  return h.fetch(`/api/sign/${submitterId}/complete`, {
    method: 'POST', cookie,
    headers: {
      'cf-connecting-ip': meta.ip ?? '203.0.113.7',
      'user-agent': meta.userAgent ?? 'PumasiSignTest/1.0',
    },
    body: JSON.stringify({ values, consent_accepted: true, consent_version: 'pumasi-esign-consent-v1' }),
  });
}

// ── reading back ────────────────────────────────────────────────────────────

interface SubmissionRow {
  status: string;
  completed_at: string | null;
  completed_pdf_key: string | null;
  completed_pdf_blob: Uint8Array | null;
}

const submissionRow = (h: Harness, id: string): SubmissionRow =>
  h.db.prepare(
    `SELECT status, completed_at, completed_pdf_key, completed_pdf_blob FROM submissions WHERE id = ?`,
  ).get(id) as unknown as SubmissionRow;

/** The `completed` audit row's parsed details, or null when it carries none. */
function completedAudit(h: Harness, id: string): { originalHash?: string; completedHash?: string } | null {
  const row = h.db.prepare(
    `SELECT details_json FROM audit_events WHERE submission_id = ? AND event_type = 'completed'`,
  ).get(id) as { details_json: string | null } | undefined;
  assert.ok(row, 'no `completed` audit event was written');
  return row.details_json === null ? null : JSON.parse(row.details_json);
}

const auditCount = (h: Harness, id: string, type: string): number =>
  (h.db.prepare(
    `SELECT COUNT(*) AS n FROM audit_events WHERE submission_id = ? AND event_type = ?`,
  ).get(id, type) as { n: number }).n;

/** Download the executed document as the given principal. */
async function downloadSigned(h: Harness, id: string, cookie: string): Promise<Response> {
  return h.fetch(`/api/files/signed-pdf/${id}`, { cookie });
}

/** Every text run on the certificate page, which is always the last one. */
const certificateOf = (probe: { pages: string[][] }) => probe.pages[probe.pages.length - 1];

/** The one line of a text list that starts with `prefix`. Fails loudly when absent. */
function line(lines: string[], prefix: string): string {
  const hit = lines.filter((l) => l.startsWith(prefix));
  assert.equal(hit.length, 1, `expected exactly one line starting "${prefix}", got ${JSON.stringify(hit)}`);
  return hit[0];
}

// ── A-600 ───────────────────────────────────────────────────────────────────

test('A-600 · a fully signed envelope really is stamped: the whole chain executes and the artefact is new', async () => {
  // THE READER GUARD, and the reason it comes first. Every content case below
  // reads text out of a PDF. If the reader found nothing -- wrong stream, wrong
  // operator, a pdf-lib upgrade -- those cases would pass vacuously by
  // asserting things about an empty list. This case makes that impossible: it
  // pins that the reader finds the SENDER'S OWN text in the document that came
  // back, and that the returned artefact is not the one that went in.
  //
  // Mutation that turns it red: replace stampAndCertifyPdf's return with the
  // input bytes; drop the addPage; make finalize skip storePdf.
  const h = newHarness();
  const owner = await signIn(h, 'owner@pumasi.ai');
  const pdf = await makePdf(['CONFIDENTIALITY UNDERTAKING']);
  const env = seedEnvelope(h, {
    owner: 'owner@pumasi.ai',
    pdf,
    signers: [{ email: 'ada@example.test', name: 'Ada Lovelace' }],
    fields: [{ signer: 0, type: 'signature' }],
  });

  const cookie = await signerCookie(h, env.signers[0]);
  const sig = await uploadSignature(h, env.signers[0].id, cookie);
  const res = await complete(h, env.signers[0].id, cookie, { [env.fields[0].id]: sig });

  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { ok: true, status: 'completed' });

  const row = submissionRow(h, env.id);
  assert.equal(row.status, 'completed');
  assert.ok(row.completed_at, 'completed_at was not stamped');

  // The executed document exists, and it is NOT the original.
  const stored = row.completed_pdf_blob;
  assert.ok(stored, 'no executed PDF was stored');
  assert.notEqual(sha256(new Uint8Array(stored)), env.originalHash);

  // The audit trail's `originalHash` is the SHA-256 THIS CASE computed over the
  // bytes it seeded -- so the number in the record is checked against an
  // independently derived one, not against itself.
  const details = completedAudit(h, env.id);
  assert.ok(details, 'the completed audit row carried no hashes');
  assert.equal(details.originalHash, env.originalHash);
  assert.equal(details.completedHash, sha256(new Uint8Array(stored)));

  // And the reader works: the sender's own words survived into the artefact.
  const probe = await readPdf(new Uint8Array(stored));
  assert.ok(probe.all.length > 0, 'the PDF reader found no text at all -- every content case below would be vacuous');
  assert.ok(probe.pages[0].includes('CONFIDENTIALITY UNDERTAKING'));
});

// ── A-601 ───────────────────────────────────────────────────────────────────

test('A-601 · the certificate names this envelope, this title and this document\'s fingerprint', async () => {
  // Mutation: stamp a constant envelope id; drop the title line; print the
  // completed hash where the original one belongs.
  const h = newHarness();
  await signIn(h, 'owner@pumasi.ai');
  const pdf = await makePdf(['SUPPLY AGREEMENT']);
  const env = seedEnvelope(h, {
    owner: 'owner@pumasi.ai',
    title: 'Supply Agreement 2026',
    pdf,
    signers: [{ email: 'ada@example.test', name: 'Ada Lovelace' }],
    fields: [{ signer: 0, type: 'signature' }],
  });

  const cookie = await signerCookie(h, env.signers[0]);
  const sig = await uploadSignature(h, env.signers[0].id, cookie);
  assert.equal((await complete(h, env.signers[0].id, cookie, { [env.fields[0].id]: sig })).status, 200);

  const row = submissionRow(h, env.id);
  const probe = await readPdf(new Uint8Array(row.completed_pdf_blob!));
  const cert = certificateOf(probe);

  // The envelope's PUBLIC uid, not its internal id -- that distinction is the
  // whole point of the column and a reader should be able to see it pinned.
  assert.equal(line(cert, 'Envelope ID:'), `Envelope ID: ${env.publicUid}  |  Completed: ${row.completed_at}`);
  assert.equal(line(cert, 'Title:'), `Title: ${env.title}`);
  assert.equal(line(cert, 'Original SHA-256:'), `Original SHA-256: ${env.originalHash}`);

  // The certificate is a certificate: it says what it is and under what.
  assert.ok(cert.some((l) => l.includes('Signature Certificate and Audit Trail')));
  assert.ok(cert.some((l) => l.includes('ESIGN Act and eIDAS')));
});

// ── A-602 ───────────────────────────────────────────────────────────────────

test('A-602 · each signer gets their own block, from their own request; a CC recipient gets none', async () => {
  // Two signers in order, each finishing from a different address. The
  // certificate must carry each one's OWN email, OWN timestamp and OWN IP --
  // a mutation that stamps the first signer's metadata against every block
  // passes a shape assertion and fails here.
  //
  // Mutation: index signers by position rather than by id in stamping.ts; drop
  // `AND is_cc = 0` from finalize's submitter query; pass `now` as every
  // signer's signedAt.
  const h = newHarness();
  const owner = await signIn(h, 'owner@pumasi.ai');
  const pdf = await makePdf(['JOINT VENTURE TERMS']);
  const env = seedEnvelope(h, {
    owner: 'owner@pumasi.ai',
    pdf,
    signers: [
      { email: 'ada@example.test', name: 'Ada Lovelace', role: 'Signer', order: 1 },
      { email: 'grace@example.test', name: 'Grace Hopper', role: 'Approver', order: 2 },
      { email: 'watcher@example.test', name: 'Cecil Watcher', role: 'Copied', order: 3, cc: true },
    ],
    fields: [
      { signer: 0, type: 'signature' },
      { signer: 1, type: 'signature', y: 0.4 },
    ],
  });

  const first = await signerCookie(h, env.signers[0]);
  const firstSig = await uploadSignature(h, env.signers[0].id, first);
  const r1 = await complete(h, env.signers[0].id, first, { [env.fields[0].id]: firstSig }, { ip: '198.51.100.11' });
  assert.equal(r1.status, 200);
  assert.equal((await r1.json() as any).status, 'signed', 'the envelope completed before the second signer');

  const second = await signerCookie(h, env.signers[1]);
  const secondSig = await uploadSignature(h, env.signers[1].id, second);
  const r2 = await complete(h, env.signers[1].id, second, { [env.fields[1].id]: secondSig }, { ip: '198.51.100.22' });
  assert.equal(r2.status, 200);
  assert.equal((await r2.json() as any).status, 'completed');

  const row = submissionRow(h, env.id);
  const cert = certificateOf(await readPdf(new Uint8Array(row.completed_pdf_blob!)));

  const signedAt = (id: string) =>
    (h.db.prepare(`SELECT signed_at FROM submitters WHERE id = ?`).get(id) as { signed_at: string }).signed_at;

  assert.ok(cert.includes('Ada Lovelace (Signer)'));
  assert.equal(line(cert, 'Email: ada@'), 'Email: ada@example.test');
  assert.ok(cert.includes(`Signed at: ${signedAt(env.signers[0].id)} UTC`));
  assert.ok(cert.includes('IP Address: 198.51.100.11'));

  assert.ok(cert.includes('Grace Hopper (Approver)'));
  assert.equal(line(cert, 'Email: grace@'), 'Email: grace@example.test');
  assert.ok(cert.includes(`Signed at: ${signedAt(env.signers[1].id)} UTC`));
  assert.ok(cert.includes('IP Address: 198.51.100.22'));

  // The two blocks are distinct records, not one record printed twice.
  assert.notEqual(signedAt(env.signers[0].id), signedAt(env.signers[1].id));

  // The CC recipient never signed and is not certified as having done so --
  // finalize's `AND is_cc = 0`. They still get the completion email, which is
  // the `for (const s of ...)` loop with no is_cc filter, and that asymmetry is
  // deliberate; see spec/0010 §S4.
  assert.ok(!cert.some((l) => l.includes('Cecil Watcher')), 'a CC recipient was certified as a signer');
  assert.ok(!cert.some((l) => l.includes('watcher@example.test')));

  // Exactly one completion, and the owner can fetch what it produced.
  assert.equal(auditCount(h, env.id, 'completed'), 1);
  assert.equal((await downloadSigned(h, env.id, owner)).status, 200);
});

// ── A-603 ───────────────────────────────────────────────────────────────────

test('A-603 · what the signer entered is stamped onto the page, and what they did not enter is filled from the record', async () => {
  // The product's actual job on the body pages. Five field types, one case,
  // because each is one line of stamping.ts's `if` ladder and splitting them
  // would triple the setup for no extra evidence.
  //
  // Mutation: stamp `field.id` instead of `field.value`; drop the `label`
  // default_value fallback in finalize's field mapping; make the checkbox draw
  // unconditionally; take the `name` field's value from the client.
  const h = newHarness();
  await signIn(h, 'owner@pumasi.ai');
  const pdf = await makePdf(['SCHEDULE 1']);
  const env = seedEnvelope(h, {
    owner: 'owner@pumasi.ai',
    pdf,
    signers: [{ email: 'ada@example.test', name: 'Ada Lovelace' }],
    fields: [
      { signer: 0, type: 'signature' },
      { signer: 0, type: 'text', y: 0.3 },
      { signer: 0, type: 'name', y: 0.4 },
      { signer: 0, type: 'date', y: 0.5, required: false },
      { signer: 0, type: 'checkbox', y: 0.6, w: 0.03, h: 0.02 },
      { signer: 0, type: 'checkbox', y: 0.65, w: 0.03, h: 0.02 },
      { signer: 0, type: 'label', y: 0.7, defaultValue: 'FOR INTERNAL USE ONLY' },
    ],
  });
  const [sigF, textF, nameF, dateF, tickedF, untickedF] = env.fields;

  const cookie = await signerCookie(h, env.signers[0]);
  const sig = await uploadSignature(h, env.signers[0].id, cookie);
  const res = await complete(h, env.signers[0].id, cookie, {
    [sigF.id]: sig,
    [textF.id]: 'Registered office: 4 Marylebone Road',
    // The client tries to name someone else. The stamp must not take it.
    [nameF.id]: 'Somebody Else Entirely',
    [tickedF.id]: true,
    [untickedF.id]: false,
  });
  assert.equal(res.status, 200);

  const row = submissionRow(h, env.id);
  const probe = await readPdf(new Uint8Array(row.completed_pdf_blob!));
  const body = probe.pages[0];

  // What was typed is on the page, not merely in the database.
  assert.ok(body.includes('Registered office: 4 Marylebone Road'));

  // A `name` field is stamped from the SIGNER RECORD, not from the request.
  assert.ok(body.includes('Ada Lovelace'));
  assert.ok(!body.includes('Somebody Else Entirely'), 'the client chose the name printed on the document');

  // A `date` field left empty is filled from the signer's own signing time.
  const signedAt = (h.db.prepare(`SELECT signed_at FROM submitters WHERE id = ?`)
    .get(env.signers[0].id) as { signed_at: string }).signed_at;
  assert.ok(body.includes(signedAt.slice(0, 10)));

  // A `label` carries the sender's default text even though no signer touched
  // it -- finalize maps label values from default_value.
  assert.ok(body.includes('FOR INTERNAL USE ONLY'));

  // Checkboxes draw strokes, not text, so neither box adds a text run; what is
  // pinned instead is the stored values, which is what the ladder branches on.
  const valueOf = (id: string) =>
    (h.db.prepare(`SELECT value FROM submission_fields WHERE id = ?`).get(id) as { value: string }).value;
  assert.equal(valueOf(tickedF.id), 'true');
  assert.equal(valueOf(untickedF.id), 'false');
  assert.ok(!body.some((l) => l === 'true' || l === 'false'), 'a checkbox was stamped as the word rather than a mark');
});

// ── A-604 ───────────────────────────────────────────────────────────────────

test('A-604 · a field lands on the page it was placed on, and one placed past the end is dropped', async () => {
  // finalize() translates the web contract's 0-BASED page to stamping's
  // 1-BASED `PlacedField.page` (durable.ts's own comment). An off-by-one here
  // stamps every signature onto the wrong page of every executed document and
  // no shape assertion in this repository would notice.
  //
  // Mutation: `page: f.page` instead of `f.page + 1`; `page: f.page + 2`; drop
  // stamping.ts's `pageIndex >= pages.length` bounds check.
  const h = newHarness();
  await signIn(h, 'owner@pumasi.ai');
  const pdf = await makePdf(['FIRST PAGE BODY', 'SECOND PAGE BODY', 'THIRD PAGE BODY']);
  const env = seedEnvelope(h, {
    owner: 'owner@pumasi.ai',
    pdf,
    pageCount: 3,
    signers: [{ email: 'ada@example.test', name: 'Ada Lovelace' }],
    fields: [
      { signer: 0, type: 'signature', page: 0 },
      { signer: 0, type: 'text', page: 0, y: 0.3 },
      { signer: 0, type: 'text', page: 1, y: 0.3 },
      { signer: 0, type: 'text', page: 2, y: 0.3 },
      // Placed on a page this document does not have. stamping.ts skips it.
      { signer: 0, type: 'text', page: 40, y: 0.3, required: false },
    ],
  });
  const [sigF, onFirst, onSecond, onThird, offTheEnd] = env.fields;

  const cookie = await signerCookie(h, env.signers[0]);
  const sig = await uploadSignature(h, env.signers[0].id, cookie);
  assert.equal((await complete(h, env.signers[0].id, cookie, {
    [sigF.id]: sig,
    [onFirst.id]: 'MARK-ON-PAGE-ONE',
    [onSecond.id]: 'MARK-ON-PAGE-TWO',
    [onThird.id]: 'MARK-ON-PAGE-THREE',
    [offTheEnd.id]: 'MARK-OFF-THE-END',
  })).status, 200);

  const row = submissionRow(h, env.id);
  const probe = await readPdf(new Uint8Array(row.completed_pdf_blob!));

  // Three original pages plus exactly one certificate.
  assert.equal(probe.pageCount, 4);

  assert.ok(probe.pages[0].includes('FIRST PAGE BODY'));
  assert.ok(probe.pages[0].includes('MARK-ON-PAGE-ONE'));
  assert.ok(!probe.pages[0].includes('MARK-ON-PAGE-TWO'));

  assert.ok(probe.pages[1].includes('SECOND PAGE BODY'));
  assert.ok(probe.pages[1].includes('MARK-ON-PAGE-TWO'));

  assert.ok(probe.pages[2].includes('THIRD PAGE BODY'));
  assert.ok(probe.pages[2].includes('MARK-ON-PAGE-THREE'));

  // The signature went on page one, where it was placed.
  assert.equal(probe.drawsImage[0], true);
  assert.equal(probe.drawsImage[1], false);
  assert.equal(probe.drawsImage[2], false);

  // The out-of-range field was accepted, stored, and silently not stamped
  // anywhere -- including onto the certificate page.
  assert.ok(!probe.all.includes('MARK-OFF-THE-END'));
});

// ── A-605 ───────────────────────────────────────────────────────────────────

test('A-605 · the file the service hands back is the file the certificate attests, to both principals', async () => {
  // The tamper-evidence claim, end to end: `completedHash` in the audit trail
  // must name the bytes a user can actually download, and the original must
  // still be there and still hash to `originalHash`. A finalize that stored one
  // artefact and served another would pass every other case in this file.
  //
  // Mutation: hash before the last save in stamping.ts; have the signed-pdf
  // route fall back to the original blob; overwrite original_pdf_blob in
  // finalize; return the input unstamped (this case reads the certificate's
  // own printed hash off the served bytes, so an artefact with no certificate
  // is red HERE and not only in A-601 -- a spec review objected that the first
  // draft compared audit-row state only and named the certificate anyway).
  const h = newHarness();
  const owner = await signIn(h, 'owner@pumasi.ai');
  const pdf = await makePdf(['DEED OF ASSIGNMENT']);
  const env = seedEnvelope(h, {
    owner: 'owner@pumasi.ai',
    title: 'Deed of Assignment',
    pdf,
    signers: [{ email: 'ada@example.test', name: 'Ada Lovelace' }],
    fields: [{ signer: 0, type: 'signature' }],
  });

  const cookie = await signerCookie(h, env.signers[0]);
  const sig = await uploadSignature(h, env.signers[0].id, cookie);
  assert.equal((await complete(h, env.signers[0].id, cookie, { [env.fields[0].id]: sig })).status, 200);

  const details = completedAudit(h, env.id)!;

  const asOwner = await downloadSigned(h, env.id, owner);
  assert.equal(asOwner.status, 200);
  assert.equal(asOwner.headers.get('content-type'), 'application/pdf');
  assert.equal(asOwner.headers.get('content-disposition'), 'attachment; filename="Deed_of_Assignment.pdf"');
  const ownerBytes = new Uint8Array(await asOwner.arrayBuffer());
  assert.equal(sha256(ownerBytes), details.completedHash);

  // And the certificate INSIDE those bytes prints the original's hash -- the
  // printed claim, read off the artefact a user holds, not the audit row.
  const printed = line(certificateOf(await readPdf(ownerBytes)), 'Original SHA-256:');
  assert.equal(printed, `Original SHA-256: ${env.originalHash}`);

  // The signer gets the same artefact, not a different rendering of it.
  const asSigner = await downloadSigned(h, env.id, cookie);
  assert.equal(asSigner.status, 200);
  const signerBytes = new Uint8Array(await asSigner.arrayBuffer());
  assert.deepEqual(signerBytes, ownerBytes);

  // Whoever holds neither cookie gets 404 rather than the document.
  assert.equal((await h.fetch(`/api/files/signed-pdf/${env.id}`)).status, 404);

  // The original survives finalize untouched and still matches the hash the
  // certificate printed -- so the certificate's claim is checkable afterwards
  // and not only at the moment it was made.
  const preview = await h.fetch(`/api/files/document-preview/${env.id}`, { cookie: owner });
  assert.equal(preview.status, 200);
  assert.equal(preview.headers.get('content-disposition'), 'inline; filename="Deed_of_Assignment.pdf"');
  const original = new Uint8Array(await preview.arrayBuffer());
  assert.equal(sha256(original), env.originalHash);
  assert.equal(sha256(original), details.originalHash);
  assert.equal(`Original SHA-256: ${sha256(original)}`, printed);
});

// ── A-606 ───────────────────────────────────────────────────────────────────

test('A-606 · with R2 bound the executed PDF goes to the bucket and not into the row', async () => {
  // The first assertion in this repository to execute `service/src/storage/r2.ts`
  // (BACKLOG.md item 2 residual B measured this by import: the module was
  // imported by no test at all). The bucket is an in-memory stand-in; the
  // WRAPPER is real, and so is finalize's choice of where to put the bytes.
  //
  // Mutation: make storePdf return null; drop the `completedKey ? null : bytes`
  // ternary so both columns are written; change the key prefix.
  const bucket = fakeBucket();
  const h = newHarness({ DOCUMENTS: bucket as unknown as any });
  const owner = await signIn(h, 'owner@pumasi.ai');
  const pdf = await makePdf(['LEASE AGREEMENT']);
  const env = seedEnvelope(h, {
    owner: 'owner@pumasi.ai',
    pdf,
    key: 'originals/seeded.pdf',
    bucket,
    signers: [{ email: 'ada@example.test', name: 'Ada Lovelace' }],
    fields: [{ signer: 0, type: 'signature' }],
  });

  const cookie = await signerCookie(h, env.signers[0]);
  const sig = await uploadSignature(h, env.signers[0].id, cookie);
  assert.equal((await complete(h, env.signers[0].id, cookie, { [env.fields[0].id]: sig })).status, 200);

  const row = submissionRow(h, env.id);
  assert.equal(row.status, 'completed');
  assert.equal(row.completed_pdf_key, `completed/${env.id}.pdf`);
  assert.equal(row.completed_pdf_blob, null, 'the executed PDF was written to the row as well as to R2');

  // It really crossed the wrapper: the original was READ from the bucket and
  // the executed document was PUT back into it, with a content type.
  assert.ok(bucket.calls.some((c) => c.op === 'get' && c.key === 'originals/seeded.pdf'));
  assert.ok(bucket.calls.some((c) => c.op === 'put' && c.key === `completed/${env.id}.pdf`));
  const held = bucket.objects.get(`completed/${env.id}.pdf`)!;
  assert.ok(held, 'the bucket does not hold the key the row points at');
  assert.equal(held.contentType, 'application/pdf');

  // And what comes back down the route is those bytes, and they are what the
  // certificate attests.
  const details = completedAudit(h, env.id)!;
  assert.equal(sha256(held.data), details.completedHash);
  const served = new Uint8Array(await (await downloadSigned(h, env.id, owner)).arrayBuffer());
  assert.equal(sha256(served), details.completedHash);

  // The artefact is a real stamped document, not an empty object with the
  // right key.
  const probe = await readPdf(served);
  assert.equal(probe.pageCount, 2);
  assert.ok(probe.pages[0].includes('LEASE AGREEMENT'));
  assert.equal(line(certificateOf(probe), 'Original SHA-256:'), `Original SHA-256: ${env.originalHash}`);
});

// ── A-607 ───────────────────────────────────────────────────────────────────

test('A-607 · initials use their field-specific mark, including for an initials-only signer', async () => {
  // WHAT THIS CASE ASSERTS IS NOT ENDORSED. It records two behaviours a reader
  // would reasonably assume away, so that a packet which changes them knows it
  // changed them. Red here means someone took the strand, not that the worker
  // broke. spec/0010 §S3; the idiom is spec/0005 A-409's and spec/0009 A-502's.
  //
  //  (i) `embeddedSignatures` is keyed by SIGNER, not by field, so a signer who
  //      drew a signature has that same full image stamped into their INITIALS
  //      box too.
  //  (ii) durable.ts captures `signature_blob` only from a field of type
  //      `signature`. A signer whose only box is an `initials` box therefore has
  //      no image at finalize time even though they uploaded one and referenced
  //      it -- and stamping falls back to `signer.name`, printing the full
  //      typed name where initials were asked for.
  //
  // Mutation: key embeddedSignatures by field; capture signature_blob from
  // `initials` fields too; change the fallback from `signer?.name` to
  // `field.value`.
  const h = newHarness();
  await signIn(h, 'owner@pumasi.ai');
  const pdf = await makePdf(['PAGE FOR INITIALS', 'PAGE FOR NOBODY']);
  const env = seedEnvelope(h, {
    owner: 'owner@pumasi.ai',
    pdf,
    pageCount: 2,
    signers: [
      { email: 'ada@example.test', name: 'Ada Lovelace', order: 1 },
      { email: 'jonathan@example.test', name: 'Jonathan Reginald Whitmore', order: 2 },
    ],
    fields: [
      // Ada: a signature box AND an initials box.
      { signer: 0, type: 'signature', page: 0, y: 0.2 },
      { signer: 0, type: 'initials', page: 0, y: 0.35, w: 0.08, h: 0.04 },
      // Jonathan: an initials box and nothing else.
      { signer: 1, type: 'initials', page: 0, y: 0.5, w: 0.08, h: 0.04 },
    ],
  });
  const [adaSig, adaInitials, jonInitials] = env.fields;

  const ada = await signerCookie(h, env.signers[0]);
  const adaImage = await uploadSignature(h, env.signers[0].id, ada);
  assert.equal((await complete(h, env.signers[0].id, ada, {
    [adaSig.id]: adaImage,
    [adaInitials.id]: adaImage,
  })).status, 200);

  const jon = await signerCookie(h, env.signers[1]);
  // Jonathan draws too. The image is uploaded and referenced by his field.
  const jonImage = await uploadSignature(h, env.signers[1].id, jon);
  assert.equal((await complete(h, env.signers[1].id, jon, { [jonInitials.id]: jonImage })).status, 200);

  const blobOf = (id: string) =>
    (h.db.prepare(`SELECT signature_blob FROM submitters WHERE id = ?`).get(id) as { signature_blob: unknown }).signature_blob;

  // An initials-only signer retains their selected mark for certificate fallback.
  assert.ok(blobOf(env.signers[0].id), 'the signature field did not capture the drawn image');
  assert.ok(blobOf(env.signers[1].id), 'an initials-only signer lost their drawn mark');

  const row = submissionRow(h, env.id);
  const probe = await readPdf(new Uint8Array(row.completed_pdf_blob!));
  const body = probe.pages[0];

  // (i) Ada's initials box drew an image. Her name is not typed on the page.
  assert.equal(probe.drawsImage[0], true);
  assert.ok(!body.includes('Ada Lovelace'), 'RECORDED: an image-backed initials box typed the name instead');

  // Jonathan's initials field is an image, not his full typed name.
  assert.ok(!body.includes('Jonathan Reginald Whitmore'), 'initials field printed the signer full name');

  // Both are certified as signers regardless -- the certificate does not
  // distinguish a drawn mark from a typed one.
  const cert = certificateOf(probe);
  assert.ok(cert.includes('Ada Lovelace (Signer)'));
  assert.ok(cert.includes('Jonathan Reginald Whitmore (Signer)'));
});

// ── A-608 ───────────────────────────────────────────────────────────────────

test('A-608 · a document that cannot be loaded leaves the envelope pending and reports completion failure', async () => {
  // Amended by spec/0011. Before this repair the same position returned 200,
  // marked the envelope completed, wrote a hash-less completed event, and sent
  // completion mail despite having no executed document.
  const bucket = fakeBucket();
  const h = newHarness({ DOCUMENTS: bucket as unknown as any });
  const owner = await signIn(h, 'owner@pumasi.ai');
  const env = seedEnvelope(h, {
    owner: 'owner@pumasi.ai',
    // The row points at a key. The bucket does not hold it, and no `bucket`
    // is passed to the seeder, so nothing was ever put there.
    pdf: null,
    key: 'originals/vanished.pdf',
    signers: [{ email: 'ada@example.test', name: 'Ada Lovelace' }],
    fields: [{ signer: 0, type: 'signature' }],
  });

  const cookie = await signerCookie(h, env.signers[0]);
  const sig = await uploadSignature(h, env.signers[0].id, cookie);
  const res = await complete(h, env.signers[0].id, cookie, { [env.fields[0].id]: sig });

  assert.equal(res.status, 503);
  assert.deepEqual(await res.json(), {
    error: 'Your signature was saved, but the final document could not be produced. Please try again shortly.',
  });

  const row = submissionRow(h, env.id);
  assert.equal(row.status, 'pending');
  assert.equal(row.completed_at, null);

  // There is no executed document, by either route it could have taken.
  assert.equal(row.completed_pdf_key, null);
  assert.equal(row.completed_pdf_blob, null);
  assert.ok(!bucket.objects.has(`completed/${env.id}.pdf`));
  // The read was attempted and came back empty -- so this is the missing-object
  // path and not a case where R2 was never consulted.
  assert.ok(bucket.calls.some((c) => c.op === 'get' && c.key === 'originals/vanished.pdf'));
  assert.ok(!bucket.calls.some((c) => c.op === 'put'));

  assert.equal(auditCount(h, env.id, 'completed'), 0);
  assert.equal(auditCount(h, env.id, 'completion_failed'), 1);

  // And the owner, told the envelope is complete, cannot download it.
  const download = await downloadSigned(h, env.id, owner);
  assert.equal(download.status, 404);
  assert.deepEqual(await download.json(), { error: 'Not available' });
});

// ── A-610 ───────────────────────────────────────────────────────────────────

test('A-610 · the sender can retry completion once the original is available, and repeated retry is idempotent', async () => {
  const bucket = fakeBucket();
  const h = newHarness({ DOCUMENTS: bucket as unknown as any });
  const owner = await signIn(h, 'owner@pumasi.ai');
  const original = await makePdf(['RECOVERABLE AGREEMENT']);
  const key = 'originals/recoverable.pdf';
  const env = seedEnvelope(h, {
    owner: 'owner@pumasi.ai', pdf: null, key,
    signers: [{ email: 'ada@example.test', name: 'Ada Lovelace' }],
    fields: [{ signer: 0, type: 'signature' }],
  });

  const signer = await signerCookie(h, env.signers[0]);
  const sig = await uploadSignature(h, env.signers[0].id, signer);
  const failed = await complete(h, env.signers[0].id, signer, { [env.fields[0].id]: sig });
  assert.equal(failed.status, 503);

  bucket.objects.set(key, { data: original, contentType: 'application/pdf' });
  const retried = await h.fetch(`/api/submissions/${env.id}/retry-completion`, { method: 'POST', cookie: owner });
  assert.equal(retried.status, 200);
  assert.equal((await retried.json() as { status: string }).status, 'completed');
  assert.equal(auditCount(h, env.id, 'completed'), 1);
  assert.ok(bucket.objects.has(`completed/${env.id}.pdf`));

  const completedWrites = bucket.calls.filter((c) => c.op === 'put' && c.key === `completed/${env.id}.pdf`).length;
  const again = await h.fetch(`/api/submissions/${env.id}/retry-completion`, { method: 'POST', cookie: owner });
  assert.equal(again.status, 200);
  assert.equal((await again.json() as { status: string }).status, 'completed');
  assert.equal(auditCount(h, env.id, 'completed'), 1);
  assert.equal(
    bucket.calls.filter((c) => c.op === 'put' && c.key === `completed/${env.id}.pdf`).length,
    completedWrites,
  );
});

// ── A-609 ───────────────────────────────────────────────────────────────────

test('A-609 · stamping adds; it does not replace, reorder, or drop the sender\'s document', async () => {
  // A preservation invariant, the analogue of spec/0002 A-109 and spec/0001
  // A-005. CORRECTLY GREEN before and after: nothing in this packet changes
  // stamping. Its value is that it fails the change that "simplifies" stamping
  // into rendering a fresh document from field values -- which would satisfy
  // every certificate assertion above while losing the contract the parties
  // actually signed.
  //
  // Mutation: build the output from PDFDocument.create() instead of load();
  // insert the certificate at index 0; drop the original pages.
  const h = newHarness();
  await signIn(h, 'owner@pumasi.ai');
  const bodies = ['ARTICLE I - DEFINITIONS', 'ARTICLE II - TERM', 'ARTICLE III - GOVERNING LAW'];
  const pdf = await makePdf(bodies);
  const env = seedEnvelope(h, {
    owner: 'owner@pumasi.ai',
    pdf,
    pageCount: 3,
    signers: [{ email: 'ada@example.test', name: 'Ada Lovelace' }],
    fields: [{ signer: 0, type: 'signature', page: 2 }],
  });

  const before = await readPdf(env.originalPdf!);
  assert.equal(before.pageCount, 3);

  const cookie = await signerCookie(h, env.signers[0]);
  const sig = await uploadSignature(h, env.signers[0].id, cookie);
  assert.equal((await complete(h, env.signers[0].id, cookie, { [env.fields[0].id]: sig })).status, 200);

  const row = submissionRow(h, env.id);
  const after = await readPdf(new Uint8Array(row.completed_pdf_blob!));

  // Exactly one page was added, and it is the certificate, and it is last.
  assert.equal(after.pageCount, before.pageCount + 1);
  assert.ok(certificateOf(after).some((l) => l.includes('Signature Certificate and Audit Trail')));

  // Every original page is still there, still in order, still carrying its own
  // text -- and no original page became the certificate.
  bodies.forEach((text, i) => {
    assert.ok(after.pages[i].includes(text), `page ${i + 1} lost its own text`);
    assert.ok(!after.pages[i].some((l) => l.includes('Signature Certificate')));
  });

  // The stored original is byte-identical to what the sender uploaded.
  const stored = (h.db.prepare(`SELECT original_pdf_blob AS b FROM submissions WHERE id = ?`)
    .get(env.id) as { b: Uint8Array }).b;
  assert.deepEqual(new Uint8Array(stored), env.originalPdf);
  assert.equal(sha256(new Uint8Array(stored)), env.originalHash);
});
