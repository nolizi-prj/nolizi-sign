# SPEC 0009 — The OAuth callback, characterized; and a file that claimed to be an end-to-end test

**Intent:** [`INTENT.md`](INTENT.md).
**Takes:** two of the five strands `roadmap/BACKLOG.md` item 2 lists under
*"What is left"* at `f0d1912` — its **named first slice** (the OAuth callback)
and the **`e2e-workflow.test.ts` misnomer**. It takes none of the other three,
and §S8 names them.
**Measured at** `f0d1912`, by the coder seat of job `0080`, 2026-09-01 UTC.
`main` was `f0d1912` at the lock and did not move under this seat; every line
number below was read at that SHA.

**Governing charter — named here rather than left to a reviewer to guess.**
`pumasi/governance/CHARTER.md`, the copy containing Part 0. Two copies exist
and neither says which governs (`pumasi/DECISIONS.md` **Q-032**); spec/0007
§S10 established naming it in the spec as this product's workaround and
spec/0008 repeated it. This spec resolves nothing about Q-032.

**One sentence about what kind of change this is, because it governs how
everything below should be read.** There is **no repair here.** Not one byte of
`service/src/durable.ts` changes. The deliverable *is* the frozen cases, plus a
rename. That inverts the usual evidence: "red before, green after" is not
available, because the code under test is not moving. What replaces it is §S7's
mutation table, which mutates **the worker** and records which case catches
each mutation. A characterization suite that no mutation can turn red is
decorative, and this spec is written to make that checkable rather than
asserted.

---

## S1 · What was uncovered, measured rather than carried

`grep -rin oauth service/src/test/` at `f0d1912` — **no matches.** The two legs
of `GET /api/auth/oauth/(google|microsoft)(/callback)?` (`durable.ts:783`) had
no assertion of any kind on them: not the authorize redirect, not the state
row, not the token exchange, not the claim guard, not the session it mints.

`roadmap/BACKLOG.md` item 2 cites this branch at `durable.ts:766` from the
fourth evaluation and marks the number **carried, not confirmed**. **Re-measured
by this seat: the guard is `durable.ts:848`**, and `grep -rn email_verified
service/src/` returns **exactly one hit**, that line. The guard itself is
unchanged from what the entry describes.

```ts
const email = String(claims.email || claims.preferred_username || '').trim().toLowerCase();
if (!email || !email.includes('@') || claims.email_verified === false) {
  return new Response(null, { status: 302, headers: { Location: '/login' } });
}
const name = String(claims.name || email.split('@')[0]).slice(0, 120);
const { cookie } = this.establishSession(email, name, oauthMatch[1]);
```

## S2 · The trap this suite is built around, and it is the reason the cases are heavy

**Five distinct failures on this route return the byte-identical response
`302 → Location: /login`:**

| Failure | Where |
| :--- | :--- |
| no `auth_codes` row for the state | `durable.ts:818` |
| no `code` query parameter | `durable.ts:818` |
| the token exchange answered non-`ok` | `durable.ts:835` |
| the `id_token` payload did not parse, or was absent | falls through to `:848` with `claims = {}` |
| the claim guard rejected the claim set | `durable.ts:848` |

A case that asserted *only* status and `Location` would therefore pass while
exercising **a completely different branch from the one it names** — and would
keep passing if the branch it names were deleted. That is
`pumasi/lessons/L-006` at branch scale, and it is the specific way a
characterization suite on this route goes decorative.

**So every negative case in this file also asserts how far the request got:**

- **the token endpoint was called** — counted on the stub, not inferred. This
  is what separates "the guard refused" from "the state check refused".
- **the state row was or was not consumed**, read back from `auth_codes`. Every
  negative case pins this; A-505 did not in the first draft and was corrected
  by the spec review, which is §S7b.
