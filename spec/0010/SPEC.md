# SPEC 0010 — `finalize`'s stamping branch, characterized by reading the artefact

**Intent:** [`INTENT.md`](INTENT.md).
**Takes:** **residual A** of `roadmap/BACKLOG.md` item 2's *"What is left"*
list, in the order that entry itself ranks its reasons — specifically its
reason **(ii)**, *"`finalize`'s stamping branch is the only uncovered path that
produces the artefact [`VALUE.md`](../../roadmap/VALUE.md) C1 promises"*. It
does **not** take residual A's other strands (envelope creation, copy,
templates, admin, the non-file routes); §S8 names them. It takes nothing of
residuals B, C or D.
**Also takes** `roadmap/BACKLOG.md` item 6(2) — the `CLAUDE.md` sentence that
counts this suite's files — because this packet is the one changing the number.
**Measured at** `132ee67`, by hand, 2026-09-01 06:45–06:56 UTC — outside the
queue, see §S0. **Re-verified at `a5d38f5`** by coder job `0099` on 2026-09-01
from 19:14 UTC. `a5d38f5` is one commit past `132ee67` and touches only
`service/src/feedback.ts` (+5 −2) — `durable.ts`, `core/stamping.ts` and
`storage/r2.ts` are byte-identical at both. Every line number below was
re-read at `a5d38f5`; four were **mis-cited by the hand build** (wrong at
`132ee67` by the same amount, since the files did not move) and are corrected
in place and listed in §S0.

## S0 · Provenance — this build was found in the tree, not filed by a job

**What was found.** At the project-manager tick of 2026-09-01 19:14 UTC the
working tree at `132ee67` held this spec (`INTENT.md`, `SPEC.md`),
`service/src/test/finalize-stamping.test.ts`, `service/src/test/support/pdf-probe.ts`
and a 14-line edit to `CLAUDE.md` — **uncommitted**, file mtimes 06:45–06:56
UTC, the same window in which job `0088` had been marked `FAILED` on a
weekly-limit error after running nothing. It had no author of record, no
review transcript, no gate run, and no test count measured under the queue.
Job `0095` reported *"nothing ran, the tree is clean"* and was rejected 2–1
because the tree was not clean; job `0099` was filed to read the build as a
submission rather than as its own.

**What job `0099` did with it, in order, all at `a5d38f5`.** (1) Pulled to
`a5d38f5` under the dirty tree — it fast-forwards because the one commit touches
none of the four paths. (2) Measured the service suite with the two test files
present and then moved aside: `# pass 48 # fail 0` and `# pass 38 # fail 0`,
which match job `0087`'s 38 at `132ee67` and this file's own claims. (3)
Re-ran §S7a's fifteen mutations from a script that aborts if a substitution
fails to match, against the whole service suite, reverting between rows:
**all fifteen reproduced exactly** as the hand build's table stated — the
same `# pass`/`# fail` counts and the same set of red cases, row for row.
After A-605 was strengthened on a spec-review objection (§S10b), the table was
re-run in full: M1 and M2 each gain A-605 and every other row is unchanged
(§S10c). (4) Re-ran the import scan §S1a
describes and the file counts §S6 states: eight `*.test.ts`, six importing
`support/durable-harness.js`, no test importing `mail.ts`, `feedback.ts` or
`convert/graph.ts`. (5) Ran root `npm test` with the `CLAUDE.md` edit in
place: A-107, A-108 and A-109 green. (6) Read every clause of §S3 and §S4
against `durable.ts`, `core/stamping.ts` and `storage/r2.ts` at `a5d38f5`;
each holds.

**What was corrected, and it is line numbers only.** Four `durable.ts`
references were **wrong as written** — not drifted: `durable.ts` is
byte-identical at `132ee67` and `a5d38f5`, so the hand build mis-read them by
one or two lines at the SHA it named. Corrected: `:1652` → `:1654` (§S3a, the
`signature_blob` capture), `:1749` → `:1750` (M4, `signedAt: s.signed_at`),
`:1783` → `:1782` (§S3b and M8, the `completedKey ? null : …` ternary),
`:1720` → `:1721` (M14, the `signed-pdf` branch of the file route). Each was
checked by reading the line at `a5d38f5`. The undeployed-repair count in §S1c,
§S3b and §S9 is restated for `a5d38f5`. No assertion, no case, no finding and
no mutation row was changed, and every mutation was re-run against the line it
now cites (§S10c).

