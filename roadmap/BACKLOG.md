# BACKLOG — what gets built next, in order

**Owned by the product-manager role** ([`pumasi-ops/roles/product-manager.md`](https://github.com/pumasi-ai/pumasi-ops/blob/main/roles/product-manager.md), duty 5).
First pass 2026-08-30, steward-directed: *"introduce very similar UI and UX
[to the incumbent] in pumasi sign — let these items in the queue."*
**Reordered 2026-08-31 (third reorder)** after the product evaluation that
re-measured this file against `main` @ `d18d534`; the reasoning is in that
commit's message, and the steward vetoes by reverting.

One list, features and bugs together, because a priority that cannot compare
them is not a priority. Every entry points at its source and carries one line
of why-here. **The top of this file is what the project manager's next coder
packet builds.**

**This reorder exists for the same reason the last one did, and that is the
point.** The previous top two entries — #7's raw 404 and the merge gate that
did not run the served tree — were **both delivered in one packet** at
`d18d534` (coder job `0037`, `spec/0003`, release note
[`2026-08-31-pumasi-sign-sign-in-again.md`](https://github.com/pumasi-ai/pumasi/blob/main/releases/2026-08-31-pumasi-sign-sign-in-again.md),
`pumasi/DECISIONS.md` **Q-027**), exactly as both entries' own text asked. They
are in [Retired](#retired) below, with what this evaluation verified itself
rather than what the job reported. Until this commit nothing in this repository
said what a coder should build next on this product; **that entry is now item 1
and it is named as such.**

**One substantive change of rank, not a shift-up.** The old item 4 — widening
the deployed tree's tests — moves from fourth to first, past three entries that
were ahead of it. The reason is what item 2's delivery *did*: the root
`npm test` now prints `# pass 2 · # fail 0` from `service/`, so `GATE: PASS`
on this repository carries a number about production for the first time, and
that number is **2**, both assertions against one file. Every release note from
here quotes it. See item 1. The rest keep their relative order.

Context the ordering assumes: UX-parity phase 1 is **delivered** (PR #1, merged
`70c692e`). The parity source of truth is the clean-room spec
[`docs/ux/incumbent-ux-spec.md`](../docs/ux/incumbent-ux-spec.md) (§ refs
below) with the phase map in
[`docs/ux/similar-ux-plan.md`](../docs/ux/similar-ux-plan.md). **Builders work
from the spec, never from the tour screenshots** (product-hunt `TOUR.md`,
"Studying clean").

**Why the parity items are now at 6.** They did not lose their mandate and they
did not move: two entries left the front of this list by being built, so the
count in front of them fell from seven to five. Each of items 1–5 is either
something a real user met, something a rule requires, or the thing that makes
an "it works" claim below it checkable. The parity work resumes at item 6 and
is otherwise untouched.

---

## The order

**1 · Test the deployed tree beyond its PDF stamper — the highest build entry**
— source: coder job `0032`'s `SUGGESTED_NEXT_TASKS` (`priority: high`),
`pumasi/DECISIONS.md` **Q-018** and **Q-025**, [`STAGE.md`](STAGE.md) §2.1,
`CLAUDE.md` (*"test coverage here is thin and you should know it before you
trust it"*). **This is what the next coder packet takes.**

**Why it moved to the top, measured this tick and not inherited.** The entry
above it was delivered, and delivering it is what promoted this one. The root
`npm test` — step 1 of `pumasi/tools/gate.sh`, and with `main` unprotected the
whole gate — now installs, builds and runs `service/`'s suite. Run by this
evaluation at `d18d534`:

```
Test Files  6 passed (6) · Tests  85 passed (85)
# pass 2 · # fail 0
assert-service-suite-ran: 2 passing, 0 failing, from 2 compiled
```

So `GATE: PASS` here now carries a number about the tree that answers
`sign.pumasi.ai` — and the number is **2**. Both assertions are against one
file. The release note that shipped the gate says so in its own words: *"the
gate no longer reports a number that excludes production — not that production
is now well covered."* Making that number mean something is now the
highest-leverage build on this product, because every release note and every
stage claim from here quotes it.

Both service test files were **read in full** at `d18d534` rather than counted,
and the finding is worse than "two tests":

- `service/src/test/stamping.test.ts` and `service/src/test/e2e-workflow.test.ts`
  have **identical import lists**: `node:test`, `node:assert/strict`, `pdf-lib`,
  and `stampAndCertifyPdf` from `../core/stamping.js`. Nothing else. They are
  two builds of the same scenario against the same pure function.
- **`e2e-workflow.test.ts` is not an end-to-end test of anything.** It calls no
  route, starts no worker, touches no store. A reader of the file *name* — or of
  a `# pass 2` in a release note — will over-read the coverage.
- Both assert **shape, not content**: stamped bytes longer than original, page
  count 2, two 64-char hex hashes, and `notEqual(originalHash, completedHash)`.
  No assertion that a signer's name, a date or a checkbox value reached the
  page. `notEqual` on the hashes passes for *any* mutation, including a wrong
  one.
- Covered by nothing: `durable.ts` (sessions, envelopes, signing, the whole API
  surface, and the `establishSession` domain gate Q-018 flags as diverging from
  `backend/`), `worker.ts`, `storage/r2.ts`, `mail.ts`, `feedback.ts`,
  `convert/graph.ts`.
- **And the suite that would cover a route points at the wrong tree.**
  `frontend/playwright.config.ts` boots `uvicorn` locally, or in CI a Docker
  image built from the root `Dockerfile` — `backend/`, both times.

**#7 is now the proof rather than the argument.** The old item 1 was a live
`404` on the sign-in path, and **no job in this repository could have gone red
on it**: `service`'s two tests do not touch routing, and the six Playwright
specs drive the one tree where the missing route existed. Re-checked by this
evaluation at `d18d534`: run
[33430138500](https://github.com/pumasi-ai/pumasi-sign/actions/runs/33430138500)
is `backend` ✓ `frontend` ✓ `service` ✓ `e2e` ✓ — and the defect is **still
live in production** (item 1's fix is merged and undeployed; see
[Blocked](#blocked--not-in-the-build-order-until-a-steward-answers) and
[`STAGE.md`](STAGE.md) §5). A green estate over a live defect is the whole of
this entry's case.

**Three distinct things, and a packet should say which it takes:** the unit
suite is thin, the merge gate's number is two, and the integration suite drives
the wrong server. Suggested first slice, so a packet has a shippable edge:
`establishSession`'s account-creation rule (`service/src/durable.ts:655` — the
Q-018 divergence, and the one with a live user consequence), then session
validation, then envelope state transitions. **Boundary the packet must
respect:** a test that *records* what the worker does today is ordinary work; a
test written to assert that the worker's account rule is the *correct* one
would be answering Q-018, which is the steward's. Characterize, do not adjudicate.

**2 · #6: the colour buttons touch — on three views, not one** — source: issue
[#6](https://github.com/pumasi-ai/pumasi-sign/issues/6) (`accepted`,
`priority: normal`). Re-measured at `d18d534` and unchanged from the last
reorder. This frontend has no Tailwind — Vuetify `^3.13.0` only, whose utility
is `ga-*`; `.ga-2` is in `vuetify.css` and `.gap-2` is not (counted this tick:
1 and 0). Inert `gap-*` classes are in **three** views:

- `BrandingView.vue:113`, `:128`, `:142` — the reported surface.
- `LoginView.vue:119` — the sign-in page.
- `LandingView.vue` (`:41`, `:48`, `:53`, `:90`) — these *do* render, because
  that file defines `.gap-2/.gap-3/.gap-4` in its own `<style scoped>` block
  (`:260`–`:262`). Left alone or converted for consistency; the coder's call.

Why here: three characters per site and a real user noticed. **The free ride
this entry used to claim is spent, and that is recorded rather than left to
look like inaction.** The last reorder ranked it here partly because
`LoginView.vue` would ship alongside the #7 fix; `d18d534` touched
`SignedOutView.vue` and `utils/http.ts` and **not** `LoginView.vue`, so the fix
is now standalone. It stays at 2 anyway: it is the smallest entry in the file
and the only remaining one a user reported and can see.

**3 · The feedback screenshot must be attached, not pre-attached** — source:
`PRODUCT-RULES.md` **PR-2** (v1.0, read fresh this packet from `pumasi` branch
`worktree-product-rules` `0115758`; **still not on `pumasi` main** — that is
**Q-017**, now flagged by five consecutive evaluations, and absence from main
is not compliance), CHARTER §5.2.
Re-checked at `d18d534` and **unchanged**: opening the dialog sets a fallback
canvas as the attachment immediately (`FeedbackDialog.vue:185`–`188`,
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
is not met. Measured at `d18d534`: the root `package.json` carries **no
`version` field**; `frontend/package.json` reads `0.0.0` and
`service/package.json` reads `0.1.0` (two hand-maintained copies — L-007); no
version is visible to a user anywhere in the SPA; there is no `/version`
endpoint; and `FeedbackDialog.vue::buildContext` (`:105`–`:122`) sends
**thirteen** fields — page, URL, user, browser, platform, language, timezone,
viewport, screen, network, time, cores, device memory — and not the version.
Why here: all five open issues are defect reports without a version, which is a
request to guess, and the fix is one source of truth plus two readers.

**The cost of this entry went up at `d18d534`, and the note that it "rides
naturally with item 2" is now wrong and is removed.** The root `package.json`
was edited by that commit and its `version` field was **deliberately** left
absent — `spec/0003` froze acceptance case **A-208**, which asserts the absence
precisely so that "a later packet cannot take it in passing"
(`spec/0003/SPEC.md:211`, `:251`). So the packet that takes this item must also
retire or amend A-208 in the same commit, and should say so in its intent.
That is a small, stated cost, not a blocker.

**5 · A settings shell, with branding inside it** — source: issue
[#5](https://github.com/pumasi-ai/pumasi-sign/issues/5) (`accepted`,
`priority: normal`); pulled out of item 15 (spec §8), which keeps the rest.
There is no `settings` route and `/branding` is top-level
(`router/index.ts:70`, `App.vue:50`). Ship the shell and move branding under
it; the account defaults, notification preferences and retention controls that
fill it stay in item 15. Why here: it is the container every later
settings-shaped item needs, and shipping it early stops each of them inventing
its own home.

**6 · Focus-mode shells for prepare / tag / sign** — source: spec §1
(shell 2). Full-screen wizard and signing surfaces: global chrome hidden,
minimal header with close-X (back to origin), step title, primary actions
top-right. Why here: the single largest *perceptual* gap to the incumbent —
every send and every signature passes through these screens. **This is where
the steward-directed parity mandate resumes.**

**7 · One-page accordion envelope setup** — source: spec §4 step 1,
checklist 8. Documents / recipients / message as three collapsible sections on
one page; inline validation on attempted progression; implicit drafts on
close. Replaces paged steps 1–2. Why here: with item 6 it completes the incumbent's
prepare flow shape; touching the wizard once for both avoids rework.

**8 · Tagging-canvas mechanics** — source: spec §4 step 2, checklist 1, 16.
Drag-from-palette with cursor ghost (keep click-to-arm as fallback), zoom
control, undo/redo, field copy/paste, grouped palette; multi-document
envelopes as separate files with per-file thumbnail cards. **Scope is under
`pumasi/DECISIONS.md` Q-016** (issue
[#4](https://github.com/pumasi-ai/pumasi-sign/issues/4), `escalated`): Option A
— cards over the existing upload-time merge, with the combination stated in
the UI *and in the certificate* — is the named default and may proceed
pre-`launched`; Option B (true per-document separation, backend rework) is not
authorized by that default. Why here: the canvas is "the product" per the
spec's own ranking; do it after item 6 so it lands inside the focus shell.

**9 · Signature identity: styles, saved list, frame imprint** — source: spec
§5 adopt modal, §8 signature adoption + framing, checklist 4. Generated styles
from name/initials with live preview, multiple saved signature/initials pairs
in a profile page, and the "signed by" bracket frame + short envelope/party ID
burned into the stamped PDF behind an account toggle (`service/src/core/stamping.ts`;
`backend/app/stamping.py` only if Q-018 keeps that tree). Why here: this is
what makes a signed document *look* like the incumbent's output — the artifact
everyone outside the org actually sees.

**10 · Post-sign share loop** — source: spec §5 finish sequence, checklist 12.
After Finish: share-by-email modal (multi-email chips, prefilled subject, short
message with counter), each recipient getting a tokenized free download link;
declining still completes. Why here: cheap, and it is the incumbent's growth
loop — the commons' S8 outward-transmission thesis for picking this product in
the first place.

**11 · Manager depth: bulk, folders, trash, richer filtering** — source: spec
§3, checklist 7, 21. Row checkboxes + bulk bar (download / move / delete), user
folders, a real Deleted view with restore (soft-delete; archive stays per-user
hide), quick-views dropdown, default date-window chip with inline clear,
two-line rows (title over "To: recipients"), density toggle. Why here:
daily-driver ergonomics once volume grows; none of it blocks the flows above.

**12 · Ceremony options** — source: spec §5, §8 signing settings, checklist 5,
23. Finish-later; configurable consent/disclosure step for remote recipients
(recorded in the certificate); auto-navigation modes (page-only / required /
all). Why here: recipient-facing polish and the compliance-relevant consent
record.

**13 · Field-type parity + per-recipient auth** — source: spec §4 palette,
checklist 17, 18. Email / Company / Title contact fields; Approve / Decline
action buttons; Note; per-recipient "Customize" auth (access code; SMS later).
Payment: explicitly skipped. Why here: each is small and spec-shaped; batch
after the canvas rework so new types land once.

**14 · Template library depth** — source: spec §7, checklist 9. Description
field, favorites, my/shared-with-me groupings, "[Untitled]" implicit drafts,
starter-template gallery. Why here: value scales with template count, which is
still small.

**15 · Admin & records layer** — source: spec §6, §8, checklist 3, 11, 13, 14,
20, 25. Account defaults (reminders/expiration, signing permissions, date/time
regional formats), per-user notification preferences, envelope/document custom
metadata, retention purge, combined-into-one-PDF + zip download, certificate
depth (per-signer viewed timestamps, security level, adoption method), a
Reports section. **The settings *shell* was pulled out as item 5**; this is
everything that goes inside it. Retention here is also what
[`STAGE.md`](STAGE.md) §2.4 needs to make a data-survival claim citable. Why
here: nothing user-visible upstream depends on it.

**16 · Onboarding polish** — source: spec §2, §9, checklist 15. First-run coach
marks per surface; persistent "n/5" getting-started checklist (banner + modal,
live progress). Why last: worth doing only once the surfaces it teaches
(items 5–9) are in their final shape.

---

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
the route is registered eagerly by name (`frontend/src/router/routes.ts:15`,
`name: "landing"`, moved there from `router/index.ts` at `d18d534`) and only
its component is lazy-loaded, so the route *name* would be in the main bundle
even if the view were code-split — and `index.html` preloads no other chunk.

**This evaluation extracted the deployed route table rather than counting a
string, which settles it.** Every `path:` and `name:` literal in the bundle:
the paths are `/`, `/admin/users`, `/branding`, `/envelopes/:id`, `/login`,
`/privacy`, `/send/draft/:draftId`, `/send/:templateId?`, `/signed-out`,
`/sign/:submitterId`, `/sign/t/:accessUid`, `/templates`,
`/templates/:id/build`, `/terms` and the catch-all — and the route names
include `dashboard` and **not** `landing`. In the deployment, `/` is the
dashboard. One case-insensitive `beta` match exists in the bundle and it is
inside the CSS counter-style name `tibetan`, in a vendored library; the chip
is not there. **`LandingView.vue` has never reached a user**, which is not the
same claim as "its correction is undeployed" — see [`STAGE.md`](STAGE.md) §5,
where that row was wrong and is corrected in this pass.

**B2 · Carry #7's merged fix to the people it is for** — source: issue
[#7](https://github.com/pumasi-ai/pumasi-sign/issues/7) (`accepted`,
`priority: high`), [`STAGE.md`](STAGE.md) §5, `pumasi/DECISIONS.md` **Q-027**.
**New in this reorder.** The build is done and retired below; the user is not
served. Measured by this evaluation on 2026-08-31 at 20:10–20:12 UTC:

```
$ curl -s https://sign.pumasi.ai/ | grep -o '/assets/index-[^"]*\.js'
/assets/index-j38Qwibz.js
$ curl -s -i 'https://sign.pumasi.ai/api/auth/login?next=%2F'
HTTP/2 404
{"error":"Endpoint not found"}
```

and, decisively, **the deployed bundle still contains the helper `d18d534`
deleted.** Extracted from the shipped JavaScript by this evaluation — the
minified `loginRedirectUrl`, sitting beside `loginPageUrl`:

```js
function pl(e){return`/api/auth/login?next=`+encodeURIComponent(e)}
function ml(e){return`/login?next=`+encodeURIComponent(e)}
```

That is not an inference from a filename. It is the removed code, still
shipping.

**Blocked on two entries, not one, and the second one is the finding.**

- **Q-012** — who carries a merged build to users — open, and explicitly
  outside CHARTER Part 0's proceed-on-default rule.
- **Q-021** — the licence — open, **and it binds this deploy too.**
  `service/wrangler.jsonc:8` serves `../frontend/dist` as one `ASSETS`
  directory, and `routes.ts:15` puts `LandingView` at `/`. `frontend/dist` is
  `.gitignore`d and must be rebuilt for the fix to be in it (`CLAUDE.md`: *"a
  stale `dist` ships a stale SPA"*). So **the only build that carries #7's
  repair also publishes `LandingView.vue`'s "Apache-2.0 (Open Source)"**
  (`:43`, `:80`, `:210`) on a repository that still has no `LICENSE`. The two
  cannot be shipped apart without a `frontend/` change nobody has proposed —
  which is Q-021's own named alternative, and is a decision, not a workaround.

Q-021's `Blocks` row names only the deploy that closes #8, because when it was
written #7's repair did not exist. It now holds a live user-facing defect fix
as well. **That is recorded here and raised as `pumasi/DECISIONS.md` Q-028
rather than routed around**; no seat here may weigh a licence question against
a broken sign-in button.

---

## Retired

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

**Retired from the build order, and issue #7 stays open on purpose.** The
*build* is done; the user is not served. `sign.pumasi.ai` still runs the
pre-fix bundle — see [Blocked](#blocked--not-in-the-build-order-until-a-steward-answers)
**B2**, which is new, and [`STAGE.md`](STAGE.md) §5, where this is now the
worked example of *fixed in source and still wrong in production*.

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

**What is carried forward, and it is item 1.** The gate now runs the served
tree; what it runs there is two assertions against one file. `main` is still
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
lineage is item 1: a gate that runs the served tree, over a suite two
assertions wide.

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
runs is now **item 1**, the top of this file.

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