- **`users`, `sessions` and `org_branding`**, so a refusal is proved to have
  written nothing rather than merely redirected. Empty, except in A-506's two
  pre-exchange refusals, which run on a store that already holds the account
  A-506 signed in and therefore pin the counts as *unchanged* rather than as
  zero — a stronger check on a non-empty store, and named here because §S2's
  claim is "every negative case" and a claim with a silent exception is the
  defect two rounds of this spec's review already caught (§S7b).

**A-500 is the guard on the guards** (`auth-session.test.ts` A-300's role, at
route scale): it proves the authorize leg really stores state, that the
callback really consumes it, and that the stub is really reached — with the
exact form body. Without A-500, four of the five negative cases could be green
on a request that never left `:818`.

## S3 · The finding, stated at the strength the evidence supports and no higher

**Measured, at `f0d1912`, by A-502: an `id_token` whose payload OMITS
`email_verified` is admitted. It receives a `sign_session` cookie, an account
row is created, and `GET /api/auth/me` answers `200` on that cookie.** The
guard tests `=== false`, and `undefined !== false`.

That is the whole claim. Four things it is **not**:

- **It is not a demonstrated vulnerability, and this seat does not assert one.**
  `BACKLOG.md` item 2 calls the strand *"security-shaped on a live auth path,
  not a demonstrated vulnerability"* and records that the proposing seat was
  not asserting exploitability. Nothing measured here changes that. Reaching
  the branch requires an `id_token` from the configured provider's own token
  endpoint, for this deployment's `client_id`, with this deployment's
  `client_secret`, against a state row this worker minted minutes earlier.
- **The mitigation in the code's comment is real and is not waved away.**
  `durable.ts:840`–`:841`: the token comes directly from the provider's token
  endpoint over TLS. That is why the missing signature check is a considered
  position rather than an oversight, and it is why the *cheap* next step was
  always the covering test rather than a patch.
- **It is not a claim about production.** This suite runs node:sqlite under
  `node --test`, not workerd (spec/0004 §S1c). And the deployed bundle is not
  this tree: `sign.pumasi.ai` has served `/assets/index-CnoFAC2c.js` since
  2026-09-01 01:02 UTC with four merged repairs behind it (`BACKLOG.md` item 1,
  **Q-012**). Q-018's default part (c) applies in full.
- **It is not a decision.** See §S4.

**What would raise it.** A path by which an attacker obtains a token-endpoint
response for this deployment's credentials carrying an email they do not
control and no `email_verified` claim. Google's and Microsoft's `id_token`s
both carry the claim in ordinary operation, which is why nobody has met this;
whether either omits it under any configuration is a question about the
providers, not about this repository, and this seat did not answer it. That is
the gap between A-502 and a promotion, and it is stated so that the next seat
knows what evidence would close it.

## S4 · The boundary: characterize, do not adjudicate

`BACKLOG.md` item 2's boundary is *"characterize, do not adjudicate"*, it says
that boundary **must survive**, and it names `auth-session.test.ts` **A-302**
as the model. This spec honours it exactly and the mechanism is copied, not
paraphrased:

**No guard is changed.** `service/src/durable.ts` is byte-identical to
`f0d1912` (`git diff f0d1912 -- service/src/durable.ts` is empty). A-502 is
marked **RECORDED, NOT ENDORSED** in its own comment, and that comment states
the consequence in advance, the way A-302 does: **if a later packet tightens
the guard, A-502 going red is the correct outcome** — amend it with that
change, do not treat it as a regression and do not work around it.

**Why the restraint is right here and is not timidity.** Item 2's own text
ranks this as a slice *because* the covering test is the cheap step; job
`0050`'s proposal 5 asked for the test at `priority: medium`, not for a fix;
and the packet is explicit that a guard change is a behaviour change on a live
auth path that this job was not vetted for. Changing who may enter a product,
in the same commit as the first test that ever ran the path, on this seat's own
reading, is the shape of change this whole flow exists to prevent. §S9's
handover asks for the ranking.

**Two things the mutation table proves about that restraint** (§S7):
`M1` — tightening the guard to `claims.email_verified !== true` — turns
**A-502 red and nothing else**, and leaves A-501 and A-506 green. So the fix is
one token, the suite already discriminates it, and the next seat inherits both
the change and its test. The restraint costs that seat nothing.

