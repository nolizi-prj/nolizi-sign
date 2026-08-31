# BACKLOG — what gets built next, in order

**Owned by the product-manager role** ([`pumasi-ops/roles/product-manager.md`](https://github.com/pumasi-ai/pumasi-ops/blob/main/roles/product-manager.md), duty 5).
First pass 2026-08-30, steward-directed: *"introduce very similar UI and UX
[to the incumbent] in pumasi sign — let these items in the queue."*
**Reordered 2026-08-31 (second reorder)** after the product evaluation that
re-measured this file against `main` @ `ef851d6`; the reasoning is in that
commit's message, and the steward vetoes by reverting.

One list, features and bugs together, because a priority that cannot compare
them is not a priority. Every entry points at its source and carries one line
of why-here. **The top of this file is what the project manager's next coder
packet builds.**

**That last sentence is now load-bearing, and it is why this reorder exists.**
The previous top two entries were both stale: item 1 ranked pending in full
though halves (a) and (c) merged at `a49f594`, and item 2 was delivered at
`ef851d6`. Worse, what remained of item 1 was **not a build** — (b) waits on
`pumasi/DECISIONS.md` **Q-021** and (d) is a deploy, **Q-012** — so a coder
packet taking the top of this file would have delivered nothing. Entries that
no coder may execute are no longer in the numbered order; they are in
[Blocked](#blocked--not-in-the-build-order-until-a-steward-answers) below, and
the numbered order is again a list of things somebody can build tomorrow.

Context the ordering assumes: UX-parity phase 1 is **delivered** (PR #1, merged
`70c692e`). The parity source of truth is the clean-room spec
[`docs/ux/incumbent-ux-spec.md`](../docs/ux/incumbent-ux-spec.md) (§ refs
below) with the phase map in
[`docs/ux/similar-ux-plan.md`](../docs/ux/similar-ux-plan.md). **Builders work
from the spec, never from the tour screenshots** (product-hunt `TOUR.md`,
"Studying clean").

**Why the parity items are still down at 8.** They did not lose their mandate.
Six items were in front of them at the last reorder; two of those six are now
retired, two arrived from coder job `0032`, and one moved into Blocked. The
count is unchanged and so is the reason: each of items 1–7 is either something
a real user met, something a rule requires, or the thing that makes an "it
works" claim below it checkable. Each is small. The parity work resumes at
item 8 and is otherwise untouched.

---

## The order

**1 · #7: "sign in again" sends the user to a raw 404 — the cause, measured** —
source: issue [#7](https://github.com/pumasi-ai/pumasi-sign/issues/7)
(`accepted`, `priority: high`). **This entry was "reproduce it"; it is now
"here is the cause".** `SignedOutView.vue:26` renders *Sign in again* as
`<a :href="signInUrl">`, and `signInUrl` is `loginRedirectUrl("/")` =
`/api/auth/login?next=%2F` (`utils/http.ts:30`) — a full-page navigation, not
a router push. Measured against the deployed tree on 2026-08-31:

```
$ curl -s -i 'https://sign.pumasi.ai/api/auth/login?next=%2F'
HTTP/2 404
{"error":"Endpoint not found"}
```

So the user is handed the worker's error JSON, rendered raw in the browser.
**`GET /api/auth/login` is a `backend/` route** — `backend/app/routers/auth.py:82`
is `@router.get("/login")` under prefix `/api/auth` — and the worker defines
**no** `GET` under `/api/auth/login` at all: `service/src/durable.ts` has only
`POST /api/auth/login/request` (`:775`) and `POST /api/auth/login/verify`
(`:798`). The SPA calls a route that exists only in the tree nobody reaches.

**Every CI job was green on this bug, and one of them was green *because* of
it.** Run 33420378497 at `ef851d6` is `backend` ✓, `frontend` ✓, `service` ✓,
`e2e` ✓ — while the button 404s in production. The `e2e` job is the reason to
care: `frontend/playwright.config.ts` boots `uvicorn`, or in CI a Docker image
built from the root `Dockerfile`, and both are **`backend/`** — the one tree in
which `GET /api/auth/login` exists. So the six Playwright specs exercise a
sign-in path that works, on a server no user reaches, and would keep passing
however long this defect stayed live. That is L-006 and L-009 in one artefact,
and it is item 4's strongest argument.

Why here: it is the only `priority: high` defect that is **live, on the entry
path, and buildable today** — the other one, #8, is Blocked. A signed-out user
who cannot get back in is the plainest counterexample to the next stage's
whole promise, and the cause is no longer a mystery to be budgeted for. It is
also **[L-009](https://github.com/pumasi-ai/governance/blob/main/lessons/L-009-two-paths-one-claim.md)
in this product for the third time** (after Q-018's `dev-login` 404 and its
`establishSession` domain-gate divergence): the frontend was written against
`backend/`, and `backend/` is not what serves users. Which of the two repairs
is right — point the button at `loginPageUrl("/")`, the SPA `/login` page that
already exists one function below it in the same file, or add the missing
route to the worker — is the coder's call with a spec, and it decides whether
the fix lands in `frontend/` or in `service/`. **If it lands in `service/`,
item 2 below covers it and item 2 should ride in the same packet.**

**2 · Make `GATE: PASS` cover the tree users actually meet** — source: coder
job `0032`'s `SUGGESTED_NEXT_TASKS` (`priority: high`), `pumasi/DECISIONS.md`
**Q-025** rider (a), [`STAGE.md`](STAGE.md) §2.1. **CI now runs the served
tree; the merge gate still does not.** Re-measured 2026-08-31, not inherited:
`pumasi/tools/gate.sh:25` is `if npm test; then echo "   tests: PASS"`, and
this repository's root `package.json` `test` script is exactly
`cd frontend && npm run test:unit && npx vue-tsc -b --force`. The string
`service` occurs **zero** times in that script and zero times in `gate.sh`. So
a coder can print `GATE: PASS` here having run zero service tests — on the
only tree that answers `sign.pumasi.ai`.

**And the gate is the whole gate.** Measured this tick:
`GET /repos/pumasi-ai/pumasi-sign/branches/main/protection` → **404 "Branch
not protected"**. The `service` CI job reports; it blocks nothing. Between a
change and `main` there is one check, it is run by hand by the author, and it
does not run the deployed tree's suite. That is Q-025's question — *is
`GATE: PASS` an agent's own report?* — in its sharpest form in the fleet, and
it is sharper here than on `pumasi-booking` because here CI **does** run the
served tree and the gate still does not.

Why here rather than at 1: the same sentence that put the old item 2 above the
old item 3 no longer holds. When CI covered `service/` with nothing, an
ungated suite meant the code was untested; now CI runs it on every push, so
the backstop exists and this entry is about what a *string in a release note*
evidences, not about whether production code is exercised. That is real and it
is one rung below a user who cannot sign in. Scope: the root `package.json`
`test` script, plus whatever `service` needs to be runnable from the root
(`npm ci` and `npm run build` in `service/` before `npm test` — `dist/` is
`.gitignore`d, which is the trap `.github/scripts/assert-service-suite-ran.sh`
and frozen case A-103 exist for). **Do not shrink the frontend half to make
room.** Left alone by `0032` on purpose: the **old** BACKLOG item 2 (now
Retired) and Q-018(b) both said
*"CI gains a job"* in those words, and the root `package.json` was authored one
commit earlier under `spec/0001`'s scope.

**An objection to this entry sitting at 2 rather than 1, recorded because it is
a good one.** A cross-family review of this ranking (gemini, the one family
answering — see [`STAGE.md`](STAGE.md) §0) argued for swapping: that calling CI
a "backstop" over-claims when branch protection is absent, and that item 1 is
*caused* by this gap, so fixing #7 first means pushing a hotfix through the
pipeline that produced it. **The first half lands and the wording above was
written to concede it.** The second half does not survive checking, and
checking it found something worse: this entry's fix is the root `test` script
running `service`'s suite, and that suite could be *complete* and still not
catch item 1, which is a frontend `href` pointing at a route the worker lacks.
The suite that should have caught it — `e2e` — passes, because it drives
`backend/`. Nothing in the current four jobs could go red on item 1. So the two
entries are not cause and effect; they are two different holes, and the one
with a user standing in it goes first. The tiebreak that settles it: if a
packet takes only the top item and stops, ordering this first leaves a user
unable to sign in for another cycle, while ordering #7 first leaves one merge
cycle whose gate evidence is weaker than it should be — on a branch where CI
still *reports*, even though it does not block. The first is worse.
**Both entries say it in their own text: take them in one packet.**

**3 · #6: the colour buttons touch — on three views, not one** — source: issue
[#6](https://github.com/pumasi-ai/pumasi-sign/issues/6) (`accepted`,
`priority: normal`). Re-measured at `ef851d6` and **wider than this entry
previously recorded**. This frontend has no Tailwind — Vuetify `^3.13.0` only,
whose utility is `ga-*`; `.ga-2` is in `vuetify.css` and `.gap-2` is not
(counted: 1 and 0). Inert `gap-*` classes are in **three** views:

- `BrandingView.vue:113`, `:128`, `:142` — the reported surface.
- `LoginView.vue:119` — **not previously listed**, and it is the sign-in page,
  the same surface item 1 is about.
- `LandingView.vue` (`:41`, `:48`, `:53`, `:90`) — these *do* render, because
  that file defines `.gap-2/.gap-3/.gap-4` in its own `<style scoped>` block
  (`:260`–`:262`). Left alone or converted for consistency; the coder's call.

Why here: three characters per site, a real user noticed, and `LoginView.vue`
means it now **ships free alongside item 1**, which is already in that file's
neighbourhood.

**4 · Test the deployed tree beyond its PDF stamper** — source: coder job
`0032`'s `SUGGESTED_NEXT_TASKS` (`priority: high`), `pumasi/DECISIONS.md`
**Q-018**, [`STAGE.md`](STAGE.md) §2.1, `CLAUDE.md` (*"test coverage here is
thin and you should know it before you trust it"*). Both service test files
were **read in full** this tick rather than counted, and the finding is worse
than "two tests":

- `service/src/test/stamping.test.ts` (89 lines) and
  `service/src/test/e2e-workflow.test.ts` (107 lines) have **identical import
  lists**: `node:test`, `node:assert/strict`, `pdf-lib`, and
  `stampAndCertifyPdf` from `../core/stamping.js`. Nothing else. They are two
  builds of the same scenario against the same pure function.
- **`e2e-workflow.test.ts` is not an end-to-end test of anything.** It calls
  no route, starts no worker, touches no store. A reader of the file *name* —
  or of `STAGE.md`'s table row — will over-read the coverage, and this
  evaluation nearly did.
- Both assert **shape, not content**: stamped bytes longer than original, page
  count 2, two 64-char hex hashes, and `notEqual(originalHash, completedHash)`.
  No assertion that a signer's name, a date or a checkbox value reached the
  page. `notEqual` on the hashes passes for *any* mutation, including a wrong
  one.
- Covered by nothing: `durable.ts` (sessions, envelopes, signing, the whole
  API surface, and the `establishSession` domain gate Q-018 flags as diverging
  from `backend/`), `worker.ts`, `storage/r2.ts`, `mail.ts`, `feedback.ts`,
  `convert/graph.ts`.
- **And the suite that would cover a route points at the wrong tree.**
  `frontend/playwright.config.ts` boots `uvicorn` locally, or in CI a Docker
  image built from the root `Dockerfile` — `backend/`, both times. The six e2e
  specs therefore assert that a *FastAPI* server signs users in. Item 1 is the
  proof that this is not a theoretical complaint: those specs are green on a
  live production 404. **This is a third thing, distinct from the two above** —
  the unit suite is thin, the merge gate does not run it, and the integration
  suite drives the wrong server — and a packet on this item should say which of
  the three it is taking.

Why here: now that the `service` CI job exists, *"the tests pass"* finally says
something about production — and what it says is "the PDF stamper works". This
entry decides how much more it should say. Ranked below items 1–3 because it is
the only one of the four that is days rather than characters, and CLAUDE.md
correctly calls widening it this file owner's call rather than a side errand.
Suggested first slice, so a packet has a shippable edge: `establishSession`'s
account-creation rule (the Q-018 divergence, and the one with a live user
consequence), then session validation, then envelope state transitions.

**5 · The feedback screenshot must be attached, not pre-attached** — source:
`PRODUCT-RULES.md` **PR-2** (v1.0, read fresh this packet from `pumasi` branch
`worktree-product-rules` `0115758`; still not on `pumasi` main — that is
**Q-017**, and absence from main is not compliance), CHARTER §5.2.
Re-checked at `ef851d6` and **unchanged**: opening the dialog sets a fallback
canvas as the attachment immediately (`FeedbackDialog.vue:185`–`188`,
`screenshotIsAuto.value = true`) and then replaces it asynchronously with a
real `html2canvas(document.body)` capture (`:193`–`:197`). The user presses
nothing. PR-2 says *"a screenshot travels only when the user attaches one"*.
The user sees it and can remove it (`removeScreenshot`, `:201`), so today this
is opt-out and informed — but in an e-signature product the page being
captured is somebody's contract, and §5.2 says *never the user's own material*.
Make it a button the user presses. Why here: PR-2 binds at the `beta`
promotion, this is the only clause it fails, and it is cheaper to fix now than
to hold a promotion for.

**6 · One version number, and put it in the reports** — source:
`PRODUCT-RULES.md` **PR-1**, which binds *always, from the first commit*, and
is not met. **Narrowed since the last reorder**: a root `package.json` now
exists (authored under `spec/0001` for `gate.sh`), so the missing piece is no
longer the file. Measured at `ef851d6`: the root `package.json` carries **no
`version` field** — deliberately, and it says so in its own `description`, to
avoid taking this item inside a packet scoped to something else;
`frontend/package.json` reads `0.0.0` and `service/package.json` reads `0.1.0`
(two hand-maintained copies — L-007); no version is visible to a user anywhere
in the SPA; there is no `/version` endpoint; and `FeedbackDialog.vue::buildContext`
(`:105`–`:122`) sends **thirteen** fields — page, URL, user, browser, platform,
language, timezone, viewport, screen, network, time, cores, device memory — and
not the version. Why here: all five open issues are defect reports without a
version, which is a request to guess, and the fix is one source of truth plus
two readers. Note it rides naturally with item 2, which is already editing the
root `package.json`.

**7 · A settings shell, with branding inside it** — source: issue
[#5](https://github.com/pumasi-ai/pumasi-sign/issues/5) (`accepted`,
`priority: normal`); pulled out of item 17 (spec §8), which keeps the rest.
There is no `settings` route and `/branding` is top-level
(`router/index.ts:70`, `App.vue:50`). Ship the shell and move branding under
it; the account defaults, notification preferences and retention controls that
fill it stay in item 17. Why here: it is the container every later
settings-shaped item needs, and shipping it early stops each of them inventing
its own home.

**8 · Focus-mode shells for prepare / tag / sign** — source: spec §1
(shell 2). Full-screen wizard and signing surfaces: global chrome hidden,
minimal header with close-X (back to origin), step title, primary actions
top-right. Why here: the single largest *perceptual* gap to the incumbent —
every send and every signature passes through these screens. **This is where
the steward-directed parity mandate resumes.**

**9 · One-page accordion envelope setup** — source: spec §4 step 1,
checklist 8. Documents / recipients / message as three collapsible sections on
one page; inline validation on attempted progression; implicit drafts on
close. Replaces paged steps 1–2. Why here: with #8 it completes the incumbent's
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
Reports section. **The settings *shell* was pulled out as item 7**; this is
everything that goes inside it. Retention here is also what
[`STAGE.md`](STAGE.md) §2.4 needs to make a data-survival claim citable. Why
here: nothing user-visible upstream depends on it.

**18 · Onboarding polish** — source: spec §2, §9, checklist 15. First-run coach
marks per surface; persistent "n/5" getting-started checklist (banner + modal,
live progress). Why last: worth doing only once the surfaces it teaches
(items 7–11) are in their final shape.

---

## Blocked — not in the build order until a steward answers

Entries here have real work left, and **no coder may execute it today**. They
are out of the numbered list rather than sitting at its top, because the top
of that list is what the next coder packet builds, and a packet that takes an
entry nobody may execute delivers nothing. They come back into the order the
day their window closes, at whatever rank they then deserve.

**B1 · Make the landing page's licence claim true, then let users have it** —
source: issue [#8](https://github.com/pumasi-ai/pumasi-sign/issues/8)
(`accepted`, `priority: high`), [`STAGE.md`](STAGE.md) §2.3.
**This is what is left of the old item 1** after halves (a) and (c) were
delivered at `a49f594` (see Retired). Both remaining halves are steward-held
and **neither is released by CHARTER Part 0**:

- **(b)** *"Apache-2.0 (Open Source)"* is still on the page — the banner
  (`LandingView.vue:43`), the hero strip (`:80`) and the comparison table's
  License row (`:210`) — and this repository still carries no `LICENSE`.
  **`pumasi/DECISIONS.md` Q-021**, open; its named default is to add
  Apache-2.0 byte-identical to `pumasi-web/LICENSE`, **and nobody has taken
  it** — `pumasi-web` marketing job `0035` raised exactly that to the steward
  at 12:58 on 2026-08-31. Adding a licence is an outward grant a third party
  may rely on, which is why Part 0's reversibility rule does not release it.
  Frozen case `spec/0001` **A-005** pins those three strings byte-identical to
  `10a523d` and **retires with Q-021** — whichever way that entry lands, A-005
  is updated or deleted in the same commit.
- **(d)** then deploy — `wrangler deploy` from `service/`, **not** the Railway
  path (Q-018). **`pumasi/DECISIONS.md` Q-012**, open and explicitly outside
  Part 0's proceed-on-default rule. This entry does not ask for the deploy and
  does not schedule it; it records that #8 closes on one. Note the same deploy
  would carry ~6 commits of otherwise-unreviewed change; it should be
  deliberate, not incidental.

**Verified undeployed again this tick, not inherited from job `0024`.** The
live bundle filename is unchanged, which is itself the finding:

```
$ curl -s https://sign.pumasi.ai/ | grep -o '/assets/[^"]*\.js'
/assets/index-j38Qwibz.js
$ curl -s -o idx.js -w '%{http_code} %{size_download}\n' \
    https://sign.pumasi.ai/assets/index-j38Qwibz.js
200 839941
$ grep -oic 'landing' idx.js
0
```

Zero occurrences of `landing`, `LandingView` or `Apache-2.0` in 839 941 bytes.
This is a **stronger** measurement than a missing component chunk would be:
`router/index.ts:16` registers the route eagerly as `name: "landing"` and
lazy-loads only its component, so the route *name* would be in the main bundle
even if the view were code-split — and `index.html` preloads no other chunk.
The route is not in the deployment at all.

---

## Retired

**~~Green main: fix the 4 backend pytest failures~~ — met 2026-08-31.** Was
item 1. CI run
[33410370102](https://github.com/pumasi-ai/pumasi-sign/actions/runs/33410370102)
at `5cb3bf8`: `backend` ✓, `frontend` ✓, `e2e` ✓ (coder job `0018`; the four
failures were single-tenant expectations against multi-tenant normalization,
`1c8590d`, and `e2e` had two further causes, `5cb3bf8`). Retired rather than
deleted, with one thing carried forward: **that gate covers `backend/`, which
is not what users reach.** The re-sourced version of this entry's purpose —
*a gate whose green means something* — became the old item 2, retired directly
below, whose own successor is item 2 of the current order.

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
above: the gate half this never covered is **item 2**, and the thinness of
what the new job runs is **item 4**.

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
