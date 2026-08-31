# SPEC · 0005 — what an envelope may become, recorded

**Item:** `roadmap/BACKLOG.md` **1**, sub-item **3** — envelope state
transitions. The first two sub-items are `spec/0004`; that spec's §S5 names
this one as not taken, and this is it.
**Intent:** [`INTENT.md`](INTENT.md), same directory.
**Repository:** `pumasi-sign` @ `eb1ec3c`.
**Adds:** `service/src/test/envelope-lifecycle.test.ts` — ten frozen cases,
**A-400 – A-409**.
**Modifies:** nothing. `git diff service/src/durable.ts` and
`git diff service/src/test/support/durable-harness.ts` are both empty in the
commit that carries this spec.

**Measured by this packet, at `eb1ec3c`, before the change:**

```
Test Files  6 passed (6) · Tests  85 passed (85)
# pass 11 · # fail 0
assert-service-suite-ran: 11 passing, 0 failing, from 3 compiled
```

**and after:**

```
assert-service-suite-ran: 21 passing, 0 failing, from 4 compiled
```

---

## S1 · The harness, reused rather than rebuilt

**S1a.** These cases use `service/src/test/support/durable-harness.ts` exactly
as `spec/0004` wrote it. It is **not modified**: a change there would put nine
frozen cases at risk to save this packet a helper, and it is not needed.

**S1b.** Every limit `spec/0004` §S1 states carries over verbatim and is not
restated here (`lessons/L-007`). The one that matters most to a reader of a
green count: **this is `node:sqlite`, not workerd's SQLite**, so a case here is
evidence about `durable.ts`'s own logic, not about Cloudflare's storage engine.

**S1c.** **Mail is deliberately unconfigured.** `sendMail` throws without
`GMAIL_SA_KEY`/`MAIL_IMPERSONATE` and `mailOrLog` (`durable.ts:378`) catches
it, so every notifying path — `inviteCurrentTurn`, the decline notice,
`finalize`'s two mailings — runs to completion offline. Nothing in this suite
reaches the network. The `[mail] send to … failed` lines in the runner's
diagnostics are that, and the file says so at the top.

**S1d.** **No envelope in this suite carries a PDF.** That is deliberate and
it is what makes the completion path affordable: `finalize` (`durable.ts:1537`)
branches at `:1586` into a no-stamping completion when there are no original
bytes, so A-406 and A-409 drive the real transition without pulling `pdf-lib`
or R2 into a case about a status word.

**S1e.** Only the **starting position** is seeded (a row written straight to
the store by `seedEnvelope`). **Every transition is driven through `fetch()`.**
A case that wrote a status and then read it back would be testing the harness.

## S2 · What is characterized

Ten cases against `durable.ts`'s lifecycle, by line:

| | Where | What is recorded |
| :-- | :--- | :--- |
| **a** | `:190`, `:207` | the two schema defaults — a submission begins `draft`, a submitter `pending` — read from the schema the worker wrote, not from the test |
| **b** | `:1210` | `DELETE` is draft-only; deleting a draft also takes its submitters, fields and audit trail; every other status is refused 409 and survives |
| **c** | `:1227`–`:1233` | `send` moves `draft` → `pending` and audits `sent`; on a `pending` envelope the same route is a **reminder** and audits `reminded`; the branch keys on the envelope's status, never on the word in the URL, so `/remind` on a draft **sends** it |
| **d** | `:1230`–`:1231` | `send` and `remind` are both refused 409 on `completed`, `cancelled` and `declined`, and the refusal writes no audit event |
| **e** | `:1239`–`:1243` | `cancel` — the ordinary `pending` → `cancelled`, its `reason` in `details_json`, **and that it guards on nothing** (§S6.1) |
| **f** | `:1295` | `resend` is scoped to its own envelope (a real signer of another envelope is a 404, not a 200) and is refused 409 for a signer who is `signed` **or** `declined` |
| **g** | `:1434`–`:1438`, `:1479`–`:1489` | signing is in order, is once, refuses a dead envelope; the last outstanding **non-CC** signer moves the submission to `completed`, stamps `completed_at`, and the completion is audited to `system@pumasi.ai`, not to the signer |
| **h** | `:1490`–`:1495` | one decline ends the envelope for everyone and leaves the other signers as they were — **and that decline carries none of `complete`'s guards** (§S6.2) |
| **i** | `:101`, `:590`, `:1320`–`:1325`, `:1411` | the wire word and the column word differ: `outSubmitterStatus` rewrites a submitter's `signed` to `completed` on the way out, so one payload says `completed` for a submitter whose column says `signed` beside a submission that is still `pending`; and the public token view has a fifth vocabulary — `cancelled`, `declined`, `completed`, `already_signed`, `open` — tested in that fixed precedence |
| **j** | `:803`, `:1359`, and an absence | **`expired` is a status the product claims and the worker never writes** (§S6.3) |