## S5 · The rename, and the frozen case it trips

**What was measured, at `f0d1912`, not carried.** `e2e-workflow.test.ts`'s
imports are `node:test`, `node:assert/strict`, `pdf-lib` and
`stampAndCertifyPdf` — **identical to `stamping.test.ts`** — and the file holds
one `test()` which builds a PDF in memory and stamps it. It calls no route,
starts no worker, touches no store. Item 2 has carried that sentence since the
fourth evaluation and it is still true.

**`git mv service/src/test/e2e-workflow.test.ts
service/src/test/stamping-multi-signer.test.ts`**, and the `test()` title from
*"End-to-End Signing Workflow: Multi-Signer Agreement -> Stamping -> Audit
Certificate Verification"* to *"stampAndCertifyPdf stamps a two-signer
agreement and appends a parseable audit certificate"*. **Not one assertion
changed**; a header comment was added recording the old name, what was wrong
with it, and that the suite's only end-to-end coverage over HTTP is still the
Playwright suite driving `backend/` — so the correction does not leave a reader
believing a gap closed that did not.

### S5a · A-109, and `pumasi/DECISIONS.md` Q-030

**The rename trips a frozen acceptance case, and the packet did not know it.**
`frontend/src/ci-covers-service.spec.ts:369` — **A-109**, frozen under
spec/0002 §S4b — asserts that `service/src/test/` holds `stamping.test.ts` and
`e2e-workflow.test.ts`, by name. A-109 is spec/0002's **preservation** case:
its stated purpose is to fail *"the packet that satisfies 'make the gate cover
the tree users actually meet' by making the gate smaller"* — the assertion form
of *do not delete a test, a job, or a directory*.

CHARTER Part 3 requirement 2 freezes it and forbids the builder to edit it,
and names its own remedy: amend the spec in the open, take a fresh cross-family
spec review. **Who may author that amendment is Q-030, which is open.**

**This spec proceeds on Q-030's stated default, and says so rather than
proceeding quietly.** That default: the remedy *is* available to the builder,
on the conditions the clause already states — a numbered amendment in the spec
file, never a silent edit — plus rider (a) (say whether the amendment changes a
**fixture** or an **assertion**) and rider (b) (the amendment's spec reviewer
must not be the code reviewer of the change). Two supports beyond the default's
own text: `roadmap/STAGE.md` is `alpha`, so **CHARTER Part 0** applies — *"open
windows do not hold work … a veto reverts instead of prevents"* — and **this
repository has already done exactly this**, at `68e5d08`, where spec/0006
§S4-Q030 amended frozen cases A-404, A-406 and A-407 in the open under the same
default. This is that precedent's second use, not its first.

**Rider (a): this is the harder classification of the two, and it is claimed as
a fixture change with the reasoning shown rather than asserted.** The
*standard* A-109 enforces is "nothing is bought by deletion". **Nothing was
deleted**: it is one `git mv`, the artefact is the same artefact, and the suite
that runs it is the same suite. What moved is **the string by which the case
locates what it protects** — which is rider (a)'s *"how a case is set up"*
rather than *"what a case asserts"*.

**Precisely what did and did not change inside the renamed file, because an
earlier draft of this paragraph said "the file's content is byte-identical" and
a spec review cited that against §S5, which records a changed `test()` title
and an added header comment** (the third round of
`reviews/20260831-*-spec-qwen.md`; the claim was wrong and is withdrawn).
**Measured, `git diff -M`: the whole diff removes exactly one line — the old
`test()` title — and adds a title and a header comment. Not one assertion, not
one fixture value and not one import changed.** That is the accurate form of
the claim rider (a) needs, and it is weaker than what the earlier draft
asserted.

**A reviewer may still reasonably disagree with the classification**, on the
ground that a filename inside an `existsSync` is textually an assertion; if so,
weigh it as a standard change, and note that under that reading the amendment
is still in the direction below.

