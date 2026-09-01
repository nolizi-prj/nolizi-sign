# VALUE — who this is for, and why they would choose it

**Owned by the product-manager role** ([`pumasi-ops/roles/product-manager.md`](https://github.com/pumasi-ai/pumasi-ops/blob/main/roles/product-manager.md), duty 2).
First pass 2026-08-31, written against `main` @ `5cb3bf8` and the live host.

**Every claim here carries what would falsify it.** A claim without a falsifier
is marketing; this file is evidence. Kept current with releases — a value
proposition that lags the product is the drift this project keeps paying for
([L-007](https://github.com/pumasi-ai/governance/blob/main/lessons/L-007-restating-a-rule-forks-it.md)).

**Two things a reader must know before the claims.**

1. **The stage is [`alpha`](STAGE.md)**, not `beta`. *Updated 2026-09-01
   (sixth evaluation):* this line used to add *"whatever the chip on the
   landing page says"*, because the page carried a `BETA` chip. **It no longer
   does, and the page is now live**: the served landing chunk derives its badge
   from `STAGE.md` and renders `ALPHA — ACTIVE DEVELOPMENT`. Nothing below is a
   promise to a stranger yet.
2. **Claims are grounded in the tree that serves users** — the Cloudflare
   Worker in `service/`, which is what `sign.pumasi.ai` runs. The FastAPI app
   in `backend/` implements the same product and is not in production; which
   one *is* Pumasi Sign is open as `pumasi/DECISIONS.md` **Q-018**. Where a
   claim is grounded only in `backend/`, it is not made here.

Competitor facts come from [`MARKET.md`](MARKET.md), cited and dated. No
competitor number appears in this file that is not in that one.

---

## 1 · Who it is for

**The team that sends the same three documents over and over.** Offer letters,
NDAs, contractor agreements, consent forms. They already know exactly what a
signature workflow looks like — they are not shopping for a category, they are
tired of paying per seat for one. Template creation, reusable field placement
and a per-envelope status list are the whole of what they need.

**The sender who hit the envelope ceiling.** DocuSign's two mainstream business
plans state a limit of 100 envelopes per user per year at $30 and $45 per user
per month ([`MARKET.md` §1](MARKET.md)). The person this product is for is the
one who found that out in month eleven. Here there is no meter: the deployed
service contains no quota, plan, billing or subscription code at all — a `grep`
over `service/src` for `quota|plan|billing|stripe|subscription` returns nothing
but rate-limiting.

**The organisation that wants its own name on the envelope without an upgrade.**
Company name, logo and primary colour are per-owner rows in the deployed
service (`service/src/durable.ts`, the `org_branding` table at `:166` and the
signer-facing read at `:890`), applied to what recipients see, at no tier —
because there are no tiers.

**The external signer, who did not choose any of this.** They get a link and an
emailed code, sign in a browser, and never make an account
(`durable.ts:1456` — `SELECT … FROM submitters WHERE token = ?`; the access
token *is* the identity). This is the largest population the product touches
and the one that never reads a pricing page.

**Not yet: the operator who wants to run it themselves.** The repository is
public but carries **no `LICENSE`** (`gh repo view --json licenseInfo` →
`null`, re-measured 2026-09-01 at `2471a29`). Until that is resolved —
`pumasi/DECISIONS.md` **Q-021** — a self-hoster has no grant of rights, and
this file does not name them as an audience. See §4.

***Updated 2026-09-01 (sixth evaluation):*** **the product's own landing page
now tells this audience the opposite**, in three separate places, and it has
done so publicly since 01:02 UTC. This paragraph is the register and is
unchanged; the page is wrong; **Q-021** owns the divergence. A self-hoster
reading `sign.pumasi.ai` today would be relying on a grant this repository does
not make.

**Contested, and named rather than papered over.** `README.md` describes an
internal tool for Pumasi employees; the landing page sells public self-serve
signup; the live worker's `establishSession` (`durable.ts:727`) creates an
account for any verified email address, with no domain gate. Three different
answers to *who may hold an account*, in one product. That is Q-018's second
half, and no claim below depends on which way it lands.

## 2 · The pain

E-signature is bought once and then paid for forever, by the seat, with the
ceiling written where nobody reads it. The features that make it usable for a
team — your logo on the envelope, more than a handful of sends — are the ones
held one tier up. And the cost is not only money: the artifact everyone
downstream actually relies on is *the signed PDF and its certificate*, and that
artifact is produced by a vendor whose code the signer cannot read.

## 3 · The claims, and what would falsify each

**C1 — A signed document comes back with a cryptographic record of what was
signed, on every envelope, at no tier.** `stampAndCertifyPdf`
(`service/src/core/stamping.ts`) hashes the original bytes with SHA-256 before
stamping (`:52`), draws the digest onto an appended certificate page (`:199`),
and hashes the completed output (`:278`). It runs on the completion path
(`durable.ts:1735`), not behind a flag.
*Falsified by:* one completed envelope whose stored PDF has no certificate
page; one certificate whose printed digest does not match `sha256sum` of the
file it claims to describe; any tier or setting that turns it off.

**C2 — No meter, no seat, no upgrade path.** See §1. There is nothing in the
deployed service to bill with.
*Falsified by:* any envelope, template, branding or recipient count that
refuses work on quantity; any code path that reads a plan; a
commercialization decision that moves a feature named in this file behind
payment.

**C3 — A recipient signs without an account, from an email.** Token link plus
an emailed verification code; no login, no password, no signup for the person
who only has to sign.
*Falsified by:* an external recipient being asked to create an account, set a
password, or verify a domain in order to complete a signature.

**C4 — Your organisation's identity, not the vendor's, on what the recipient
sees.** Per-owner company name, logo and colour (§1), defaulting to
`Pumasi Sign` / `#1A56DB` when unset (`durable.ts:919`).
*Falsified by:* branding that a recipient never sees; branding gated on
anything.

**C5 — The whole thing runs on one edge service you could point at your own
account.** `service/` is a single Cloudflare Worker with a Durable Object store
and R2 for documents; `npm run deploy` is `wrangler deploy`. No Kubernetes, no
database server to operate.
*Today's honest limit, and it is the sharp one:* **there is no licence**, so
"you could" is an architectural statement, not a legal one. This claim is
**suspended** until Q-021 resolves and may not be used in public copy before
then.

***Updated 2026-09-01 (sixth evaluation), and the update is the reason this
suspension mattered.*** This file suspended C5 rather than write the claim, and
[`BACKLOG.md`](BACKLOG.md) **B1** held the page behind Q-021 for the same
reason. **The page deployed anyway, at 01:02 UTC on 2026-09-01, with the claim
in it** — three times, in three distinct sentences (`STAGE.md` §2.3.2). So the
position this file took is intact and the product's public surface no longer
matches it: **a Pumasi page is now making a claim this file refuses to make.**
That is not a reason to relax the suspension. It is recorded here, and as
evidence on Q-021, Q-028 and Q-012, because the next seat to write public copy
about this product will find the live page and this file disagreeing, and needs
to know which one is the register. **This one is.**
*Falsified by:* a deployment that needs a component not in this repository; a
resolved Q-021 that declines to license the code.

**C6 — What the incumbents do at the top of their price list, this does at the
bottom.** The comparison is `MARKET.md` §1 and only §1: unlimited envelopes
against a stated 100/user/year on DocuSign Standard and Business Pro; per-owner
branding against plans that do not list it; senders metered by SignWell's paid
tiers against no sender concept here.
*Falsified by:* any of `MARKET.md`'s cited rows changing on the vendors' own
pages without this file being updated — which is the failure mode this
project is built to notice.

## 4 · What this file does not claim, on purpose

- **Not "open source."** No licence (§1, C5) — `ls LICENSE*` returns nothing
  and `gh repo view --json licenseInfo` returns `null` on a `PUBLIC`
  repository, re-measured at `2471a29`. **This line is now in direct conflict
  with the product's own front page**, which says the opposite three times.
  The conflict is **Q-021**'s to resolve and no seat may resolve it by editing
  either side; see C5.
- **Not "beta," and not "reliable for strangers."** [`STAGE.md`](STAGE.md) §2
  lists **six** reasons. *Corrected 2026-08-31 (fourth evaluation):* this line
  said the largest was that the deployed tree carries **"two tests, both on the
  PDF stamper"**, and that stopped being true then. *Re-measured 2026-09-01
  (sixth evaluation):* the served tree's suite is **28 tests across five
  files**, three of which drive a real Durable Object and one of which drives
  `service/src/worker.ts`.
  *Re-run 2026-09-01 (fifth evaluation) at `56a8bf8` and unchanged*, over four
  runs: `# pass 21 · # fail 0`. `STAGE.md` §2.1 carries the measurement.
  What holds the label back is what that coverage went and found — two defects
  on the served tree — and **the fifth evaluation has to state their two
  different states separately, because one was repaired and the product did not
  change**:
  - The **envelope transitions** that let an executed agreement be voided,
    re-completed or declined after the fact were fixed on `main` at `68e5d08`
    and are **now live to every user** — *updated 2026-09-01 (sixth
    evaluation)*, the deployment at 01:02 UTC carried them. `STAGE.md` §2.6(i);
    `pumasi/DECISIONS.md` **Q-031**, window open to 2026-09-07.
  - The **`expires_at` a worker never acts on** is **fixed in source at
    `2471a29` and still true for every user**: the live worker's handler list
    is `fetch` alone, so no sweep runs. `STAGE.md` §2.6(ii);
    `pumasi/DECISIONS.md` **Q-035**, window open to 2026-09-07, and **Q-012**,
    which owns the deploy and is open.
  - **New at the sixth evaluation, and it is live in both trees:** the
    envelope-settings dialog **deletes the sender's message to signers** on
    every save. `BACKLOG.md` **item 1**; `STAGE.md` §5.

  Breadth is still missing (R2, mail, feedback, conversion, the OAuth
  callback), which is `BACKLOG.md` **item 2** — though **`2471a29` closed the
  sharpest strand**, covering `service/src/worker.ts` for the first time, and
  took the served tree's suite from 21 across four files to **28 across
  five**.
- **Not a QES / eIDAS-qualified signature.** The product produces an advanced
  electronic signature with a hash-based audit certificate; qualified
  signatures need hardware the product does not touch. (The landing page states
  this correctly today and should keep doing so.)
- **Not "your data is safe forever."** There is no stated retention or backup
  posture for the Durable Object store and R2 to cite. `STAGE.md` §2.4.
- **Nothing about a competitor that is not in `MARKET.md` with a source and a
  date.**

## 5 · How this file gets checked

At every product evaluation (role duty 4): does the release just shipped
deliver a claim above, and does any claim now have a live falsifier? A claim
that acquires one is *demoted in this file in the same commit that finds it* —
the same rule `STAGE.md` runs on.

**Sixth evaluation, 2026-09-01, against `main` @ `2471a29` — and, for the first
time in this file's life, against a deployment that had moved.**
Release checked: [`2026-09-01-pumasi-sign-expiration-dates-bind.md`](https://github.com/pumasi-ai/pumasi/blob/main/releases/2026-09-01-pumasi-sign-expiration-dates-bind.md)
(`pumasi/DECISIONS.md` **Q-035**, 7-day can-hurt window open, closes
2026-09-07). **Plus an unannounced deployment of `sign.pumasi.ai` at
2026-09-01 01:02 UTC, which no release note covers and which is the reason this
evaluation exists.**

- **Does the release deliver a claim above? No, and it is honest about which.**
  `2471a29` makes the worker honour a deadline the SPA already promised. That
  is not one of C1–C6; it repairs a promise the *interface* made that this file
  never wrote down, which is the good case for a value register — the claim was
  never made here because it was never true.
- **Does the deployment deliver one? Two, and both are C-adjacent rather than
  C-delivering.** The envelope guards behind **C1**'s integrity story reached
  users, and the cited-pricing table behind **C6** reached them cited. Neither
  is a new claim; both are the first time an existing one is *true in front of
  a stranger* rather than only in a repository.
- **Does any claim now have a live falsifier? One does, and it is C5.**
  C5's stated falsifier is *"a resolved Q-021 that declines to license the
  code"*. Q-021 is not resolved, so C5 is not falsified — **but its suspension
  has been overtaken by an act rather than by an answer.** This file suspended
  the claim; the product published it anyway, three times, on its own front
  page. **C5 stays suspended.** A page is not a register, and this file does
  not adopt a claim because a deployment made it.
- **And one new falsifier was found for nothing in particular, which is why it
  is here.** The settings dialog's silent deletion of the sender's message does
  not falsify C1 — the stamped PDF and its certificate are untouched — but it
  is the second time in three evaluations that *the row and the artefact
  disagree*, which is **L-009** at row scale for the second time. Two instances
  is a pattern, and the pattern belongs to `BACKLOG.md` item 2's breadth
  argument rather than to any claim above.
- **Citations re-taken, not carried.** Every `durable.ts` line number in this
  file had drifted — job `0064` found four of them wrong at `ba1cea7` while
  writing `README.md`, and `2471a29` moved them again. Re-measured at
  `2471a29`: `org_branding` at `:166`, the signer-facing branding read at
  `:890`, the branding default at `:919`, `establishSession` at `:727`, the
  token-is-identity `SELECT` at `:1456`, `stampAndCertifyPdf` at `:1735`. The
  numbers inside the historical evaluation entries below are **not** updated —
  they are records of what was cited then.

---

**Fifth evaluation, 2026-09-01, against `main` @ `56a8bf8`.**
Release checked: [`2026-08-31-pumasi-sign-finished-envelopes-stay-finished.md`](https://github.com/pumasi-ai/pumasi/blob/main/releases/2026-08-31-pumasi-sign-finished-envelopes-stay-finished.md)
(`pumasi/DECISIONS.md` **Q-031**, 7-day can-hurt window open, closes
2026-09-07).

- **Does it deliver a claim above? No — it repairs the near miss the fourth
  evaluation wrote down, and that is the cleanest possible illustration of why
  C1 was right not to be demoted.** `68e5d08` guards `cancel`, `complete` and
  `decline` against terminal statuses. The claim it protects is not C1: it is
  the *record around* C1's artifact — the Durable Object row and the audit log
  no longer come to contradict a certificate that says `completed`. **C1 stood
  as written before the fix and stands as written after it**, which is what the
  fourth evaluation predicted in the paragraph above.
- **Does any claim acquire a live falsifier? No.** C1–C6 re-read against
  `56a8bf8`; nothing in either merged commit touches the stamping path, the
  absence of a meter, branding, or `MARKET.md`'s cited rows. C5 remains
  **suspended** under Q-021, unchanged.
- **What the fourth evaluation got wrong about the defect, corrected here
  because this file cited it.** The paragraph above cites `durable.ts:1240` and
  `:1490` for `cancel` and `decline`. Those are the **pre-fix** line numbers
  and no longer locate anything; the guards are now at `:1252`, `:1452` and
  `:1513`, one predicate `isTerminal` at `:109`, verified in the tree at
  `56a8bf8`. Separately, `BACKLOG.md` item 1 had described the `complete`
  omission as *"mostly the wrong refusal code rather than a wrong write"* —
  **false**, disproved by a CC recipient reaching `finalize()` twice
  (`spec/0006/SPEC.md` §S1a; frozen case **A-406**). Neither error was in this
  file's *claims*; both are recorded because this file relied on the register
  that carried them.
- **And the repair does not move anything this file says about maturity.** It
  is **merged, not shipped** — re-`curl`ed 2026-09-01 00:29 UTC, the deployed
  bundle is unchanged and the three transitions behave the old way for every
  user of `sign.pumasi.ai`. It also **widened no coverage**: `# pass 21`,
  identical either side, over four runs. §4 above states both.

---

**Fourth evaluation, 2026-08-31, against `main` @ `f7c8d03`.**
**No release note has been published since the last evaluation**, so duty 4's
release question has nothing to answer and this pass does not invent one. What
triggered it was duty 1 — two open unlabelled issues — plus two merged coder
deliveries (`spec/0004` at `3d01198`, `spec/0005` at `f7c8d03`) that changed
facts this file states.

- **Does either delivery deliver a claim above? No.** Both are test suites over
  the served tree. C1–C6 are about what the product *does*; a characterization
  test changes what is *known*, not what is promised. Saying so is the honest
  answer, and padding it into a claim would be the defect this file warns about
  two paragraphs down.
- **Does any claim acquire a live falsifier? No — and one near miss is worth
  writing down, because the next reader will reach for it.** `spec/0005` found
  that `cancel` and `decline` can flip a **completed** envelope to `cancelled`
  or `declined` with no status guard (`durable.ts:1240`, `:1490`). That looks
  like it should falsify **C1**, and it does not. C1's stated falsifiers are
  *a completed envelope whose stored PDF has no certificate page*, *a
  certificate whose printed digest does not match the file*, and *a tier or
  setting that turns it off*. A status overwrite touches the Durable Object row
  and the audit log; **the stamped PDF and its certificate in R2 are
  untouched**, and `stampAndCertifyPdf` still runs unconditionally on the
  completion path. So C1 stands as written. What the defect damages is the
  *record around* the artifact — the row and the audit trail come to contradict
  the certificate — which `STAGE.md` §2.6 carries and `BACKLOG.md` item 1
  fixes. **C1 is not weakened here and it is not quietly widened either.**
- **One claim this file still does not make, and this evaluation is the second
  to note it.** Nothing in C1–C6 promises that a deadline a sender sets is
  honoured, which is why `BACKLOG.md` item 2 — the SPA telling senders
  *"Without an expiration date, the envelope stays open until completed or
  voided."* while the worker has no scheduled handler at all — falsifies no
  claim here while being a real broken promise. That is the same coverage gap
  the third evaluation found with #7 and the sign-in path: **this file's claims
  are about what the product does once you are inside it, and the promises it
  makes *around* the signing act are unclaimed.** Left as a standing
  observation for whoever next writes a claim, rather than a claim invented to
  fit a defect already found.

---

**Third evaluation, 2026-08-31, against `main` @ `d18d534` and the live host.**
Release checked: [`2026-08-31-pumasi-sign-sign-in-again.md`](https://github.com/pumasi-ai/pumasi/blob/main/releases/2026-08-31-pumasi-sign-sign-in-again.md)
(`pumasi/DECISIONS.md` **Q-027**, 7-day window open).

- **Does it deliver a claim above? No, and that is worth stating rather than
  padding.** The release repairs the *entry path* — a signed-out user's way
  back in — and fixes what the merge gate measures. No claim C1–C6 is about
  either. C3 is the nearest and is not touched: it is about an **external
  recipient** signing from an email without an account, and #7 was on the
  internal sign-in button.
- **Does any claim acquire a live falsifier? No.** C1, C2, C4 and C6 were
  re-read against `d18d534` and nothing in that commit touches the stamping
  path, the absence of a meter, branding, or `MARKET.md`'s cited rows. C5
  remains **suspended** under Q-021, unchanged.
- **One thing this evaluation notes for the next one.** Nothing in this file
  promises that a user can get back into the product, which is why a live
  `404` on the sign-in button falsified no claim here for two evaluations while
  being the most serious thing on `STAGE.md`. That is a gap in this file's
  coverage, not a reason to relax: the honest response is that C1–C6 are about
  *what the product does when you are in it*, and the way in is assumed. Left
  as an observation for whoever next writes a claim, rather than inventing one
  to fit a release that has already shipped.