## S3 · What the cases must not do

**S3a.** No case may assert that a transition is the *correct* one. Where a
case sits on a decision, it says so at the assertion (§S4).

**S3b.** No case may edit, import from, or otherwise depend on `spec/0004`'s
frozen file. The two small helpers they share (`seedCode`, a sign-in) are
duplicated locally, at a cost of about ten lines, so that A-300 – A-308 cannot
be broken from here.

**S3c.** No assertion may be conditional on an outcome the test does not
control (`lessons/L-006`). One place this bites: `audit_events.created_at` is a
millisecond ISO string and two events written inside one request can tie, so
the helper that reads the audit trail **sorts** and every assertion about it is
about a multiset, never an order.

**S3d.** No network, no filesystem outside the process, no new dependency.

## S4 · The characterize / adjudicate boundary, in the cases themselves

**S4a.** Four assertions record behaviour that a reasonable person may want
changed. Each carries, at the assertion, a comment that (i) reads
`RECORDED, NOT ENDORSED`, (ii) names its §S6 entry, and (iii) states that **red
there means someone took the backlog entry — a decision — and not that the
worker regressed.** They are in A-404, A-406, A-407 and A-409.

**S4b.** No case name uses a word of approval or disapproval, and no case
asserts that a guard *should* exist. `cancel` having no guard is written the
way it is true: `assert.equal(again.status, 200, 'cancel on … is accepted
today')`.

**S4c.** This is `spec/0004` §S4's idiom, applied to a different kind of line.
There, red would mean a steward answered **Q-018**. Here, red means the product
manager scheduled a repair. Both are decisions; neither is a regression; and a
characterization case is only safe if it says which.

**S4d.** Nothing in this change deletes a tree, re-points a domain, moves data,
edits `CLAUDE.md`, or proposes an answer to any open `DECISIONS.md` entry.

## S5 · Where the slice stops, and the coverage it does not claim

**Taken:** sub-item 3, envelope state transitions, in full — every status the
worker writes, and the one it does not.

**Not taken, and stated rather than left to be discovered:**

- **The OAuth branch of `establishSession`** (`durable.ts:766`–`:770`) remains
  uncharacterized. It was offered to this packet *"if the slice still has
  room"*, and the slice does not: the new test file is 30 632 bytes on its own,
  and `reviews/20260831-160531-code-qwen.md` and
  `reviews/20260831-161553-code-glm.md` — both in this repository, both from
  one job ago — record two families going mute on a 55 6xx-byte bundle of the
  previous slice. Spending the cross-family review to buy one more case is a
  bad trade, and it is `spec/0004` §S5's stated limit either way.
- **`worker.ts`, `storage/r2.ts`, `mail.ts`, `feedback.ts`,
  `convert/graph.ts`** are still covered by nothing. So are envelope
  **creation** (`POST /api/submissions`, `/adhoc`), **correction** (`PATCH`),
  `copy`, `archive`, templates, branding, admin, and every file route.
- **`finalize`'s stamping branch** (`durable.ts:1569`) is not reached by these
  cases; only its no-PDF branch is. `stamping.test.ts` and `e2e-workflow.test.ts`
  cover the stamper as a pure function, and nothing covers the two joined.

**This change moves the number the gate prints from 11 to 21. It does not make
`service/` well covered, and no release note or stage claim may read it as
doing so.**

## S6 · Found while characterizing — proposed, not taken

Four. **None is patched in this commit.** Each is offered to the product
manager as a `roadmap/BACKLOG.md` entry, with the line it was verified at.

1. **`cancel` has no status guard** — `durable.ts:1239`–`:1243`. Every other
   transition checks the current status first. `cancel` does not, so a
   `completed`, `declined` or already-`cancelled` envelope is silently
   overwritten and a second `cancelled` audit event is written over the first.
   A completed, signed agreement can be voided after the fact by its sender,
   and the audit trail records the void without recording that anything was
   destroyed. **Recorded by A-404.**