**The amendment does two things, and the second is why the first is safe.**

1. The spelling: `"e2e-workflow.test.ts"` → `"stamping-multi-signer.test.ts"`.
2. **A new `it()`: `service/src/test/` never holds fewer than two `*.test.ts`
   files**, counted by reading the directory rather than by naming anything.

**Direction — the test spec/0002's own amendment 1 applied to itself.** (2)
makes A-109 *strictly more able to fail* and *no easier to pass*. **No
assertion was weakened or removed**; both filenames are still required to
exist, and (2) can only ever add a way for the case to go red.

**What (2) actually guarantees, stated narrowly — and this paragraph is
qwen's, from the first spec review of this document
(`reviews/20260831-231324-spec-qwen.md`), which objected to an earlier draft
that overclaimed here.** That draft said (2) *"now catches a deletion whatever
anything is called"*. **That was false and is withdrawn.** The floor is `>= 2`;
`service/src/test/` holds seven files today, so deleting an unlisted third file
leaves five and the case stays green. What (2) does guarantee is narrower and
is the whole of it: **the directory can never be emptied or reduced below the
two files this case froze, whatever the survivors are called** — so a packet
that satisfies A-109 by deleting its filename list along with the files it
names still fails. That is a real hole and it is the one this amendment closes;
it is not the general one.

**And the general one is not left unguarded, it is simply guarded elsewhere.**
`.github/scripts/assert-service-suite-ran.sh` compares the count of
`src/test/*.test.ts` against `dist/test/*.test.js` on every run and fails on a
mismatch — exercised by frozen case **A-104**, and §S10 records it catching a
real stale artefact during this very job. A per-file census inside A-109 would
need a recorded baseline of the current count, which would go stale on every
legitimate addition (L-007: a second copy of a number forks from the first).
The floor is chosen for what it can hold without forking; the honest limit is
stated here rather than discovered by the next reader.

**Rider (b) is honoured in §S10.**

## S6 · What was NOT renamed, and it is a choice rather than an omission

`grep -rn e2e-workflow` over the tree after the rename still returns matches in
`roadmap/BACKLOG.md` (4), `roadmap/STAGE.md` (4), `spec/0002/INTENT.md`,
`spec/0002/SPEC.md` §S4b, `spec/0004/INTENT.md`, `spec/0005/SPEC.md` and one
`reviews/` transcript. **None was rewritten, and the exit criterion's
"no dangling reference" is read as being about references a reader or a runner
follows, not about dated prose that recorded a true thing on the day it was
written.** Three reasons, in order of weight:

- **They are published dated records.** Review transcripts, `STAGE.md`'s
  evaluation change-log rows (`:1330`, `:1331`), `BACKLOG.md`'s
  *"Re-verification, and what was measured against what"* section, and the
  published `INTENT.md` files all say what somebody measured on a stated date.
  This repository's rule for those is `pumasi/DECISIONS.md` Q-034's — correct
  by a new entry, never by an edit to what was published — and spec/0008 §S11
  applied it within the hour, declining to fix a wrong job number in two
  published records. Rewriting them would make them stop being records.
- **`roadmap/` is the product manager's ranking, and the packet's boundary is
  explicit.** *"You may not re-rank `roadmap/BACKLOG.md` … Say in your return
  block what you delivered; the next evaluation strikes it."* Item 2's
  paragraphs about this file are the entry's *argument for its own rank*;
  editing them is editing that argument. **Established practice agrees:**
  neither prior coder commit on this product (`68e5d08`, `9659e69`) touched
  `roadmap/` at all, and in both cases the next product-manager evaluation
  struck the entry.
- **The trail still leads somewhere.** The renamed file's own header names the
  old name, what was wrong with it, and this spec. A reader who greps the old
  name lands on the record of why it changed.

**So this is handed up, in §S9 and in the return block**, as: `BACKLOG.md` item
2's `e2e-workflow.test.ts` strand and `STAGE.md` §2.1's matching bullet are
**delivered**, and the sentences asserting the file *is still* misnamed are now
false and are the next evaluation's to strike.

