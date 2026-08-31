# BACKLOG — what gets built next, in order

**Owned by the product-manager role** ([`pumasi-ops/roles/product-manager.md`](https://github.com/pumasi-ai/pumasi-ops/blob/main/roles/product-manager.md), duty 5).
First pass 2026-08-30, steward-directed: *"introduce very similar UI and UX
[to the incumbent] in pumasi sign — let these items in the queue."*
**Reordered 2026-08-31** after the product evaluation that published
[`STAGE.md`](STAGE.md) and [`VALUE.md`](VALUE.md); the reasoning is in that
commit's message, and the steward vetoes by reverting.

One list, features and bugs together, because a priority that cannot compare
them is not a priority. Every entry points at its source and carries one line
of why-here. **The top of this file is what the project manager's next coder
packet builds.**

Context the ordering assumes: UX-parity phase 1 is **delivered** (PR #1, merged
`70c692e`). The parity source of truth is the clean-room spec
[`docs/ux/incumbent-ux-spec.md`](../docs/ux/incumbent-ux-spec.md) (§ refs
below) with the phase map in
[`docs/ux/similar-ux-plan.md`](../docs/ux/similar-ux-plan.md). **Builders work
from the spec, never from the tour screenshots** (product-hunt `TOUR.md`,
"Studying clean").

**Why the parity items moved down.** They did not lose their mandate; six items
got in front of them. Five are things a real user met or a rule requires, and
one is the gate that makes every "it works" claim below it checkable. Each of
the six is small. The parity work resumes at item 8 and is otherwise untouched.

---

## The order

**1 · Make the landing page true, then let users have it** — source: issue
[#8](https://github.com/pumasi-ai/pumasi-sign/issues/8) (`accepted`,
`priority: high`), [`STAGE.md`](STAGE.md) §2.3, [`MARKET.md`](MARKET.md) §1.
`LandingView.vue` and the public `/` route are merged (`10a523d`) and **the
deployment does not have them** — the live bundle
`/assets/index-j38Qwibz.js` was fetched at HTTP 200 on 2026-08-31 and contains
zero occurrences of `landing`. So #8 closes on a deploy, not a commit. But that
deploy is the moment three unbacked claims on the page become public, so the
build half comes first:
   - **(a)** the `BETA` chip and "in active Beta" banner (`LandingView.vue:34`)
     → the stage this product actually has. `STAGE.md` says `alpha`;
     `STAGE_PLAYBOOK.md`'s own Stage-1 Surface B deliverable asks for
     `[ALPHA - ACTIVE DEVELOPMENT]`.
   - **(b)** "Apache-2.0 (Open Source)" in the banner and the comparison table
     → there is no `LICENSE` file in this repository and GitHub reports no
     licence. Either the file lands (`pumasi/DECISIONS.md` **Q-021**, default:
     add Apache-2.0, matching `pumasi-web` and `pumasi-tunnel`) or the claim
     goes. Do not deploy the claim ahead of the file.
   - **(c)** the uncited competitor pricing → cite `MARKET.md`'s figures or
     drop the rows. Against the vendors' own pages on 2026-08-31 the page's
     "$25 – $65" and "$10 – $30" are wrong at both ends. Precedent for removal
     rather than argument: `pumasi-booking` `0d1674d`.
   - **(d)** then deploy — `wrangler deploy` from `service/`, **not** the
     Railway path `CLAUDE.md` describes (Q-018). Note that the same deploy
     carries ~5 commits of unreviewed UX change; it should be deliberate, not
     incidental.
Why here: it is the oldest open high-priority defect, the fix is already
written, and every day it waits the app root shows strangers nothing. **Whose
hand runs (d) is `pumasi/DECISIONS.md` Q-012, still open** — (a)–(c) need no
deploy decision to be written, reviewed and merged, so a coder packet that
cannot deploy still delivers this item's build half and says so.

**2 · Make the gate cover the tree users actually meet** — source:
`pumasi/DECISIONS.md` **Q-018** parts (a) and (b), [`STAGE.md`](STAGE.md) §2.1.
`.github/workflows/ci.yaml` contains no occurrence of `service`. Measured
2026-08-31: `backend/` has 541 test functions (545 collected) and the e2e job
drives 6 Playwright specs — all on a tree no user reaches — while `service/`,
which serves `sign.pumasi.ai`, has **2 tests** and no CI job. (a) `CLAUDE.md`
stops calling Railway/FastAPI *the* deployment and names the worker; (b) CI
gains a job running `service/src/test/`. Neither deletes anything or re-points
anything — those parts of Q-018 stay the steward's. Why here: this is
[L-006](https://github.com/pumasi-ai/governance/blob/main/lessons/L-006-tests-that-cannot-fail.md)
at suite scale, and until it is done every later entry's "tests pass" means
nothing about production. Ranked first by coder job `0018`; it sits at 2 only
because item 1 is already built and users are looking at the gap today.

**3 · #7: "sign in again" gives an error — explain it on the deployed tree** —
source: issue [#7](https://github.com/pumasi-ai/pumasi-sign/issues/7)
(`accepted`, `priority: high`). `SignedOutView.vue`'s button resolves through
`utils/http.ts:30` to `/api/auth/login?next=/`. It was provisionally linked to
#9; #9 is now closed as another product's defect, which removes the
explanation and leaves this report standing with no cause. Reproduce against
`sign.pumasi.ai` (the worker), not against a local FastAPI run — that is the
mistake this backlog is now shaped to prevent. Why here: a signed-out user who
cannot get back in is the plainest counterexample to the next stage's whole
promise.

**4 · #6: the branding colour buttons touch** — source: issue
[#6](https://github.com/pumasi-ai/pumasi-sign/issues/6) (`accepted`,
`priority: normal`). `BrandingView.vue:113`, `:128`, `:142` use `gap-2` /
`gap-3`. This frontend has no Tailwind — Vuetify `^3.13.0` only, whose utility
is `ga-*`; `.ga-2` is in `vuetify.css` and `.gap-2` is not, and the sole
`.gap-2` in the repository is inside a `<style scoped>` block in
`LandingView.vue`. The classes are inert on `/branding`. Why here: three
characters, a real user noticed, and it ships free alongside anything else.

**5 · The feedback screenshot must be attached, not pre-attached** — source:
`PRODUCT-RULES.md` **PR-2** (v1.0, read from `pumasi` branch
`worktree-product-rules` `0115758`; not on `pumasi` main — that is Q-017, and
absence from main is not compliance), CHARTER §5.2.
`FeedbackDialog.vue:188` auto-captures the page and pre-attaches it; PR-2 says
"a screenshot travels only when the user attaches one". The user sees it and
can remove it, so today this is opt-out and informed — but in an e-signature
product the page being captured is somebody's contract, and §5.2 says *never
the user's own material*. Make it a button the user presses. Why here: PR-2
binds at the `beta` promotion, this is the only clause it fails, and it is
cheaper to fix now than to hold a promotion for.

**6 · One version number, and put it in the reports** — source:
`PRODUCT-RULES.md` **PR-1**, which binds *always, from the first commit*, and
is not met. There is no root `package.json`; `frontend/package.json` reads
`0.0.0` and `service/package.json` reads `0.1.0` (two hand-maintained copies —
L-007); no version is visible to a user anywhere; there is no `/version`
endpoint; and `FeedbackDialog.vue::buildContext` sends page, browser, platform,
viewport and timezone but not the version. Why here: all six issues in this
backlog are defect reports without a version, which is a request to guess, and
the fix is one source of truth plus two readers.

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

## Retired

**~~Green main: fix the 4 backend pytest failures~~ — met 2026-08-31.** Was
item 1. CI run
[33410370102](https://github.com/pumasi-ai/pumasi-sign/actions/runs/33410370102)
at `5cb3bf8`: `backend` ✓, `frontend` ✓, `e2e` ✓ (coder job `0018`; the four
failures were single-tenant expectations against multi-tenant normalization,
`1c8590d`, and `e2e` had two further causes, `5cb3bf8`). Retired rather than
deleted, with one thing carried forward: **that gate covers `backend/`, which
is not what users reach.** The re-sourced version of this entry's purpose —
*a gate whose green means something* — is now item 2.

---

Not copied, on purpose: plan-gating/upsell surfaces (Pumasi Sign is unmetered —
that is the pitch), SMS-delivery premium gating, payment fields, enterprise
admin consoles (permission profiles, CORS, API usage).