2. **`decline` has no guard where `complete` has three** — `:1490`, against
   `:1434`–`:1438`. `complete` refuses a `cancelled`/`declined` envelope (410),
   a repeat signature (409) and an out-of-turn one (409). `decline`, five lines
   later, checks none of them: it flips a `completed` envelope to `declined`,
   and flips a signer who has already **signed** to `declined`. A-407 puts the
   asymmetry in one case: the same envelope, in the same breath, refuses a
   signature and accepts a decline. **Recorded by A-407.**
3. **`expired` is a status the product documents and the worker cannot
   reach** — `CLAUDE.md`:108–109 against `durable.ts`. The string `expired`
   occurs twice in `durable.ts`, both inside *"Invalid or expired verification
   code"* (`:803`, `:1359`). `submissions.expires_at` (`:194`) is written by
   the create routes (`:1023`, `:1096`) and read only to be echoed back
   (`:572`). This is **not** a sweep that fails to run: the worker exposes no
   jobs route, `worker.ts` exports no `scheduled` handler, and
   `service/wrangler.jsonc` declares no cron trigger — all three verified by
   grep at `eb1ec3c`. `backend/` flips this status from `POST /api/jobs/daily`;
   the deployed tree has no equivalent, so an envelope with a deadline in the
   past is signable indefinitely. **Recorded by A-409.**
4. **A completed envelope still accepts a signature** — `:1434`. `complete`'s
   dead-envelope guard tests `cancelled` and `declined` and **not**
   `completed`, so any recipient who has not yet signed — a CC recipient, or a
   signer added out of band — can sign afterwards. That runs `finalize` a
   second time on an already-completed envelope and writes a **second**
   `completed` audit event; with a PDF present it would re-stamp and overwrite
   the executed document. **Recorded by A-406**, which asserts the two
   completion events.

**A fifth, outside this slice and named because the packet asked for it, not
because a case here covers it:** `durable.ts:766` reads
`claims.email_verified === false`, so an `id_token` whose claim set **omits**
`email_verified` is accepted and only an explicit `false` is refused. Verified
by reading the line at `eb1ec3c`. It is on the OAuth branch, which §S5 records
as uncharacterized, so **no case in this file asserts it** — it is proposed on
the strength of the source, and the entry that takes it should bring the case.

## S7 · Out of scope, stated so a reviewer can hold it

Every `service/src` file that ships to the worker · `service/src/test/support/`
and `spec/0004`'s A-300 – A-308 · `backend/**` · `frontend/**` · `.github/**`
and the root `package.json` (and so **A-208**, untouched — `BACKLOG.md` item 4
is not taken in passing) · `roadmap/**`, the product manager's, **including
retiring item 1** · **deploying (Q-012, Q-018)** · `LICENSE` and
`LandingView.vue` (Q-021, Q-028) · `pumasi/catalog.json` (Q-019) ·
`pumasi/HUMAN.md` · `pumasi/tools/`, which a parallel commons job is holding ·
`web/` and `pumasi-web` · `reviews/20260831-143359-code-qwen.md`, which this
packet may not commit, edit or delete, and has not.

---

## Frozen acceptance cases

Ten cases, in `service/src/test/envelope-lifecycle.test.ts`. They are **new
coverage of unchanged code**, so "red against the change-absent tree" is not a
meaningful column — at `eb1ec3c` the file does not exist. The column that
carries the weight is the last one: **the single mutation that turns the case
red**, applied to the tree under test and then reverted.

**Every mutation below was run.** Each was applied to `service/src/durable.ts`,
`npm run build` re-run, `npm test` re-run, the `not ok` line and the
`# pass`/`# fail` summary read from the runner's own output, and the file
restored from a copy taken before the edit. **Every one of the eleven isolates
exactly one case: `pass=20 fail=1`.**