**What was not adopted.** §S10's before/after figures and its `GATE: PASS`
line are the hand build's own claims and are labelled as such there; the
figures the commit message carries are §S10c's, measured under the queue. The
review round in §S10b is job `0099`'s, run on this text after the corrections
above.

**Governing charter — named here rather than left to a reviewer to guess.**
`pumasi/governance/CHARTER.md`, the copy containing Part 0. Two copies exist and
neither says which governs (`pumasi/DECISIONS.md` **Q-032**); spec/0007 §S10
established naming it in the spec as this product's workaround, and 0008 and
0009 repeated it. This spec resolves nothing about Q-032.

**One sentence about what kind of change this is, because it governs how
everything below should be read.** There is **no repair here.**
`service/src/durable.ts` and `service/src/core/stamping.ts` are byte-identical
to `132ee67`. The deliverable is ten frozen cases, one test-support module, and
four corrected sentences in `CLAUDE.md`. That inverts the usual evidence —
"red before, green after" is not available, because the code under test is not
moving — and what replaces it is **§S7a's mutation table**, which mutates the
worker fifteen ways and records which case catches each. A characterization
suite that no mutation can turn red is decorative (**L-006**), and this spec is
written to make that checkable rather than asserted.

---

## S1 · What was uncovered, measured rather than carried

### S1a · The branch

`service/src/durable.ts:1770`–`:1786`:

```ts
if (originalPdf) {
  const stampRes = await stampAndCertifyPdf({ ... });
  const completedKey = await this.storePdf('completed', submissionId, stampRes.stampedPdfBytes);
  this.sql.exec(
    `UPDATE submissions SET status = 'completed', completed_at = ?, completed_pdf_blob = ?, completed_pdf_key = ?, updated_at = ? WHERE id = ?`,
    now, completedKey ? null : stampRes.stampedPdfBytes, completedKey, now, submissionId,
  );
  this.audit(submissionId, 'completed', 'system@pumasi.ai', 'Pumasi Sign Engine', undefined, {
    originalHash: stampRes.originalHash, completedHash: stampRes.completedHash,
  });
} else { ... }
```

**Nothing had ever executed the `if` side.** Measured, not carried:
`envelope-lifecycle.test.ts`'s own seeder says so in its header — *"No
submission carries a PDF, which is the branch of finalize() that completes
without stamping"* — and it is the only file in the suite that reaches
`finalize` at all. So every `completed` envelope this repository had ever
asserted on was one with **no document**, taking the `else` at `:1787`.

