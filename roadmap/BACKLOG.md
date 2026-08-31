# BACKLOG — what gets built next, in order

**Owned by the product-manager role** ([`pumasi-ops/roles/product-manager.md`](https://github.com/pumasi-ai/pumasi-ops/blob/main/roles/product-manager.md), duty 5).
First pass 2026-08-30, steward-directed: *"introduce very similar UI and UX
[to the incumbent] in pumasi sign — let these items in the queue."*

One list, features and bugs together. Every entry points at its source and
carries one line of why-here. **The top of this file is what the project
manager's next coder packet builds.** Reordering is a commit with the
reasoning in the message; the steward vetoes by reverting.

Context the ordering assumes: UX-parity phase 1 is **delivered** (PR #1,
merged `70c692e`: hero quick actions, self-sign, download picker, thumbnail
rail, field mini-toolbar). The parity source of truth is the clean-room spec
[`docs/ux/incumbent-ux-spec.md`](../docs/ux/incumbent-ux-spec.md) (§ refs
below) with the phase map in
[`docs/ux/similar-ux-plan.md`](../docs/ux/similar-ux-plan.md). **Builders
work from the spec, never from the tour screenshots** (product-hunt
`TOUR.md`, "Studying clean").

---

## The order

**1 · Green main: fix the 4 backend pytest failures** — source: CI on main,
red since the 2026-08-30 auth/external-corp pushes (`test_auth`,
`test_email_login`, `test_users`: `pumasi.ai`→`pumasi.com` domain
expectations; external-signer name validation). Decide which side is right —
the multi-tenant code or the single-tenant tests — and align. Why here: every
later item ships through this gate; a red gate hides new breakage, and no
other entry's "tests pass" claim means anything until it is green.

**2 · Focus-mode shells for prepare / tag / sign** — source: spec §1
(shell 2). Full-screen wizard and signing surfaces: global chrome hidden,
minimal header with close-X (back to origin), step title, primary actions
top-right. Why here: the single largest *perceptual* gap to the incumbent —
every send and every signature passes through these screens.

**3 · One-page accordion envelope setup** — source: spec §4 step 1,
checklist 8. Documents / recipients / message as three collapsible sections
on one page; inline validation on attempted progression; implicit drafts on
close. Replaces paged steps 1–2. Why here: with #2 it completes the
incumbent's prepare flow shape; touching the wizard once for both avoids
rework.

**4 · Tagging-canvas mechanics** — source: spec §4 step 2, checklist 1, 16.
Drag-from-palette with cursor ghost (keep click-to-arm as fallback), zoom
control, undo/redo, field copy/paste, grouped palette; multi-document
envelopes as separate files with per-file thumbnail cards (today: merged to
one PDF at upload — the card UI can front the merge first, true multi-doc
needs backend). Why here: the canvas is "the product" per the spec's own
ranking; do it after #2 so it lands inside the focus shell.

**5 · Signature identity: styles, saved list, frame imprint** — source: spec
§5 adopt modal, §8 signature adoption + framing, checklist 4. "Choose" tab
of generated styles from name/initials (cursive renders, live preview),
multiple saved signature/initials pairs managed in a profile page, and the
"signed by" bracket frame + short envelope/party ID burned into the stamped
PDF behind an account toggle (backend `stamping.py` / worker core). Why
here: this is what makes a signed document *look* like the incumbent's
output — the artifact everyone outside the org actually sees.

**6 · Post-sign share loop** — source: spec §5 finish sequence, checklist
12. After Finish: share-by-email modal (multi-email chips, prefilled
subject, short message with counter), each recipient getting a tokenized
free download link; declining still completes. Why here: cheap, and it is
the incumbent's growth loop — the commons' S8 outward-transmission thesis
for picking this product in the first place.

**7 · Manager depth: bulk, folders, trash, richer filtering** — source: spec
§3, checklist 7, 21. Row checkboxes + bulk bar (download / move / delete),
user folders, a real Deleted view with restore (soft-delete; archive stays
per-user hide), quick-views dropdown, default date-window chip with inline
clear, two-line rows (title over "To: recipients"), density toggle. Why
here: daily-driver ergonomics once volume grows; none of it blocks the
flows above.

**8 · Ceremony options** — source: spec §5, §8 signing settings, checklist
5, 23. Finish-later; configurable consent/disclosure step for remote
recipients (recorded in the certificate); auto-navigation modes
(page-only / required / all). Why here: recipient-facing polish and the
compliance-relevant consent record.

**9 · Field-type parity + per-recipient auth** — source: spec §4 palette,
checklist 17, 18. Email / Company / Title contact fields; Approve / Decline
action buttons; Note; per-recipient "Customize" auth (access code; SMS
later). Payment: explicitly skipped. Why here: each is small and
spec-shaped; batch after the canvas rework so new types land once.

**10 · Template library depth** — source: spec §7, checklist 9. Description
field, favorites, my/shared-with-me groupings, "[Untitled]" implicit
drafts, starter-template gallery. Why here: value scales with template
count, which is still small.

**11 · Admin & records layer** — source: spec §6, §8, checklist 3, 11, 13,
14, 20, 25. Account defaults (reminders/expiration, signing permissions,
date/time regional formats), per-user notification preferences, envelope/
document custom metadata, retention purge, combined-into-one-PDF + zip
download, certificate depth (per-signer viewed timestamps, security level,
adoption method), a Reports section. Why here: a coherent settings-shell
workstream; nothing user-visible upstream depends on it.

**12 · Onboarding polish** — source: spec §2, §9, checklist 15. First-run
coach marks per surface; persistent "n/5" getting-started checklist
(banner + modal, live progress). Why last: worth doing only once the
surfaces it teaches (items 2–5) are in their final shape.

---

Not copied, on purpose: plan-gating/upsell surfaces (Pumasi Sign is
unmetered — that is the pitch), SMS-delivery premium gating, payment
fields, enterprise admin consoles (permission profiles, CORS, API usage).