| # | Case | Clause | Single mutation that turns it red | Measured |
| :-- | :--- | :--- | :--- | :--- |
| **A-400** | the schema the worker declares: a submission defaults to `draft`, a submitter to `pending`, the envelope surface routes, and the owner scope is real | S2a | **two, both run.** *M-400*: drop `DEFAULT 'draft'` from `submissions.status` (`:190`). *M-400b*: drop `DEFAULT 'pending'` from `submitters.status` (`:207`) | M-400 → `pass=20 fail=1`, A-400 alone. M-400b → `pass=20 fail=1`, A-400 alone |
| **A-401** | only a draft can be deleted, and deleting one takes its signers, fields and audit trail with it | S2b | replace `if (sub.status !== 'draft')` with `if (false)` (`:1210`) | `pass=20 fail=1` — A-401 alone |
| **A-402** | `send` moves a draft to `pending` exactly once; on a pending envelope the same route is a reminder; `/remind` on a draft still **sends** | S2c | make `send`'s draft branch key on `'pending'` instead (`:1227`) | `pass=20 fail=1` — A-402 alone |
| **A-403** | a `completed`, `cancelled` or `declined` envelope can be neither sent nor reminded, and the refusal writes nothing | S2d | replace `} else if (sub.status !== 'pending') {` with `} else if (false) {` (`:1230`) | `pass=20 fail=1` — A-403 alone |
| **A-404** | **recorded, not endorsed:** `cancel` has no status guard — it overwrites a `completed`, `declined` or already-`cancelled` envelope and audits again | S2e, S4a, S6.1 | **give `cancel` the guard §S6.1 proposes** — refuse anything but `draft`/`pending` (`:1239`) | `pass=20 fail=1` — A-404 alone. This is the mutation that *is* the repair, which is what makes red here mean "someone decided" |
| **A-405** | resending is scoped to its own envelope and refused for a signer who is `signed` or `declined` | S2f | replace `if (target.status !== 'pending')` with `if (false)` (`:1295`) | `pass=20 fail=1` — A-405 alone |
| **A-406** | signing is in order and once; the last outstanding **non-CC** signer completes the envelope, `completed_at` is stamped, and the completion is audited to the engine — **and, recorded not endorsed, a completed envelope still accepts a signature and completes twice** | S2g, S4a, S6.4 | drop `AND is_cc = 0` from the outstanding-signer count (`:1479`), so a CC recipient holds the envelope open | `pass=20 fail=1` — A-406 alone |
| **A-407** | one decline ends the envelope for everyone and leaves the other signers as they were — **and, recorded not endorsed, `decline` carries none of `complete`'s guards** | S2h, S4a, S6.2 | **give `decline` the guards `complete` has** (`:1490`), which is §S6.2's repair | `pass=20 fail=1` — A-407 alone |
| **A-408** | a submitter reports `completed` while its column reads `signed`, beside a submission that is still `pending`; and the token view's five words, in their fixed precedence | S2i | make `outSubmitterStatus` the identity function (`:101`) | `pass=20 fail=1` — A-408 alone |
| **A-409** | **recorded, not endorsed:** the worker never writes `expired` — a day-old deadline transitions nothing, the envelope signs and completes normally, and `POST /api/jobs/daily` is a 404 | S2j, S4a, S6.3 | **give the worker an expiry sweep** — one statement on the envelope route (`:1139`) flipping a past-deadline `pending` to `expired` | `pass=20 fail=1` — A-409 alone |

**Determinism, re-measured for the suite as it exists after this change**
(`pumasi/DECISIONS.md` Q-025 rider (b)): **30 consecutive `npm test` runs, 30
pass, 0 fail, identical counts on every run** — `# pass 21 # fail 0` thirty
times over.

### Why A-400 is not decorative

It is this file's reader guard, the analogue of `spec/0002`'s A-100,
`spec/0003`'s A-200 and `spec/0004`'s A-300. **Every other case here seeds
`status` explicitly** — `seedEnvelope` writes the word it was asked for — so a
schema that carried no `DEFAULT` on either status column, or a harness that
stored the word and handed back something else, would leave all nine of them
green while the two columns this entire file is about were never the worker's.
A-400 is the one case that reads both defaults from the schema `initSchema`
wrote, and then reads the same two words back out through `fetch()`. Its two
mutations are the proof: dropping either `DEFAULT` reddens A-400 and **nothing
else**.

### What these cases do **not** claim

They do not claim `service/` is covered. They cover the transitions of one
resource, through a SQLite shim rather than `workerd` (§S1b), on envelopes that
carry no document (§S1d), with creation, correction, copy, templates, files and
the whole of `worker.ts` still covered by nothing (§S5). They move the number
`.github/scripts/assert-service-suite-ran.sh` prints from **11** to **21**, and
the number is still small.

**They also do not claim the worker is correct.** Four of the ten record
something a reasonable person would call a defect, and §S6 is where those go.
A green run of this file means the deployed tree does today what this file
says it does — no more than that, and that is the whole point of a
characterization suite.