**And the R2 boundary had never been crossed by anything.** `BACKLOG.md` item 2
residual B measured this **by import, not by grep**, and the method is part of
the finding: `grep -rl mail service/src/test/` hits every file because *email*
contains *mail*. Re-measured here at `132ee67` (and again at `a5d38f5` by §S0,
with the same result plus this packet's own `./support/pdf-probe.js`), the complete set of non-`node:`
module imports under `service/src/test/` was `../worker.js`,
`../core/stamping.js`, `../../durable.js`, `./support/durable-harness.js` and
`pdf-lib` (the harness import was missing from the first draft of this list; a
spec review caught it). **`storage/r2.ts` appeared in none of them**, so `docs()` (`:359`), `storePdf` (`:368`) and the
key-taking half of `loadPdf` (`:377`) had no assertion of any kind.

### S1b · What the two existing stamping cases do and do not assert

`stamping.test.ts` and `stamping-multi-signer.test.ts` call
`stampAndCertifyPdf` directly. Between them they assert: the returned byte
length exceeds the input's, `pageCount === 2`, and `originalHash !==
completedHash`. **That is the whole of it.** Neither loads the returned PDF.
Neither reads one character of what was stamped. Neither goes near the Durable
Object, a signer, a request, or the file route.

**This is not a criticism of those cases and this spec does not touch them.**
It is the measurement that sets this spec's problem: the product's central
artefact was covered by three shape predicates, and §S7a says what that costs
in exact numbers.

### S1c · What this suite does not claim

Three limits, stated so a green count is not over-read:

- **This is SQLite, but it is not workerd's SQLite** (spec/0004 §S1c). Evidence
  here is about `durable.ts`'s own logic, not about Cloudflare's storage engine.
- **The R2 binding is an in-memory stand-in** (`support/pdf-probe.ts`
  `fakeBucket()`). The **wrapper** under test — `R2SignStorage`, its key
  building, its content type, its null handling — is real and executes. What is
  stood in for is Cloudflare, which a test machine cannot reach. A case here is
  evidence about `storage/r2.ts` and `durable.ts`; it is **not** evidence about
  R2's durability, consistency or limits.
- **The PDF reader is not a general PDF text extractor** and must not be read as
  one. It walks each page's content stream through pdf-lib's own
  `decodePDFRawStream` and returns the operands of `Tj` show-text operators. That
  covers exactly what `core/stamping.ts` emits — pdf-lib's `drawText` writes one
  `Tj` per call — and nothing else. No case is written against a PDF this project
  did not itself create. A-600 is the reader's own guard (§S2).
- **And it is not a claim about production.** `sign.pumasi.ai` answered `200` at
  **06:53:25 UTC on 2026-09-01** serving `/assets/index-CnoFAC2c.js`,
  **unchanged** since the 01:02 UTC deploy, with `/api/version` still `404`.
  Re-curled by job `0099` at **19:34 UTC**: `200`, same bundle. Five merged
  repairs are behind it after `a5d38f5`, and this packet — test-only — does not
  make it six. That is `BACKLOG.md` item 1 and **Q-012**,
  it is operator action, and Q-018's default part (c) applies in full.

## S2 · The trap this suite is built around

**A test that reads a PDF can go vacuously green.** If the reader stops finding
text — a pdf-lib upgrade, a different content-stream shape, a wrong operator —
then `assert.ok(pages[0].includes('X'))` fails loudly, but
`assert.ok(!pages[0].includes('Y'))` and every "this did not appear" assertion
passes on an empty list. Half the content assertions in this file are of the
second kind, because "the client's chosen name is **not** printed" and "the CC
recipient is **not** certified" are exactly the things worth pinning.

**So A-600 is the guard on the guards**, the role `auth-session.test.ts`'s
A-300 and `oauth-callback.test.ts`'s A-500 play in their files. It asserts, on a
document produced by the whole chain, that the reader finds **the sender's own
body text** in the artefact, and that `probe.all.length > 0`. If the reader ever
stops working, A-600 goes red before any negative assertion elsewhere can pass
by finding nothing.

**The second trap is the one §S1b names, and §S7a is the measurement of it.**
Fifteen single-edit mutations of the worker were built and run. **Twelve of the
fifteen were invisible to the entire pre-existing 38-assertion suite** — every
frontend case, every service case, both stamping cases — and are caught only by
cases in this file. That is not an argument that shape assertions are weak; it
is the count.

## S3 · Three findings, recorded and not repaired

All three are marked **RECORDED, NOT ENDORSED** in the case file itself, in the
idiom spec/0004 §S4 established, spec/0005 A-409 used for `expired` and
spec/0009 A-502 used for the OAuth claim guard. Red at one of these means *"a
later packet took the strand"*, not *"the worker broke"*.

### S3a · An initials box gets a full signature, or a full typed name (A-607)

`stamping.ts:67` keys `embeddedSignatures` by **signer**, not by field. So:

- **(i)** a signer who drew a signature has that same full image stamped into
  their `initials` box as well as their `signature` box; and
- **(ii)** `durable.ts:1654` captures `signature_blob` **only** from a field of
  type `signature`. A signer whose only box is an `initials` box therefore
  arrives at `finalize` with no image — *even though they uploaded one and
  their field references it* — and `stamping.ts:95` falls back to
  `signer?.name`, printing the **full typed name** where initials were asked
  for.

A-607 pins (ii)'s cause where it happens rather than inferring it from the
output: it asserts the drawn mark reached the signature-field signer's
`submitters` row and did **not** reach the initials-only signer's.

**Not repaired**, and the reason is not caution: which of the two behaviours is
wrong is a product question. (i) might be intended (a drawn mark is a drawn
mark). (ii) is harder to defend, but the fix — capturing `signature_blob` from
`initials` fields too — changes what appears on documents people have already
been shown a preview of, and belongs to whoever ranks that against the rest.

### S3b · An envelope completes when its document cannot be loaded (A-608)

`finalize`'s `else` at `durable.ts:1787` marks the envelope `completed`, writes
a `completed` audit row **with no details**, and sends every party the *"is
fully signed"* email — while **no executed document exists**. The signer's
`POST /complete` answers `200 {"ok":true,"status":"completed"}`. The dashboard
says done. `GET /api/files/signed-pdf/:id` answers **`404 {"error":"Not
available"}`**.

**The only trace anywhere that no certificate was made is that one audit row's
`details_json` is `NULL`, and nothing in the product reads it.**

**Reaching it needs only `loadPdf` returning null**, which is not contrived:
`loadPdf` (`:377`) calls `this.docs()?.getDocument(key)`, and `R2SignStorage.getDocument`
returns `null` for a missing object rather than throwing — then falls through to
`original_pdf_blob`, which is `NULL` **by design whenever R2 is bound**
(`storePdf` writes the key and `durable.ts:1782`'s ternary nulls the column;
A-606 pins that). So a row pointing at an object the bucket no longer holds
takes this branch. A-608 drives exactly that and asserts, on the fake bucket's
own call log, that the read **was attempted and came back empty** — so it is the
missing-object path and not a case where R2 was never consulted.

**Not repaired, and this seat states plainly what it is not asserting.** It is
not asserting that this has happened in production; nobody has looked, and
`sign.pumasi.ai` is five repairs behind this tree anyway. It is not asserting
that throwing is the right fix — a `finalize` that refuses would leave the
envelope `pending` with every signer already signed and no route forward, which
is a worse failure wearing a better error message. **M10 in §S7a is that fix,
run**: it turns A-608 red as designed and *also* turns **A-406 and A-409** red,
two frozen cases from spec/0005 and spec/0006 that have nothing to do with
documents. That is the measurement that says this is not a one-line change, and
it is handed up rather than taken.

### S3c · A field placed past the end of the document is silently dropped (A-604)

`stamping.ts:79` skips any field whose page is out of range. The field is
accepted at `/complete`, its value is stored, and it appears nowhere in the
executed document — no error, no audit entry. Recorded inside A-604 rather than
given a case of its own, because it is the same line as the page-mapping
assertion and splitting them would double the setup for no extra evidence.

## S4 · One asymmetry worth naming, because it looks like a bug and is not this seat's to call

`finalize` builds the certificate's signer list with `AND is_cc = 0`
(`durable.ts:1746`) — so a CC recipient is **not** certified as having signed,
which is right. The completion-email loop further down the same function
(`durable.ts:1803`) has **no** `is_cc` filter — so a CC recipient **is** emailed
*"Everyone has signed"* with a retrieval link, which is also right, because that
is what being copied means.

A-602 pins **both halves**, and this spec names the asymmetry so that the next
reader does not "fix" one of them into consistency with the other. Neither is
changed here.

## S5 · What changes, exactly

| File | Change |
| :--- | :--- |
| `service/src/test/finalize-stamping.test.ts` | **New.** Ten frozen cases, A-600 – A-609. |
| `service/src/test/support/pdf-probe.ts` | **New.** The per-page PDF text reader, `makePdf`, the 1×1 PNG data URL, and `fakeBucket()`. Not a `*.test.ts` file, so it is neither counted by `assert-service-suite-ran.sh` nor run by `node --test`. |
| `CLAUDE.md:78`–`:81` | **Corrected.** §S6. |
| everything else | **Unchanged.** `durable.ts`, `core/stamping.ts`, `storage/r2.ts`, `worker.ts`, every existing test, `package.json`, `ci.yaml`, both `.github/scripts/` files, `roadmap/`. |

**No existing frozen case is amended, and this was checked rather than
assumed.** `frontend/src/ci-covers-service.spec.ts`'s A-109 holds a
**floor** — `files.length >= 2` — plus two named files that both still exist, so
an *added* file trips nothing. That floor's deliberate weakness is spec/0009
§S5a's and is unchanged by this packet. Nothing in `package.json`,
`.github/workflows/ci.yaml` or either `.github/scripts/` file names a test file
individually, so an eighth file needs no wiring: the guard's `src`-vs-`dist`
count moves from 7/7 to 8/8 on its own, and §S10 records it doing so.

## S6 · The `CLAUDE.md` sentence, which had been false for four packets

`CLAUDE.md:78`–`:81` at `132ee67` read:

> *"Test coverage here is thin and you should know it before you trust it:
> `src/test/` holds **two files and both exercise `core/stamping.ts` only**.
> **Auth, the Durable Object store, R2 and mail are covered by nothing.**"*

**Every clause in bold was false.** At `132ee67` the directory held **seven**
files, **five** of which drove the real Durable Object (`git grep -l
durable-harness 132ee67 -- 'service/src/test/*.test.ts'` → 5 of 7; the first
draft of this sentence said *four*, carrying `BACKLOG.md`'s figure, and a spec
review caught it); auth was covered by `auth-session.test.ts` and
`oauth-callback.test.ts`, and the store by the other three.
This is `BACKLOG.md` item 6(2). Three packets declined it as out of scope and
job `0087` could not take it — `CLAUDE.md` is not in the product-manager seat's
may-write list, and it recorded that as the reason. **It is in this seat's, and
this is the packet that changes the number, so it is taken here.**

The replacement states the count (**eight**), the split (**six** drive the real
Durable Object through `fetch()`, **two** call `core/stamping.ts` directly and
assert only shape), and what is **still** covered by nothing — `mail.ts` beyond
its unconfigured throw, `feedback.ts`, `convert/graph.ts`. Every figure in it
was measured on this tree by the import scan §S1a describes, not carried.

**It stays a warning rather than becoming a boast**, which is the point of the
sentence and the reason the "two files call stamping directly and assert only
the shape of what it returns" clause is in it. A file count is not coverage, and
a `CLAUDE.md` that implied it would be the same defect in the other direction.

**Checked against the frozen cases that read this file:** A-107 requires
`sign.pumasi.ai`, `service/`, `Cloudflare Worker`, `wrangler` and `Q-018` to be
present and two orderings to hold; A-108 requires `vue-tsc --noEmit` to be
absent. The edited paragraph contains none of those strings and moves no
heading. Both cases were run after the edit (§S10) and are green.

## S7 · The frozen cases

New file `service/src/test/finalize-stamping.test.ts`, run by the same
`.github/scripts/run-service-suite.sh` as every other case here. **No second
runner is stood up.**

| Case | What it pins |
| :--- | :--- |
| **A-600** | **The reader guard** (§S2). The whole chain — owner sign-in, signer token verify, signature upload, `POST /complete` — produces a `completed` envelope whose stored PDF is **not** the bytes that went in, whose audit row's `originalHash` equals a SHA-256 **this case computed** over the bytes it seeded, whose `completedHash` equals the SHA-256 of the stored artefact, and whose first page still carries the sender's own text. |
| **A-601** | The certificate names **this** envelope: `Envelope ID: <public_uid>  |  Completed: <the row's completed_at>` matched in full, `Title:`, `Original SHA-256:` against the independently computed hash, and the two legal lines. The **public** uid, not the internal id. |
| **A-602** | Two signers in order, finishing from **different addresses**. Each certificate block carries that signer's own name, role, email, `signed_at` and IP — and the two timestamps are asserted **different**, so a mutation that stamps one record twice cannot pass. Plus §S4's asymmetry: the CC recipient appears **nowhere** on the certificate. Plus: exactly one `completed` audit row, and the owner can download. |
| **A-603** | The body pages. What was typed is stamped; a `name` field is stamped **from the signer record and not from the request** (the case posts a different name and asserts it does not appear); an empty `date` is filled from the signer's own signing date; a `label` carries the sender's `default_value`; a ticked and an unticked checkbox store `'true'`/`'false'` and stamp **no text** either way. |
| **A-604** | The 0-based → 1-based page translation at `durable.ts:1766`. Three body pages, one field on each, each asserted **on its own page and not on the others**; the signature image on page one and on no other page; §S3c's out-of-range field dropped from every page including the certificate; page count 3 + 1. |
| **A-605** | The tamper-evidence claim end to end. `GET /api/files/signed-pdf/:id` returns bytes whose SHA-256 **equals the audit row's `completedHash`**, identically to the owner and to the signer, `404` to neither; `Content-Disposition` on both routes; the certificate page **inside the served bytes** prints `Original SHA-256: <h>`; and the original survives `finalize` byte-identical and hashes to that same `h` — read off the artefact a user holds, **and** off the audit row — so the certificate's claim is checkable *afterwards*, not only when it was made. (The first draft compared the audit row only while naming the certificate; a spec review caught it under M1, and the case now reads the printed line, which is why M1 and M2 turn it red.) |
| **A-606** | **The first assertion in this repository to execute `storage/r2.ts`.** With `DOCUMENTS` bound: `completed_pdf_key` is `completed/<id>.pdf`, `completed_pdf_blob` is `NULL`, the bucket's own call log shows the original **read** and the executed document **put** with `application/pdf`, the bucket's bytes hash to `completedHash`, the route serves those bytes, and the artefact is a real two-page stamped document rather than an object with the right key. |
| **A-607** | **RECORDED, NOT ENDORSED.** §S3a, both halves, plus the cause pinned at the `submitters` row. |
| **A-608** | **RECORDED, NOT ENDORSED.** §S3b, including the bucket call log proving the read was attempted, the `NULL` `details_json` as the only trace, and the owner's `404` on a document the product told them was complete. |
| **A-609** | A **preservation invariant**, the analogue of spec/0002 A-109 and spec/0001 A-005. Correctly green before and after. Exactly one page added; it is the certificate; it is **last**; every original page keeps its own text in its own order and none of them became the certificate; the stored original is byte-identical to what was uploaded. Its value is that it fails the change that "simplifies" stamping into rendering a fresh document from field values — which would satisfy every certificate assertion above while losing the contract the parties actually signed. |

### S7a · Mutations — run, not argued

Each row is a **single** edit to `service/src/durable.ts` or
`service/src/core/stamping.ts`, built with `npm run build` and run against the
**whole** service suite, then reverted. All fifteen were executed by this seat at
`132ee67`. The unmutated tree is `# pass 48 # fail 0`.

| # | Mutation | Result | Red |
| :-- | :--- | :--- | :--- |
| **M1** | `stamping.ts:277` returns the input bytes unstamped | `# pass 37 # fail 11` | A-600 – A-607, A-609 **+ both existing stamping cases** |
| **M2** | the certificate page is `insertPage(0, …)` rather than appended | `# pass 39 # fail 9` | A-600 – A-607, A-609 |
| **M3** | `durable.ts:1766` stops translating 0-based page to 1-based | `# pass 45 # fail 3` | A-603, A-604, A-607 |
| **M4** | `durable.ts:1750` stops passing each signer's own `signed_at` | `# pass 47 # fail 1` | **A-602 only** |
| **M5** | `durable.ts:1746` drops `AND is_cc = 0` | `# pass 47 # fail 1` | **A-602 only** |
| **M6** | `stamping.ts:106` prefers the client's value over the signer record for a `name` field | `# pass 47 # fail 1` | **A-603 only** |
| **M7** | `durable.ts:1767` stops filling a `label` from `default_value` | `# pass 47 # fail 1` | **A-603 only** |
| **M8** | `durable.ts:1782` writes the executed PDF to the row even when R2 took it | `# pass 47 # fail 1` | **A-606 only** |
| **M9** | `stamping.ts:67` never populates `embeddedSignatures`, so no drawn signature is embedded | `# pass 46 # fail 2` | A-604, A-607 |
| **M10** | `finalize`'s `else` (`:1787`) becomes `return` — it refuses to complete an envelope whose document it cannot load | `# pass 45 # fail 3` | A-608 **+ A-406, A-409**. See §S3b. |
| **M11** | `stamping.ts:278` hashes the input rather than the saved document | `# pass 43 # fail 5` | A-600, A-605, A-606 **+ both existing stamping cases** |
| **M12** | `stamping.ts:52` computes `originalHash` over the wrong bytes | `# pass 44 # fail 4` | A-600, A-601, A-605, A-606 |
| **M13** | `stamping.ts:79` drops the out-of-range page guard | `# pass 47 # fail 1` | **A-604 only** |
| **M14** | the `signed-pdf` route (`:1721`) falls back to the original document | `# pass 46 # fail 2` | A-605, A-606 |
| **M15** | the certificate stops printing the envelope's public uid | `# pass 47 # fail 1` | **A-601 only** |
| — | the tree as merged | `# pass 48 # fail 0` | — |

### S7b · What the table says, in one number

**Twelve of the fifteen — M2 through M9, M12 through M15 — turned nothing red
outside this file.** Not one of the 38 assertions that existed at `132ee67`
noticed the certificate losing the envelope's identity (M15), every signature
landing on the wrong page (M3), the client choosing the name printed on a legal
document (M6), a CC recipient being certified as a signer (M5), one signer's
timestamp being stamped against every block (M4), or the executed PDF being
written to a database row that a bound R2 was supposed to keep it out of (M8).

**Three were caught by the pre-existing suite**, and it is worth being precise
about which: **M1** and **M11** by the two existing stamping cases — which is
those cases working, on exactly the two shape predicates they hold — and **M10**
by A-406 and A-409, which caught it as a *status* regression rather than as
anything about documents.

**M12 is the sharpest single row.** `originalHash` is the number the certificate
prints as the document's fingerprint, and it is the whole of what "tamper-evident"
means on that page. Corrupting it was invisible to a suite whose only hash
assertion was `originalHash !== completedHash` — which stays true when one of
them is nonsense.

## S8 · What is deliberately not built

**Residual A's other strands**, named so the register is not left to guess:
envelope creation (`POST /api/submissions`), copy, templates, admin, and the
`signature` file route. Untouched. `finalize` is reached only through
`POST /api/sign/:id/complete`; the envelope is seeded, which is
`envelope-lifecycle.test.ts`'s convention and its stated reason — dragging the
creation wizard in would make a red here ambiguous between two subjects.

**Residual B beyond `storage/r2.ts`.** `mail.ts` beyond its unconfigured throw,
`feedback.ts` and `convert/graph.ts` are untouched; each crosses a network
boundary this suite has no stubs for. `worker.ts` is still reached only through
`scheduled()` (A-415).

**Residual C.** `frontend/playwright.config.ts:58`–`:66` still boots
`alembic upgrade head` and `uvicorn app.main:app` against `backend/`.
**Re-read at `132ee67`, not touched**, per the packet's boundary and item 2's
own grounds: it cannot be measured on this machine, and re-pointing the only
route-driving suite is the closest a build comes to *acting on* Q-018.

**Residual D.** `durable.ts:848` is not edited, so neither the dead `!email`
clause nor mutation M1-of-spec/0009 is closed — *"close both or neither"*, and
this packet does neither because it never goes near that line.

**And in this slice specifically:**

- **No worker change.** Not one byte of `durable.ts` or `core/stamping.ts`. The
  three findings in §S3 are recorded and handed up.
- **No `RISK_ZONES.yaml`.** Still absent — re-checked at `132ee67`, `ls
  RISK_ZONES.yaml` → *No such file or directory*. Still `BACKLOG.md` item 5, and
  §S9 records what its absence cost a **fourth** consecutive spec.
- **No deploy, and no seat here proposes a deployer or a date.** Q-012.
- **`roadmap/` untouched**, including `STAGE.md`. Ranking is the
  product-manager seat's; the sentences this packet made false are named in the
  return block for that seat to strike, which is how job `0087` recovered job
  `0080`'s entire re-rank.
- **No release note.** §S9.

## S9 · Risk class — `ordinary`, argued rather than assumed

**This change adds two test-tree files and edits four lines of `CLAUDE.md`.
Every runtime source file is byte-identical to `132ee67`. No byte reaches a
user either way.**

CHARTER Part 4's question is *can this change hurt someone outside the
project?*, and its own table's `Ordinary` row reads **"docs, tests, library
code"**. This change is exactly those two categories and nothing else.

**The counter-reading is stated rather than skipped**, because this repository
has **no `RISK_ZONES.yaml`** and Part 4 defaults to *can hurt someone* when
unmapped. Part 4's inheritance rule is *"risk travels along the handling
path"* — a component is can-hurt if it **handles** the money, credential or
personal data. **This change adds no handling path**: the new files run only
under `node --test`, are not bundled by `wrangler`, and construct their own
in-memory database and their own fake bucket. Test fixtures contain invented
names and `example.test` addresses, which is documentation-range data by
construction.

Part 4's can-hurt procedure differs from the ordinary one in exactly one
respect: *"the **release** proceeds through the 7-day veto window on a
plain-language note"*. **There is no release.** Nothing user-visible changed, so
a note would have to be manufactured to give the window something to govern.
**And one thing this seat checked because the packet made it an explicit
boundary:** merging this is a **test-only change** and moves the undeployed
count by nothing. `a5d38f5` made that count five; this packet adds no runtime
byte, so it stays five and `BACKLOG.md` item 1 is unaffected by anything here.

**So: `ordinary`, no release note, no 7-day window, and this seat is not
reclassifying any path** — Part 4 makes reclassification itself a can-hurt act,
and nothing here moves a path in either direction. If a reviewer cites the
unmapped default against this reading, the remedy is one extra review, not a
note about a change no user can see. That a **fourth** consecutive spec has had
to argue Part 4 by hand is itself the argument for `BACKLOG.md` item 5, and is
handed up as such.

## S10 · Verification, and review

**The figures in this section down to §S10a are the hand build's own, measured
outside the queue at `132ee67` (§S0). They are kept as what that build claimed.
The figures measured under the queue, at `a5d38f5`, are §S10c's, and those are
the ones the commit message carries.**

**Before, at `132ee67`, with this packet's two new files moved aside and
`CLAUDE.md` reverted — root `npm test`, three consecutive runs, identical, at
06:51:29 / 06:51:43 / 06:51:58 UTC:**
`Test Files 6 passed (6)` · `Tests 86 passed (86)` · `# pass 38` · `# fail 0` ·
`assert-service-suite-ran: 38 passing, 0 failing, from 7 compiled file(s) for 7
source file(s)`.

**These are job `0087`'s figures, independently re-measured on this tree by this
seat rather than carried**, and they match exactly.

**After, three consecutive runs, identical, at 06:52:20 / 06:52:35 / 06:52:51
UTC:**
`Test Files 6 passed (6)` · `Tests 86 passed (86)` · `# pass 48` · `# fail 0` ·
`assert-service-suite-ran: 48 passing, 0 failing, from 8 compiled file(s) for 8
source file(s)`.

**`service/` alone, three consecutive runs, each preceded by
`rm -rf dist && npm run build`, at 06:53:12 / 06:53:15 / 06:53:18 UTC:**
`# tests 48` · `# pass 48` · `# fail 0` each time.

**+10 service assertions across an eighth file** (A-600 – A-609), **+1 source
file**, **+0 frontend assertions** — the frontend count is unchanged at 86
because A-109's floor is `>= 2` and an added file trips nothing (§S5), and
because A-107/A-108 read `CLAUDE.md` for strings this edit does not touch (§S6).
The frontend suite was run after the `CLAUDE.md` edit and is green in all three
after-runs above.

**`rm -rf service/dist` was run before every build in this packet.** No test
file was renamed or deleted here, so the A-104 trap spec/0009 §S10 hit does not
apply — but the mutation table rebuilt the tree thirty times, and a stale `dist`
would have silently run a previous mutation's output. The habit is cheap and the
alternative is unmeasurable.

**`pumasi/tools/gate.sh`** — the hand build's `GATE: PASS` claim is **not
adopted**; the queue's own gate run is recorded in §S10b.

### S10c · Re-measured under the queue, at `a5d38f5` (job `0099`)

All at `a5d38f5`, `node` v22.22.1, each service run preceded by `rm -rf dist &&
npm run build`, 2026-09-01 19:2x UTC:

| Run | Result |
| :--- | :--- |
| `service/` alone, the two new files **present** | `# tests 48` · `# pass 48` · `# fail 0` |
| `service/` alone, the two new files **moved aside** | `# tests 38` · `# pass 38` · `# fail 0` |
| root `npm test`, files present, `CLAUDE.md` edited | `Test Files 6 passed (6)` · `Tests 86 passed (86)` · `# pass 48` · `# fail 0` · `assert-service-suite-ran: 48 passing, 0 failing, from 8 compiled file(s) for 8 source file(s)` |
| §S7a, all fifteen rows, scripted, whole service suite — **first run, against the found file** | **every row reproduced exactly** as the hand build's table stated — M1 38/10, M2 40/8, M3 45/3, M4 47/1, M5 47/1, M6 47/1, M7 47/1, M8 47/1, M9 46/2, M10 45/3, M11 43/5, M12 44/4, M13 47/1, M14 46/2, M15 47/1, same red set per row; unmutated 48/0 afterwards |
| §S7a, all fifteen rows, **second run, after A-605 was strengthened** (§S10b) | M1 **37/11** and M2 **39/9** (each gains A-605); M3–M15 identical to the first run; unmutated 48/0 afterwards. This is the table §S7a now prints. |

The 38-without figure matches job `0087`'s at `132ee67`; the PR body for
`a5d38f5` reported `2/2`, which is a different count of a different thing and
was not reconciled here.

### S10a · Review

CHARTER §3, and `roadmap/STAGE.md` is `alpha`, so **Part 0 makes review advisory
rather than blocking** — it is run in full regardless, and its transcripts are
committed **including any that time out or object**. `efed763` is this
repository's own standing example of a timeout published rather than dropped.
Reviewers are chosen by `tools/review.sh`; the builder is `claude` and no
reviewer may share that family (requirement 3).

**What is known about the fleet before the round is planned, from job `0080`'s
measurements:** `grok` is HTTP 402 fleet-wide, and `qwen` timed out at curl's
600 s ceiling on a **150,607-byte** code review while returning cited, correct
objections on 31–35 KB spec rounds. This packet's diff is smaller than that one
but not small. Both outcomes are recorded in §S10b as measured, not as expected.

### S10b · The round as run

*Filled in by the implementation commit, from the transcripts under `reviews/`.*

---

## S11 · One thing this spec asks the next seat to notice

**The three findings in §S3 were not looked for.** They fell out of writing
assertions against the *content* of an artefact that had only ever been checked
for *shape* — which is `BACKLOG.md` item 2's reason (iii) holding for a fifth
consecutive delivery: *"the defects have actually been in `durable.ts`, found by
coverage of `durable.ts`. That is an observed base rate over four deliveries,
not a guess."* It is now five, and the base rate is the strongest argument in
the register for what to fund next.
