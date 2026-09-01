# BACKLOG — what gets built next, in order

**Owned by the product-manager role** ([`pumasi-ops/roles/product-manager.md`](https://github.com/pumasi-ai/pumasi-ops/blob/main/roles/product-manager.md), duty 5).
First pass 2026-08-30, steward-directed: *"introduce very similar UI and UX
[to the incumbent] in pumasi sign — let these items in the queue."*
**Reordered 2026-09-01 (sixth reorder)** after the product evaluation that
re-measured this file against `main` @ `2471a29` **and against the deployed
build**; the reasoning is in that commit's message, and the steward vetoes by
reverting.

One list, features and bugs together, because a priority that cannot compare
them is not a priority. Every entry points at its source and carries one line
of why-here. **The top of this file is what the project manager's next coder
packet builds.**

## Why this reorder exists

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
  router table and `gap-*` classes.
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

**1 · The envelope-settings dialog silently deletes the sender's message to
signers** — source: coder job `0065`'s hand-off (`spec/0007` §S9a), verified
independently here against the **deployed** build.

**The defect, in three lines that sit next to each other.** The settings dialog
PATCHes three fields and no others; the worker treats an absent `message` as a
request to clear it, while treating an absent `title` as a request to keep it.

Served `EnvelopeDetailView-C4VlFBtA.js`, extracted from `sign.pumasi.ai` at
2026-09-01 02:02 UTC:

```js
patch(`/submissions/${e}`,{expires_at:t,reminders_enabled:U.value,reminder_interval_days:dt.value}),
z.value=!1,S.toast(`Envelope settings updated.`)
```

`service/src/durable.ts`, the PATCH handler, at the deployed commit `0e26917`
(`:1209`–`:1211`) and unchanged in substance at `2471a29`:

```ts
`UPDATE submissions SET title = ?, message = ?, updated_at = ? WHERE id = ?`,
String(body.title ?? sub.title).slice(0, 200),
body.message != null ? String(body.message).slice(0, 2000) : null,
```

**`title` has `?? sub.title`. `message` has no counterpart.** Job `0065` drove
it through the Durable Object harness at `2471a29`:
`message BEFORE: "Please sign by Friday."` → `PATCH` → `200` →
`message AFTER: null`.

**Why this is item 1 and not item 5.**

- **It is live.** `git log -S` puts the line's introduction at a single commit,
  `c2b674e`, with no change since, so it is in the deployed build and on `main`
  alike. Unlike every other defect this file has ranked in the last three
  reorders, no deploy is needed to expose it and none would fix it.
- **It destroys user content, silently, and reports success.** The sender's
  message to signers is the covering note on an agreement. It is shown to every
  recipient (`durable.ts:1418` returns it on the token view) and it is gone
  after any use of a dialog whose own toast says *"Envelope settings
  updated."* Nothing in the UI says the message was touched, and nothing asks.
- **The dialog is the one the product tells senders to use.** A past-due
  envelope's detail page reads *"Its expiration date has already passed — set a
  new one"* and draws the pencil that opens this dialog. So the product invites
  the sender into the exact action that deletes their message.
- **And it gets worse the moment `2471a29` deploys, not better.** Today the
  dialog discards the deadline too, so a sender who used it achieved nothing
  and lost their message. After the deploy the deadline saves — which means
  senders will be *encouraged* to use the dialog, and each use will still wipe
  the message.

**What this entry does and does not decide.** The repair is small and is the
coder's to shape; the obvious form is `body.message !== undefined ? … :
sub.message`, matching `title`'s idiom on the line above, with an explicit
`null` still meaning *clear it*. **This entry does not authorise widening the
settings dialog** to send `message`, which would be a different change with a
UI cost. It also does not decide whether the `corrected` audit row should
record a message change; `2471a29` added a `changed` list to that row, and
whichever way the fix goes it should appear there.

**A frozen case belongs with it.** Item 2's suite already drives the PATCH
route through `test/support/durable-harness.ts`, so the case is cheap: set a
message, PATCH settings only, assert the message survives. **Not `can_hurt`
under CHARTER Part 4 on this seat's reading** — it repairs a destructive write
rather than creating one — but this repository has no `RISK_ZONES.yaml`
(item 5), so Part 4's *unmapped defaults to `can_hurt`* applies and the packet
should plan for the 7-day window rather than discover it at the gate.


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

- ~~"both assertions are against one file"~~ — **five** files now; three of
  them drive routes against a real Durable Object.
- ~~"`durable.ts` … covered by nothing"~~ — sessions and the envelope surface
  are covered.
- ~~"`worker.ts` is covered by nothing"~~ — **retired at `2471a29`**, which is
  the first assertion in this repository's history to drive the entrypoint.
  **A-415** reaches the single Durable Object through `scheduled()`, proves the
  throw is load-bearing, and proves the sweep's internal path is closed to the
  internet.

**One sentence survives verbatim, re-checked in the tree at `2471a29` by this
evaluation:**
`e2e-workflow.test.ts` **is still not an end-to-end test of anything.** Its
imports are `node:test`, `node:assert/strict`, `pdf-lib` and
`stampAndCertifyPdf` — identical to `stamping.test.ts` — and it calls no route,
starts no worker and touches no store. The file *name* over-states what it
does, and `# pass 28` in a release note will be over-read exactly as `# pass 2`
was. Renaming it is a five-minute honesty fix and belongs in whichever packet
takes this item. **Note what `2471a29` did *not* change about it:** that release
added a genuine worker-level test in a different file and left this one's name
alone, so the misnomer is now surrounded by the thing it claims to be.

**What is left, and a packet should say which strand it takes.**

- **Named first slice — the OAuth callback, which is where job `0050`'s
  proposal 5 lives.** Verified by the fourth evaluation at `service/src/durable.ts:766`; `0058` moved
lines in this file, so the number is **carried, not confirmed** — the guard
itself was re-read and is unchanged:
  the guard is `claims.email_verified === false`, so an `id_token` that
  **omits** the claim passes. Stated at the strength the evidence supports and
  no higher: this is on an **uncovered branch**, proposed from source with no
  test exercising it, and the code takes the token directly from the provider's
  token endpoint over TLS (the comment at `:757`–`:758` says so), which is real
  mitigation. It is *security-shaped on a live auth path*, not a demonstrated
  vulnerability, and this seat is **not** asserting it is exploitable. That is
  precisely why it ranks as the first slice here rather than as its own
  `priority: high` entry: **the cheap next step is the covering test**, which
  is what job `0050` suggested as a `priority: medium` packet (the OAuth
  branch, token endpoint stubbed). If the test shows a real admission path, it
  is promoted out of this entry on that evidence.
- Covered by nothing, re-checked: `worker.ts`, `storage/r2.ts`, `mail.ts`,
  `feedback.ts`, `convert/graph.ts`; and inside `durable.ts` — envelope
  creation, correction and copy, templates, admin, every file route, and
  `finalize`'s stamping branch.
- **The integration suite still drives the wrong tree.**
  `frontend/playwright.config.ts:63` boots `uvicorn app.main:app` locally, or a
  container from the root `Dockerfile` in CI — `backend/`, both times.
  Unchanged, and now the single largest thing in this entry.

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

**Why it ranks seventh and not higher — the packet asked for this reasoning
here, so here it is.**

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
   long feature run — which is why it sits immediately above item 8, where the
   parity mandate resumes and several entries will be `can_hurt`.

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
   exercise `core/stamping.ts` only"*.** At `2471a29` it holds **five**:
   `stamping`, `auth-session`, `envelope-lifecycle`, `e2e-workflow` and
   `envelope-expiry`. Three of them drive a real Durable Object through
   `service/src/test/support/durable-harness.ts`, and A-415 drives
   `service/src/worker.ts`. **The sentence understates coverage, which is the
   direction that reads as conservative and is still false** — an agent told
   the suite tests one file will not think to check whether its change is
   already covered.
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