**One thing that IS a runner reference and was updated:**
`frontend/src/ci-covers-service.spec.ts` (§S5a). Nothing in `package.json`,
`.github/workflows/ci.yaml` or either `.github/scripts/` file names any test
file individually — checked, not assumed — so the rename needed no change
there.

## S7 · The frozen cases, and the mutation table that is this spec's real evidence

New file `service/src/test/oauth-callback.test.ts`, seven cases, run by the
same `.github/scripts/run-service-suite.sh` as every other case here. **No
second runner is stood up.**

| Case | What it pins |
| :--- | :--- |
| **A-500** | The reader guard. The authorize leg redirects to the provider with `client_id`, `redirect_uri`, `scope`, `prompt` and a `state`; the state is an `auth_codes` row under `oauth:<state>` carrying the `next`; the callback reaches the token endpoint at the provider's real URL with the exact five-field form body; the state row is consumed. Plus the authorize leg's open-redirect guard: `https://evil…` and `//evil…` are stored as `/`. |
| **A-501** | `email_verified: true` establishes a session: cookie set, account created, address lower-cased, `provider` recorded as the URL segment, `org_branding` created, redirect to the **stored** `next`, and the cookie is one `/api/auth/me` accepts. |
| **A-502** | **The finding.** `email_verified` **absent** is admitted — cookie, account, working session, redirect to `/`. Recorded, not endorsed (§S3, §S4). |
| **A-503** | `email_verified: false` is refused: `/login`, no cookie, no user, no session, no workspace — **and the token endpoint was called**, so the refusal is the guard's and not the state check's. Plus: the state was spent before the exchange, so a replay of it cannot re-enter. |
| **A-504** | A non-`ok` token response is refused **before the payload is read** — the fixture's body carries a claim set that would otherwise pass, so a case that skipped the status check would sign someone in. |
| **A-505** | Four unparseable/absent `id_token` shapes, each on its own harness, and an address with no `@`. What refuses them is the `!email` / `includes('@')` half of the guard rather than the `try/catch`, which is what makes this case survive a future edit that gave `claims` a default. Each shape also pins the token endpoint being reached and the state row being consumed — see §S7b. |
| **A-506** | Microsoft's `preferred_username` fallback and the local-part display name (**not** title-cased — the email path's prettifying is not on this route, recorded because it is the kind of difference a reader assumes away); provider `503` on both legs when unconfigured, minting no state; an unknown provider is `404`; and a callback with no state row or no `code` is refused **without reaching the token endpoint**. |

### S7a · Mutations — run, not argued

Each row is a **single** edit to `service/src/durable.ts`, built and run
against the seven cases, then reverted. All ten were executed by this seat at
`f0d1912`.

| # | Mutation of the worker | Result |
| :-- | :--- | :--- |
| **M1** | the guard tightened: `=== false` → `!== true` | `# pass 6 # fail 1` — **A-502 only** |
| **M2** | the `email_verified` clause dropped from the guard | `# pass 6 # fail 1` — **A-503 only** |
| **M3** | `if (!tokenRes.ok)` → `if (false)` | `# pass 6 # fail 1` — **A-504 only** |
| **M4** | the `!email` clause dropped from the guard | `# pass 7 # fail 0` — **nothing red.** See below. |
| **M5** | the `!email.includes('@')` clause dropped | `# pass 6 # fail 1` — **A-505 only** |
| **M6** | the `DELETE FROM auth_codes` after the state lookup removed | `# pass 2 # fail 5` — A-500, A-502, A-503, A-504, A-505 |
| **M7** | the `claims.preferred_username` fallback dropped | `# pass 6 # fail 1` — **A-506 only** |
| **M8** | the authorize leg's `next` guard → `const next = rawNext;` | `# pass 6 # fail 1` — **A-500 only** |
| **M9** | the provider-unconfigured `503` weakened to `if (!provider)` | `# pass 6 # fail 1` — **A-506 only** |
| **M10** | the display name no longer derived from the local part | `# pass 6 # fail 1` — **A-506 only** |
| — | the tree as merged | `# pass 7 # fail 0` |

