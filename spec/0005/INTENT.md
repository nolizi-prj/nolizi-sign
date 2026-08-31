# INTENT · 0005 — what an envelope may become, recorded

**Date:** 2026-08-31
**Source:** `roadmap/BACKLOG.md` item **1** — *"Test the deployed tree beyond
its PDF stamper"* — and specifically its **third and last sub-item**. That
entry names three in order: `establishSession`, then session validation, then
**envelope state transitions**. `spec/0004` took the first two and said so in
the open: its §S5 reads *"Not taken: sub-item 3, envelope state transitions."*
**This packet takes that remaining sub-item. Item 1 was never retired and this
does not retire it** — that is the product manager's act, proposed in the
return block and not performed here.
**Repository:** `pumasi-sign`. Touches `service/src/test/` and `spec/` only.
**Not touched:** any `service/src` file that ships to the worker, `frontend/**`,
`backend/**`, `.github/**`, the root `package.json`, `roadmap/**`.

## What is wrong

**The tree that answers `sign.pumasi.ai` now has a tested front door and an
untested interior.** Measured at `eb1ec3c` by running it, not inherited:

```
Test Files  6 passed (6) · Tests  85 passed (85)
# pass 11 · # fail 0
assert-service-suite-ran: 11 passing, 0 failing, from 3 compiled
```

Of those eleven, nine are `spec/0004`'s cases on `establishSession` and the
session cookie, and two are the PDF stamper. **Nothing whatever covers what
happens to a document after it exists.** `durable.ts` decides, today and in
production, whether an envelope may be deleted, sent, reminded, cancelled,
signed, declined or completed — and every one of those decisions is
uncharacterized.

The specific shape of the gap matters, because it is not uniform:

- **Four of those transitions are guarded and four guards were never
  exercised.** `DELETE` is draft-only (`durable.ts:1210`), `send` distinguishes
  a first send from a reminder and refuses a terminal envelope (`:1227`–`:1233`),
  `resend` refuses a signer who is not pending (`:1295`), `complete` refuses a
  dead envelope, a repeat signature and an out-of-turn one (`:1434`–`:1438`).
- **Three transitions are guarded by nothing at all**, and until this packet
  nobody had written that down anywhere a test could hold. See §S6.
- **One status the product documents is never written by the worker.**
  `CLAUDE.md`:108–109 names six envelope statuses; `expired` is one, and
  `durable.ts` contains the string `expired` exactly twice, both times inside
  the message *"Invalid or expired verification code"* (`:803`, `:1359`).

## What this change does

**It adds ten frozen characterization cases, A-400 – A-409**, in one new file,
`service/src/test/envelope-lifecycle.test.ts`. They construct the Durable
Object over `spec/0004`'s existing `node:sqlite` harness and drive **every
transition through `fetch()`** — the same entrypoint `worker.ts` uses. No new
npm dependency, no new harness, nothing leaves the process.

The suite the merge gate prints goes from **11 passing, from 3 compiled** to
**21 passing, from 4 compiled**.

## The boundary this packet is under, and how the cases respect it

The packet that carries this says it in the same words `BACKLOG.md` item 1
does: **a test that *records* what the worker does today is ordinary work; a
test written to assert that a transition is the *right* one is a product
decision.** `spec/0004` §S4 established the idiom for a case that sits on such
a line, and every case here that does carries it: the assertion is marked
`RECORDED, NOT ENDORSED`, names the §S6 entry it belongs to, and says in the
file that **red there means someone took the backlog entry — a decision — and
not that the worker broke.**

Four such marks exist, on A-404, A-406, A-407 and A-409. **Not one of them is
repaired here**, and `git diff service/src/durable.ts` is empty in the commit
that carries this spec.

## What this change deliberately does not do

- **It does not change one byte of shipped worker code.** Four defects were
  found while characterizing. All four are proposed as `roadmap/BACKLOG.md`
  entries in §S6 and in the return block, and none rides in this packet.
- **It does not add `cancel`'s missing guard, an `expired` transition, or a
  tightened `email_verified` check.** Those are the three the packet named in
  advance, and they are proposals.
- **It does not characterize the OAuth branch of `establishSession`**
  (`durable.ts:766`–`:770`), which `spec/0004` §S5 records as a stated limit.
  The packet offered it *"if the slice still has room"* and **the slice does
  not have room** — measured, not felt: the test file alone is 30 632 bytes,
  and this repository carries two transcripts from one job ago of two families
  going mute on a bundle of that order — `recruit -f qwen` timing out at curl's
  600 s ceiling on 55 626 bytes (the figure the packet records), and `glm`
  returning an empty body on the 55 632 bytes its own header names. Growing the diff further would buy coverage by
  spending the cross-family review. It remains a stated limit and is proposed
  as its own small packet in §S6.
- **It does not deploy.** **Q-012** is open and explicitly outside CHARTER
  Part 0's proceed-on-default rule; **Q-018** adds that shipping this product
  means `wrangler deploy` from `service/`. A test-only change ships nothing to
  a user either way.
- **It does not add a `version` field to the root `package.json`**
  (`BACKLOG.md` item 4). Frozen case **A-208** asserts its absence precisely so
  a later packet cannot take it in passing; this packet does not open the file.
- **It does not touch `roadmap/**` or `spec/0004`'s frozen cases A-300–A-308.**
  Retiring or re-ranking item 1 is the product manager's.
- **It does not answer Q-018.** Nothing is deleted, no domain re-pointed, no
  data moved, and `CLAUDE.md`'s account of the two trees is untouched.
