# BACKLOG — what gets built next, in order

**Owned by the product-manager role** ([`pumasi-ops/roles/product-manager.md`](https://github.com/pumasi-ai/pumasi-ops/blob/main/roles/product-manager.md), duty 5).
First pass 2026-08-30, steward-directed: *"introduce very similar UI and UX
[to the incumbent] in pumasi sign — let these items in the queue."*
**Reordered 2026-09-01 (sixth reorder)** after the product evaluation that
re-measured this file against `main` @ `2471a29` **and against the deployed
build**; the reasoning is in that commit's message, and the steward vetoes by
reverting.
**Reordered again 2026-09-01 (seventh reorder)** at `c23c7e6`, a narrow pass
triggered by one published release note; what it re-measured and what it
carried is the next section, and the reasoning is in that commit's message.
**Reordered again 2026-09-01 (eighth reorder)** at `efed763`, triggered by a
merge no file here had a record of — coder job `0080` landed four commits and
the dispatcher then recorded the job `FAILED: timed out after 5400s`. **The
work is in `main`; only the wrap-up died**, and this reorder is the wrap-up.
What it re-measured and what it carried is the next section.

One list, features and bugs together, because a priority that cannot compare
them is not a priority. Every entry points at its source and carries one line
of why-here. **The top of this file is what the project manager's next coder
packet builds** — except where an entry says in its own text that it is
**operator action** rather than a build, as **item 1 does from this reorder
onward**; the packet then takes the highest entry that *is* a build, and the
operator item keeps its rank rather than being demoted for being unbuildable.
That exception is `pumasi-booking`'s, adopted here at `2453adc`'s shape,
because this repository has now acquired the same problem: merged repairs that
no commit can deliver.

## What the eighth reorder changed, and what it did not measure

**One entry moved, three sentences in this file were false and are struck, and
the residual strands of the top build entry are ranked for the first time.
That is stated first so nothing below is over-read.**

**Labels, and there is no unlabelled entry.** Anything marked **re-verified at
`efed763`** was re-run or re-read by this pass at this tree or against the live
host, with the UTC time given. **Every entry, sentence and figure in this file
that is not so marked is `carried, not confirmed` from the seventh reorder at
`c23c7e6`** — which is itself blanket-carried from the sixth at `2471a29` for
everything the seventh did not touch. This pass did not re-read items 3, 4, 5,
7 or 8–18, or B1, and does not pretend to have. The blanket form is used rather
than seventeen copies of the same sentence, and it means exactly what the
per-entry form means.

**Why this pass exists at all, and it is not a routine tick.** `roadmap/`
described a tree that does not exist. Job `0080` merged `af617e1` → `efed763`,
pushed, `GATE: PASS`, and its return block says in as many words *"FOR YOUR
STRIKE — I deliberately did not edit `roadmap/`"* — correctly, because ranking
is this seat's. The dispatcher then killed the job on a 5400 s timeout **after**
the push. **A job recorded `FAILED` is not evidence that the build failed**;
this pass judged it on the tree and the tree is where the work is.

**What moved.**

- **Item 2's misnomer strand is struck as BUILT at `07e0188`**, not claimed as
  delivered — nothing in it reaches a user. `e2e-workflow.test.ts` no longer
  exists; it is `stamping-multi-signer.test.ts`.
- **Item 2's named first slice — the OAuth callback — is struck as BUILT at
  `07e0188`.** `service/src/test/oauth-callback.test.ts`, frozen cases
  **A-500**–**A-506**, both provider legs, through the real Durable Object.
- **Item 2 stays at rank 2 and stays the top *build* entry.** It did not become
  less urgent and nothing above it was built: **item 1 is still operator action
  and still four repairs deep.** What changed inside it is that its **three
  residual strands are now ranked against each other, with reasons** — the
  packet after this one should be able to read which strand it takes without
  opening a log. They were an unordered list before.
- **A fourth residual — the `email_verified` guard — is given a ranked home
  inside item 2 rather than promoted out of it**, because the evidence that
  `spec/0009` §S3 names as what *would* promote it has not been gathered. See
  the entry.
- **Item 6's figure is corrected from five files to seven** and its routing is
  made specific: the next coder packet taking item 2 folds it in.
- **Nothing else changed rank, and no entry was renumbered.** Items 1–18 and B1
  keep their numbers for the reason the seventh reorder gave and this pass
  re-affirms: `STAGE.md`, `pumasi/DECISIONS.md` **Q-037** and `pumasi-web` all
  cite entries here by number, and two of those three are not this seat's to
  edit in the same commit.

**Re-verified at `efed763` by this pass, with the numbers it actually ran.**

- **The suite, re-run rather than read off the coder's commit message.** Root
  `npm test` **×3**, byte-identical every run: `Test Files 6 passed (6)`,
  `Tests 86 passed (86)`, `# pass 38`, `# fail 0`,
  `assert-service-suite-ran: 38 passing, 0 failing, from 7 compiled`. Run by
  this seat **2026-09-01 06:02–06:09 UTC**. `service/` `npm test` alone a
  further **×3**, `# pass 38 # fail 0` each time. **31 across six files → 38
  across seven.** The coder's self-report is confirmed, not carried. **Three
  runs is not forty** and no determinism claim is made from it —
  [`STAGE.md`](STAGE.md) §0 rider (b) records that as a gap again.
- **The suite's contents, read by import rather than by grep.** `ls
  service/src/test/` returns **seven** files — `auth-session`,
  `envelope-correction`, `envelope-expiry`, `envelope-lifecycle`,
  `oauth-callback`, `stamping-multi-signer`, `stamping` — and the *complete*
  set of non-`node:` module imports across all seven plus the harness is
  `../worker.js`, `../core/stamping.js` and `../../durable.js`. **This is why
  the method matters:** `grep -rl mail service/src/test/` hits all seven files,
  because `email` contains `mail`, and would have reported `mail.ts` covered.
  It is not. Neither is `storage/r2.ts`, `feedback.ts` or `convert/graph.ts`.
- **`service/src/durable.ts` is byte-identical to `f0d1912`** — `git diff
  f0d1912 -- service/src/durable.ts` is empty, checked here. **No worker code
  changed in this merge**, which is why no release note was owed, why nothing
  user-visible moved, and why **item 1's count is still four and not five**.
- **The guard, re-read at its current line.** `service/src/durable.ts:848` is
  `if (!email || !email.includes('@') || claims.email_verified === false)`.
  Both of `0080`'s findings about it are on that one line.
- **The Playwright suite, re-read.** `frontend/playwright.config.ts:58`–`:66`
  still boots `alembic upgrade head` and `uvicorn app.main:app` with
  `cwd: backendDir`. Unchanged. It still drives `backend/`.
- **The live host, and it has not moved.** `https://sign.pumasi.ai/` → **200**
  at **2026-09-01 06:08:55 UTC**, serving `/assets/index-CnoFAC2c.js` — the
  same bundle filename the sixth *and* seventh passes measured. **Nothing has
  been deployed since 01:02 UTC on 2026-09-01.** `/api/version` → **404**
  (item 4, unchanged, and PR-1's user-visible clause still unmet).
- **Triage (duty 1), measured rather than manufactured.** `gh issue list
  --state open` returns **one** issue, **#15**, already carrying `bug` ·
  `feedback` · `rejected`. **There are no unlabelled open issues**, so duty 1
  is a no-op this pass and is recorded as one.
- **`PRODUCT-RULES.md`, read fresh this packet and reported rather than
  assumed.** Still **not on `pumasi` main** — checked at `pumasi` @ `196b749`:
  `ls PRODUCT-RULES.md` → *No such file or directory*, and it exists on one
  commit, `0115758`, on the unmerged branch `worktree-product-rules`. That is
  **Q-017**, open, now flagged by **ten** consecutive evaluations, and
  **absence from main is not compliance**. Read from that branch this pass:
  v1.0, PR-1 and PR-2 unchanged from the last reading. Both gaps stay ranked,
  at items 4 and 3.

**One correction to another seat's reading, re-measured rather than inherited —
and it is small, which is the point of recording it.** Job `0080`'s return
block states that *"`grep -rin oauth service/src/test/` returned nothing at
`f0d1912` — this branch had never been executed"*. **The grep returns one hit**
(`auth-session.test.ts:204`, a comment about the OAuth path's 120-character
name cap). **The conclusion it was offered for is nonetheless correct**, on a
sharper measurement taken here:
`git grep -in 'auth/oauth\|email_verified\|id_token' f0d1912 -- service/src/test/`
returns **nothing**, so no assertion reached the route, the guard or the token.
Recorded because the sixth reorder counted **four stale citations in four
days** in this repository and corrected them one by one; this is another
instance of the same practice, and the practice is the finding, not the seat.
No count of a streak is claimed here, because this pass did not go back and
count one.

**Routed, ranked or declined in writing — the three things job `0080` handed up
and did not act on.** Each gets a disposition here rather than a mention.

1. **`durable.ts:848`'s `!email` clause is dead code** — fully subsumed by
   `!email.includes('@')`; `''.includes('@')` is already `false`, so no single
   mutation of it is observable (`0080`'s M4: `# pass 7 # fail 0`).
   **Disposition: folded, not ranked.** It gets **no entry of its own** —
   `0080` proposed exactly that and it is right. It is folded into **item 2's
   guard strand**, because the dead clause and the loose `email_verified`
   comparison are **on the same line of the same file**, and one packet editing
   `:848` should close both or neither.
2. **`npm run build` leaves stale `dist/` output**, so a local run after any
   test-file rename fails the L-006 guard until `rm -rf service/dist`; CI is
   unaffected because it builds from a fresh checkout. **Disposition:
   declined as an entry, recorded as a reproduction step.** `0080` calls it
   *"A-104 proving load-bearing — a papercut, not a hole"* and this seat
   agrees: the guard did exactly what `spec/0002` froze it to do, loudly and
   correctly, and a backlog entry for a guard working is a defect in the
   backlog. It is written into [`STAGE.md`](STAGE.md) §0 rider (b) beside the
   command, where the next seat reproducing the figures will meet it, and this
   pass hit it and cleared it that way. **Re-verified at `efed763`**: this seat
   built from a removed `dist/`.
3. **Review breadth is one family, not five of six.** `0080` measured across
   seven review invocations that **qwen times out at curl's 600 s ceiling on a
   150 KB code review** while returning correct, cited objections on 31–35 KB
   spec rounds, and that **grok is unreachable fleet-wide (HTTP 402)**. With
   gemini and kimi spent on the spec, **glm was the only family that could
   review that code**. **Disposition: handed up, not acted on, and not this
   repository's to fix.** It is **D-104**'s subject and `pumasi-ops`'; no
   `review.sh` change is proposed here and none is this seat's. It is recorded
   in [`STAGE.md`](STAGE.md)'s change log because §3's `beta` argument leans on
   review breadth, and a reader weighing that argument is entitled to know the
   breadth was one. **Carried, not confirmed** — this seat did not re-invoke
   any reviewer.

**What this pass did not do**, so that its silence is not read as a finding: it
did not re-run `backend/` pytest or the Playwright `e2e` suite (neither can run
on this machine — [`STAGE.md`](STAGE.md) §0 rider (b)), did not re-check CI or
branch protection, did not re-read `pumasi/catalog.json`, did not re-run
`wrangler deployments list`, did not re-invoke any review family, and
**answered, closed, softened, dated or moved the default of no `DECISIONS.md`
question**. It **proposed no deployer, no date and no rollback** — item 1 is
**Q-012**, which is open and explicitly outside CHARTER Part 0's
proceed-on-default rule. It **wrote no worker code, no test and no spec**, and
it did **not** edit `CLAUDE.md`, which is not in this role's may-write list —
that is recorded as the reason under item 6, not left as an oversight.

**And it wrote no `pumasi-ops` `DIGEST.md` entry, which duty 4 would otherwise
ask for.** The reason is a measurement, not a preference: at the time of this
pass the `pumasi-ops` working tree was **dirty with a live dispatcher tick** —
two job files staged for deletion and six review transcripts untracked, `HEAD`
at `255d797` (*"tick 05:58–06:20 UTC"*) — so another writer holds that
checkout, and the role file forbids acting while one does. **This pass's
evaluation record is therefore the [`STAGE.md`](STAGE.md) change-log row and
this commit's message**, which is where the steward vetoes by reverting. It
also wrote nothing in `pumasi`: job `0080` already added the Q-030 evidence row
at `196b749` and this pass added no second copy of it.

## What the seventh reorder changed, and what it did not measure

**One thing was delivered, one thing was found in this file's neighbour, and
nothing else was re-measured. That is stated first so nothing below is
over-read.**

**Labels, and there is no unlabelled entry.** Anything marked **re-verified at
`c23c7e6`** was re-run or re-read by this pass at this tree or against the live
host, with the UTC time given. **Every entry, sentence and figure in this file
that is not so marked is `carried, not confirmed` from the sixth reorder at
`2471a29`** — this pass did not re-read items 2, 3, 4, 6, 7 or 8–18, and does
not pretend to have. The blanket form is used rather than seventeen copies of
the same sentence, and it means exactly what the per-entry form means.

**What moved.**

- **Item 1 — the settings dialog deleting the sender's message — is struck as
  BUILT at `9659e69`** and retired below, **not** claimed as delivered. Coder
  job `0074` was barred from touching rankings and correctly left the strike to
  this seat; its own return block says so.
- **A new item 1 exists and it is not a build.** The undeployed set reached
  four repairs at `9659e69` and had no ranked home in this file — it was parked
  inside a *Retired* entry, where a reader looking for what is owed to users
  would not look. It now has one. **It proposes no deployer, no date and no
  revert**; it is **Q-012**, which is open and explicitly outside CHARTER
  Part 0's proceed-on-default rule.
- **The new top *build* entry is item 2 — test the deployed tree beyond its
  stamper.** It is the entry the project manager's next coder packet takes.
  **That is a delivery above it, not a promotion of it**: item 2 did not become
  more urgent, the thing outranking it was built.
- **Item 5 (`RISK_ZONES.yaml`) was weighed for promotion and stays at 5**, with
  the new evidence and the reason recorded in its own entry rather than
  inherited.
- **Nothing else changed rank, and no entry was renumbered.** Items 2–18 and B1
  keep their numbers deliberately: `STAGE.md`, `pumasi/DECISIONS.md` Q-037 and
  `pumasi-web` all cite entries here by number, two of those three are not this
  seat's to edit, and a renumber would manufacture stale citations in files
  that cannot be fixed in the same commit. This repository has spent four
  consecutive days correcting stale citations; it does not need three more.

**Re-verified at `c23c7e6` by this pass, with the numbers it actually ran.**

- **The repair itself, read in the tree rather than taken from the commit
  message.** `service/src/durable.ts:1326`–`:1328` now reads
  `body.message !== undefined ? (body.message != null ? String(body.message).slice(0, 2000) : null) : (sub.message ?? null)`,
  with `title`'s `?? sub.title` unchanged on the line above. An omitted
  `message` is kept; an explicit `null` still clears it. Three frozen cases
  **A-417–A-419** in the new `service/src/test/envelope-correction.test.ts`
  drive it.
- **Root `npm test` at `c23c7e6` — 40 consecutive runs, 40 pass, 0 fail**,
  identical counts on every run: `Test Files 6 passed (6)`,
  `Tests 85 passed (85)`, `# pass 31`, `# fail 0`,
  `assert-service-suite-ran: 31 passing, 0 failing, from 6 compiled`. Run by
  this seat between **03:25:00 and 03:36:03 UTC**. Job `0074` measured `28 → 31` from
  two runs before and two after; **this is 40 runs of the after state**, and it
  is the first time in three evaluations that `STAGE.md` §0 rider (b)'s ask for
  40 has been met rather than declined. The three added assertions are exactly
  A-417–A-419.
- **The live host, and it has not moved.** `https://sign.pumasi.ai/` → **200**
  at **03:25:05 UTC**; the served bundle is still `/assets/index-CnoFAC2c.js`,
  the same filename the sixth evaluation measured, so **nothing has been
  deployed since 01:02 UTC on 2026-09-01** and none of the four merged repairs
  has reached anybody. `/api/version` → **404** (item 4, unchanged).
- **B1's facts, re-measured at 03:27 UTC** rather than carried: `ls LICENSE*` →
  *No such file or directory*;
  `gh repo view --json licenseInfo,visibility` → `{"licenseInfo":null,"visibility":"PUBLIC"}`;
  the served `LandingView-C5khdw3s.js` is **10 046 bytes** and still contains
  **three** `Apache-2.0` claims. **B1 is unchanged, still `Blocked`, still
  ranked, and no seat here touched it.**
- **Triage (duty 1), measured rather than manufactured.** `gh issue list
  --state open` on `pumasi-ai/pumasi-sign` returns **one** issue, **#15**,
  already carrying `bug` · `feedback` · `rejected`. **There are no unlabelled
  open issues**, so duty 1 is a no-op this pass and is recorded as one.

**What this pass did not do**, so that its silence is not read as a finding: it
did not re-run `backend/` pytest or the Playwright `e2e` suite (neither can run
on this machine — `STAGE.md` §0 rider (b)), did not re-check CI, did not
re-check branch protection, did not re-read `pumasi/catalog.json` or
`PRODUCT-RULES.md` for their own sake, and answered, closed, softened or dated
**no** `DECISIONS.md` question. `PRODUCT-RULES.md` was read for this packet and
is reported rather than assumed: **still not on `pumasi` main** — `ls
PRODUCT-RULES.md` at `pumasi` @ `3ad9b1c` → *No such file or directory*, which
is **Q-017**, open, and now flagged by **nine** consecutive evaluations.
PR-1 and PR-2 are unchanged and stay at items 4 and 3.

## Why the sixth reorder existed

**Something deployed, and it emptied more of this file than any merge ever
has.** Between 00:46 and 01:02 UTC on 2026-09-01, `sign.pumasi.ai` was deployed
four times (`pumasi-ops/DIGEST.md`, and [`STAGE.md`](STAGE.md) §2.2 for the
dating). **Both `Blocked` entries, two numbered items and four issues went with
it.** No release note, no digest entry, no `DECISIONS.md` line — this file's
previous reorder had them all recorded as waiting on **Q-012**, and none of
them was waiting any more.

**And the same deploy created the worst thing in this file.** B1 had two halves
left: **(b)** make the landing page's licence claim true, and **(d)** deploy
it. **(d) ran. (b) did not.** So *"Apache-2.0 (Open Source)"* is now served to
the public from a repository with `licenseInfo: null` and no `LICENSE` file.
That is **Q-021**, whose own premise was *"not yet public"*, and no seat here
may answer it in either direction. B1 stays `Blocked` and is now **one half
wide and strictly worse than when it was two**.

### What moved

- **Old item 1 (`expires_at`) → Retired as built**, at `2471a29`, **and
  explicitly not claimed as delivered** — the live worker's handler list is
  `fetch` alone, so every deadline on `sign.pumasi.ai` still does nothing.
- **Old item 3 (#6, #10, #11) → Retired**, delivered at `bbde48f` and
  `1d2743f`; all three issues closed. **Its residue is new item 7**, because
  two of the three were fixed only on the surface that was reported.
- **Old item 6 (settings shell) → Retired in the half a user can see**;
  issue #5 is closed by the Settings menu `bbde48f` added. The route/shell
  residue joins new item 7.
- **B2 → Retired.** #7's fix is live and this evaluation verified it on the
  served bundle rather than on the tracker.
- **B1 → still Blocked, reduced to (b), and escalated in the digest.**
- **New item 1 — the settings dialog deletes the sender's message.** Found by
  coder job `0065` and handed up rather than folded in; **verified here against
  the deployed artefact, not only the source.** It is the only live data-loss
  defect this product has ever had ranked.
- **New item 6** — three sentences in `CLAUDE.md` that are now false.
- **Old items 2, 4, 5, 7 → 2, 3, 4, 5.** Substance unchanged except where
  re-verification moved a fact.
- **Old items 8–18 keep their numbers.** The parity mandate still resumes at
  item 8.

### Re-verification, and what was measured against what

`2471a29` rewrote parts of `service/src/durable.ts` and a deploy changed what
users meet, so **both** kinds of citation in this file were suspect. Two
distinct measurements were taken and they are not interchangeable:

- **Against the tree at `2471a29`** — item 2's `e2e-workflow.test.ts` imports,
  item 3's `FeedbackDialog.vue` capture, item 4's three `package.json` files,
  item 5's `ls RISK_ZONES.yaml`, item 6's `CLAUDE.md` sentences, item 7's
  router table and `gap-*` classes. **This line is the sixth reorder's dated
  record of what it measured and it is left exactly as written — Q-034.**
  `e2e-workflow.test.ts` existed at `2471a29` and its imports were read there;
  the file was renamed at `07e0188` and the *live* claims that rested on it are
  struck in item 2, not here. A record of what was true when written is a
  record, not an error.
- **Against the served build**, which is what settles anything about a user:
  the bundle (`/assets/index-CnoFAC2c.js`), the route table, the landing chunk,
  the `EnvelopeDetailView` chunk, the stylesheet, and
  `wrangler versions view`'s handler list. **A green suite here is not evidence
  about production** — Q-018's default part (c) — and at this reorder the two
  are one release apart.

Root `npm test` at `2471a29`, run twice by this evaluation on 2026-09-01 at
02:03 and 02:05 UTC, identical both times: `Test Files 6 passed (6)`,
`Tests 85 passed (85)`, `# pass 28`, `# fail 0`,
`assert-service-suite-ran: 28 passing, 0 failing, from 5 compiled`.

**`PRODUCT-RULES.md`, read fresh this packet and reported rather than assumed.**
Still **not on `pumasi` main** — checked at `pumasi` @ `cdc0b9a`:
`ls PRODUCT-RULES.md` → *No such file or directory*, and it exists on one
commit, `0115758`, on the unmerged branch `worktree-product-rules`. That is
**Q-017**, open, now flagged by **eight** consecutive evaluations, and
**absence from main is not compliance**. Read from that branch this pass: v1.0,
PR-1 (version numbers, binds always) and PR-2 (in-app feedback, binds at
`beta`) unchanged from the last reading. Both gaps stay ranked, now at items 4
and 3 respectively. **PR-1's user-visible clause acquired its first observed
cost on this product at this evaluation:** issue #15 arrived from the live
product carrying thirteen diagnostic fields and no version, and there is no way
for its reporter to have supplied one — `/api/version` answers `404` and no
version string occurs in the served bundle.

---

## The order

**1 · Deploy the reviewed build to `sign.pumasi.ai` — four merged repairs, and
not one of them has reached a user** · **operator action, not a build** —
source: `pumasi/DECISIONS.md` **Q-012** (open), **Q-028**'s own count, **Q-035**
and **Q-037**'s `Status` rows, [`STAGE.md`](STAGE.md) §2.6(ii) and §5's state
(iii). **New in this reorder, and it is new as an *entry*, not as a fact** —
every one of these repairs was already recorded somewhere in this file. What
was missing was a single ranked place where a reader could see what the product
owes its users, so the set was living inside the *Retired* section, which is
where a reader looks for things that are **done**.

**No coder packet takes this entry.** It cannot be built. **The next coder
packet takes item 2**, which is the highest entry on this list that a commit
can close. This entry keeps rank 1 rather than being demoted for being
unbuildable, because its rank is a statement about what users are owed and not
a statement about what is schedulable.

**What is behind it, counted at `c23c7e6` and named one by one.** Each is
merged, gate-passed, reviewed and released; each is invisible to every person
using the product.

| Merged | What a user would get | Where it is recorded |
| :--- | :--- | :--- |
| `68e5d08` → **deployed 01:02 UTC** | finished envelopes stay finished | Q-031 — **delivered**, listed only so the count below is not misread |
| `2471a29` | the expiration date the app asks for is one the service keeps | **Q-035**, window closes 2026-09-07; [`STAGE.md`](STAGE.md) §2.6(ii) |
| `9659e69` | the settings dialog stops deleting the sender's message | **Q-037**, window closes 2026-09-08; retired below |
| the login-page presentation batch and #8's landing page | — | already delivered by the 01:02 UTC deploy |

**The number Q-037 uses is four and this seat did not re-derive it.** Q-028
counted three repairs waiting in the undeployed bundle; the release note of
`9659e69` says *"this is the fourth"*. **Carried, not confirmed** — this pass
did not re-run `wrangler deployments list`, and says so rather than restating
someone else's count as its own measurement.

**Re-verified at `c23c7e6`, and it is the one thing here this pass did
measure.** `https://sign.pumasi.ai/` answered **200** at **2026-09-01 03:25:05
UTC** and serves `/assets/index-CnoFAC2c.js` — **the same bundle filename the
sixth evaluation measured at 01:57 UTC**. Nothing has been deployed since
01:02 UTC on 2026-09-01. So, right now, on the product: **a past-due envelope
is still signable, and the settings pencil still deletes the sender's message
to signers and still reports success.**

**What this entry does not do, stated in full because the temptation is
obvious.** It **proposes no deployer**, names no person, sets no date, asks for
no rollback and takes no position on **Q-021**. **Q-012 is open and is
explicitly outside CHARTER Part 0's proceed-on-default rule** — that rule
releases *reversible* work from an open window, and assigning a deploy duty is
a register change. Job `0071` spent a pass measuring four un-announced
`wrangler deploy` runs from a workstation and added the evidence to Q-028
without naming an actor; nothing here adds a fifth or names one either.

**And one thing this entry cannot fix, kept beside the work rather than in a
release note nobody will re-read.** The messages already deleted by the
settings dialog are **gone** — overwritten with `NULL`, no shadow copy. A
deploy stops the next one. It does not return the last one.

**Why this is item 1 and not item 6.** Because the alternative is a file whose
top says *build this next* while the product's most serious defects sit
finished on a shelf, and a register that cannot show that is the exact drift
this repository keeps paying for. **Its growth is the thing worth watching**:
one repair waiting was a delay, four is a pattern, and whether that pattern
warrants an escalation beyond recording it is **the steward's**, through
Q-012 — not this seat's, which is why this entry escalates nothing and only
counts.


**2 · Test the deployed tree beyond its stamper — the breadth that is left**
— source: coder job `0032`'s `SUGGESTED_NEXT_TASKS` (`priority: high`),
`pumasi/DECISIONS.md` **Q-018** and **Q-025**, [`STAGE.md`](STAGE.md) §2.1,
`CLAUDE.md` (*"test coverage here is thin and you should know it before you
trust it"*). **Was item 3, and item 1 before that. Not retired, and demoted
on delivery rather than silently — it has now been passed twice by defects its
own coverage found.**

**What its three named slices delivered, verified in the tree this pass.** The
entry proposed, in order: `establishSession`'s account rule, then session
validation, then envelope state transitions. **All three are in.**
`auth-session.test.ts` (A-300–A-308) constructs the real Durable Object —
*"whole schema, migrations, routing"* (A-300) — through
`test/support/durable-harness.ts`, and covers the Q-018 divergence as
**A-302**, *"establishSession admits a verified email at any domain — recorded,
not endorsed"*. That is the entry's own boundary honoured exactly:
**characterize, do not adjudicate.** `envelope-lifecycle.test.ts` (A-400–A-409)
covers the transitions and is what found the two defects that became items 1
and 2 of the fourth reorder — the first of which is delivered and retired below,
the second of which is now this file's item 1.

**So the two sharpest sentences this entry used to carry are now false and are
withdrawn**, rather than left to read as pending:

- ~~"both assertions are against one file"~~ — **seven** files now; **four** of
  them drive routes against a real Durable Object. **Re-verified at `efed763`,
  2026-09-01 06:05 UTC** (this bullet read *five* and *three* through the sixth
  and seventh reorders, measured at `2471a29`).
- ~~"`durable.ts` … covered by nothing"~~ — sessions and the envelope surface
  are covered.
- ~~"`worker.ts` is covered by nothing"~~ — **retired at `2471a29`**, which is
  the first assertion in this repository's history to drive the entrypoint.
  **A-415** reaches the single Durable Object through `scheduled()`, proves the
  throw is load-bearing, and proves the sweep's internal path is closed to the
  internet.

**The sentence that survived three reorders does not survive this one. Struck
as BUILT at `07e0188`, re-verified at `efed763` by the eighth reorder:**
~~`e2e-workflow.test.ts` is still not an end-to-end test of anything.~~ **The
file does not exist.** It was renamed to **`stamping-multi-signer.test.ts`**,
which is what it always was — a second stamper test. **Measured here rather than taken from the coder's log:** `git diff -M`
across `07e0188` reports the file **`-1 / +24`** — the single removal is the
old test title, and the additions are a header comment recording the rename
plus the new title. **No assertion, fixture or import moved.** `ls service/src/test/` at `efed763` returns seven files and the
old name is not among them. **The five-minute honesty fix this entry asked for
in three consecutive reorders was taken, in the packet that took this item,
exactly as this entry said it should be.** What the renamed file still *is* — a
shape-not-content stamper assertion — is unchanged and is recorded in
[`STAGE.md`](STAGE.md) §2.1, not here; it is not a strand of this entry.

**The named first slice is BUILT, at `07e0188`, and is struck rather than left
to read as pending.**

- ~~**Named first slice — the OAuth callback, which is where job `0050`'s
  proposal 5 lives.**~~ **Delivered.** `service/src/test/oauth-callback.test.ts`
  holds frozen cases **A-500**–**A-506** and drives **both** legs of
  `GET /api/auth/oauth/(google|microsoft)(/callback)?` through the real Durable
  Object via `test/support/durable-harness.ts`, with **only** the provider's
  token endpoint stubbed. **A-500 is the reader guard** — it proves the
  authorize leg really stores state, the callback really consumes it and the
  stub is really reached, so the five negative cases cannot be green on a
  request that never left the route. **One correction to the merging seat's own account, re-measured
  here rather than repeated:** job `0080`'s return block states that
  *"`grep -rin oauth service/src/test/` returned nothing at `f0d1912`"*. It
  returns **one** hit — `auth-session.test.ts:204`, a comment noting that the
  OAuth path caps a name at 120 characters where the code path under test does
  not. **The substance is unaffected and is what this entry cares about:**
  `git grep -in 'auth/oauth\|email_verified\|id_token' f0d1912 -- service/src/test/`
  returns **nothing at all**, so no assertion anywhere in the suite reached the
  route, the guard or the token, and the branch had genuinely never been
  executed. The claim was right; the measurement quoted for it was not, and
  this file does not carry another seat's grep as its own. **This entry forecast the shape of its own delivery and the
  forecast held** — it said *"the cheap next step is the covering test"*, and
  the covering test is what landed, with **no guard changed**.

**What is left. Ranked against each other for the first time, because an
unordered list of four is not a priority — the packet after this one should be
able to read which strand it takes without opening a log.** All four
re-verified at `efed763`, 2026-09-01 06:05 UTC.

- **Residual A — `durable.ts`'s uncovered interior. Take this one next.**
  Envelope creation and copy, templates, admin, every file route, and
  **`finalize`'s stamping branch**. Three reasons, in the order they carry
  weight. **(i)** It is the cheapest per assertion: the harness this entry's
  own three deliveries built (`test/support/durable-harness.ts`) already
  constructs the whole object — schema, migrations, routing — so a packet here
  writes assertions and not scaffolding. Every one of this entry's deliveries
  has confirmed that forecast, most recently `A-417`–`A-419`. **(ii)**
  `finalize`'s stamping branch is **the only uncovered path that produces the
  artefact [`VALUE.md`](VALUE.md) C1 promises** — the stamped PDF and its audit
  certificate. Everything this product is *for* passes through it, and the two
  tests that touch stamping at all assert shape rather than content. **(iii)**
  It is where the defects have actually been: the three unguarded transitions,
  the ignored `expires_at`, the deleted sender message and the double-`finalize`
  re-stamp were **all** found in `durable.ts`, by coverage of `durable.ts`.
  That is an observed base rate over four deliveries, not a guess.
- **Residual B — the four modules imported by no test at all.**
  `storage/r2.ts`, `mail.ts`, `feedback.ts`, `convert/graph.ts` — plus
  `worker.ts` beyond **A-415**, which is imported once and driven only through
  `scheduled()`. **Re-measured by import, not by grep, and the method is the
  finding:** `grep -rl mail service/src/test/` hits all seven test files
  because `email` contains `mail`, and would report `mail.ts` covered. It is
  not; the complete set of non-`node:` module imports in the directory is
  `../worker.js`, `../core/stamping.js` and `../../durable.js`. **Second, not
  first, and the reason is cost rather than value:** three of these four cross
  a network boundary this suite has no stubs for — Microsoft Graph
  (`convert/graph.ts`, `mail.ts`), R2 (`storage/r2.ts`) and the GitHub issues
  API (`feedback.ts`) — so a packet here pays for scaffolding that residual A
  does not. **`feedback.ts` is the one worth naming inside this strand**: it
  carries a user's own material into a **public** GitHub issue, which is
  CHARTER §5.2 and `PRODUCT-RULES.md` PR-2's sanitization clause, and it is
  also item 3's subject — a packet taking item 3 should consider taking this
  with it.
- **Residual C — the integration suite still drives the wrong tree, and it
  ranks last despite still being the single largest thing in this entry.**
  Re-read at `efed763`: `frontend/playwright.config.ts:58`–`:66` boots
  `alembic upgrade head` and `uvicorn app.main:app` with `cwd: backendDir`
  locally, or a container from the root `Dockerfile` in CI — **`backend/`,
  both times**. Unchanged. **Three grounds for last, and none of them is that
  it is small.** **(i)** It cannot be measured on this machine at all: `docker`
  is not on `PATH` and a TCP connect to Postgres on `:5433` is refused
  ([`STAGE.md`](STAGE.md) §0 rider (b)), so a packet taking it cannot compare
  before against after — and this repository's own **L-006** is the lesson that
  a suite you cannot watch fail is not evidence. **(ii)** Re-pointing the
  **only** route-driving suite from `backend/` to the worker is the closest any
  build comes to *acting on* **Q-018**, which is the steward's and is open. A
  packet may honestly decide the mechanics; it may not decide which tree is the
  product by moving the only suite that tests one over HTTP. **(iii)** It is
  the one strand whose cost this seat cannot estimate, and ranking an
  unestimated strand first is how a queue stalls. **What would move it up:**
  Q-018 answered, or a packet that scopes it as *add* a worker-driving HTTP
  suite beside the existing one rather than *re-point* it — that framing takes
  ground (ii) away entirely and this seat would rank it first if proposed.
- **Residual D — the `email_verified` guard, now measured rather than proposed
  from source. It stays inside this entry and is not promoted, and the reason
  is the evidence, not caution.** `service/src/durable.ts:848` reads
  `if (!email || !email.includes('@') || claims.email_verified === false)`.
  **A-502 measures, in the tree, that an `id_token` which OMITS the claim is
  admitted** — cookie set, account row created, `GET /api/auth/me` answers
  `200` on that cookie. That is a real change in evidence status: it was
  *proposed from source on an uncovered branch* through three reorders, and it
  is now *measured*. **It is still not a demonstrated vulnerability and this
  seat does not assert one.** Reaching the branch needs a token from the
  configured provider's own endpoint, for this deployment's `client_id` **and**
  `client_secret`, against a state row this worker minted minutes earlier; the
  code takes the token directly from that endpoint over TLS. **`spec/0009` §S3
  names exactly what would raise it** — a path by which such a token carries an
  uncontrolled email and no claim — **and says plainly that nobody gathered
  it.** That is a question about Google and Microsoft, not about this
  repository, and it has not been answered since. **So: no promotion, on the
  stated ground that the promotion condition this entry set for itself is
  unmet.** What it gets instead is a route: **the fix is one token and its test
  already exists.** `0080`'s mutation **M1** — `=== false` → `!== true` — turns
  **A-502 red and nothing else**, and A-502's own comment says in advance that
  *"if a later packet tightens the guard, A-502 going red is the correct
  outcome"*. **Folded in here, on the same line:** `!email` at `:848` is **dead
  code**, fully subsumed by `!email.includes('@')` (`''.includes('@')` is
  already `false`; `0080`'s M4 shows no single mutation of it is observable).
  **Whichever packet next edits `:848` should close both or neither** — one
  line, two findings, one existing test that proves the tightening. It gets no
  entry of its own; `0080` proposed exactly that and is right.

**Boundary, unchanged and it must survive:** *characterize, do not adjudicate.*
A test that records what the worker does is ordinary work; a test written to
assert the worker's account rule is the *correct* one answers **Q-018**, which
is the steward's. A-302 is the model.


**Why here, and this is the first reorder at which this entry moved forward
rather than merely surviving.** `2471a29` took it from **21 assertions across
four files to 28 across five**, re-run twice by this evaluation, and closed its
sharpest open strand by covering `worker.ts` at all. It stays at 2 rather than
dropping: the strands named above — R2, mail, feedback, conversion and the
OAuth callback — are untouched, and `e2e`, the only suite that drives routes
over HTTP, still drives `backend/`. Breadth ranks below the live data-loss
defect at item 1 and above everything no user has reported. **And it ranks
above item 1's own frozen case for a reason worth stating: item 1's test is
cheap precisely because this entry's three deliveries built the harness it will
use.**

**Updated by the seventh reorder at `c23c7e6`, and this is the whole of what
changed here.** **This is now the top *build* entry on this list — the entry
the project manager's next coder packet takes.** It did not move and it did not
become more urgent: **the data-loss defect that outranked it was built**, at
`9659e69`, and is retired below. The two sentences above about ranking below
*"the live data-loss defect at item 1"* describe the sixth order and are left
as its record; item 1 today is the undeployed set, which is operator action and
not a build. **The forecast in the last of them held exactly**: that entry's
frozen case was cheap because this entry's harness already existed —
`envelope-correction.test.ts`'s three new cases (**A-417–A-419**) reach the
real Durable Object through `test/support/durable-harness.ts`, which is this
entry's own delivery. Assertion count **re-verified at `c23c7e6` by this pass**
and moved again: **28 across five files → 31 across six**, `# fail 0`, over
**40 consecutive runs**. **Everything else in this entry — the OAuth-callback
strand, the uncovered modules, `e2e-workflow.test.ts`'s misnomer and the
Playwright suite driving `backend/` — is `carried, not confirmed` from the
sixth reorder;** this pass did not re-read any of it. **That sentence is the
seventh reorder's dated record of its own scope and is left as written —
Q-034.** Two of the four things it names were delivered at `07e0188` and are
struck above by the eighth reorder, which re-read all four.

**Updated by the eighth reorder at `efed763`, and this is the whole of what
changed here.** **This is still the top *build* entry, and it did not move.**
Nothing above it was built: item 1 is operator action and is still four repairs
deep, re-verified against the live host at 06:08:55 UTC. **Two of this entry's
strands were delivered by coder job `0080` and are struck above** — the named
first slice (the OAuth callback, `A-500`–`A-506`) and the misnomer (the rename
to `stamping-multi-signer.test.ts`). **The entry did not empty and this seat
will not let the delivery read as one:** four modules are still imported by no
test, `worker.ts` is driven only through `scheduled()`, `durable.ts`'s interior
is untouched, and the only route-driving suite still drives `backend/`.
**Assertion count re-verified at `efed763` by this pass and moved again: 31
across six files → 38 across seven**, `# fail 0`, over **3** consecutive runs
at 06:02–06:09 UTC — three, not forty, and the difference is stated rather than
inherited from the seventh reorder's forty. **The residual is ranked A → B → C
above, with a reason each, and D is folded rather than promoted.** **The
boundary below held under the packet that took this entry and is re-affirmed
rather than restated:** `07e0188` changed **no** worker code —
`git diff f0d1912 -- service/src/durable.ts` is empty, checked by this seat —
and A-502 is marked *recorded, not endorsed* in its own comment, which is
`A-302`'s mechanism copied rather than paraphrased. **A packet taking residual
A, B or C must not assume otherwise**: characterizing what `durable.ts` does is
ordinary work; a test written to assert that what it does is *correct* answers
**Q-018**, which is the steward's.

**3 · The feedback screenshot must be attached, not pre-attached** — source:
`PRODUCT-RULES.md` **PR-2** (v1.0, read fresh this packet from `pumasi` branch
`worktree-product-rules` `0115758`; **still not on `pumasi` main** — checked at
`pumasi` @ `cdc0b9a`; that is **Q-017**, now flagged by **seven** consecutive
evaluations, and absence from main is not compliance), CHARTER §5.2.
Re-read in the tree at `2471a29` by this evaluation and **unchanged**: opening the dialog sets a fallback
canvas as the attachment immediately (`FeedbackDialog.vue:185`–`:189`,
`screenshotIsAuto.value = true`) and then replaces it asynchronously with a
real `html2canvas(document.body)` capture (`:193`–`:197`). The user presses
nothing. PR-2 says *"a screenshot travels only when the user attaches one"*.
The user sees it and can remove it (`removeScreenshot`, `:201`), so today this
is opt-out and informed — but in an e-signature product the page being captured
is somebody's contract, and §5.2 says *never the user's own material*. Make it
a button the user presses. Why here: PR-2 binds at the `beta` promotion, this is
the only clause it fails, and it is cheaper to fix now than to hold a promotion
for. **This is the deployed behaviour, not a branch one** — the feedback widget
that produced issues #4–#9 is the one live on `sign.pumasi.ai`.


**4 · One version number, and put it in the reports** — source:
`PRODUCT-RULES.md` **PR-1**, which binds *always, from the first commit*, and
is not met. Re-measured at `2471a29` by this evaluation and unchanged: the root `package.json` carries **no
`version` field**; `frontend/package.json` reads `0.0.0` and
`service/package.json` reads `0.1.0` (two hand-maintained copies — L-007); no
version is visible to a user anywhere in the SPA; there is no `/version`
endpoint; and `FeedbackDialog.vue::buildContext` (`:105`–`:121`) sends
**thirteen** fields — page, URL, user, browser, platform, language, timezone,
viewport, screen, network, time, cores, device memory — and not the version.
Why here: all **seven** open issues are defect reports without a version, which is a
request to guess, and the fix is one source of truth plus two readers.

**The cost of this entry went up at `d18d534`, and the note that it "rides
naturally with item 2" is now wrong and is removed.** The root `package.json`
was edited by that commit and its `version` field was **deliberately** left
absent — `spec/0003` froze acceptance case **A-208**, which asserts the absence
precisely so that "a later packet cannot take it in passing"
(`spec/0003/SPEC.md:211`, `:251`). So the packet that takes this item must also
retire or amend A-208 in the same commit, and should say so in its intent.
That is a small, stated cost, not a blocker.


**5 · Classify this repository's paths — the `RISK_ZONES.yaml` that does not
exist** — source: `pumasi/DECISIONS.md` **Q-031**'s own *Risk class* row, which
reports the absence, and CHARTER **Part 4**. **New in this reorder.** It is a
build; this seat ranks it and does not write it.

**The gap, measured rather than reported.** `ls RISK_ZONES.yaml` in this
repository → *No such file or directory*, confirmed by this evaluation at
`2471a29`. CHARTER Part 4 says the classification *"lives in `RISK_ZONES.yaml`
in each repository, is one boolean per path, and defaults to **can hurt
someone** when unmapped or unclear."*

**The cost of the absence is on the record and is exactly one paragraph.** Job
`0058` had to apply Part 4's table by hand to classify Q-031, and said so
inside the decision entry rather than hiding it: *"`pumasi-sign` carries no
`RISK_ZONES.yaml` (checked, not assumed), so CHARTER Part 4's table was applied
directly."* It reached the right answer — `can_hurt` — and the reasoning is
auditable. The next such release repeats the work, and the release after that
may reason to a different answer, which is the actual risk here.

**Weighed for promotion at the seventh reorder and kept at 5 — the packet asked
that this rank be weighed rather than inherited, so here is the weighing and
the new evidence it rests on.** **Re-verified at `c23c7e6`: `ls
RISK_ZONES.yaml` → *No such file or directory*, still.** What has changed is
the cost, and it is now measured rather than forecast. **CHARTER Part 4 has
defaulted three consecutive releases in this repository to `can_hurt` for the
sole reason that this file does not exist** — **Q-031** (*"`pumasi-sign`
carries no `RISK_ZONES.yaml` (checked, not assumed), so CHARTER Part 4's table
was applied directly"*), **Q-035**, and now **Q-037**, whose *Risk class* row
re-checked the absence at `3edd06f` and took a 7-day window on it. **And the
risk this entry forecast has materialised once**: Q-037's row records that
item 1's author read the change as **not** `can_hurt` on the merits, that the
releasing seat **agreed with that reading and took the window anyway**, and
that it did so because reclassification is itself a can-hurt change. That is
two seats reasoning to the same outcome by different routes and writing the
disagreement down — the cheap version of the failure, not the expensive one,
and it is exactly what a one-line file would have made unnecessary.

**It still does not move, and the reason is the first of the three below rather
than inertia.** The tax is real, it is now three releases deep, and it is
**paid in the safe direction every time** — no release has been
*under*-classified and none can be while Part 4's default stands. Items 2, 3
and 4 are each wrong in a direction the system does not self-correct, and item
1 is what users are owed. Promoting this above them would buy tidier paperwork
at the price of the only entries with a user on the other end. **What this pass
does instead is name the trigger**: the moment a seat reasons to a *different*
classification than a previous one did, rather than to the same one by a
different route, this entry stops being process infrastructure and is promoted
on that evidence. **Two riders**, so the rank is not merely re-inherited next
pass: it stays the strongest candidate to be **folded into whichever packet
next touches this repository's root**, exactly as item 6 is; and it is
deliberately **not renumbered**, because `pumasi/DECISIONS.md` Q-037 — published
one hour before this pass — cites it as *"that repository's `BACKLOG.md` item
5"*, and that entry is the steward's to edit, not this seat's.

**Why it ranks fifth and not higher — the packet asked for this reasoning
here, so here it is.** *(This heading read **"seventh"** from the day the entry
was written, and ground 3 below says the entry "sits immediately above item 8",
which is true of rank 7 and not of rank 5. Both are corrected at `c23c7e6` as
what they are — drafting residue from an entry that was placed at 5 carrying
the words for 7 — and no claim is made about how it happened. **The three
grounds themselves are the sixth reorder's, unchanged and `carried, not
confirmed`**, with one live caveat: ground 2's *"items 1 and 2 are a broken
promise and the coverage that would catch the next one"* described the sixth
order. Item 1 today is the undeployed set.)*

1. **The charter's default already fails safe, and that is decisive.** An
   absent file cannot cause *under*-classification: *unmapped or unclear
   defaults to can hurt someone*, and Part 4 adds that *"guessing wrong in the
   safe direction costs one extra review."* So the whole harm this file
   prevents is an over-classification tax and an inconsistency between two
   seats' hand-reasoning. Every entry above it addresses something that is
   wrong in a direction the system does **not** correct on its own.
2. **It serves no user.** Items 1 and 2 are a broken promise and the coverage
   that would catch the next one; item 3 is three defects three people
   reported; items 4 and 5 are `PRODUCT-RULES.md` clauses that bind. This is
   process infrastructure. It is worth doing and it is not worth doing first.
3. **It is small, which cuts both ways.** Half an hour of work is a weak reason
   to rank something high and a good reason not to leave it undone before a
   long feature run — which is why it sits above item 8, where the parity
   mandate resumes and several entries will be `can_hurt`. *(Read "immediately
   above item 8" until `c23c7e6`; the entry has been item 5, with 6 and 7
   between, since it was written.)*

**The precedent is not what it was described as, and a packet should know
before copying it.** The report that prompted this entry says `pumasi-booking`
has a `RISK_ZONES.yaml`. Read directly at `pumasi-booking` @ `2453adc`, it has
**two** — `core/spec/RISK_ZONES.yaml` and `service/spec/0002/RISK_ZONES.yaml` —
and **neither is at the repository root Part 4 names**. Both are scoped to a
spec item. No other repository in the fleet has one at all (`pumasi`,
`pumasi-web`, `pumasi-ops` and `pumasi-tunnel` checked, none tracked). So
*"the classification lives in `RISK_ZONES.yaml` in each repository"* is
currently true of no repository.

**This entry does not raise a `DECISIONS.md` question about that**, because it
does not need one: Part 4's words name the repository root, and booking's
nesting is a deviation rather than an authority. **Put the file at the root.**
Record the divergence from booking in the commit rather than silently matching
either shape.

**What the file should say, and why it is nearly a one-liner.** Booking's
service-level file is the useful precedent for its *content*: `can_hurt: "*"`
with a stated reason, on the grounds that the service holds third parties'
personal data and acts on their behalf. `service/` here is the same shape and
stronger — it holds signers' names, email addresses, IP addresses, user agents,
signature images and the documents they signed, it sends mail on a sender's
behalf, and it writes the audit record of a legal act. Enumerating exceptions
inside it would be looking for loopholes in our own risk model. `backend/` is
the harder call and **the packet must not answer Q-018 by classifying it** —
recording that it serves no user is a fact; concluding it therefore does not
matter is the steward's.

**6 · Three sentences in `CLAUDE.md` that are now false, and one of them is
this file's own history** — source: `roadmap/STAGE.md` §5's third row and coder
job `0064`'s hand-off. **New in this reorder.** All three re-read in the tree
at `2471a29` by this evaluation.

`CLAUDE.md` is the file every agent working here reads first. These are not
documentation defects with a documentation cost; they are wrong instructions.

1. **`:107`–`:110`: `expired` is *"past its optional `expires_at` deadline —
   flipped by the **daily** job"*.** For five evaluations this was wrong
   because there was **no** job. `2471a29` added one and it is
   **hourly** — `"triggers": {"crons": ["0 * * * *"]}` in
   `service/wrangler.jsonc`. So the sentence went from *wrong about the
   mechanism* to *wrong about the cadence*, which is smaller and still false,
   and it now reads as a claim about the deployed product that is false there
   too (`Handlers: fetch`, [`STAGE.md`](STAGE.md) §2.6(ii)). Job `0065` measured
   this, correctly declined to edit `CLAUDE.md` from a `service/`-scoped packet,
   and handed it here.
2. **The `service/` coverage sentence — *"`src/test/` holds two files and both
   exercise `core/stamping.ts` only. Auth, the Durable Object store, R2 and
   mail are covered by nothing"* (`CLAUDE.md:78`–`:81`).** ~~At `2471a29` it
   holds **five**: `stamping`, `auth-session`, `envelope-lifecycle`,
   `e2e-workflow` and `envelope-expiry`.~~ — the sixth reorder's dated reading,
   superseded twice and kept as its record. **Re-verified at `efed763` by the
   eighth reorder: it holds SEVEN** — `auth-session`, `envelope-correction`,
   `envelope-expiry`, `envelope-lifecycle`, `oauth-callback`,
   `stamping-multi-signer`, `stamping`. **Four** drive a real Durable Object
   through `service/src/test/support/durable-harness.ts`, A-415 drives
   `service/src/worker.ts`, and auth is covered twice over (`A-300`–`A-308`,
   `A-500`–`A-506`). **A quarter of the sentence is still true and this entry
   says so rather than striking the whole:** `mail.ts` and `storage/r2.ts` are
   imported by no test. **The sentence understates coverage, which is the
   direction that reads as conservative and is still false** — an agent told
   the suite tests one file will not think to check whether its change is
   already covered — **and the gap it understates by has grown from three files
   to five.**
3. **The Deployment section still describes the Railway stack first.** It does
   carry Q-018's correction, so this is the mildest of the three, but
   `README.md` was rewritten at `ba1cea7` to put the served tree first and
   `CLAUDE.md` was not. Two front doors, two orders of presentation.

**Why here, and why it is not item 1.** No user meets any of it. It ranks above
the parity mandate because the cost falls on every future packet and the fix is
minutes. **The right way to take it is to fold it into whichever packet next
touches `CLAUDE.md`** — job `0064` said exactly that about (2) and it is right
about all three. It is ranked rather than left unwritten so that it does not
get rediscovered a seventh time.

**The eighth reorder makes the routing specific rather than leaving it to the
next reader, because "whichever packet next touches `CLAUDE.md`" has now failed
to fire three times running.** `0064`, `0065` and `0080` each measured a false
sentence here, each correctly declined to edit `CLAUDE.md` from a `service/`-
scoped packet, and each handed it up. **So: the next coder packet taking item 2
folds in (2), and (2) alone.** That packet is the one changing the number, its
spec has to state the coverage shape anyway, and one line of `CLAUDE.md` is
inside any honest account of what it did. (1) and (3) stay unrouted here and
keep waiting for a packet that touches those sections. **This seat did not edit
`CLAUDE.md` itself and the reason is recorded rather than left implicit:
`CLAUDE.md` is not in the product-manager role's may-write list**
(`pumasi-ops/roles/product-manager.md`, *May write*), which enumerates issue
labels, the four `roadmap/` files, `DECISIONS.md` questions and the ops
`DIGEST.md`. Editing agent instructions on the strength of an unlisted power is
**L-003**, and this repository has paid for that twice. **The entry stays at 6
and is not promoted**: it got staler — (2) now understates by five files rather
than three — but staleness in the conservative direction is still the mildest
thing on this list, and every entry above it has either a user or a rule on the
other end. Recorded as weighed, not as overlooked.


**7 · The residue of three closed issues — inert `gap-*` on two live views,
and the settings *shell* behind the settings *menu*** — source: issues
[#5](https://github.com/pumasi-ai/pumasi-sign/issues/5) and
[#6](https://github.com/pumasi-ai/pumasi-sign/issues/6), both **closed**, both
with something left. **New in this reorder, and the reason it exists is the
finding rather than the work.**

**Two issues were closed by a fix scoped to the surface that was reported,
which is a legitimate thing to do and leaves this file holding the rest.**

- **`gap-*` is inert on `/login` and `/branding`, on the live product.**
  Measured against the **served stylesheet**, not the source: this frontend has
  no Tailwind (Vuetify `^3.13.0` only, whose utility is `ga-*`), and the single
  `index-D9vWh8vx.css` that every view loads contains **`.ga-2{gap:8px!important}`
  and zero `gap-` rules of any kind**. The only `.gap-*` definitions that ship
  are `.gap-2/3/4[data-v-774abb43]` in `LandingView-780GD1NO.css`, a chunk
  loaded only for `/`. **So `class="d-flex align-center gap-3"` at
  `BrandingView.vue:113` and `:143`, and `gap-2` at `LoginView.vue:121`,
  produce no gap for any user.** `bbde48f` fixed #6 by giving the reported
  colour-swatch row an inline `style="gap: 8px;"` — correct for the report,
  and it left the class-name bug on three other rows. Converge on `ga-*` or on
  the scoped definitions; the coder's call, and it is one afternoon.
- **There is still no settings route.** `bbde48f` closed #5 by replacing the
  app bar's `Branding` and `Users` buttons with a `Settings` dropdown
  containing both — which is what the reporter asked for and is why the issue
  is correctly closed. But `grep -n settings frontend/src/router/routes.ts`
  returns nothing and the served route table registers no `/settings`, so
  `/branding` is still top-level and every later settings-shaped item still has
  no home. The shell was pulled out of item 17 (spec §8) for exactly that
  reason and the reason survives.

**Two limits carried forward from the entry this replaces, and they are the
packet's, not suggestions.** **(i) No visual design is promised here** — if any
of this wants a responsive lockup or a provider-logo policy rather than a CSS
repair, that is the **Graphics Designer's** through the project manager.
**(ii)** On the app-bar wordmark (#10), this evaluation records what it can
support and no more: `bbde48f` removed one button from the bar, which reduces
the crowding the report described at 384px, and the `v-app-bar-title` still
renders `<img>` and `{{ branding.companyName || 'Pumasi Sign' }}` in one row
with no responsive lockup. **This seat did not reproduce the report at 384px**
and does not assert the clipping is gone.

**Why here.** Below everything that touches correctness, coverage, a product
rule or an agent's instructions; above the parity mandate, because a closed
issue whose defect is still live is the kind of thing that gets rediscovered as
a new report from a real user.


**8 · Focus-mode shells for prepare / tag / sign** — source: spec §1
(shell 2). Full-screen wizard and signing surfaces: global chrome hidden,
minimal header with close-X (back to origin), step title, primary actions
top-right. Why here: the single largest *perceptual* gap to the incumbent —
every send and every signature passes through these screens. **This is where
the steward-directed parity mandate resumes.**

**9 · One-page accordion envelope setup** — source: spec §4 step 1,
checklist 8. Documents / recipients / message as three collapsible sections on
one page; inline validation on attempted progression; implicit drafts on
close. Replaces paged steps 1–2. Why here: with item 8 it completes the incumbent's
prepare flow shape; touching the wizard once for both avoids rework.

**10 · Tagging-canvas mechanics** — source: spec §4 step 2, checklist 1, 16.
Drag-from-palette with cursor ghost (keep click-to-arm as fallback), zoom
control, undo/redo, field copy/paste, grouped palette; multi-document
envelopes as separate files with per-file thumbnail cards. **Scope is under
`pumasi/DECISIONS.md` Q-016** (issue
[#4](https://github.com/pumasi-ai/pumasi-sign/issues/4), `escalated`): Option A
— cards over the existing upload-time merge, with the combination stated in
the UI *and in the certificate* — is the named default and may proceed
pre-`launched`; Option B (true per-document separation, backend rework) is not
authorized by that default. Why here: the canvas is "the product" per the
spec's own ranking; do it after item 8 so it lands inside the focus shell.

**11 · Signature identity: styles, saved list, frame imprint** — source: spec
§5 adopt modal, §8 signature adoption + framing, checklist 4. Generated styles
from name/initials with live preview, multiple saved signature/initials pairs
in a profile page, and the "signed by" bracket frame + short envelope/party ID
burned into the stamped PDF behind an account toggle (`service/src/core/stamping.ts`;
`backend/app/stamping.py` only if Q-018 keeps that tree). Why here: this is
what makes a signed document *look* like the incumbent's output — the artifact
everyone outside the org actually sees.

**12 · Post-sign share loop** — source: spec §5 finish sequence, checklist 12.
After Finish: share-by-email modal (multi-email chips, prefilled subject, short
message with counter), each recipient getting a tokenized free download link;
declining still completes. Why here: cheap, and it is the incumbent's growth
loop — the commons' S8 outward-transmission thesis for picking this product in
the first place.

**13 · Manager depth: bulk, folders, trash, richer filtering** — source: spec
§3, checklist 7, 21. Row checkboxes + bulk bar (download / move / delete), user
folders, a real Deleted view with restore (soft-delete; archive stays per-user
hide), quick-views dropdown, default date-window chip with inline clear,
two-line rows (title over "To: recipients"), density toggle. Why here:
daily-driver ergonomics once volume grows; none of it blocks the flows above.

**14 · Ceremony options** — source: spec §5, §8 signing settings, checklist 5,
23. Finish-later; configurable consent/disclosure step for remote recipients
(recorded in the certificate); auto-navigation modes (page-only / required /
all). Why here: recipient-facing polish and the compliance-relevant consent
record.

**15 · Field-type parity + per-recipient auth** — source: spec §4 palette,
checklist 17, 18. Email / Company / Title contact fields; Approve / Decline
action buttons; Note; per-recipient "Customize" auth (access code; SMS later).
Payment: explicitly skipped. Why here: each is small and spec-shaped; batch
after the canvas rework so new types land once.

**16 · Template library depth** — source: spec §7, checklist 9. Description
field, favorites, my/shared-with-me groupings, "[Untitled]" implicit drafts,
starter-template gallery. Why here: value scales with template count, which is
still small.

**17 · Admin & records layer** — source: spec §6, §8, checklist 3, 11, 13, 14,
20, 25. Account defaults (reminders/expiration, signing permissions, date/time
regional formats), per-user notification preferences, envelope/document custom
metadata, retention purge, combined-into-one-PDF + zip download, certificate
depth (per-signer viewed timestamps, security level, adoption method), a
Reports section. **The settings *shell* was pulled out as item 6**; this is
everything that goes inside it. Retention here is also what
[`STAGE.md`](STAGE.md) §2.4 needs to make a data-survival claim citable. Why
here: nothing user-visible upstream depends on it.

**18 · Onboarding polish** — source: spec §2, §9, checklist 15. First-run coach
marks per surface; persistent "n/5" getting-started checklist (banner + modal,
live progress). Why last: worth doing only once the surfaces it teaches
(items 7–11) are in their final shape.

---

---

## Blocked — not in the build order until a steward answers

Entries here have real work left, and **no coder may execute it today**. They
are out of the numbered list rather than sitting at its top, because the top
of that list is what the next coder packet builds, and a packet that takes an
entry nobody may execute delivers nothing. They come back into the order the
day their window closes, at whatever rank they then deserve.

**One entry, where there were two, and the survivor is worse than it was.**

**B1 · The landing page's licence claim is now published, and it is still not
true** — source: issue [#8](https://github.com/pumasi-ai/pumasi-sign/issues/8)
(**closed 2026-09-01 00:59:11 UTC**), [`STAGE.md`](STAGE.md) §2.3.2,
`pumasi/DECISIONS.md` **Q-021**.

**This entry had two halves. The deploy took the second one and left the
first.** Half **(d)** — *then deploy* — ran at 01:02 UTC on 2026-09-01 without
Q-012 being answered. Half **(b)** — *make the claim true first* — did not.
**That ordering is the entire content of this entry now**, and it is why #8's
closure does not retire it: the issue asked for a full-featured landing page
and got one; this entry asks that the page not lie, and it does.

**(b), re-measured against the artefact a stranger downloads** — served
`LandingView-C5khdw3s.js`, 10 046 bytes, fetched 2026-09-01 01:57 UTC. **Three
distinct claims, not one string three times:**

```
` Zero Per-Seat Fees • Unmetered Envelopes • 100% Apache-2.0 `
`Pumasi Sign is in active ` + Alpha + ` — Unmetered PDF stamping & SHA-256 audit certificates under Apache-2.0.`
`License & Source Code` | `Apache-2.0 (Open Source)` | `Proprietary Closed Source` | `Proprietary Closed Source`
```

against, at `2471a29`:

```console
$ ls LICENSE*
ls: cannot access 'LICENSE*': No such file or directory
$ gh repo view pumasi-ai/pumasi-sign --json licenseInfo,visibility
{"licenseInfo":null,"visibility":"PUBLIC"}
```

The third is the one that matters most, because it is a **comparison**: the
row invites a reader to prefer this product on terms that the repository does
not offer, against two named competitors it calls *"Proprietary Closed
Source"*.

**Why no seat here may close it, and why that is not a formality.**
**Q-021** is open and its named default — add `LICENSE`, Apache-2.0,
byte-identical to `pumasi-web/LICENSE` — is an **outward grant a third party
may rely on**, which CHARTER Part 0's reversibility rule explicitly does not
release. Its named alternative — strike the three strings — answers the
steward's question by deleting the evidence for it, and would additionally
require `roadmap/VALUE.md` §1 and C5 and `roadmap/MARKET.md` §2–3 to move,
since the wedge those files state is two clauses wide for exactly this reason.
Frozen case **A-005** (`frontend/src/landing-claims.spec.ts:198`) pins the
three strings byte-identical to `10a523d` and carries its own instruction —
*"RETIRE THIS CASE WITH Q-021"* — so whichever way the steward lands, A-005 is
updated or deleted in the same commit. **The frozen case and the deployed
bundle agree**, verified here: nothing drifted, the strings simply left the
repository.

**What changed about the question, stated once because it is the reason this
pass exists.** Q-021 was raised as *"a question and not an incident"* on the
express ground that the page was undeployed. **It is deployed.** Evidence rows
were added by this evaluation to Q-021 and to **Q-028** — whose entanglement
resolved itself by shipping, exactly as that entry forecast, without either
question being answered — and to **Q-012**, which is the entry that owns the
act. **No window was closed, no deadline set, no default softened, and no
`LICENSE` file was added or removed by this seat.**

**One instruction attaches to the downstream page and belongs here rather than
only in the digest.** `pumasi-web/content/products/pumasi-sign.md` says Surface
B is undeployed, which is now false and is a marketing packet's to fix — after
[`STAGE.md`](STAGE.md), not before (**L-007**). That card **must not** start
claiming Apache-2.0 on the ground that the live page does. One surface
repeating an untrue licence grant is a mistake; two is a pattern.

---

## Retired

**Four entries retire at this reorder. One of them was retired by a build; the
other three were retired by a deployment nobody announced.** That split is
recorded in those words rather than flattened into *delivered*, because a
register that says a thing shipped without saying what shipped it is how the
next seat learns the wrong lesson — and because the one retired by a build is
the one that has **not** reached a user.

---

**One entry retires at the seventh reorder, and like the sixth's build-retired
entry it is retired from the *build order* and not claimed as delivered.**

**~~1 · The envelope-settings dialog silently deletes the sender's message to
signers~~ — BUILT 2026-09-01 at `9659e69`, and deliberately NOT recorded as
delivered** (coder job **`0074`** — not `0073`, corrected at `c23c7e6` and at
`pumasi` `df89865`; `spec/0008`; `pumasi/DECISIONS.md` **Q-037**, 7-day
can-hurt window open, closes **2026-09-08**). **Was item 1.** Struck by this
seat: the job that built it was barred from touching rankings, said in its own
return block that the strike was the next evaluation's job, and did not touch
this file.

**Re-verified at `c23c7e6` by this pass, in the tree rather than taken from the
commit message.** `service/src/durable.ts:1326`–`:1328`:

```ts
const message = body.message !== undefined
  ? (body.message != null ? String(body.message).slice(0, 2000) : null)
  : (sub.message ?? null);
```

`title`'s `?? sub.title` is unchanged on the line above, so the two fields now
have the same rule; **an omitted `message` is kept and an explicit `null` still
clears it**, which is the discrimination this entry asked for by name and the
one the tempting `??` shortcut would have collapsed. Three frozen cases
**A-417–A-419** in a new file, `service/src/test/envelope-correction.test.ts`,
drive the real service through its own entry point — A-417 sends *literally the
body the settings dialog sends* and asserts the message survives on the stored
row, in the response and on the recipient's token view. Root `npm test` at
`c23c7e6`, **40 runs, 40 pass**: `# pass 31`, `# fail 0`, `from 6 compiled` —
28 → 31 is exactly these three.

**Two things retire with it and neither is optional reading.**

**(1) It is delivered in the half a commit can deliver, and not in the
product.** Q-037's own `Status` row says so: *"As of publication the settings
dialog on `sign.pumasi.ai` still deletes the sender's message to signers,
silently, and still reports success."* **Re-verified at `c23c7e6`:**
`https://sign.pumasi.ai/` answered **200** at **2026-09-01 03:25:05 UTC** and
still serves `/assets/index-CnoFAC2c.js`, the bundle the sixth evaluation
measured — built from `0e26917`, which predates this repair by two releases.
**That residue is item 1 of the order above**, where it sits beside the
`expires_at` sweep and where a reader looking for what users are owed will
find it. It is **not** left here, because the *Retired* section is where a
reader looks for things that are finished.

**(2) What the repair cannot do, and it is the entry's real outcome.**
**Messages already deleted are gone.** They were overwritten with `NULL` and
there is no shadow copy, so there is nothing to restore from and no count of
how many there were. This entry stops the next deletion; it does not undo one
that happened. The release note says this in the sender's own words rather than
letting *"fixed"* imply otherwise, and it is recorded here for the same reason:
a Completed section that records only what was gained is a register that
teaches the wrong lesson about what a data-loss defect costs.

**One thing this entry asked for and did not decide, answered elsewhere and
recorded rather than left dangling.** It declined to say whether the
`corrected` audit row should name a message change. **Q-037 answered it: yes,
and `title` goes with it**, compared against the stored row rather than against
presence in the body. That is a change to what a past-facing record says about
a correction, which is why it is named here and not only in a diff. The 409
guard stays keyed on `settings` alone; **A-416, from the `expires_at` release
earlier the same day, passes unaltered, and no frozen case was amended — so
`pumasi/DECISIONS.md` Q-030 is not reached by this build and no reading of it
is taken here in either direction.**

---

**~~1 · Make `expires_at` do what the UI already tells the user it does~~ —
BUILT 2026-09-01 at `2471a29`, and deliberately NOT recorded as delivered**
(coder job `0065`, `spec/0007`, `pumasi/DECISIONS.md` **Q-035**, 7-day can-hurt
window open, closes **2026-09-07**). **Was item 1.**

**Verified in the tree at `2471a29` by this evaluation rather than taken from
the job's report:** `service/wrangler.jsonc:22` carries
`"triggers": { "crons": ["0 * * * *"] }`; `worker.ts:189` exports `scheduled`;
`expired` joined `isTerminal` (`durable.ts:114`), so job `0058`'s three guards
cover a fifth terminal status with no fourth guard written — `cancel` 409 at
`:1383`, `complete` 410 at `:1591`, `decline` 409 at `:1652`; and seven frozen
cases **A-410–A-416** drive the sweep, the token surface and the idempotency.

**This entry's own text was wrong about the shape of the work, and the
correction is recorded rather than quietly dropped.** It called the sweep's
enumeration of Durable Objects *"the real work in this item"*, on the premise
that *"every envelope lives in one"* and there is no pattern in `service/` to
copy. Measured by the job and confirmed here: `worker.ts` resolves
`idFromName('pumasi-sign-main')` — **a constant** — for every `/api/*` request.
**There is one Durable Object.** There was nothing to enumerate. The ranking
was right and the difficulty estimate was not, and the effort went into the
guards and the acceptance cases instead.

**Why this is retired from the build order and is not a claim about the
product.** The live worker's version metadata, read by this evaluation at
02:00 UTC, reports **`Handlers: fetch`** and nothing else; a build carrying
`2471a29` would list `fetch, scheduled`. **Every deadline on `sign.pumasi.ai`
still does nothing, and a past-due envelope is still signable there.** That is
**Q-012**, which is not a build entry. See [`STAGE.md`](STAGE.md) §2.6(ii) and
§5, where this is state (iii)'s new and only occupant.

**One honest debit carried from the build.** Frozen case **A-409**'s header
comment now says something stale — *"no `scheduled` handler and no cron
trigger"*. It is a comment, not an assertion; A-409 still passes unchanged,
because the sweep is the only writer of `expired` and A-409 never invokes it,
so a deadline *by itself* still transitions nothing. Recorded in `spec/0007`
rather than by editing a frozen file, and named here so it is not mistaken for
drift.

---

**~~3 · Three small presentation defects, one packet — #6, #10 and #11~~ —
DELIVERED 2026-08-31 at `bbde48f` and `1d2743f`, and live to users since
2026-09-01 01:02 UTC.** All three issues closed. **Was item 4 before that, and
item 3 at the last reorder.**

**Verified against the served build, not the tracker.** `#11` — the provider
marks: the live `LoginView-D-zAW__C.js` contains inline `<svg>` with Google's
brand hexes (`#4285F4`, `#EA4335`) behind the same two labels, replacing
`prepend-icon="mdi-google"`/`mdi-microsoft`, which is the `pumasi-booking`
**behaviour** the entry asked for. `#10` — the app bar: `bbde48f` replaced two
buttons (`Branding`, `Users`) with one `Settings` dropdown, which is a real
reduction in the crowding the report described at 384px. `#6` — the colour
swatches: the reported row got an inline `style="gap: 8px;"`.

**This retirement is partial in a way worth naming, and the remainder is new
item 7.** `#6`'s underlying defect is a class name — `gap-*` where this
frontend ships `ga-*` — and the fix was scoped to the row that was reported,
leaving three other rows on two live views still using it. `#10` was addressed
by removing a competitor for the space rather than by a responsive lockup, and
**this seat did not reproduce the report at 384px**. Both are correct
resolutions of the reports and both leave something; the something is ranked
rather than lost.

---

**~~6 · A settings shell, with branding inside it~~ — RESOLVED for the user
2026-08-31 at `bbde48f`**; issue [#5](https://github.com/pumasi-ai/pumasi-sign/issues/5)
closed. **Was item 6.** The app bar now carries a `Settings` dropdown holding
*Branding & Design* and, for admins, *Team & Users* — which is what the
reporter asked for. **The shell itself does not exist**: there is no `settings`
route in `frontend/src/router/routes.ts` and none in the served route table, so
`/branding` is still top-level. That residue is **item 7**, and the account
defaults, notification preferences and retention controls that would fill a
real shell stay in item 17.

---

**~~B2 · Carry #7's merged fix to the people it is for~~ — DELIVERED
2026-09-01 at 01:02 UTC by a deployment, not by a merge.** Issue
[#7](https://github.com/pumasi-ai/pumasi-sign/issues/7) closed 00:59:12 UTC.
`pumasi/DECISIONS.md` **Q-027**'s window still runs.

**Verified on the served bundle rather than on the tracker**, which is the
whole point of this entry having existed:

```console
$ curl -s https://sign.pumasi.ai/ | grep -o '/assets/index-[^"]*\.js'
/assets/index-CnoFAC2c.js
$ grep -c '/api/auth/login?next=' index-CnoFAC2c.js
0
$ curl -s -o /dev/null -w '%{http_code}\n' 'https://sign.pumasi.ai/login?next=%2F'
200
```

**The `0` is the decisive line.** This entry's previous text quoted the removed
helper still shipping —
``function pl(e){return`/api/auth/login?next=`+encodeURIComponent(e)}`` — beside
the one that replaced it. The pair is gone; only the replacement remains, and
the served `SignedOutView` chunk calls it with `"/"`.

**What this retirement costs the register, and it should be said plainly.**
This entry was blocked on **Q-012** and **Q-021**, both open, both unanswered.
It did not become unblocked. **It was overtaken** — the deploy it was waiting
for happened, carrying with it the licence claim Q-021 exists to decide, which
is precisely the outcome **Q-028** was raised to prevent and precisely the
artefact it predicted. Retiring it as *delivered* is accurate about the user
and would be misleading about the process, so it is retired as *delivered by an
act nobody in the queue authorised or announced*. See [`STAGE.md`](STAGE.md)
§2.5.

---


**~~Repair the three unguarded envelope transitions~~ — delivered 2026-08-31
at `68e5d08`** (coder job `0058`, `spec/0006`, `pumasi/DECISIONS.md` **Q-031**,
7-day can-hurt window open, closes **2026-09-07**). **Was item 1.** Verified in
the tree at `56a8bf8` by the fifth evaluation rather than taken from the decision
entry — the guards, their status codes and their current line numbers are in
the table at the top of this file. All three refuse before reading the request
body, so a refusing path writes nothing and audits nothing, and one predicate
(`isTerminal`, `durable.ts:109`) backs all three.

**This entry is retired with its own wrong sentence recorded, not deleted.**
The struck sentence, and it was this file's ranking argument for treating
`complete` as the least of the three:

> ~~So the omission mostly produces the **wrong refusal** — *"Already signed"*
> (409) where the other terminal states give *"no longer active"* (410) —
> rather than a wrong write.~~

**What disproved it:** the CC recipient. The reasoning rested on an envelope
only completing once every non-CC signer is `signed`, but the completion count
reads `AND is_cc = 0`, so a CC recipient is still `pending` at completion,
passes both guards, re-enters `finalize()` and writes a second `completed`
audit event — re-stamping the executed PDF where one is present. A reachable
wrong write. **Where the measurement lives:** `spec/0006/SPEC.md` **§S1a** for
the reasoning, frozen case **A-406** for the measurement (it asserted the
second completion event; the count was `2`), and `spec/0005` §S6.4, which had
it right before this file did.

**Two things this retirement does not claim.** It did **not** widen coverage —
the gate printed the same 21 assertions from the same four files as before the
release. (**The figure has since moved to 28 across five files, at `2471a29`,
which is a different release's doing** and is recorded at item 2.) And it did **not** falsify
[`VALUE.md`](VALUE.md) **C1**: the stamped PDF and its certificate live in R2
and a status overwrite never touched them. What was damaged is the row and the
audit log disagreeing with the certificate — **L-009** at row scale.

**~~Retired from the build order, and the defect is still live to every
user.~~ — struck 2026-09-01 by the sixth evaluation, and this is the only
sentence in this file that a deployment made *better*.** The paragraph read
that the transitions *"behave the old way on `sign.pumasi.ai` today"*, measured
against the unchanged bundle at 00:29 UTC. **The deployment at 01:02 UTC
carried the repair.** `68e5d08` is an ancestor of `0e26917`
(`git merge-base --is-ancestor`), which is the commit the served build was
fingerprinted to ([`STAGE.md`](STAGE.md) §2.2), and `wrangler.jsonc` ships the
worker and `frontend/dist` as one artefact. The guards are live.
**`pumasi/DECISIONS.md` Q-031's Status line — *"the three transitions still
behave the old way for anyone using the live service"* — is now stale in the
good direction; that is the steward's entry and this seat did not edit it.**
Q-031's 7-day window still closes 2026-09-07.

**Also recorded here because it belongs to this entry's history:** job `0058`
amended frozen cases **A-404**, **A-406** and **A-407** in the open, under the
default reading of **Q-030** (*may a builder amend a frozen acceptance case?*),
having read that question mid-run. **Q-030 is open**, `pumasi-tunnel` reverted
the same move under an objection, and nothing in this file pre-empts the
steward's answer. Two objections on this product cited CHARTER Part 3
requirement 2 against the amendment; both cite the **stale** copy of the
charter (**Q-032**), which is a fact about the objections and not an answer to
Q-030.


**~~#7: "sign in again" sends the user to a raw 404~~ — delivered 2026-08-31
at `d18d534`** (coder job `0037`, `spec/0003`, `pumasi/DECISIONS.md` **Q-027**,
7-day window open). Was item 1. **Verified by this evaluation in the source
tree, not taken from the job's report:**

- `SignedOutView.vue:2` imports `loginPageUrl` and `:6` sets
  `const signInUrl = loginPageUrl("/")`; `utils/http.ts:44` returns
  `"/login?next=" + encodeURIComponent(next)`.
- **`loginRedirectUrl` is gone.** `git grep loginRedirectUrl` over the tracked
  tree returns no definition and no caller — only a header comment at
  `utils/http.ts:39` explaining why it was removed, a frozen case at
  `frontend/src/signed-out-entry.spec.ts:153` asserting the name appears
  nowhere in the SFC, an old plan document, and a review file.
- The page it now targets answers on the deployed tree:
  `GET https://sign.pumasi.ai/login?next=%2F` → **200 `text/html`**, measured
  by this evaluation.

**~~Retired from the build order, and issue #7 stays open on purpose.~~ —
struck 2026-09-01 by the sixth evaluation.** The paragraph read that
*"`sign.pumasi.ai` still runs the pre-fix bundle"*, and it is the sentence this
entry carried for three reorders. **It stopped being true at 01:02 UTC on
2026-09-01.** The served bundle is `/assets/index-CnoFAC2c.js`,
`grep -c '/api/auth/login?next=' ` over it returns **0**, and issue #7 was
closed at 00:59:12 UTC. **B2 is retired above**, and [`STAGE.md`](STAGE.md)
§5's state (iii) — of which this was the founding example — is now occupied by
`expires_at` instead.

**~~Make `GATE: PASS` cover the tree users actually meet~~ — delivered
2026-08-31 at `d18d534`** (coder job `0037`, `spec/0003`,
`pumasi/DECISIONS.md` **Q-025** rider (a)). Was item 2. Verified by this
evaluation by running it, not by reading it:

- The root `package.json` `test` script is now
  `npm run test:frontend && npm run test:service`; `test:service` is
  `.github/scripts/run-service-suite.sh`, which `npm ci`s, **builds**
  (`service/dist/` is `.gitignore`d and the suite runs `dist/`), runs the
  suite, and hands its output to `.github/scripts/assert-service-suite-ran.sh`
  — the **same file** `ci.yaml`'s `service` job calls, not a copy (L-007).
- Run at `d18d534` by this evaluation: `Test Files 6 passed (6)`,
  `Tests 85 passed (85)`, `# pass 2`, `# fail 0`,
  `assert-service-suite-ran: 2 passing, 0 failing, from 2 compiled`. Before
  `d18d534` the same command reported 5 files / 69 tests and **zero** service
  assertions.
- Determinism re-measured for the suite that exists **today**, because the
  shape changed: **40 consecutive runs, 40 pass, 0 fail**, every run reporting
  the identical counts above. Details and method in [`STAGE.md`](STAGE.md) §0
  rider (b).

**What is carried forward, and it is item 2.** The gate runs the served
tree. *Updated by the sixth reorder:* what it runs there is no longer "two
assertions against one file" and no longer the fourth reorder's **21 across
four** — it is **28 across five** at `2471a29`, three of which drive a real
Durable Object and one of which drives `worker.ts`. The carried-forward
complaint is narrower again and is breadth. `main` is still
**not a protected branch** — `GET /repos/pumasi-ai/pumasi-sign/branches/main/protection`
→ 404 *"Branch not protected"*, re-checked this tick — so this one hand-run
command remains the whole gate. Q-025 is untouched and stays open.

**~~Green main: fix the 4 backend pytest failures~~ — met 2026-08-31.** Was
item 1. CI run
[33410370102](https://github.com/pumasi-ai/pumasi-sign/actions/runs/33410370102)
at `5cb3bf8`: `backend` ✓, `frontend` ✓, `e2e` ✓ (coder job `0018`; the four
failures were single-tenant expectations against multi-tenant normalization,
`1c8590d`, and `e2e` had two further causes, `5cb3bf8`). Retired rather than
deleted, with one thing carried forward: **that gate covers `backend/`, which
is not what users reach.** The re-sourced version of this entry's purpose —
*a gate whose green means something* — became the old item 2, retired directly
below. That entry's own successor — the *merge* gate, as against CI — was in
turn delivered at `d18d534` and is retired below it. What is left of the
lineage is item 3: a gate that runs the served tree, over a suite that is now
21 assertions wide and still leaves `worker.ts`, R2, mail, feedback and
conversion uncovered.

**~~Make the gate cover the tree users actually meet~~ — delivered 2026-08-31
at `ef851d6`** (coder job `0032`, `pumasi/DECISIONS.md` Q-018 parts (a), (b),
(c)). Was item 2. Confirmed independently by this evaluation rather than taken
from the job's report:

- `.github/workflows/ci.yaml` now defines **four** jobs — `backend` (`:10`),
  `frontend` (`:60`), **`service` (`:104`)** and `e2e` (`:144`). The `service`
  job checks out, `npm ci`s, **builds** (`dist/` is `.gitignore`d, so the
  build is not an optimisation), runs the suite through `tee`, and then runs
  `.github/scripts/assert-service-suite-ran.sh` against its own reported
  counts — deliberately independent of the build step, so deleting that step
  still turns the job red.
- Run [33420378497](https://github.com/pumasi-ai/pumasi-sign/actions/runs/33420378497)
  on `main` @ `ef851d6`: `backend` ✓, `frontend` ✓, `service` ✓, `e2e` ✓.
- **The job can fail, and that was proven on real runs, not argued.** Run
  [33419949879](https://github.com/pumasi-ai/pumasi-sign/actions/runs/33419949879)
  (`proof/service-break`): `service` **failure** while `backend`, `frontend`
  and `e2e` all succeeded. Run
  [33419950651](https://github.com/pumasi-ai/pumasi-sign/actions/runs/33419950651)
  (`proof/service-unbuilt`): `service` **failure** on a tree with no build
  step — the exit-0-having-run-nothing trap (L-006), caught by the guard.
- `CLAUDE.md` now opens with *"there are two backends"*, names the worker as
  what serves `sign.pumasi.ai`, and carries Q-018 part (c) as a sentence
  rather than by deleting a job.

**Retired, not deleted, and what is carried forward:** Q-018 itself stays open
— nothing was deleted, the domain was not re-pointed, no data moved, and
*which tree is the product* is untouched. Two successors are in the order
above: the gate half this never covered was **the old item 2**, delivered at
`d18d534` and retired directly below; and the thinness of what the new job
runs is **item 2** (it was item 1 through the third reorder, then item 3; the two
deliveries at `3d01198` and `f7c8d03` are why it moved).

**~~Item 1(a): the `BETA` chip, and 1(c): the uncited competitor pricing~~ —
merged 2026-08-31 at `a49f594`** (coder job `0026`, under `spec/0001`).
Verified at `ef851d6`:

- **(a)** `LandingView.vue` no longer writes a rung. `frontend/src/stage.ts`
  exports `STAGE = "alpha"` as the single constant, with `STAGE_LABEL` and
  `STAGE_BADGE` derived from it by expression; the template renders
  `{{ STAGE_BADGE }}` and `in active {{ STAGE_LABEL }}`. The register stays
  `roadmap/STAGE.md` and frozen case **A-001** fails the build if the two move
  apart — L-007 closed by a gate rather than by a copy nobody checks.
- **(c)** the comparison table's figures now match
  [`MARKET.md`](MARKET.md) §1's cited pricing rows (DocuSign $11 / $30 / $45
  with the 5-per-month and 100-per-user-per-year limits; SignWell $10–$12 per
  **sender** and $30–$36 for three senders), read from each vendor's own page
  on 2026-08-31. The shipped `$25 – $65` and `$10 – $30` are gone, and
  `MARKET.md` — which did not exist at the last reorder — now does. Frozen
  cases **A-003** and **A-004** parse the figures and plan names out of
  `MARKET.md` at test time, so neither can fork from the file it checks.

Half (b) and the deploy (d) are **not** retired; they are B1 above.

---

Not copied, on purpose: plan-gating/upsell surfaces (Pumasi Sign is unmetered —
that is the pitch), SMS-delivery premium gating, payment fields, enterprise
admin consoles (permission profiles, CORS, API usage).