### S7b · One case was strengthened by the spec review, and the table above is the re-measurement

**The second spec review objected, cited, and was right.** `reviews/20260831-232258-spec-qwen.md`
(qwen) held §S2's claim — that *every* negative case pins how far the request
got, including whether the state row was consumed — against §S7a's M6 row, and
observed that **A-505 stayed green when the `DELETE` was removed**, so it was
exempting itself from the claim the spec made on its behalf.

**Resolved by making the claim true rather than by narrowing it.** A-505 now
asserts the state row is consumed on all four `id_token` shapes and on the
no-`@` address, and asserts the token endpoint was reached on the no-`@` case,
which it also omitted. **M6 was then re-run**, and its row above is that
re-measurement, not the earlier one: `# pass 3 # fail 4` → **`# pass 2 # fail 5`**,
A-505 joining the four cases that already caught it. Every other row of §S7a
was measured against the case file as it now stands and is unchanged.

That is the second cited objection this spec took from the same reviewer and
the second time the correct response was to move rather than to argue; the
first is recorded in §S5a. Both are the review requirement working, and both
are recorded here rather than in a commit message nobody re-reads.

**M4 is reported as a negative result rather than repaired, and it is a finding
about the worker.** No single-clause mutation of `!email` is observable,
because `''.includes('@')` is already `false` — so `!email.includes('@')`
subsumes `!email` entirely. **The `!email` clause in `durable.ts:848` is
redundant.** That is a fact about the code, not a weakness in the case: writing
a case that could only go red on M4 would require an input where the two
clauses disagree, and there is none. It is recorded here, it is harmless, and
it is not repaired — because this spec changes no worker code (§S4), and a
redundant clause on an auth guard is exactly the sort of thing to leave alone
until someone is deliberately editing that line.

## S8 · What is deliberately not built

**Item 2's other three strands, named so the register is not left to guess:**

- **The Playwright suite still drives `backend/`.** `frontend/playwright.config.ts:58`–`:63`
  still boots `alembic upgrade head` and `uvicorn app.main:app` from
  `backendDir` — re-confirmed at `f0d1912`, **not touched**, per the packet's
  boundary. Item 2 calls it *"the single largest thing in this entry"*.
- **The five modules covered by nothing** — `worker.ts` (beyond A-415),
  `storage/r2.ts`, `mail.ts`, `feedback.ts`, `convert/graph.ts`. Untouched.
- **The uncovered interior of `durable.ts`** — envelope creation and copy,
  templates, admin, the file routes, `finalize`'s stamping branch. Untouched.

**And, in this slice specifically:**

- **No guard change.** §S4.
- **No signature verification of the `id_token`.** Not proposed, not designed,
  not costed. It is a larger change (JWKS fetch, key cache, clock skew) and its
  justification is the branch this suite has just measured, not this suite.
- **No `RISK_ZONES.yaml`.** Still absent — re-checked at `f0d1912`,
  `ls RISK_ZONES.yaml` → *No such file or directory*. Still `BACKLOG.md` item
  5. §S9 records what that cost this spec.
- **No deploy, and no seat here proposes a deployer or a date.** Q-012.
- **`roadmap/` and `STAGE.md` untouched.** §S6.

## S9 · Risk class — `ordinary`, argued rather than assumed

**This change adds a test file, renames a test file, and amends one frozen
test. `service/src/durable.ts` and every other runtime source file are
byte-identical to `f0d1912`. No byte reaches a user either way.**

CHARTER Part 4's question is *can this change hurt someone outside the
project?*, and its own table's `Ordinary` row reads **"docs, tests, library
code"**. That is a mapping, and it is the one this change lands on.

