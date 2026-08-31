# INTENT · 0004 — the deployed tree's front door, recorded

**Date:** 2026-08-31
**Source:** `roadmap/BACKLOG.md` item **1** — *"Test the deployed tree beyond
its PDF stamper"* — whose own text names the first slice: *"`establishSession`'s
account-creation rule (`service/src/durable.ts:655` …), then session
validation, then envelope state transitions."* Behind it:
`pumasi/DECISIONS.md` **Q-018** and **Q-025**, `roadmap/STAGE.md` §2.1, and
`CLAUDE.md`'s own sentence that coverage in `service/` *"is thin and you should
know it before you trust it"*.
**Repository:** `pumasi-sign`. Touches `service/src/test/` and `spec/` only.
**Not touched:** any `service/src` file that ships to the worker, `frontend/**`,
`backend/**`, `.github/**`, the root `package.json`, `roadmap/**`.

## What is wrong

**The tree that answers `sign.pumasi.ai` has two tests and they are the same
test.** Re-measured at `38ba661`, by reading both files rather than counting
them:

- `service/src/test/stamping.test.ts` and `service/src/test/e2e-workflow.test.ts`
  have **identical import lists** — `node:test`, `node:assert/strict`,
  `pdf-lib`, and `stampAndCertifyPdf` from `../core/stamping.js`. Nothing else.
- **`e2e-workflow.test.ts` is not an end-to-end test of anything.** It calls no
  route, constructs no Durable Object, touches no store. A reader of the file
  *name* over-reads it, and so does a reader of a `# pass 2` in a release note.
- Covered by nothing: `durable.ts` — sessions, envelopes, signing, the entire
  API surface — plus `worker.ts`, `storage/r2.ts`, `mail.ts`, `feedback.ts`,
  `convert/graph.ts`.

Run by this packet at `38ba661`, not inherited:

```
Test Files  6 passed (6) · Tests  85 passed (85)
# pass 2 · # fail 0
assert-service-suite-ran: 2 passing, 0 failing, from 2 compiled
```

`GATE: PASS` on this repository now carries a number about production —
`spec/0003` bought that — and the number is **2**, both assertions against one
pure function.

### The proof that this is the highest build entry, re-checked here

CI run
[33430138500](https://github.com/pumasi-ai/pumasi-sign/actions/runs/33430138500)
is `backend` ✓ `frontend` ✓ `service` ✓ `e2e` ✓ at `d18d534` **while issue #7
was live in production**. Nothing in the estate could have gone red on it: the
two `service` tests do not reach routing, and the six Playwright specs drive
`backend/`. A green estate over a live defect is this item's whole case, and it
is why a test that *can* fail on the served tree is worth more here than
another one that cannot.

## What this change does

**It gives the served tree its first test that constructs the Durable Object
and drives it through `fetch()`** — the same entrypoint `worker.ts` uses — and
it spends that first test on the one function `BACKLOG.md` item 1 named:
`establishSession` (`service/src/durable.ts:655`), reached from both sign-in
paths, and the session cookie it mints.

Two files:

- `service/src/test/support/durable-harness.ts` — a `SqlStorage`-shaped shim
  over `node:sqlite`'s in-memory `DatabaseSync`, and a fake
  `DurableObjectState` carrying it, so `PumasiSignService` can be constructed
  under `node --test`. No new npm dependency; nothing leaves the process.
- `service/src/test/auth-session.test.ts` — nine frozen cases, **A-300 – A-308**.

## The boundary this packet is under, and how the cases respect it

`roadmap/BACKLOG.md` item 1 and the packet that carries it both say it in the
same words: **a test that *records* what the worker does today is ordinary
work; a test written to assert that the worker's account rule is the *correct*
one would be answering Q-018, which is the steward's. Characterize, do not
adjudicate.**

So **A-302** records that `establishSession` creates an account for a verified
email at **any** domain, with no gate — and records, in the case file itself,
that this is the divergence Q-018 names, that `backend/` gates on
`ALLOWED_EMAIL_DOMAINS`, and that **the day a steward answers Q-018 in
`backend/`'s favour, A-302 going red is the correct outcome and not a
regression.** A characterization case whose red means *"someone decided"*
rather than *"someone broke it"* is only safe if it says so, and it does — in
the spec, in the case name, and in a comment at the assertion.

Nothing here proposes an answer, weighs the two trees, deletes anything,
re-points a domain or moves data.

## What this change deliberately does not do

- **It does not change one byte of shipped worker code.** `durable.ts` is read,
  not edited. If characterizing turned up a defect it is proposed as a
  `roadmap/BACKLOG.md` entry in the return, not patched here. Two were found
  and are proposed; see `SPEC.md` §S6.
- **It does not deploy.** **Q-012** is open and explicitly outside CHARTER
  Part 0's proceed-on-default rule; **Q-018** adds that shipping this product
  means `wrangler deploy` from `service/`. A test-only change ships nothing to
  a user either way.
- **It does not take the third sub-item** — envelope state transitions. The
  slice is coherent at *sign in, and what the cookie admits*; §S5 says where it
  stops and what the next slice is.
- **It does not characterize the OAuth branch of `establishSession`**
  (`durable.ts:770`), which needs the provider token endpoint stubbed. That is
  a **stated** coverage limit, in §S5, not a hidden one.
- **It does not add a `version` field to the root `package.json`**
  (`BACKLOG.md` item 4). Frozen case **A-208** asserts its absence precisely so
  that a later packet cannot take it in passing, and this packet does not open
  that file at all.
- **It does not touch `roadmap/**`.** Retiring or re-ranking item 1 is the
  product manager's; this packet proposes and does not edit.
- **It does not switch the runner to `@cloudflare/vitest-pool-workers`.**
  Running the suite on real `workerd` is the stronger shape and it is not
  taken: it would replace `node --test`, whose TAP `# pass`/`# fail` lines are
  what `.github/scripts/assert-service-suite-ran.sh` reads, and that guard and
  its frozen cases **A-103**, **A-104**, **A-207** are `spec/0002`'s and
  `spec/0003`'s. It is proposed in §S6 as its own packet.