**The counter-reading is stated rather than skipped**, because this repository
has **no `RISK_ZONES.yaml`** and Part 4 says the classification *"defaults to
can hurt someone when unmapped or unclear"* — which is how spec/0008 §S9
classified `9659e69`. Two things separate this from that one, and a reviewer
should test both. **(a)** That change edited a runtime write path handling a
sender's own text; this one edits no runtime path at all, so Part 4's
inheritance rule — risk travels *along the handling path* — has nothing to
travel along. **(b)** Part 4's can-hurt procedure differs from the ordinary one
in exactly one respect: *"the **release** proceeds through the 7-day veto window
on a plain-language note"*. **There is no release.** Nothing user-visible
changed, so a release note would have to be manufactured to have something for
the window to govern, and the packet's exit criterion 5 says in terms: *"a
release note if and only if something a user could see changed. Nothing in this
packet should qualify — say so rather than manufacturing one."*

**So: `ordinary`, no release note, no 7-day window, and this seat is not
reclassifying any path** — Part 4 makes reclassification itself a can-hurt act,
and nothing here moves a path from can-hurt to ordinary. If a reviewer cites
the unmapped default against this reading, the remedy is one extra review, not
a note about a change no user can see. The absence of `RISK_ZONES.yaml` forcing
a third consecutive spec to argue Part 4 by hand is itself the argument for
`BACKLOG.md` item 5 and is handed up as such.

## S10 · Verification, and review

**Before, at `f0d1912`, root `npm test`, run three times, identical:**
`Test Files 6 passed (6)` · `Tests 85 passed (85)` · `# pass 31` · `# fail 0` ·
`assert-service-suite-ran: 31 passing, 0 failing, from 6 compiled file(s) for 6
source file(s)`.

**After, run three consecutive times, identical:**
`Test Files 6 passed (6)` · `Tests 86 passed (86)` · `# pass 38` · `# fail 0` ·
`assert-service-suite-ran: 38 passing, 0 failing, from 7 compiled file(s) for 7
source file(s)`.

**+7 service assertions across a seventh file** (A-500 – A-506), **+1 frontend
assertion** (A-109's new count floor), **+1 source file**; the rename is
count-neutral. Every figure above was measured by this seat on this tree, not
inherited: the seventh reorder's `31 / 6` at `c23c7e6` was independently
re-measured here at `f0d1912` before anything was written, and matched.

**One thing the first post-change run caught, recorded because it is the guard
doing its job.** The run reported `service/dist/test holds 8 compiled test
file(s)` for 7 sources and **failed** — `tsc` does not remove stale output, so
the renamed file's old `dist/e2e-workflow.test.js` was still there and still
being run. `.github/scripts/assert-service-suite-ran.sh`'s count comparison
caught it immediately. CI is unaffected (a fresh checkout has no `dist/`), but
**a local run after any test-file rename needs `rm -rf service/dist` first**,
and the guard tells you so. That the guard is load-bearing rather than
decorative is now a measured fact and not only A-104's claim.

### S10a · Review

CHARTER §3, and `roadmap/STAGE.md` is `alpha`, so **Part 0 makes review
advisory rather than blocking** — it is run in full regardless, and its
transcripts are committed including any that object. Reviewers are chosen by
`tools/review.sh`; the builder is `claude` and no reviewer may share that
family (requirement 3).

**Requirement 1's breadth rule, and Q-030 rider (b), bind together here and
are honoured as one:** the spec review of this document — which contains the
A-109 amendment (§S5a) — and the code review of the diff **must come from
different families, neither of them the builder's**. That is requirement 1's
own rule, and it is also exactly rider (b)'s condition, which exists so that
the amendment remedy cannot become a way for one family to bless both a changed
standard and the code meeting it.

---

## S11 · The amendment to spec/0002, restated where that spec keeps its log

Recorded as **amendment 2** in [`spec/0002/SPEC.md`](../0002/SPEC.md)'s
*Amendment log*, in the open, before the implementation commit — the ordering
spec/0002's own amendment 1 established and gave its reasons for. §S5a here is
the argument; that log entry is the record in the file the frozen case belongs
to. Neither restates the other's content; both point at this section.
